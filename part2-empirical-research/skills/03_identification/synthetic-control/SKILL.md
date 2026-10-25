---
name: synthetic-control
name_zh: 合成控制与SDID
description: 合成控制法 (SCM) 与 Synthetic DID，用于处理少数受体/单一地区的政策评估与安慰剂推断。
category: 03_identification
priority: medium
inputs: [面板数据集, 被解释变量, 受处理单位名称, 处理发生时间, 控制池(Donor Pool)]
outputs: [合成权重向量, 处理组与合成对照组路径对比图, 拟合残差, 安慰剂推断分布]
dependencies: [identification-strategy]
source_repository: AER-Skills / CausalPy
source_path: docs/methods-reference.md
original_skill_name: aer-identification
license: Apache-2.0 / MIT
adaptation_status: adapted
---

# 合成控制法与 Synthetic DID (SCM & SDID)

## 一、 这个 Skill 是干什么的
`synthetic-control` 专门用于解决受处理单位极少（如单一省份、城市或国家）的政策效应评估问题。它通过控制池 (Donor Pool) 中未受处理单位的线性组合构建“合成对照组”(Synthetic Counterfactual)。同时包含 Synthetic DID (Arkhangelsky et al. 2021)，通过双重加权提升平行趋势与截距拟合的稳健性。

## 二、 什么时候使用
- 当处理组个体仅有 1 个或极少数几个；
- 拥有较长且高质量的处理前时期 (Pre-treatment periods) 时。

## 三、 什么时候不要使用
- 当处理前时期极短（少于 4-5 个时间节点）；
- 当控制池中的单位受到与其他政策交叉感染时。

## 四、 需要什么输入
1. 宏观/微观面板数据集；
2. 被解释变量 $Y_{it}$；
3. 受处理个体 ID 与处理发生时间 $T_0$；
4. 供合成的控制池 (Donor Pool) 样本列表。

## 五、 执行与推断流程
1. **控制池构建**：排除受到政策外溢效应或相似政策冲击的样本；
2. **权重优化 (Weight Optimization)**：最小化处理前 $Y$ 及预测变量的均方预测误差 (MSPE)；
3. **Synthetic DID (可选扩展)**：引入个体与时间双重加权，降低对拟合度的极度敏感；
4. **安慰剂检验推断 (Placebo Inference)**：
   - 空间安慰剂 (In-space Placebo)：将控制池中的单位轮流作为假处理组；
   - 评估处理后差距与处理前差距之比 (Post-MSPE / Pre-MSPE ratio)。

## 六、 规范与警告
- **视觉拟合不等于推断**：严禁仅凭借处理前拟合良好的曲线图就直接断言效应显著，必须报告 Placebo 推断的 $p$ 值分布；
- **预处理拟合较差警示**：若处理前 MSPE 过大，提示合成失败风险。

## 七、 诊断要求
- 报告各控制单位的权重分配向量 $W$（检查是否存在单一控制组权重超过 90%）；
- 报告 Post/Pre-MSPE 比值分布与置信区间。

## 八、 输出结果
- 合成权重表与预测变量平衡表；
- 真实处理组与合成对照组路径对比图 (SCM Path Plot)；
- 安慰剂检验排列分布图。

## 九、 失败条件
- 处理前时期太短导致严重过拟合；
- 处理前拟合极其糟糕 (Pre-MSPE 异常高)。

## 十、 底层工具
- Python: `CausalPy`, `scikit-learn`；
- Stata: `synth`, `synth_runner`, `sdid`；
- R: `Synth`, `synthdid`.

## 十一、 来源与许可证信息
- 来源：AER-Skills (`methods-reference.md`) / CausalPy；
- 许可证：Apache-2.0 / MIT License。

## 十二、 中文用户说明与防避坑指南
合成控制法常用于评估宏观政策（如某省设立自贸区）。本 Skill 不仅帮你算出合成权重，还会自动对控制池里的所有地区做排列组合安慰剂检验，用严格的统计推断验证效果是否真实存在。
