---
name: staggered-did
name_zh: 错位/多期实施DID
description: 针对多期错位实施政策的现代 DID 估计量 (CS / Sun-Abraham / BJS Imputation)，彻底解决 TWFE 负权重偏误。
category: 03_identification
priority: critical
inputs: [面板数据集, 被解释变量, 首次受处理时间(first_treat), 个体ID, 时间ID]
outputs: [Group-Time ATT(g,t), 汇总 ATT, 异质性稳健动态事件研究图, Bacon分解结果]
dependencies: [identification-strategy]
source_repository: AER-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 错位/多期实施 DID (Staggered DiD)

## 一、 这个 Skill 是干什么的
`staggered-did` 专门用于解决面板数据中**政策在不同个体、不同年份/月份错位分批实施 (Staggered Rollout)** 的因果识别问题。它采用 2020 年代现代 DID 前沿估计量（Callaway-Sant'Anna, Sun-Abraham, Borusyak-Jaravel-Spiess 插补法），消除传统双向固定效应 (TWFE) 因“已处理组作为对照组”产生的负加权偏误 (Forbidden Comparisons)。

## 二、 什么时候使用
- 当处理变量在不同时间段陆续实施（如政策试点逐批扩围）；
- 当处理效应可能随时间累积或在不同 Cohort 之间存在异质性时。

## 三、 什么时候不要使用
- 当所有受处理单位在同一时间接受处理，且效应同质时（可用 `did`）。

## 四、 需要什么输入
1. 面板数据集；
2. 被解释变量 $Y_{it}$；
3. 个体 ID `id` 与时间 ID `time`；
4. 首次受处理时间变量 `first_treat`（未受处理单位填 0 或无穷大）。

## 五、 执行流程与现代估计量选择
1. **Goodman-Bacon 分解**：计算传统 TWFE 权重中来自“早处理 vs 晚处理”坏对比的比例；
2. **现代估计量拟合**（三选一或对比）：
   - **Callaway & Sant'Anna (2021)**：估计组-时间边际效应 $ATT(g,t)$；
   - **Sun & Abraham (2021)**：交互加权事件研究法；
   - **Borusyak et al. (2024)**：双向固定效应插补法 (Imputation)；
3. **动态效应聚合**：生成未污染的事件研究动态系数图 (Dynamic Event-Study Plot)；
4. **联合前检验**：对处理前各期 $ATT(g,t)$ 进行联合检验 (Joint Pre-test, Roth 2022)。

## 六、 硬性质量门 (Quality Gate)
- **绝对禁止**：在存在错位处理和效应异质性时，仅将传统单系数 TWFE 作为论文唯一的核心因果结论！必须报告至少一种现代异质性稳健估计量。

## 七、 诊断要求
- 报告 Goodman-Bacon 分解中坏对比权重的占比；
- 进行平行趋势联合 p 值检验，若联合 $p < 0.05$，标记平行趋势假设风险。

## 八、 输出结果
- $ATT(g,t)$ 组-时间效应矩阵与总体平均处理效应 $ATT$；
- 现代事件研究动态效应图；
- Bacon 分解结果图表。

## 九、 失败条件
- 缺少未处理或未届处理组 (Not-yet-treated) 作为对照；
- 处理前观测期不足 2 期导致无法检验预前期趋势。

## 十、 底层工具
- Python: `differences` / `pyfixest` (did2s) / `statsmodels`；
- Stata: `csdid`, `eventstudyinteract`, `did_imputation`, `bacondecomp`；
- R: `did::att_gt`, `fixest::sunab`, `did2s`.

## 十一、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md` + `sun-abraham-demo`)；
- 许可证：MIT License。

## 十二、 中文用户说明与防避坑指南
近年来 Top-5 经济学期刊对错位 DID 的审核极其严格。传统 TWFE 回归会将先试点的样本作为后试点样本的对照组，在效应随时间增长时导致估计系数反向。使用 `staggered-did` 能确保你的估计结果符合当代顶刊的方法论硬要求。
