---
name: mechanism
name_zh: 因果机制诊断组件
description: 评估因果传导机制，区分相关性中介证据与真正的因果机制，排除替代传导解释。
category: 05_further-analysis
priority: medium
inputs: [基准模型, 机制中介变量, 替代机制变量]
outputs: [机制检验回归结果, 机制证据强度评级, 替代解释排除说明]
dependencies: [baseline-regression]
source_repository: AER-Skills
source_path: skills/aer-robustness/
original_skill_name: aer-robustness
license: MIT
adaptation_status: adapted
---

# 因果机制诊断组件 (Mechanism Analysis)

## 一、 这个 Skill 是干什么的
`mechanism` 负责检验核心政策冲击影响被解释变量的**经济学传导机制 (Transmission Mechanisms)**。它超越传统的简单中介效应，区分“相关性中介证据”与“真正的因果机制”，强调排除竞争性/替代性传导渠道 (Alternative Mechanisms)。

## 二、 什么时候使用
- 当基准因果效应确立，需要论证“政策究竟通过什么渠道产生作用”时。

## 三、 规则与硬性禁忌
- **严禁滥用简单中介三步法**：绝对禁止将传统 Baron-Kenny / 温忠麟中介三步法中“中介变量显著”直接等同于“因果机制得到完美证明”！因为中介变量本身往往是内生的（存在遗漏变量或反向因果）；
- **强调机制识别**：优先采用：1) 机制变量外生冲击法；2) Gelbach (2016) 序贯条件分解；3) 排除法（证明竞争性机制不成立）。

## 四、 执行与诊断流程
1. **提出机制假设链条**：定义政策 $D \to$ 机制变量 $M \to$ 被解释变量 $Y$；
2. **机制相关性检验**：检验政策 $D$ 是否显著改变机制变量 $M$；
3. **竞争性机制排除 (Ruling out alternative explanations)**：
   - 纳入潜在的竞争性机制变量 $M_{alt}$；
   - 证明政策 $D$ 对 $M_{alt}$ 无显著影响，或控制 $M_{alt}$ 后主机制 $M$ 依然稳健；
4. **机制证据强度评级**：
   - **强证据**：机制变量本身有外生变异或被成功分解；
   - **中等证据**：中介变量显著且排除了主要替代解释；
   - **弱证据**：仅存在 $D \to M$ 的相关性，无法排除 $M$ 的内生性。

## 五、 输出与要求
- 机制回归检验表；
- 机制传导链条示意图；
- 竞争性替代解释排除说明。

## 六、 底层工具
- Python: `statsmodels`；
- Stata: `gelbach` (`b1o2`), `medeff`；
- R: `mediation`, `sensemakr`.

## 七、 来源与许可证信息
- 来源：AER-Skills (`aer-robustness`)；
- 许可证：MIT License。
