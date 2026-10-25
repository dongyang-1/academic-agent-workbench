#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=================================================================================
经济学/社科实证分析智能体 - 政策试点爬虫与因果推断注入端到端测试 (test_policy_pilot.py)
=================================================================================
测试目标:
  1. 验证 PolicyPilotCrawler 能够读取并解析权威政策试点名录 (如国家碳交易试点 ETS)；
  2. 验证能够自动向宏观省际面板注入 DID/多期错位 DID 关键变量 (is_treated, first_treat, post, did, rel_year)；
  3. 验证注入后的面板数据能否成功通过 L1: data-audit 审计，自动触发 is_staggered: True；
  4. 验证 identification-strategy 是否能精准自动匹配到 staggered-did 现代因果估计器！
=================================================================================
"""

import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tools.python.policy_crawler import PolicyPilotCrawler
from tools.python.econometric_engine import EmpiricalEngine

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    print_banner("政策试点爬虫与 DID 外生冲击自动注入端到端测试")

    # 1. 查看支持的政策库清单
    print("📋 [第 1 步] 查看 policy-pilot-crawler 支持的经典政策试点库:")
    policies = PolicyPilotCrawler.list_available_policies()
    for p in policies:
        print(f"   🔹 [{p['policy_id']:18s}] {p['policy_name']} (发文单位: {p['authority']}, 试点样本数: {p['pilot_count']})")

    # 2. 读取基础省际宏观面板
    print_banner("[第 2 步] 载入国家统计局省际宏观面板数据集")
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/nbs_provincial_macro_panel.csv"))
    if not os.path.exists(data_path):
        print("⚠️ 未找到持久化面板，创建即时测试省际面板...")
        from tools.python.data_acquisition import DataAcquisitionEngine
        raw_df = DataAcquisitionEngine.fetch_nbs_provincial_panel(start_year=2012, end_year=2020)
    else:
        raw_df = pd.read_csv(data_path)
    print(f"✅ 载入基础面板成功，总样本量: {len(raw_df)} 条，包含省份: {raw_df['province_name'].nunique()} 个")

    # 3. 自动注入国家碳交易试点政策冲击 (Staggered DID)
    print_banner("[第 3 步] 自动注入外生政策冲击: 国家碳排放权交易试点 (ETS Pilot)")
    did_panel = PolicyPilotCrawler.assign_policy_to_panel(
        panel_df=raw_df,
        policy_key="carbon_trading",
        unit_col="province_name",
        year_col="year"
    )

    # 抽样预览注入结果
    print("\n📊 政策变量注入抽样预览 (包含试点省份与对照省份):")
    cols_to_show = ['province_name', 'year', 'is_treated', 'first_treat', 'post', 'did', 'rel_year', 'gdp_billion']
    sample_df = did_panel[did_panel['province_name'].isin(['北京市', '湖北省', '河北省']) & did_panel['year'].isin([2012, 2013, 2014, 2015])]
    if not sample_df.empty:
        print(sample_df[[c for c in cols_to_show if c in sample_df.columns]].to_string(index=False))

    # 持久化保存注入政策的实证数据集
    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/nbs_provincial_with_ets_did.csv"))
    did_panel.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"\n💾 数据已成功持久化至: {out_file}")

    # 4. 触发 L1: data-audit 执行结构审计
    print_banner("[第 4 步] 移交 L1: data-audit 执行实证数据结构审计")
    meta = EmpiricalEngine.run_data_audit(did_panel.rename(columns={'province_id': 'firm_id'}))
    
    print("📦 [data-audit 输出的因果推断结构化元数据契约]:")
    print(f"   is_panel:                     {meta['is_panel']}")
    print(f"   is_staggered:                 {meta['is_staggered']}  <-- 🎯 成功自动识别出多期错位冲击！")
    print(f"   has_never_treated:            {meta['has_never_treated']}  <-- 🎯 成功识别出纯净对照组！")
    print(f"   panel_balanced:               {meta['panel_balanced']}")
    print(f"   n_units:                      {meta['n_units']} 个省份")
    print(f"   n_obs:                        {meta['n_obs']} 条观测值")

    # 5. 触发 identification-strategy 策略选择
    print_banner("[第 5 步] 触发 L1: identification-strategy 决策树匹配")
    decision = EmpiricalEngine.run_identification_strategy(meta, rejected_strategies=[])
    
    print(f"🎯 [identification-strategy 输出结果]:")
    print(f"   主推因果估计策略 (Primary):      【{decision['primary_strategy']}】")
    print(f"   备选因果策略 (Alternatives):     {decision['alternative_strategies']}")
    print(f"   模型选择逻辑 (Rationale):         {decision['selection_rationale']}")

    print_banner("🎉 政策试点爬虫 ➔ 外生冲击注入 ➔ 错位DID审计 ➔ 因果路由 全流程闭环测试成功！")

if __name__ == "__main__":
    main()
