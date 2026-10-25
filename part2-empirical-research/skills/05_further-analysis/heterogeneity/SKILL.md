---
name: heterogeneity
name_zh: 异质性分析组件
description: 理论与制度背景驱动的分组异质性分析与交互效应估计，含组间系数差异检验。
category: 05_further-analysis
priority: medium
inputs: [数据集, 基准模型, 分组异质性变量(如企业所有制/地区/规模)]
outputs: [分组回归对比表, 交互项估计系数, 组间系数差异检验 p 值]
dependencies: [baseline-regression]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: skills/aer-robustness/
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 异质性分析组件 (Heterogeneity Analysis)

## 一、 这个 Skill 是干什么的
`heterogeneity` 负责分析处理效应在不同群体、地区、时期或企业特征之间的非均匀分布（异质性）。它通过**分组回归 (Subsample Regressions)** 或 **连续/离散交互项 (Interaction Terms)** 展开，并执行严格的**组间系数差异检验 (Test of Equality of Coefficients Across Subsamples)**。

## 二、 什么时候使用
- 需要验证政策冲击对特定脆弱群体、特定所有制企业或特定市场环境的非对称影响时。

## 三、 规则与禁忌
- **严禁无脑数据挖掘**：坚决禁止为了凑 $p < 0.05$ 显著性而机械盲目罗列几十种无意义的分组！分组变量必须有明确的经济学理论、制度背景或政策设计逻辑支撑。

## 四、 执行与检验流程
1. **确定理论异质性维度**：如国企 vs 民企、东部 vs 中西部、高融资约束 vs 低融资约束；
2. **估计与交互模型**：
   - 分组回归：对各子样本分别估计主效应系数 $\beta_1, \beta_2$；
   - 交互项模型：$Y = \beta_0 + \beta_1 Treat + \beta_2 Hetero + \beta_3 (Treat \times Hetero) + \Gamma X + \varepsilon$；
3. **组间系数差异检验**：
   - 采用 SUR (Seemingly Unrelated Regressions) / `suest` 或 Fisher 组合排列检验 (Fisher's Permutation Test)，汇报组间系数差异 $\beta_1 - \beta_2$ 的 $p$ 值。

## 五、 输出与要求
- 分组回归系数对比表，包含组间差异检验 $p$ 值；
- 边际效应与交互效应可视化图。

## 六、 底层工具
- Python: `pyfixest`, `statsmodels`；
- Stata: `suest`, `bdiff`, `esttab`；
- R: `fixest`, `marginaleffects`.

## 七、 来源与许可证信息
- 来源：AER-Skills (`aer-robustness`) / AERS；
- 许可证：MIT License。
