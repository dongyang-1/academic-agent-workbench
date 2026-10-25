# -*- coding: utf-8 -*-
"""
学术全流程多智能体编排协调中枢 (AcademicWorkflowCoordinator)

能力：
1. 三个子智能体可单独调用：run_literature / run_empirical / run_writing
2. 组合运行 run_pipeline，并支持审稿人回环：判定为致命缺陷时换识别策略重跑（限次数）
3. 对话分发 dispatch_chat / dispatch_chat_stream 保留给前端使用

所有跨模块数据交换走 core.contracts，不以字典约定为准。
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents.empirical_agent import EmpiricalAgent
from .agents.literature_review_agent import LiteratureReviewAgent
from .agents.literature_search_agent import LiteratureSearchAgent
from .llm_client import academic_llm_client
from .memory_reme import ReMeMemoryClient

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.store import store  # noqa: E402

logger = logging.getLogger("AcademicWorkflowCoordinator")

# 识别策略回退链：回环时依次尝试
STRATEGY_FALLBACK_CHAIN: List[str] = ["cs_did", "twfe"]


# 记忆服务地址：云端部署时用 ACA_REME_BASE_URL 指向独立部署的 ReMe，
# 未配置则用本机默认地址；连不上时记忆功能自动降级为离线，不影响主流程。
DEFAULT_REME_BASE_URL = os.getenv("ACA_REME_BASE_URL", "http://127.0.0.1:2333")


class AcademicWorkflowCoordinator:
    """学术全流程编排协调器"""

    def __init__(
        self,
        reme_base_url: str = DEFAULT_REME_BASE_URL,
        output_dir: Optional[str] = None,
    ):
        self.memory_client = ReMeMemoryClient(base_url=reme_base_url)
        self.search_agent = LiteratureSearchAgent()
        self.review_agent = LiteratureReviewAgent()
        self.empirical_agent = EmpiricalAgent(output_dir=output_dir)
        self.output_dir = Path(output_dir) if output_dir else \
            Path(__file__).resolve().parents[1] / "part2-empirical-research" / "deliverables"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 单独调用
    # ------------------------------------------------------------------
    def run_literature(
        self,
        research_question: str,
        max_records: int = 20,
        start_year: int = 2010,
        end_year: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """只跑文献检索"""
        end_year = end_year or datetime.now().year
        out = self.search_agent.plan_and_search(
            research_question=research_question,
            max_records=max_records,
            start_year=start_year,
            end_year=end_year,
        )
        if session_id:
            self.memory_client.save_session_memory(session_id, "literature_search", out)
        return out

    def run_empirical(
        self,
        task: Any,
        session_id: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """只跑实证分析（同样落库留痕，便于事后回溯）"""
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        chain = self._strategy_chain(task)
        store.create_run(
            run_id=run_id, session_id=session_id or "",
            research_topic=self._question_of(task),
            task=task if isinstance(task, dict) else {},
            strategy_chain=chain,
        )
        out = self.empirical_agent.execute(task, output_dir=output_dir or str(self.output_dir))
        out["run_id"] = run_id
        _att = out.get("att") or {}
        store.update_run(
            run_id,
            status=out.get("status", "unknown"),
            strategy_used=out.get("strategy_used", chain[0] if chain else ""),
            verdict=(out.get("review") or {}).get("verdict", ""),
            result_json={k: v for k, v in out.items() if k != "raw"},
            att_coef=_att.get("coef"),
            att_se=_att.get("se"),
            att_p=_att.get("p_value"),
            attempts=1,
            skill_trace=out.get("skill_trace", []),
        )
        if session_id:
            self.memory_client.save_session_memory(session_id, "empirical_analysis", out)
        return out

    def run_writing(
        self,
        research_question: str,
        literature_records: Optional[List[Dict[str, Any]]] = None,
        empirical_results: Optional[Dict[str, Any]] = None,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        target_journal: str = "经济研究",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """只跑写作"""
        draft = self.review_agent.compose_full_academic_paper(
            research_question=research_question,
            literature_records=literature_records,
            empirical_results=empirical_results,
            hypotheses=hypotheses,
            target_journal=target_journal,
        )
        out = draft.model_dump()
        if session_id:
            self.memory_client.save_session_memory(session_id, "paper_draft", out)
        return out

    # ------------------------------------------------------------------
    # 带回环的组合运行
    # ------------------------------------------------------------------
    def run_empirical_with_loopback(
        self,
        task: Any,
        session_id: Optional[str] = None,
        max_attempts: int = 3,
        on_event=None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行实证并在审稿人判定为致命缺陷时换策略重跑。

        :param task: TaskSpec（或其等价字典）
        :param max_attempts: 最多尝试次数
        :param on_event: 可选回调 fn(event_type, message, progress)，用于向前端推送
        :param run_id: 归属的运行记录 ID，用于落库留痕
        """
        attempted: List[str] = []
        carried_reasons: List[str] = []
        last: Dict[str, Any] = {}
        strategy_chain = self._strategy_chain(task)
        run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        # 单独调用本方法时也要建主记录，否则 run_steps 会成为没有主记录的孤儿行
        store.create_run(
            run_id=run_id,
            session_id=session_id or "",
            research_topic=self._question_of(task),
            task=task if isinstance(task, dict) else {},
            strategy_chain=strategy_chain,
        )

        for i, strategy in enumerate(strategy_chain[:max_attempts], start=1):
            attempt_task = self._with_strategy(task, strategy)
            if on_event:
                on_event("strategy_attempt", f"第 {i}/{min(len(strategy_chain), max_attempts)} 次尝试：识别策略 {strategy}", 5 + i * 5)
            logger.info("实证回环 第 %d 次尝试，策略=%s", i, strategy)

            last = self.empirical_agent.execute(attempt_task, output_dir=str(self.output_dir))
            attempted.append(strategy)

            if last.get("status") == "failed":
                reason = "；".join(last.get("errors", []))
                logger.warning("策略 %s 执行失败：%s", strategy, reason)
                store.add_step(run_id, "empirical_attempt", strategy, "failed",
                               reasons=last.get("errors", []))
                if on_event:
                    on_event("strategy_failed", f"策略 {strategy} 未能执行：{reason}", 5 + i * 5)
                continue

            verdict = (last.get("review") or {}).get("verdict")
            store.add_step(
                run_id, "empirical_attempt", strategy,
                status=last.get("status", ""),
                verdict=verdict or "",
                reasons=(last.get("review") or {}).get("reasons", []),
                payload={"att": last.get("att"), "attempt": i},
            )
            if verdict != "red":
                logger.info("策略 %s 通过审查（%s）", strategy, verdict)
                break

            reasons = (last.get("review") or {}).get("reasons", [])
            # 前序策略判红的原因要向后传递：备用策略可能压根不做该项诊断，
            # 不能因为"没检查"就显示通过。
            carried_reasons.extend(f"[策略 {strategy} 未通过] {r}" for r in reasons)
            logger.warning("策略 %s 被判定为致命缺陷：%s", strategy, reasons)
            if on_event:
                on_event("strategy_rejected", f"策略 {strategy} 未通过审稿：{'；'.join(reasons)}", 5 + i * 5)
            if i >= min(len(strategy_chain), max_attempts):
                break

        # 若最终策略通过，但此前有策略被判红，则降级为黄灯并保留继承的疑虑
        if carried_reasons and last.get("review") is not None:
            rev = last["review"]
            if rev.get("verdict") == "green":
                rev["verdict"] = "yellow"
            rev["reasons"] = list(rev.get("reasons", [])) + carried_reasons
            rev["remediation"] = list(rev.get("remediation", [])) + [
                "前序识别策略曾未通过审稿，当前结论依赖于未复检同一诊断项的备用策略，投稿前须人工复核"
            ]
        last["carried_concerns"] = carried_reasons

        if last.get("review") is not None:
            last.setdefault("review", {})
            last["review"]["attempted_strategies"] = attempted
        last["attempted_strategies"] = attempted
        last["run_id"] = run_id

        att = last.get("att") or {}
        store.update_run(
            run_id,
            status=last.get("status", "unknown"),
            strategy_used=last.get("strategy_used", ""),
            verdict=(last.get("review") or {}).get("verdict", ""),
            result_json={k: v for k, v in last.items() if k != "raw"},
            strategy_chain=attempted,
            att_coef=att.get("coef"),
            att_se=att.get("se"),
            att_p=att.get("p_value"),
            attempts=len(attempted),
            skill_trace=last.get("skill_trace", []),
        )
        for art in (last.get("deliverables_manifest") or {}).get("artifacts", []) or []:
            if isinstance(art, dict) and art.get("path"):
                store.add_artifact(run_id, art.get("kind", "file"), art.get("name", ""), art.get("path"))

        if session_id:
            self.memory_client.save_session_memory(session_id, "empirical_analysis", last)
        return last

    @staticmethod
    def _strategy_chain(task: Any) -> List[str]:
        """根据用户指定的策略生成回退链；auto 时从默认链首开始"""
        if isinstance(task, dict):
            explicit = (task.get("strategy") or "auto")
        else:
            explicit = getattr(task, "strategy", "auto") or "auto"
        if explicit and explicit != "auto":
            return [explicit] + [s for s in STRATEGY_FALLBACK_CHAIN if s != explicit]
        return list(STRATEGY_FALLBACK_CHAIN)

    @staticmethod
    def _with_strategy(task: Any, strategy: str) -> Any:
        """返回替换了 strategy 的任务副本"""
        if isinstance(task, dict):
            new = dict(task)
            new["strategy"] = strategy
            return new
        try:
            return task.model_copy(update={"strategy": strategy})
        except Exception:
            return task

    def run_pipeline(
        self,
        task: Any,
        enable_search: bool = True,
        enable_empirical: bool = True,
        enable_writing: bool = True,
        max_attempts: int = 3,
        session_id: Optional[str] = None,
        on_event=None,
    ) -> Dict[str, Any]:
        """组合运行三个子智能体"""
        session_id = session_id or f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        research_question = self._question_of(task)
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        store.create_run(
            run_id=run_id,
            session_id=session_id,
            research_topic=research_question,
            task=task if isinstance(task, dict) else getattr(task, "model_dump", lambda: {})(),
            strategy_chain=self._strategy_chain(task),
        )

        logger.info("==== 工作流启动 %s | run=%s | 课题：%s ====", session_id, run_id, research_question)
        result: Dict[str, Any] = {
            "session_id": session_id,
            "run_id": run_id,
            "research_topic": research_question,
            "stages": {},
        }

        search_out: Dict[str, Any] = {}
        if enable_search:
            if on_event:
                on_event("search", "文献检索智能体启动", 5)
            search_out = self.run_literature(research_question, session_id=session_id)
            result["stages"]["literature_search"] = search_out.get("status", "unknown")
            result["literature_search"] = search_out

        empirical_out: Dict[str, Any] = {}
        if enable_empirical:
            if on_event:
                on_event("empirical", "因果实证智能体启动", 30)
            empirical_out = self.run_empirical_with_loopback(
                task, session_id=session_id, max_attempts=max_attempts, on_event=on_event,
                run_id=run_id,
            )
            result["stages"]["empirical"] = empirical_out.get("status", "unknown")
            result["empirical"] = empirical_out

        paper_out: Dict[str, Any] = {}
        if enable_writing:
            if on_event:
                on_event("writing", "论文写作智能体启动", 75)
            # 文献来源优先级：本次检索结果 > 任务自带的文献上下文
            lit_records = (search_out or {}).get("records") or list(getattr(task, "literature_records", []) or [])
            hyp = self.review_agent.synthesize_and_derive_hypotheses(
                research_question=research_question,
                literature_records=lit_records,
            )
            paper_out = self.run_writing(
                research_question=research_question,
                literature_records=lit_records,
                empirical_results=empirical_out,
                hypotheses=hyp.get("hypotheses", []),
                target_journal=self._journal_of(task),
                session_id=session_id,
            )
            result["stages"]["writing"] = "ok" if paper_out.get("sections") else "failed"
            result["hypotheses"] = hyp
            result["paper"] = paper_out

            if paper_out.get("sections"):
                store.add_artifact(run_id, "paper", "academic_full_paper.md",
                                   str(self.output_dir / f"academic_full_paper_{session_id}.md"),
                                   {"journal": self._journal_of(task),
                                    "sections": list(paper_out["sections"].keys())})

        result["status"] = "completed" if not self._has_blocker(result) else "completed_with_warnings"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        store.update_run(
            run_id,
            status=result["status"],
            strategy_used=(result.get("empirical") or {}).get("strategy_used", ""),
            verdict=((result.get("empirical") or {}).get("review") or {}).get("verdict", ""),
            result_json={k: v for k, v in result.items() if k not in ("empirical", "paper")},
        )
        self.memory_client.save_session_memory(session_id, "pipeline_result", result)
        logger.info("==== 工作流结束 %s | run=%s ====", session_id, run_id)
        return result

    @staticmethod
    def _has_blocker(result: Dict[str, Any]) -> bool:
        emp = result.get("empirical") or {}
        if emp.get("status") == "failed":
            return True
        if (emp.get("review") or {}).get("verdict") == "red":
            return True
        paper = result.get("paper") or {}
        if paper and not paper.get("sections"):
            return True
        return False

    @staticmethod
    def _question_of(task: Any) -> str:
        if isinstance(task, dict):
            return task.get("research_question") or task.get("topic") or ""
        return getattr(task, "research_question", "") or ""

    @staticmethod
    def _journal_of(task: Any) -> str:
        v = task.get("target_journal") if isinstance(task, dict) else getattr(task, "target_journal", None)
        return v or "经济研究"

    # ------------------------------------------------------------------
    # 综合报告
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 对话分发（前端 /api/chat 使用）
    # ------------------------------------------------------------------
    def dispatch_chat(
        self,
        session_id: str,
        target_agent: str,
        user_message: str,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """单智能体自然语言对话分发"""
        ctx = session_context or {}
        chat_history = ctx.get("chat_history", [])

        if academic_llm_client.is_available():
            status = academic_llm_client.chat_completion_with_status(
                target_agent=target_agent,
                user_message=user_message,
                context_data=ctx,
                chat_history=chat_history,
            )
            if status.get("success"):
                reply = status.get("reply", "")
            else:
                banner = (
                    f"> ⚠️ 大模型调用失败：`{status.get('error', '未知错误')}`\n"
                    f"> 已切换为基于当前会话真实结果的本地答复。\n\n"
                )
                reply = banner + self._local_chat(target_agent, user_message, ctx)
        else:
            reply = self._local_chat(target_agent, user_message, ctx) + \
                "\n\n*(当前未配置大模型 API，以上答复仅基于会话中已有的真实结果，未调用模型)*"

        self.memory_client.save_session_memory(session_id, f"chat_{datetime.now().strftime('%H%M%S')}", {
            "target_agent": target_agent,
            "user_message": user_message,
            "agent_reply": reply,
        })
        return reply

    def _local_chat(self, target_agent: str, user_message: str, ctx: Dict[str, Any]) -> str:
        """无模型时基于会话真实数据作答，不编造数值"""
        if target_agent in ("literature_search", "search_agent", "part1"):
            return self.search_agent.chat(user_message, ctx)
        if target_agent in ("empirical_research", "empirical_agent", "part2"):
            return self.empirical_agent.chat(user_message, ctx)
        if target_agent in ("academic_writing", "writing_agent", "literature_review", "part3"):
            return self.review_agent.chat(user_message, ctx)

        topic = (ctx.get("task_input") or {}).get("research_topic") or ctx.get("topic") or "当前课题"
        return (
            f"### 学术全流程协同编排总控\n\n"
            f"课题《{topic}》。可分别调用：\n"
            f"1. **文献检索**：在文献检索面板按主题发起多源检索；\n"
            f"2. **实证分析**：需先指定数据文件与列角色（个体、时间、被解释变量、首次处理年份）；\n"
            f"3. **论文写作**：需要配置大模型 API，且建议先完成前两步。\n"
        )

    def dispatch_chat_stream(
        self,
        session_id: str,
        target_agent: str,
        user_message: str,
        session_context: Optional[Dict[str, Any]] = None,
    ):
        """流式对话分发，产出 SSE 帧：thought / content / done / error"""
        import time

        ctx = session_context or {}
        chat_history = ctx.get("chat_history", [])

        if academic_llm_client.is_available():
            for frame in academic_llm_client.stream_chat_completion(
                target_agent=target_agent,
                user_message=user_message,
                context_data=ctx,
                chat_history=chat_history,
            ):
                ftype = frame.get("type")
                if ftype == "done":
                    self.memory_client.save_session_memory(session_id, f"chat_{datetime.now().strftime('%H%M%S')}", {
                        "target_agent": target_agent,
                        "user_message": user_message,
                        "agent_reply": frame.get("full_content", ""),
                        "thought_process": frame.get("full_thought", ""),
                    })
                    yield frame
                    return
                if ftype == "error":
                    yield {
                        "type": "error_banner",
                        "error": frame.get("error", "外部模型请求中断"),
                        "banner": f"> 外部模型响应异常：`{frame.get('error')}`，已切换为本地答复。\n\n",
                    }
                    break
                yield frame

        body = self._local_chat(target_agent, user_message, ctx)
        for idx in range(0, len(body), 5):
            yield {"type": "content", "delta": body[idx:idx + 5]}
            time.sleep(0.012)
        self.memory_client.save_session_memory(session_id, f"chat_{datetime.now().strftime('%H%M%S')}", {
            "target_agent": target_agent,
            "user_message": user_message,
            "agent_reply": body,
        })
        yield {"type": "done", "full_content": body, "full_thought": ""}

    def _assemble_synthesis_report(
        self,
        session_id: str,
        research_topic: str,
        search_result: Dict[str, Any],
        review_result: Dict[str, Any],
        empirical_output: Dict[str, Any],
    ) -> str:
        """汇编综合交付报告。数值全部取自真实结果。"""
        att = (empirical_output or {}).get("att") or {}
        coef = att.get("coef")
        se = att.get("se")
        p = att.get("p_value")
        prof = (empirical_output or {}).get("data_profile") or {}
        pre = ((empirical_output or {}).get("pre_trend_test") or {}).get("evidence") or {}
        sens = (empirical_output or {}).get("sensitivity") or {}
        rev = (empirical_output or {}).get("review") or {}
        prov = (empirical_output or {}).get("provenance", "unknown")

        if coef is None:
            att_line = "未得到可用估计量。"
        else:
            stars = "***" if (p is not None and p < 0.01) else ("**" if (p is not None and p < 0.05) else ("*" if (p is not None and p < 0.1) else ""))
            att_line = f"核心估计量 **{coef:.4f}{stars}**（聚类稳健标准误 {se}，p = {p}），{'统计显著' if (p is not None and p < 0.1) else '不显著'}。"

        pt_line = (
            f"平行趋势联合检验：卡方 {pre.get('statistic'):.4f}（df={pre.get('df')}），p = {pre['p_value']:.4f}，"
            + ("未拒绝平行趋势假设。" if pre.get("p_value", 1) > 0.05 else "平行趋势假设被拒绝。")
        ) if pre.get("p_value") is not None else "平行趋势联合检验：不可用。"

        mb = sens.get("m_bar")
        sens_line = (
            "敏感性分析不可用。" if mb is None
            else ("处理前无趋势违背，结论不受相对幅度约束影响。" if mb == float("inf")
                  else f"可容忍的处理后趋势违背为处理前最大违背的 {mb:.2f} 倍。")
        )

        recs = (search_result or {}).get("records", [])
        rec_lines = [
            f"{i}. **{r.get('title','无标题')}**（{r.get('year','n.d.')}），*{r.get('venue','来源未知')}*"
            for i, r in enumerate(recs[:8], start=1)
        ]

        return f"""# 学术全流程综合交付报告

- **研究课题**：{research_topic}
- **会话标识**：`{session_id}`
- **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **数据性质**：{"演示数据（不可用于正式研究）" if prov == "demo" else "真实数据"}

---

## 一、文献检索

- 检索状态：{(search_result or {}).get('status', '未执行')}
- 纳入文献：{len(recs)} 篇
{chr(10).join(rec_lines) if rec_lines else "（未检索到文献）"}
{chr(10).join('- ' + e for e in (search_result or {}).get('errors', []))}

---

## 二、因果实证

- 识别策略：{(empirical_output or {}).get('strategy_used', '—')}
- 样本：{prof.get('n_obs', '—')} 个观测 / {prof.get('n_units', '—')} 个个体 / {prof.get('n_periods', '—')} 个时期
- {att_line}
- {pt_line}
- {sens_line}
- 审稿人判定：**{rev.get('verdict', '—')}**
{chr(10).join('- ' + r for r in rev.get('reasons', []))}
{chr(10).join('- 补救建议：' + r for r in rev.get('remediation', []))}
- 尝试过的策略：{', '.join((empirical_output or {}).get('attempted_strategies', [])) or '—'}

---

## 三、论文正文

{('已生成章节：' + '、'.join((review_result or {}).get('sections', {}).keys())) if (review_result or {}).get('sections') else '未生成正文（' + '；'.join((review_result or {}).get('warnings', ['写作智能体未产出'])) + '）'}
"""
