"""
测试用例: 验证子智能体统一接口 (agent_api.py) 与出版级交付物自动生成 (test_agent_api_and_deliverables.py)
"""

import os
import sys
import json
import unittest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.python.agent_api import run_empirical_task

def test_subagent_api_and_deliverables():
    print("=" * 80)
    print("🧪 [测试开始] 验证实证分析子智能体统一接口与交付物生成")
    print("=" * 80)

    output_dir = os.path.join(project_root, "deliverables")
    
    # 模拟上游【文献选题 Agent】传来的标准化输入 JSON
    proposal_from_upstream = {
        "topic": "国家碳交易试点 (ETS) 对企业数字化转型的政策效应——兼论管理层短视的调节作用",
        "hypothesis": "外生环境规制政策倒逼受冲击企业数字化转型，但管理层短视具有显著抑制效应",
        "policy_shock": "carbon_trading",
        "dependent_var": "digital_transformation_ln",
        "mediators": ["managerial_myopia_ln"],
        "candidate_controls": ['leverage_pct', 'roa_pct', 'ln_assets']
    }

    # 1. 调用统一入口
    result = run_empirical_task(proposal_from_upstream, output_dir=output_dir)

    # 2. 验证执行状态与返回值契约
    assert result["status"] == "SUCCESS", "子智能体执行未成功！"
    assert "core_estimates" in result, "缺失核心估计值！"
    assert "audit_certificate" in result, "缺失审稿人合格认证！"
    assert result["audit_certificate"]["perfect_collinearity_cleared"] is True, "未排查多重共线性！"
    assert result["audit_certificate"]["dag_bad_control_passed"] is True, "未通过坏控制审查！"

    # 3. 验证交付物文件是否真实生成
    manifest = result["deliverables_manifest"]
    
    # 表格检查
    t1_md = manifest["tables"]["table1_descriptive_stats"]["markdown"]
    t1_tex = manifest["tables"]["table1_descriptive_stats"]["latex"]
    t2_md = manifest["tables"]["table2_baseline_regression"]["markdown"]
    t2_tex = manifest["tables"]["table2_baseline_regression"]["latex"]
    
    for p in [t1_md, t1_tex, t2_md, t2_tex]:
        assert os.path.exists(p), f"表格文件未生成: {p}"
        assert os.path.getsize(p) > 100, f"表格文件内容过小: {p}"
        print(f"  ✓ 表格文件验证通过: {os.path.basename(p)}")

    # 图表检查
    f1_pdf = manifest["figures"]["fig1_event_study"]["pdf"]
    f1_png = manifest["figures"]["fig1_event_study"]["png"]
    f2_pdf = manifest["figures"]["fig2_honest_did_bounds"]["pdf"]
    f2_png = manifest["figures"]["fig2_honest_did_bounds"]["png"]
    
    for p in [f1_pdf, f1_png, f2_pdf, f2_png]:
        assert os.path.exists(p), f"图表文件未生成: {p}"
        assert os.path.getsize(p) > 1000, f"图表文件内容异常: {p}"
        print(f"  ✓ 高清矢量图/位图验证通过: {os.path.basename(p)}")

    # 论文写作正文草稿检查
    narrative_md = manifest["narrative_for_writing"]
    assert os.path.exists(narrative_md), f"写作草稿未生成: {narrative_md}"
    assert os.path.getsize(narrative_md) > 500, f"写作草稿内容不完整: {narrative_md}"
    print(f"  ✓ 面向论文写作 Agent 的正文实证摘要验证通过: {os.path.basename(narrative_md)}")

    print("\n" + "=" * 80)
    print("🎉 [测试通过] 子智能体 I/O 接口与出版级交付物模块 100% 验收成功！")
    print("=" * 80)

if __name__ == "__main__":
    test_subagent_api_and_deliverables()
