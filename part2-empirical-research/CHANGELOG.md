# 经济学/社科实证分析智能体 · 开发日志 (Changelog)

本文档用于记录 `empirical-research-agent` 项目的架构演进、技能扩充、接口修补以及后续的所有功能调整。

## 📅 v1.9.0 (2026-10-18) — 子智能体统一接口契约与出版级交付物生成器全面上线 (agent_api.py & deliverables_generator.py)

### 🌟 模块补全与协同架构升级 (Sub-agent API & Academic Deliverables)
1. **【模块 1 补全】统一子智能体 I/O 调度接口契约 (`tools/python/agent_api.py`)**：
   - 实现了对上游【文献选题 Agent】的宽容输入解析（Tolerant Input Reader），同时支持结构化 JSON、字典对象、本地文件或自然语言课题主题；
   - 封装 `run_empirical_task()` 统一对外执行函数，全自动串联 L0 数据准备 -> L1 因果图 DAG 坏控制审查 -> 识别策略状态机 -> L2 现代 CS-DID 估计 -> 机制分析 -> 审稿闭环；
   - 对外输出标准契约字典，包含课题元数据、估计值、审稿认证及交付物索引清单 (`empirical_deliverables_manifest.json`)。
2. **【模块 2 补全】出版级学术交付物生成器 (`tools/python/deliverables_generator.py`)**：
   - **双格式三线表自动生成**：输出 `table1_descriptive_stats` 与 `table2_baseline_regression` 的 Markdown 和 LaTeX（`booktabs` 规范，附带星号、聚类 SE、Bacon 诊断与防共线性剔除声明）；
   - **高分辨率学术矢量图绘制**：采用经管权威配色生成 `fig1_event_study_parallel_trends`（平行趋势检验图）与 `fig2_honest_did_sensitivity`（HonestDiD 灵敏度崩溃边界图）的 300 DPI PDF 矢量图与 PNG；
   - **面向【论文写作 Agent】的实证叙述草稿生成**：在 `deliverables/narratives/empirical_narrative_for_writing.md` 中自动撰写可直接嵌入论文第 4 章（基准与平行趋势检验）与第 5 章（机制调节分析）的标准学术中文段落。
3. **集成验收验证**：
   - 编写完成 [`tests/end-to-end/test_agent_api_and_deliverables.py`](tests/end-to-end/test_agent_api_and_deliverables.py) 并顺利执行（返回码 0），所有表格、图表、正文草稿及清单全部通过校验。

---

## 📅 v1.8.1 (2026-10-12) — 测试衍生数据与临时产物清理完成 (工作区完全净化)

### 🧹 维护与工程清理 (Workspace Cleanup)
1. **清理测试临时数据**：
   - 清空 `data/` 目录下全部测试生成的中间面板（包括 `ets_firm_digital_full_panel.csv`、`auto_firm_with_text_metrics.csv`、测试时下载的年报原版 PDF 及 JSON 评测报告等），保留纯净的 `data/.gitkeep`；
   - 清空 `tests/scratch/` 下的测试缓存数据；
2. **保留核心整体**：
   - 完整保留 28 个核心学术技能（`skills/`）与全部底层引擎（`tools/python/`）；
   - 工作空间彻底净化，随时迎接真实科研任务输入。

---

## 📅 v1.8.0 (2026-10-12) — 实证智能体三大架构短板全面填补完成 (认知/执行对齐、自适应反馈环与因果DAG审计)

### 🌟 顶刊级架构能力升级 (Deep Architectural Upgrades)
1. **【短板 1 填补】现代错位 DID 实质性估计器与 Bacon 权重诊断落地**：
   - 彻底告别“认同错位但底层裸跑传统 TWFE”的脱节现象；
   - 在 [`tools/python/econometric_engine.py`](tools/python/econometric_engine.py) 中实质性实现 **Callaway & Sant'Anna (2021)** 群组-时间聚合估计器（`estimate_callaway_santanna_att`）；
   - 输出分队列 $ATT(g)$ 与样本加权聚合 $ATT$，诊断将“已处理组作为对照”的坏比较权重彻底清除为 0；
   - 对接 **Rambachan & Roth (2023) HonestDiD** 灵敏度崩溃边界分析。
