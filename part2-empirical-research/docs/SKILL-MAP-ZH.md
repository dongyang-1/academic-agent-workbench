# Skill 来源、许可证与映射矩阵 (Skill Map) — v1.2 最终版

> 架构扩展说明:
> 本版在 L2 计量方法层中补充了 4 个顶刊前沿因果识别估计器 (`double-machine-learning`, `bunching-design`, `regression-kink-design`, `local-projections`),
> 使 L2 方法由 7 个扩充至 11 个。
>
> **总计: L1 6 个 + L2 11 个 + L3 8 个 = 25 个 Skill**。

## L1: 核心决策层 (6)

| Skill ID | 中文名称 | 关键功能描述 | 知识来源 | 许可证 |
|---|---|---|---|---|
| `empirical-router` | 实证分析全局路由 | 控制整体状态机闭环与降级重新路由 | 自研 / AER | MIT |
| `data-audit` | 实证数据结构审计 | 审计面板/截面、断点、IV、高维特征等 | AERS (00.1~00.3) | CC-BY-SA-4.0 |
| `identification-strategy` | 因果识别策略选择器 | 从 11 个 L2 策略中匹配最佳设计与防死循环 | AER (aer-identification) | MIT |
| `baseline-regression` | 基准回归估计器 | 高维固定效应/OLS/面板模型设定与共线性排查 | AERS (00.1~00.3) | CC-BY-SA-4.0 |
| `robustness-router` | 稳健性检验路由器 | 识别驱动的稳健性检验组合 | AER (aer-robustness) | MIT |
| `econometric-reviewer` | 计量审稿人综合审查器 | 审稿人视角评估结果并执行 🟢/🟡/🔴 拦截 | 自研 / AER (referee-sim) | MIT |

## L2: 计量方法层 (11 - 扩充 4 大顶刊前沿方法)

| Skill ID | 中文名称 | 关键功能描述 | 知识来源 | 许可证 |
|---|---|---|---|---|
| `did` | 基础双向固定效应DID | 标准 2×2 DID 与基础 TWFE 回归 | AERS / Mixtape | CC-BY-SA-4.0 |
| `staggered-did` | 错位/多期实施DID | CS / Sun-Abraham / Imputation (消解坏对比偏误) | AER (methods-reference) | MIT |
| `iv` | 工具变量与弱工具推断 | 2SLS, Effective F, AR 弱工具置信区间 | AER / AERS | MIT / CC-BY-SA-4.0 |
| `rdd` | 断点回归设计 | 局部线性、RBC置信区间、密度检验研判 | AER / AERS | MIT |
| `synthetic-control` | 合成控制与SDID | SCM, SDID, Placebo 空间/时间排列推断 | AER / CausalPy | Apache-2.0 / MIT |
| `matching` | 倾向得分与精确匹配 | PSM、精确匹配、共同范围检验与 Love Plot | AERS | CC-BY-SA-4.0 |
| `shift-share` | Bartik/份额移动IV | 份额外生 vs 冲击外生检验与冲击层级标准误 | AER (methods-reference) | MIT |
| **`double-machine-learning`** (DML / 双重机器学习) | 双重机器学习 (DML) | Neyman 正交化+交叉拟合消解高维混杂偏误 | AER / Chernozhukov(2018) | MIT |
| **`bunching-design`** (Bunching / 行为聚束分析设计) | 行为聚束分析设计 | 反事实无堆积密度拟合与超额堆积量 B/结构弹性 | AERS / Saez(2010) | CC-BY-SA-4.0 |
| **`regression-kink-design`** (RKD / 斜率断点回归设计) | 斜率断点回归设计 (RKD) | 驱动变量断点处斜率折角 (Kink in Slope) 识别 | AER / Card(2015) | MIT |
| **`local-projections`** (LP & LP-DiD / 局部投影与 LP-DiD) | 局部投影法与 LP-DiD | 动态脉冲响应带 (IRF) 与 LP-DiD 多期冲击 | AER / Jordà(2005) | MIT |

## L3: 工具/分析组件层 (8)

| Skill ID | 中文名称 | 关键功能描述 | 知识来源 | 许可证 |
|---|---|---|---|---|
| `placebo` | 安慰剂检验组件 | 时间/个体置换与伪Cutoff 蒙特卡洛密度 | AER / AERS | MIT |
| `clustering` | 聚类层级与Wild Bootstrap | 少数Cluster修正与聚类选择 | AER / AERS | MIT |
| `alternative-specification` | 替代规格与敏感性分析 | 共线性防范、替代模型与 Oster(2019) delta | AER | MIT |
| `heterogeneity` | 异质性分析组件 | 理论驱动的分组与组间系数差异检验 | AER / AERS | MIT |
| `mechanism` | 因果机制诊断组件 | 机制假设与替代解释排除 | AER (aer-robustness) | MIT |
| `tables-and-figures` | 论文级表格与图表生成 | AER/AEJ 风格 LaTeX booktabs / Markdown 表格 | AER (aer-tables-figures) | MIT |
| `replication-tools` | 实证复现与差异比对工具 | 对既有论文/代码复现数值比对 | 自研 | MIT |
| `sensitivity-bounds` | 平行趋势敏感性边界 (HonestDiD) | 🟡/🔴 判定后的补救路线图 (Rambachan-Roth) | AER (methods-reference) | MIT |
