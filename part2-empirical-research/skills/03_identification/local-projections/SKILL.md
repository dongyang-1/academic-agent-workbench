---
name: local-projections
name_zh: 局部投影法与 LP-DiD
description: 基于 Jordà (2005) 与 Dube 等 (2023) 框架，采用局部投影法 (LP & LP-DiD) 估计动态脉冲响应与多期政策冲击。
category: 03_identification
priority: high
inputs: [时间序列/面板数据集, 被解释变量, 政策冲击变量(Shock/Policy), 前瞻步数(Horizon H), 滞后控制项]
outputs: [各前瞻步数(h=0..H)的脉冲响应系数, 动态脉冲响应带, Newey-West/Driscoll-Kraay 稳健SE]
dependencies: [identification-strategy]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# 局部投影法与 LP-DiD (Local Projections & LP-DiD)

## 一、 这个 Skill 是干什么的
`local-projections` 负责估计时间序列与面板数据中**政策冲击对经济系统的长期动态脉冲响应 (Impulse Response Functions, IRFs)**。它遵循 Jordà (2005, *AER*) 的局部投影 (Local Projections, LP) 理论，并引入 Dube et al. (2023) 最新提出的 **LP-DiD** 框架。通过针对每个前瞻预测步数 $h = 0, 1, \dots, H$ 运行独立的回归方程，它克服了传统向量自回归 (VAR) 对模型误设定的极高敏感性，并在多期动态政策冲击中展现出极高的稳健性。

## 二、 什么时候使用
- 当需要估计政策冲击在未来多个时期（如未来 1 到 24 个月）的动态累积效应或脉冲响应曲线；
- 当数据包含高频宏观/金融面板（如各省/各国的货币政策、财政支出冲击、关税变化）；
- 当控制变量中包含被解释变量与处理变量的多个滞后项 (Lags) 时。

## 三、 什么时候不要使用
- 当截面样本极小且时间序列极短（$T < 10$）导致前瞻预测期失真时。

## 四、 需要什么输入
1. 时间序列或面板数据集；
2. 被解释变量 $Y_{i,t}$；
3. 外生政策冲击变量 $D_{i,t}$（或结构化 Shock）；
4. 前瞻步数上限 $H$（例如 $H=12$）；
5. 滞后控制阶数 $p$（如 $Y_{i,t-1}, D_{i,t-1}$ 等滞后项）。

## 五、 LP & LP-DiD 估计方程与流程

```text
设定前瞻步数 h = 0, 1, 2, ..., H
  │
  ├── 针对每一个前瞻步数 h 拟合独立方程：
  │      Y_{i, t+h} - Y_{i, t-1} = beta_h * D_{i, t} + Gamma_h * X_{i, t-1} + alpha_i + lambda_t + e_{i, t+h}
  │
  ├── 调整重叠前瞻窗口导致的时间序列自相关标准误
  │      ──► 修正为 Newey-West 或 Driscoll-Kraay 序列自相关聚类标准误。
  │
  └── 汇总系数序列 [beta_0, beta_1, ..., beta_H]
         └── 绘制带 95% 置信带的动态脉冲响应曲线图 (Impulse Response Plot)。
```

## 六、 规范与诊断要求
- **序列自相关修正**：由于预测目标 $Y_{t+h}$ 在 $h > 0$ 时存在机械性的移动平均自相关（Overlap），必须使用 Driscoll-Kraay 或 HAR (Heteroskedasticity and Autocorrelation Robust) 标准误；
- **控制滞后项阶数测试**：汇报不同滞后阶数 $p \in [1, 4]$ 下脉冲响应曲线的稳定性。

## 七、 输出结果
- 前瞻步数 $h=0 \dots H$ 下的动态反应系数 $\hat{\beta}_h$、标准误及 $P$ 值表；
- 动态脉冲响应响应带图 (IRF Plot)。

## 八、 失败条件
- 前瞻期 $H$ 设置过大超过时间序列总长度的 1/3；
- 未包含关键滞后项导致回归存在严重的动态遗漏偏误。

## 九、 底层工具
- Python: `statsmodels.tsa`, `linearmodels`, StatsPAI `lp_did`；
- Stata: `lpdid`, `lpseries`；
- R: `lpdid`, `lpschedule`.

## 十、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / Jordà (2005) & Dube et al. (2023)；
- 许可证：MIT License。

## 十一、 中文用户说明与防避坑指南
在做宏观政策、金融市场或高频面板分析时，传统 VAR 很容易因为一个滞后项设错而导致整个脉冲响应图大相径庭。局部投影法（LP 和 LP-DiD）是目前顶刊最推崇的方法，它对每个未来时期单独做回归，结果极其稳健。