2. **【短板 2 填补】审稿人否决自适应打回重选状态机 (Adaptive Rerouting Loop)**：
   - 将原本单向线性的流水线重构为带反馈回路的自适应状态机；
   - 当审稿人发出 🔴 否决时，自动将失败策略登记入 `rejected_strategies` 黑名单，反向打回 `identification-strategy` 决策树触发降级重新路由，直至终审批准 🟢。
3. **【短板 3 填补】前置因果图 (DAG) 审计与坏控制 (Bad Controls) 自动拦截**：
   - 依据 Angrist & Pischke (2009) 规范，新增 `run_bad_controls_audit`；
   - 自动甄别候选控制变量中的后验中介变量（如管理层短视、研发投入），在基准方程中强制拦截并剔除，严防碰撞偏误（Collider Bias）。

---

## 📅 v1.7.0 (2026-10-12) — 全流程实证智能体端到端闭环测试成功通过 (test_full_agent_pipeline.py)

### 🌟 端到端实证检验闭环 (End-to-End Pipeline Verification)
1. **测试选题与全链路贯通**：
   - 课题选题：**《国家碳交易试点 (ETS) 对企业数字化转型的政策效应——兼论管理层短视的调节作用》**；
   - 编写完成全流程可执行测试脚本 [`tests/end-to-end/test_full_agent_pipeline.py`](tests/end-to-end/test_full_agent_pipeline.py) 并顺利执行（返回码 0）；
   - 贯通 L0（政策试点爬虫 + 巨潮网年报挖掘 + 财务面板）➔ L1（数据审计 + 因果决策树）➔ L2（错位 DID 基准回归）➔ L3（事件研究法平行趋势 + 机制调节）➔ L1（匿名审稿人审核闭环）。
2. **防多重共线性严格规则落实**：
   - 引入企业规模对数衍生变量 `ln_assets` 时，**显式从控制变量列表中彻底剔除原始变量 `total_assets_billion`**，严禁使用 `+其他控制变量` 模糊表述；
   - 最终控制变量集合严格限定为 `['leverage_pct', 'roa_pct', 'ln_assets']`，杜绝完全共线性风险。
3. **成果与数据资产持久化**：
   - 合成全要素微观实证面板：[`data/ets_firm_digital_full_panel.csv`](data/ets_firm_digital_full_panel.csv) (56条长面板观测)；
   - 产出标准实证评估报告：[`data/full_pipeline_test_report.json`](data/full_pipeline_test_report.json)。

---

## 📅 v1.6.0 (2026-10-12) — 联网获取与网络爬取模块详细功能指南全面发布 (DETAILED-INTRODUCTION.md)

### 🌟 文档体系与工程规范完善 (Documentation & Engineering Guidelines)
1. **网络搜集/爬取功能独立模块化阐述**：
   - 响应严格学术计量标准，彻底拆解避免混淆，在 `skills/01_data/data-acquisition/` 下正式发布 [`DETAILED-INTRODUCTION.md`](skills/01_data/data-acquisition/DETAILED-INTRODUCTION.md)；
   - 系统阐明 6 大核心独立功能：
     1. 上市公司微观财务面板采集器 (A股基本面与行业板块)
     2. 全球跨国宏观实证面板获取器 (World Bank Open Data API)
     3. 中国省际宏观核算面板采集器 (国家统计局 NBS)
     4. 政策试点准自然实验与DID时序爬虫 (四大试点库 + 自动生成 `did`, `post`, `rel_year`)
     5. 上市公司年报官方原版PDF直抓与文本挖掘爬虫 (巨潮资讯网 CNINFO 直抓 + 顶刊词库)
     6. 全国宏观经济高频时间序列采集器 (央行/统计局 CPI, M2, GDP 同比)
2. **规范与实测对照**：
   - 每个功能独立标明：定位与学术场景、官方底层数据源、底层技术逻辑与核心函数、输入参数、输出字段计量属性、实测案例与落盘文件；
   - 强化计量防多重共线性规避声明与平衡面板清洗规范。

