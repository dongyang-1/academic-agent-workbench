---
name: data-audit
name_zh: 实证数据结构审计
description: 审计数据维度、面板/截面特征、处理变量时序分布、断点/斜率特征、候选 IV、高维特征及高频序列，输出结构化元数据。
category: 01_data
priority: high
inputs: [原始数据集, 变量名称说明]
outputs: [数据结构审计报告, 结构化数据元数据 (is_panel, is_staggered, has_running_var_cutoff, has_slope_kink, has_bunching_threshold, has_candidate_iv, has_donor_pool, has_shift_share_structure, has_high_dim_controls, has_time_series_lags)]
dependencies: []
source_repository: Auto-Empirical-Research-Skills
source_path: skills/00.1-Full-empirical-analysis-skill_Python/
original_skill_name: Full-empirical-analysis-skill
license: CC-BY-SA-4.0
adaptation_status: adapted
---

# 实证数据结构审计 (Data Audit)

## 一、 这个 Skill 是干什么的
`data-audit` 负责在进入任何模型估计之前，对数据集进行全方位的经济学实证审计。它把数据结构与后续的**全套 11 类因果识别方法**（DID, Staggered-DID, IV, RDD, SCM, Matching, Shift-share, DML, Bunching, RKD, LP）直接绑定，输出下游决策树所必需的完整结构化元数据契约。

## 二、 什么时候使用
- 数据载入后的第一步；
- 在决定使用 11 类因果推断方法中的任何一种前必须运行。

## 三、 什么时候不要使用
- 在数据结构已经完成深度审计且未发生更新时。

## 四、 执行流程 (11 大方法数据特征审计)
1. **数据形态与面板特征**：判别截面、面板并计算平衡度（`is_panel`, `panel_balanced`）；
2. **错位处理审计 (DID / Staggered-DID)**：识别是否分批错位实施（`is_staggered`, `has_never_treated`）；
3. **水平与斜率断点特征审计 (RDD / RKD)**：检查水平突变（`has_running_var_cutoff`）与斜率折角（`has_slope_kink`）；
4. **行为堆积特征审计 (Bunching)**：检查关键门槛阈值处是否存在显著行为聚集（`has_bunching_threshold`）；
5. **工具变量与 Bartik 结构审计 (IV / Shift-Share)**：检查外生 IV 候选（`has_candidate_iv`）与份额-冲击结构（`has_shift_share_structure`）；
6. **宏观合成控制审计 (SCM)**：检查受体规模与 Donor Pool（`has_donor_pool`）；
7. **高维特征与非线性审计 (DML)**：检查控制变量维度是否极高（`has_high_dim_controls`）；
8. **高频序列与动态冲击审计 (LP)**：检查数据是否包含高频时间序列与动态滞后项（`has_time_series_lags`）。

## 五、 输出结构化元数据契约
```json
{
  "is_panel": true,
  "is_staggered": true,
  "has_never_treated": true,
  "panel_balanced": true,
  "has_running_var_cutoff": false,
  "has_slope_kink": false,
  "has_bunching_threshold": false,
  "has_candidate_iv": false,
  "has_donor_pool": false,
  "has_shift_share_structure": false,
  "has_high_dim_controls": false,
  "has_time_series_lags": false
}
```

## 六、 底层工具
- Python (`pandas`, `numpy`, `statsmodels`)；
- Stata (`isid`, `xtset`, `codebook`)；
- R (`tidyverse`, `panelView`).

## 七、 来源与许可证信息
- 来源：AERS 00.1~00.3 全流程数据准备模块；
- 许可证：CC-BY-SA-4.0 License。
