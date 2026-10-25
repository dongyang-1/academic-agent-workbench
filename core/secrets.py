# -*- coding: utf-8 -*-
"""
统一密钥与 LLM 配置管理层 (Secrets)

解决的问题：
    整改前 api_key 以明文写在项目根目录 _llm_config.json 中，随项目目录
    （含 git 仓库、打包 zip）一起外泄。本模块把密钥彻底移出项目目录。

读取优先级（高 → 低）：
    1. 环境变量      ACA_LLM_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY ...
    2. 用户级密钥库  ~/.aca/secrets.json        (默认写入位置，不在项目内)
    3. 项目本地覆盖  <root>/config.local.json   (已在 .gitignore 中，仅本机调试用)
    4. 内置默认值（不含任何密钥，等价于"未配置"）

对外承诺：
    - api_key 永不以明文形式通过任何 API 响应返回，只返回脱敏串。
    - 任何历史遗留的 _llm_config.json 会在首次加载时自动迁移并删除。
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("aca.secrets")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]

# 历史遗留的明文配置文件（迁移成功后删除）
LEGACY_CONFIG_FILE = INTEGRATED_ROOT / "_llm_config.json"
# 项目内本地覆盖（不入库）
LOCAL_OVERRIDE_FILE = INTEGRATED_ROOT / "config.local.json"
# 用户级密钥库（默认落点）
USER_SECRETS_FILE = Path.home() / ".aca" / "secrets.json"

ENV_KEY_VARS = ("ACA_LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY")
ENV_BASE_URL_VARS = ("ACA_LLM_BASE_URL", "LLM_BASE_URL")
ENV_MODEL_VARS = ("ACA_LLM_MODEL", "LLM_MODEL")
ENV_PROVIDER_VARS = ("ACA_LLM_PROVIDER", "LLM_PROVIDER")

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "builtin",
    "api_key": "",
    "base_url": "https://api.deepseek.com/v1",
    "model_name": "deepseek-chat",
    # 写作/生成类调用可单独指定模型。reasoner 类模型会把推理链吐出来、
    # 且单次全文生成耗时数分钟；写作默认用 chat 类模型更快更干净。
    "writing_model_name": "deepseek-chat",
    "is_custom_enabled": False,
    # 记录配置来源，便于排查"到底用的是哪份配置"
    "_source": "default",
}


def _first_env(names) -> Optional[str]:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return None


def mask_key(key: Optional[str]) -> str:
    """把密钥脱敏为 sk-14b5****f3f 形式，用于接口回显与日志。"""
    if not key:
        return ""
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}****{key[-4:]}"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取配置文件失败 %s: %s", path, exc)
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 密钥文件仅本人可读写
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:  # noqa: BLE001  Windows 上 chmod 可能失败，忽略
        pass


def migrate_legacy_config() -> bool:
    """
    一次性迁移：把项目内遗留的 _llm_config.json 搬进用户级密钥库并删除原文件。
    仅在遗留文件存在且用户级密钥库尚无有效 key 时执行，返回是否发生了迁移。
    """
    if not LEGACY_CONFIG_FILE.exists():
        return False
    legacy = _read_json(LEGACY_CONFIG_FILE)
    existing = _read_json(USER_SECRETS_FILE)
    if legacy.get("api_key") and not existing.get("api_key"):
        merged = dict(existing)
        merged.update({k: v for k, v in legacy.items() if k in DEFAULT_CONFIG})
        _write_json(USER_SECRETS_FILE, merged)
        logger.info("已将遗留明文配置迁移至 %s", USER_SECRETS_FILE)
    try:
        LEGACY_CONFIG_FILE.unlink()
        logger.info("已删除明文配置文件 %s", LEGACY_CONFIG_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("删除遗留配置文件失败，请手动删除 %s: %s", LEGACY_CONFIG_FILE, exc)
    return True


def load_llm_config() -> Dict[str, Any]:
    """按优先级加载 LLM 配置；api_key 为空即视为未配置。"""
    migrate_legacy_config()

    cfg = dict(DEFAULT_CONFIG)

    # 3. 项目内本地覆盖
    local = _read_json(LOCAL_OVERRIDE_FILE)
    if local:
        cfg.update({k: v for k, v in local.items() if k in DEFAULT_CONFIG})
        cfg["_source"] = "config.local.json"

    # 2. 用户级密钥库（优先级高于项目内覆盖）
    user = _read_json(USER_SECRETS_FILE)
    if user:
        cfg.update({k: v for k, v in user.items() if k in DEFAULT_CONFIG})
        cfg["_source"] = str(USER_SECRETS_FILE)

    # 1. 环境变量（最高优先级）
    env_key = _first_env(ENV_KEY_VARS)
    if env_key:
        cfg["api_key"] = env_key
        cfg["_source"] = "env"
    env_url = _first_env(ENV_BASE_URL_VARS)
    if env_url:
        cfg["base_url"] = env_url
        cfg.setdefault("_source", "env")
    env_model = _first_env(ENV_MODEL_VARS)
    if env_model:
        cfg["model_name"] = env_model
    env_provider = _first_env(ENV_PROVIDER_VARS)
    if env_provider:
        cfg["provider"] = env_provider

    cfg["is_custom_enabled"] = bool(cfg.get("api_key"))
    if not cfg.get("writing_model_name"):
        cfg["writing_model_name"] = cfg.get("model_name", "deepseek-chat")
    return cfg


def save_llm_config(update: Dict[str, Any]) -> Dict[str, Any]:
    """
    持久化 LLM 配置。密钥只写入用户级密钥库；非敏感项同时写入项目本地覆盖，
    保证换机器时 base_url/model 这类非敏感默认值仍可随项目走。
    """
    current = load_llm_config()
    current.update({k: v for k, v in update.items() if k in DEFAULT_CONFIG})

    sensitive = {k: current[k] for k in ("api_key",)}
    non_sensitive = {k: current[k] for k in ("provider", "base_url", "model_name")}

    store = _read_json(USER_SECRETS_FILE)
    store.update(sensitive)
    store.update(non_sensitive)
    _write_json(USER_SECRETS_FILE, store)

    local = _read_json(LOCAL_OVERRIDE_FILE)
    local.update(non_sensitive)
    _write_json(LOCAL_OVERRIDE_FILE, local)

    logger.info("已保存 LLM 配置: provider=%s model=%s (密钥存于 %s)",
                current.get("provider"), current.get("model_name"), USER_SECRETS_FILE)
    return current


def public_view(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """返回可安全回显给前端的配置视图（密钥脱敏）。"""
    cfg = cfg or load_llm_config()
    view = dict(cfg)
    view["api_key"] = mask_key(cfg.get("api_key"))
    view["api_key_configured"] = bool(cfg.get("api_key"))
    # 允许用户显式清空：前端传空串视为"不修改"
    view["_hint"] = "api_key 为脱敏展示；如需修改请传入新值，留空表示保持不变。"
    return view


def is_configured() -> bool:
    return bool(load_llm_config().get("api_key"))