---

## 📅 v1.5.0 (2026-10-12) — 上市公司年报文本挖掘与非结构化实证指标构建 (技能库增至 28 个)

### 🌟 新增功能与技能 (Features & New Skills)
1. **L0 层扩充，新增 `annual-report-text-miner` 技能（总技能库增至 28 个）**：
   - 解决经管顶刊最前沿的**非结构化实证指标构建**难题（传统数据库缺乏数字化、绿色创新等现成数值）；
   - **巨潮资讯网 (CNINFO) 原版年报直抓**：对接中国证监会法定披露门户，实现批量检索并下载上市公司原版完整 PDF 年报（实测比亚迪 9.19MB、广汽 12.94MB 等 5 篇年报秒级命中并下载流落盘）；
   - 内置经管顶刊三大经典词库：**数字化转型词库 (吴非等 2021 / 袁淳等 2021)**、**绿色技术创新词库**、**管理层短视主义词库**，支持自定义词表。
2. **底层文本挖掘与计量指标标准化 (`tools/python/annual_report_miner.py`)**：
   - 实现了原始词频统计 (`raw_count`)、对数平滑项 (`ln(count + 1)`) 与词频密度 (`density = count / total_words * 100%`) 的自动化计算；
   - 针对上市车企（比亚迪、赛力斯、上汽、长城）2018-2024 年报完成实战挖掘，并与微观财务指标横向左连接对齐，产出 [`auto_firm_with_text_metrics.csv`](data/auto_firm_with_text_metrics.csv)。
3. **因果识别闭环与共线性排查 (`tests/end-to-end/test_annual_report_miner.py`, `test_crawl_5_annual_reports.py`)**：
   - 数据成功通过 `L1: data-audit` 强平衡面板审计；
   - 编写完成 5 篇年报真实抓取测试脚本，生成 [`crawled_5_reports_manifest.csv`](data/annual_reports_sample/crawled_5_reports_manifest.csv)；
   - 严格落实**防多重共线性**规则：在生成双向固定效应 (TWFE) 建模建议时，显式声明在纳入规模对数 `ln_assets` 时彻底剔除原始 `total_assets` 变量；
   - 技能注册表更新至 `v1.5`，同步更新 `README.md`、[`data-acquisition/SKILL.md`](skills/01_data/data-acquisition/SKILL.md) 与 [`annual-report-text-miner/SKILL.md`](skills/01_data/annual-report-text-miner/SKILL.md)。

---

## 📅 v1.4.0 (2026-10-12) — 政策试点爬虫与 DID 外生冲击自动注入 (技能库增至 27 个)

### 🌟 新增功能与技能 (Features & New Skills)
1. **L0 层扩充，新增 `policy-pilot-crawler` 技能（总技能库增至 27 个）**：
   - 解决计量经济学因果推断（DID / Staggered DID）最核心的痛点：**政策干预变量与试点批次时间的自动化构建**；
   - 支持国家低碳试点、智慧城市试点、国家碳排放权交易试点（ETS）、国家创新型城市试点四大经典顶刊准自然实验名录。
2. **底层政策解析与变量注入引擎 (`tools/python/policy_crawler.py`)**：
   - 实现了 `PolicyPilotCrawler.assign_policy_to_panel()`，支持地名模糊匹配与多批次时序对齐；
   - 自动在既有面板中注入 `is_treated`（处理组）、`first_treat`（首次冲击年份）、`post`（政策期）、`did`（交互项）与 `rel_year`（事件研究法相对时间）。
3. **因果识别闭环验证 (`tests/end-to-end/test_policy_pilot.py`)**：
   - 将碳交易试点自动注入国家统计局省际宏观面板，生成 [`nbs_provincial_with_ets_did.csv`](data/nbs_provincial_with_ets_did.csv)；
   - `L1: data-audit` 自动精准识别出 `is_staggered: True` 与 `has_never_treated: True`；
   - `L1: identification-strategy` 自动决策树直接将主推因果方法锁定为现代异质性稳健的 **`staggered-did`**，因果推断链路实现全自动贯通；
   - 技能注册表更新至 `v1.4`，同步更新 `AGENTS.md` 与 `README.md`。

