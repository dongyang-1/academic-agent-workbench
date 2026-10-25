---
name: iv
name_zh: 工具变量与弱工具推断
description: 2SLS 估计与弱工具变量诊断，包含 Effective F (Montiel Olea-Pflueger)、AR 置信区间及排他性逻辑论证。
category: 03_identification
priority: high
inputs: [数据集, 被解释变量, 内生变量, 外生控制变量, 工具变量]
outputs: [第一阶段回归结果, 2SLS估计系数, Effective F统计量, AR置信区间]
dependencies: [identification-strategy]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT / CC-BY-SA-4.0
adaptation_status: adapted
---

# 工具变量与弱工具推断 (Instrumental Variables & Weak IV)

## 一、 这个 Skill 是干什么的
`iv` 负责处理包含遗漏变量、双向因果或测量误差的内生性问题，执行两阶段最小二乘法 (2SLS)。它弃用了机械的“第一阶段 $F > 10$”判定法，引入现代弱工具变量推断体系（Effective F, Anderson-Rubin 弱工具稳健置信区间），并要求对排他性约束 (Exclusion Restriction) 进行制度背景与经济学理论论证。

## 二、 什么时候使用
- 当核心解释变量存在明确内生性，且拥有符合外生性与相关性假定的工具变量时；
- 需要评估工具变量强度及对弱工具风险进行稳健推断时。

## 三、 什么时候不要使用
- 当无法找到符合外生性假定的工具变量，或工具变量与内生变量完全无关时。

## 四、 需要什么输入
1. 数据集；
2. 被解释变量 $Y$；
3. 内生解释变量 $X_{endo}$；
4. 工具变量 $Z_{iv}$；
5. 外生控制变量与固定效应。

## 五、 弱工具变量非机械诊断流程

```text
第一阶段回归 (First-Stage Regression)
  │
  ├── 1. 第一阶段相关性检验 (First-stage coefficient & p-value)
  ├── 2. 传统 F 统计量 & Kleibergen-Paap rk F 统计量 (针对异方差/聚类)
  ├── 3. Montiel Olea-Pflueger (2013) Effective F 统计量 (阈值基于相对偏误/Size control)
  │
  └── 4. 弱工具变量稳健推断 (Weak-IV-Robust Inference)
        └── 对于边际弱工具/中等强度工具，强制报告 【Anderson-Rubin (AR) 置信区间】
```

## 六、 规则与禁忌
- **废除机械规则**：严禁仅以 $F > 10$ 或 $F < 10$ 简单宣称工具变量绝对有效或绝对无效；
- **排他性论证**：必须提供排他性约束（工具变量仅通过内生变量影响被解释变量）的经济学逻辑与可能违反渠道分析。

## 七、 诊断要求
- 报告第一阶段回归系数、标准误与 $F$ 统计量；
- 报告 2SLS 估计系数与 Anderson-Rubin 稳健置信区间。

## 八、 输出结果
- 第一阶段与第二阶段 2SLS 回归表；
- 弱工具变量检验统计量与 AR 置信区间；
- 排他性约束逻辑核查清单。

## 九、 失败条件
- 第一阶段 $F < 1$ 极度弱相关；
- 工具变量直接与被解释变量存在不可忽视的直接因果关联（违反排他性）。

## 十、 底层工具
- Python: `linearmodels.iv.IV2SLS`, `statsmodels`；
- Stata: `ivreg2`, `weakivtest`, `weakiv`；
- R: `AER::ivreg`, `ivDiag::ivDiag`.

## 十一、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / AERS；
- 许可证：MIT / CC-BY-SA-4.0 License。

## 十二、 中文用户说明与防避坑指南
现代计量学已经证明，传统的 $F > 10$ 只能控制相对偏误大小，不能保证二阶段 $t$ 检验的 Size。使用本 Skill 可以计算 Montiel Olea-Pflueger Effective F，并自动输出 Anderson-Rubin 区间，使你的工具变量分析符合当前主流期刊的规范。
