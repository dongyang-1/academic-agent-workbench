# Literature Search Module Interface

本文档定义文献检索模块与总经济学研究 Agent 之间的稳定接口。增加数据源、调整网页或更换排序策略时，应保持该接口向后兼容。

## 模块边界

| 项目 | 约定 |
| --- | --- |
| 模块 ID | `literature-search` |
| 负责范围 | 检索规划、来源执行、标准化、去重、质量评分、初筛、检索留痕和候选文献交接 |
| 不负责 | 根据标题臆测结论、撰写最终综述、绕过付费墙下载全文 |
| 自动来源 | `crossref`, `nber`, `datacite`, `arxiv`, `core`, `openalex`, `econbiz`, `world-bank` |
| 网页辅助来源 | `google-scholar`, `ssrn`, `ideas-repec`, `econpapers`, `cepr`, `iza`, `cnki`, `wanfang`, `bfi`, `siepr`, `lse-cep` |

网页辅助来源只生成可追溯的官方检索入口，结果必须标记为 `manual-check-needed`。CNKI、万方和 Google Scholar 当前不应被描述为自动抓取。

## 输入：SearchPlan

输入遵守 `schemas/search-plan.schema.json`。核心字段包括：

- `research_question`：研究问题。
- `mode`：`exploratory` 或 `systematic`。
- `concept_blocks`：政策、结果、机制、样本、方法等概念块及同义词。
- `sources`：来源 ID 列表；不得在主流程中硬编码供应商逻辑。
- `source_policy.ranking`：`combined`、`latest`、`relevance` 或 `citations`。
- `screening`：纳入标准、排除标准及协议确认状态。

系统检索模式必须先确认协议并至少填写一条纳入标准。默认检索数量 20 是运行参数，不是 schema 限制。

## 输出：LiteratureSearchOutput

输出遵守 `schemas/literature-search-output.schema.json`，主要包含：

- `records`：统一的 `LiteratureRecord` 列表。
- `search_logs`：每个来源的查询、时间、状态、命中数和人工核验状态。
- `search_protocol`：模式、概念块、方法与纳排标准。
- `search_metrics`：检索前后数量、重复数量及去重原因。
- `coverage_advisories`：时间、来源、证据深度或方法过度集中的提醒。
- `coverage_notes`：未覆盖范围、API 限制和后续动作。
- `handoff`：交给筛选、综述、引用管理或总编排模块的说明。
- `session_id`：可复现检索会话标识；网页运行时生成。

每条记录保留 `retrieval_sources`、`source_record_ids`、`verification_status`、`source_specific`、`venue`、`issn`、`journal_ranking`、六维 `quality_scores`、`total_score`、`screening_status` 和 `screening_reason`。

## 合并规则

1. 总 Agent 只通过 `SearchPlan` 调用，并消费 `LiteratureSearchOutput`；不依赖网页 DOM、SQLite 或临时文件。
2. 新来源只新增 adapter 与配置，不修改总 Agent 的调用字段。
3. 去重顺序为 DOI、外部 ID、标准化标题、标题相似度与第一作者；合并后保留全部来源 ID。
4. 工作论文与正式发表版本优先合并为同一研究记录，除非下游明确要求版本比较。
5. 质量评分用于候选排序和人工判断，不替代全文阅读或因果识别评价。
6. JSON 是模块间主交换格式；RIS、BibTeX、EndNote XML 风格 ENW 用于引文管理软件。
7. 会话数据库、检索快照、缓存与调试结果仅写入工作区 `_ai_temp/`。

## 版本

| 版本 | 能力 |
| --- | --- |
| `0.2` | 多来源检索、标准化记录和基础网页工作台 |
| `0.5` | 检索协议、增强去重、质量评分、分布提醒、人工筛选、会话留档、语料导入和引文导出 |
| `0.6` | EconBiz 与世界银行自动来源、高校工作论文入口、校内期刊等级、本机 Zotero 写入和通用批量选择 |
| `1.0` | 与总经济学研究 Agent 完成稳定集成后发布 |
