# 经济学文献检索 Agent

这是经济学科研辅助 Agent 的文献检索模块。目前已具备多源检索、检索协议生成、去重评分、期刊分级、结果筛选与导出、开放 PDF 下载及本机 Zotero 保存能力。模块采用独立 JSON Schema 和 source adapter，便于后续接入其他研究模块或继续增加数据源。

## 当前能力

- 根据中文经济学问题生成英文工作检索式、概念块、方法词和中文检索协议。
- 自动检索 Crossref、NBER、DataCite、arXiv、CORE、OpenAlex、EconBiz 和 World Bank。
- 为 Google Scholar、SSRN、IDEAS/RePEc、EconPapers、CEPR、IZA、CNKI、万方、BFI、SIEPR 和 LSE CEP 生成网页检索入口及核验日志。
- 按 DOI、外部 ID、标准化标题及标题/作者相似度去重。
- 提供主题、方法、数据、来源、证据完整性和开放材料六维候选排序评分。
- 显示期刊来源，并依据《浙江财经大学中外文学术期刊定级管理办法（2024年修订）》内置清单匹配期刊等级；动态清单未命中时标记为“待核验”。
- 导出 JSON、CSV、RIS、BibTeX 和 ENW。
- 批量下载明确开放的 PDF，并将选中文献及可下载 PDF 保存到本机 Zotero。
- 保存检索会话、参数、结果数量和哈希，支持重新载入。

## 目录

```text
paper/
├── src/literature_search/       # 检索、清洗、评分、导出、Zotero 与网页服务
├── web/                         # 可视化操作页面
├── config/                      # 数据源、运行参数和期刊分级配置
├── schemas/                     # 与总 Agent 合并时使用的 JSON Schema
├── skills/literature-search/    # 文献检索 Skill 及扩展说明
├── tests/                       # 单元测试
├── examples/                    # 输入输出示例
├── prompts/                     # Agent 提示词模板
├── evals/                       # 检索评测用例与量表
├── INTERFACE.md                 # 模块合并接口
└── WEB_UI.md                    # 网页功能与数据位置说明
```

## 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- 当前代码只使用 Python 标准库，不需要安装额外 Python 包。
- 保存至 Zotero 时，需要启动 Zotero Desktop，并允许本机其他应用与 Zotero 通信。

## API Key

CORE 和 OpenAlex 通过 Windows 用户环境变量读取 API Key，不应把 Key 写进项目文件：

```powershell
[Environment]::SetEnvironmentVariable("CORE_API_KEY", "你的Key", "User")
[Environment]::SetEnvironmentVariable("OPENALEX_API_KEY", "你的Key", "User")
```

设置后重新打开 PowerShell 或重新启动网页服务。Semantic Scholar 适配器已预留，取得 Key 后可继续实现并通过 `SEMANTIC_SCHOLAR_API_KEY` 配置。

## 启动网页

在本目录打开 PowerShell：

```powershell
$env:PYTHONPATH = "src"
python -m literature_search.web --host 127.0.0.1 --port 8765
```

随后访问：<http://127.0.0.1:8765>

## 运行测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

整理本版本时共 42 项测试通过，覆盖数据源解析、检索协议、去重评分、会话、期刊分级和 Zotero 保存。

## Zotero 与 PDF 说明

网页将条目保存到 Zotero 当前选中的收藏夹。PDF 不限于 arXiv：只要数据源返回可直接访问的 `open_access_pdf_url`，Agent 就会尝试下载并作为 `Full Text PDF` 子附件保存。World Bank、EconStor/EconBiz、CORE 等开放直链可用；ScienceDirect 等出版商可能因登录、权限或反爬限制返回 403，此时只保存文献元数据。

单个 PDF 上限为 100 MB。程序不会绕过登录、验证码、机构权限或付费墙。

## 团队合并

- 文献检索模块入口：`src/literature_search/`
- 数据契约：`schemas/`
- 详细接口：`INTERFACE.md`
- 新数据源扩展指南：`skills/literature-search/references/add-source-adapter.md`

后续与选题、文献阅读、证据综合、实证分析或写作模块合并时，应通过 Schema 定义的输入输出交换数据，避免其他模块直接依赖网页内部状态。

## 运行数据

运行时会在工作区 `_ai_temp/` 下生成最新结果、SQLite 会话索引、会话快照和 NBER 缓存。这些文件属于本机运行记录，不包含在本次源码包中，也不是模块合并的必要依赖。

## 当前限制

- Semantic Scholar 尚未正式启用。
- CNKI、万方、Google Scholar 等受限来源目前采用网页辅助检索和人工核验。
- 自动评分用于候选排序，不等同于论文质量或因果识别质量的最终学术判断。
- 已保存到 Zotero 的旧错误条目不会被自动修改，需要删除后重新保存或在 Zotero 中手工校正。
