# -*- coding: utf-8 -*-
"""
期刊格式档案库

把 formats/ 下六份期刊技能包注册为可查询的档案，
写作智能体按需把对应章节的 SKILL.md 载入系统提示，而不是靠模板拼字符串。

已接入：经济研究 / 管理世界 / 中国工业经济 / 经济学（季刊） / 金融研究 / AER。
其中 AER 为英文顶刊通道（本仓库依据 AEA 公开指南自建章节骨架）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("journal_profiles")

PART3_ROOT = Path(__file__).resolve().parents[1] / "part3-文献综述"
FORMATS_ROOT = PART3_ROOT / "formats"


# 标准章节 -> 各期刊对应技能文件（相对技能包根目录）
JOURNALS: Dict[str, Dict[str, Any]] = {
    "经济研究": {
        "package_root": FORMATS_ROOT / "经济研究" / "经济研究",
        "skill_prefix": "er-",
        "sections": {
            "workflow": "skills/er-workflow/SKILL.md",
            "style": "skills/er-style/SKILL.md",
            "abstract": "skills/er-abstract/SKILL.md",
            "introduction": "skills/er-introduction/SKILL.md",
            "theory_hypotheses": "skills/er-theory-hypotheses/SKILL.md",
            "literature_review": "skills/er-literature-review/SKILL.md",
            "data_sample": "skills/er-data-sample/SKILL.md",
            "identification": "skills/er-identification/SKILL.md",
            "results": "skills/er-tables-figures/SKILL.md",
            "mechanism": "skills/er-mechanism/SKILL.md",
            "heterogeneity": "skills/er-heterogeneity/SKILL.md",
            "robustness": "skills/er-robustness/SKILL.md",
            "policy": "skills/er-policy-implication/SKILL.md",
        },
        "exemplars": "resources/worked-examples",
    },
    "管理世界": {
        "package_root": FORMATS_ROOT / "管理世界" / "管理世界",
        "skill_prefix": "mw-",
        "sections": {
            "workflow": "skills/mw-workflow/SKILL.md",
            "topic": "skills/mw-topic-selection/SKILL.md",
            "institutional_background": "skills/mw-institutional-background/SKILL.md",
            "literature_review": "skills/mw-literature-review/SKILL.md",
            "identification": "skills/mw-identification/SKILL.md",
            "results": "skills/mw-tables-figures/SKILL.md",
            "mechanism": "skills/mw-mechanism-heterogeneity/SKILL.md",
            "policy": "skills/mw-policy-implication/SKILL.md",
            "submission": "skills/mw-submission/SKILL.md",
        },
        "exemplars": "resources/worked-examples",
    },
    "中国工业经济": {
        "package_root": FORMATS_ROOT / "中国工业经济" / "中国工业经济",
        "skill_prefix": "cie-",
        "sections": {
            "workflow": "skills/cie-workflow/SKILL.md",
            "fit": "skills/cie-fit-positioning/SKILL.md",
            "topic": "skills/cie-topic-selection/SKILL.md",
            "institutional_background": "skills/cie-institutional-background/SKILL.md",
            "literature_review": "skills/cie-literature-review/SKILL.md",
            "identification": "skills/cie-did-identification/SKILL.md",
            "results": "skills/cie-tables-figures/SKILL.md",
            "mechanism": "skills/cie-mechanism/SKILL.md",
            "heterogeneity": "skills/cie-heterogeneity/SKILL.md",
            "robustness": "skills/cie-robustness/SKILL.md",
            "policy": "skills/cie-policy-implication/SKILL.md",
            "rebuttal": "skills/cie-rebuttal/SKILL.md",
            "submission": "skills/cie-submission/SKILL.md",
        },
        "exemplars": "resources/worked-examples",
    },
    "经济学（季刊）": {
        "package_root": FORMATS_ROOT / "经济学（季刊）" / "经济学（季刊）",
        "skill_prefix": "ceq-",
        "sections": {
            "workflow": "skills/ceq-workflow/SKILL.md",
            "fit": "skills/ceq-fit-positioning/SKILL.md",
            "topic": "skills/ceq-topic-selection/SKILL.md",
            "literature_review": "skills/ceq-literature-review/SKILL.md",
            "identification": "skills/ceq-identification/SKILL.md",
            "modern_did": "skills/ceq-modern-did/SKILL.md",
            "inference": "skills/ceq-inference/SKILL.md",
            "robustness": "skills/ceq-inference/SKILL.md",
            "mechanism": "skills/ceq-mechanism/SKILL.md",
            "results": "skills/ceq-figures/SKILL.md",
            "abstract": "skills/ceq-abstract-english/SKILL.md",
            "rebuttal": "skills/ceq-rebuttal/SKILL.md",
            "submission": "skills/ceq-submission/SKILL.md",
        },
        "exemplars": "resources/worked-examples",
    },
    "金融研究": {
        "package_root": FORMATS_ROOT / "金融研究" / "金融研究",
        "skill_prefix": "jfr-",
        "sections": {
            "workflow": "skills/jfr-workflow/SKILL.md",
            "fit": "skills/jfr-fit-positioning/SKILL.md",
            "topic": "skills/jfr-topic-selection/SKILL.md",
            "institutional_background": "skills/jfr-institutional-background/SKILL.md",
            "literature_review": "skills/jfr-literature-review/SKILL.md",
            "identification": "skills/jfr-identification/SKILL.md",
            "results": "skills/jfr-tables-figures/SKILL.md",
            "mechanism": "skills/jfr-mechanism/SKILL.md",
            "heterogeneity": "skills/jfr-heterogeneity/SKILL.md",
            "policy": "skills/jfr-policy-implication/SKILL.md",
            "rebuttal": "skills/jfr-rebuttal/SKILL.md",
            "submission": "skills/jfr-submission/SKILL.md",
        },
        "exemplars": "resources/worked-examples",
    },
    "AER": {
        "package_root": FORMATS_ROOT / "AER" / "AER",
        "skill_prefix": "aer-",
        "sections": {
            "workflow": "skills/aer-workflow/SKILL.md",
            "fit": "skills/aer-fit-positioning/SKILL.md",
            "abstract": "skills/aer-abstract/SKILL.md",
            "introduction": "skills/aer-introduction/SKILL.md",
            "identification": "skills/aer-identification/SKILL.md",
            "inference": "skills/aer-inference/SKILL.md",
            "robustness": "skills/aer-inference/SKILL.md",
            "results": "skills/aer-tables-figures/SKILL.md",
            "data_sample": "skills/aer-data-availability/SKILL.md",
            "submission": "skills/aer-submission/SKILL.md",
        },
        "exemplars": "resources",
    },
}

DEFAULT_JOURNAL = "经济研究"

# 期刊的展示元信息（前端下拉与运行留痕用）
JOURNAL_META: Dict[str, Dict[str, str]] = {
    "经济研究": {"lang": "zh", "field": "经济学综合", "note": "CSSCI 经济学顶刊"},
    "管理世界": {"lang": "zh", "field": "管理学综合", "note": "CSSCI 管理学期刊"},
    "中国工业经济": {"lang": "zh", "field": "产业经济", "note": "实证工程化取向"},
    "经济学（季刊）": {"lang": "zh", "field": "经济学（国际范式）", "note": "识别规范性要求最高"},
    "金融研究": {"lang": "zh", "field": "金融学", "note": "宏观金融 / 公司金融双线"},
    "AER": {"lang": "en", "field": "Economics (top-5)", "note": "英文顶刊通道"},
}

# 全文写作的章节顺序
PAPER_SECTIONS: List[str] = [
    "abstract",
    "introduction",
    "literature_review",
    "theory_hypotheses",
    "data_sample",
    "identification",
    "results",
    "mechanism",
    "heterogeneity",
    "robustness",
    "policy",
]


def available_journals() -> List[str]:
    return [j for j, cfg in JOURNALS.items() if (cfg["package_root"] / cfg["sections"]["workflow"]).exists()]


def load_journal_skill(journal: str, section: str) -> Optional[str]:
    """读取指定期刊指定章节的写作规范；不存在则返回 None"""
    cfg = JOURNALS.get(journal) or JOURNALS.get(DEFAULT_JOURNAL)
    rel = cfg["sections"].get(section)
    if not rel:
        return None
    path = cfg["package_root"] / rel
    if not path.exists():
        logger.warning("期刊 %s 的章节规范缺失: %s", journal, path)
        return None
    return path.read_text(encoding="utf-8")


def load_journal_context(journal: str, sections: List[str]) -> str:
    """拼接多个章节的写作规范，作为系统提示的期刊约束部分"""
    parts: List[str] = [f"# 目标期刊：{journal}", ""]
    for s in sections:
        text = load_journal_skill(journal, s)
        if text:
            parts.append(f"\n## 章节规范：{s}\n\n{text}\n")
    return "\n".join(parts)


def journal_catalog() -> List[Dict[str, Any]]:
    """给前端下拉用的期刊清单（含章节与元信息），只列真正可用的"""
    out: List[Dict[str, Any]] = []
    for name in available_journals():
        cfg = JOURNALS[name]
        meta = JOURNAL_META.get(name, {})
        missing = [
            s for s, rel in cfg["sections"].items()
            if not (cfg["package_root"] / rel).exists()
        ]
        out.append({
            "journal": name,
            "label": f"《{name}》" if meta.get("lang", "zh") == "zh" else name,
            "lang": meta.get("lang", "zh"),
            "field": meta.get("field", ""),
            "note": meta.get("note", ""),
            "sections": sections_for_journal(name),
            "n_skills": len(cfg["sections"]),
            "missing": missing,
        })
    return out


def sections_for_journal(journal: str) -> List[str]:
    """返回该期刊支持的章节顺序（与 PAPER_SECTIONS 取交集后保序）"""
    cfg = JOURNALS.get(journal) or JOURNALS.get(DEFAULT_JOURNAL)
    supported = set(cfg["sections"].keys())
    ordered = [s for s in PAPER_SECTIONS if s in supported]
    extra = [s for s in cfg["sections"] if s not in PAPER_SECTIONS and s not in ("workflow", "style")]
    return ordered + extra
