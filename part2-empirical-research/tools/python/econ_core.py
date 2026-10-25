# -*- coding: utf-8 -*-
"""
真实计量内核 (Econometric Core)

纯 numpy / scipy 实现，不依赖 pyfixest 或 statsmodels。若环境中装有 statsmodels，
仅在显著性检验上复用其分布函数，估计过程仍由本模块完成。

提供的能力：
1. 高维固定效应吸收（交替投影，FWL 残差）
2. 一维聚类稳健标准误（含小样本修正与少聚类警告）
3. TWFE 基准回归
4. Callaway & Sant'Anna (2021) ATT(g,t) 与三种聚合（simple / dynamic / group）
5. 单位级 Bootstrap：给出事件研究向量的联合协方差，用于真实平行趋势联合检验
6. Rambachan & Roth (2023) 相对幅度敏感性（水平型 RM 变体）与击穿值 M_bar
7. 异质性分组与机制交互项
8. 完全共线性诊断与变量剔除

所有估计都来自输入数据本身，模块内不存在任何写死的系数、标准误或 p 值。
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("econ_core")

try:  # scipy 仅用于分布函数，缺失时退化为正态近似
    from scipy import stats as _scipy_stats
except Exception:  # pragma: no cover
    _scipy_stats = None


# ----------------------------------------------------------------------------
# 基础线性代数
# ----------------------------------------------------------------------------

def _t_pvalue(t: float, df: float) -> float:
    """双尾 t 检验 p 值"""
    if df <= 0 or not np.isfinite(t):
        return float("nan")
    if _scipy_stats is not None:
        return float(2.0 * _scipy_stats.t.sf(abs(t), df))
    return float(math.erfc(abs(t) / math.sqrt(2.0)))


def _chi2_pvalue(stat: float, df: int) -> float:
    if df <= 0 or not np.isfinite(stat):
        return float("nan")
    if _scipy_stats is not None:
        return float(_scipy_stats.chi2.sf(stat, df))
    return float(np.nan)


def _demean(mat: np.ndarray, codes: np.ndarray, n_groups: int) -> np.ndarray:
    """按分组做组内去均值（吸收单个固定效应）"""
    if mat.size == 0:
        return mat
    counts = np.bincount(codes, minlength=n_groups).astype(float)
    counts[counts == 0] = 1.0
    sums = np.zeros((n_groups, mat.shape[1]), dtype=float)
    np.add.at(sums, codes, mat)
    means = sums / counts[:, None]
    return mat - means[codes]


def absorb(mat: np.ndarray, fe_list: Sequence[np.ndarray], tol: float = 1e-10, max_iter: int = 200) -> np.ndarray:
    """
    交替投影吸收多个固定效应，收敛到 FWL 残差 M_fe @ mat。
    依据 von Neumann 交替投影定理：在闭子空间上交替投影收敛到交空间上的投影，
    而各固定效应空间之补的交等于其和之补，故收敛结果即 FWL 所需残差。
    """
    out = np.asarray(mat, dtype=float).copy()
    fe = [c for c in fe_list if c is not None]
    if not fe:
        return out
    for _ in range(max_iter):
        prev = out
        for codes in fe:
            n_groups = int(codes.max()) + 1 if codes.size else 0
            out = _demean(out, codes, n_groups)
        if np.max(np.abs(out - prev)) < tol:
            break
    return out


def collinearity_report(X: pd.DataFrame, name: str = "X") -> Dict[str, Any]:
    """
    逐步加列做秩检验，识别完全共线性并给出建议剔除的列。
    返回：dropped（被剔除）、kept（保留）、rank、n_cols
    """
    cols = list(X.columns)
    if not cols:
        return {"dropped": [], "kept": [], "rank": 0, "n_cols": 0, "details": []}
    kept: List[str] = []
    dropped: List[str] = []
    details: List[Dict[str, str]] = []
    cur = np.zeros((len(X), 0))
    cur_rank = 0
    for c in cols:
        col = X[[c]].to_numpy(dtype=float)
        if not np.all(np.isfinite(col)):
            col = np.nan_to_num(col)
        cand = np.hstack([cur, col]) if cur.shape[1] else col
        r = int(np.linalg.matrix_rank(cand, tol=1e-10))
        if r > cur_rank:
            kept.append(c)
            cur = cand
            cur_rank = r
        else:
            dropped.append(c)
            # 找出与它线性相关的已保留列组合（用最小二乘给出解释）
            try:
                beta, *_ = np.linalg.lstsq(cur, col, rcond=None)
                related = [kept[i] for i in range(len(kept)) if abs(beta[i]) > 1e-8]
            except Exception:
                related = []
            details.append({
                "column": c,
                "reason": "与已保留列线性相关" if related else "常数列或全缺失",
                "related_to": ", ".join(related) if related else "",
            })
    return {"dropped": dropped, "kept": kept, "rank": cur_rank, "n_cols": len(cols), "details": details}


# ----------------------------------------------------------------------------
# OLS 与聚类稳健推断
# ----------------------------------------------------------------------------

@dataclass
class FitResult:
    """一次回归的结果容器"""

    params: Dict[str, float] = field(default_factory=dict)
    se: Dict[str, float] = field(default_factory=dict)
    tstats: Dict[str, float] = field(default_factory=dict)
    pvalues: Dict[str, float] = field(default_factory=dict)
    ci_low: Dict[str, float] = field(default_factory=dict)
    ci_high: Dict[str, float] = field(default_factory=dict)
    n_obs: int = 0
    n_clusters: int = 0
    df_resid: int = 0
    r_squared: float = float("nan")
    vcov_type: str = "cluster"
    warnings: List[str] = field(default_factory=list)
    # 联合检验要用：系数向量协方差矩阵与对应的变量名顺序
    vcov: Optional[np.ndarray] = None
    vcov_names: List[str] = field(default_factory=list)

    def estimate(self, key: str, level: float = 1.96) -> Dict[str, Any]:
        return {
            "coef": self.params.get(key),
            "se": self.se.get(key),
            "t_stat": self.tstats.get(key),
            "p_value": self.pvalues.get(key),
            "ci_low": self.ci_low.get(key),
            "ci_high": self.ci_high.get(key),
            "n_obs": self.n_obs,
        }


def fit_ols(
    df: pd.DataFrame,
    y_col: str,
    x_cols: Sequence[str],
    fe_cols: Sequence[str] = (),
    cluster_col: Optional[str] = None,
    weights: Optional[np.ndarray] = None,
) -> FitResult:
    """
    带固定效应吸收与一维聚类稳健标准误的 OLS。

    :param df: 数据
    :param y_col: 被解释变量
    :param x_cols: 解释变量（不含截距，截距自动添加）
    :param fe_cols: 固定效应列，逐个吸收
    :param cluster_col: 聚类列，缺省按个体聚类
    """
    res = FitResult()
    needed: List[str] = []
    for c in [y_col, *x_cols, *fe_cols] + ([cluster_col] if cluster_col else []):
        if c and c not in needed:
            needed.append(c)
    use = df[needed].dropna()
    n = len(use)
    if n == 0:
        res.warnings.append("有效样本为 0，无法估计")
        return res

    y_raw = use[y_col].to_numpy(dtype=float).reshape(-1, 1)
    X_raw = use[list(x_cols)].to_numpy(dtype=float) if x_cols else np.zeros((n, 0))
    names = ["const"] + list(x_cols)
    X_raw = np.hstack([np.ones((n, 1)), X_raw])

    fe_list = []
    df_fe = 0
    for c in fe_cols:
        codes, _ = pd.factorize(use[c], sort=False)
        fe_list.append(codes)
        df_fe += int(len(np.unique(codes)) - 1)

    y = absorb(y_raw, fe_list)[:, 0]
    X = absorb(X_raw, fe_list)

    # 秩亏处理
    rep = collinearity_report(pd.DataFrame(X, columns=names))
    keep_idx = [names.index(c) for c in rep["kept"]]
    X = X[:, keep_idx]
    keep_names = [names[i] for i in keep_idx]
    if rep["dropped"]:
        res.warnings.append("因完全共线性已剔除: " + ", ".join(rep["dropped"]))

    k = X.shape[1]
    try:
        XtX_inv = np.linalg.pinv(X.T @ X)
    except np.linalg.LinAlgError:
        res.warnings.append("设计矩阵奇异，无法估计")
        return res

    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    res.n_obs = n
    res.df_resid = max(int(n - k - df_fe), 1)

    tss = float(((y - y.mean()) ** 2).sum())
    rss = float((resid ** 2).sum())
    res.r_squared = 1.0 - rss / tss if tss > 0 else float("nan")

    # 聚类稳健方差
    if cluster_col and cluster_col in use.columns:
        cl_codes, _ = pd.factorize(use[cluster_col], sort=False)
        G = int(len(np.unique(cl_codes)))
    else:
        cl_codes = np.arange(n)
        G = n
    res.n_clusters = G

    meat = np.zeros((k, k))
    for g in range(G):
        m = cl_codes == g
        Xg = X[m]
        ug = resid[m]
        score = Xg.T @ ug
        meat += np.outer(score, score)

    corr = 1.0
    if G > 1:
        corr *= G / (G - 1.0)
    if res.df_resid > 0:
        corr *= (n - 1.0) / res.df_resid
    V = XtX_inv @ (corr * meat) @ XtX_inv

    if G < 40:
        res.warnings.append(
            f"聚类数仅 {G} 个，聚类稳健标准误可能严重低估，建议改用 Wild Bootstrap"
        )

    se = np.sqrt(np.clip(np.diag(V), 0.0, None))
    dof = max(G - 1, 1)
    res.vcov = V
    res.vcov_names = list(keep_names)
    for j, nm in enumerate(keep_names):
        t = beta[j] / se[j] if se[j] > 0 else float("nan")
        p = _t_pvalue(t, dof)
        res.params[nm] = float(beta[j])
        res.se[nm] = float(se[j])
        res.tstats[nm] = float(t)
        res.pvalues[nm] = float(p)
        res.ci_low[nm] = float(beta[j] - 1.96 * se[j])
        res.ci_high[nm] = float(beta[j] + 1.96 * se[j])
    return res


# ----------------------------------------------------------------------------
# Callaway & Sant'Anna (2021)
# ----------------------------------------------------------------------------

def _att_gt_single(
    df: pd.DataFrame,
    g: float,
    t: float,
    y_col: str,
    id_col: str,
    time_col: str,
    g_col: str,
    controls: Sequence[str],
    cluster_col: Optional[str],
    use_never: bool,
) -> Optional[Tuple[float, float, int]]:
    """
    单个 ATT(g,t) 的 2×2 回归估计。

    基期固定为 g-1；对照组为「截至 max(base,t) 仍未处理」的单位（含从未处理）。
    回归 y ~ G + P + G:P + X，G:P 的系数即 ATT(g,t)。
    """
    base = g - 1.0
    periods = {base, t}
    gvals = df[g_col].to_numpy(dtype=float)

    cut = max(base, t)
    if use_never:
        ctrl_mask = gvals == 0
    else:
        ctrl_mask = (gvals == 0) | (gvals > cut)
    treat_mask = gvals == g

    sub = df[(treat_mask | ctrl_mask) & (df[time_col].isin(periods))]
    if sub.empty:
        return None
    if sub[id_col].nunique() < 2 or sub[time_col].nunique() < 2:
        return None
    # 处理组与对照组都必须同时覆盖两个时期
    gnum = pd.to_numeric(sub[g_col], errors="coerce")
    for is_treat in (True, False):
        part = sub[(gnum == g) == is_treat]
        if part[time_col].nunique() < 2 or part[id_col].nunique() < 1:
            return None

    work = sub.copy()
    work["_G"] = (work[g_col] == g).astype(float)
    work["_P"] = (work[time_col] == t).astype(float)
    work["_GP"] = work["_G"] * work["_P"]

    xcols = ["_G", "_P", "_GP", *controls]
    fit = fit_ols(work, y_col, xcols, fe_cols=(), cluster_col=cluster_col or id_col)
    coef = fit.params.get("_GP")
    sev = fit.se.get("_GP")
    if coef is None or not np.isfinite(coef):
        return None
    return float(coef), (float(sev) if sev is not None else float("nan")), len(work)


def cs_att_gt(
    df: pd.DataFrame,
    y_col: str,
    id_col: str,
    time_col: str,
    g_col: str,
    controls: Sequence[str] = (),
    cluster_col: Optional[str] = None,
) -> Dict[Tuple[float, float], Tuple[float, float, int]]:
    """计算全部 ATT(g,t)。返回 {(g,t): (coef, se, n_obs)}"""
    use = df.dropna(subset=[y_col, id_col, time_col, g_col, *controls]).copy()
    gvals = use[g_col].astype(float)
    cohorts = sorted(v for v in gvals.unique() if v > 0)
    periods = sorted(use[time_col].unique())
    use_never = bool((gvals == 0).any())

    out: Dict[Tuple[float, float], Tuple[float, float, int]] = {}
    for g in cohorts:
        base = g - 1.0
        if base not in periods:
            continue
        for t in periods:
            if abs(t - base) < 1e-9:
                out[(g, t)] = (0.0, 0.0, 0)
                continue
            r = _att_gt_single(use, g, t, y_col, id_col, time_col, g_col, controls, cluster_col, use_never)
            if r is not None:
                out[(g, t)] = r
    return out


def _cohort_sizes(df: pd.DataFrame, id_col: str, g_col: str) -> Dict[float, int]:
    tmp = df[[id_col, g_col]].drop_duplicates()
    return {float(g): int(c) for g, c in tmp[g_col].value_counts().items()}


def aggregate_simple(
    att_gt: Dict[Tuple[float, float], Tuple[float, float, int]],
    sizes: Dict[float, int],
) -> float:
    """整体 ATT：按队列规模对处理后各期加权"""
    num = 0.0
    den = 0.0
    for (g, t), (c, _, _) in att_gt.items():
        if t < g or (c == 0.0 and abs(t - (g - 1.0)) < 1e-9):
            continue
        w = sizes.get(g, 1)
        num += w * c
        den += w
    return num / den if den else float("nan")


def aggregate_dynamic(
    att_gt: Dict[Tuple[float, float], Tuple[float, float, int]],
    sizes: Dict[float, int],
) -> Dict[int, float]:
    """事件研究：按相对期 e = t - g 聚合（基期 e = -1 归一化）"""
    buckets: Dict[int, List[Tuple[float, int]]] = {}
    for (g, t), (c, _, _) in att_gt.items():
        e = int(round(t - g))
        buckets.setdefault(e, []).append((c, sizes.get(g, 1)))
    out: Dict[int, float] = {}
    for e, items in buckets.items():
        wsum = sum(w for _, w in items)
        out[e] = sum(c * w for c, w in items) / wsum if wsum else float("nan")
    out.setdefault(-1, 0.0)
    out[-1] = 0.0
    return dict(sorted(out.items()))


def aggregate_group(
    att_gt: Dict[Tuple[float, float], Tuple[float, float, int]],
) -> Dict[float, float]:
    """分队列 ATT(g)"""
    buckets: Dict[float, List[float]] = {}
    for (g, t), (c, _, _) in att_gt.items():
        if t >= g:
            buckets.setdefault(g, []).append(c)
    return {g: float(np.mean(v)) for g, v in sorted(buckets.items())}


# ----------------------------------------------------------------------------
# Bootstrap：为事件研究向量提供联合协方差
# ----------------------------------------------------------------------------

def bootstrap_event_study(
    df: pd.DataFrame,
    y_col: str,
    id_col: str,
    time_col: str,
    g_col: str,
    controls: Sequence[str] = (),
    cluster_col: Optional[str] = None,
    n_boot: int = 100,
    seed: int = 20240,
) -> Dict[str, Any]:
    """
    单位级非参数 Bootstrap。返回：
    - event_study: 点估计 {e: coef}
    - se: 每个相对期的标准误
    - draws: (E × B) 的抽样矩阵，用于联合检验
    - overall: 点估计与标准误
    """
    rng = np.random.default_rng(seed)
    base = cs_att_gt(df, y_col, id_col, time_col, g_col, controls, cluster_col)
    if not base:
        return {"event_study": {}, "se": {}, "draws": None, "event_times": [], "overall": float("nan"), "overall_se": float("nan")}

    sizes = _cohort_sizes(df, id_col, g_col)
    es_point = aggregate_dynamic(base, sizes)
    overall_point = aggregate_simple(base, sizes)
    event_times = sorted(es_point.keys())

    units = df[id_col].unique()
    draws = np.full((len(event_times), n_boot), np.nan)
    overall_draws = np.full(n_boot, np.nan)

    for b in range(n_boot):
        pick = rng.choice(units, size=len(units), replace=True)
        parts = []
        for j, u in enumerate(pick):
            block = df[df[id_col] == u].copy()
            block[id_col] = f"{u}__b{j}"
            parts.append(block)
        sample = pd.concat(parts, ignore_index=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                att_b = cs_att_gt(sample, y_col, id_col, time_col, g_col, controls, cluster_col)
            sizes_b = _cohort_sizes(sample, id_col, g_col)
            es_b = aggregate_dynamic(att_b, sizes_b)
            for i, e in enumerate(event_times):
                draws[i, b] = es_b.get(e, np.nan)
            overall_draws[b] = aggregate_simple(att_b, sizes_b)
        except Exception as exc:  # 单个重抽样失败不应中断整体
            logger.debug("bootstrap 第 %d 次抽样失败: %s", b, exc)
            continue

    se_map: Dict[int, float] = {}
    for i, e in enumerate(event_times):
        row = draws[i, :]
        row = row[np.isfinite(row)]
        se_map[e] = float(np.nanstd(row, ddof=1)) if len(row) > 1 else float("nan")

    ov = overall_draws[np.isfinite(overall_draws)]
    overall_se = float(np.nanstd(ov, ddof=1)) if len(ov) > 1 else float("nan")

    return {
        "event_study": es_point,
        "se": se_map,
        "draws": draws,
        "event_times": event_times,
        "overall": overall_point,
        "overall_se": overall_se,
        "n_boot": n_boot,
    }


def pre_trend_joint_test(boot: Dict[str, Any]) -> Dict[str, Any]:
    """
    平行趋势联合检验：对处理前各期（e <= -2）系数做 Wald 联合检验。
    协方差由 Bootstrap 抽样矩阵估计。
    """
    draws = boot.get("draws")
    times: List[int] = boot.get("event_times", [])
    if draws is None or not times:
        return {"statistic": float("nan"), "p_value": float("nan"), "df": 0, "tested_periods": [], "detail": "抽样矩阵不可用"}

    pre_idx = [i for i, e in enumerate(times) if e <= -2]
    if not pre_idx:
        return {"statistic": float("nan"), "p_value": float("nan"), "df": 0, "tested_periods": [], "detail": "无处理前相对期可用于检验"}

    theta = np.array([boot["event_study"][times[i]] for i in pre_idx], dtype=float)
    sub = draws[pre_idx, :]
    sub = sub[:, np.all(np.isfinite(sub), axis=0)]
    if sub.shape[1] < 2:
        return {"statistic": float("nan"), "p_value": float("nan"), "df": len(pre_idx), "tested_periods": [times[i] for i in pre_idx], "detail": "有效抽样次数不足"}

    cov = np.cov(sub)
    cov = np.atleast_2d(cov)
    try:
        cov_inv = np.linalg.pinv(cov, rcond=1e-10)
    except np.linalg.LinAlgError:
        return {"statistic": float("nan"), "p_value": float("nan"), "df": len(pre_idx), "tested_periods": [times[i] for i in pre_idx], "detail": "协方差矩阵不可逆"}
    stat = float(theta @ cov_inv @ theta)
    dfree = len(pre_idx)
    return {
        "statistic": stat,
        "p_value": _chi2_pvalue(stat, dfree),
        "df": dfree,
        "tested_periods": [times[i] for i in pre_idx],
        "detail": f"对 {dfree} 个处理前相对期（e<=-2）的联合 Wald 检验",
    }


# ----------------------------------------------------------------------------
# 敏感性分析：Rambachan & Roth 相对幅度（水平型变体）
# ----------------------------------------------------------------------------

def sensitivity_relative_magnitudes(
    att: float,
    att_se: float,
    pre_coefs: Dict[int, float],
    m_grid: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0),
    level: float = 1.96,
) -> Dict[str, Any]:
    """
    水平型相对幅度（RM）敏感性分析。

    约束含义：处理后任一期的平行趋势违背不超过处理前最大违背的 M 倍，
    即 |Δ_post| <= M * max_{e<=-2} |Δ_pre,e|。由此 ATT 的识别区间为
        [att - M*v_max - z*se,  att + M*v_max + z*se]
    击穿值 M_bar 为区间首次覆盖 0 的 M。
    """
    vmax = max((abs(v) for e, v in pre_coefs.items() if e <= -2 and np.isfinite(v)), default=0.0)
    if not np.isfinite(att) or not np.isfinite(att_se) or att_se <= 0:
        return {"method": "rm_relative_magnitudes", "m_bar": None, "max_pre_violation": vmax, "grid": [], "conclusion": "估计量或标准误不可用，无法进行敏感性分析"}

    grid = []
    breakdown = None
    for m in m_grid:
        lo = att - m * vmax - level * att_se
        hi = att + m * vmax + level * att_se
        excludes = not (lo <= 0.0 <= hi)
        grid.append({"m": float(m), "ci_low": float(lo), "ci_high": float(hi), "excludes_zero": bool(excludes)})
        if excludes:
            breakdown = float(m)

    if vmax > 0:
        m_bar = max(0.0, (abs(att) - level * att_se) / vmax)
    else:
        m_bar = float("inf") if abs(att) > level * att_se else 0.0

    if np.isinf(m_bar):
        conclusion = "处理前无趋势违背，结论不受相对幅度约束影响"
    elif m_bar <= 0:
        conclusion = "在 M=0（严格平行趋势）下结论即不显著，敏感性分析无补救空间"
    else:
        conclusion = f"可容忍的处理后趋势违背最高为处理前最大违背的 {m_bar:.2f} 倍，超过该值结论不再显著"

    return {
        "method": "rm_relative_magnitudes",
        "m_bar": (float(m_bar) if np.isfinite(m_bar) else None),
        "breakdown_m_bar": breakdown,
        "max_pre_violation": float(vmax),
        "grid": grid,
        "conclusion": conclusion,
        "note": "采用水平型 RM 变体；正式发表建议使用 HonestDiD 官方实现复核",
    }


# ----------------------------------------------------------------------------
# 异质性与机制
# ----------------------------------------------------------------------------

def heterogeneity_by_group(
    df: pd.DataFrame,
    y_col: str,
    treat_col: str,
    group_col: str,
    controls: Sequence[str],
    fe_cols: Sequence[str],
    cluster_col: Optional[str],
) -> List[Dict[str, Any]]:
    """按分组变量分别估计处理效应，并基于交互项检验组间差异"""
    out: List[Dict[str, Any]] = []
    if group_col not in df.columns:
        return out
    groups = [v for v in df[group_col].dropna().unique()]
    for v in groups:
        sub = df[df[group_col] == v]
        if sub.empty or sub[treat_col].nunique() < 2:
            continue
        fit = fit_ols(sub, y_col, [treat_col, *controls], fe_cols=fe_cols, cluster_col=cluster_col)
        out.append({
            "group_value": (str(v) if not isinstance(v, (int, float)) else v),
            "coef": fit.params.get(treat_col),
            "se": fit.se.get(treat_col),
            "p_value": fit.pvalues.get(treat_col),
            "n_obs": fit.n_obs,
        })
    return out


def mechanism_interaction(
    df: pd.DataFrame,
    y_col: str,
    treat_col: str,
    mediator_col: str,
    controls: Sequence[str],
    fe_cols: Sequence[str],
    cluster_col: Optional[str],
) -> Dict[str, Any]:
    """处理 × 机制变量的交互项检验"""
    work = df.copy()
    inter = f"_inter_{treat_col}_x_{mediator_col}"
    work[inter] = work[treat_col].astype(float) * work[mediator_col].astype(float)
    fit = fit_ols(work, y_col, [treat_col, mediator_col, inter, *controls], fe_cols=fe_cols, cluster_col=cluster_col)
    return {
        "mediator": mediator_col,
        "interaction_coef": fit.params.get(inter),
        "interaction_se": fit.se.get(inter),
        "interaction_p": fit.pvalues.get(inter),
        "treatment_coef": fit.params.get(treat_col),
        "n_obs": fit.n_obs,
        "warnings": fit.warnings,
    }


# ----------------------------------------------------------------------------
# 联合 Wald 检验 / 事件研究 / 工具变量（本模块补建的内核）
# ----------------------------------------------------------------------------

def joint_wald_test(
    res: FitResult,
    names: Sequence[str],
    values: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """
    对一组系数做联合 Wald 检验（H0: 全部等于给定值，默认 0）。

    需要先拿到系数向量的联合协方差，因此 fit_ols 会保留 vcov。
    同时给出卡方 p 值与小样本 F 近似（F = chi2 / q，自由度 q 与 G-q）。
    """
    out: Dict[str, Any] = {
        "names": list(names),
        "statistic": None,
        "df": 0,
        "p_value": None,
        "f_stat": None,
        "p_value_f": None,
        "detail": "",
    }
    if res.vcov is None or not res.vcov_names:
        out["detail"] = "回归未提供联合协方差矩阵，无法做联合检验"
        return out
    idx = [res.vcov_names.index(n) for n in names if n in res.vcov_names]
    if len(idx) != len(names):
        out["detail"] = "部分系数因共线性被剔除，联合检验不可用：" + ", ".join(
            n for n in names if n not in res.vcov_names
        )
        return out
    q = len(idx)
    b = np.array([res.params[n] for n in names], dtype=float)
    v0 = np.zeros(q) if values is None else np.asarray(values, dtype=float)
    d = b - v0
    V = res.vcov[np.ix_(idx, idx)]
    try:
        stat = float(d @ np.linalg.solve(V, d))
    except np.linalg.LinAlgError:
        out["detail"] = "协方差矩阵奇异，联合检验无法计算"
        return out
    out["statistic"] = stat
    out["df"] = q
    out["p_value"] = _chi2_pvalue(stat, q)
    if q > 0 and res.n_clusters > q:
        f = stat / q
        out["f_stat"] = float(f)
        if _scipy_stats is not None:
            out["p_value_f"] = float(_scipy_stats.f.sf(f, q, res.n_clusters - q))
    out["detail"] = (
        f"联合 Wald 检验：chi2({q}) = {stat:.4f}"
        + (f"，p = {out['p_value']:.4f}" if out["p_value"] is not None else "")
    )
    return out


def event_study_coefficients(
    df: pd.DataFrame,
    y_col: str,
    id_col: str,
    time_col: str,
    g_col: str,
    controls: Sequence[str] = (),
    cluster_col: Optional[str] = None,
    base_period: int = -1,
    min_k: Optional[int] = None,
    max_k: Optional[int] = None,
    bin_ends: bool = True,
) -> Dict[str, Any]:
    """
    经典事件研究（相对时期虚拟变量法）。

    - 相对期数 k = t - g；从未处理组（g<=0）全部虚拟变量取 0，仅通过固定效应
      贡献信息（Sun–Abraham 式的"以从未处理为参照"）。
    - 基期默认 k = -1，被省略；端点默认做 binning（超出窗口的事件时间并入端点），
      避免少数样本期主导估计。
    - 同时给出处理后期系数的等权平均 ATT（delta 法标准误，用联合协方差）。
    """
    out: Dict[str, Any] = {
        "method": "event_study_twfe",
        "base_period": int(base_period),
        "points": {},
        "pre_trend": {},
        "post_att": {},
        "binned": bool(bin_ends),
        "n_obs": 0,
        "n_clusters": 0,
        "warnings": [],
    }
    work = df.copy()
    g = pd.to_numeric(work[g_col], errors="coerce").fillna(0.0)
    t = pd.to_numeric(work[time_col], errors="coerce")
    rel = pd.Series(np.where(g > 0, t - g, np.nan), index=work.index)

    obs = rel.dropna()
    if obs.empty:
        out["warnings"].append("没有任何已处理单位，事件研究无法估计")
        return out
    lo, hi = int(obs.min()), int(obs.max())
    kmin = lo if min_k is None else max(int(min_k), lo)
    kmax = hi if max_k is None else min(int(max_k), hi)
    rel_bin = rel.copy()
    if bin_ends:
        rel_bin = rel_bin.clip(lower=kmin, upper=kmax)
    rel_int = rel_bin.round().astype("Int64")

    grid = [k for k in range(kmin, kmax + 1) if k != int(base_period)]
    if not grid:
        out["warnings"].append("窗口内没有可用相对期数（检查基期设置）")
        return out
    if int(base_period) < kmin or int(base_period) > kmax:
        out["warnings"].append(f"基期 k={base_period} 不在观测窗口 [{kmin}, {kmax}] 内")

    names: List[str] = []
    for k in grid:
        nm = f"k_{'m' if k < 0 else ''}{abs(k)}"
        work[nm] = ((rel_int == k) & rel_int.notna()).astype(float)
        names.append(nm)

    fit = fit_ols(
        work, y_col, [*names, *controls],
        fe_cols=[id_col, time_col],
        cluster_col=cluster_col or id_col,
    )
    out["n_obs"] = fit.n_obs
    out["n_clusters"] = fit.n_clusters
    out["warnings"].extend(fit.warnings)
    out["window"] = [kmin, kmax]

    dof = max(fit.n_clusters - 1, 1)
    for k, nm in zip(grid, names):
        c = fit.params.get(nm)
        s = fit.se.get(nm)
        if c is None:
            continue
        tv = c / s if s and s > 0 else float("nan")
        out["points"][int(k)] = {
            "coef": float(c),
            "se": float(s) if s is not None else None,
            "t_stat": float(tv),
            "p_value": float(_t_pvalue(tv, dof)),
            "ci_low": float(c - 1.96 * s) if s else None,
            "ci_high": float(c + 1.96 * s) if s else None,
        }

    # 事前趋势联合检验（k < 基期）
    pre_names = [nm for k, nm in zip(grid, names) if k < int(base_period)]
    if pre_names:
        jt = joint_wald_test(fit, pre_names)
        jt["n_pre"] = len(pre_names)
        out["pre_trend"] = jt
    else:
        out["warnings"].append("窗口内没有处理前的期数，无法做事前趋势检验")

    # 处理后等权平均 ATT（delta 法）
    post_names = [nm for k, nm in zip(grid, names) if k >= 0]
    if post_names and fit.vcov is not None:
        idx = [fit.vcov_names.index(n) for n in post_names if n in fit.vcov_names]
        if len(idx) == len(post_names):
            b = np.array([fit.params[n] for n in post_names], dtype=float)
            w = np.ones(len(idx)) / len(idx)
            V = fit.vcov[np.ix_(idx, idx)]
            coef = float(w @ b)
            var = float(w @ V @ w)
            se = math.sqrt(max(var, 0.0))
            tv = coef / se if se > 0 else float("nan")
            out["post_att"] = {
                "coef": coef,
                "se": se,
                "t_stat": float(tv),
                "p_value": float(_t_pvalue(tv, dof)),
                "ci_low": coef - 1.96 * se,
                "ci_high": coef + 1.96 * se,
                "n_periods": len(idx),
                "note": "处理后各期系数的等权平均（delta 法标准误）",
            }
    return out


def fit_iv(
    df: pd.DataFrame,
    y_col: str,
    endog_col: str,
    instrument_cols: Sequence[str],
    controls: Sequence[str] = (),
    fe_cols: Sequence[str] = (),
    cluster_col: Optional[str] = None,
    grid_points: int = 241,
    grid_span: float = 8.0,
) -> Dict[str, Any]:
    """
    2SLS 工具变量估计（含弱工具稳健推断）。

    流程：
      1. 用与 fit_ols 相同的交替投影吸收固定效应（FWL）；
      2. 一阶段：内生变量 ~ [工具变量 + 外生控制]，报告排除工具的联合 F；
      3. 二阶段：y ~ [拟合值 + 外生控制]，聚类稳健标准误（2SLS 公式）；
      4. 弱工具：Anderson–Rubin 置信集（对 β0 网格做 AR 检验）；
      5. 过度识别：Hansen J（工具数 > 内生变量数时）。

    不写死任何系数：所有数值来自输入数据。
    """
    out: Dict[str, Any] = {
        "method": "2sls",
        "endog_col": endog_col,
        "instruments": list(instrument_cols),
        "coef": None, "se": None, "t_stat": None, "p_value": None,
        "ci_low": None, "ci_high": None,
        "first_stage": {}, "ar_confidence_set": {}, "overid": {},
        "ols_reference": {},
        "n_obs": 0, "n_clusters": 0, "warnings": [],
    }
    z_cols = list(instrument_cols)
    if not z_cols:
        out["warnings"].append("未指定工具变量，IV 无法估计")
        return out

    cols = [y_col, endog_col, *z_cols, *controls, *fe_cols] + ([cluster_col] if cluster_col else [])
    seen: List[str] = []
    for c in cols:
        if c and c not in seen:
            seen.append(c)
    use = df[seen].dropna()
    n = len(use)
    if n == 0:
        out["warnings"].append("有效样本为 0，无法估计")
        return out
    out["n_obs"] = int(n)

    fe_list = []
    for c in fe_cols:
        codes, _ = pd.factorize(use[c], sort=False)
        fe_list.append(codes)

    y = absorb(use[[y_col]].to_numpy(dtype=float), fe_list)[:, 0]
    D = absorb(use[[endog_col]].to_numpy(dtype=float), fe_list)[:, 0]
    Z = absorb(use[z_cols].to_numpy(dtype=float), fe_list)
    X = absorb(use[list(controls)].to_numpy(dtype=float), fe_list) if controls else np.zeros((n, 0))

    # --- 一阶段：D ~ [Z, X]
    W = np.hstack([Z, X]) if X.shape[1] else Z
    try:
        WtW_inv = np.linalg.pinv(W.T @ W)
    except np.linalg.LinAlgError:
        out["warnings"].append("工具矩阵奇异，IV 无法估计")
        return out
    Pw = W @ WtW_inv @ W.T
    D_hat = Pw @ D
    gamma = np.linalg.lstsq(W, D, rcond=None)[0]
    u1 = D - W @ gamma

    cluster_codes = (
        pd.factorize(use[cluster_col], sort=False)[0]
        if cluster_col and cluster_col in use.columns
        else np.arange(n)
    )
    G = int(len(np.unique(cluster_codes)))
    out["n_clusters"] = G
    if G < 40:
        out["warnings"].append(f"聚类数仅 {G} 个，聚类稳健标准误可能严重低估")

    def _cluster_meat(A: np.ndarray, u: np.ndarray) -> np.ndarray:
        meat = np.zeros((A.shape[1], A.shape[1]))
        for g in np.unique(cluster_codes):
            m = cluster_codes == g
            s = A[m].T @ u[m]
            meat += np.outer(s, s)
        corr = (G / (G - 1.0)) if G > 1 else 1.0
        return corr * meat

    # 一阶段排除工具的联合显著性
    V1 = WtW_inv @ _cluster_meat(W, u1) @ WtW_inv
    L = Z.shape[1]
    gz = gamma[:L]
    Vz = V1[:L, :L]
    try:
        chi1 = float(gz @ np.linalg.solve(Vz, gz))
    except np.linalg.LinAlgError:
        chi1 = float("nan")
    f_excl = chi1 / L if L else float("nan")
    out["first_stage"] = {
        "coefficients": {z: float(gz[i]) for i, z in enumerate(z_cols)},
        "f_excluded": float(f_excl),
        "chi2_excluded": chi1,
        "df1": int(L),
        "p_value": float(_scipy_stats.f.sf(f_excl, L, max(G - L, 1))) if _scipy_stats is not None and np.isfinite(f_excl) else None,
    }
    if np.isfinite(f_excl) and f_excl < 10:
        out["warnings"].append(f"一阶段排除工具 F = {f_excl:.2f} < 10，存在弱工具问题，请以 AR 置信集为准")

    # --- 二阶段：y ~ [D_hat, X]
    A = np.hstack([D_hat.reshape(-1, 1), X]) if X.shape[1] else D_hat.reshape(-1, 1)
    try:
        AtA_inv = np.linalg.pinv(A.T @ A)
    except np.linalg.LinAlgError:
        out["warnings"].append("二阶段设计矩阵奇异，IV 无法估计")
        return out
    theta = AtA_inv @ (A.T @ y)
    beta = float(theta[0])
    resid = y - np.hstack([D.reshape(-1, 1), X]) @ theta if X.shape[1] else y - D * beta
    V2 = AtA_inv @ _cluster_meat(A, resid) @ AtA_inv
    se = float(math.sqrt(max(V2[0, 0], 0.0)))
    dof = max(G - 1, 1)
    tv = beta / se if se > 0 else float("nan")
    out.update({
        "coef": beta,
        "se": se,
        "t_stat": float(tv),
        "p_value": float(_t_pvalue(tv, dof)),
        "ci_low": beta - 1.96 * se,
        "ci_high": beta + 1.96 * se,
    })

    # --- Anderson–Rubin 置信集：对每个 β0 检验"u(β0) 与工具正交"
    def _ar_p(beta0: float) -> float:
        u0 = y - D * beta0
        if X.shape[1]:
            Wx = np.hstack([Z, X])
        else:
            Wx = Z
        g_all = np.linalg.lstsq(Wx, u0, rcond=None)[0]
        r = u0 - Wx @ g_all
        WxWx_inv = np.linalg.pinv(Wx.T @ Wx)
        Vz2 = (WxWx_inv @ _cluster_meat(Wx, r) @ WxWx_inv)[:L, :L]
        try:
            chi = float(g_all[:L] @ np.linalg.solve(Vz2, g_all[:L]))
        except np.linalg.LinAlgError:
            return float("nan")
        return float(_chi2_pvalue(chi, L))

    span = max(abs(beta), se, 1e-8) * grid_span
    grid = np.linspace(beta - span, beta + span, int(grid_points))
    acc = [float(b0) for b0 in grid if (lambda p: np.isfinite(p) and p > 0.05)(_ar_p(float(b0)))]
    if acc:
        out["ar_confidence_set"] = {
            "ci_low": min(acc),
            "ci_high": max(acc),
            "n_accepted": len(acc),
            "grid_low": float(grid[0]),
            "grid_high": float(grid[-1]),
            "unbounded": bool(min(acc) <= grid[0] + 1e-12 or max(acc) >= grid[-1] - 1e-12),
            "note": "Anderson–Rubin 95% 置信集（对弱工具稳健）",
        }
    else:
        out["ar_confidence_set"] = {
            "ci_low": None, "ci_high": None, "n_accepted": 0,
            "grid_low": float(grid[0]), "grid_high": float(grid[-1]),
            "unbounded": False,
            "note": "AR 置信集为空：在整个搜索区间内模型被拒绝，检查工具有效性或设定",
        }

    # --- 过度识别（工具数 > 内生变量数）
    if L > 1:
        # Hansen J：用 2SLS 残差对 [Z, X] 回归，检验 Z 的系数联合为 0
        Wx = np.hstack([Z, X]) if X.shape[1] else Z
        gj = np.linalg.lstsq(Wx, resid, rcond=None)[0]
        rj = resid - Wx @ gj
        Wx_inv = np.linalg.pinv(Wx.T @ Wx)
        Vj = (Wx_inv @ _cluster_meat(Wx, rj) @ Wx_inv)[:L, :L]
        try:
            jstat = float(gj[:L] @ np.linalg.solve(Vj, gj[:L]))
        except np.linalg.LinAlgError:
            jstat = float("nan")
        out["overid"] = {
            "j_stat": jstat,
            "df": int(L - 1),
            "p_value": float(_chi2_pvalue(jstat, L - 1)),
            "note": "Hansen J（过度识别检验）；p 小意味着至少一个工具不满足排除限制",
        }

    # --- OLS 参照（同一设定的 naive 估计，便于对比偏误方向）
    try:
        ols = fit_ols(use, y_col, [endog_col, *controls], fe_cols=fe_cols, cluster_col=cluster_col)
        out["ols_reference"] = {
            "coef": ols.params.get(endog_col),
            "se": ols.se.get(endog_col),
            "p_value": ols.pvalues.get(endog_col),
            "note": "同一设定的 OLS 估计，仅供与 IV 对比，不是因果估计",
        }
    except Exception as exc:  # noqa: BLE001
        out["warnings"].append(f"OLS 参照估计失败: {exc}")

    out["first_stage"]["endog_col"] = endog_col
    return out


# ----------------------------------------------------------------------------
# 数据结构审计
# ----------------------------------------------------------------------------

def profile_panel(
    df: pd.DataFrame,
    id_col: str,
    time_col: str,
    g_col: Optional[str],
    outcome_col: str,
    controls: Sequence[str] = (),
) -> Dict[str, Any]:
    """面板结构审计：平衡性、处理时点分布、缺失率、被解释变量分布"""
    prof: Dict[str, Any] = {
        "n_obs": int(len(df)),
        "n_units": int(df[id_col].nunique()),
        "n_periods": int(df[time_col].nunique()),
        "time_min": None,
        "time_max": None,
        "balanced": False,
        "has_never_treated": False,
        "treatment_timings": [],
        "staggered": False,
        "missing_rate": {},
        "outcome_stats": {},
        "warnings": [],
    }
    if df.empty:
        prof["warnings"].append("数据集为空")
        return prof

    try:
        tvals = pd.to_numeric(df[time_col], errors="coerce")
        prof["time_min"] = float(tvals.min())
        prof["time_max"] = float(tvals.max())
    except Exception:
        pass

    counts = df.groupby(id_col)[time_col].nunique()
    prof["balanced"] = bool(counts.nunique() == 1)
    if not prof["balanced"]:
        prof["warnings"].append(f"非平衡面板：个体期数从 {int(counts.min())} 到 {int(counts.max())} 不等")

    if g_col and g_col in df.columns:
        gvals = pd.to_numeric(df[g_col], errors="coerce")
        timings = sorted(v for v in gvals.dropna().unique() if v > 0)
        prof["treatment_timings"] = [float(v) for v in timings]
        prof["staggered"] = len(timings) > 1
        prof["has_never_treated"] = bool((gvals.fillna(0) == 0).any())
        if not prof["has_never_treated"] and prof["staggered"]:
            prof["warnings"].append("缺少从未处理组，将使用「尚未处理」作为对照")

    cols = [outcome_col, *controls]
    for c in cols:
        if c in df.columns:
            prof["missing_rate"][c] = float(df[c].isna().mean())
    if outcome_col in df.columns:
        y = pd.to_numeric(df[outcome_col], errors="coerce").dropna()
        if len(y):
            prof["outcome_stats"] = {
                "mean": float(y.mean()),
                "std": float(y.std(ddof=1)) if len(y) > 1 else 0.0,
                "min": float(y.min()),
                "max": float(y.max()),
            }
    return prof
