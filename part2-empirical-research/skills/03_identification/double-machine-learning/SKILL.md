---
name: double-machine-learning
name_zh: 双重机器学习
description: 基于 Chernozhukov 等 (2018) 框架，通过 Neyman 正交化与交叉拟合在高维复杂协变量下估计无偏因果效应 (ATE/ATT)。
category: 03_identification
priority: high
inputs: [数据集, 被解释变量, 处理变量, 高维控制变量矩阵, ML算法模型(RandomForest/Lasso/XGBoost)]
outputs: [正交化因果效应估计量, 标准根号N渐近正态SE, 交叉拟合拟合度, 协变量相对重要性]
dependencies: [identification-strategy]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: examples/dml-plr-demo/
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 双重机器学习 (Double/Debiased Machine Learning - DML)

## 一、 这个 Skill 是干什么的
`double-machine-learning` 专门用于解决**控制变量维度极高（变量数接近或大于样本量）**或**混杂因素与被解释变量之间存在复杂非线性关系**时的因果推断问题。它遵循 Chernozhukov et al. (2018, *Econometrica*) 理论框架，通过 **Neyman 正交化 (Neyman Orthogonality)** 与 **K-折交叉拟合 (Cross-Fitting)**，结合灵活的机器学习算法（随机森林、Lasso、XGBoost、神经网络），消除传统 ML 估计中的“过拟合偏误”和“插件偏误 (Plug-in Bias)”，恢复标准 $\sqrt{N}$ 渐近正态推断。

## 二、 什么时候使用
- 当控制变量数量极多（包含高维特征、文本特征、地理网格或成千上万个交叉交互项）；
- 当假设混杂因素对 $Y$ 和 $D$ 的影响高度非线性，无法用简单线性 OLS 满足时。

## 三、 什么时候不要使用
- 当控制变量较少（如只有 3-5 个常规变量）且样本量极小 ($N < 200$) 时（常规 OLS 更稳定）。

## 四、 需要什么输入
1. 数据集；
2. 被解释变量 $Y$ 与处理变量 $D$（可为连续或二值）；
3. 高维控制变量矩阵 $X$（特征维度可达数百甚至数千）；
4. 机器学习估计器设定（如 `LassoCV`, `RandomForestRegressor`, `GradientBoostingRegressor`）。

## 五、 DML 核心算法与执行流程

```text
高维数据输入 (Y, D, X)
  │
  ├── 1. K-折交叉分块 (K-Fold Cross-Fitting, 如 K=5)
  │      防止估计同一子样本导致的正则化偏误 (Regularization Bias)。
  │
  ├── 2. 双重残差正交化 (Neyman Orthogonalization)
  │      ├── 用 ML 算法训练 Y ~ X，预测残差  y_res = Y - g(X)
  │      └── 用 ML 算法训练 D ~ X，预测残差  d_res = D - m(X)
  │
  └── 3. 残差对残差正交回归 (Orthogonal Residual Regression)
         └── y_res = alpha * d_res + e  ──► 获得无偏估计量 alpha (ATE/ATT)
```

## 六、 规范与诊断要求
- **评估 ML 残差可预测性**：报告 $Y \sim X$ 与 $D \sim X$ 在交叉验证下的 $R^2$ 或 MSE；
- **校验算法敏感性**：至少对比两种不同的 ML 底层算法（如 Lasso vs Random Forest），评估估计系数 $\hat{\alpha}$ 的稳定性。

## 七、 输出结果
- DML 偏线性模型 (Partial Linear Model, PLR) 或 交互模型 (Interactive Model, IRM) 的因果效应系数 $\hat{\alpha}$ 与标准误；
- 各特征的相对重要性 (Feature Importance) 排名表。

## 八、 失败条件
- 处理变量 $D$ 能够以 $R^2 \approx 1.0$ 被高维特征 $X$ 完全精确预测（违反重叠假定 / Overlap Failure）；
- 样本量太小导致交叉拟合的各 Fold 样本无法训练机器学习模型。

## 九、 底层工具
- Python: `DoubleML`, `econml`, `scikit-learn`；
- R: `DoubleML`；
- Stata: `ddml`.

## 十、 来源与许可证信息
- 来源：AER-Skills (`examples/dml-plr-demo/`) / Chernozhukov et al. (2018)；
- 许可证：MIT License。

## 十一、 中文用户说明与防避坑指南
很多研究者误以为把机器学习（如随机森林）直接用来回归就能做因果推断，但这会导致严重的正则化偏误。DML 通过“两次机器学习求残差 + 交叉拟合”的方法剔除混杂因素，是高维大数据时代Top-5期刊做因果推断的最前沿工具。
