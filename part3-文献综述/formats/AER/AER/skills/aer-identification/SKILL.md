---
name: aer-identification
description: Use when designing or defending the research design of an American Economic Review submission — the credibility bar is design-first: randomized or quasi-experimental variation, or an explicit structural model, with OLS-plus-controls treated as descriptive.
---

# 识别（aer-identification）

## AER 的识别门槛

- **设计优先**：引言与数据部分必须先讲清"什么变异识别了这个参数"，再谈估计。
- "OLS + 一堆控制"在 AER 语境下是**描述性**证据，不能单独承担因果主张。
- 三条主路：**实验 / 准实验**（DID、事件研究、IV、RDD、合成控制）、**结构模型**、或**极强的制度细节 + 多种设计交叉验证**。

## 写识别部分的标准顺序

1. **识别问题**：内生性从哪来（反向因果、遗漏变量、选择、测量误差），各会造成什么方向的偏误。
2. **变异来源**：政策/制度/自然实验的具体规则，为何对个体而言外生；给出时间线与资格条件。
3. **设计**：处理组/对照组定义、处理时点、估计方程、对照组选择（never-treated / not-yet-treated）。
4. **识别假设**：平行趋势 / 排除限制 / 连续性 / SUTVA，逐条说清**为何成立**，并给出可检验的含义。
5. **威胁与应对**：预期效应、溢出、构成变化、选择性进入/退出、同期其他政策——逐条给出检验或论证。

## 常见退稿点

| 问题 | 应对 |
|------|------|
| 交错处理仍用裸 TWFE | 换 Callaway–Sant'Anna / Sun–Abraham / 堆叠 DID；报告 ATT(g,t) 与聚合权重 |
| 对照组被处理污染 | 明确 never-treated，或做剔除/再定义 |
| IV 排除限制靠讲道理 | 给制度理由 + 过度识别检验 + 弱工具稳健推断 + 单调性讨论 |
| 预期效应未处理 | 事件研究前置期检验 + 剔除临近期 |
| 溢出/一般均衡 | 定义暴露口径，或明确说明估计的是 reduced-form 局部效应 |

## 与中文刊包的分工

`er-identification` / `mw-identification` / `cie-did-identification` / `jfr-identification` / `ceq-identification` 提供具体的 Stata/Python 实现与国内审稿口径；本 skill 只规定**英文稿该把哪部分讲在前面、讲多细**——AER 的识别部分通常比中文刊更长、更偏"为什么可信"，而不是罗列稳健性。
