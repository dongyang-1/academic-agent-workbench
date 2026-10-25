---
name: tables-and-figures
name_zh: 论文级表格与图表生成
description: 生成 AER/AEJ 顶刊规范的 Publication-ready LaTeX (booktabs) 与 Markdown 表格、事件研究图及系数图。
category: 08_output
priority: high
inputs: [回归模型对象列表, 统计量字典, 绘图数据]
outputs: [LaTeX booktabs 代码, Markdown 渲染表格, 出版级 High-res PNG/PDF 图表]
dependencies: []
source_repository: AER-Skills
source_path: skills/aer-tables-figures/
original_skill_name: aer-tables-figures
license: MIT
adaptation_status: adapted
---

# 论文级表格与图表生成 (Publication-Ready Tables & Figures)

## 一、 这个 Skill 是干什么的
`tables-and-figures` 负责将各种估计算法与诊断技能产生的数值结果，转化为符合顶级经济学期刊（AER, AEJ, QJE）排版规范的**出版级 LaTeX 表格 (LaTeX booktabs)**、**Markdown 表格**以及**矢量高清图表（事件研究图、动态效应图、系数对比图）**。

## 二、 什么时候使用
- 当实证分析完成，需要将估计与诊断结果呈现给研究者或插入论文正文时。

## 三、 规范与排版要求
1. **LaTeX 表格规范**：
   - 必须使用 `booktabs` 宏包（使用 `\toprule`, `\midrule`, `\bottomrule`），严禁出现竖线（Vertical lines）；
   - 标注显式显著性星号（`* p<0.10, ** p<0.05, *** p<0.01`）；
   - 必须包含标准底部面板：样本量 $N$、$R^2$、个体固定效应、时间固定效应、聚类标准误层级说明；
2. **图表绘制规范**：
   - 事件研究图必须包含 95% 置信区间条与 $t=0$ 政策基准线；
   - 字体与配色对齐学术出刊标准（如 Arial / Times New Roman, 简洁深色调，避免花哨调色）。

## 四、 输出表格类型
- **Table 1**：描述性统计与组间均值差异检验表；
- **Table 2**：基准因果回归表格（多规格逐步加入 FE 与控制变量）；
- **Table 3**：稳健性检验矩阵表格；
- **Table 4**：异质性与机制分析表格；
- **Figure 1-N**：事件研究动态效应图 (Event Study Plot) / 安慰剂分布图 / 敏感性边界图。

## 五、 底层工具
- Python: `matplotlib` (seaborn-v0_8-whitegrid), `pyfixest` 格式导出；
- Stata: `esttab`, `coefplot`；
- R: `fixest::iplot`, `ggplot2`.

## 六、 来源与许可证信息
- 来源：AER-Skills (`aer-tables-figures`)；
- 许可证：MIT License。
