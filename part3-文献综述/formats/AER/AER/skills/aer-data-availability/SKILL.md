---
name: aer-data-availability
description: Use when assembling the replication package for an American Economic Review submission — data, code, README, and the signed Data and Code Availability Form required for conditionally accepted empirical, simulation, or experimental papers.
---

# 数据与代码可得性（aer-data-availability）

## 政策要点

- AEA 的政策是：**只发表那些数据被清晰、精确记录且可被任何研究者用于复现的论文**。
- 含**实证、模拟或实验**的稿件，在**有条件接受后**必须提交足以复现的数据、代码与计算细节，存放于**公开可信仓储**（AEA Data and Code Repository / openICPSR）。
- 归档须含 **README**：列出全部文件、说明每个文件的用途/格式/来源，并给出复现步骤。
- 须提交签字的 **Data and Code Availability Form** 与 **Data and Code Archive Agreement**。
- 数据专有或受限时，**投稿时**即通知主编并说明；不要到接受阶段才提出。
- 实验类论文另需更细材料：原始说明、受试者筛选规则、程序与配置、原始数据。

## 复现包结构（建议）

```
replication/
  README.md          # 文件清单 + 逐步复现指令 + 运行环境
  code/
    00_master.do|.py # 一键跑通全部结果
    01_clean.do
    02_analysis.do
    03_figures.do
  data/
    raw/             # 原始（若可公开）
    derived/         # 分析用
  output/
    tables/ figures/
```

## README 必须包含

1. 每个文件一句话说明与来源（供应商、许可、下载日期）。
2. 运行环境（Stata/Python/R 版本、依赖包）。
3. 从原始数据到正文每一张表的**逐表对应指令**。
4. 不能公开的数据：获取途径与限制条件。

## 提交前自检

```
[ ] 00_master 能一次性跑出正文全部数字
[ ] 正文每个数字都能在 output/ 找到出处
[ ] README 含文件清单、来源、复现步骤
[ ] 专有数据已在投稿时说明
[ ] 表单已签字（接受阶段）
```
