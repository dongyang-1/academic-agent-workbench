# -*- coding: utf-8 -*-
"""
Zotero 写入桥接

part1 的 zotero.py 已经写好了 Connector 通道（/connector/saveItems），但有两个
现实缺口，本模块补上：

1. 状态不明：Zotero 没启动 / 没开启"允许本机其他应用与 Zotero 通信"时，
   界面只显示"未检测"，用户不知道该点哪里。这里给出可执行的分步指引。
2. 写不到指定分类：Connector 通道只会写进 Zotero 当前选中的分类。
   做课题的人通常有固定分类库（如"成本绩效""零基预算下的城市维运"），
   因此额外支持 Local API 通道：拿到 API key 后可列出分类并写入指定集合。

两条通道都建立在本机 127.0.0.1:23119 上，不外发任何数据。
API key 只写进 ~/.aca/secrets.json（600 权限），不进项目目录。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aca.zotero_bridge")

LOCAL_BASE = "http://127.0.0.1:23119"
USER_AGENT = "economics-research-agent/0.3 (non-commercial research prototype)"
TIMEOUT = 8

# 写入 ~/.aca/secrets.json，与 LLM key 同一处、同一权限
SECRETS_FILE = Path.home() / ".aca" / "secrets.json"


def _opener():
    """本机请求必须绕开系统代理，否则会被 127.0.0.1 的代理规则拦掉"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _request(url: str, method: str = "GET", body: Optional[bytes] = None,
             headers: Optional[Dict[str, str]] = None, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    with _opener().open(req, timeout=timeout) as resp:
        return resp.status, resp.read()


# ---------------------------------------------------------------------------
# 配置持久化
# ---------------------------------------------------------------------------

