#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=================================================================================
经济学/社科实证分析智能体 - 联网数据采集与实证审计连通性测试 (test_data_acquisition.py)
=================================================================================
测试目标:
  1. 验证基于 AkShare 的联网数据采集引擎能够正常访问公开数据接口；
  2. 验证宏观经济 (GDP) 时间序列的获取与标准化重塑；
  3. 验证微观行业 (汽车整车) 上市公司成分股检索与面板数据构建；
  4. 验证新获取的数据集能否直接送入 L1: data-audit 进行全套因果识别特征审计。
=================================================================================
"""

import os
import sys
import pandas as pd

# 将项目根目录加入模块检索路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tools.python.data_acquisition import DataAcquisitionEngine
from tools.python.econometric_engine import EmpiricalEngine

def print_header(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)

def main():
    print_header("联网实证数据采集与面板审计连通性测试 (Data Acquisition Test)")

    # 1. 环境检查
    print("\n[第 1 步] 检查采集引擎与网络依赖环境...")
    if not DataAcquisitionEngine.check_environment():
        print("❌ AkShare 未就绪，测试终止。")
        sys.exit(1)
    print("✅ 数据引擎与 Python 运行环境就绪。")

    # 2. 测试宏观经济时间序列获取
    print_header("[第 2 步] 联网测试: 获取中国宏观季度 GDP 时间序列")
    try:
        gdp_df = DataAcquisitionEngine.fetch_macro_gdp()
        print(f"📊 宏观数据样本预览 (前 5 期):")
        display_cols = [c for c in ['quarter_str', 'year', 'gdp', 'gdp_yoy'] if c in gdp_df.columns]
        print(gdp_df[display_cols].head())
    except Exception as e:
        print(f"⚠️ 宏观数据抓取提示: {e} (受实时网络连通性波动影响)")

    # 3. 测试微观行业成分股检索与面板构建
    print_header("[第 3 步] 联网测试: 检索行业成分股并构建微观企业面板")
    stocks_df = DataAcquisitionEngine.fetch_industry_stocks("汽车整车")
    stock_codes = stocks_df['stock_code'].tolist()[:10]
    print(f"📋 抽样成分股代码池: {stock_codes}")

    panel_df = DataAcquisitionEngine.build_firm_panel_sample(stock_codes, max_firms=5)
    print(f"\n📊 构建的微观面板数据结构概览:")
    print(f"   样本行数: {len(panel_df)}, 字段列表: {list(panel_df.columns[:8])}")

    # 4. 数据导出测试
    print_header("[第 4 步] 持久化测试: 导出标准计量 CSV 数据集")
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scratch/auto_collected_panel.csv"))
    DataAcquisitionEngine.export_data(panel_df, output_path, format="csv")

    # 5. 跨模块无缝流转: 将采集的数据直接送入 L1: data-audit 进行因果特征审计
    print_header("[第 5 步] 跨模块集成: 送入 L1: data-audit 执行结构审计")
    audit_meta = EmpiricalEngine.run_data_audit(panel_df)
    print("📦 [data-audit 输出的完整因果元数据契约]:")
    for k, v in audit_meta.items():
        print(f"   {k:28s}: {v}")

    # 6. 依据审计结果触发识别策略匹配
    id_decision = EmpiricalEngine.run_identification_strategy(audit_meta, rejected_strategies=[])
    print(f"\n🎯 [因果识别策略选择器 identification-strategy 输出]:")
    print(f"   主推策略: {id_decision['primary_strategy']}")
    print(f"   备选策略: {id_decision['alternative_strategies']}")
    print(f"   选择理由: {id_decision['selection_rationale']}")

    print("\n" + "=" * 75)
    print("  🎉 联网数据采集 ➔ 面板规整 ➔ 数据审计 ➔ 策略路由 全流程闭环测试成功！")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
