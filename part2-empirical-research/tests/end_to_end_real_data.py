# -*- coding: utf-8 -*-
"""
端到端验证：任务契约 -> 数据载入 -> 审计 -> 估计 -> 诊断 -> 交付物

三组验证：
A. 真实数据文件（临时生成的 CSV，但走完整读文件流程）
B. 演示模式（应打上 demo 水印）
C. 缺参数时应报错而不是静默造假
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PY_DIR = HERE.parent / "tools" / "python"
sys.path.insert(0, str(PY_DIR))
sys.path.insert(0, str(HERE.parents[1]))

from agent_api import run_empirical_task  # noqa: E402
from core.contracts import TaskSpec  # noqa: E402

TRUE_TAU = 1.2


def make_csv(path: Path, n_units=300, tau=TRUE_TAU, seed=101):
    rng = np.random.default_rng(seed)
    ids = np.arange(n_units)
    cut = rng.random(n_units)
    g = np.zeros(n_units)
    g[(cut >= 0.35) & (cut < 0.55)] = 2017
    g[(cut >= 0.55) & (cut < 0.75)] = 2019
    g[cut >= 0.75] = 2021
    unit_fe = rng.normal(0, 1.0, n_units)
    size = rng.normal(5, 1.5, n_units)
    rows = []
    for i in ids:
        for t in range(2014, 2023):
            d = 1.0 if (g[i] > 0 and t >= g[i]) else 0.0
            lev = rng.normal(0, 0.3)
            y = unit_fe[i] + 0.04 * (t - 2014) + tau * d + 0.25 * size[i] + 0.1 * lev + rng.normal(0, 0.2)
            rows.append({"firm_id": f"F{i:04d}", "year": t, "rd_intensity": y,
                         "first_treat": g[i], "firm_size": size[i], "leverage": lev})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df


def show(tag, res):
    print(f"\n{'='*66}\n{tag}\n{'='*66}")
    if res.get("status") == "failed":
        print("状态: failed")
        for e in res.get("errors", []):
            print("  错误:", e)
        return res
    att = res.get("att") or {}
    prof = res.get("data_profile") or {}
    print(f"策略: {res.get('strategy_used')}   数据性质: {res.get('provenance')}")
    print(f"样本: N={prof.get('n_obs')} 个体={prof.get('n_units')} 时期={prof.get('n_periods')} 平衡={prof.get('balanced')}")
    print(f"ATT = {att.get('coef'):.4f}  SE = {att.get('se'):.4f}  p = {att.get('p_value'):.4g}"
          if att.get("coef") is not None else "ATT: 不可用")
    pre = (res.get("pre_trend_test") or {}).get("evidence") or {}
    print(f"平行趋势联合检验: 卡方={pre.get('statistic'):.4f} df={pre.get('df')} p={pre.get('p_value'):.4f}"
          if pre.get("p_value") is not None else "平行趋势检验: 不可用")
    sens = res.get("sensitivity") or {}
    mb = sens.get("m_bar")
    print(f"敏感性 M_bar = {mb if mb is None or np.isfinite(mb) else 'inf'}")
    rev = res.get("review") or {}
    print(f"审稿人判定: {rev.get('verdict')}  {rev.get('reasons')}")
    dl = res.get("deliverables") or {}
    print("交付物:")
    for k, v in (dl.get("tables") or {}).items():
        print(f"  表 {k}: md={Path(v['markdown']).name if v.get('markdown') else None}")
    for k, v in (dl.get("figures") or {}).items():
        print(f"  图 {k}: png={Path(v['png']).name if v.get('png') else None}")
    print(f"  叙述: {Path(dl['narrative_for_writing']).name if dl.get('narrative_for_writing') else None}")
    return res


def main():
    tmp = Path(tempfile.mkdtemp(prefix="academic_e2e_"))
    csv_path = tmp / "panel.csv"
    make_csv(csv_path)

    task_a = TaskSpec(
        research_question="外生政策冲击对企业研发投入强度的影响",
        data={
            "file_path": str(csv_path),
            "id_col": "firm_id",
            "time_col": "year",
            "outcome_col": "rd_intensity",
            "g_col": "first_treat",
            "controls": ["firm_size", "leverage"],
        },
        strategy="auto",
        output_directory=str(tmp / "out_a"),
    )
    res_a = show("A. 真实数据文件（走完整读文件流程）", run_empirical_task(task_a))
    ok_a = False
    if res_a.get("status") != "failed" and res_a.get("att", {}).get("coef") is not None:
        err = abs(res_a["att"]["coef"] - TRUE_TAU)
        ok_a = err < 3 * (res_a["att"]["se"] or 1)
        print(f"\n真值 {TRUE_TAU} vs 估计 {res_a['att']['coef']:.4f}，偏差 {err:.4f} -> {'还原成功' if ok_a else '还原失败'}")

    task_b = TaskSpec(
        research_question="演示模式验证",
        demo_mode=True,
        data={"id_col": "id", "time_col": "year", "outcome_col": "y", "g_col": "g", "controls": ["x"]},
        output_directory=str(tmp / "out_b"),
    )
    res_b = show("B. 演示模式（应标记 demo 并打水印）", run_empirical_task(task_b))
    ok_b = res_b.get("provenance") == "demo"
    md_path = ((res_b.get("deliverables") or {}).get("tables") or {}).get("table2_baseline_regression", {}).get("markdown")
    if md_path and Path(md_path).exists():
        ok_b = ok_b and ("演示数据" in Path(md_path).read_text(encoding="utf-8"))
    print(f"\n演示模式水印: {'已打上' if ok_b else '缺失'}")

    task_c = TaskSpec(
        research_question="缺数据文件且未开 demo",
        data={"id_col": "id", "time_col": "year", "outcome_col": "y"},
    )
    res_c = show("C. 缺少必要参数（应报错，不静默造假）", run_empirical_task(task_c))
    ok_c = res_c.get("status") == "failed" and bool(res_c.get("errors"))

    print("\n" + "=" * 66)
    print(f"A 真实数据还原真值: {'通过' if ok_a else '未通过'}")
    print(f"B 演示模式水印:     {'通过' if ok_b else '未通过'}")
    print(f"C 缺参数正确报错:   {'通过' if ok_c else '未通过'}")
    print("=" * 66)
    print(f"临时目录: {tmp}")
    return 0 if (ok_a and ok_b and ok_c) else 1


if __name__ == "__main__":
    sys.exit(main())
