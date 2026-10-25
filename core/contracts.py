# -*- coding: utf-8 -*-
"""
统一数据契约层 (Contracts)

三个子智能体之间、以及子智能体与编排层之间，只通过这里定义的结构交换数据。
任何新增字段都必须在这里声明，禁止在调用方私自拼字典。

设计原则：
1. 字段语义唯一：不再出现 empirical_agent 的 data_config 与 agent_api 的 dependent_var 两套说法。
2. 可选字段显式为 None，不允许用默认值掩盖"用户没填"。
3. 所有结果对象都带 provenance（来源），可区分真实估计与演示数据。
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# 数据侧
# ----------------------------------------------------------------------------

class DataSpec(BaseModel):
    """数据集与列角色映射。列角色由用户显式指定，系统不做猜测性推断。"""

    file_path: Optional[str] = Field(
        default=None,
        description="数据文件路径，支持 csv / xlsx / parquet / dta。为 None 时必须显式开启 demo_mode。",
    )
    id_col: Optional[str] = Field(default=None, description="个体标识列")
    time_col: Optional[str] = Field(default=None, description="时间列")
    outcome_col: Optional[str] = Field(default=None, description="被解释变量")

    # 处理变量：两种写法二选一
    treatment_col: Optional[str] = Field(
        default=None,
        description="0/1 处理状态列（每个个体每年是否有处理）",
    )
    g_col: Optional[str] = Field(
        default=None,
        description="首次处理年份列 g；0 或 NaN 表示从未处理。多期错位 DID 必需。",
    )

    controls: List[str] = Field(default_factory=list, description="控制变量")
    mediators: List[str] = Field(default_factory=list, description="机制/中介变量，不得进入控制集")
    moderators: List[str] = Field(default_factory=list, description="调节变量，用于交互项")
    fe_cols: List[str] = Field(default_factory=list, description="额外固定效应列")
    cluster_col: Optional[str] = Field(default=None, description="聚类层级列，缺省用 id_col")

    # IV 专用：内生解释变量与工具变量
    endogenous_col: Optional[str] = Field(
        default=None,
        description="IV 的内生解释变量；缺省时用 treatment_col（0/1 处理变量）",
    )
    instrument_cols: List[str] = Field(
        default_factory=list,
        description="IV 的工具变量列（可多个，用于过度识别检验与 AR 置信集）",
    )

    def missing_roles(self) -> List[str]:
        """返回尚未指定、但执行所必需的列角色"""
        need = {
            "id_col": self.id_col,
            "time_col": self.time_col,
            "outcome_col": self.outcome_col,
        }
        miss = [k for k, v in need.items() if not v]
        if not self.treatment_col and not self.g_col:
            miss.append("treatment_col 或 g_col")
        return miss


class DataProfile(BaseModel):
    """数据结构审计结果，决定识别策略的可用性"""

    n_obs: int = 0
    n_units: int = 0
    n_periods: int = 0
    time_min: Optional[float] = None
    time_max: Optional[float] = None
    balanced: bool = False
    has_never_treated: bool = False
    treatment_timings: List[float] = Field(default_factory=list)
    staggered: bool = False
    missing_rate: Dict[str, float] = Field(default_factory=dict)
    outcome_stats: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# 任务侧
# ----------------------------------------------------------------------------

StrategyName = Literal[
    "auto",
    "twfe",
    "cs_did",
    "event_study",
    "iv",
    "rdd",
    "synthetic_control",
    "matching",
]


class TaskSpec(BaseModel):
    """贯穿三层的唯一任务契约"""

    research_question: str = Field(default="", description="研究问题")
    hypothesis: Optional[str] = Field(default=None, description="待检验假说")

    data: DataSpec = Field(default_factory=DataSpec)

    strategy: StrategyName = Field(default="auto", description="识别策略；auto 时由审计结果路由")
    allow_fallback: bool = Field(default=True, description="审计不通过时是否允许降级换策略")
    max_strategy_attempts: int = Field(default=3, description="回环重选策略的最大次数")

    demo_mode: bool = Field(
        default=False,
        description="演示模式：无真实数据时合成面板。为 True 时交付物必须打演示水印。",
    )
    output_directory: Optional[str] = Field(default=None, description="交付物输出目录")

    # 写作与检索的可选上下文
    literature_records: List[Dict[str, Any]] = Field(default_factory=list)
    target_journal: Optional[str] = Field(default=None, description="目标期刊，决定排版格式")

    def validate_for_empirical(self) -> List[str]:
        """返回阻止执行的错误列表；空列表表示可执行"""
        errs: List[str] = []
        if not self.data.file_path and not self.demo_mode:
            errs.append("未指定数据文件且未开启 demo_mode，无法执行实证分析")
        miss = self.data.missing_roles()
        if miss:
            errs.append("缺少必要的列角色映射: " + ", ".join(miss))
        if self.strategy == "iv":
            if not self.data.instrument_cols:
                errs.append("策略为 iv 但未指定工具变量列（instrument_cols）")
            if not (self.data.endogenous_col or self.data.treatment_col):
                errs.append("策略为 iv 但未指定内生解释变量（endogenous_col 或 treatment_col）")
        return errs


# ----------------------------------------------------------------------------
# 估计结果侧
# ----------------------------------------------------------------------------

class Estimate(BaseModel):
    """单个估计量"""

    coef: float
    se: Optional[float] = None
    p_value: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    t_stat: Optional[float] = None
    n_obs: int = 0


class EventStudyPoint(BaseModel):
    rel_year: int
    estimate: Estimate


class SensitivityResult(BaseModel):
    """平行趋势违背的敏感性分析"""

    method: str = "rm_relative_magnitudes"
    m_bar: Optional[float] = None
    breakdown_m_bar: Optional[float] = None
    conclusion: str = ""
    detail: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


ReviewVerdict = Literal["green", "yellow", "red"]


class ReviewResult(BaseModel):
    verdict: ReviewVerdict = "yellow"
    reasons: List[str] = Field(default_factory=list)
    remediation: List[str] = Field(default_factory=list)
    attempted_strategies: List[str] = Field(default_factory=list)


class EmpiricalResult(BaseModel):
    """实证子智能体的标准输出"""

    module_id: str = "empirical-research"
    research_question: str = ""
    strategy_used: Optional[str] = None
    data_profile: DataProfile = Field(default_factory=DataProfile)
    att: Optional[Estimate] = None
    event_study: List[EventStudyPoint] = Field(default_factory=list)
    pre_trend_test: Optional[DiagnosticResult] = None
    sensitivity: Optional[SensitivityResult] = None
    heterogeneity: List[Dict[str, Any]] = Field(default_factory=list)
    mechanism: List[Dict[str, Any]] = Field(default_factory=list)
    diagnostics: List[DiagnosticResult] = Field(default_factory=list)
    review: ReviewResult = Field(default_factory=ReviewResult)
    collinearity: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = Field(default="real", description="real 或 demo")
    warnings: List[str] = Field(default_factory=list)
    deliverables: Dict[str, Any] = Field(default_factory=dict)


class PaperDraft(BaseModel):
    """写作子智能体的标准输出"""

    module_id: str = "academic-writing"
    research_question: str = ""
    target_journal: Optional[str] = None
    sections: Dict[str, str] = Field(default_factory=dict)
    full_text: str = ""
    word_count: int = 0
    provenance: str = Field(default="llm", description="llm 或 template")
    warnings: List[str] = Field(default_factory=list)


class RunState(BaseModel):
    """编排层的一次运行态，支持回环与续跑"""

    session_id: str
    status: Literal["idle", "running", "completed", "failed", "awaiting_input"] = "idle"
    current_stage: Optional[str] = None
    stages: Dict[str, str] = Field(default_factory=dict)
    attempts: Dict[str, int] = Field(default_factory=dict)
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    search: Optional[Dict[str, Any]] = None
    empirical: Optional[EmpiricalResult] = None
    paper: Optional[PaperDraft] = None
    errors: List[str] = Field(default_factory=list)
