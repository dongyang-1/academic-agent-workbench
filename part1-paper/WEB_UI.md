# 文献检索可视化工作台

页面直接调用 `src/literature_search/runtime.py`，与命令行和总 Agent 共用同一套标准化、去重、评分与输出结构。

## 启动

> **入口已统一**：本页能力已接入主工作台 `http://127.0.0.1:8088` 的「🔎 文献检索」标签页
> （桥接层：`web_platform/literature_bridge.py`）。日常使用只启动 :8088 即可，
> 无需再单独启动 :8765；下列命令仅在需要调试 part1 原始页面时使用。

```powershell
$env:PYTHONPATH = "src"
python -m literature_search.web --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765`。服务可读取当前进程或 Windows 用户级的 `CORE_API_KEY`、`OPENALEX_API_KEY`。Zotero 使用本机 `127.0.0.1:23119` Connector 接口，网页只显示本机 Zotero 是否在线及版本号。

## Zotero 本地保存

1. 启动 Zotero Desktop。
2. 在 Zotero 中先选中希望保存到的收藏夹。
3. 在网页结果中勾选文献并点击“保存到本机 Zotero”。

当前兼容 Zotero 9 的 Connector 保存协议，不需要 Zotero.org API Key。Zotero 9 的该接口会将条目保存到 Zotero 当前选中的收藏夹，不能由网页可靠指定其他收藏夹。

## 页面能力

- 根据中文经济学问题同步生成英文工作检索式、概念块、建议方法和纳排标准，也允许人工编辑。
- 检索协议以中文呈现；概念和方法同时保留英文数据库检索术语，兼顾可读性与机器检索效果。
- 经济学问题变化后自动重新生成协议，并取消原有协议确认，避免沿用上一问题的检索边界。
- 选择探索检索或系统检索，并设置概念块、方法、纳入标准、排除标准与排序策略。
- 同时运行自动来源并生成网页辅助来源的官方检索入口。
- 按 DOI、外部 ID、标准化标题及标题和作者相似度去重。
- 计算主题、方法、数据、来源、证据完整性、开放材料六维评分。
- 提醒时间、来源、证据深度和方法分布可能存在的偏斜。
- 将文献标记为纳入、待定或排除，并记录理由。
- 导入已有 JSON 文献语料，与当前结果统一标准化、去重和评分。
- 导出完整 JSON、筛选后 CSV、RIS、BibTeX 或 ENW。
- 将“开放 PDF”直接链接到来源返回的原始开放 PDF 地址。
- 结果表在年份后单独显示期刊来源、ISSN 匹配得到的校内分类等级，并将 API 数据源拆分为独立列。
- 支持按浙江财经大学期刊等级筛选。附件明确列出的期刊自动定级，涉及 CSSCI、CSCD、JCR、AJG 等动态清单且未命中时标记为“待核验”。
- 支持按需生成题名中文译文；详情页摘要可按需翻译并在中文与原文之间切换。
- 检索结果可逐条勾选，表头支持选择当前筛选结果；工具栏可批量下载其中的开放 PDF，或将所有选中文献的 DOI 与元数据保存到 Zotero。
- 保存每次检索的参数、结果、数量与 SHA-256 哈希，并从“检索会话”页重新载入。

## 数据位置

- 最新网页结果：`_ai_temp/literature-search-web-latest.json`
- 会话索引：`_ai_temp/literature-search-sessions/sessions.sqlite3`
- 会话快照：`_ai_temp/literature-search-sessions/<session_id>.json`

这些文件是运行留痕，不是总 Agent 的内部依赖。模块合并时应使用 JSON schema 接口。

## 当前限制

- CNKI、万方、Google Scholar 等只提供网页检索入口和人工核验日志。
- 页面不会绕过登录、机构权限、验证码或付费墙。
- Zotero 当前在本地保存题名、作者、年份、来源、DOI、摘要、URL 与期刊等级标签；预印本会保存为 `Preprint` 类型。存在开放 PDF 时，agent 会先创建父条目，再下载 PDF 并通过 Connector 附加为本地存储的 `Full Text PDF` 子附件（单个文件上限 100 MB）。
- 质量评分是透明的候选排序工具，不代表论文质量的最终学术判断。
