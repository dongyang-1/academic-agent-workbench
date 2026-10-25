---
name: alternative-specification
name_zh: 替代规格与敏感性分析
description: 替代模型设定、样本缩尾/子样本敏感性、Oster(2019) 遗漏变量敏感性 bounds 与共线性审查。
category: 04_robustness
priority: medium
inputs: [基准回归模型, 控制变量子集, 替代变量]
outputs: [规格敏感性矩阵, Oster delta/bounds 值, 样本剔除前后对比表]
dependencies: [baseline-regression]
source_repository: AER-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 替代规格与敏感性分析 (Alternative Specification & Sensitivity)

## 一、 这个 Skill 是干什么的
`alternative-specification` 负责检验基准估计结果对各种非关键模型设定的敏感程度。它包括：1) 逐步增加控制变量组；2) 替换被解释变量或处理变量的度量方式；3) 样本缩尾 (Winsorize 1%/5%) 与剔除特殊子样本（如直辖市、金融业）；4) 评估 **Oster (2019) 遗漏变量偏差敏感性**。同时作为**共线性防范规则**的执行接口。

## 二、 什么时候使用
- 当基准结论成立，需要证明结论不受特定控制变量选择或度量误差驱动时。

## 三、 共线性与冗余防范规则
- **完全共线性排查**：排查哑变量陷阱或线性组合造成的完全共线性矩阵奇异；
- **保留模型必要项**：禁止在引入二次项 ($X, X^2$)、交互项 ($X, Z, X \times Z$) 或多项式时机械强行删除原始变量 $X$。保留与否由模型物理/经济意义决定。

## 四、 Oster (2019) 遗漏变量偏差评估
- 计算系数变动与 $R^2$ 变动之间的比例系数 $\delta$；
- 假定最大拟合度 $R_{max} = 1.3 \hat{R}^2$，计算使估计系数降为 0 所需要的相对遗漏变量重要性 $\delta$。若 $\delta > 1$，说明未观测遗漏变量需比现有控制变量重要 1 倍以上才能颠覆结论（结论稳健）。

## 五、 输出与要求
- 替代被解释变量/处理变量回归对比表；
- 缩尾 1% 与剔除极端样本后的估计表；
- Oster $\delta$ 值与系数边界 (Bounds)。

## 六、 底层工具
- Python: `statsmodels`, `pyfixest`；
- Stata: `psmatch2`, `oster` (`psacalc`)；
- R: `robumeta`, `oaxaca`.

## 七、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`)；
- 许可证：MIT License。
