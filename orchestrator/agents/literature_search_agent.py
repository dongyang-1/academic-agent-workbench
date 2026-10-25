# -*- coding: utf-8 -*-
"""
文献检索智能体 (LiteratureSearchAgent)

负责制定检索协议 (SearchPlan)、调用 part1 的多源检索运行时、返回候选文献。

重要约束：本模块不得在检索失败时返回"看起来像真的"占位文献。
检索不可用即如实报告，由上层决定重试或提示用户。
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
INTEGRATED_ROOT = CURRENT_DIR.parents[1]
PART1_SRC = INTEGRATED_ROOT / "part1-paper" / "src"
if str(PART1_SRC) not in sys.path:
    sys.path.insert(0, str(PART1_SRC))

if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.skill_loader import skill_loader  # noqa: E402

try:
    from literature_search.runtime import search_plan
    RUNTIME_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover
    search_plan = None
    RUNTIME_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

logger = logging.getLogger("LiteratureSearchAgent")


class LiteratureSearchAgent:
    """文献检索与定级智能体"""

    def __init__(self, name: str = "文献检索智能体", timeout: int = 15):
        self.name = name
        self.timeout = timeout

    def build_plan(
        self,
        research_question: str,
        concept_terms: Optional[List[str]] = None,
        start_year: int = 2015,
        end_year: int = 2026,
        max_records: int = 10,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """按 schemas/search-plan.schema.json 构建检索计划"""
        if not concept_terms:
            concept_terms = [
                t for t in research_question.replace("，", " ").replace("对", " ").replace("的", " ").split()
                if len(t) >= 2
            ]
        concept_blocks = [
            {"name": "policy_or_treatment", "terms": concept_terms[:2] or ["policy"]},
            {"name": "outcome_or_mechanism", "terms": concept_terms[2:4] or ["outcome"]},
        ]
        return {
            "research_question": research_question,
            "mode": "exploratory",
            "concept_blocks": concept_blocks,
            "sources": sources or ["crossref", "openalex", "arxiv", "nber"],
            "source_policy": {"ranking": "relevance", "max_records_per_source": max_records},
            "scope": {
                "time_range": f"{start_year}-{end_year}",
                "methods": ["Difference-in-Differences", "Causal Inference", "Panel Data"],
            },
            "screening": {
                "inclusion_criteria": [f"聚焦于 {research_question} 相关的微观或宏观因果识别研究"],
                "exclusion_criteria": ["纯理论模型无实证检验、缺乏对照组分析的文献"],
            },
        }

    def plan_and_search(
        self,
        research_question: str,
        concept_terms: Optional[List[str]] = None,
        start_year: int = 2015,
        end_year: int = 2026,
        max_records: int = 10,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        执行检索。失败时返回 status=failed 与原因，不返回占位文献。
        """
        plan = self.build_plan(research_question, concept_terms, start_year, end_year, max_records, sources)

        if search_plan is None:
            return {
                "module_id": "literature-search",
                "status": "failed",
                "records": [],
                "search_protocol": plan,
                "errors": [f"文献检索运行时不可用（{RUNTIME_IMPORT_ERROR}）"],
            }

        try:
            output = search_plan(plan, timeout=self.timeout)
        except Exception as exc:
            logger.warning("[%s] 检索执行失败: %s", self.name, exc)
            return {
                "module_id": "literature-search",
                "status": "failed",
                "records": [],
                "search_protocol": plan,
                "errors": [f"检索执行失败：{type(exc).__name__}: {exc}"],
            }

        if not output or not output.get("records"):
            return {
                "module_id": "literature-search",
                "status": "empty",
                "records": [],
                "search_protocol": plan,
                "search_metrics": (output or {}).get("search_metrics", {}),
                "coverage_notes": (output or {}).get("coverage_notes", []),
                "errors": [],
                "notice": "各数据源均未返回命中结果，请调整关键词、放宽年份或增加数据源",
            }

        output.setdefault("status", "ok")
        output["search_protocol"] = plan
        logger.info("[%s] 检索完成，纳入 %d 篇文献", self.name, len(output.get("records", [])))
        return output

    def chat(self, user_message: str, session_context: Dict[str, Any]) -> str:
        """
        基于会话中真实检索结果作答；无结果时不编造文献。

        LLM 可用时由模型组织答复，系统提示注入 part1 检索技能规范，
        并明确禁止引用结果中不存在的文献。
        """
        records = session_context.get("literature") or []
        topic = (session_context.get("task_input") or {}).get("research_topic") or "当前课题"

        if not records:
            return (
                f"当前会话还没有检索到文献，无法给出文献清单。\n\n"
                f"请在【文献检索】面板以《{topic}》为主题发起检索；"
                f"若检索返回为空，通常是关键词过窄或数据源未命中，可放宽年份或增加数据源后重试。"
            )

        llm = self._llm()
        if llm is not None:
            skill_text, _trace = skill_loader.compose_injection(
                skill_loader.for_literature(),
                heading="本轮生效的文献检索技能规范",
                max_chars=10000,
            )
            facts = "\n".join(
                f"{i}. 《{r.get('title') or '无标题'}》（{r.get('year') or 'n.d.'}），"
                f"{r.get('venue') or '来源未知'}，核验状态：{r.get('verification_status') or 'unknown'}"
                for i, r in enumerate(records[:30], start=1)
            )
            system = (
                "你是经管学术文献检索与计量定级助手。\n\n"
                f"{skill_text}\n\n"
                "# 铁律\n"
                "1. 只能引用下方【真实检索结果】中的文献，禁止补充任何未检索到的文献、"
                "作者、年份或期刊。\n"
                "2. 核验状态不是 verified 的条目必须如实提示其未核验。\n"
                "3. 用户要的结果里没有时，直接说明未提供。\n"
                f"\n# 真实检索结果（共 {len(records)} 篇）\n{facts}\n"
            )
            status = llm.chat_completion_with_status(
                target_agent="literature_search",
                user_message=user_message,
                context_data={"topic": topic},
                chat_history=session_context.get("chat_history", []),
                system_override=system,
            )
            if status.get("success") and status.get("reply"):
                return status["reply"]
            return (
                f"> ⚠️ 大模型调用失败：`{status.get('error', '未知错误')}`\n"
                f"> 以下为基于真实检索结果的本地清单。\n\n" + self._local_listing(records)
            )
        return self._local_listing(records)

    def _llm(self):
        try:
            from llm_client import academic_llm_client
            if academic_llm_client.is_available():
                return academic_llm_client
        except Exception as exc:  # noqa: BLE001
            logger.debug("LLM 客户端不可用: %s", exc)
        return None

    @staticmethod
    def _local_listing(records: List[Dict[str, Any]]) -> str:
        """无模型时的本地清单：只列真实条目"""
        lines = [f"### 已检索文献（共 {len(records)} 篇）", ""]
        for i, r in enumerate(records[:10], start=1):
            title = r.get("title") or "（无标题）"
            year = r.get("year") or "n.d."
            venue = r.get("venue") or "来源未知"
            status = r.get("verification_status") or "unknown"
            lines.append(f"{i}. **{title}**（{year}），*{venue}* —— 核验状态：{status}")
        lines.append("")
        lines.append("需要导出 BibTeX / RIS，或按期刊等级筛选，请直接说明。")
        return "\n".join(lines)
