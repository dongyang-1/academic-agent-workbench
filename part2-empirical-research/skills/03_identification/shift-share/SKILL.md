---
name: shift-share
name_zh: Bartik/份额移动IV
description: Bartik / Shift-Share 工具变量法，区分份额外生 (Shares Exogeneity) 与冲击外生 (Shocks Exogeneity) 识别假定并执行诊断。
category: 03_identification
priority: medium
inputs: [截面/面板数据集, 份额数据(Shares), 全国/总体冲击数据(Shocks), 被解释变量]
outputs: [Bartik工具变量值, 2SLS估计系数, Rotemberg权重分析, 冲击层级聚类标准误]
dependencies: [identification-strategy]
source_repository: AER-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: MIT
adaptation_status: adapted
---

# Bartik / 份额移动 IV (Shift-Share IV)

## 一、 这个 Skill 是干什么的
`shift-share` 专门用于构建和评估 Bartik / Shift-Share 工具变量。它将地区初始产业/人口份额（Shares）与全国性总趋势冲击（Shocks）结合构造成工具变量。它遵循现代 Shift-Share 计量文献，显式区分**份额外生 (Shares Exogeneity)** 与 **冲击外生 (Shocks Exogeneity)** 两类互不交叠的识别假设，并实施对应推断。

## 二、 什么时候使用
- 当需要估计全国/宏观外生冲击对局部地区（如城市、县域、行业）的因果效应，且各地初始结构不同时。

## 三、 什么时候不要使用
- 当初始份额 $w_{ik}$ 与冲击 $g_k$ 均强相关于局部地区遗漏的动态趋势时。

## 四、 需要什么输入
1. 地区面板/截面数据集；
2. 初始基期份额向量 $w_{ik0}$（加总为 1）；
3. 聚合层级总体冲击 $g_{kt}$；
4. 地区层级被解释变量 $Y_{it}$ 与局部内生变量 $X_{it}$。

## 五、 两类识别假设与诊断流程

```text
 ┌──────────────────────┬────────────────────────────────────────────────────────┐
 │ 识别假设方向         │ 理论代表与对应诊断方法                                 │
 ├──────────────────────┼────────────────────────────────────────────────────────┤
 │ 1. 份额外生          │ Goldsmith-Pinkham, Sorkin & Swift (2020)               │
 │ (Shares Exogeneity)  │ ──► 计算 Rotemberg 权重，找出起决定性作用的主导行业；  │
 │                      │ ──► 检验主导行业初始特征对预前期趋势的控制。           │
 ├──────────────────────┼────────────────────────────────────────────────────────┤
 │ 2. 冲击外生          │ Borusyak, Hull & Jaravel (2022) / Adão et al. (2019)   │
 │ (Shocks Exogeneity)  │ ──► 转化为冲击层级 (Shock-level) 回归估计；            │
 │                      │ ──► 标准误必须在 【冲击/行业层级】 聚类，避免伪显著。  │
 └──────────────────────┴────────────────────────────────────────────────────────┘
```

## 六、 规范与禁忌
- **明确选择假设**：研究者必须显式声明论文依靠“份额外生”还是“冲击外生”，不能含糊其辞；
- **标准误修正**：必须采用 Adão, Kolesár & Morales (2019) 或 Borusyak et al. (2022) 的 Shift-Share 专用聚类标准误，常规地区聚类标准误会严重向下偏误。

## 七、 诊断要求
- 报告 Rotemberg 权重 Top-5 行业的分布情况；
- 报告基于冲击层级转换后的第一阶段 F 统计量与标准误。

## 八、 输出结果
- Bartik IV 2SLS 估计系数与修正后的 Shift-Share 标准误；
- Rotemberg 权重分解表。

## 九、 失败条件
- Rotemberg 权重高度集中于单个不可信的传统行业；
- 冲击变量与初始份额均存在明显的自相关遗漏趋势。

## 十、 底层工具
- Stata: `ssaggregate`, `rotemberg_weights`；
- R: `ShiftShareSE`；
- Python: 自研转换估计脚本。

## 十一、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`)；
- 许可证：MIT License。

## 十二、 中文用户说明与防避坑指南
Bartik 工具变量在劳动经济学和城市经济学中极受欢迎，但近年来审稿人最常问：“你的识别到底靠份额外生还是冲击外生？”本 Skill 会自动计算 Rotemberg 权重并进行冲击层级标准误修正，避免因标准误未调整而导致虚假显著。
