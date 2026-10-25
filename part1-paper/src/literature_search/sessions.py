from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime import WORKSPACE_ROOT


SESSION_ROOT = WORKSPACE_ROOT / "_ai_temp" / "literature-search-sessions"
SESSION_DB = SESSION_ROOT / "sessions.sqlite3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SESSION_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS search_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            research_question TEXT NOT NULL,
            working_query TEXT NOT NULL,
            mode TEXT NOT NULL,
            ranking TEXT NOT NULL,
            source_ids_json TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            open_pdf_count INTEGER NOT NULL,
            result_path TEXT NOT NULL,
            result_sha256 TEXT NOT NULL
        )
    """)
    return connection


def save_session(result: dict[str, Any], parameters: dict[str, Any], session_id: str | None = None) -> str:
    session_id = session_id or f"ls-{uuid.uuid4().hex[:12]}"
    result["session_id"] = session_id
    rendered = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    path = SESSION_ROOT / f"{session_id}.json"
    path.write_bytes(rendered)
    with closing(_connect()) as connection:
        with connection:
            connection.execute("""
                INSERT OR REPLACE INTO search_sessions (
                    session_id, created_at, research_question, working_query, mode, ranking,
                    source_ids_json, record_count, open_pdf_count, result_path, result_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, result.get("created_at") or _now(), parameters.get("research_question") or result.get("input_summary") or "",
                parameters.get("query") or "", parameters.get("mode") or "exploratory", parameters.get("ranking") or "combined",
                json.dumps(result.get("source_ids") or []), len(result.get("records") or []),
                sum(bool(record.get("open_access_pdf_url")) for record in result.get("records") or []),
                str(path), hashlib.sha256(rendered).hexdigest(),
            ))
    return session_id


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT * FROM search_sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [
        {
            "session_id": row["session_id"], "created_at": row["created_at"],
            "research_question": row["research_question"], "working_query": row["working_query"],
            "mode": row["mode"], "ranking": row["ranking"],
            "source_ids": json.loads(row["source_ids_json"]), "record_count": row["record_count"],
            "open_pdf_count": row["open_pdf_count"], "result_sha256": row["result_sha256"],
        }
        for row in rows
    ]


def load_session(session_id: str) -> dict[str, Any]:
    if not re_safe_id(session_id):
        raise ValueError("检索会话 ID 无效。")
    path = SESSION_ROOT / f"{session_id}.json"
    if not path.exists():
        raise ValueError("没有找到该检索会话。")
    return json.loads(path.read_text(encoding="utf-8"))


def update_screening(session_id: str, record_id: str, status: str, reason: str | None) -> dict[str, Any]:
    if status not in {"unscreened", "include", "maybe", "exclude"}:
        raise ValueError("筛选状态无效。")
    result = load_session(session_id)
    record = next((item for item in result.get("records", []) if item.get("record_id") == record_id), None)
    if record is None:
        raise ValueError("检索会话中没有找到该文献。")
    record["screening_status"] = status
    record["screening_reason"] = (reason or "").strip() or None
    records = result.get("records") or []
    metrics = result.setdefault("search_metrics", {})
    metrics.update({
        "records_screened": sum(item.get("screening_status") != "unscreened" for item in records),
        "records_included": sum(item.get("screening_status") == "include" for item in records),
        "records_excluded": sum(item.get("screening_status") == "exclude" for item in records),
        "records_maybe": sum(item.get("screening_status") == "maybe" for item in records),
    })
    parameters = result.get("search_parameters") or {
        "research_question": result.get("input_summary"), "query": "", "mode": "exploratory", "ranking": "combined"
    }
    save_session(result, parameters, session_id)
    return record


def re_safe_id(value: str) -> bool:
    return bool(value) and value.startswith("ls-") and value[3:].isalnum()
