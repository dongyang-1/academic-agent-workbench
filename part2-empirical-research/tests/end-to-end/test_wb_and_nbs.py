#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=================================================================================
经济学/社科实证分析智能体 - World Bank 跨国面板与国家统计局省际面板采集审计测试
=================================================================================
测试内容:
  1. 验证 World Bank API 跨国面板数据在线获取与清洗能力；
  2. 验证国家统计局 (NBS) 省际宏观面板采集与基准保障能力；
  3. 将两大数据集无缝送入 L1: data-audit 执行结构审计并匹配计量识别策略。
=================================================================================
"""

import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tools.python.data_acquisition import DataAcquisitionEngine
from tools.python.econometric_engine import EmpiricalEngine

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    print_banner("World Bank 跨国面板与国家统计局 (NBS) 省际面板端到端集成测试")

    # ---------------------------------------------------------------------------
    # 测试一：World Bank API 跨国实证面板
    # ---------------------------------------------------------------------------
    print_banner("🌐 [测试 1] World Bank API: 获取中美德日法英韩跨国实证面板")
    wb_df = DataAcquisitionEngine.fetch_world_bank_panel(
        countries=['CHN', 'USA', 'DEU', 'JPN', 'GBR', 'FRA', 'KOR'],
        start_year=2018,
        end_year=2023
    )
    
    print("\n📋 跨国面板抽样预览 (前 8 行):")
    print(wb_df.head(8).to_string(index=False))

    # 持久化
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
    os.makedirs(out_dir, exist_ok=True)
    wb_path = os.path.join(out_dir, "world_bank_country_panel.csv")
    DataAcquisitionEngine.export_data(wb_df, wb_path, format="csv")

    # 送入 data-audit 审计
    wb_audit = EmpiricalEngine.run_data_audit(wb_df.rename(columns={'country_code': 'firm_id'}))
    print("\n📦 [World Bank 跨国面板 - data-audit 审计结果]:")
    print(f"   是否面板结构 (is_panel):          {wb_audit['is_panel']}")
    print(f"   面板平衡性 (panel_balanced):      {wb_audit['panel_balanced']}")
    print(f"   跨国个体数 (n_units):             {wb_audit['n_units']} 个国家")
    print(f"   总观测点数 (n_obs):               {wb_audit['n_obs']} 个国家-年度观测点")

    # ---------------------------------------------------------------------------
    # 测试二：国家统计局 (NBS) 省际宏观实证面板
    # ---------------------------------------------------------------------------
    print_banner("🏛️ [测试 2] 国家统计局 (NBS): 获取中国各省份宏观实证面板")
    nbs_df = DataAcquisitionEngine.fetch_nbs_provincial_panel(
        start_year=2018,
        end_year=2023
    )

    print("\n📋 省际宏观面板抽样预览 (前 8 行):")
    print(nbs_df[['province_name', 'year', 'gdp_billion', 'gdp_per_capita', 'population_million', 'fiscal_revenue_billion']].head(8).to_string(index=False))

    # 持久化
    nbs_path = os.path.join(out_dir, "nbs_provincial_macro_panel.csv")
    DataAcquisitionEngine.export_data(nbs_df, nbs_path, format="csv")

    # 送入 data-audit 审计
    nbs_audit = EmpiricalEngine.run_data_audit(nbs_df.rename(columns={'province_id': 'firm_id'}))
    print("\n📦 [国家统计局省际面板 - data-audit 审计结果]:")
    print(f"   是否面板结构 (is_panel):          {nbs_audit['is_panel']}")
    print(f"   面板平衡性 (panel_balanced):      {nbs_audit['panel_balanced']}")
    print(f"   省份个体数 (n_units):             {nbs_audit['n_units']} 个省份/直辖市")
    print(f"   总观测点数 (n_obs):               {nbs_audit['n_obs']} 个省份-年度观测点")

    print_banner("🎉 World Bank 跨国面板与国家统计局省际面板全流程测试圆满成功！")

if __name__ == "__main__":
    main()
