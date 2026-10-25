# 实证分析智能体 · Skills 参考说明书 (v1.2 扩充版)

> 本手册按 `skills/` 下的文件夹顺序 (00 → 08) 逐块讲解：每块先说“这一块要解决什么问题、通过什么机制实现”，再列出块内每个 skill 具体做什么、吃什么输入、吐什么输出。内容依据当前仓库里 25 个 `SKILL.md` 的实际字段整理，不是概念性复述。

---

## 00_router —— 全局调度层

**这块解决的问题**：谁来决定“现在该跑哪个 skill”、以及“上一次失败了该怎么办”，不能让每个 skill 各自为政。

**实现机制**：`empirical-router` 在自己的上下文里维护一个 `execution_history` 状态对象，里面固定记录三样东西——`current_step`（当前走到哪一步）、`rejected_strategies`（历史上被否决过的识别策略数组）、`attempted_count`（总共尝试了几轮）。它按“数据审计 → 识别设计 → L2 估计器 → 基准回归 → 稳健性 → 审稿人”的固定顺序调用其余 skill，自己不做任何计算或判断，只做编排；当 `econometric-reviewer` 给出 🔴 判定时，它把被否决的策略连同否决原因追加进 `rejected_strategies`，再打回第二步重新选策略。如果 `attempted_count` 超过 3 轮仍然找不到能通过审查的策略，直接终止并向用户报告“现有数据和假定无法支持可靠的因果推断”，不会无限循环下去。

| Skill | 作用 |
|---|---|
| `empirical-router` | 全局状态机与总调度，维护否决历史，决定下一步该调用谁 |

---

## 01_data —— 数据结构审计层

**这块解决的问题**：在选任何计量方法之前，必须先知道数据本身长什么样、能支持哪些方法，不能靠猜。

**实现机制**：`data-audit` 是一个纯诊断型 skill，不涉及任何模型估计。它对着数据集依次审计 11 类结构特征——是否面板数据、面板是否平衡、处理是否分批错位实施、是否存在断点变量（Running Variable + Cutoff）、是否存在斜率折角（Kink）、是否存在行为堆积阈值（Bunching Threshold）、是否存在候选工具变量、是否存在“合成对照”控制池（Donor Pool）、是否具备 Shift-share 份额与冲击矩阵、是否包含高维特征（High-dimensional Controls）、是否包含高频序列与动态滞后项。最终输出一份**结构化的 JSON/字典**（`is_panel`、`is_staggered`、`has_running_var_cutoff`、`has_slope_kink`、`has_bunching_threshold`、`has_candidate_iv`、`has_donor_pool`、`has_shift_share_structure`、`has_high_dim_controls`、`has_time_series_lags` 等），这份字典是下游 `identification-strategy` 唯一读取的输入原料。

| Skill | 作用 |
|---|---|
| `data-audit` | 审计面板结构、错位处理、断点、斜率、堆积、候选IV、Donor Pool、Shift-share、高维特征及高频序列，产出完整结构化元数据契约 |

---

## 02_model —— 基准估计层

**这块解决的问题**：识别策略已经选定之后，第一次真正把模型跑出来，同时防止最基础的建模错误。

**实现机制**：`baseline-regression` 依赖 `identification-strategy` 的输出才能启动，根据被解释变量的类型（连续/二值/计数）配置高维固定效应（个体、时间、行业、地区等）与标准误聚类层级，产出标准化的基准回归结果。它同时承担“共线性防火墙”的角色——排查完全共线性与冗余变量，但不会因为出现了二次项、交互项等衍生变量就机械删除原始变量。

| Skill | 作用 |
|---|---|
| `baseline-regression` | 确定模型类型与固定效应/聚类设定，产出基准回归结果，排查共线性 |

---

## 03_identification —— 识别策略决策与估计器层 (全系统核心模块 · 11 大估计器)

**这块解决的问题**：全套 11 种因果识别方法里到底该用哪一种，选错了后面全白做。

**实现机制**：`identification-strategy` 是这一块的决策中枢，自己**不做任何估计**。它读取 `data-audit` 产出的结构化元数据，配合一张**显式优先级表**做决策（优先级从高到低：RDD / RKD / Bunching > DID / 错位DID > DML > 合成控制法 / LP-DiD > Shift-share / IV > Matching），同时读取 `rejected_strategies` 历史，强制把已经被否决过的方法从候选集里剔除。最终输出结构化的 `primary_strategy`（主策略）+ `alternative_strategies`（备选策略列表）+ `selection_rationale`（选择理由）+ `required_diagnostics`（该策略专属的必检项清单）。选定的方法名之后才会被路由到对应的 L2 估计器。

