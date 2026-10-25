---
name: empirical-router
name_zh: 实证分析全局路由
description: 控制全局状态机闭环、维护 rejected_strategies 否决历史，编排 L1/L2/L3 技能调用与降级重新路由。
category: 00_router
priority: critical
inputs: [研究问题描述, 原始数据集, 用户提示词/计划书]
outputs: [数据审计报告, 识别设计方案, 计量估计结果, 审稿人诊断意见, 出版级表格图表]
dependencies: [data-audit, identification-strategy, baseline-regression, robustness-router, econometric-reviewer]
source_repository: Self-developed / AER-Skills
source_path: skills/aer-workflow/
original_skill_name: aer-workflow
license: MIT
adaptation_status: self-developed
---

# 实证分析全局路由 (Empirical Router)

## 一、 这个 Skill 是干什么的
`empirical-router` 是整个实证分析智能体的大脑与总控中枢。它维护全局状态机，管理任务在“数据审计 → 识别设计 → 模型估计 → 诊断与稳健性 → 审稿人审查”之间的流转。当 `econometric-reviewer` 给出 🔴 判定时，Router 负责记录 `rejected_strategies` 数组与否决原因，打回 `identification-strategy` 执行**非重复的降级/替代策略重新路由**。

## 二、 什么时候使用
- 当接收到新的社科/经济学实证分析任务请求时；
- 当后序审稿人技能给出 🔴 打回指令并携带 `rejected_strategies` 时。

## 三、 闭环状态机与历史防死循环机制
Router 在上下文中维护 `execution_history` 状态对象：

```json
{
  "current_step": "identification_re_routing",
  "rejected_strategies": ["staggered-did"],
  "rejection_reasons": {
    "staggered-did": "预前期趋势联合检验 p=0.012 < 0.05, 违反平行趋势"
  },
  "attempted_count": 2
}
```

## 四、 执行流程
1. **调用 `data-audit`**：生成包含面板、错位处理、RDD 断点、IV 候选、Donor Pool 等全套结构化元数据；
2. **调用 `identification-strategy`**：传入 `data-audit` 元数据及 `rejected_strategies`；
   - 提取 `primary_strategy`（确保排除已否决策略）；
3. **路由至选定的 L2 估计器**（如 `did`, `staggered-did`, `iv`, `rdd`, `synthetic-control`, `matching`, `shift-share`）；
4. **调用 `baseline-regression`**：完成基准估计；
5. **调用 `robustness-router`**：组织专属稳健性检验矩阵；
6. **调用 `econometric-reviewer`**：
   - 🟢 **可信** ──► 路由至 `tables-and-figures` 产出最终报告；
   - 🟡 **存疑** ──► 调用 `sensitivity-bounds` (HonestDiD) 补充补救路线图；
   - 🔴 **致命缺陷** ──► 将被否决策略写入 `rejected_strategies`，打回步骤 2 重新选策略。

## 五、 失败终结条件
- 尝试次数 `attempted_count > 3` 且所有可能识别策略均被 🔴 否决；
- 向研究者汇报：“现有数据和假定无法支持可靠的因果推断。”

## 六、 底层工具
- Python 状态机引擎 / JSON 流转管道。

## 七、 来源与许可证信息
- 来源：自研 / 借鉴 AER-Skills Workflow；
- 许可证：MIT License。
