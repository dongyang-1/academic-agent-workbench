---
name: matching
name_zh: 倾向得分与精确匹配
description: 倾向得分匹配 (PSM) 与精确匹配，用于消除可观测协变量的选择偏误，并提供协变量平衡性检验。
category: 03_identification
priority: medium
inputs: [截面/面板数据集, 处理变量, 匹配协变量列表]
outputs: [倾向得分拟合结果, 匹配后数据子集, 协变量平衡性检验表(Love Plot), 共同范围图]
dependencies: [identification-strategy]
source_repository: Auto-Empirical-Research-Skills
source_path: skills/15-Felpix-Studios-social-science-research/
original_skill_name: data-analysis
license: CC-BY-SA-4.0
adaptation_status: adapted
---

# 倾向得分与精确匹配 (PSM & Matching)

## 一、 这个 Skill 是干什么的
`matching` 用于通过倾向得分匹配 (Propensity Score Matching, PSM) 或 Mahalanobis 精确匹配，消除处理组与对照组之间在**可观测协变量**上的选择偏误 (Selection Bias)。它评估共同范围 (Common Support) 假定，并生成协变量平衡性检验结果（Standardized Mean Differences, Love Plot）。

## 二、 什么时候使用
- 当处理组与对照组在背景特征上存在明显系统性差异；
- 常与 DID 结合使用 (PSM-DID)，先匹配剔除样本差异，再估计双重差分。

## 三、 什么时候不要使用
- 严禁将匹配作为解决不可观测内生性（遗漏变量、双向因果）的唯一手段；PSM 只能消除可观测变量的偏误。

## 四、 需要什么输入
1. 数据集；
2. 处理状态变量 $D$ (0/1)；
3. 匹配协变量向量 $X_{match}$；
4. 匹配参数（卡尺值 Caliper、近邻匹配数 $k$、有无放回）。

## 五、 匹配与检验流程
1. **倾向得分 Logit/Probit 估计**：$\hat{p}(X) = P(D=1 \mid X)$；
2. **共同范围假设检验 (Common Support)**：绘制处理组与对照组倾向得分概率密度图，剔除极端越界样本；
3. **近邻匹配执行**（1:1 或 1:k 卡尺匹配）；
4. **协变量平衡性检验**：
   - 计算匹配前后各协变量的标准化均值差 (Standardized Bias %)；
   - 要求匹配后所有协变量的绝对 Standardized Bias < 10%，且 $t$ 检验不显著。

## 六、 规范与提示
- **清楚识别前提**：强调 PSM 假设“基于可观测变量的可忽略性”(Selection on Observables)；
- **PSM-DID 注意事项**：若用于面板 PSM-DID，通常要求基于处理前基期特征进行单次匹配，避免动态匹配引入选择偏误。

## 七、 诊断要求
- 输出匹配前后 Standardized Bias 变化表（Love Plot）；
- 输出共同范围损失样本数统计。

## 八、 输出结果
- 匹配后的平稳数据集对象；
- 协变量平衡性检验表与倾向得分分布图。

## 九、 失败条件
- 匹配后大部分处理组单位不在共同范围内而被丢弃；
- 匹配后协变量标准化偏差依然高于 15%。

## 十、 底层工具
- Python: `causalml`, `statsmodels`, `scikit-learn`；
- Stata: `psmatch2`, `pstest`, `teffects psmatch`；
- R: `MatchIt`, `cobalt`.

## 十一、 来源与许可证信息
- 来源：AERS 匹配分析模块 / MatchIt 标准；
- 许可证：CC-BY-SA-4.0 License。

## 十二、 中文用户说明与防避坑指南
PSM 能够有效解决“苹果和桔子不能对比”的问题（让处理组和控制组特征尽可能相似）。但请注意，PSM 不能解决遗漏变量问题。因此，在社科研究中，通常推荐将 PSM 与 DID 结合（PSM-DID）使用。