| Skill | 适用场景 | 核心产出 |
|---|---|---|
| `identification-strategy` | 决策中枢，不做估计 | 主/备选策略、决策理由、专属诊断清单 |
| `did` | 处理在**单一时点**统一发生，有明确未受处理对照组 | DID系数、平行趋势检验、简单事件研究图 |
| `staggered-did` | 处理在**不同个体分批错位**实施 (如政策试点逐批扩围) | Group-Time ATT(g,t)、汇总ATT、Bacon分解、异质性稳健事件研究图——用现代估计量 (CS/Sun-Abraham/BJS插补) 替代传统TWFE，消除坏对比负权重偏误 |
| `iv` | 核心解释变量存在内生性，且有满足外生性+相关性的工具变量 | 第一阶段结果、2SLS系数、Effective F统计量、AR置信区间——弃用“F>10”机械判定 |
| `rdd` | 处理状态由某个连续驱动变量是否跨越固定断点决定 | LATE处理效应、带宽敏感性图、密度检验结果、断点两侧拟合图——用MSE最优带宽+RBC置信区间，密度检验异常不机械判死刑 |
| `synthetic-control` | 受处理单位极少 (单一省份/城市)，且有较长的处理前时期数据 | 合成权重向量、处理组vs合成对照组路径图、安慰剂排列推断分布 |
| `matching` | 处理组与对照组在可观测背景特征上系统性差异明显 | 倾向得分结果、匹配后子样本、协变量平衡性检验 (Love Plot)、共同范围图——常与DID组合使用 (PSM-DID) |
| `shift-share` | 需要评估全国/宏观外生冲击对不同初始结构地区的因果效应 | Bartik工具变量值、2SLS系数、Rotemberg权重分析——显式区分“份额外生”与“冲击外生”两类假设并分别检验 |
| **`double-machine-learning`** (DML / 双重机器学习) | 控制变量特征极高维、混杂因素与 $Y$ 存在复杂非线性关系 | Neyman 正交化因果效应估计量 $\alpha$、交叉拟合 $R^2$ 与特征重要性——解决高维过度拟合与插件偏误 |
| **`bunching-design`** (Bunching / 行为聚束分析设计) | 政策在税率/补贴门槛处产生边际激励突变，导致直方图形成行为堆积 | 反事实无堆积密度曲线、超额堆积量 $B$、结构弹性及其 Bootstrap 置信区间 |
| **`regression-kink-design`** (RKD / 斜率断点回归设计) | 政策在 Cutoff 处水平连续，但斜率发生折角/突变 (Kink in Slope) | RKD 边际因果效应估计量、斜率突变对比图、带宽敏感性及协变量斜率连续性检验 |
| **`local-projections`** (LP & LP-DiD / 局部投影与 LP-DiD) | 高频面板/宏观动态脉冲响应分析或带有动态滞后项的多期冲击 | 各前瞻步数 ($h=0..H$) 动态脉冲响应带 (IRF)、Driscoll-Kraay 稳健标准误——避免传统 VAR 偏误与 LP-DiD 估计 |

---

## 04_robustness —— 稳健性检验层

**这块解决的问题**：基准结果算出来了，但不能只看一次就下结论，得证明它不是偶然、不是设定敏感、不是趋势造成的假象。

**实现机制**：`robustness-router` 根据 `identification-strategy` 选定的具体方法，只调用该方法**专属**的检验组合，而不是机械地把所有稳健性检验都跑一遍（比如 RDD 不需要 Wild Cluster Bootstrap，DID 需要平行趋势相关的检验）。五个具体的检验/补救组件各管一段：

| Skill | 作用 | 触发/使用场景 |
|---|---|---|
| `robustness-router` | 编排调度，按识别策略路由到对应的检验组合 | 基准回归完成、系数显著之后 |
| `placebo` | 处理组随机置换 (In-space)、处理时间虚构提前/推后 (In-time)、RDD假Cutoff检验，输出安慰剂系数分布 | 排除不可观测混杂因素驱动结果的可能性 |
| `clustering` | 检查标准误聚类层级是否合理，少数 Cluster (G<30) 场景下用 Wild Cluster Bootstrap 修正 | 处理变量在更高行政/行业层级分配时 |
| `alternative-specification` | 逐步增减控制变量、替换变量度量方式、样本缩尾/剔除子样本、Oster(2019)遗漏变量敏感性bounds，同时是共线性防范规则的执行接口 | 需要证明结论不受特定设定或度量误差驱动 |
| `sensitivity-bounds` | 基于 Rambachan-Roth (2023) HonestDiD 框架，在平行趋势“没有完全通过但也没有完全崩坏”时，计算处理效应能承受多大程度的前趋势偏离（临界值 M*），产出补救路线图 | 由 `econometric-reviewer` 在🟡判定时调用，不会因为前趋势有点问题就直接判死刑 |

---

## 05_further-analysis —— 深度分析层

**这块解决的问题**：因果效应“存在”这件事确立之后，回答“对谁更有效”“是通过什么渠道起作用”这两个更进一步的问题。

