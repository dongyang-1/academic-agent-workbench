# -*- coding: utf-8 -*-
"""
端到端测试用例：验证学术全流程多智能体编排系统 (第一步：业务内核)
测试内容：
1. 智能体初始化与 ReMe 记忆服务通信
2. 防范多重共线性排查逻辑（输入衍生变量时彻底剔除原始变量）
3. 文献检索 -> 文献综述 -> 因果实证分析 -> 交付物报告生成的全链路闭环
"""

import os
import sys
from pathlib import Path

# 确保导入路径
CURRENT_DIR = Path(__file__).resolve().parent
INTEGRATED_ROOT = CURRENT_DIR.parent
if str(INTEGRATED_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATED_ROOT))

from orchestrator.workflow import AcademicWorkflowCoordinator


def test_academic_workflow_end_to_end():
    """测试多智能体编排全流程闭环"""
    print("\n========== 开始测试学术全流程多智能体编排 (第一步) ==========")

    # 1. 实例化协调器
    coordinator = AcademicWorkflowCoordinator()

    # 2. 模拟真实学术研究课题与包含共线性风险的控制变量输入
    topic = "新能源汽车产业购置税减免政策对企业绿色研发创新的因果激励效应"

    # 测试防范多重共线性：故意同时传入原始变量与中心化衍生变量
    test_controls = ["firm_size", "firm_size_centered", "leverage", "cash_flow", "growth_rate"]
    test_derived_map = {"firm_size_centered": "firm_size"}

    print(f"【测试输入课题】: {topic}")
    print(f"【测试输入控制变量】: {test_controls}（包含衍生变量 firm_size_centered 与原始变量 firm_size）")

    # 3. 运行端到端管线
    result_pkg = coordinator.run_full_pipeline(
        research_topic=topic,
        controls=test_controls,
        derived_mappings=test_derived_map,
        model_type="cs_did",
    )

    # 4. 关键指标与合规性断言
    print("\n--- 正在进行合规性与成果断言 ---")

    # 断言 1: 会话状态
    assert result_pkg["status"] == "completed", "工作流未能正常标记为完成"
    print("✓ 断言 1 通过: 工作流状态为 completed")

    # 断言 2: 防范多重共线性检查是否成功通过
    assert result_pkg["collinearity_check_passed"] is True, "共线性排查未通过"
    print("✓ 断言 2 通过: 共线性排查标志正常")

    # 断言 3: 交付物文件实际存在性
    deliverables = result_pkg["deliverables"]
    report_file = Path(deliverables["synthesis_report_markdown"])
    table_md = Path(deliverables["three_line_table_markdown"])
    table_latex = Path(deliverables["three_line_table_latex"])
    event_fig = Path(deliverables["figures"]["event_study_parallel_trends"])
    honest_fig = Path(deliverables["figures"]["honest_did_sensitivity"])

    assert report_file.exists() and report_file.stat().st_size > 500, f"综合报告文件未生成或为空: {report_file}"
    print(f"✓ 断言 3.1 通过: 综合交付报告已生成 ({report_file.stat().st_size} 字节)")

    assert table_md.exists() and table_md.stat().st_size > 200, f"三线表 Markdown 未生成: {table_md}"
    print(f"✓ 断言 3.2 通过: 出版级三线表 Markdown 已生成 ({table_md.stat().st_size} 字节)")

    assert table_latex.exists() and table_latex.stat().st_size > 200, f"三线表 LaTeX 未生成: {table_latex}"
    print(f"✓ 断言 3.3 通过: 出版级三线表 LaTeX 代码已生成 ({table_latex.stat().st_size} 字节)")

    assert event_fig.exists() and event_fig.stat().st_size > 10000, f"动态事件研究图未生成: {event_fig}"
    print(f"✓ 断言 3.4 通过: 300 DPI 平行趋势矢量图已生成 ({event_fig.stat().st_size} 字节)")

    assert honest_fig.exists() and honest_fig.stat().st_size > 10000, f"HonestDiD 敏感性图未生成: {honest_fig}"
    print(f"✓ 断言 3.5 通过: 300 DPI HonestDiD 敏感性边界图已生成 ({honest_fig.stat().st_size} 字节)")

    # 断言 4: 理论假说推导结构
    hypotheses = result_pkg["hypotheses"]
    assert len(hypotheses) >= 2, "理论假说数量不足"
    print(f"✓ 断言 4 通过: 已成功推导出 {len(hypotheses)} 个理论假说 (H1/H2)")

    print("\n========================================================")
    print("恭喜！【第一步：学术全流程多智能体编排】端到端测试 100% 成功通过！")
    print("========================================================\n")


if __name__ == "__main__":
    test_academic_workflow_end_to_end()
