# -*- coding: utf-8 -*-
"""
计量内核反演测试：用已知真实处理效应的数据检验估计器能否还原真值。
已知 DGP 中真实 ATT = TRUE_TAU，处理前各期效应应为 0。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools" / "python"))

import econ_core as ec  # noqa: E402

TRUE_TAU = 0.8
SEED = 7


def build_panel(n_units=240, years=range(2015, 2023), tau=TRUE_TAU, seed=SEED):
    rng = np.random.default_rng(seed)
    ids = np.arange(n_units)
    # 40% 从未处理，其余分三个处理时点
    cut = rng.random(n_units)
    g = np.zeros(n_units)
    g[(cut >= 0.40) & (cut < 0.60)] = 2018
    g[(cut >= 0.60) & (cut < 0.80)] = 2019
    g[cut >= 0.80] = 2020

    unit_fe = rng.normal(0, 1.0, n_units)
    x = rng.normal(0, 1.0, n_units)  # 一个时不变协变量（会被吸收，仅测试鲁棒性）

    rows = []
    for i in ids:
        for t in years:
            treated = 1.0 if (g[i] > 0 and t >= g[i]) else 0.0
            time_fe = 0.05 * (t - 2015)
            y = unit_fe[i] + time_fe + tau * treated + 0.3 * x[i] + rng.normal(0, 0.25)
            rows.append({"id": i, "year": t, "y": y, "g": g[i], "x": x[i], "did": treated})
    return pd.DataFrame(rows)


def main():
    df = build_panel()
    print(f"样本: N={df['id'].nunique()}, T={df['year'].nunique()}, 观测={len(df)}")
    print(f"处理时点: {sorted(v for v in df['g'].unique() if v>0)}  从未处理占比: {(df.groupby('id')['g'].first()==0).mean():.2%}")

    prof = ec.profile_panel(df, "id", "year", "g", "y", controls=["x"])
    print(f"\n[审计] 平衡面板={prof['balanced']}  错位={prof['staggered']}  有从未处理组={prof['has_never_treated']}")

    att_gt = ec.cs_att_gt(df, "y", "id", "year", "g", controls=["x"], cluster_col="id")
    print(f"\n[CS] 可估 ATT(g,t) 数量: {len(att_gt)}")

    sizes = ec._cohort_sizes(df, "id", "g")
    att = ec.aggregate_simple(att_gt, sizes)
    es = ec.aggregate_dynamic(att_gt, sizes)
    print(f"[CS] 整体 ATT = {att:.4f}   (真值 {TRUE_TAU})")

    boot = ec.bootstrap_event_study(df, "y", "id", "year", "g", controls=["x"], n_boot=60, seed=11)
    print(f"[Bootstrap] 整体 ATT = {boot['overall']:.4f}, SE = {boot['overall_se']:.4f}")
    z = (boot["overall"] - TRUE_TAU) / boot["overall_se"] if boot["overall_se"] else float("nan")
    print(f"[Bootstrap] 相对真值的 z = {z:.3f}  (|z|<2.5 视为还原成功)")

    print("\n[事件研究] 相对期  系数    标准误")
    for e in sorted(es.keys()):
        se = boot["se"].get(e, float("nan"))
        print(f"          e={e:>3}   {es[e]:>7.4f}  {se:>7.4f}")

    pre = ec.pre_trend_joint_test(boot)
    print(f"\n[平行趋势联合检验] 卡方={pre['statistic']:.4f}, df={pre['df']}, p={pre['p_value']:.4f}")
    print(f"                  检验期: {pre['tested_periods']}  -> {'通过' if pre['p_value'] and pre['p_value']>0.05 else '不通过'}")

    sens = ec.sensitivity_relative_magnitudes(boot["overall"], boot["overall_se"], es)
    print(f"\n[敏感性] 处理前最大违背 v_max={sens['max_pre_violation']:.4f}")
    print(f"[敏感性] 击穿值 M_bar={sens['m_bar']}   {sens['conclusion']}")

    # TWFE 对照
    fit = ec.fit_ols(df, "y", ["did", "x"], fe_cols=["id", "year"], cluster_col="id")
    print(f"\n[TWFE] did = {fit.params.get('did'):.4f} (SE {fit.se.get('did'):.4f}, p={fit.pvalues.get('did'):.4g})  R2={fit.r_squared:.4f}")

    # 共线性诊断
    df2 = df.copy()
    df2["x_dup"] = df2["x"] * 2.0
    rep = ec.collinearity_report(df2[["x", "x_dup", "did"]])
    print(f"\n[共线性] 保留={rep['kept']}  剔除={rep['dropped']}")

    ok = abs(boot["overall"] - TRUE_TAU) < 2.5 * boot["overall_se"]
    print("\n" + "=" * 60)
    print("反演测试:", "通过" if ok else "未通过")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
