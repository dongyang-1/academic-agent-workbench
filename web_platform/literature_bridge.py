# -*- coding: utf-8 -*-
"""
Part 1 文献检索能力桥接层

part1-paper 自带一套 :8765 的独立前端。本模块把它的真实能力（检索方案生成、
多源检索、质量分级、导出、Zotero 写入）直接接进 :8088 主平台，
使 :8088 成为唯一入口，:8765 不必再单独启动。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aca.literature_bridge")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
PART1_SRC = INTEGRATED_ROOT / "part1-paper" / "src"

_loaded: Dict[str, Any] = {}
_error: Optional[str] = None


def _load() -> Dict[str, Any]:
    """延迟导入 part1 的实现；失败时保留错误信息而不是静默降级。"""
    global _error
    if _loaded or _error:
        return _loaded
    if not PART1_SRC.exists():
        _error = f"未找到 part1 源码目录: {PART1_SRC}"
        return {}
    if str(PART1_SRC) not in sys.path:
        sys.path.insert(0, str(PART1_SRC))
    try:
        from literature_search.web import (  # type: ignore
            generate_search_protocol,
            run_search,
            translate_research_question,
        )
        from literature_search.formats import export_records  # type: ignore
        from literature_search.sessions import list_sessions, load_session, update_screening  # type: ignore
        from literature_search.zotero import (  # type: ignore
            local_zotero_status,
            save_records_to_zotero,
            zotero_configuration,
        )
        from literature_search.runtime import AVAILABLE_SOURCES  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _error = f"Part 1 能力加载失败: {exc}"
        logger.warning(_error)
        return {}
    _loaded.update({
        "generate_search_protocol": generate_search_protocol,
        "run_search": run_search,
        "translate_research_question": translate_research_question,
        "export_records": export_records,
        "list_sessions": list_sessions,
        "load_session": load_session,
        "update_screening": update_screening,
        "local_zotero_status": local_zotero_status,
        "save_records_to_zotero": save_records_to_zotero,
        "zotero_configuration": zotero_configuration,
        "AVAILABLE_SOURCES": AVAILABLE_SOURCES,
    })
    return _loaded


def status() -> Dict[str, Any]:
    """桥接层与本机 Zotero 的可用状态"""
    api = _load()
    if not api:
        return {"available": False, "error": _error}
    try:
        zotero = api["zotero_configuration"]()
        live = api["local_zotero_status"]()
    except Exception as exc:  # noqa: BLE001
        zotero, live = {"available": False}, {"available": False, "error": str(exc)}
    return {
        "available": True,
        "sources": list(api.get("AVAILABLE_SOURCES") or []),
        "zotero": zotero,
        "zotero_live": live,
    }


def _require() -> Dict[str, Any]:
    api = _load()
    if not api:
        raise RuntimeError(_error or "Part 1 能力不可用")
    return api


def protocol(research_question: str) -> Dict[str, Any]:
    api = _require()
    return api["generate_search_protocol"](research_question)


def translate(research_question: str) -> Dict[str, Any]:
    api = _require()
    return api["translate_research_question"](research_question)


def search(payload: Dict[str, Any]) -> Dict[str, Any]:
    api = _require()
    return api["run_search"](payload)


def export(records: List[Dict[str, Any]], fmt: str = "ris") -> Dict[str, Any]:
    api = _require()
    content, content_type, extension = api["export_records"](list(records)[:500], fmt)
    return {"content": content, "content_type": content_type, "extension": extension, "n_records": min(len(records), 500)}


def screening(session_id: str, record_id: str, decision: str, reason: Optional[str] = None) -> Dict[str, Any]:
    api = _require()
    return api["update_screening"](session_id, record_id, decision, reason)


def sessions() -> List[Dict[str, Any]]:
    api = _require()
    return api["list_sessions"]()


def session_detail(session_id: str) -> Dict[str, Any]:
    api = _require()
    return api["load_session"](session_id)


def zotero_status() -> Dict[str, Any]:
    api = _require()
    return {
        "config": api["zotero_configuration"](),
        "live": api["local_zotero_status"](),
    }


def zotero_save(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    api = _require()
    return api["save_records_to_zotero"](list(records))
