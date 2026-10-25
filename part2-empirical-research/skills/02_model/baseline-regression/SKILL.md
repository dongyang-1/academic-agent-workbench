---
name: baseline-regression
name_zh: 基准回归估计器
description: 确定模型类型、高维固定效应与聚类标准误设定，产出基准回归结果，并排查完全共线与冗余变量。
category: 02_model
priority: high
inputs: [数据集, 核心变量定义, 识别策略方案]
outputs: [基准回归模型结果, 系数估计算法对象, 拟合度与统计量]
dependencies: [identification-strategy]
source_repository: Auto-Empirical-Research-Skills
source_path: skills/00.1-Full-empirical-analysis-skill_Python/
original_skill_name: Full-empirical-analysis-skill
license: CC-BY-SA-4.0
adaptation_status: adapted
---

# 基准回归估计器 (Baseline Regression)

## 一、 这个 Skill 是干什么的
`baseline-regression` 负责执行具体的基准回归建模。根据被解释变量类型（连续/二值/计数）和因果识别方案，配置固定效应（个体、时间、行业、地区等高维 FE）与标准误聚类层级（Clustering SE），生成标准化的基准计量回归表格。

## 二、 什么时候使用
- 当 `identification-strategy` 确定了模型设定框架后；
- 需要输出核心回归系数、标准误、t 值/p 值与 $R^2$ 时。

## 三、 什么时候不要使用
- 在未完成数据审计与变量设定时。

## 四、 需要什么输入
1. 审计后的数据集；
2. 被解释变量 $Y$、核心解释变量 $X$、控制变量列表 $C$；
3. 固定效应维度（如 `entity_id`, `year`）与聚类层级（如 `cluster_id`）。

## 五、 执行流程
1. **模型类型匹配**：
   - 连续变量 ──► 高维固定效应 OLS (`pyfixest.feols` / `reghdfe`)；
   - 二值变量 ──► Logit / Probit / FE Logit；
   - 计数变量 ──► Poisson / `fepois`；
2. **多重共线性与冗余检查**：
   - 检查是否存在完全共线性（如哑变量陷阱）；
   - **共线性防范规则**：禁止完全共线或无意义的冗余变量。但若模型中包含二次项（$X, X^2$）或交互项（$X, Z, X \times Z$），必须依据模型设定保留原始变量，不得机械删除；
3. **固定效应与标准误计算**：
   - 包含个体与时间双向固定效应 (TWFE)；
   - 标准误默认按个体或更高行政层级聚类（Cluster-robust SE）；
4. **输出标准回归结果**。

## 六、 方法选择逻辑
- 优先采用高维固定效应估计器（如 Python 的 `pyfixest` 或 Stata 的 `reghdfe`），以保证大规模面板数据的快速收敛与准确度；
- 根据数据生成过程自动调整模型分布族。

## 七、 诊断要求
- 检查是否存在因为单值变量被固定效应完全吸纳 (Absorbed) 的情况；
- 检查是否存在缺失值导致回归样本数急剧缩减的情况。

## 八、 输出结果
- 模型估计系数表、标准误、P 值与置信区间；
- 样本量 $N$、$R^2$ / Pseudo $R^2$、F 统计量与聚类信息。

## 九、 失败条件
- 存在完全共线性导致设计矩阵奇异不可逆；
- 核心变量由于高维固定效应被全额吸收。

## 十、 底层工具
- Python: `pyfixest`, `linearmodels`, `statsmodels`；
- Stata: `reghdfe`, `esttab`；
- R: `fixest`.

## 十一、 来源与许可证信息
- 来源：AERS 00.1~00.3 计量建模模块；
- 许可证：CC-BY-SA-4.0 License。

## 十二、 中文用户说明与防避坑指南
基准回归不仅给出系数与显著性，更重要的是规范了标准误的聚类层级与高维固定效应设定，避免因忽略标准误自相关而导致过度显著（False Positive）。
