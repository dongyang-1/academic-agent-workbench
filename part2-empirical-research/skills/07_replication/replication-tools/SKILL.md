---
name: replication-tools
name_zh: 实证复现与差异比对工具
description: 自动化提取论文表格数字、比对当前复现回归结果，定位数值与标准误差异及来源。
category: 07_replication
priority: medium
inputs: [既有论文表格数据, 复现数据与代码]
outputs: [复现差异对比表, 偏误比例, 差异来源诊断报告]
dependencies: [baseline-regression]
source_repository: Self-developed / AER-Skills
source_path: skills/aer-replication/
original_skill_name: aer-replication
license: MIT
adaptation_status: self-developed
---

# 实证复现与差异比对工具 (Replication & Difference Diagnosis)

## 一、 这个 Skill 是干什么的
`replication-tools` 专门用于对已发表论文的复现数据包 (Replication Package) 进行验证。它能自动提取原论文表格数字，与当前基于同一数据运行的代码结果进行精准对比，定位估算系数、标准误、样本量 $N$ 及 $R^2$ 的百分比差异，并分析差异产生的原因（如 Stata 与 Python 固定效应算法差异、缩尾处理差异或样本筛选差异）。

## 二、 什么时候使用
- 当研究者尝试复现某篇顶级期刊论文，或进行文献基准对标时。

## 三、 什么时候不要使用
- 当缺乏原论文的明确表格数值与代码逻辑时。

## 四、 执行与比对流程
1. **数值对标提取**：提取目标论文表格中的关键系数 $\hat{\beta}_{paper}$ 与标准误 $SE_{paper}$；
2. **复现估计运行**：运行本地复现代码得到 $\hat{\beta}_{local}$ 与 $SE_{local}$；
3. **计算差异百分比**：
   $$\text{Diff \%} = \frac{|\hat{\beta}_{local} - \hat{\beta}_{paper}|}{|\hat{\beta}_{paper}|} \times 100\%$$
4. **差异来源定位**：
   - 检查样本量 $N$ 是否完全匹配（判别样本筛选偏误）；
   - 检查固定效应吸收维度是否一致；
   - 检查标准误聚类层级（常规 vs 聚类 SE）。

## 五、 输出结果
- 复现比对矩阵表（原论文 vs 复现值 vs 差异 %）；
- 差异定位诊断结论（Perfect Match / Minor Tolerance / Unreplicable）。

## 六、 底层工具
- Python: `pandas`, `numpy` 比对模块；
- Stata: AEA Replication Checklist 标准。

## 七、 来源与许可证信息
- 来源：自研 / AER Replication 合规模块；
- 许可证：MIT License。
