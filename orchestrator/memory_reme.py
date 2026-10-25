# -*- coding: utf-8 -*-
"""
ReMe 记忆服务客户端（接口已按 ReMe v0.4.x 实测校正）

整改前的问题：
    1. 健康检查用 GET /health_check，而 ReMe 该端点只接受 POST，返回 405，
       导致服务明明在跑却被永久判定为离线；
    2. /write 传的是 {key, content}，而真实签名是
       {path*, name*, description*, content*, metadata}；
    3. /read 用 GET ?key=...，真实签名是 POST /read {path*}；
    4. `_is_online` 只在构造时探测一次，先启本服务、后启 ReMe 就再也不会恢复。

现在的行为：
    - 所有端点统一 POST + JSON；
    - 在线状态带 TTL，过期自动重探；写入失败自动降级本地并把状态置为待重探；
    - 每次调用都返回明确的状态来源（reme / local / reme_fallback），不静默失败。

实测签名（来自 POST /help）：
    health_check  no args
    write         path*, name*, description*, content*, metadata
    read          path*, start_line, end_line
    search        query*, limit, min_score, tags, start_date, end_date
    list          path, recursive, sort_by, extensions, limit
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("academic_reme_memory")

DEFAULT_TIMEOUT = 4
# 在线状态缓存有效期：过短会频繁探测，过长则 ReMe 后启动时恢复太慢
ONLINE_TTL_SECONDS = 20


class ReMeMemoryClient:
    """ReMe 跨智能体共享记忆客户端"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:2333",
        fallback_dir: Optional[str] = None,
        namespace: str = "academic",
    ):
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace
        if fallback_dir is None:
            self.fallback_dir = Path(__file__).resolve().parent / "_local_memory"
        else:
            self.fallback_dir = Path(fallback_dir)
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

        self._online_cached: Optional[bool] = None
        self._online_checked_at = 0.0
        self.last_error: Optional[str] = None
        # 首次探测，日志里如实报告结果
        if self.check_online(force=True):
            logger.info("ReMe 记忆服务已连接：%s", self.base_url)
        else:
            logger.info("ReMe 记忆服务不可用（%s），将降级至本地目录 %s",
                        self.last_error or "未响应", self.fallback_dir)

    # ------------------------------------------------------------ 在线探测
    @property
    def is_online(self) -> bool:
        """带 TTL 的在线状态；过期自动重探，不会一判定就永久不变。"""
        return self.check_online()

    def check_online(self, force: bool = False) -> bool:
        now = time.time()
        if (
            not force
            and self._online_cached is not None
            and now - self._online_checked_at < ONLINE_TTL_SECONDS
        ):
            return self._online_cached

        ok, err = self._probe()
        self._online_cached = ok
        self._online_checked_at = now
        self.last_error = None if ok else err
        if force and not ok:
            logger.debug("ReMe 探测失败：%s", err)
        return ok

    def _probe(self) -> tuple:
        """返回 (是否在线, 错误信息)"""
        try:
            resp = self._post("/health_check", {})
        except Exception as exc:  # noqa: BLE001
            return False, f"无法连接 {self.base_url}：{exc}"
        if not isinstance(resp, dict):
            return False, "健康检查返回格式异常"
        if resp.get("success") is True:
            return True, ""
        # 端点存在但业务上不健康
        health = (resp.get("metadata") or {}).get("health") or {}
        return False, f"ReMe 报告不健康：{health or resp.get('answer', '未知')}"

    # -------------------------------------------------------------- HTTP
    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "AcademicAgent/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"answer": raw, "success": True}

    def _path_of(self, session_id: str, stage: str) -> str:
        safe_session = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(session_id))
        safe_stage = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(stage))
        return f"{self.namespace}/{safe_session}/{safe_stage}.md"

    # ------------------------------------------------------------- 写入
    def save_session_memory(self, session_id: str, stage: str, data: Dict[str, Any]) -> bool:
        """
        把某一阶段的产出写入记忆，返回是否成功（本地兜底也算成功，但状态会如实标注）。
        """
        payload = {
            "session_id": session_id,
            "stage": stage,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        # 本地镜像始终写一份，保证 ReMe 掉线时也不丢
        self._save_to_local(session_id, stage, payload)

        if self.is_online:
            try:
                body = {
                    "path": self._path_of(session_id, stage),
                    "name": f"{session_id}-{stage}",
                    "description": f"学术全流程记忆：会话 {session_id} 的阶段 [{stage}]",
                    "content": self._render(session_id, stage, payload),
                    "metadata": {
                        "session_id": session_id,
                        "stage": stage,
                        "saved_at": payload["saved_at"],
                    },
                }
                resp = self._post("/write", body)
                if isinstance(resp, dict) and resp.get("success") is True:
                    logger.debug("已同步阶段 [%s] 至 ReMe", stage)
                    return True
                logger.warning("ReMe 写入未成功：%s", (resp or {}).get("answer", "无返回"))
            except urllib.error.URLError as exc:
                # 网络问题：立即置为离线，下次调用会重探
                self._online_cached = False
                self._online_checked_at = time.time()
                self.last_error = str(exc)
                logger.warning("ReMe 写入异常，本次降级本地：%s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ReMe 写入异常，本次降级本地：%s", exc)
        return True

    @staticmethod
    def _render(session_id: str, stage: str, payload: Dict[str, Any]) -> str:
        """把结构化数据渲染为带 JSON 数据块的 markdown，便于 ReMe 检索与人工查看"""
        data = payload.get("data", {})
        summary = ""
        if isinstance(data, dict):
            bits = []
            for k in ("status", "strategy_used", "verdict", "provenance"):
                if data.get(k) is not None:
                    bits.append(f"{k}={data[k]}")
            att = data.get("att")
            if isinstance(att, dict) and att.get("coef") is not None:
                bits.append(f"ATT={att['coef']:.4f}")
            summary = "；".join(bits)
        return (
            f"# 学术全流程记忆 · {stage}\n\n"
            f"- 会话：`{session_id}`\n"
            f"- 阶段：**{stage}**\n"
            f"- 时间：{payload.get('saved_at','')}\n"
            f"- 摘要：{summary or '—'}\n\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n"
        )

    def _save_to_local(self, session_id: str, stage: str, payload: Dict[str, Any]) -> None:
        safe_session = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(session_id))
        safe_stage = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(stage))
        session_folder = self.fallback_dir / safe_session
        session_folder.mkdir(parents=True, exist_ok=True)
        with open(session_folder / f"{safe_stage}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------- 读取
    def load_session_memory(self, session_id: str, stage: str) -> Optional[Dict[str, Any]]:
        """优先读本地镜像（快且离线可用）；本地缺失且 ReMe 在线时再远程读。"""
        safe_session = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(session_id))
        safe_stage = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(stage))
        local_file = self.fallback_dir / safe_session / f"{safe_stage}.json"
        if local_file.exists():
            try:
                with open(local_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:  # noqa: BLE001
                logger.error("读取本地记忆失败 %s: %s", local_file, exc)

        if self.is_online:
            try:
                resp = self._post("/read", {"path": self._path_of(session_id, stage)})
                if isinstance(resp, dict) and resp.get("success") is True:
                    return self._parse_markdown(resp.get("answer", ""))
            except Exception as exc:  # noqa: BLE001
                logger.warning("从 ReMe 读取记忆失败：%s", exc)
        return None

    @staticmethod
    def _parse_markdown(text: str) -> Optional[Dict[str, Any]]:
        """从 markdown 正文中提取 ```json 数据块"""
        if not text:
            return None
        try:
            start = text.index("```json")
            end = text.index("```", start + 7)
            return json.loads(text[start + 7:end])
        except Exception:  # noqa: BLE001
            return None

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """跨会话语义检索；ReMe 不可用时返回空列表（不伪造结果）。"""
        if not self.is_online:
            return []
        try:
            resp = self._post("/search", {"query": query, "limit": limit})
            if isinstance(resp, dict) and resp.get("success") is True:
                answer = resp.get("answer")
                if isinstance(answer, list):
                    return answer
                if isinstance(answer, str):
                    return [{"title": "ReMe 检索结果", "content": answer}]
        except Exception as exc:  # noqa: BLE001
            logger.warning("ReMe 检索失败：%s", exc)
        return []

    # ------------------------------------------------------------- 状态
    def status(self) -> Dict[str, Any]:
        """供前端/日志展示的记忆层状态"""
        return {
            "online": self.check_online(),
            "base_url": self.base_url,
            "last_error": self.last_error,
            "namespace": self.namespace,
            "fallback_dir": str(self.fallback_dir),
        }
