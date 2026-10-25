---
name: placebo
name_zh: 安慰剂检验组件
description: 时间/个体置换随机化安慰剂检验、假政策时间与假 Cutoff 检验，生成估计系数分布图。
category: 04_robustness
priority: medium
inputs: [数据集, 基准回归设定, 随机化次数(如500/1000)]
outputs: [安慰剂估计系数分布, 真实系数的P值位置, 蒙特卡洛密度图]
dependencies: [baseline-regression]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: skills/aer-robustness/
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 安慰剂检验组件 (Placebo Test Component)

## 一、 这个 Skill 是干什么的
`placebo` 专门用于执行各种形式的**安慰剂检验 (Placebo Test)**，验证基准结果是否由不可观测的随机因素、未控制的动态趋势或纯粹的统计偶然驱动。它支持：1) 处理组随机置换 (In-space Placebo)；2) 处理时间虚构提前/推后 (In-time Placebo)；3) 断点回归中的假 Cutoff 检验。

## 二、 什么时候使用
- 当基准因果回归显著，且需要排除潜在的不可观测混杂因素时。

## 三、 什么时候不要使用
- 当基准模型估计由于缺失值或代码错误尚未成功运行前。

## 四、 执行流程
1. **构建伪处理 (False Treatment)**：
   - 空间置换：从控制池中随机抽取与真实处理组规模相当的样本作为假处理组；
   - 时间置换：将政策发生时间提前 2-3 年（要求样本包含足够的 Pre-period）；
2. **重复估计循环 (Monte Carlo Simulations)**：重复运行基准回归 500-1000 次，记录假估计系数 $\hat{\beta}^{placebo}$；
3. **计算经验 $p$ 值与密度分布**：比较真实估计系数 $\hat{\beta}^{true}$ 在假系数分布中的相对位置。

## 五、 输出与要求
- 真实估计系数应位于假系数蒙特卡洛核密度分布两侧极罕见尾部（经验 $p < 0.01$）；
- 假系数分布图必须包含真实系数的显著标度线。

## 六、 底层工具
- Python: `numpy` 随机抽样 + `pyfixest` 循环；
- Stata: `permute`, `bootstrap`；
- R: `purrr`, `ggplot2`.

## 七、 来源与许可证信息
- 来源：AER-Skills / AERS；
- 许可证：MIT License。
