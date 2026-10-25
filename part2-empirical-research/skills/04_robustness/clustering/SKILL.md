---
name: clustering
name_zh: 聚类层级与Wild Bootstrap
description: 标准误聚类层级选择 (Clustering SE) 与少数 Cluster 场景下的 Wild Cluster Bootstrap 修正。
category: 04_robustness
priority: medium
inputs: [基准模型, 候选聚类变量, Cluster 数量]
outputs: [不同聚类层级下的标准误比对表, Wild Cluster Bootstrap p值]
dependencies: [baseline-regression]
source_repository: AER-Skills / Auto-Empirical-Research-Skills
source_path: docs/methods-reference.md
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 聚类层级与 Wild Bootstrap (Clustering & Wild Bootstrap)

## 一、 这个 Skill 是干什么的
`clustering` 负责审查和校正计量回归中的标准误聚类层级 (Cluster-robust Standard Errors)。当标准误存在空间/行业层级相关性或聚类单位数量极少 (Few Clusters, $G < 30$) 时，传统聚类标准误会导致严重向下偏误（过度拒绝原假设）。本技能自动执行 **Wild Cluster Bootstrap** 修正（Cameron, Gelbach & Miller 2008）。

## 二、 什么时候使用
- 当处理变量在更高行政/行业层级分配（如省份层级政策）；
- 当聚类单位数量 $G < 30-50$ 时。

## 三、 什么时候不要使用
- 当观察值之间完全独立且同分布（极少见）。

## 四、 执行与诊断流程
1. **聚类层级判定**：聚类层级应不低于政策赋值发生的层级（Policy Assignment Level）；
2. **Cluster 数量诊断**：
   - 若 $G \ge 50$ ──► 传统 Cluster-robust SE 可靠；
   - 若 $G < 30$ ──► 传统聚类标准误失效，强制激活 **Wild Cluster Bootstrap**；
3. **Wild Bootstrap 抽样拟合**：采用 Rademacher 或 Webb 权重分布计算重抽样 $p$ 值。

## 五、 输出与要求
- 输出不同聚类层级下（个体、城市、省份、双向聚类）标准误与 $t$ 值的敏感性表；
- 输出少数 Cluster 下的 Wild Bootstrap p 值。

## 六、 底层工具
- Python: `wildboottest` / `pyfixest`；
- Stata: `boottest`；
- R: `fwildclusterboot`.

## 七、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`)；
- 许可证：MIT License。
