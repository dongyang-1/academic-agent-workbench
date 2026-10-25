---
name: did
name_zh: 基础双向固定效应DID
description: 标准 2×2 DID 与单一时点处理下的双向固定效应 (TWFE) 回归。检测到错位处理必须转交 staggered-did。
category: 03_identification
priority: high
inputs: [面板数据集, 被解释变量, 处理变量, 个体ID, 时间ID, 控制变量]
outputs: [DID回归系数, 平行趋势检验结果, 动态效应图]
dependencies: [identification-strategy]
source_repository: Auto-Empirical-Research-Skills
source_path: skills/10-Jill0099-causal-inference-mixtape/
original_skill_name: causal-inference-mixtape
license: CC-BY-SA-4.0
adaptation_status: adapted
---

# 基础双向固定效应 DID (Basic DiD)

## 一、 这个 Skill 是干什么的
`did` 负责实现标准的双重差分法 (Difference-in-Differences)。它适用于**所有受处理个体在同一个时间点统一接受处理**的经典 2×2 DID 设计或单一时点 TWFE 模型。它提供平行趋势检验和简单事件研究设定。

## 二、 什么时候使用
- 当政策或事件在单一统一时间点（Single Treatment Timing）对处理组实施时；
- 当存在明确未受处理的对照组 (Never-treated controls) 时。

## 三、 什么时候不要使用
- 严禁在政策分批错位实施 (Staggered Rollout) 的情况下使用本技能作为唯一核心因果结果，此时必须交由 `staggered-did` 技能处理。

## 四、 需要什么输入
1. 面板数据集；
2. 被解释变量 $Y$；
3. 处理组标识 `treat` 与处理后时间标识 `post`（或两者乘义项 `treat * post`）；
4. 个体与时间固定效应变量。

## 五、 执行流程
1. **统一时点校验**：确认受处理单位的处理开始时间 $T_0$ 是否唯一；
2. **基准回归设定**：
   $$Y_{it} = \alpha_i + \lambda_t + \beta (Treat_i \times Post_t) + \gamma X_{it} + \varepsilon_{it}$$
3. **平行趋势检验**：设置处理前若干期的 Dummy 交互项进行 Granger 检验与可视化绘制。

## 六、 方法选择逻辑
- 仅当处理时点单一、个体同质且控制组稳定时，TWFE 估计量才是无偏的；
- 否则，TWFE 存在负加权偏误，必须转向现代 DID 估计量。

## 七、 诊断要求
- 检验处理前各期系数的 Joint p-value 是否显著异于 0；
- 检查是否存在特定个体对全局估计结果的过度杠杆拉动。

## 八、 输出结果
- 2×2 DID 回归估计表与估计系数 $\hat{\beta}$；
- 经典事件研究 (Event Study) 动态系数图。

## 九、 失败条件
- 处理前显著偏离平行趋势假定；
- 找不到未受处理的对照组。

## 十、 底层工具
- Python: `pyfixest.feols`, `statsmodels`；
- Stata: `reghdfe`, `esttab`；
- R: `fixest::feols`.

## 十一、 来源与许可证信息
- 来源：AERS / Causal Inference Mixtape；
- 许可证：CC-BY-SA-4.0 License。

## 十二、 中文用户说明与防避坑指南
标准 2×2 DID 是因果推断的基础，但前提是所有处理组在同一时间受政策影响。如果是“不同城市在不同年份试点”，切勿直接使用本 Skill，而应使用 `staggered-did`。
