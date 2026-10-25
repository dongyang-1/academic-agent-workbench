---
name: rdd
name_zh: 断点回归设计
description: 断点回归估计 (RDD)，包含 MSE 最优带宽选择、RBC 置信区间、McCrary/Cattaneo 密度检验与协变量连续性研判。
category: 03_identification
priority: high
inputs: [数据集, 被解释变量, 驱动变量(Running Variable), 断点值(Cutoff)]
outputs: [RDD估计处理效应(LATE), 带宽敏感性图, 密度检验结果, 断点两侧拟合图]
dependencies: [identification-strategy]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 断点回归设计 (Regression Discontinuity Design - RDD)

## 一、 这个 Skill 是干什么的
`rdd` 负责处理基于连续变量断点规则赋值（规则硬断点 Sharp RDD 或软断点 Fuzzy RDD）的因果推断。它遵循现代 RDD 规范（Calonico, Cattaneo & Titiunik 2014），采用局部线性多项式回归、MSE 最优带宽选择与 Robust Bias-Corrected (RBC) 置信区间。对 McCrary 密度检验采取非机械式的综合研判。

## 二、 什么时候使用
- 当个体受处理状态由某个连续驱动变量 (Running Variable) 是否跨越固定断点 (Cutoff) 决定时。

## 三、 什么时候不要使用
- 当驱动变量极度离散（观测值少于 10 个独特取值）或不存在清晰断点时。

## 四、 需要什么输入
1. 数据集；
2. 被解释变量 $Y$；
3. 驱动变量 $X$ 与断点值 $c$；
4. 针对 Fuzzy RDD：实际受处理状态 $D$。

## 五、 非机械式操纵诊断与估计流程

```text
1. 驱动变量 Cutoff 密度检验 (McCrary / Cattaneo Density Test)
   ├── 发现密度不连续 (Discontinuity at Cutoff, p < 0.05)
   └── ⚠️ 提示操纵风险 (Manipulation Risk)，而非直接判定 RDD 彻底作废！
       └── 结合 【制度背景】(个体验算成本)、【协变量连续性检验】 与 【假 Cutoff 检验】 综合判断。

2. 局部线性估计 (Local Linear Regression)
   ├── MSE-optimal 带宽选择 (h)
   ├── 三角核 (Triangular Kernel) 加权
   └── 报告 Robust Bias-Corrected (RBC) 估计量与置信区间 (Gelman & Imbens 2019 推荐)。
```

## 六、 规范与禁忌
- **废除高阶多项式**：禁止使用 3 阶或 4 阶全局多项式拟合；推荐使用局部线性（1 阶）或局部二次（2 阶）多项式；
- **非机械判死刑**：不得因密度检验 $p < 0.05$ 就直接否定 RDD，必须分析个体验算能力与制度现实。

## 七、 诊断要求
- 进行协变量在 Cutoff 两侧的连续性检验（均值无突变）；
- 进行带宽敏感性测试（以 0.5h, 1h, 1.5h, 2h 运行回归）；
- 进行伪 Cutoff 断点安慰剂检验（在无政策处设置假 Cutoff）。

## 八、 输出结果
- RDD 处理效应估计量 (LATE) 与 RBC 置信区间；
- 断点两侧散点与拟合曲线图 (RDD Plot)；
- 带宽敏感性与密度检验诊断报告。

## 九、 失败条件
- 驱动变量被个体完全精准操纵；
- 多种预设协变量在 Cutoff 处存在大幅突变。

## 十、 底层工具
- Python: `rdrobust`；
- Stata: `rdrobust`, `rddensity`；
- R: `rdrobust`, `rddensity`.

## 十一、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / AERS；
- 许可证：MIT License。

## 十二、 中文用户说明与防避坑指南
很多初学者喜欢用全局高阶多项式做 RDD，但这会导致边界权重畸变。本 Skill 严格采用现代 `rdrobust` 局部线性回归与 RBC 偏差修正置信区间，并能客观分析密度检验，避免误判正常的政策申报现象。
