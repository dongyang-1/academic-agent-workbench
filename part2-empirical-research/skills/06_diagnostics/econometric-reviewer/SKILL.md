---
name: econometric-reviewer
name_zh: 计量审稿人综合审查器
description: 以顶级期刊审稿人视角评估结果，输出 🟢/🟡/🔴 判定；判定 🔴 时向 Router 写入 rejected_strategies 触发重新路由。
category: 06_diagnostics
priority: critical
inputs: [基准回归结果, 识别假定诊断, 稳健性矩阵, 当前主识别策略 (primary_strategy)]
outputs: [审稿人综合评审报告, 风险等级判定 (🟢/🟡/🔴), 被否决策略名称 (rejected_strategy), 否决原因 (rejection_reason)]
dependencies: [robustness-router]
source_repository: Self-developed / AER-Skills
source_path: skills/aer-referee-sim/
original_skill_name: aer-referee-sim
license: MIT
adaptation_status: self-developed
---

# 计量审稿人综合审查器 (Econometric Reviewer)

## 一、 这个 Skill 是干什么的
`econometric-reviewer` 是本智能体系统的核心创新防线。它扮演 *American Economic Review* (AER) 等顶级期刊的匿名审稿人，审查实证结论。它具备 **🟢 (可信)、🟡 (存疑但可补充)、🔴 (致命因果缺陷)** 的判定能力。当给出 🔴 判定时，它将当前识别策略打包写入 `rejected_strategy` 并附带否决原因，交给 Router 触发打回。

## 二、 审查动作与打回接口契约
1. 🟢 **可信 (Green Light)**：
   - 动作：批准生成出版级实证报告与标准 LaTeX 表格。
2. 🟡 **存疑但可补充 (Yellow Light)**：
   - 动作：调用 `sensitivity-bounds` (HonestDiD)，计算崩溃点并产出敏感性补救路线图。
3. 🔴 **致命因果识别缺陷 (Red Light - 触发拦截打回)**：
   - 条件：平行趋势检验失败 ($p < 0.05$)、弱工具变量无法克服 (AR 置信区间包含 0 且无边界)、RDD 密度与协变量双重突变；
   - 动作：输出 `decision_level: "RED"`，并填入打回契约字段：

```json
{
  "decision_level": "RED",
  "rejected_strategy": "staggered-did",
  "rejection_reason": "处理前第 2、3 期事件研究系数显著异于 0 (p=0.012)，平行趋势假定未通过",
  "action": "TRIGGER_REROUTING"
}
```

## 三、 输出结果
- 审稿人综合评审报告；
- 结构化决策字典（包含 `decision_level`, `rejected_strategy`, `rejection_reason`）。

## 四、 来源与许可证信息
- 来源：自研 / AER Referee Simulator；
- 许可证：MIT License。