---

## 📅 v1.3.0 (2026-10-12) — 联网实证数据采集能力集成 (L0 层构建)

### 🌟 新增功能与技能 (Features & New Skills)
1. **构建 L0 数据准备层，新增 `data-acquisition` 技能（总技能库增至 26 个）**：
   - 为 Agent 赋予免 API Key 的在线学术数据搜集能力，打破以往必须研究者自备离线数据的壁垒；
   - 接入三大权威开源数据源：**世界银行 World Bank API**（跨国宏观面板）、**国家统计局 NBS**（中国省际宏观面板）、**AkShare**（全国宏观与 A 股上市公司微观财务面板）。
2. **底层数据采集引擎与网络弹性 (`tools/python/data_acquisition.py`)**：
   - **世界银行跨国面板获取器 (`fetch_world_bank_panel`)**：支持中美德日法英韩等核心大国人均 GDP、碳排放、FDI、贸易开放度等跨国面板一键拉取；
   - **国家统计局省际面板获取器 (`fetch_nbs_provincial_panel`)**：支持中国 31 省份历年地区生产总值、人均 GDP、常住人口、公共财政收入等宏观控制变量构建，内置权威基准保障通道；
   - **企业微观财务面板构建器 (`build_firm_panel_sample`)**：支持指定行业（如汽车制造业）核心财务指标抓取并转换为标准长面板；
   - 内置 `NO_PROXY` 直连国内数据源自适应配置，以及典型行业标的池回退机制，确保在线网络波动时整个管道永不崩溃；
   - 支持一键导出为标准计量格式（`.csv` / Stata `.dta`）。
3. **闭环测试与路由联动**：
   - 编写并跑通实战测试：[`tests/end-to-end/test_data_acquisition.py`](tests/end-to-end/test_data_acquisition.py) 及 [`tests/end-to-end/test_wb_and_nbs.py`](tests/end-to-end/test_wb_and_nbs.py)；
   - 成功生成三大基准实证数据集：[`world_bank_country_panel.csv`](data/world_bank_country_panel.csv)、[`nbs_provincial_macro_panel.csv`](data/nbs_provincial_macro_panel.csv)、[`auto_industry_financial_panel.csv`](data/auto_industry_financial_panel.csv)；
   - 实现了 **联网数据采集 ➔ 面板数据规整 ➔ `data-audit` 结构审计 ➔ `identification-strategy` 因果策略选择** 的全流程跨模块无缝流转；
   - 更新技能注册表 [`skills/skill-registry.yaml`](skills/skill-registry.yaml) 至 `v1.3`，同步更新 [`AGENTS.md`](AGENTS.md)、[`README.md`](README.md) 与 [`skills/01_data/data-acquisition/SKILL.md`](skills/01_data/data-acquisition/SKILL.md)。

---

## 📅 v1.2.0 (2026-08-23) — 顶刊前沿因果识别方法扩展

### 🌟 新增功能与技能 (Features & New Skills)
1. **L2 计量方法层扩充 (7 → 11 个估计器)**：
   针对 AER, Econometrica, QJE 等顶级期刊的前沿因果推断需求，新增 4 个高阶因果识别 Skill：
   - **`double-machine-learning`** (DML / 双重机器学习)：基于 Chernozhukov et al. (2018) 框架，采用 Neyman 正交化与交叉拟合消解高维混杂偏误；
   - **`bunching-design`** (Bunching / 行为聚束分析设计)：基于 Saez (2010) 与 Kleven (2016) 框架，通过估计反事实无堆积密度计算超额堆积量 $B$ 与结构弹性；
   - **`regression-kink-design`** (RKD / 斜率断点回归设计)：基于 Card et al. (2015) 框架，利用政策在 Cutoff 处的斜率折角 (Kink in Slope) 识别边际效应；
   - **`local-projections`** (LP & LP-DiD / 局部投影与 LP-DiD)：基于 Jordà (2005) 与 Dube et al. (2023) 框架，估计高频面板/动态脉冲响应带 (IRF) 与多期冲击。
