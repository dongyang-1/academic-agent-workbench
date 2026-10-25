---
name: data-acquisition
name_zh: 联网实证数据采集与面板构建
description: 联网获取开源宏观经济、行业与微观企业财务数据，并自动清洗规整为标准计量经济学面板/时间序列数据。
category: 01_data
priority: high
inputs: [研究课题意图, 数据类型需求 (宏观GDP/CPI/行业微观面板/股票池), 目标时间范围]
outputs: [标准化计量面板数据集 (.csv / .dta), 样本描述统计, 数据来源说明]
dependencies: []
source_repository: Self-developed
source_path: tools/python/data_acquisition.py
original_skill_name: data-acquisition
license: MIT
adaptation_status: native
---

# 联网实证数据采集与面板构建 (Data Acquisition)

## 一、 这个 Skill 是干什么的
`data-acquisition` 作为整个智能体数据链路的最前置技能（L0 / 01_data），赋予实证 Agent **主动联网搜集公开实证数据**的能力。它通过集成四大权威公开数据源（巨潮资讯网 CNINFO、世界银行 World Bank、国家统计局 NBS、AkShare），将用户模糊的研究意图转化为具体的指标抓取任务，自动规整为包含 `firm_id`（个体标识）、`year`（时间维度）及关键变量的标准计量面板或时间序列，无缝传递给下游的 `data-audit` 进行结构审计。

### 💡 核心底层逻辑与官方数据源架构
1. **上市公司原版年报 (巨潮资讯网 CNINFO 直抓)**：
   - 底层直连中国证监会法定披露门户 **巨潮资讯网**，检索股票历年定期公告，智能排除摘要噪音，获取原版完整披露 PDF 直链并流式下载，为非结构化文本挖掘（MD&A）提供原始文本底座；
2. **全球跨国面板 (世界银行 World Bank API)**：免密拉取 200+ 国家人均 GDP、碳排放与贸易开放度；
3. **中国省际宏观面板 (国家统计局 NBS)**：拉取 31 省份 GDP、财政收支、人口并配备权威基准保障；
4. **国内高频时序与A股财务 (AkShare)**：一键拉取全国季度 GDP、月度 CPI 与微观财务指标。

## 二、 什么时候使用
- 用户提出实证需求但尚未提供本地数据集；
- 用户明确要求从互联网公开渠道拉取宏观指标（如 GDP、CPI）或上市公司财务数据（如某行业研发投入、总资产、营业收入等）；
- 需要直接检索并下载上市公司原版年报 PDF 或构建数字化转型等文本词频指标；
- 需要扩充既有数据集的外生宏观控制变量或政策试点背景。

## 三、 什么时候不要使用
- 用户已经提供了本地的完整研究数据集（如已上传 `.dta` 或 `.csv` 文件）；
- 涉及需要学校内网账号付费登录的商业私有数据库（如未经授权的完整 CSMAR/Wind 全库批量下载）。

## 四、 执行流程与核心能力
1. **意图解析与数据类型匹配**：
   - 识别用户需要的是“宏观时间序列”、“中观行业指标”、“微观企业面板”还是“原版年报文本”。
2. **免密公开接口调用**：
   - **全球跨国面板 (World Bank API)**：调用 `DataAcquisitionEngine.fetch_world_bank_panel()` 一键获取跨国人均 GDP、碳排放、贸易开放度等国家级面板；
   - **中国省际宏观面板 (国家统计局 NBS)**：调用 `DataAcquisitionEngine.fetch_nbs_provincial_panel()` 获取中国各省份历年 GDP、人均生产总值、人口与财政收支等宏观控制变量；
   - **国内宏观时序 (AkShare)**：调用 `DataAcquisitionEngine.fetch_macro_gdp()`、`fetch_macro_cpi()` 获取全国季度 GDP 与月度 CPI；
   - **上市公司微观面板 (A股财务)**：调用 `DataAcquisitionEngine.fetch_industry_stocks()` 与 `build_firm_panel_sample()` 抓取指定板块上市公司的财务微观面板；
   - **上市公司年报直抓与文本挖掘 (巨潮资讯网 CNINFO)**：调用 `AnnualReportTextMiner.fetch_cninfo_annual_reports()` 直接检索下载官方原版年报 PDF 直链，并提取 MD&A 章节统计顶刊词频；
   - **外生政策冲击赋能 (联动 `policy-pilot-crawler`)**：调用 `assign_policy_pilot_shock()` 自动为获取的面板注入准自然实验变量 (`first_treat`, `post`, `did`, `rel_year`)。
3. **计量面板标准化规整**：
   - 严格规范个体唯一标识（`country_code` / `province_id` / `firm_id`）与时间标识（`year`）；
   - 处理缺失值与奇异值；
4. **持久化与下游移交**：
   - 导出为标准 `.csv` 或 Stata `.dta` 文件；
   - 触发 `data-audit` 对所获取的数据进行全套 11 类因果识别方法特征审计。

## 五、 底层工具与支持库
- Python: `world_bank_data`, `akshare`, `pandas`, `numpy`
- 工具模块: `tools/python/data_acquisition.py`

## 六、 详细功能指南与文档索引
关于每个联网搜集/爬取功能的独立定位、底层实现逻辑、官方数据源接口、字段计量属性及实测落盘文件的详尽说明，请参阅：
👉 [联网数据获取与爬取详细功能指南 (DETAILED-INTRODUCTION.md)](skills/01_data/data-acquisition/DETAILED-INTRODUCTION.md)
