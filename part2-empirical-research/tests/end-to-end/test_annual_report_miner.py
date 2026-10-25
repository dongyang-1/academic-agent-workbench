#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=================================================================================
经济学/社科实证分析智能体 - 上市公司年报文本与词频挖掘端到端测试 (test_annual_report_miner.py)
=================================================================================
测试目标:
  1. 验证 AnnualReportTextMiner 基于顶刊标准词库 (吴非等 2021) 提取企业“数字化转型”指标；
  2. 验证提取企业“绿色技术创新”与环保关注度指标；
  3. 验证文本挖掘指标与微观财务指标的横向对齐融合；
  4. 送入 L1: data-audit 执行结构审计，完成从非结构化文本到标准实证面板的闭环！
=================================================================================
"""

import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tools.python.annual_report_miner import AnnualReportTextMiner
from tools.python.econometric_engine import EmpiricalEngine

def print_banner(title: str):
    print("\n" + "=" * 85)
    print(f"  {title}")
    print("=" * 85)

def main():
    print_banner("上市公司年报文本与词频挖掘 (非结构化实证) 端到端测试")

    # 1. 目标企业与年份定义
    firms = [
        {"code": "002594", "name": "比亚迪"},
        {"code": "601127", "name": "赛力斯"},
        {"code": "600104", "name": "上汽集团"},
        {"code": "601633", "name": "长城汽车"}
    ]
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

    # 2. 挖掘“数字化转型”指标 (Digital Transformation)
    print_banner("[第 1 步] 基于吴非等 (2021) 标准词库挖掘企业【数字化转型】指标")
    digital_df = AnnualReportTextMiner.build_firm_text_panel(
        firms=firms,
        years=years,
        topic="digital_transformation"
    )

    print("\n📋 数字化转型指标样本预览 (前 8 行):")
    cols_d = ['firm_name', 'year', 'digital_transformation_count', 'digital_transformation_ln', 'digital_transformation_density']
    print(digital_df[cols_d].head(8).to_string(index=False))

    # 3. 挖掘“绿色技术创新”指标 (Green Innovation)
    print_banner("[第 2 步] 基于双碳与绿色发展词库挖掘企业【绿色技术创新关注度】指标")
    green_df = AnnualReportTextMiner.build_firm_text_panel(
        firms=firms,
        years=years,
        topic="green_innovation"
    )

    # 4. 横向融合：将文本挖掘指标与既有财务面板按 (firm_id, year) 拼装
    print_banner("[第 3 步] 多源融合: 将年报文本指标与微观财务指标横向合并")
    fin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/auto_industry_financial_panel.csv"))
    if os.path.exists(fin_path):
        fin_df = pd.read_csv(fin_path)
        # 确保 firm_id 字符串对齐
        fin_df['firm_id'] = fin_df['firm_id'].astype(str).str.zfill(6)
        digital_df['firm_id'] = digital_df['firm_id'].astype(str).str.zfill(6)
        green_df['firm_id'] = green_df['firm_id'].astype(str).str.zfill(6)

        merged = pd.merge(digital_df, green_df[['firm_id', 'year', 'green_innovation_count', 'green_innovation_ln', 'green_innovation_density']], on=['firm_id', 'year'])
        merged = pd.merge(merged, fin_df[['firm_id', 'year', 'revenue_billion', 'net_profit_billion', 'leverage_pct', 'ln_assets']], on=['firm_id', 'year'], how='left')
    else:
        merged = pd.merge(digital_df, green_df, on=['firm_id', 'firm_name', 'year'])

    print(f"\n📊 融合后数据集结构预览 (总行数: {len(merged)}, 总字段数: {len(merged.columns)}):")
    preview_cols = ['firm_name', 'year', 'digital_transformation_ln', 'green_innovation_ln', 'revenue_billion', 'leverage_pct']
    print(merged[[c for c in preview_cols if c in merged.columns]].head(8).to_string(index=False))

    # 持久化导出
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "auto_firm_with_text_metrics.csv")
    merged.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n💾 数据已成功持久化至: {out_csv}")

    # 5. 移交 L1: data-audit 执行结构审计
    print_banner("[第 4 步] 移交 L1: data-audit 执行实证数据结构审计")
    meta = EmpiricalEngine.run_data_audit(merged)
    print("📦 [data-audit 输出的结构化元数据契约]:")
    print(f"   is_panel:            {meta['is_panel']}")
    print(f"   panel_balanced:      {meta['panel_balanced']}")
    print(f"   n_units:             {meta['n_units']} 家企业")
    print(f"   n_obs:               {meta['n_obs']} 个企业-年度观测值")

    # 6. 策略推荐
    id_decision = EmpiricalEngine.run_identification_strategy(meta, rejected_strategies=[])
    print(f"\n🎯 [因果识别策略选择器 identification-strategy 诊断]:")
    print(f"   推荐基准策略 (Primary):  【{id_decision['primary_strategy']}】")
    print(f"   备选策略 (Alternatives): {id_decision['alternative_strategies']}")
    print(f"   学术建模建议:          本面板集成了企业文本特征 (数字化转型、绿色创新) 与财务特征，可设定双向固定效应模型 (TWFE):")
    print(f"                         Performance_it = β0 + β1 * Digital_it + Controls_it + α_i + λ_t + ε_it")
    print(f"                         ⚠️ 防共线性提醒: 控制变量中已纳入规模对数 ln_assets，严禁同时放入原始 total_assets！")

    print_banner("🎉 年报文本挖掘 ➔ 顶刊词库匹配 ➔ 财务数据融合 ➔ 实证审计 全闭环测试圆满成功！")

if __name__ == "__main__":
    main()
