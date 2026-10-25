# -*- coding: utf-8 -*-
"""
通用学术大模型调用客户端 (Academic LLM Client)
支持：
1. 兼容 OpenAI 格式的各类主流大模型（DeepSeek V3/R1, 阿里通义千问 Qwen, OpenAI GPT-4o, 智谱 GLM-4 等）
2. 具备思考链与学术规范前置 Prompt 约束（严守防多重共线性规范、因果推断规范）
3. 支持动态读取配置与优雅离线降级
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("AcademicLLMClient")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.secrets import load_llm_config, save_llm_config  # noqa: E402

# 系统级学术规范约束 Prompt
ACADEMIC_SYSTEM_PROMPTS = {
    "coordinator": (
        "你是一个顶尖经济学与管理学实证研究全流程编排总控智能体。\n"
        "你的职责是协助学者统筹研究全流程：从文献综述挖掘、因果识别策略选择（如 CS-DID, IV, RDD, SCM）、"
        "双向固定效应回归审计，到顶刊规范学术论文全文撰写。\n"
        "请使用专业、深刻、富有学术严谨性的中文回复。若涉及计量模型，严守因果推断前沿规范与多重共线性排查。"
    ),
    "literature_search": (
        "你是一个权威经管学术文献检索与计量定级智能体。\n"
        "你精通 EconLit, Crossref, OpenAlex, NBER, SSRN 等权威学术库文献检索与计量筛选。\n"
        "你善于提炼前沿顶刊（如 AER, QJE, JFE, 《经济研究》, 《管理世界》）的最新研究脉络与学术争论。"
    ),
    "empirical_research": (
        "你是一个经管顶刊审稿人级别的因果实证分析与计量经济学智能体。\n"
        "【关键计量规范 - 强制遵循】：\n"
        "在协助构建计量模型或排查协变量时，若模型引入了某个既有控制变量的衍生/转换形态（如中心化、标准化、对数、虚拟变量），"
        "必须显式声明并从控制变量列表中彻底剔除原始变量，坚决防范完美共线性 (Perfect Collinearity)。\n"
        "你精通现代交错实施 DID（Callaway & Sant'Anna 2021）、HonestDiD 敏感性分析、Bacon 分解与 DAG 坏控制审计。"
    ),
    "academic_writing": (
        "你是一个顶刊出版级学术综述与全文撰写智能体。\n"
        "你擅长结合已有文献与实证回归结果，撰写结构严密、叙事宏大、逻辑推导严密的学术论文全文初稿。\n"
        "论文结构涵盖：引言与制度背景、文献综述与假说推演、模型识别与数据、实证回归分析、稳健性检验与结论建议。"
    ),
}


class AcademicLLMClient:
    """通用学术大模型客户端"""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        加载大模型配置。密钥来源由 core.secrets 统一管理：
        环境变量 > ~/.aca/secrets.json > config.local.json > 内置默认值。
        项目内不再保存任何明文密钥。
        """
        try:
            return load_llm_config()
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载 LLM 配置失败，回退到空配置: %s", exc)
            return {
                "provider": "builtin",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "is_custom_enabled": False,
                "_source": "fallback",
            }

    def update_config(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """持久化更新配置（密钥写入用户级密钥库）并热重载。"""
        self.config = save_llm_config(update)
        return self.config

    def reload_config(self):
        """重新加载最新配置"""
        self.config = self._load_config()

    def is_available(self) -> bool:
        """
        外部大模型是否可用。
        workflow 的流式对话依赖此方法，缺失会导致 /api/chat/stream 直接抛 AttributeError。
        """
        cfg = getattr(self, "config", None) or self._load_config()
        return bool(cfg.get("api_key")) and bool(cfg.get("is_custom_enabled", True))

    def test_connection(self, temp_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        测试大模型 API 的连通性
        :param temp_cfg: 可选的临时测试配置字典
        :return: {"ok": bool, "latency_ms": int, "model": str, "reply": str, "error": str}
        """
        import time
        cfg = temp_cfg if temp_cfg else self._load_config()
        api_key = (cfg.get("api_key") or "").strip()
        base_url = (cfg.get("base_url") or "https://api.deepseek.com/v1").strip().rstrip("/")
        model_name = (cfg.get("model_name") or "deepseek-chat").strip()

        if not api_key:
            return {"ok": False, "error": "请先输入有效的 API Key！"}

        if not base_url.endswith("/chat/completions"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = base_url

        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "请只回复两个字：收到"}
            ],
            "max_tokens": 50,
            "temperature": 0.3,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        start_time = time.time()
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                elapsed_ms = int((time.time() - start_time) * 1000)
                body = resp.read().decode("utf-8")
                res_json = json.loads(body)
                choices = res_json.get("choices", [])
                reply_text = ""
                if choices:
                    reply_text = choices[0].get("message", {}).get("content", "").strip()
                return {
                    "ok": True,
                    "latency_ms": elapsed_ms,
                    "model": model_name,
                    "reply": reply_text or "连接正常",
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.error("API 测试连接 HTTP 错误: %s %s", he.code, err_body)
            # 尝试解析 JSON 错误
            msg = err_body
            try:
                ej = json.loads(err_body)
                if "error" in ej and "message" in ej["error"]:
                    msg = ej["error"]["message"]
            except Exception:
                pass
            return {
                "ok": False,
                "error": f"HTTP {he.code}: {msg}",
            }
        except Exception as e:
            logger.error("API 测试连接网络异常: %s", e)
            return {
                "ok": False,
                "error": f"网络连接异常: {str(e)}",
            }

    def chat_completion_with_status(
        self,
        target_agent: str,
        user_message: str,
        context_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        system_override: Optional[str] = None,
        include_reasoning: bool = True,
        purpose: str = "chat",
    ) -> Dict[str, Any]:
        """
        发起大模型调用并返回状态信息，包含深度思考与状态追踪

        :param system_override: 调用方指定的完整系统提示。
            传入时**完全替换**内置的 agent 级提示与上下文拼装，
            用于把 SKILL.md 规范注入生成环节（写作 / 实证解读）。
        :param include_reasoning: 是否把推理链包装成展示用 HTML 前插进 reply。
            聊天界面需要 True（展示"深度思考"卡片）；
            写作/生成类调用必须 False，否则思考过程会被写进论文正文。
            无论该参数取值如何，返回值始终带 "reply_plain"（纯净正文）
            与 "reasoning"（推理链原文）两个字段，调用方按需取用。
        :return: {"success": bool, "reply": str, "reply_plain": str,
                  "reasoning": str, "error": Optional[str], "has_custom_api": bool}
        """
        self.reload_config()
        cfg = self.config
        api_key = (cfg.get("api_key") or "").strip()
        is_custom_enabled = cfg.get("is_custom_enabled", True)

        if not api_key or not is_custom_enabled:
            return {
                "success": False,
                "reply": "",
                "error": "未配置外部大模型 API Key",
                "has_custom_api": False,
            }

        base_url = cfg.get("base_url", "https://api.deepseek.com/v1").rstrip("/")
        model_name = cfg.get("model_name", "deepseek-chat")
        if purpose == "writing" and cfg.get("writing_model_name"):
            # 写作走独立模型：reasoner 会吐推理链且慢，chat 类更适合产出正文
            model_name = cfg["writing_model_name"]

        if not base_url.endswith("/chat/completions"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = base_url

        if system_override:
            # 调用方自带系统提示（含技能规范与事实约束），不再叠加内置拼装，
            # 避免两套规范互相打架。
            messages = [{"role": "system", "content": system_override}]
        else:
            system_prompt = ACADEMIC_SYSTEM_PROMPTS.get(target_agent, ACADEMIC_SYSTEM_PROMPTS["coordinator"])

            # 注入当前课题上下文与计量防多重共线性铁律
            ctx = context_data or {}
            topic = ctx.get("task_input", {}).get("research_topic") or ctx.get("topic") or "学术实证课题"
            controls = ctx.get("task_input", {}).get("control_variables") or []

            context_prompt = (
                f"\n【当前研究项目上下文信息】：\n"
                f"- 核心研究课题：《{topic}》\n"
            )
            if controls:
                context_prompt += (
                    f"- 当前设定的候选控制变量列表：{controls}\n"
                    f"- 【计量防多重共线性特别规则】：若用户或模型引入了既有控制变量的衍生/转换形态（如去中心化、标准化、对数、虚拟变量），"
                    f"必须在控制变量列表中彻底剔除原始变量，严防完美多重共线性！\n"
                )
            if ctx.get("empirical"):
                context_prompt += f"- 现有实证估计要点：已执行异质性稳健 DID，已排查衍生变量多重共线性。\n"

            # 引导模型进行学术深度思考
            deep_think_instruction = (
                "\n【思考与回复规范】：\n"
                "请以顶尖经管学者与审稿人的高度审视问题。在给出最终建议前，请先进行严密的逻辑推演与计量审计，"
                "分析因果识别的潜在威胁（坏控制、反向因果、多重共线性等），并给出具有建设性的学术推断。"
            )
            messages = [
                {"role": "system", "content": system_prompt + context_prompt + deep_think_instruction}
            ]

        # 注入历史记录（最近 6 轮）
        if chat_history:
            for h in chat_history[-6:]:
                role = "assistant" if h.get("sender") != "user" else "user"
                messages.append({"role": role, "content": h.get("message", "")})

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 3000,
            "stream": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_body = resp.read().decode("utf-8")
                res_json = json.loads(res_body)
                choices = res_json.get("choices", [])
                if choices:
                    msg_obj = choices[0].get("message", {})
                    content = msg_obj.get("content", "")
                    reasoning_content = msg_obj.get("reasoning_content")

                    # 处理标签格式的 <think>...</think>
                    if not reasoning_content and "<think>" in content and "</think>" in content:
                        parts = content.split("</think>", 1)
                        reasoning_part = parts[0].replace("<think>", "").strip()
                        content = parts[1].strip()
                        reasoning_content = reasoning_part

                    formatted_reply = ""
                    if reasoning_content and include_reasoning:
                        # 呈现美观的高级思考链卡片（仅聊天界面需要）
                        formatted_reply += (
                            f"<details class='r1-thought-box' open>\n"
                            f"  <summary>🧠 深度思考过程 (Reasoning Chain · {model_name})</summary>\n"
                            f"  <div class='thought-inner-content'>\n\n{reasoning_content}\n\n</div>\n"
                            f"</details>\n\n"
                        )
                    formatted_reply += content
                    return {
                        "success": True,
                        "reply": formatted_reply,
                        "reply_plain": content,
                        "reasoning": reasoning_content or "",
                        "error": None,
                        "has_custom_api": True,
                    }
                else:
                    return {
                        "success": False,
                        "reply": "",
                        "error": "大模型返回结果为空 (choices 列表为空)",
                        "has_custom_api": True,
                    }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.error("调用大模型 API 出现 HTTP 错误 (%s): %s %s", endpoint, he.code, err_body)
            msg = err_body
            try:
                ej = json.loads(err_body)
                if "error" in ej and "message" in ej["error"]:
                    msg = ej["error"]["message"]
            except Exception:
                pass
            return {
                "success": False,
                "reply": "",
                "error": f"HTTP {he.code}: {msg}",
                "has_custom_api": True,
            }
        except Exception as e:
            logger.error("调用大模型 API 出现网络异常 (%s): %s", endpoint, e)
            return {
                "success": False,
                "reply": "",
                "error": str(e),
                "has_custom_api": True,
            }

    def stream_chat_completion(
        self,
        target_agent: str,
        user_message: str,
        context_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ):
        """
        发起大模型真实流式推理调用 (SSE 逐帧推送)
        实时输出：
        - 思考片段与实时秒表耗时：{"type": "thought", "delta": "...", "thought_time": float}
        - 思考结束状态：{"type": "thought_end", "thought_time": float}
        - 正文回答片段：{"type": "content", "delta": "..."}
        - 生成完毕总结：{"type": "done", "full_thought": str, "full_content": str, "total_time": float}
        - 异常诊断提示：{"type": "error", "error": str}
        """
        import time
        self.reload_config()
        cfg = self.config
        api_key = (cfg.get("api_key") or "").strip()
        is_custom_enabled = cfg.get("is_custom_enabled", True)

        if not api_key or not is_custom_enabled:
            yield {"type": "error", "error": "未配置外部大模型 API Key，转为本地智能体流式推演"}
            return

        base_url = cfg.get("base_url", "https://api.deepseek.com/v1").rstrip("/")
        model_name = cfg.get("model_name", "deepseek-chat")

        if not base_url.endswith("/chat/completions"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = base_url

        system_prompt = ACADEMIC_SYSTEM_PROMPTS.get(target_agent, ACADEMIC_SYSTEM_PROMPTS["coordinator"])
        ctx = context_data or {}
        topic = ctx.get("task_input", {}).get("research_topic") or ctx.get("topic") or "学术实证课题"
        controls = ctx.get("task_input", {}).get("control_variables") or []
        
        context_prompt = (
            f"\n【当前研究项目上下文信息】：\n"
            f"- 核心研究课题：《{topic}》\n"
        )
        if controls:
            context_prompt += (
                f"- 当前设定的候选控制变量列表：{controls}\n"
                f"- 【计量防多重共线性特别规则】：若模型引入了既有控制变量的衍生/转换形态（如去中心化、标准化、对数、虚拟变量），"
                f"必须在控制变量列表中彻底剔除原始变量，严防完美多重共线性！\n"
            )
        if ctx.get("empirical"):
            context_prompt += f"- 现有实证估计要点：已执行异质性稳健 DID，已排查衍生变量多重共线性。\n"

        deep_think_instruction = (
            "\n【思考与回复规范】：\n"
            "请以顶尖经管学者与审稿人的高度审视问题。在给出最终建议前，请先进行严密的逻辑推演与计量审计，"
            "分析因果识别的潜在威胁（坏控制、反向因果、多重共线性等），并给出具有建设性的学术推断。"
        )

        messages = [
            {"role": "system", "content": system_prompt + context_prompt + deep_think_instruction}
        ]

        if chat_history:
            for h in chat_history[-6:]:
                role = "assistant" if h.get("sender") != "user" else "user"
                messages.append({"role": role, "content": h.get("message", "")})

        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 3500,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        start_time = time.time()
        thought_start_time = start_time
        has_thought = False
        thought_ended = False
        full_thought = ""
        full_content = ""

        # 支持标签形式的 <think> 状态机
        in_tag_think = False

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=90) as resp:
                for line in resp:
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if not line_str or not line_str.startswith("data:"):
                        continue
                    data_str = line_str[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except Exception:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    # 1. 优先提取 DeepSeek-R1 原生的 reasoning_content 字段
                    reasoning_delta = delta.get("reasoning_content")
                    content_delta = delta.get("content")

                    if reasoning_delta:
                        has_thought = True
                        full_thought += reasoning_delta
                        elapsed = round(time.time() - thought_start_time, 1)
                        yield {
                            "type": "thought",
                            "delta": reasoning_delta,
                            "thought_time": elapsed,
                        }

                    # 2. 正文输出处理
                    if content_delta:
                        # 兼容直接在 content 里输出 <think> 和 </think> 的模型
                        if "<think>" in content_delta:
                            in_tag_think = True
                            has_thought = True
                            content_delta = content_delta.replace("<think>", "")
                        if "</think>" in content_delta:
                            parts = content_delta.split("</think>", 1)
                            thought_part = parts[0]
                            content_delta = parts[1]
                            if thought_part:
                                full_thought += thought_part
                                elapsed = round(time.time() - thought_start_time, 1)
                                yield {"type": "thought", "delta": thought_part, "thought_time": elapsed}
                            in_tag_think = False
                            thought_ended = True
                            thought_duration = round(time.time() - thought_start_time, 1)
                            yield {"type": "thought_end", "thought_time": thought_duration}

                        if in_tag_think:
                            if content_delta:
                                full_thought += content_delta
                                elapsed = round(time.time() - thought_start_time, 1)
                                yield {"type": "thought", "delta": content_delta, "thought_time": elapsed}
                        else:
                            # 首次从思考转入正文时触发 thought_end
                            if has_thought and not thought_ended:
                                thought_ended = True
                                thought_duration = round(time.time() - thought_start_time, 1)
                                yield {"type": "thought_end", "thought_time": thought_duration}

                            if content_delta:
                                full_content += content_delta
                                yield {
                                    "type": "content",
                                    "delta": content_delta,
                                }

            total_duration = round(time.time() - start_time, 1)
            thought_duration = round(time.time() - thought_start_time, 1) if has_thought else 0.0
            if has_thought and not thought_ended:
                yield {"type": "thought_end", "thought_time": thought_duration}

            yield {
                "type": "done",
                "full_thought": full_thought,
                "full_content": full_content,
                "total_time": total_duration,
                "thought_time": thought_duration,
            }

        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.error("大模型流式调用 HTTP 错误 (%s): %s %s", endpoint, he.code, err_body)
            msg = err_body
            try:
                ej = json.loads(err_body)
                if "error" in ej and "message" in ej["error"]:
                    msg = ej["error"]["message"]
            except Exception:
                pass
            yield {"type": "error", "error": f"HTTP {he.code}: {msg}"}
        except Exception as e:
            logger.error("大模型流式调用出现网络异常 (%s): %s", endpoint, e)
            yield {"type": "error", "error": str(e)}

    def chat_completion(
        self,
        target_agent: str,
        user_message: str,
        context_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """向后兼容的旧版单例调用"""
        res = self.chat_completion_with_status(target_agent, user_message, context_data, chat_history)
        if res.get("success"):
            return res.get("reply")
        return None


# 全局单例
academic_llm_client = AcademicLLMClient()


