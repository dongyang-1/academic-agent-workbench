---
name: aer-tables-figures
description: Use when preparing exhibits for an American Economic Review submission — figures carry the design, tables carry the estimates, both must be publication-quality and LaTeX-ready.
---

# 图表（aer-tables-figures）

## 总体原则

- **图负责说服，表负责记录**。事件研究图、bin-scatter、系数图常比回归表更能传达识别价值。
- AER 中图表称 **exhibits**（Figure / Table 统一编号），正文按出现顺序引用。
- 提交阶段接受 PDF；**接受后须按 Chicago Manual of Style + AER Style Guide** 排版，建议早期就用 AEA LaTeX 模板写作，避免返工。

## 图

- 事件研究图：横轴相对期数，纵轴效应，标注基期、置信区间（建议 95%）、处理起始竖线；前置期系数用于支撑平行趋势。
- bin-scatter：分箱散点 + 拟合线，控制协变量后残差化；标出箱数与样本量。
- 黑白可辨：避免只靠颜色区分序列；线型/标记点并用。
- 坐标轴标签自解释，图注写明样本、控制、聚类与置信水平。

## 表

- 每列一列规格，逐列叠加控制与固定效应；**底部固定写明**：观测数、R²、固定效应、聚类维度。
- 标准误置于系数下方括号内；不要在同一张表混用不同标准误而不标注。
- 主表放正文，稳健性/附加规格进 **Supplemental Appendix**（单独 PDF，标题以 "Supplemental Appendix" 开头）。
- 变量含义写入 notes，不依赖正文回忆。

## 复现一致性

- 表中每个数字必须能由提交的代码与数据**逐字复现**（见 `aer-data-availability`）。
- 不要在正文与附录给出同一规格的不同数值；若口径不同，明确标注区别。

## 自检

```
[ ] 每张图表都在正文按顺序引用
[ ] 图注含样本/规格/置信水平
[ ] 表底含 N、固定效应、聚类
[ ] 黑白打印仍可区分
[ ] 正文数字与输出文件逐项对账
```