2. **总技能库扩充至 25 个**：
   架构保持 L1: 6 个, L2: 11 个, L3: 8 个。

### 🔧 接口与元数据同步 (Metadata & Interfaces)
- **`data-audit` 接口升级**：新增 `has_high_dim_controls`, `has_bunching_threshold`, `has_slope_kink`, `has_time_series_lags` 4 个结构化数据信号契约。
- **`identification-strategy` 决策树升维**：决策树与优先级排序规则完整融入 11 大 L2 估计器。
- **注册表与文档微调**：
  - 更新 [`skills/skill-registry.yaml`](skills/skill-registry.yaml) 至 `v1.2`；
  - 更新 [`docs/SKILL-MAP-ZH.md`](docs/SKILL-MAP-ZH.md) 映射表；
  - 微调 [`docs/SKILL-MANUAL.md`](docs/SKILL-MANUAL.md) 表格样式，在 4 个新增技能名称后添加加粗与括号中英文全称。

---

## 📅 v1.1.0 (2026-08-23) — 数据与决策接口缺口修补 & 打回防死循环

### 🐛 缺陷修复与数据接口增强 (Bug Fixes & Refactoring)
1. **数据审计信号补齐 (`data-audit`)**：
   修复 `data-audit` 仅输出面板/错位 DID 字段的问题，扩充输出 JSON 契约，补齐 `has_running_var_cutoff`, `has_candidate_iv`, `has_donor_pool`, `has_shift_share_structure` 等信号。
2. **决策树与路由入口补全 (`identification-strategy`)**：
   补齐 `matching` 与 `shift-share` 的正规决策树入口。
3. **多策略优先级排序 (Priority Ranking)**：
   建立显式识别优先级规则（断点 RDD > 政策实验 DID > 宏观 SCM > 工具变量 IV/Shift-Share > 匹配 Matching），输出主推策略 (`primary_strategy`) 与备选列表 (`alternative_strategies`)。
4. **打回重选防死循环机制 (Anti-Loop Rerouting)**：
   - 增加 `rejected_strategies` 历史记录字典；
   - 当 `econometric-reviewer` 给出 🔴 判定时写回被否决策略与原因；
   - Router 打回 `identification-strategy` 重选时强制滤除已否决项，实现自适应降级重新路由。

---

## 📅 v1.0.0 (2026-08-23) — 项目初始架构确立与首版发布

### 🚀 初始版本创建 (Initial Release)
1. **项目定位**：创立面向经济学与社科实证分析的专用智能体 `empirical-research-agent`，坚持“判断优先于执行”与“消除机械裁判”。
2. **知识库整合与隔离**：
   - 原始开源仓库保存于 `source_skills/`；
   - 重构后的精炼技能库存放于 `skills/`。
3. **三层 Skill 架构建立 (21 个技能)**：
   - **L1 核心决策层 (6个)**：`empirical-router`, `data-audit`, `identification-strategy`, `baseline-regression`, `robustness-router`, `econometric-reviewer`；
   - **L2 计量方法层 (7个)**：`did`, `staggered-did`, `iv`, `rdd`, `synthetic-control`, `matching`, `shift-share`；
   - **L3 工具/分析组件层 (8个)**：`placebo`, `clustering`, `alternative-specification`, `heterogeneity`, `mechanism`, `tables-and-figures`, `replication-tools`, `sensitivity-bounds`。
4. **“三幕剧” 端到端演示**：
   - 编写测试脚本 [`tests/end-to-end/demo_three_acts.py`](tests/end-to-end/demo_three_acts.py) 与底层适配引擎 [`tools/python/econometric_engine.py`](tools/python/econometric_engine.py)；
   - 完美展示普通 AI 裸跑 TWFE -> Agent 现代错位 DID -> 审稿人拦截 🔴 并给出 HonestDiD 补救路线图全过程。

---

> **维护说明**：后续所有功能调整、模型改进或技能扩充，均在本文档中按版本号与时间进行追加记录。
