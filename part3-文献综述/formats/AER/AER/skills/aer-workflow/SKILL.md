---
name: aer-workflow
description: Use when deciding which aer-* sub-skill to invoke next, or when sequencing an American Economic Review (AER) manuscript from fit screening through submission. Routes — does not replace — the specialized skills.
---

# AER 工作流（aer-workflow）

## 总览

路由器，不替代任何专用 skill。目标期刊：**American Economic Review**（American Economic Association 主办，1911 年创刊，月刊，ISSN 0002-8282 / 1944-7981，economics "top-5"，官网 aeaweb.org/journals/aer）。

本包是**英文顶刊通道**：与中文刊包（er- / mw- / cie- / jfr- / ceq-）的差异不在语言，而在**评审逻辑**——AER 先看**经济学重要性与读者广度**，再看识别；中文刊多数先看**选题与政策/现实意义**。因此写英文稿时不要用中文刊的叙事顺序直译。

> 事实核验：`resources/journal-profile.md`（README 标注核验日期 2026-06-17）。投稿前仍须以 AEA 官网现行指南为准。

## 路由表

| 当前症状 | 下一个 Skill |
|----------|-------------|
| 不确定该不该投 AER / 会不会被 desk reject | `aer-fit-positioning` |
| 摘要超 100 词 / 贡献写空 | `aer-abstract` |
| 引言前两页立不住、贡献对不上具体文献 | `aer-introduction` |
| 识别被质疑"这只是相关性" | `aer-identification` |
| 聚类理由、弱工具、多重检验被挑 | `aer-inference` |
| 图表不规范、LaTeX 排版 | `aer-tables-figures` |
| 数据包 / 复现材料 / DAP 表单 | `aer-data-availability` |
| 提交清单、披露声明、R&R 回复 | `aer-submission` |

## 阶段顺序

1. **Fit 筛查**（自评，不写在稿子里）：重要性与广度 → `aer-fit-positioning`
2. **设计定稿**：识别策略先于回归输出 → `aer-identification`
3. **结果 + 推断**：效应量、稳健性、推断口径 → `aer-inference`
4. **写作**：Introduction → 正文 → 图表 → 摘要**最后写** → `aer-abstract`
5. **交付物**：复现包 + 披露 + 提交 → `aer-data-availability` → `aer-submission`

## 硬约束速查

- 摘要 **≤ 100 词**，与标题、署名、单位同页。
- 首页不放独立 title page；标题与署名置于第一页顶部。
- **每位**合著者单独提交 PDF 披露声明（资助 / 利益冲突 / IRB，无亦须声明）。
- 含实证、模拟或实验的稿件，**有条件接受后**必须提交数据与代码（AEA Data and Code Repository / openICPSR）+ README + 签署的 Data and Code Availability Form 与 Archive Agreement。
- 田野实验须提供 **AEA RCT 注册号**；使用 AI 辅助须在稿件中简要说明。
- 材料不齐 = incomplete，不送审。
