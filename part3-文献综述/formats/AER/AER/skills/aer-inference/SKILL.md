---
name: aer-inference
description: Use when setting the inference standard for an American Economic Review submission — clustering justification, weak-instrument-robust inference, multiple-testing correction, and randomization inference.
---

# 推断与稳健性（aer-inference）

## AER 的默认期待

"报告稳健标准误"不够。审稿人会追问**为什么这么聚类、有多少 cluster、多重比较是否校正、弱工具是否用了稳健推断**。

## 聚类

- 说明聚类维度与**理由**：assignment 层面（处理分配在哪一级）优先；否则按误差相关结构。
- cluster 数少（< ~40）时：报告 wild cluster bootstrap p 值，或用有效样本/随机化推断，不要只报渐近 SE。
- 多维度相关（如 × 行业 × 年份）：用双重聚类或说明主导维度。

## 多重检验

- 多个结局 / 多个子样本时，预先声明**主结局**或做多重检验校正（FDR / Bonferroni / 预先设定的 family）。
- 异质性分析若未预注册，明确定位为**探索性**，不要用强因果语言。

## 弱工具与 IV

- 一阶段 F 之外，报告 **AR / CLR** 等弱工具稳健置信集（F > 10 的经验规则不足以应对现代审稿）。
- 讨论**单调性与 LATE 的人群**：估计的是 compliers 的效应，外推须论证。
- 有过度识别时报告 Hansen J 并解释。

## 其他常用口径

- 随机化/置换推断：当设计清楚、样本小或 cluster 少时，是最有说服力的 p 值。
- 预分析计划（实验）：提交时附上，或说明无 PAP 的原因。
- 报告**效应量的经济含义**（标准化、与均值/标准差比较、与政策成本比较），不要只报星号。

## 自检

```
[ ] 聚类维度与理由写明
[ ] 少 cluster 时有 wild bootstrap / 随机化推断
[ ] 多结局处理有主结局或 FDR
[ ] IV 有弱工具稳健推断
[ ] 探索性分析与主结果分开表述
[ ] 效应量有经济含义解释
```
