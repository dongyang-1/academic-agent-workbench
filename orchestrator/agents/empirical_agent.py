# -*- coding: utf-8 -*-
"""
因果实证分析智能体 (EmpiricalAgent)

编排层适配器：把 TaskSpec 交给 part2 的执行器，并把结果收敛为统一的 EmpiricalResult。
本文件不再自行拼装字段，杜绝「上层传 data_config、下层只认 dependent_var」这类错配。
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

CURRENT_DIR = Path(__file__).resolve().parent
INTEGRATED_ROOT = CURRENT_DIR.parents[1]
PART2_PYTHON = INTEGRATED_ROOT / "part2-empirical-research" / "tools" / "python"
if str(PART2_PYTHON) not in sys.path:
    sys.path.insert(0, str(PART2_PYTHON))
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.contracts import TaskSpec  # noqa: E402
from core.skill_loader import skill_loader  # noqa: E402
from agent_api import run_empirical_task  # noqa: E402

logger = logging.getLogger("EmpiricalAgent")


class EmpiricalAgent:
    """因果计量实证分析智能体"""

    def __init__(self, name: str = "因果实证智能体", output_dir: Optional[str] = None):
        self.name = name
        self.output_dir = output_dir

    def execute(
        self,
        task: Union[TaskSpec, Dict[str, Any]],
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行实证分析。task 必须是 TaskSpec（或其等价字典）。
        """
        out = output_dir or self.output_dir
        res = run_empirical_task(task, output_dir=out)
        if res.get("status") == "failed":
            logger.warning("[%s] 实证分析未通过前置校验: %s", self.name, res.get("errors"))
        else:
            att = res.get("att") or {}
            logger.info(
                "[%s] 实证完成：策略=%s ATT=%s (SE=%s) 判定=%s",
                self.name, res.get("strategy_used"), att.get("coef"), att.get("se"),
                (res.get("review") or {}).get("verdict"),
            )
        # 记录本轮生效的计量技能。注意：技能只约束"解读与诊断口径"，
        # 不参与确定性计算——估计量仍由 econ_core 给出，保证可复现。
        strategy = res.get("strategy_used") or self._strategy_of(task)
        _text, trace = skill_loader.compose_injection(
            skill_loader.for_empirical(strategy=strategy, include_output=True),
            heading="本轮生效的计量技能规范",
            max_chars=10000,
        )
        res["skill_trace"] = trace
        return res

    @staticmethod
    def _strategy_of(task) -> str:
        if isinstance(task, dict):
            return task.get("strategy") or ""
        return getattr(task, "strategy", "") or ""

    def chat(self, user_message: str, session_context: Dict[str, Any]) -> str:
        """
        基于当前会话真实结果的问答。

        LLM 可用时：由模型组织语言，系统提示注入本轮生效的计量技能，
        但所有数值只能取自给定结果（提示中明确禁止改写）；
        LLM 不可用时：退回本地模板，只报数不发挥，不编造。
        """
        empirical = session_context.get("empirical") or {}
        if not empirical:
            return (
                "还没有可解读的实证结果。请先在右侧配置数据文件的列角色映射"
                "（个体列、时间列、被解释变量、首次处理年份列）并运行实证分析。"
            )
        att = empirical.get("att") or {}
        coef = att.get("coef")
        se = att.get("se")
        p = att.get("p_value")
        if coef is None:
            return "当前会话中的实证结果不包含可用系数，无法解读。"

        llm = self._llm()
        if llm is not None:
            strategy = empirical.get("strategy_used") or ""
            skill_text, _trace = skill_loader.compose_injection(
                skill_loader.for_empirical(strategy=strategy),
                heading="本轮生效的计量技能规范",
                max_chars=10000,
            )
            system = (
                "你是经管顶刊审稿人级别的计量经济学助手。\n\n"
                f"{skill_text}\n\n"
                "# 铁律\n"
                "1. 只能使用【真实结果】中的数值，禁止改写、估算或补充任何系数、"
                "标准误、p 值、样本量。\n"
                "2. 用户问到结果中不存在的内容时，直接说明该项未提供，不得推测。\n"
                "3. 区分统计显著性与经济显著性；未经识别策略支持不得下因果结论。\n"
                f"\n# 真实结果\n{self._facts_block(empirical)}\n"
            )
            status = llm.chat_completion_with_status(
                target_agent="empirical_research",
                user_message=user_message,
                context_data={"empirical": empirical},
                chat_history=session_context.get("chat_history", []),
                system_override=system,
            )
            if status.get("success") and status.get("reply"):
                return status["reply"]
            return (
                f"> ⚠️ 大模型调用失败：`{status.get('error', '未知错误')}`\n"
                f"> 以下为基于会话真实结果的本地答复。\n\n" + self._local_answer(empirical)
            )
        return self._local_answer(empirical)

    def _llm(self):
        try:
            from llm_client import academic_llm_client
            if academic_llm_client.is_available():
                return academic_llm_client
        except Exception as exc:  # noqa: BLE001
            logger.debug("LLM 客户端不可用: %s", exc)
        return None

    @staticmethod
    def _facts_block(empirical: Dict[str, Any]) -> str:
        """把真实结果整理成给模型的事实块，模型不得越雷池一步"""
        att = empirical.get("att") or {}
        prof = empirical.get("data_profile") or {}
        pre = (empirical.get("pre_trend_test") or {}).get("evidence") or {}
        sens = empirical.get("sensitivity") or {}
        rev = empirical.get("review") or {}
        lines = [
            f"识别策略：{empirical.get('strategy_used')}",
            f"样本：{prof.get('n_obs')} 观测 / {prof.get('n_units')} 个体 / {prof.get('n_periods')} 时期",
            f"核心估计量：{att.get('coef')}（标准误 {att.get('se')}，p = {att.get('p_value')}）",
        ]
        if pre.get("p_value") is not None:
            lines.append(f"平行趋势联合检验：卡方 {pre.get('statistic')}（df={pre.get('df')}），p = {pre['p_value']}")
        if sens.get("m_bar") is not None:
            lines.append(f"敏感性 M_bar：{sens['m_bar']}")
        if rev:
            lines.append(f"审稿判定：{rev.get('verdict')}；理由：{'；'.join(rev.get('reasons', [])) or '无'}")
        return "\n".join(lines)

    def _local_answer(self, empirical: Dict[str, Any]) -> str:
        """无模型时的本地答复：只报真实数值，不做解读性发挥"""
        att = empirical.get("att") or {}
        coef = att.get("coef")
        se = att.get("se")
        p = att.get("p_value")
        stars = "***" if (p is not None and p < 0.01) else ("**" if (p is not None and p < 0.05) else ("*" if (p is not None and p < 0.1) else ""))
        sig = "在统计上显著" if (p is not None and p < 0.1) else "未达到常规显著性水平"
        lines = [
            f"### 实证结果解读",
            f"",
            f"- **识别策略**：{empirical.get('strategy_used')}",
            f"- **核心估计量**：{coef:.4f}{stars}（聚类稳健标准误 {se:.4f}，p = {p:.4g}）" if se else f"- **核心估计量**：{coef:.4f}",
            f"- **统计结论**：{sig}",
        ]
        pre = (empirical.get("pre_trend_test") or {}).get("evidence") or {}
        if pre.get("p_value") is not None:
            lines.append(f"- **平行趋势联合检验**：卡方 {pre.get('statistic'):.4f}（df={pre.get('df')}），p = {pre['p_value']:.4f}")
        sens = empirical.get("sensitivity") or {}
        if sens.get("m_bar") is not None:
            mb = sens["m_bar"]
            mb_txt = "不受相对幅度约束影响" if mb == float("inf") else f"{mb:.2f} 倍"
            lines.append(f"- **敏感性**：可容忍的处理后趋势违背为处理前最大违背的 {mb_txt}")
        rev = empirical.get("review") or {}
        if rev.get("reasons"):
            lines.append("")
            lines.append("**审稿人提示**：")
            lines.extend(f"- {r}" for r in rev["reasons"])
        return "\n".join(lines)
