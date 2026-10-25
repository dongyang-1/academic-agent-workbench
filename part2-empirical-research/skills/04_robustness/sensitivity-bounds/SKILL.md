---
name: sensitivity-bounds
name_zh: 平行趋势敏感性边界分析 (HonestDiD)
description: 当平行趋势假设出现偏离时，基于 Rambachan-Roth (2023) 框架计算相对幅度/光滑性敏感性边界，提供补救路线图。
category: 04_robustness
priority: medium
inputs: [事件研究估计系数向量, 协方差矩阵, 敏感性参数 M/Mbar]
outputs: [HonestDiD 敏感性分解边界, 击穿原假说的临界 M* 值, 补救路线图报告]
dependencies: [staggered-did, baseline-regression]
source_repository: AER-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 平行趋势敏感性边界分析 (HonestDiD Sensitivity Bounds)

## 一、 这个 Skill 是干什么的
`sensitivity-bounds` 专门用于解决 DID / Staggered DID 分析中**预前期趋势检验未完全通过（或存在轻微漂移）时的补救与敏感性分析问题**。它基于 Rambachan & Roth (2023) 的 *HonestDiD* 理论框架，放弃“平行趋势必须绝对为 0”的僵化假定，允许处理后趋势偏离程度约束在预前期偏离程度的 $M$ 倍以内（Relative Magnitudes 或 Smoothness Bounds），计算处理效应保持显著的临界 $M^*$ 值。

## 二、 什么时候使用
- 当 `econometric-reviewer` 对 DID 诊断输出 🟡 (存疑) 或 🔴 (前趋势轻微偏离) 时；
- 需要评估“处理后效应在多大程度的平行趋势违反下依然成立”时。

## 三、 核心理论与计算框架 (Rambachan & Roth 2023)
假设处理前趋势的最大违反对称幅度为 $\Delta^{RM}(\bar{M})$，其中 $\bar{M}$ 表示处理后违反程度相对于处理前最大违反程度的倍数：

```text
 1. 相对幅度限制 (Relative Magnitudes):
    限制处理后各期偏离平行趋势的幅度不超过处理前最大偏离的 Mbar 倍。

 2. 崩溃点计算 (Breakdown Value M*):
    不断增大 Mbar，直到 95% 置信区间包含 0。
    - 若 M* > 1：说明即使处理后违反趋势是处理前的 1 倍以上，结论依然稳健 (🟢 补救成功)；
    - 若 M* < 0.5：说明结论对平行趋势违反极度敏感 (🔴 确实无法救回)。
```

## 四、 执行流程
1. **提取估计量与协方差**：从 `staggered-did` 或基准事件研究导出向量 $\hat{\beta}$ 与方差-协方差矩阵 $\hat{\Sigma}$；
2. **设定 Mbar 遍历范围**：如 $M \in [0, 2.0]$，步长 0.1；
3. **计算各 Mbar 下的 HonestDiD 边界**；
4. **生成“补救路线图”**：给出论文中如何向审稿人解释该敏感性边界的标准化段落。

## 五、 输出与要求
- HonestDiD 敏感性边界图（$Mbar$ vs 置信区间）；
- 崩溃点临界值 $M^*$；
- 论文补救解释文本。

## 六、 底层工具
- R: `HonestDiD` 包；
- Stata: `honestdid`；
- Python: 将 $\hat{\beta}$ 和 $\hat{\Sigma}$ 导出至 R 执行并返回结果。

## 七、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / Rambachan & Roth (2023)；
- 许可证：MIT License。

## 八、 中文用户说明与防避坑指南
以前只要平行趋势 $p < 0.05$，论文往往就被死刑枪毙。有了 `sensitivity-bounds` (HonestDiD)，你可以计算：“即使处理后趋势违反程度是处理前的 1.5 倍，我们的因果结论依然显著。”这是目前 Top-5 期刊处理预趋势瑕疵最前沿的标准补救手段。
