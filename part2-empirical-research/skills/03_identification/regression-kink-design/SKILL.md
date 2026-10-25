---
name: regression-kink-design
name_zh: 斜率断点回归设计
description: 基于 Card 等 (2015) 框架，利用政策在断点 (Cutoff) 处的斜率转折/折角 (Kink in Slope) 进行边际因果效应估计。
category: 03_identification
priority: high
inputs: [数据集, 被解释变量, 驱动变量(Running Variable), 斜率转折点(Cutoff c)]
outputs: [RKD 斜率因果效应估计量, 带宽敏感性测试, 驱动变量一阶与二阶导数拟合图]
dependencies: [identification-strategy]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 斜率断点回归设计 (Regression Kink Design - RKD)

## 一、 这个 Skill 是干什么的
`regression-kink-design` 专门用于利用**政策在驱动变量特定断点 (Cutoff) 处的斜率转折/折角 (Kink)** 进行因果效应估计。与传统 RDD 依赖水平突变 (Jump in Level) 不同，RKD 适用于政策在断点处**水平完全连续，但函数斜率（一阶导数）发生突变**的制度安排（如失业保险金上限给付公式、累进税率阶梯斜率、补贴退坡比例转折点）。它遵循 Card, Lee, Pei & Weber (2015, *Econometrica*) 的理论规范。

## 二、 什么时候使用
- 当政策确定规则在 Cutoff $c$ 处形式为：$D(X) = \gamma_0 + \gamma_1 (X - c) \times \mathbb{I}(X \ge c)$，即边际激励斜率存在断裂；
- 当观察到被解释变量 $Y$ 在 Cutoff 处呈现出明显的“折角/斜率改变”特征。

## 三、 什么时候不要使用
- 当政策在 Cutoff 处直接发生了水平突变（应当使用 `rdd` 技能）；
- 当驱动变量在 Cutoff 附近存在密度的非连续跳跃（存在精准操纵）。

## 四、 需要什么输入
1. 数据集；
2. 被解释变量 $Y$；
3. 驱动变量 $X$ 与斜率转折断点 $c$；
4. 针对 Fuzzy RKD：实际处理斜率指标。

## 五、 RKD 核心估计逻辑

```text
计算驱动变量相对值  X_tilde = X - c
  │
  ├── 1. 检验驱动变量密度一阶导数的连续性 (Density Slope Smoothness)
  │      ──► 确保个体无法精准操纵斜率转折点
  │
  ├── 2. 估计被解释变量在 Cutoff 两侧的斜率突变比例
  │      ──► 运行局部二次多项式或局部线性回归：
  │          Y = alpha + beta_1 X_tilde + beta_2 (X_tilde * I(X>=0)) + beta_3 X_tilde^2 + ...
  │
  └── 3. 计算 RKD 因果效应估计量 (Kink Estimator)
         └── Tau_RKD = ( dY/dX |_+ - dY/dX |_- ) / ( dD/dX |_+ - dD/dX |_- )
```

## 六、 诊断与质量要求
- **驱动变量密度连续性及斜率检验**：评估密度在 Cutoff 处是否存在导数突变；
- **协变量斜率连续性检验**：对所有关键预设协变量进行 RKD 估计，要求其斜率突变系数不显著；
- **带宽敏感性检验**：测试不同 MSE-optimal 带宽下的斜率估计稳定性。

## 七、 输出结果
- RKD 边际因果效应估计系数及其 RBC 偏差修正置信区间；
- Cutoff 两侧拟合斜率对比图 (RKD Plot)。

## 八、 失败条件
- 协变量在 Cutoff 处同样发生了斜率突变；
- 驱动变量密度在一阶导数上存在明显操纵性跳跃。

## 九、 底层工具
- Python: `rdrobust` (二阶导数估计)；
- Stata: `rdkink`, `rdrobust`；
- R: `rdkink`.

## 十、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / Card et al. (2015)；
- 许可证：MIT License。

## 十一、 中文用户说明与防避坑指南
许多政策（如失业金给付）并不是一下子断崖下跌，而是到了某个收入线后斜率变缓。这种情况下用 RDD 是测不出来的，必须用 RKD。本 Skill 专门帮你提取斜率的变化，测算政策边际激励的真实影响。
