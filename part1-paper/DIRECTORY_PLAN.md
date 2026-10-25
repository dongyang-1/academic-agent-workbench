# Economics Research Agent 目录规划

## 设计原则

1. agent 本体只负责角色、边界、调度逻辑和输出标准。
2. 具体能力拆成 skills，每个 skill 保持独立、可测试、可替换。
3. 文献检索先做成第一个核心 skill，后续再扩展筛选、综述、引用管理等能力。
4. 临时脚本和中间数据仍遵守工作区规则，统一放到 `C:\Users\16638\vs code\_ai_temp\`。

## 建议目录树

```text
economics-research-agent/
├── README.md
├── DIRECTORY_PLAN.md
├── agent.md
├── config/
│   ├── sources.example.yaml
│   └── ranking.example.yaml
├── prompts/
│   ├── system.md
│   └── templates/
│       └── search-brief.md
├── schemas/
│   ├── literature-record.schema.json
│   └── search-plan.schema.json
├── src/
│   └── literature_search/
├── tests/
│   └── test_runtime.py
├── skills/
│   ├── literature-search/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── search-workflow.md
│   │   │   └── source-map.md
│   │   ├── scripts/
│   │   └── assets/
│   ├── literature-screening/
│   ├── literature-synthesis/
│   ├── citation-management/
│   └── replication-support/
└── evals/
    ├── literature-search-cases.md
    └── rubric.md
```

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `agent.md` | 定义 agent 的角色、输入输出、可调用 skills、停止条件和质量标准。 |
| `config/` | 存放可调整配置，例如检索源、排序权重、黑白名单期刊、年份范围默认值。 |
| `prompts/` | 存放系统提示词和可复用任务模板。 |
| `schemas/` | 约束文献记录、检索计划、筛选结果等结构化输出。 |
| `src/` | 可运行的统一检索器、数据源适配和标准化逻辑。 |
| `tests/` | 数据源解析、标准字段和运行回归测试。 |
| `skills/` | 存放各个能力模块。每个 skill 使用独立 `SKILL.md` 和可选资源目录。 |
| `evals/` | 存放测试案例、评价标准和回归检查清单。 |

## 第一阶段优先实现

1. `INTERFACE.md`：固定文献检索模块和总 agent 的输入输出契约。
2. `skills/literature-search/`：将研究问题转换为检索策略，当前通过 Crossref、NBER、DataCite 和 arXiv adapter 生成可追溯文献表。
3. `schemas/literature-record.schema.json`：统一文献元数据字段。
4. `schemas/search-log.schema.json`：记录每次检索的 source、query、参数和状态。
5. `evals/literature-search-cases.md`：沉淀典型经济学检索任务，用于回归测试。

## 当前新增的合并相关文件

| 文件 | 用途 |
| --- | --- |
| `INTERFACE.md` | 总 agent 调用文献检索模块的契约。 |
| `USER_TASKS.md` | 你需要补充的问题样例、排序偏好和团队约定。 |
| `config/source-adapters/semantic-scholar.adapter.json` | Semantic Scholar 的机器可读 adapter 配置。 |
| `config/source-adapters/*.adapter.json` | 各数据源的机器可读 adapter 配置。 |
| `src/literature_search/` | 无第三方依赖的检索运行器。 |
| `examples/search-plan.semantic-scholar.json` | 上游模块调用文献检索模块的示例输入。 |
| `examples/literature-search-output.semantic-scholar.json` | 文献检索模块交给下游模块的示例输出。 |
| `schemas/literature-search-output.schema.json` | 模块总输出 schema。 |
| `schemas/search-log.schema.json` | 检索日志 schema。 |
| `schemas/source-adapter.schema.json` | 新增数据源 adapter 的 schema。 |

## 后续可扩展 skills

| Skill | 目标 |
| --- | --- |
| `literature-screening` | 根据纳入排除标准筛选文献，标注保留/排除原因。 |
| `literature-synthesis` | 按理论机制、识别策略、数据集和结论组织文献综述。 |
| `citation-management` | 处理 BibTeX、DOI、Zotero 条目和引用格式。 |
| `replication-support` | 辅助寻找数据、代码、附录和复现实证设计。 |
