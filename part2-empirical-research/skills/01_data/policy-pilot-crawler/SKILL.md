---
name: policy-pilot-crawler
name_zh: 政策试点名单与事件时序爬虫
description: 联网检索或调取中央部委政策试点名录 (低碳城市、智慧城市、碳交易ETS等)，自动为既有面板数据注入 DID / Staggered DID 因果推断核心变量 (is_treated, first_treat, post, did, rel_year)。
category: 01_data
priority: high
inputs: [既有实证面板数据, 目标政策名称或公文关键词, 个体标识列名, 时间年份列名]
outputs: [注入因果干预变量的 DID 计量面板, 试点实施时序分布报告, 处理组/对照组样本统计]
dependencies: []
source_repository: Self-developed
source_path: tools/python/policy_crawler.py
original_skill_name: policy-pilot-crawler
license: MIT
adaptation_status: native
---

# 政策试点名单与事件时序爬虫 (Policy Pilot Crawler)

## 一、 这个 Skill 是干什么的
`policy-pilot-crawler` 是实证分析因果推断的“外生冲击构建利器”。在经济学、管理学研究中，评估一项公共政策的影响通常采用双重差分法（DID）或错位 DID（Staggered DID），其最关键的先决条件是确定**“哪些个体属于处理组”**以及**“各批次试点是在哪一年实施的”**。该 Skill 自动检索中央部委政策文件或调用权威试点名录库，自动为面板数据匹配生成 `first_treat`（首次处理年份）、`is_treated`（处理组虚拟变量）、`post`（政策期）与 `rel_year`（事件研究法相对时间），使数据集可以直接输入给 `data-audit` 触发因果策略评估。

### 💡 核心定位与工作机制（它能爬取所有政策吗？）
**并非全网所有政策都能凭空全自动抓取，其本质是充当“政府公文文本”到“计量 DID 变量矩阵 (0/1)”的自动翻译器**：
1. **第一轨（经典顶刊政策·开箱即用）**：
   - 经管顶刊 80% 高频使用的国家级准自然实验（低碳城市、智慧城市、碳交易ETS、创新型城市）已内置权威批次名录与实施年份映射表。研究者只需提政策名称，**无需等待即可秒级完成面板标记**。
2. **第二轨（冷门与最新政策·定向抽取与转译）**：
   - 面对最新或细分部委政策（如绿色金融试验区、专精特新、跨境电商试点等），研究者只需提供**政策公文网址**或**直接复制发文正文/名单文本**；
   - 系统自动提取发文年份（`first_treat`）与入选名单，并通过地名/企业名称模糊对齐，自动生成 `is_treated`, `post`, `did`, `rel_year`，**彻底省去研究者在 Excel 里手动逐行对照打勾的繁重体力劳动**。

## 二、 什么时候使用
- 用户需要基于某项国家政策（如国家低碳试点、智慧城市试点、碳交易试点）开展 DID / 错位 DID 实证检验；
- 用户只有基础财务或宏观面板，缺少核心解释变量（政策虚拟变量与实施年份）；
- 需要进行平行趋势检验与事件研究法（Event Study Design）。

## 三、 支持的顶刊高频政策库
1. **国家碳排放权交易试点 (ETS Pilot)**：2013-2014年两省五市；
2. **国家低碳城市/省区试点 (Low-Carbon Pilot)**：2010年首批、2012年第二批、2017年第三批；
3. **国家智慧城市试点 (Smart City Pilot)**：2012年首批、2013年第二批、2014年第三批；
4. **国家创新型城市试点 (National Innovative City)**：2008年深圳、2010年扩大、2011-2013年多批推进。

## 四、 执行流程
1. **试点名录调取**：调用 `PolicyPilotCrawler.assign_policy_to_panel()`；
2. **行政区划/个体模糊对齐**：支持地名全称或简称（如“广东”自动匹配“广东省”）；
3. **因果变量自动生成**：
   - `first_treat`: 首次实施年份（未实施为 0）；
   - `is_treated`: 是否处理组（1/0）；
   - `post`: 是否处于冲击年份及之后（1/0）；
   - `did`: $is\_treated \times post$；
   - `rel_year`: $year - first\_treat$（相对年份，用于平行趋势检验）；
4. **移交实证审计**：数据移交 `L1: data-audit`，由于包含 `first_treat`，审计模块将自动识别出 `is_staggered: True`，无缝路由至 `staggered-did`。

## 五、 底层工具与支持库
- Python: `pandas`, `numpy`, `re`
- 工具模块: `tools/python/policy_crawler.py`