**实现机制**：两个 skill 都依赖 `baseline-regression` 已经产出的基准模型，不重新做识别判断，而是在已确定的因果框架内做拓展分析。

| Skill | 作用 |
|---|---|
| `heterogeneity` | 通过分组回归或交互项，检验处理效应在不同群体/地区/时期/企业特征间是否存在差异，并做**组间系数差异的正式检验** (不是简单地看两组系数数值不一样就下结论) |
| `mechanism` | 检验政策效果的传导渠道，严格区分“相关性中介证据”和“真正的因果机制”，要求排除替代性传导解释后才能下结论 |

---

## 06_diagnostics —— 审稿人终审层

**这块解决的问题**：前面所有步骤跑完之后，这个结果到底能不能信，谁来做最后把关。

**实现机制**：`econometric-reviewer` 以顶刊审稿人视角综合评估识别假定是否成立、稳健性检验是否充分，依据一套明确的判定条件（如平行趋势 p<0.05、AR置信区间包含0且无边界、RDD密度+协变量双重突变）输出 🟢/🟡/🔴 三档判定。**关键在于它拥有否决权**：判 🔴 时不是简单地报警，而是输出结构化的 `{decision_level, rejected_strategy, rejection_reason, action: "TRIGGER_REROUTING"}`，这段结构化数据被 `empirical-router` 接住并写入否决历史，真正驱动系统回到 `identification-strategy` 重新选策略——而不是给出一个不了了之的警告文字。判 🟡 时则调用 `sensitivity-bounds` 走补救路线，不需要推倒重来。

| Skill | 作用 |
|---|---|
| `econometric-reviewer` | 输出🟢/🟡/🔴综合判定，🔴时拥有打回重选的否决权 |

---

## 07_replication —— 复现比对层

**这块解决的问题**：如果目标是复现已发表论文的结果，要精确定位“算出来的数字”和“论文里的数字”差在哪、差多少、为什么差。这一层和前面“识别策略对不对”是两件不同的事——即使方法完全选对了，复现结果依然可能因为样本筛选、固定效应设定、标准误算法这些细节不一致而对不上。

**实现机制**：`replication-tools` 依赖 `baseline-regression` 的输出，做的是纯粹的数值比对：提取论文表格里的系数与标准误，与本地复现结果对比，按公式 `|本地值-论文值| / |论文值| × 100%` 算出差异百分比，再依次核查样本量是否一致、固定效应维度是否一致、标准误聚类层级是否一致，最终给出“完全吻合 / 差异在容忍范围内 / 无法复现”三档结论。

| Skill | 作用 |
|---|---|
| `replication-tools` | 提取论文数字，与复现结果比对差异百分比，定位差异来源 (样本/固定效应/标准误) |

---

## 08_output —— 成果输出层

**这块解决的问题**：所有分析都完成、且通过了审稿人审查之后，把数值结果转换成能直接放进论文里的格式。

**实现机制**：`tables-and-figures` 不参与前面任何判断或估计，只在 `econometric-reviewer` 给出 🟢 判定之后被调用，把各环节产出的回归对象和统计量，转换成符合 AER/AEJ/QJE 排版规范的 LaTeX(booktabs) 表格、Markdown 表格，以及事件研究图、系数对比图等出版级图表。

| Skill | 作用 |
|---|---|
| `tables-and-figures` | 生成顶刊规范的 LaTeX/Markdown 表格与出版级图表 |

---

## 全局执行链路总览

```
00_router (总调度，维护否决历史)
   │
   ▼
01_data / data-audit  ──► 产出包含 11 类识别信号的结构化数据元数据 (不做估计)
   │
   ▼
03_identification / identification-strategy  ──► 依据元数据+优先级+否决历史，在 11 大估计器中选定主/备选策略 (不做估计)
   │
   ▼
03_identification / 11个具体估计器之一 (did / staggered-did / iv / rdd / synthetic-control / matching / shift-share / double-machine-learning / bunching-design / regression-kink-design / local-projections)
   │  ← 全系统第一次真正跑模型
   ▼
02_model / baseline-regression  ──► 产出标准化基准回归结果
   │
   ▼
04_robustness / robustness-router  ──► 按策略类型路由专属检验组合
   │        ├─ placebo / clustering / alternative-specification
   │        └─ (可选) 05_further-analysis / heterogeneity / mechanism
   ▼
06_diagnostics / econometric-reviewer  ──► 🟢/🟡/🔴 终审
   │
   ├─ 🟢 ──► 08_output / tables-and-figures ──► 出刊级成果
   ├─ 🟡 ──► 04_robustness / sensitivity-bounds ──► 补救路线图
   └─ 🔴 ──► 写入否决历史，退回 identification-strategy 重新选策略
```

`07_replication / replication-tools` 是独立于这条主链的旁支功能，仅在需要对标已发表论文数字时被单独调用。
