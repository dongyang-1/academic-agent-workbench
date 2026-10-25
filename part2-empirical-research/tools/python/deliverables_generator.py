"""
经济学/社科实证分析智能体 - 出版级学术交付物生成器 (deliverables_generator.py)

功能:
  1. 生成符合经管顶刊标准的 LaTeX 与 Markdown 出版级规范三线表（描述性统计、基准回归）；
  2. 绘制 300 DPI 高分辨率学术矢量图与位图（平行趋势置信区间图、敏感性边界图）；
  3. 为下游论文写作智能体撰写可嵌入正文的实证结论段落。

约束：本模块不写死任何系数、标准误、p 值或样本量，全部数值由调用方传入。
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# 学术绘图风格与中文支持
# 字体按"macOS → Windows → Linux/容器"顺序兜底，保证跨平台都不出方块字
# （Dockerfile 里装了 fonts-noto-cjk，容器内会命中 Noto Sans CJK SC）
plt.rcParams["font.sans-serif"] = [
    "PingFang SC", "Heiti SC", "Songti SC", "SimHei", "Arial Unicode MS",
    "Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans CJK JP",
    "WenQuanYi Zen Hei", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 300


def _stars(p: Optional[float]) -> str:
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.1 else ""))


def _fmt(coef: Optional[float], se: Optional[float], p: Optional[float]) -> Tuple[str, str]:
    """格式化系数与标准误；不可用时给出占位符而非伪造数值"""
    if coef is None or not np.isfinite(coef):
        return "—", "—"
    se_txt = f"{se:.4f}" if se is not None and np.isfinite(se) else "—"
    return f"{coef:.4f}{_stars(p)}", se_txt


class AcademicDeliverablesGenerator:
    """出版级实证学术交付物生成器"""

    def __init__(self, output_dir: str = "deliverables"):
        self.output_dir = output_dir
        self.tables_dir = os.path.join(output_dir, "tables")
        self.figures_dir = os.path.join(output_dir, "figures")
        self.text_dir = os.path.join(output_dir, "narratives")

        for d in [self.output_dir, self.tables_dir, self.figures_dir, self.text_dir]:
            os.makedirs(d, exist_ok=True)

    # -- 表 1：描述性统计 ----------------------------------------------------
    def generate_descriptive_stats(self, df: pd.DataFrame, var_labels: Dict[str, str]) -> Dict[str, str]:
        records = []
        for var, label in var_labels.items():
            if var in df.columns:
                series = pd.to_numeric(df[var], errors="coerce").dropna()
                if series.empty:
                    continue
                records.append({
                    "变量代码": var,
                    "变量经济学含义": label,
                    "样本数 (N)": len(series),
                    "均值 (Mean)": f"{series.mean():.3f}",
                    "标准差 (SD)": f"{series.std():.3f}",
                    "最小值 (Min)": f"{series.min():.3f}",
                    "中位数 (p50)": f"{series.median():.3f}",
                    "最大值 (Max)": f"{series.max():.3f}",
                })
        if not records:
            return {"markdown": None, "latex": None}

        md_path = os.path.join(self.tables_dir, "table1_descriptive_stats.md")
        pd.DataFrame(records).to_markdown(md_path, index=False)

        tex_path = os.path.join(self.tables_dir, "table1_descriptive_stats.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write("% Table 1: 变量描述性统计三线表\n")
            f.write("\\begin{table}[htbp]\n\\centering\n\\small\n")
            f.write("\\caption{主要变量描述性统计}\n\\label{tab:desc_stats}\n")
            f.write("\\begin{tabular}{llcccccc}\n\\toprule\n")
            f.write("变量代码 & 经济学含义 & 样本数 & 均值 & 标准差 & 最小值 & 中位数 & 最大值 \\\\\n\\midrule\n")
            for r in records:
                f.write(
                    f"{r['变量代码'].replace('_', chr(92) + '_')} & {r['变量经济学含义']} & "
                    f"{r['样本数 (N)']} & {r['均值 (Mean)']} & {r['标准差 (SD)']} & "
                    f"{r['最小值 (Min)']} & {r['中位数 (p50)']} & {r['最大值 (Max)']} \\\\\n"
                )
            f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

        return {"markdown": md_path, "latex": tex_path}

    # -- 表 2：基准回归 ------------------------------------------------------
    def generate_baseline_table(
        self,
        dep_var_name: str,
        treat_var_name: str,
        cs_info: Dict[str, Any],
        twfe_info: Dict[str, Any],
        controls_used: List[str],
        cluster_level: str = "个体层级",
        watermark: Optional[str] = None,
    ) -> Dict[str, str]:
        """基准回归三线表。两列系数均来自真实估计。"""
        twfe_coef, twfe_se = _fmt(twfe_info.get("coef"), twfe_info.get("se"), twfe_info.get("p_value"))
        cs_coef, cs_se = _fmt(cs_info.get("att"), cs_info.get("att_se"), cs_info.get("p_value"))
        n_obs = cs_info.get("n_obs") or twfe_info.get("n_obs") or 0
        r2 = twfe_info.get("r_squared")
        r2_txt = f"{r2:.4f}" if r2 is not None and np.isfinite(r2) else "—"

        md_path = os.path.join(self.tables_dir, "table2_baseline_regression.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"| 解释变量与模型特征 | (1) 双向固定效应 TWFE | (2) 错位多期 DID (CS-DID) |\n")
            f.write("| :--- | :---: | :---: |\n")
            f.write(f"| **核心政策估计量 ({treat_var_name})** | {twfe_coef} ({twfe_se}) | {cs_coef} ({cs_se}) |\n")
            for c in controls_used:
                f.write(f"| 控制变量: `{c}` | 控制 | 控制 |\n")
            f.write("| 个体固定效应 | YES | YES |\n")
            f.write("| 时间固定效应 | YES | YES |\n")
            f.write(f"| 标准误聚类层级 | {cluster_level} | {cluster_level} |\n")
            f.write(f"| 样本量 (N) | {n_obs} | {n_obs} |\n")
            f.write(f"| 组内 R² | {r2_txt} | — |\n\n")
            f.write("*注：括号内为聚类稳健标准误，* p<0.1, ** p<0.05, *** p<0.01。*\n")
            if watermark:
                f.write(f"\n> 本报告由 **{watermark}** 生成，系数不可用于正式研究。\n")

        tex_path = os.path.join(self.tables_dir, "table2_baseline_regression.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write("% Table 2: 基准因果推断回归三线表\n")
            f.write("\\begin{table}[htbp]\n\\centering\n\\small\n")
            f.write("\\caption{基准回归估计结果}\n\\label{tab:baseline}\n")
            f.write("\\begin{tabular}{lcc}\n\\toprule\n")
            f.write(" & (1) TWFE & (2) Callaway-Sant'Anna \\\\\n\\midrule\n")
            f.write(f"政策处理效应 & {twfe_coef} & {cs_coef} \\\\\n")
            f.write(f" & ({twfe_se}) & ({cs_se}) \\\\\n")
            for c in controls_used:
                f.write(f"控制变量 {c.replace('_', chr(92) + '_')} & 控制 & 控制 \\\\\n")
            f.write("个体固定效应 & YES & YES \\\\\n")
            f.write("时间固定效应 & YES & YES \\\\\n")
            f.write(f"聚类稳健标准误 & {cluster_level} & {cluster_level} \\\\\n")
            f.write(f"观测值 & {n_obs} & {n_obs} \\\\\n")
            f.write(f"组内 $R^2$ & {r2_txt} & — \\\\\n")
            f.write("\\bottomrule\n\\end{tabular}\n")
            f.write("\\multicolumn{3}{l}{\\footnotesize 注：括号内为聚类稳健标准误；* $p<0.1$, ** $p<0.05$, *** $p<0.01$。}\\\\\n")
            if watermark:
                f.write(f"\\multicolumn{{3}}{{l}}{{\\footnotesize 警告：本表由{watermark}生成，不可用于正式研究。}}\n")
            f.write("\\end{table}\n")

        return {"markdown": md_path, "latex": tex_path}

    # -- 图 1：事件研究 ------------------------------------------------------
    def plot_event_study(self, event_study_points: List[Dict[str, Any]]) -> Dict[str, str]:
        """事件研究动态效应图。数据全部来自传入的估计点。"""
        pts = [p for p in event_study_points
               if p.get("coef") is not None and np.isfinite(p["coef"])]
        if not pts:
            raise ValueError("无可用的事件研究估计点")
        rel_years = [p["rel_year"] for p in pts]
        coefs = [p["coef"] for p in pts]
        ses = [p.get("se") or 0.0 for p in pts]

        ci_lower = [c - 1.96 * s for c, s in zip(coefs, ses)]
        ci_upper = [c + 1.96 * s for c, s in zip(coefs, ses)]

        fig, ax = plt.subplots(figsize=(8, 4.8), dpi=300)
        ax.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.axvline(-0.5, color="crimson", linestyle=":", linewidth=1.2, label="政策实施基准线")
        ax.fill_between(rel_years, ci_lower, ci_upper, color="#1f77b4", alpha=0.18, label="95% 置信区间")
        ax.errorbar(rel_years, coefs, yerr=[c - l for c, l in zip(coefs, ci_lower)],
                    fmt="o-", color="#1f77b4", ecolor="#1f77b4", elinewidth=1.5, capsize=4,
                    capthick=1.2, markersize=6, linewidth=1.8, label="动态处理效应")
        ax.set_title("事件研究动态效应与平行趋势检验", fontsize=13, pad=14)
        ax.set_xlabel("距政策实施相对期数", fontsize=11)
        ax.set_ylabel("估计系数", fontsize=11)
        ax.set_xticks(rel_years)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(frameon=True, facecolor="white", framealpha=0.9, fontsize=9.5)
        plt.tight_layout()

        pdf_path = os.path.join(self.figures_dir, "fig1_event_study_parallel_trends.pdf")
        png_path = os.path.join(self.figures_dir, "fig1_event_study_parallel_trends.png")
        fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
        fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        return {"pdf": pdf_path, "png": png_path}

    # -- 图 2：敏感性边界 ----------------------------------------------------
    def plot_honest_did_bounds(self, sensitivity_info: Dict[str, Any]) -> Dict[str, str]:
        """
        平行趋势违背敏感性边界图。
        att / att_se / v_max 全部取自传入的敏感性分析结果，不再写死。
        """
        att = sensitivity_info.get("att")
        att_se = sensitivity_info.get("att_se")
        vmax = sensitivity_info.get("max_pre_violation") or 0.0
        m_bar = sensitivity_info.get("m_bar")

        if att is None or att_se is None or not np.isfinite(att) or not np.isfinite(att_se) or att_se <= 0:
            raise ValueError("敏感性分析缺少可用的 ATT 或标准误")

        m_max = 3.0 if (m_bar in (None, float("inf")) or not np.isfinite(m_bar)) else max(3.0, float(m_bar) * 1.3)
        m_vals = np.linspace(0, m_max, 100)
        upper = att + 1.96 * att_se + m_vals * vmax
        lower = att - 1.96 * att_se - m_vals * vmax

        fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=300)
        ax.axhline(0, color="black", linestyle="--", linewidth=0.9, alpha=0.8, label="零效应基准")
        if m_bar is not None and np.isfinite(m_bar):
            ax.axvline(float(m_bar), color="darkorange", linestyle="-.", linewidth=1.5,
                       label=f"击穿值 M* = {float(m_bar):.2f}")
        ax.plot(m_vals, upper, color="#2ca02c", linewidth=2.0, label="稳健区间上限")
        ax.plot(m_vals, lower, color="#1f77b4", linewidth=2.0, label="稳健区间下限")
        ax.fill_between(m_vals, lower, upper, color="#2ca02c", alpha=0.15)
        ax.set_title("平行趋势违背敏感性边界分析", fontsize=12, pad=12)
        ax.set_xlabel("允许的处理后趋势违背倍数 M", fontsize=10.5)
        ax.set_ylabel("估计量 95% 稳健区间", fontsize=10.5)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(frameon=True, fontsize=9.5)
        plt.tight_layout()

        pdf_path = os.path.join(self.figures_dir, "fig2_honest_did_sensitivity.pdf")
        png_path = os.path.join(self.figures_dir, "fig2_honest_did_sensitivity.png")
        fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
        fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
        plt.close(fig)
        return {"pdf": pdf_path, "png": png_path}

    # -- 正文叙述 ------------------------------------------------------------
    def generate_writing_narrative(
        self,
        research_question: str,
        result: Dict[str, Any],
        twfe_info: Dict[str, Any],
        provenance: str = "real",
    ) -> str:
        """
        生成可直接引用的实证叙述。显著性与方向完全由真实估计决定，
        不显著时不使用"强有力地支持了假说"这类表述。
        """
        att = (result.get("att") or {})
        coef = att.get("coef")
        se = att.get("se")
        p = att.get("p_value")
        stars = _stars(p)
        strategy = result.get("strategy_used") or "—"
        profile = result.get("data_profile") or {}
        pre = result.get("pre_trend_test") or {}
        sens = result.get("sensitivity") or {}
        rev = result.get("review") or {}

        if coef is None or not np.isfinite(coef):
            concl = "本次估计未得到可用系数，请检查数据列角色映射与样本覆盖后再行生成正文。"
        elif p is not None and np.isfinite(p) and p < 0.1:
            direction = "正向" if coef > 0 else "负向"
            concl = (
                f"核心估计量为 {coef:.4f}{stars}（聚类稳健标准误 {se:.4f}，p = {p:.4f}），"
                f"在统计上显著，方向上表现为{direction}效应。"
            )
        else:
            pv = f"{p:.4f}" if p is not None and np.isfinite(p) else "不可用"
            concl = (
                f"核心估计量为 {coef:.4f}（聚类稳健标准误 {se if se else '—'}，p = {pv}），"
                f"未达到常规显著性水平，尚不足以支持研究假说，需要补充样本或调整识别策略。"
            )

        pt_p = (pre.get("evidence") or {}).get("p_value")
        if pt_p is not None and np.isfinite(pt_p):
            pt_txt = (
                f"处理前各期系数的联合 Wald 检验统计量为 "
                f"{(pre.get('evidence') or {}).get('statistic'):.4f}（df = "
                f"{(pre.get('evidence') or {}).get('df')}，p = {pt_p:.4f}），"
                + ("未拒绝平行趋势假设。" if pt_p > 0.05 else "平行趋势假设在统计上被拒绝，结论需谨慎。")
            )
        else:
            pt_txt = "未提供平行趋势联合检验结果。"

        m_bar = sens.get("m_bar")
        if m_bar is None:
            sens_txt = "敏感性分析不可用。"
        elif not np.isfinite(m_bar):
            sens_txt = "处理前未观察到趋势违背，结论在相对幅度约束下不受影响。"
        else:
            sens_txt = (
                f"在相对幅度（RM）约束下，可容忍的处理后趋势违背为处理前最大违背的 "
                f"{m_bar:.2f} 倍；超过该值后结论不再保持显著。"
            )

        twfe_txt = "—"
        if twfe_info.get("coef") is not None and np.isfinite(twfe_info["coef"]):
            twfe_txt = f"{twfe_info['coef']:.4f}{_stars(twfe_info.get('p_value'))}（{twfe_info.get('se'):.4f}）"

        warn = ""
        if provenance == "demo":
            warn = "\n\n> 本段由演示数据生成，仅用于验证链路，不得写入正式论文。\n"
        if rev.get("reasons"):
            warn += "\n\n审稿人提示：\n" + "\n".join(f"- {r}" for r in rev["reasons"]) + "\n"

        content = f"""# 实证分析结构化结论（供论文写作智能体引用）

**研究问题**：{research_question}
**识别策略**：{strategy}
**样本规模**：{profile.get('n_obs', '—')} 个观测，{profile.get('n_units', '—')} 个个体，{profile.get('n_periods', '—')} 个时期
**数据性质**：{"演示数据" if provenance == "demo" else "真实数据"}

---

## 一、基准回归结果

{concl}

双向固定效应（TWFE）对照估计为 {twfe_txt}。当处理时点存在错位时，TWFE 估计量可能因负权重问题产生偏误，
故正文应以异质性稳健估计量为准，TWFE 仅作为对照列示。

## 二、平行趋势与动态效应

{pt_txt}

{sens_txt}

## 三、投稿前需确认事项

1. 核对聚类层级设置与聚类数量，聚类数偏少时应改用 Wild Bootstrap 标准误；
2. 核对控制变量是否已剔除中介变量（坏控制）与完全共线变量；
3. 若平行趋势未通过，需在正文披露并补充条件平行趋势或替代识别策略。
{warn}
"""
        doc_path = os.path.join(self.text_dir, "empirical_narrative_for_writing.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        return doc_path
