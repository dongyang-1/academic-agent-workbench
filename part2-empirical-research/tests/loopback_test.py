# -*- coding: utf-8 -*-
"""
回环验证：构造处理前存在趋势差异的数据，使审稿人判定为致命缺陷，
检验编排中枢是否自动切换到备用识别策略并留下尝试痕迹。
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools" / "python"))
sys.path.insert(0, str(HERE.parents[1]))

from agent_api import run_empirical_task  # noqa: E402
from core.contracts import TaskSpec  # noqa: E402
from orchestrator.workflow import AcademicWorkflowCoordinator  # noqa: E402


def make_pretrend_violating_panel(path: Path, n_units=200, seed=5):
    """处理组在处理前即有显著上升的趋势差异，平行趋势不成立"""
    rng = np.random.default_rng(seed)
    ids = np.arange(n_units)
    g = np.where(rng.random(n_units) < 0.5, 2019.0, 0.0)
    unit_fe = rng.normal(0, 1.0, n_units)
    rows = []
    for i in ids:
        for t in range(2015, 2023):
            d = 1.0 if (g[i] > 0 and t >= g[i]) else 0.0
            # 处理组特有的事前趋势项：越接近处理期偏差越大
            trend_gap = 0.25 * (t - 2015) if g[i] > 0 else 0.0
            y = unit_fe[i] + 0.05 * (t - 2015) + 0.6 * d + trend_gap + rng.normal(0, 0.2)
            rows.append({"id": f"U{i:04d}", "year": t, "y": y, "g": g[i]})
    pd.DataFrame(rows).to_csv(path, index=False)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="loopback_"))
    csv = tmp / "panel.csv"
    make_pretrend_violating_panel(csv)

    base = TaskSpec(
        research_question="回环验证：处理前存在趋势差异",
        data={"file_path": str(csv), "id_col": "id", "time_col": "year",
              "outcome_col": "y", "g_col": "g"},
        strategy="auto",
        output_directory=str(tmp / "out"),
    )

    print("— 单次执行（cs_did）—")
    one = run_empirical_task(base.model_copy(update={"strategy": "cs_did"}), output_dir=str(tmp / "out"))
    pre = ((one.get("pre_trend_test") or {}).get("evidence") or {})
    print(f"策略={one.get('strategy_used')}  ATT={one['att']['coef']:.4f}")
    print(f"平行趋势联合检验 p={pre.get('p_value'):.6f}")
    print(f"审稿判定={one.get('review', {}).get('verdict')}  原因={one.get('review', {}).get('reasons')}")

    print("\n— 带回环执行 —")
    coord = AcademicWorkflowCoordinator(output_dir=str(tmp / "out"))
    events = []
    res = coord.run_empirical_with_loopback(
        base, max_attempts=2, on_event=lambda t, m, p: events.append((t, m)),
    )
    print(f"尝试过的策略: {res.get('attempted_strategies')}")
    print(f"最终策略: {res.get('strategy_used')}  最终判定: {(res.get('review') or {}).get('verdict')}")
    print("事件流:")
    for t, m in events:
        print(f"  [{t}] {m}")

    ok = len(res.get("attempted_strategies", [])) >= 2
    print("\n" + "=" * 60)
    print(f"回环触发: {'通过（已切换策略）' if ok else '未通过（未切换）'}")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
