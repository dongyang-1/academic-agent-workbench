---
name: identification-strategy
name_zh: 因果识别策略选择器
description: 从研究问题与审计元数据出发，在全套 11 大 L2 估计器之间做优先级匹配与防死循环策略排除。
category: 03_identification
priority: critical
inputs: [研究问题, 数据审计元数据 (is_staggered, has_running_var_cutoff, has_slope_kink, has_bunching_threshold, has_candidate_iv, has_donor_pool, has_shift_share_structure, has_high_dim_controls, has_time_series_lags 等), 被拒绝策略列表 (rejected_strategies), 否决原因 (rejection_reasons)]
outputs: [主识别策略 (primary_strategy), 备选策略列表 (alternative_strategies), 决策推导树说明]
dependencies: [data-audit]
source_repository: AER-Skills
source_path: skills/aer-identification/
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 因果识别策略选择器 (Identification Strategy)

## 一、 这个 Skill 是干什么的
`identification-strategy` 是实证分析的因果逻辑中枢。它读取 `data-audit` 产出的完整结构化数据元数据，在全套 **11 个 L2 估计器**（`did`, `staggered-did`, `iv`, `rdd`, `synthetic-control`, `matching`, `shift-share`, `double-machine-learning`, `bunching-design`, `regression-kink-design`, `local-projections`）之间进行多候选优先级匹配与降级选择，并在收到 🔴 判定时自动排除已被否决的策略。

## 二、 完整 11 大 L2 估计器决策树

```text
               ┌─────────────────────────────────────────┐
               │    数据审计结构化元数据与识别假设输入    │
               └────────────────────┬────────────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │ 检查 rejected_strategies  │
                      │ 排除上一轮已被否决的策略  │
                      └─────────────┬─────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    ▼                               ▼                               ▼
【断点/折角/堆积特征】           【政策/事件冲击特征】            【工具变量/冲击矩阵特征】
1. has_running_var_cutoff ──►【rdd】 1. 统一时点 ──► 【did】        1. 外生工具变量 ──► 【iv】
2. has_slope_kink ──► 【regression-kink-design】 2. 错位实施 ──► 【staggered-did】 2. 份额+冲击 ──► 【shift-share】
3. has_bunching ──► 【bunching-design】 3. 极少受体 ──► 【synthetic-control】
                                    4. 动态冲击 ──► 【local-projections】
    ┌───────────────────────────────┴───────────────────────────────┐
    ▼                                                               ▼
【高维控制变量/复杂非线性特征】                                 【可观测协变量偏误特征】
has_high_dim_controls == True                                  样本组间背景特征存在系统偏误
    │                                                               │
    └─► 【double-machine-learning】                                 └─► 【matching】
        (DML / 双重机器学习)                                            (PSM / 精确匹配)
```

## 三、 11 大方法多候选优先级排序 (Priority Ranking)
当数据同时满足多个策略条件时，按以下因果识别外生性等级进行优先级排序：

```text
优先级 1 (局部自然实验/断点): 【rdd】 / 【regression-kink-design】 / 【bunching-design】
优先级 2 (制度政策实验):     【staggered-did】 / 【did】
优先级 3 (前沿机器学习无偏): 【double-machine-learning】
优先级 4 (宏观合成/动态冲击): 【synthetic-control】 / 【local-projections】
优先级 5 (外生冲击/工具变量): 【shift-share】 / 【iv】
优先级 6 (可观测协变量控偏): 【matching】
```

- **主备策略输出规则**：选择优先级最高且未经否决的策略作为 `primary_strategy`，其余候选进入 `alternative_strategies`。

## 四、 输出结构化 JSON 契约
```json
{
  "primary_strategy": "double-machine-learning",
  "alternative_strategies": ["staggered-did", "matching"],
  "rejected_strategies_history": [],
  "selection_rationale": "检测到高维控制变量与非线性混杂，优先推荐选择 double-machine-learning",
  "required_diagnostics": ["cross_fitting_mse", "neyman_orthogonality_check"]
}
```

## 五、 底层工具
- AER Methods Reference 定位规则；
- 状态机决策引擎。

## 六、 来源与许可证信息
- 来源：AER-Skills (`aer-identification` + `methods-reference.md`)；
- 许可证：MIT License。
