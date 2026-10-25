"""统一路径解析与历史绝对路径迁移。

目标：整个项目可以整目录搬到任意机器 / 任意路径（含云主机）后直接可用。
- 所有持久化下来的路径一律写成「相对项目根」的形式（如 part2-empirical-research/data/uploads/xxx.csv）；
- 读取时统一用 abs_path() 还原成当前机器的绝对路径；
- 若库中还残留旧机器的绝对路径，启动时 migrate_legacy_paths() 会把旧根前缀替换成当前根。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Union

# 项目根：core/ 的上一级；可用环境变量 ACA_ROOT 覆盖（容器里常挂在 /app）
INTEGRATED_ROOT = Path(os.environ.get("ACA_ROOT") or Path(__file__).resolve().parents[1]).resolve()

# 旧机器/旧部署上遗留的绝对路径形如：... 或 ...
# 迁移目标统一为「相对项目根」，这样换机器也能直接解析
_LEGACY_RE = re.compile(r"/Users/(?:[^/\s\"']+/)*?整合版本/")
_LEGACY_WIN_RE = re.compile(r"[A-Za-z]:[\\/](?:[^\\/\s\"']+[\\/])*?整合版本[\\/]")

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".idea", ".vscode", "_ai_temp",
}
_TEXT_SUFFIX = {".json", ".md", ".txt", ".csv", ".yaml", ".yml", ".py", ".html", ".js", ".css"}


def to_rel(p: Union[str, Path]) -> str:
    """绝对路径 → 相对项目根（POSIX 风格）；不在项目根内的原样返回。"""
    if not p:
        return ""
    s = str(p)
    try:
        rp = Path(s).resolve().relative_to(INTEGRATED_ROOT)
        return rp.as_posix()
    except Exception:
        # 不在项目根下：退而求其次，尽量截出「整合版本/之后」的部分
        m = re.search(r"整合版本[/\\](.+)$", s)
        return m.group(1).replace("\\", "/") if m else s


def abs_path(p: Union[str, Path]) -> str:
    """任意写法（相对/旧的绝对路径）→ 当前机器上可用的绝对路径。"""
    if not p:
        return ""
    s = str(p)
    if s.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", s):
        if os.path.exists(s):
            return s
        # 旧机器的绝对路径：截出项目内相对部分后重新挂到当前根
        m = re.search(r"整合版本[/\\](.+)$", s)
        if m:
            return str(INTEGRATED_ROOT / m.group(1).replace("\\", "/"))
        return s
    return str(INTEGRATED_ROOT / s)


def _rewrite_file(path: Path) -> int:
    """把单个文本文件里的绝对路径改写成相对项目根；返回是否发生过改动。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    new = raw
    # 文档中 file:///旧绝对路径/... → 相对路径
    new = re.sub(r"file://" + _LEGACY_RE.pattern, "", new)
    # 当前项目根的绝对路径 → 相对路径
    cur = str(INTEGRATED_ROOT).replace("\\", "/")
    new = new.replace(cur + "/", "").replace(cur, "")
    # 其它机器上的历史绝对路径 → 相对路径
    new = _LEGACY_RE.sub("", new)
    new = _LEGACY_WIN_RE.sub("", new)
    if new == raw:
        return 0
    path.write_text(new, encoding="utf-8")
    return 1


def _rel_text(s: str) -> str:
    """把一段文本里的项目绝对路径（当前机器或历史机器）改写成相对路径。"""
    if not isinstance(s, str):
        return s
    cur = str(INTEGRATED_ROOT).replace("\\", "/")
    out = s.replace(cur + "/", "")
    out = _LEGACY_RE.sub("", out)
    out = _LEGACY_WIN_RE.sub("", out)
    return out


def _rewrite_sqlite(db: Path) -> int:
    """SQLite 中所有文本列里的项目绝对路径 → 相对路径。"""
    if not db.exists():
        return 0
    total = 0
    try:
        con = sqlite3.connect(str(db))
        con.create_function("aca_rel", 1, _rel_text)   # 注册到 SQL 里用
        cur = con.cursor()
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
            for c in cols:
                try:
                    cur.execute(
                        f'UPDATE "{t}" SET "{c}" = aca_rel("{c}") '
                        f'WHERE "{c}" LIKE ?', ("%整合版本%",),
                    )
                    total += cur.rowcount or 0
                except Exception:
                    continue
        con.commit()
        con.close()
    except Exception:
        return total
    return total


def migrate_legacy_paths() -> dict:
    """启动时调用：清理历史绝对路径。返回统计信息。"""
    stats = {"files": 0, "sqlite": 0, "skipped": 0}
    for dirpath, dirnames, filenames in os.walk(INTEGRATED_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for n in filenames:
            p = Path(dirpath) / n
            if p.suffix.lower() == ".db" or p.name.endswith(".sqlite3"):
                stats["sqlite"] += _rewrite_sqlite(p)
                continue
            if p.suffix.lower() in _TEXT_SUFFIX:
                if p.stat().st_size > 20 * 1024 * 1024:
                    stats["skipped"] += 1
                    continue
                stats["files"] += _rewrite_file(p)
    return stats


def ensure_dir(p: Union[str, Path]) -> Path:
    d = Path(abs_path(p))
    d.mkdir(parents=True, exist_ok=True)
    return d
