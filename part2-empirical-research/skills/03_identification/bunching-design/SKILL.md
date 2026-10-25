---
name: bunching-design
name_zh: 行为聚束分析设计
description: 基于 Saez(2010) 与 Kleven(2016) 框架，通过估计反事实无堆积密度分布，利用阈值处的行为聚束 (Bunching) 估计行为弹性。
category: 03_identification
priority: high
inputs: [连续观测数据, 政策阈值(Cutoff/Kink), 多项式拟合阶数, 聚束区间(Bunching Window)]
outputs: [反事实密度曲线, 超额堆积量(Excess Mass B), 结构弹性估计量, 引导抽样SE]
dependencies: [identification-strategy]
source_repository: Auto-Empirical-Research-Skills
source_path: skills/15-Felpix-Studios-social-science-research/
original_skill_name: data-analysis
license: CC-BY-SA-4.0
adaptation_status: adapted
---

# 行为聚束分析设计 (Bunching Design)

## 一、 这个 Skill 是干什么的
`bunching-design` 专门用于利用**政策在连续变量特定阈值（Cutoff 或 Kink）处产生的行为响应**进行因果推断与弹性估计。它遵循 Saez (2010) 与 Kleven (2016) 的理论框架，通过高阶多项式拟合剔除堆积区后的“反事实无堆积密度分布 (Counterfactual Density)”，精确计算阈值处的超额堆积量 ($B$, Excess Mass) 与缺口量 ($M$, Missing Mass)，进而推导经济主体的结构弹性（如劳动供给税收弹性、企业避税弹性）。

## 二、 什么时候使用
- 当政策在某个关键阈值（如税率档位、小微企业免税规模门槛、科研资助申报年龄线）产生边际激励变化；
- 当直方图或密度估计在阈值处显现出极其明显的“行为尖峰堆积 (Bunching Peak)”或“空缺 (Notch)”时。

## 三、 什么时候不要使用
- 当经济主体完全无法调整自身行为（缺少行为操纵能力），或者密度分布在阈值两侧完全平滑无堆积时。

## 四、 需要什么输入
1. 个体层级连续观测变量 $X$（如年收入、企业销售额、申请年龄）；
2. 政策发生变动的断点/档位值 $K$；
3. 聚束窗口区间 $[K - \delta_l, K + \delta_r]$；
4. 反事实多项式拟合阶数 $p$（通常取 3 至 7 阶）。

## 五、 Bunching 核心估计流程

```text
连续变量 X 直方图分箱 (Bins)
  │
  ├── 1. 排除聚束区间内的 Bin [K - delta_l, K + delta_r]
  │
  ├── 2. 用高阶多项式回归拟合剩余 Bin 的密度分布
  │      ──► 得到【反事实无堆积密度估计】 C_j(X)
  │
  ├── 3. 计算超额堆积量 B (Excess Mass)
  │      ──► B = Sum( Actual_Count_j - Counterfactual_Count_j )
  │
  └── 4. 结合制度规则推导结构弹性 (Elasticity e)
         └── 采用 Bootstrap (引导抽样) 计算 B 和 e 的标准误与 95% 置信区间。
```

## 六、 诊断与质量要求
- **反事实多项式阶数敏感性**：测试多项式阶数 $p \in [3, 7]$ 对超额堆积量 $b = B/C(K)$ 的影响；
- **聚束窗口界定敏感性**：改变聚束窗口左右边界，评估弹性的稳定性；
- **优化约束检验**：对于 Notch（档位跳跃），检查超额堆积量是否等于缺失量（积分平衡条件）。

## 七、 输出结果
- 超额堆积量 $b$（以反事实密度归一化）与结构弹性估计值及其 Bootstrap SE；
- 真实密度 vs 反事实密度对比图 (Bunching Plot)。

## 八、 失败条件
- 聚束窗口外的数据极端不平滑导致多项式拟合失真；
- 堆积区间内计数与反事实计数无统计差异 ($b \approx 0$)。

## 九、 底层工具
- Python: `scipy`, `statsmodels`, `numpy`；
- Stata: `bunching`；
- R: `bunching`.

## 十、 来源与许可证信息
- 来源：AERS / Saez (2010) & Kleven (2016)；
- 许可证：CC-BY-SA-4.0 License。

## 十一、 中文用户说明与防避坑指南
聚束分析是公共经济学和公司金融 top 期刊的“大杀器”。如果某个政策设置了免税门槛，很多企业会故意把销售额控制在门槛下方。本 Skill 能帮你画出经典的 Bunching 图，并算出企业的避税弹性，极具政策含义。
