# -*- coding: utf-8 -*-
"""
学术综述与论文写作智能体 (LiteratureReviewAgent / WritingAgent)

职责：
1. 由检索结果提炼研究假说（synthesize_and_derive_hypotheses）
2. 按目标期刊规范逐章生成论文正文（compose_full_academic_paper）

约束：
- 正文必须由大模型生成；模型不可用时返回 status=failed 并说明原因，
  不再用 f-string 模板伪造"看起来像论文"的文本。
- 期刊约束来自 core/journal_profiles 注册的真实 SKILL.md，而非硬编码。
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
INTEGRATED_ROOT = CURRENT_DIR.parents[1]
ORCHESTRATOR_DIR = CURRENT_DIR.parent
for _p in (str(INTEGRATED_ROOT), str(ORCHESTRATOR_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.contracts import PaperDraft  # noqa: E402
from core.journal_profiles import (  # noqa: E402
    DEFAULT_JOURNAL,
    load_journal_context,
    load_journal_skill,
    sections_for_journal,
)
from core.skill_loader import skill_loader  # noqa: E402

logger = logging.getLogger("LiteratureReviewAgent")

PART3_SKILL = INTEGRATED_ROOT / "part3-文献综述" / "zotero-literature-review" / "SKILL.md"


def _load_part3_skill() -> str:
    """综述与引用溯源规则，作为写作的系统级约束"""
    if PART3_SKILL.exists():
        return PART3_SKILL.read_text(encoding="utf-8")
    return "（未找到 part3 综述规则文件）"


# 展示用的推理链包装（聊天界面的"深度思考"卡片）。生成类调用绝不能让它进正文，
# 这里做一道兜底清理：即使上游某条路径漏传 include_reasoning=False 也不会污染稿件。
_THOUGHT_BLOCK_RE = re.compile(
    r"<details\s+class=['\"]r1-thought-box['\"][^>]*>.*?</details>",
    re.DOTALL | re.IGNORECASE,
)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thought_blocks(text: str) -> str:
    """剥离混入正文的推理链内容，只保留论文正文"""
    if not text:
        return ""
    cleaned = _THOUGHT_BLOCK_RE.sub("", text)
    cleaned = _THINK_TAG_RE.sub("", cleaned)
    return cleaned.strip()


class LiteratureReviewAgent:
    """学术综述与全文写作智能体"""

    def __init__(self, name: str = "学术综述与全文写作智能体", llm_client=None):
        self.name = name
        if llm_client is None:
            from llm_client import academic_llm_client  # 延迟导入，避免循环依赖
            llm_client = academic_llm_client
        self.llm = llm_client

    # -- 系统提示 -----------------------------------------------------------
    def _system_prompt(self, journal: str, section: str) -> str:
        """
        系统提示 = part3 综述规则 + 期刊格式约束 + **当前环节生效的技能正文**。
        技能正文来自磁盘上的 SKILL.md，因此修改 SKILL.md 会直接改变生成结果。
        """
        base = _load_part3_skill()
        journal_ctx = load_journal_context(journal, ["workflow", "style", section])
        skill_text, _trace = skill_loader.compose_injection(
            skill_loader.for_writing(journal=journal, section=section),
            heading="本环节生效的写作技能规范",
            max_chars=14000,
        )
        return (
            f"你是面向中文经济学顶刊的学术写作助手。\n\n"
            f"# 证据与引用规则（必须遵守）\n\n{base}\n\n"
            f"# 期刊格式约束（必须遵守）\n\n{journal_ctx}\n\n"
            f"{skill_text}\n\n"
            f"# 写作要求\n"
            f"1. 所有论断必须可追溯到给定的文献或实证结果，不得凭空杜撰文献、作者或数据。\n"
            f"2. 区分统计显著性与经济显著性，不得把相关关系表述为因果结论。\n"
            f"3. 实证结果以给定数值为准，不得改写系数、标准误或显著性。\n"
            f"4. 使用中文写作，术语首次出现时给出英文原文。\n"
        )

    def active_skills(self, journal: str, section: str) -> List[Dict[str, Any]]:
        """返回本环节实际生效的技能清单（含内容 hash，便于验证改动是否生效）"""
        _text, trace = skill_loader.compose_injection(
            skill_loader.for_writing(journal=journal, section=section),
            heading="本环节生效的写作技能规范",
            max_chars=14000,
        )
        return trace

    # -- 输入整理 -----------------------------------------------------------
    @staticmethod
    def _format_literature(records: List[Dict[str, Any]], limit: int = 30) -> str:
        if not records:
            return "（本次未提供检索文献，写作时不得引用任何具体文献）"
        lines = []
        for i, r in enumerate(records[:limit], start=1):
            authors = r.get("authors") or []
            if authors and isinstance(authors[0], dict):
                a = ", ".join(f"{x.get('family','')} {x.get('given','')}".strip() for x in authors[:3])
            else:
                a = ", ".join(str(x) for x in authors[:3]) if authors else "作者未知"
            lines.append(
                f"{i}. {a}（{r.get('year','n.d.')}）《{r.get('title','无标题')}》，"
                f"{r.get('venue','来源未知')}。摘要线索：{(r.get('abstract') or '无')[:300]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_empirical(emp: Dict[str, Any]) -> str:
        if not emp:
            return "（本次未提供实证结果，写作时不得出现任何回归系数）"
        att = emp.get("att") or {}
        pre = (emp.get("pre_trend_test") or {}).get("evidence") or {}
        sens = emp.get("sensitivity") or {}
        prof = emp.get("data_profile") or {}
        het = emp.get("heterogeneity") or []
        mech = emp.get("mechanism") or []

        lines = [
            f"识别策略：{emp.get('strategy_used')}",
            f"样本：{prof.get('n_obs')} 个观测，{prof.get('n_units')} 个个体，{prof.get('n_periods')} 个时期",
        ]
        if att.get("coef") is not None:
            lines.append(
                f"核心估计量：{att['coef']:.4f}（标准误 {att.get('se')}, p = {att.get('p_value')}）"
            )
        if pre.get("p_value") is not None:
            lines.append(f"平行趋势联合检验：卡方 {pre.get('statistic'):.4f}，df={pre.get('df')}，p={pre['p_value']:.4f}")
        if sens.get("m_bar") is not None:
            mb = sens["m_bar"]
            lines.append(f"敏感性击穿值：{mb if mb == float('inf') else f'{mb:.2f}'}")
        for h in het:
            lines.append(f"异质性（{h.get('group_value')}）：系数 {h.get('coef')}，p={h.get('p_value')}")
        for m in mech:
            lines.append(f"机制（{m.get('mediator')}）：交互项 {m.get('interaction_coef')}，p={m.get('interaction_p')}")
        if emp.get("provenance") == "demo":
            lines.append("【重要】以上结果来自演示数据，写作时必须明确标注不可用于正式投稿。")
        return "\n".join(lines)

    # -- 假说提炼 -----------------------------------------------------------
    def synthesize_and_derive_hypotheses(
        self,
        research_question: str,
        literature_records: List[Dict[str, Any]],
        target_journal: str = DEFAULT_JOURNAL,
    ) -> Dict[str, Any]:
        """由文献提炼可检验假说"""
        if not self.llm.is_available():
            return {
                "module_id": "literature-review",
                "status": "failed",
                "hypotheses": [],
                "review_narrative": "",
                "errors": ["未配置可用的大模型 API，无法生成研究假说"],
            }

        section = "theory_hypotheses" if target_journal == "经济研究" else "literature_review"
        prompt = (
            f"研究问题：{research_question}\n\n"
            f"已检索文献：\n{self._format_literature(literature_records)}\n\n"
            f"请基于上述文献提出 2 至 4 条可检验的研究假说，每条包含：\n"
            f"1. 假说陈述；2. 理论依据（引用上述文献）；3. 可检验的实证含义。\n"
            f"只输出假说列表，不要输出其他内容。"
        )
        res = self.llm.chat_completion_with_status(
            target_agent="academic_writing",
            user_message=prompt,
            context_data={"research_question": research_question},
            chat_history=[],
            system_override=self._system_prompt(target_journal, section),
            include_reasoning=False,
            purpose="writing",
        )
        if not res.get("success"):
            return {
                "module_id": "literature-review",
                "status": "failed",
                "hypotheses": [],
                "review_narrative": "",
                "errors": [res.get("error", "大模型调用失败")],
            }
        text = res.get("reply_plain") or res.get("reply", "")
        return {
            "module_id": "literature-review",
            "status": "ok",
            "hypotheses": [{"text": line.strip()} for line in text.split("\n") if line.strip()],
            "review_narrative": text,
            "provenance": "llm",
        }

    # -- 全文写作 -----------------------------------------------------------
    def compose_full_academic_paper(
        self,
        research_question: str,
        literature_records: Optional[List[Dict[str, Any]]] = None,
        empirical_results: Optional[Dict[str, Any]] = None,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        target_journal: str = DEFAULT_JOURNAL,
        sections: Optional[List[str]] = None,
    ) -> PaperDraft:
        """
        按期刊规范逐章生成论文正文。

        模型不可用时返回 provenance=template 的空草稿并附带错误，绝不伪造正文。
        """
        literature_records = literature_records or []
        empirical_results = empirical_results or {}
        hypotheses = hypotheses or []
        draft = PaperDraft(research_question=research_question, target_journal=target_journal)

        if not self.llm.is_available():
            draft.provenance = "template"
            draft.warnings = [
                "未配置可用的大模型 API，无法生成正文。"
                "请在配置中填入有效的 API Key 后重试；系统不会用模板伪造论文内容。"
            ]
            return draft

        todo = sections or sections_for_journal(target_journal)
        lit_txt = self._format_literature(literature_records)
        emp_txt = self._format_empirical(empirical_results)
        hyp_txt = "\n".join(f"- {h.get('text', h) if isinstance(h, dict) else h}" for h in hypotheses) or "（未提供假说）"

        for sec in todo:
            prompt = (
                f"研究问题：{research_question}\n\n"
                f"目标期刊：{target_journal}\n\n"
                f"可引用的文献：\n{lit_txt}\n\n"
                f"实证结果：\n{emp_txt}\n\n"
                f"待检验假说：\n{hyp_txt}\n\n"
                f"请撰写论文的【{sec}】章节。要求：\n"
                f"- 严格遵循上文给出的期刊格式约束；\n"
                f"- 只使用上面提供的文献与实证结果，不得新增任何未提供的引用或数值；\n"
                f"- 直接输出章节正文，不要输出章节标题以外的解释性说明。"
            )
            try:
                # 关键：把期刊格式约束 + 本环节生效的技能正文作为系统提示注入。
                # 整改前这里没有传 system_override，导致 _system_prompt 从未生效，
                # 模型只收到内置通用提示，SKILL.md 形同虚设。
                res = self.llm.chat_completion_with_status(
                    target_agent="academic_writing",
                    user_message=prompt,
                    context_data={"research_question": research_question, "section": sec},
                    chat_history=[],
                    system_override=self._system_prompt(target_journal, sec),
                    include_reasoning=False,
                    purpose="writing",
                )
            except Exception as exc:
                draft.warnings.append(f"章节 {sec} 调用异常：{exc}")
                continue
            if not res.get("success"):
                draft.warnings.append(f"章节 {sec} 生成失败：{res.get('error')}")
                continue
            draft.sections[sec] = _strip_thought_blocks(res.get("reply_plain") or res.get("reply", ""))
            logger.info("[%s] 已生成章节 %s（%d 字）", self.name, sec, len(res.get("reply", "")))

        if not draft.sections:
            draft.provenance = "template"
            draft.warnings.append("所有章节均生成失败，未产出正文")
            return draft

        order = [s for s in todo if s in draft.sections]
        draft.full_text = "\n\n".join(f"## {s}\n\n{draft.sections[s]}" for s in order)
        draft.word_count = len(draft.full_text)
        draft.provenance = "llm"
        return draft

    def chat(self, user_message: str, session_context: Dict[str, Any]) -> str:
        """写作侧问答；无可用模型时明确说明"""
        topic = (session_context.get("task_input") or {}).get("research_topic") or "当前课题"
        paper = session_context.get("paper") or {}
        if not self.llm.is_available():
            return (
                f"写作智能体需要大模型才能工作，当前未检测到可用的 API 配置。\n\n"
                f"请在配置中填入 API Key。在此之前我不会生成论文正文，避免产出模板化的伪内容。"
            )
        ctx = {
            "research_question": topic,
            "sections": list((paper.get("sections") or {}).keys()),
        }
        res = self.llm.chat_completion_with_status(
            target_agent="academic_writing",
            user_message=user_message,
            context_data=ctx,
            chat_history=session_context.get("chat_history", []),
        )
        if res.get("success"):
            return res.get("reply", "")
        return f"大模型调用失败：{res.get('error')}"
