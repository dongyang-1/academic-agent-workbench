# -*- coding: utf-8 -*-
"""
统一状态持久化层 (SQLite)

解决的问题：
    整改前所有会话状态存放在 web_platform 的内存 dict `active_sessions` 中，
    服务重启即全部丢失，且没有任何运行留痕可供回溯"某次结论是怎么算出来的"。

职责：
    - runs          一次流水线/子智能体调用的主记录（含策略链与最终审稿判定）
    - run_steps     每一次策略尝试的留痕（回环诊断的关键证据）
    - artifacts     产出物索引（三线表 / 图 / 正文 md / 报告）
    - sessions      前端会话上下文（替代内存 dict，重启可恢复）
    - token_usage   Token 消耗累计（不再预置假数字）

所有写入均为"幂等 upsert"，重复调用不会产生重复行。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("aca.store")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = INTEGRATED_ROOT / "data" / "aca_state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    session_id      TEXT,
    project_id      TEXT,
    research_topic  TEXT,
    status          TEXT,
    strategy_used   TEXT,
    strategy_chain  TEXT,
    verdict         TEXT,
    task_json       TEXT,
    result_json     TEXT,
    error           TEXT,
    att_coef        REAL,
    att_se          REAL,
    att_p           REAL,
    attempts        INTEGER,
    skill_trace     TEXT,
    created_at      REAL,
    updated_at      REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at);

CREATE TABLE IF NOT EXISTS run_steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    seq         INTEGER,
    stage       TEXT,
    strategy    TEXT,
    status      TEXT,
    verdict     TEXT,
    reasons     TEXT,
    payload_json TEXT,
    created_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_steps_run ON run_steps(run_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    kind        TEXT,
    name        TEXT,
    path        TEXT,
    meta_json   TEXT,
    created_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    project_id  TEXT,
    state_json  TEXT,
    created_at  REAL,
    updated_at  REAL
);

CREATE TABLE IF NOT EXISTS token_usage (
    session_id      TEXT PRIMARY KEY,
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    call_count      INTEGER DEFAULT 0,
    updated_at      REAL
);

CREATE TABLE IF NOT EXISTS kv (
    key         TEXT PRIMARY KEY,
    value_json  TEXT,
    updated_at  REAL
);
"""


def _now() -> float:
    return time.time()


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return "{}"


class Store:
    """轻量 SQLite 状态仓库（线程安全）"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()
        logger.info("状态库已就绪: %s", self.db_path)

    def _migrate(self) -> None:
        """增量迁移：为旧库补齐后加的列，避免重建数据库丢失历史留痕"""
        additions = {
            "runs": {
                "att_coef": "REAL", "att_se": "REAL", "att_p": "REAL",
                "attempts": "INTEGER", "skill_trace": "TEXT",
            },
        }
        for table, cols in additions.items():
            existing = {
                r["name"]
                for r in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for col, decl in cols.items():
                if col not in existing:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                    logger.info("状态库迁移：%s 新增列 %s", table, col)

    # ------------------------------------------------------------------ runs
    def create_run(
        self,
        run_id: str,
        session_id: str = "",
        project_id: str = "",
        research_topic: str = "",
        task: Optional[Dict[str, Any]] = None,
        strategy_chain: Optional[Iterable[str]] = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO runs
                   (run_id, session_id, project_id, research_topic, status,
                    strategy_used, strategy_chain, verdict, task_json, result_json,
                    error, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, session_id, project_id, research_topic, "running",
                    "", _json(list(strategy_chain or [])), "", _json(task or {}),
                    "{}", "", _now(), _now(),
                ),
            )
            self._conn.commit()

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "status", "strategy_used", "verdict", "result_json", "error",
            "research_topic", "session_id", "project_id", "strategy_chain", "task_json",
            # 结果摘要：供前端运行留痕直接展示，无需解析 result_json
            "att_coef", "att_se", "att_p", "attempts", "skill_trace",
        }
        cols, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            cols.append(f"{k}=?")
            if k.endswith("_json") or k == "skill_trace":
                vals.append(_json(v))
            elif isinstance(v, (list, tuple, dict)):
                vals.append(_json(v))
            else:
                vals.append(v)
        if not cols:
            return
        cols.append("updated_at=?")
        vals.append(_now())
        vals.append(run_id)
        with self._lock:
            self._conn.execute(f"UPDATE runs SET {','.join(cols)} WHERE run_id=?", vals)
            self._conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            if session_id:
                rows = self._conn.execute(
                    "SELECT * FROM runs WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- run_steps
    def add_step(
        self,
        run_id: str,
        stage: str,
        strategy: str = "",
        status: str = "",
        verdict: str = "",
        reasons: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self._lock:
            seq = self._conn.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM run_steps WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            cur = self._conn.execute(
                """INSERT INTO run_steps
                   (run_id, seq, stage, strategy, status, verdict, reasons, payload_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (run_id, seq, stage, strategy, status, verdict,
                 _json(reasons or []), _json(payload or {}), _now()),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_steps(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM run_steps WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- artifacts
    def add_artifact(self, run_id: str, kind: str, name: str, path: str,
                     meta: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO artifacts (run_id, kind, name, path, meta_json, created_at) VALUES (?,?,?,?,?,?)",
                (run_id, kind, name, path, _json(meta or {}), _now()),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM artifacts WHERE run_id=? ORDER BY id", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------- sessions
    def save_session(self, session_id: str, state: Dict[str, Any], project_id: str = "") -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO sessions (session_id, project_id, state_json, created_at, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     state_json=excluded.state_json,
                     project_id=excluded.project_id,
                     updated_at=excluded.updated_at""",
                (session_id, project_id, _json(state), _now(), _now()),
            )
            self._conn.commit()

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT state_json FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["state_json"])
        except Exception:  # noqa: BLE001
            return None

    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT session_id, project_id, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        """删除单个会话（项目删除时一并清理）"""
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            self._conn.commit()

    def delete_sessions_by_project(self, project_id: str) -> int:
        """删除某项目下的全部会话，返回删除条数"""
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE project_id=?", (project_id,))
            self._conn.commit()
            return cur.rowcount or 0

    # ------------------------------------------------------------ token usage
    def set_kv(self, key: str, value: Any) -> None:
        """通用键值存储（用于项目库等小型全局状态）"""
        with self._lock:
            self._conn.execute(
                """INSERT INTO kv (key, value_json, updated_at) VALUES (?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (key, _json(value), _now()),
            )
            self._conn.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value_json"])
        except Exception:  # noqa: BLE001
            return default
    def add_token_usage(self, session_id: str, prompt: int = 0, completion: int = 0) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO token_usage (session_id, prompt_tokens, completion_tokens, total_tokens, call_count, updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     prompt_tokens=prompt_tokens+excluded.prompt_tokens,
                     completion_tokens=completion_tokens+excluded.completion_tokens,
                     total_tokens=total_tokens+excluded.total_tokens,
                     call_count=call_count+excluded.call_count,
                     updated_at=excluded.updated_at""",
                (session_id, prompt, completion, prompt + completion, 1, _now()),
            )
            self._conn.commit()

    def get_token_usage(self, session_id: str) -> Dict[str, int]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM token_usage WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "call_count": 0}
        return {k: row[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens", "call_count")}


# 全局单例
store = Store()
