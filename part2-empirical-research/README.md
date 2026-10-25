# 经济学/社科实证分析智能体 (Empirical Research Agent)

> **核心理念**：本项目的目标不是让 AI 更快地写出一条回归命令，而是让 AI 在写回归命令之前，先做一个经济学研究者应该做的判断；在生成结果之后，像顶级期刊审稿人一样进行严谨诊断与评价。

---

## 一、 项目定位与三大突破

`Empirical Research Agent` 是一个专门面向经济学与社会科学研究的实证分析专用智能体，聚焦于**识别驱动的因果推断、计量模型诊断与结果审慎评估**。相比传统的代码生成器，本项目实现了三大突破：

1. **判断优先于执行**：AI 不盲目套用回归，而是先审计数据结构（面板/截面、处理变量时序分布、断点、高维特征），明确识别假设后在 **11 大因果估计器**中选择最匹配的设计。
2. **拒绝机械规则**：
   - 工具变量：废除 `F < 10` 机械规则，结合 Conventional F、Effective F (Montiel Olea-Pflueger) 与 Anderson-Rubin 置信区间。
   - 断点回归：McCrary 密度检验异常不判死刑，而是结合制度背景与协变量连续性综合研判。
   - 共线性防范：排查完全共线/冗余变量，但保留模型必需的原始变量与二次项/交互项。
3. **审稿人闭环拦截与打回自适应重选 (Anti-Loop Rerouting)**：当检验发现识别假定受挫（如错位 DID 前期平行趋势显著偏离），自动给出 🔴 判定并打回 Router 自动排除已被否决的策略，自适应降级重新路由或产出敏感性边界补救路线图 (HonestDiD)。

---

## 二、 四层架构体系 (L0 / L1 / L2 / L3 · 共 28 个技能)

系统将 28 个技能划分为清晰的四层架构：

* **L0：数据准备/政策爬虫/文本挖掘层 (3个技能)**
  - 🌐 `data-acquisition` (联网开源数据采集与面板构建：宏观 GDP/CPI、上市公司财务面板、World Bank 跨国面板、NBS 省际面板)
  - 🏛️ `policy-pilot-crawler` (政策试点名单与事件时序爬虫：低碳城市、智慧城市、碳交易ETS等多期冲击注入，自动生成 DID / Staggered DID 因果变量)
  - 📖 `annual-report-text-miner` (上市公司年报文本与词频挖掘爬虫：基于吴非等顶刊词库构建数字化转型、绿色创新、管理层短视等前沿非结构化实证指标)
* **L1：核心决策层 (6个大脑技能)**
  - `empirical-router` (全局中枢与防死循环状态机)
  - `data-audit` (数据结构审计，覆盖 11 大识别方法信号)
  - `identification-strategy` (因果识别策略选择器，11 大策略优先级匹配)
  - `baseline-regression` (基准回归估计器)
  - `robustness-router` (稳健性检验路由器)
  - `econometric-reviewer` (审稿人综合审查器)
* **L2：计量方法层 (11个因果估计器)**
  - `did` (基础 2×2 / 齐期 DID)
  - `staggered-did` (多期错位 DID: CS / Sun-Abraham / Imputation)
  - `iv` (工具变量与 2SLS)
  - `rdd` (水平断点回归设计)
  - `synthetic-control` (合成控制与 SDID)
  - `matching` (倾向得分与精确匹配)
  - `shift-share` (Bartik 份额移动 IV)
  - 🌟 `double-machine-learning` (双重机器学习 DML)
  - 🌟 `bunching-design` (行为聚束分析设计)
  - 🌟 `regression-kink-design` (斜率断点回归 RKD)
  - 🌟 `local-projections` (局部投影法与 LP-DiD)
* **L3：工具/分析组件层 (8个分析模块)**
  - `placebo` (安慰剂检验)
  - `clustering` (聚类层级与 Wild Bootstrap)
  - `alternative-specification` (替代规格与 Oster $\delta$ 分析)
  - `heterogeneity` (分组异质性分析与组间检验)
  - `mechanism` (因果机制与替代解释)
  - `tables-and-figures` (出版级图表生成)
  - `replication-tools` (实证复现与比对)
  - `sensitivity-bounds` (HonestDiD 敏感性边界分析)

---

## 三、 快速开始与 Demo 运行

系统的核心 Demo 为“三幕剧”演练（测试题目：*某项政策是否提升了企业创新？*）：

```bash
# 进入测试目录并运行端到端“三幕剧”Demo
python3 empirical-research-agent/tests/end-to-end/demo_three_acts.py
```

---

## 四、 目录导航与开发日志

- 📑 [`CHANGELOG.md`](CHANGELOG.md) / [`开发日志.md`](开发日志.md): 项目演进与历史修改记录
- 📋 [`skills/skill-registry.yaml`](skills/skill-registry.yaml): 25 个技能元数据注册表
- 🗺️ [`docs/SKILL-MAP-ZH.md`](docs/SKILL-MAP-ZH.md): 中文技能映射与开源许可证说明
- 📘 [`docs/SKILL-MANUAL.md`](docs/SKILL-MANUAL.md): 25 个技能详细使用手册
- 📜 [`AGENTS.md`](AGENTS.md): 智能体交互与系统指令规范
- 📂 [`skills/`](skills/): 25 个标准 Skill 执行库
