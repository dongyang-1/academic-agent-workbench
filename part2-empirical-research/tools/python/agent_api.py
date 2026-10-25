# -*- coding: utf-8 -*-
"""
实证分析子智能体 · 统一入口

对外只接受 core.contracts.TaskSpec（或其可转换形式）。执行链路：

    载入数据 -> 结构审计 -> 控制变量净化（剔除中介与共线性）
    -> 识别策略路由 -> 真实估计 -> 诊断与审稿人判定 -> 交付物落盘

本模块不再合成"看起来像真的"数据：demo_mode 为 False 时必须提供真实数据文件，
否则直接返回错误。所有系数、标准误、p 值均来自输入数据的真实估计。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
INTEGRATED_ROOT = CURRENT_DIR.parents[2]
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from core.contracts import (  # noqa: E402
    DataProfile,
    DiagnosticResult,
    EmpiricalResult,
    Estimate,
    EventStudyPoint,
    ReviewResult,
    SensitivityResult,
    TaskSpec,
)

import econ_core as ec  # noqa: E402
from deliverables_generator import AcademicDeliverablesGenerator  # noqa: E402

try:  # 路径可移植：落盘时统一写成相对项目根
    from core.paths import to_rel as _to_rel, abs_path as _abs_path
except Exception:  # pragma: no cover - 兜底，保证离线可用
    def _to_rel(p):
        try:
            return Path(p).resolve().relative_to(INTEGRATED_ROOT).as_posix()
        except Exception:
            return str(p)

    def _abs_path(p):
        s = str(p)
        return s if os.path.isabs(s) and os.path.exists(s) else str(INTEGRATED_ROOT / s)


def _relativize(obj):
    """递归把结构里的绝对路径改写为相对项目根，方便整目录搬到云上。"""
    if isinstance(obj, str):
        return _to_rel(obj) if (obj.startswith("/") or ":\\" in obj or ":/" in obj) else obj
    if isinstance(obj, dict):
        return {k: _relativize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_relativize(v) for v in obj]
    return obj

logger = logging.getLogger("EmpiricalSubAgent")

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "deliverables"

# 真正实现了估计内核的策略。其余策略（rdd / synthetic_control / matching …）
# 会返回明确的"未实现"错误，绝不静默降级为 TWFE——静默降级会产出看似正常的
# 虚假结果。
IMPLEMENTED_STRATEGIES = {"auto", "twfe", "cs_did", "event_study", "iv"}


# ----------------------------------------------------------------------------
# 输入与数据
# ----------------------------------------------------------------------------

LEGACY_KEY_MAP = {
    "dependent_var": ("data", "outcome_col"),
    "policy_shock": None,
    "candidate_controls": ("data", "controls"),
    "topic": ("research_question",),
}


def _coerce_task(task_input: Union[TaskSpec, Dict[str, Any], str, Path]) -> TaskSpec:
    """把各种历史写法统一收敛到 TaskSpec"""
    if isinstance(task_input, TaskSpec):
        return task_input
    if isinstance(task_input, (str, Path)):
        p = Path(task_input)
        if p.exists():
            return TaskSpec.model_validate_json(p.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"任务文件不存在: {p}")
    if isinstance(task_input, dict):
        data = dict(task_input)
        # 兼容旧版扁平字段
        if "data" not in data:
            data["data"] = {}
        for legacy, target in LEGACY_KEY_MAP.items():
            if legacy in data and target:
                if len(target) == 1:
                    data.setdefault(target[0], data.pop(legacy))
                else:
                    data[target[0]].setdefault(target[1], data.pop(legacy))
        if "topic" in data and not data.get("research_question"):
            data["research_question"] = data.pop("topic")
        try:
            return TaskSpec.model_validate(data)
        except Exception:
            # 未知字段直接忽略，只保留 TaskSpec 认得的键
            allowed = set(TaskSpec.model_fields)
            allowed_data = set(type(TaskSpec()).data.model_fields)
            clean: Dict[str, Any] = {}
            for k, v in data.items():
                if k in allowed:
                    clean[k] = v
            if isinstance(clean.get("data"), dict):
                clean["data"] = {k: v for k, v in clean["data"].items() if k in allowed_data}
            return TaskSpec.model_validate(clean)
    raise TypeError(f"无法识别的任务输入类型: {type(task_input)}")


def load_data(file_path: Optional[str]) -> pd.DataFrame:
    """按扩展名载入数据，不做任何内容改写"""
    if not file_path:
        raise ValueError("未提供数据文件路径")
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"数据文件不存在: {p}")
    suffix = p.suffix.lower()
    if suffix in (".csv", ".txt"):
        return pd.read_csv(p)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if suffix == ".parquet":
        return pd.read_parquet(p)
    if suffix == ".dta":
        return pd.read_stata(p)
    if suffix == ".json":
        return pd.read_json(p)
    raise ValueError(f"暂不支持的数据格式: {suffix}（支持 csv/xlsx/parquet/dta/json）")


def build_demo_panel(n_units: int = 240, years: range = range(2015, 2023), tau: float = 0.8, seed: int = 7) -> pd.DataFrame:
    """
    演示面板。仅用于 demo_mode，DGP 明确、效应已知（tau），并在交付物上打演示水印。
    """
    rng = np.random.default_rng(seed)
    ids = np.arange(n_units)
    cut = rng.random(n_units)
    g = np.zeros(n_units)
    g[(cut >= 0.40) & (cut < 0.60)] = 2018
    g[(cut >= 0.60) & (cut < 0.80)] = 2019
    g[cut >= 0.80] = 2020
    unit_fe = rng.normal(0, 1.0, n_units)
    x = rng.normal(0, 1.0, n_units)
    rows = []
    for i in ids:
        for t in years:
            treated = 1.0 if (g[i] > 0 and t >= g[i]) else 0.0
            y = unit_fe[i] + 0.05 * (t - 2015) + tau * treated + 0.3 * x[i] + rng.normal(0, 0.25)
            rows.append({"id": i, "year": t, "y": y, "g": g[i], "x": x[i], "did": treated})
    return pd.DataFrame(rows)


def derive_g_column(df: pd.DataFrame, id_col: str, time_col: str, treatment_col: str, g_col_name: str = "_g") -> pd.DataFrame:
    """由 0/1 处理状态列推导首次处理年份 g；从未处理为 0"""
    out = df.copy()
    tnum = pd.to_numeric(out[time_col], errors="coerce")
    dnum = pd.to_numeric(out[treatment_col], errors="coerce").fillna(0)
    tmp = pd.DataFrame({"id": out[id_col], "t": tnum, "d": dnum})
    first = tmp[tmp["d"] > 0].groupby("id")["t"].min()
    out[g_col_name] = out[id_col].map(first).fillna(0.0)
    return out


# ----------------------------------------------------------------------------
# 控制变量净化
# ----------------------------------------------------------------------------

def sanitize_controls(
    df: pd.DataFrame,
    controls: Sequence[str],
    mediators: Sequence[str] = (),
    outcome_col: Optional[str] = None,
) -> Dict[str, Any]:
    """
    控制变量净化：
    1. 剔除中介变量（坏控制，会吸收掉待估计的因果路径）
    2. 剔除与其余变量完全共线的列
    3. 剔除在被解释变量上全缺失导致不可用的列
    """
    info: Dict[str, Any] = {"removed_bad_controls": [], "removed_collinear": [], "kept": []}
    cand = [c for c in controls if c in df.columns]
    dropped_missing = [c for c in cand if df[c].notna().sum() == 0]

    med = set(mediators)
    kept = [c for c in cand if c not in med and c not in dropped_missing]
    info["removed_bad_controls"] = [c for c in cand if c in med]
    info["removed_missing"] = dropped_missing

    if kept:
        rep = ec.collinearity_report(df[kept])
        info["removed_collinear"] = rep["dropped"]
        kept = rep["kept"]
    info["kept"] = kept
    return info


# ----------------------------------------------------------------------------
# 审稿人判定
# ----------------------------------------------------------------------------

def review_result(
    profile: Dict[str, Any],
    att: Optional[Dict[str, Any]],
    pre_trend: Dict[str, Any],
    collinearity: Dict[str, Any],
    n_clusters: int,
    sensitivity: Dict[str, Any],
) -> ReviewResult:
    """基于真实诊断给出 🟢/🟡/🔴 判定"""
    reasons: List[str] = []
    remediation: List[str] = []
    red = False

    if att is None or att.get("coef") is None:
        return ReviewResult(verdict="red", reasons=["未能得到可用估计量"], remediation=["检查列角色映射与数据覆盖"])

    p = att.get("p_value")
    if p is not None and np.isfinite(p) and p > 0.1:
        red = True
        reasons.append(f"核心估计量不显著 (p={p:.4f})")
        remediation.append("复核样本量、变量定义与识别策略，或补充更长的样本期")

    pt_p = pre_trend.get("p_value")
    if pt_p is not None and np.isfinite(pt_p) and pt_p < 0.05:
        red = True
        reasons.append(f"平行趋势联合检验未通过 (p={pt_p:.4f})")
        remediation.append("改用条件平行趋势、加入协变量平衡或换用合成控制")

    if n_clusters < 30:
        reasons.append(f"聚类数偏少（{n_clusters}），标准误可能不可靠")
        remediation.append("改用 Wild Bootstrap 聚类标准误")
        red = True

    if collinearity.get("removed_collinear"):
        reasons.append("已自动剔除完全共线变量: " + ", ".join(collinearity["removed_collinear"]))

    if red:
        verdict = "red"
    elif reasons or (sensitivity.get("m_bar") is not None and sensitivity["m_bar"] < 0.5):
        verdict = "yellow"
        if sensitivity.get("m_bar") is not None and sensitivity["m_bar"] < 0.5:
            remediation.append("敏感性较弱，建议补充 HonestDiD 稳健区间并在正文披露")
    else:
        verdict = "green"

    return ReviewResult(verdict=verdict, reasons=reasons or ["未发现阻断性计量问题"], remediation=remediation)


# ----------------------------------------------------------------------------
# 主执行器
# ----------------------------------------------------------------------------

class EmpiricalSubAgent:
    """实证分析子智能体核心执行器"""

    def __init__(self, output_dir: str = "deliverables"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.generator = AcademicDeliverablesGenerator(output_dir=self.output_dir)

    # -- 主入口 -------------------------------------------------------------
    def execute(self, task_input: Union[TaskSpec, Dict[str, Any], str]) -> Dict[str, Any]:
        task = _coerce_task(task_input)

        errs = task.validate_for_empirical()
        if errs:
            return {
                "module_id": "empirical-research",
                "status": "failed",
                "errors": errs,
                "deliverables": {},
            }

        provenance = "demo" if task.demo_mode else "real"
        d = task.data

        # 1. 数据
        if task.demo_mode and not d.file_path:
            df = build_demo_panel()
            warnings_list = ["当前为演示模式：结果基于内置模拟面板，不可用于正式研究"]
            d = d.model_copy(update={
                "id_col": d.id_col or "id",
                "time_col": d.time_col or "year",
                "outcome_col": d.outcome_col or "y",
                "g_col": d.g_col or "g",
            })
        else:
            df = load_data(d.file_path)
            warnings_list = []

        # 2. g 列推导
        g_col = d.g_col
        if not g_col:
            g_col = "_g_derived"
            df = derive_g_column(df, d.id_col, d.time_col, d.treatment_col, g_col)

        # 3. 审计
        profile = ec.profile_panel(df, d.id_col, d.time_col, g_col, d.outcome_col, d.controls)
        profile_obj = DataProfile(**{k: v for k, v in profile.items() if k in DataProfile.model_fields})

        # 4. 控制变量净化
        col_info = sanitize_controls(df, d.controls, d.mediators, d.outcome_col)
        controls = list(col_info["kept"])

        # 5. 策略路由
        strategy = task.strategy
        if strategy == "auto":
            strategy = "cs_did" if (profile["staggered"] or profile["has_never_treated"]) else "twfe"
        if strategy not in IMPLEMENTED_STRATEGIES:
            return {
                "module_id": "empirical-research",
                "status": "failed",
                "errors": [f"策略 {strategy} 的估计内核尚未实现；当前已实现："
                           + "、".join(sorted(IMPLEMENTED_STRATEGIES))
                           + "。未实现策略不会被静默降级成 TWFE。"],
                "deliverables": {},
            }

        # 6. 估计
        att: Optional[Estimate] = None
        event_study: List[EventStudyPoint] = []
        pre_trend: Dict[str, Any] = {}
        sens: Dict[str, Any] = {}
        n_clusters = int(df[d.id_col].nunique())
        extra: Dict[str, Any] = {}

        if strategy == "cs_did":
            boot = ec.bootstrap_event_study(
                df, d.outcome_col, d.id_col, d.time_col, g_col,
                controls=controls,
                cluster_col=d.cluster_col or d.id_col,
                n_boot=100,
                seed=20240,
            )
            se = boot["overall_se"]
            coef = boot["overall"]
            t = coef / se if se and se > 0 else float("nan")
            att = Estimate(
                coef=float(coef), se=float(se), t_stat=float(t),
                p_value=float(ec._t_pvalue(t, max(n_clusters - 1, 1))),
                ci_low=float(coef - 1.96 * se) if se else None,
                ci_high=float(coef + 1.96 * se) if se else None,
                n_obs=int(len(df)),
            )
            for e in sorted(boot["event_study"]):
                c = boot["event_study"][e]
                s = boot["se"].get(e)
                event_study.append(EventStudyPoint(rel_year=int(e), estimate=Estimate(
                    coef=float(c),
                    se=float(s) if s and np.isfinite(s) else None,
                    t_stat=float(c / s) if s and s > 0 else None,
                    p_value=float(ec._t_pvalue(c / s, max(n_clusters - 1, 1))) if s and s > 0 else None,
                    ci_low=float(c - 1.96 * s) if s and np.isfinite(s) else None,
                    ci_high=float(c + 1.96 * s) if s and np.isfinite(s) else None,
                    n_obs=int(len(df)),
                )))
            pre_trend = ec.pre_trend_joint_test(boot)
            sens = ec.sensitivity_relative_magnitudes(coef, se, boot["event_study"])
            extra["att_by_group"] = ec.aggregate_group(
                ec.cs_att_gt(df, d.outcome_col, d.id_col, d.time_col, g_col, controls, d.cluster_col or d.id_col)
            )

        elif strategy == "event_study":
            es = ec.event_study_coefficients(
                df, d.outcome_col, d.id_col, d.time_col, g_col,
                controls=controls,
                cluster_col=d.cluster_col or d.id_col,
                base_period=-1,
            )
            warnings_list.extend(es.get("warnings", []))
            n_clusters = int(es.get("n_clusters") or n_clusters)
            post = es.get("post_att") or {}
            if post.get("coef") is not None:
                att = Estimate(
                    coef=float(post["coef"]), se=float(post["se"]),
                    t_stat=float(post.get("t_stat") or float("nan")),
                    p_value=float(post.get("p_value") or float("nan")),
                    ci_low=float(post["ci_low"]), ci_high=float(post["ci_high"]),
                    n_obs=int(es.get("n_obs") or len(df)),
                )
            for k in sorted(es.get("points", {})):
                p = es["points"][k]
                event_study.append(EventStudyPoint(rel_year=int(k), estimate=Estimate(
                    coef=float(p["coef"]),
                    se=float(p["se"]) if p.get("se") is not None else None,
                    t_stat=p.get("t_stat"),
                    p_value=p.get("p_value"),
                    ci_low=p.get("ci_low"),
                    ci_high=p.get("ci_high"),
                    n_obs=int(es.get("n_obs") or len(df)),
                )))
            pre_trend = {
                "statistic": (es.get("pre_trend") or {}).get("statistic"),
                "df": (es.get("pre_trend") or {}).get("df"),
                "p_value": (es.get("pre_trend") or {}).get("p_value"),
                "detail": (es.get("pre_trend") or {}).get("detail", ""),
            }
            if pre_trend.get("p_value") is not None and att is not None:
                sens = ec.sensitivity_relative_magnitudes(
                    att.coef, att.se or 0.0,
                    {k: v["coef"] for k, v in es.get("points", {}).items()},
                )
            extra["event_study"] = {
                "base_period": es.get("base_period"),
                "window": es.get("window"),
                "binned": es.get("binned"),
                "post_att": post,
            }

        elif strategy == "iv":
            endog = d.endogenous_col or d.treatment_col
            if not endog:
                return {
                    "module_id": "empirical-research",
                    "status": "failed",
                    "errors": ["策略为 iv 但既未指定 endogenous_col 也未指定 treatment_col"],
                    "deliverables": {},
                }
            iv = ec.fit_iv(
                df, d.outcome_col, endog, d.instrument_cols,
                controls=controls,
                fe_cols=[d.id_col, d.time_col, *d.fe_cols],
                cluster_col=d.cluster_col or d.id_col,
            )
            warnings_list.extend(iv.get("warnings", []))
            n_clusters = int(iv.get("n_clusters") or n_clusters)
            if iv.get("coef") is not None:
                att = Estimate(
                    coef=float(iv["coef"]), se=float(iv["se"]),
                    t_stat=float(iv.get("t_stat") or float("nan")),
                    p_value=float(iv.get("p_value") or float("nan")),
                    ci_low=float(iv["ci_low"]), ci_high=float(iv["ci_high"]),
                    n_obs=int(iv.get("n_obs") or len(df)),
                )
            extra["iv"] = iv
            # 弱工具时把 AR 置信集作为判红依据之一
            ar = iv.get("ar_confidence_set") or {}
            if ar.get("n_accepted") == 0:
                pre_trend = {
                    "statistic": None, "df": None, "p_value": 0.0,
                    "detail": "AR 置信集为空：在整个搜索区间内模型被拒绝，工具变量设定不可信",
                }
            elif (iv.get("first_stage") or {}).get("f_excluded") is not None \
                    and iv["first_stage"]["f_excluded"] < 10:
                pre_trend = {
                    "statistic": None, "df": None,
                    "p_value": (0.0 if ar.get("unbounded") else 1.0),
                    "detail": f"一阶段 F = {iv['first_stage']['f_excluded']:.2f} < 10，"
                              f"弱工具；AR 置信集 {ar.get('ci_low')} ~ {ar.get('ci_high')}"
                              + ("（在搜索边界外延伸）" if ar.get("unbounded") else ""),
                }

        elif strategy == "twfe":
            work = df.copy()
            work["_did"] = pd.to_numeric(work[g_col], errors="coerce").gt(0).astype(float) * \
                (pd.to_numeric(work[d.time_col], errors="coerce") >= pd.to_numeric(work[g_col], errors="coerce")).astype(float)
            fit = ec.fit_ols(
                work, d.outcome_col, ["_did", *controls],
                fe_cols=[d.id_col, d.time_col],
                cluster_col=d.cluster_col or d.id_col,
            )
            n_clusters = fit.n_clusters
            att = Estimate(
                coef=float(fit.params.get("_did", float("nan"))),
                se=float(fit.se.get("_did", float("nan"))),
                t_stat=float(fit.tstats.get("_did", float("nan"))),
                p_value=float(fit.pvalues.get("_did", float("nan"))),
                ci_low=float(fit.ci_low.get("_did", float("nan"))),
                ci_high=float(fit.ci_high.get("_did", float("nan"))),
                n_obs=fit.n_obs,
            )
            extra["r_squared"] = fit.r_squared
            extra["fit_warnings"] = fit.warnings
            warnings_list.extend(fit.warnings)

        # 7. 异质性与机制
        het: List[Dict[str, Any]] = []
        for mod in d.moderators:
            if mod in df.columns:
                vals = pd.to_numeric(df[mod], errors="coerce")
                grp = pd.Series(np.where(vals >= vals.median(), f"{mod}_high", f"{mod}_low"), index=df.index)
                tmp = df.copy()
                tmp["_grp_tmp"] = grp
                tmp["_did_tmp"] = (pd.to_numeric(tmp[g_col], errors="coerce").gt(0) &
                                   (pd.to_numeric(tmp[d.time_col], errors="coerce") >= pd.to_numeric(tmp[g_col], errors="coerce"))).astype(float)
                het.extend(ec.heterogeneity_by_group(
                    tmp, d.outcome_col, "_did_tmp", "_grp_tmp", controls,
                    [d.id_col, d.time_col], d.cluster_col or d.id_col,
                ))
        mech: List[Dict[str, Any]] = []
        for med in d.mediators:
            if med in df.columns:
                tmp = df.copy()
                tmp["_did_tmp"] = (pd.to_numeric(tmp[g_col], errors="coerce").gt(0) &
                                   (pd.to_numeric(tmp[d.time_col], errors="coerce") >= pd.to_numeric(tmp[g_col], errors="coerce"))).astype(float)
                mech.append(ec.mechanism_interaction(
                    tmp, d.outcome_col, "_did_tmp", med, controls,
                    [d.id_col, d.time_col], d.cluster_col or d.id_col,
                ))

        # 8. 审稿人判定
        review = review_result(profile, att.model_dump() if att else None, pre_trend, col_info, n_clusters, sens)

        result = EmpiricalResult(
            research_question=task.research_question,
            strategy_used=strategy,
            data_profile=profile_obj,
            att=att,
            event_study=event_study,
            pre_trend_test=DiagnosticResult(
                name="parallel_trends_joint_wald",
                passed=bool(pre_trend.get("p_value") is not None and np.isfinite(pre_trend["p_value"]) and pre_trend["p_value"] > 0.05),
                detail=pre_trend.get("detail", ""),
                evidence=pre_trend,
            ) if pre_trend else None,
            sensitivity=SensitivityResult(**{k: v for k, v in sens.items() if k in SensitivityResult.model_fields}) if sens else None,
            heterogeneity=het,
            mechanism=mech,
            diagnostics=[DiagnosticResult(
                name="control_variable_sanitation",
                passed=not col_info["removed_collinear"],
                detail="控制变量净化结果",
                evidence=col_info,
            )],
            review=review,
            collinearity=col_info,
            provenance=provenance,
            warnings=warnings_list,
        )

        # 9. 交付物
        deliverables = self._render_deliverables(task, df, d, g_col, controls, result, extra, provenance)
        result.deliverables = deliverables

        out = result.model_dump()
        out["status"] = "completed"
        out["att_by_group"] = extra.get("att_by_group", {})
        return out

    # -- 交付物 -------------------------------------------------------------
    def _render_deliverables(
        self,
        task: TaskSpec,
        df: pd.DataFrame,
        d,
        g_col: str,
        controls: List[str],
        result: EmpiricalResult,
        extra: Dict[str, Any],
        provenance: str,
    ) -> Dict[str, Any]:
        gen = self.generator
        y_col = d.outcome_col

        var_labels: Dict[str, str] = {y_col: "被解释变量"}
        for c in controls:
            var_labels[c] = "控制变量"
        desc = gen.generate_descriptive_stats(df, var_labels)

        # 真实的 TWFE 对照列（不再写死）
        work = df.copy()
        work["_did"] = (pd.to_numeric(work[g_col], errors="coerce").gt(0) &
                        (pd.to_numeric(work[d.time_col], errors="coerce") >= pd.to_numeric(work[g_col], errors="coerce"))).astype(float)
        twfe_fit = ec.fit_ols(
            work, y_col, ["_did", *controls],
            fe_cols=[d.id_col, d.time_col],
            cluster_col=d.cluster_col or d.id_col,
        )
        twfe_info = {
            "coef": twfe_fit.params.get("_did"),
            "se": twfe_fit.se.get("_did"),
            "p_value": twfe_fit.pvalues.get("_did"),
            "n_obs": twfe_fit.n_obs,
            "r_squared": twfe_fit.r_squared,
        }

        cs_info = {
            "att": result.att.coef if result.att else None,
            "att_se": result.att.se if result.att else None,
            "p_value": result.att.p_value if result.att else None,
            "n_obs": len(df),
        }

        baseline = gen.generate_baseline_table(
            dep_var_name=y_col,
            treat_var_name="policy_treatment",
            cs_info=cs_info,
            twfe_info=twfe_info,
            controls_used=controls,
            cluster_level=(d.cluster_col or d.id_col),
            watermark=("演示数据" if provenance == "demo" else None),
        )

        figures: Dict[str, Any] = {}
        if result.event_study:
            points = [
                {"rel_year": p.rel_year, "coef": p.estimate.coef, "se": p.estimate.se or 0.0}
                for p in result.event_study
            ]
            try:
                figures["event_study"] = gen.plot_event_study(points)
            except Exception as exc:
                logger.warning("事件研究图绘制失败: %s", exc)
        if result.sensitivity and result.att:
            try:
                payload = result.sensitivity.model_dump()
                payload.update({"att": result.att.coef, "att_se": result.att.se})
                figures["sensitivity"] = gen.plot_honest_did_bounds(payload)
            except Exception as exc:
                logger.warning("敏感性图绘制失败: %s", exc)

        narrative = gen.generate_writing_narrative(
            research_question=task.research_question or "（未填写研究问题）",
            result=result.model_dump(),
            twfe_info=twfe_info,
            provenance=provenance,
        )

        manifest = {
            "module": "empirical-research",
            "provenance": provenance,
            "strategy": result.strategy_used,
            "tables": {
                "table1_descriptive_stats": desc,
                "table2_baseline_regression": baseline,
            },
            "figures": figures,
            "narrative_for_writing": narrative,
        }
        manifest = _relativize(manifest)
        mpath = os.path.join(self.output_dir, "empirical_deliverables_manifest.json")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        manifest["manifest_path"] = _to_rel(mpath)
        return manifest


def run_empirical_task(
    task_input: Union[TaskSpec, Dict[str, Any], str],
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """统一对外接口"""
    out = output_dir or str(DEFAULT_OUTPUT_DIR)
    agent = EmpiricalSubAgent(output_dir=out)
    return agent.execute(task_input)
