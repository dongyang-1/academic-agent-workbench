# -*- coding: utf-8 -*-
"""
Token 消耗监控与模型配置管理模块 (TokenTracker)
负责：
1. 实时跟踪多智能体任务与对话的 Prompt Tokens 与 Completion Tokens
2. 预估费用核算（基于 DeepSeek/Qwen 行业基准单价）
3. 提供外部大模型 API 配置管理（支持 DeepSeek / 阿里百炼 Qwen / OpenAI）
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("TokenTracker")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.secrets import load_llm_config, save_llm_config, public_view  # noqa: E402


class TokenTracker:
    """Token 消耗量与 API 配置管理器"""

    def __init__(self):
        self.session_usage: Dict[str, Dict[str, int]] = {}
        # 用量从零开始累计，不再预置任何"看起来很真实"的假数字
        self.global_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        }
        self.llm_config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载大模型配置（密钥由 core.secrets 统一管理）"""
        try:
            return load_llm_config()
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载 LLM 配置失败: %s", exc)
            return {
                "provider": "builtin",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "is_custom_enabled": False,
            }

    def save_config(self, config_data: Dict[str, Any]) -> None:
        """保存大模型 API 配置（密钥只落盘到用户级密钥库）"""
        # 前端未重新填写密钥时传空串，视为"保持不变"
        if config_data.get("api_key") == "":
            config_data = {k: v for k, v in config_data.items() if k != "api_key"}
        self.llm_config = save_llm_config(config_data)

    def public_config(self) -> Dict[str, Any]:
        """供接口回显的配置视图（密钥脱敏）"""
        return public_view(self.llm_config)

    def estimate_tokens(self, text: str) -> int:
        """根据中英文混合特征估算 token 数量"""
        if not text:
            return 0
        chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        other_chars = len(text) - chinese_chars
        # 中文约 1 字 1.5 token，英文符号约 3 字符 1 token
        return int(chinese_chars * 1.5 + (other_chars / 3.0))

    def record_usage(self, session_id: str, prompt_text: str, completion_text: str) -> Dict[str, int]:
        """记录一次智能体调用的 Token 消耗"""
        p_tokens = self.estimate_tokens(prompt_text)
        c_tokens = self.estimate_tokens(completion_text)
        tot = p_tokens + c_tokens

        if session_id not in self.session_usage:
            self.session_usage[session_id] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "call_count": 0,
            }

        self.session_usage[session_id]["prompt_tokens"] += p_tokens
        self.session_usage[session_id]["completion_tokens"] += c_tokens
        self.session_usage[session_id]["total_tokens"] += tot
        self.session_usage[session_id]["call_count"] += 1

        self.global_usage["prompt_tokens"] += p_tokens
        self.global_usage["completion_tokens"] += c_tokens
        self.global_usage["total_tokens"] += tot
        self.global_usage["call_count"] += 1

        return {
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": tot,
        }

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取特定会话与全局的 Token 消耗统计及费用估算"""
        sess = self.session_usage.get(session_id, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        })
        
        # 按照 DeepSeek/通义千问百万 Token 约 1~2 元估算
        cost_cny = (sess["prompt_tokens"] * 0.000001 + sess["completion_tokens"] * 0.000002)

        return {
            "session_id": session_id,
            "session_prompt_tokens": sess["prompt_tokens"],
            "session_completion_tokens": sess["completion_tokens"],
            "session_total_tokens": sess["total_tokens"],
            "session_call_count": sess["call_count"],
            "session_estimated_cost_cny": round(cost_cny, 4),
            "global_total_tokens": self.global_usage["total_tokens"],
            "llm_config": {
                "provider": self.llm_config.get("provider", "local_engine"),
                "model_name": self.llm_config.get("model_name", "deepseek-chat"),
                "is_custom_enabled": self.llm_config.get("is_custom_enabled", False),
                "has_api_key": bool(self.llm_config.get("api_key")),
            },
        }


# 全局单例
token_tracker = TokenTracker()