def _read_secrets() -> Dict[str, Any]:
    try:
        if SECRETS_FILE.exists():
            return json.loads(SECRETS_FILE.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取密钥库失败: %s", exc)
    return {}


def _write_secrets(data: Dict[str, Any]) -> None:
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import os
        import stat
        os.chmod(SECRETS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:  # noqa: BLE001
        pass


def get_config() -> Dict[str, Any]:
    data = _read_secrets()
    key = data.get("zotero_api_key") or ""
    return {
        "api_key_set": bool(key),
        "api_key_masked": (f"{key[:4]}****{key[-4:]}" if len(key) > 8 else ("*" * len(key) if key else "")),
        "default_collection": data.get("zotero_default_collection") or "",
        "secrets_path": str(SECRETS_FILE),
    }


def set_config(api_key: Optional[str] = None, default_collection: Optional[str] = None) -> Dict[str, Any]:
    data = _read_secrets()
    if api_key is not None:
        if api_key.strip():
            data["zotero_api_key"] = api_key.strip()
        else:
            data.pop("zotero_api_key", None)
    if default_collection is not None:
        if str(default_collection).strip():
            data["zotero_default_collection"] = str(default_collection).strip()
        else:
            data.pop("zotero_default_collection", None)
    _write_secrets(data)
    return get_config()


# ---------------------------------------------------------------------------
# 状态检测与指引
# ---------------------------------------------------------------------------

ENABLE_STEPS = [
    "打开 Zotero（本机已安装，当前未运行）",
    "Zotero → 设置（偏好设置）→ 高级 → 勾选「允许本机其他应用与 Zotero 通信」",
    "回到本页点「🔄 Zotero 状态」重新检测",
    "若要写入指定分类库，再在 设置 → 高级 → 本地 API 里开启并生成 API key，填入下方",
]


def status() -> Dict[str, Any]:
    """同时探测 Connector 通道与 Local API 通道"""
    out: Dict[str, Any] = {
        "connector": {"available": False, "version": None},
        "local_api": {"available": False, "reason": None},
        "config": get_config(),
        "enable_steps": ENABLE_STEPS,
    }

    # Connector 通道（免 key，写进当前选中分类）
    try:
        code, _ = _request(
            f"{LOCAL_BASE}/connector/ping",
            headers={"User-Agent": USER_AGENT, "X-Zotero-Connector-API-Version": "3"},
            timeout=3,
        )
        out["connector"] = {"available": code == 200, "version": None, "http_code": code}
    except Exception as exc:  # noqa: BLE001
        out["connector"] = {"available": False, "version": None, "error": str(exc)[:120]}

    # Local API 通道（需 key，可写指定分类）
    key = _read_secrets().get("zotero_api_key") or ""
    if not key:
        out["local_api"] = {"available": False, "reason": "未配置 Zotero API key"}
        return out
    try:
        code, body = _request(
            f"{LOCAL_BASE}/api/users/0/groups?limit=1",
            headers={"User-Agent": USER_AGENT, "Zotero-API-Key": key},
            timeout=4,
        )
        out["local_api"] = {"available": code == 200, "http_code": code}
    except Exception as exc:  # noqa: BLE001
        out["local_api"] = {"available": False, "reason": str(exc)[:160]}
    return out


def collections() -> Dict[str, Any]:
    """列出本机 Zotero 分类库（需要 API key）"""
    key = _read_secrets().get("zotero_api_key") or ""
    if not key:
        return {"collections": [], "error": "未配置 Zotero API key，无法列出分类库"}
    try:
        code, body = _request(
            f"{LOCAL_BASE}/api/users/0/collections?limit=200",
            headers={"User-Agent": USER_AGENT, "Zotero-API-Key": key},
            timeout=6,
        )
        data = json.loads(body.decode("utf-8", "ignore"))
    except Exception as exc:  # noqa: BLE001
        return {"collections": [], "error": str(exc)[:200]}
    out = []
    for item in data:
        d = item.get("data") or {}
        out.append({
            "key": d.get("key"),
            "name": d.get("name"),
            "parent": d.get("parentCollection"),
            "n_items": (item.get("meta") or {}).get("numItems"),
        })
    return {"collections": out}


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------

def save_via_connector(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """走 Connector 通道：写进 Zotero 当前选中的分类，无需 key"""
    from literature_bridge import _require  # 复用 part1 已实现且测过的逻辑
    api = _require()
    return api["save_records_to_zotero"](list(records))


def save_via_api(records: List[Dict[str, Any]], collection_key: str = "") -> Dict[str, Any]:
    """走 Local API 通道：写进指定分类"""
    key = _read_secrets().get("zotero_api_key") or ""
    if not key:
        raise RuntimeError("未配置 Zotero API key")
    if not records:
        raise ValueError("请至少选择一条文献")

    from literature_search.zotero import record_to_zotero_item  # type: ignore
    from literature_bridge import PART1_SRC  # type: ignore
    import sys
    if str(PART1_SRC) not in sys.path:
        sys.path.insert(0, str(PART1_SRC))

    items = []
    for i, rec in enumerate(records):
        item = record_to_zotero_item(rec, f"api-{i}")
        item.pop("attachments", None)
        if collection_key:
            item["collections"] = [collection_key]
        items.append(item)

    body = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    code, resp = _request(
        f"{LOCAL_BASE}/api/users/0/items",
        method="POST",
        body=body,
        headers={
            "User-Agent": USER_AGENT,
            "Zotero-API-Key": key,
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if code not in (200, 201):
        raise RuntimeError(f"Zotero 拒绝写入（HTTP {code}）：{resp.decode('utf-8', 'ignore')[:200]}")
    try:
        payload = json.loads(resp.decode("utf-8", "ignore"))
    except Exception:  # noqa: BLE001
        payload = {}
    n_ok = sum(1 for k, v in (payload.get("success") or {}).items()) if isinstance(payload.get("success"), dict) else len(records)
    return {
        "mode": "local-api",
        "collection": collection_key or "（未指定分类）",
        "n_requested": len(records),
        "n_created": n_ok or len(records),
        "failed": payload.get("failed") or {},
    }


def save(records: List[Dict[str, Any]], collection_key: str = "") -> Dict[str, Any]:
    """优先写指定分类（API 通道）；没有 key 时退回 Connector 通道"""
    if not records:
        raise ValueError("请至少选择一条文献")
    key = _read_secrets().get("zotero_api_key") or ""
    if key and collection_key:
        return save_via_api(records, collection_key)
    if key and not collection_key:
        # 有 key 但用户没挑分类：写到库根
        return save_via_api(records, "")
    return save_via_connector(records)
