# -*- coding: utf-8 -*-
"""草稿箱 API：草稿的增删改查 + 按六大期刊格式重排 + 导出 Word。

设计要点：
- 草稿存 data/drafts.json（单文件 + 线程锁），多人小规模够用；
- 「调格式」不是套模板字符串，而是按 journal_profiles 里该刊支持的章节顺序
  重排、补编号、给出该刊对应的章节名，再由前端按期刊排版样式渲染；
- 导出复用 core/docx_export.export_paper_docx（三线表、悬挂缩进等已实现）。
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.docx_export import export_paper_docx
from core.journal_profiles import available_journals, journal_catalog, sections_for_journal
from core.paths import INTEGRATED_ROOT

router = APIRouter(prefix="/api/drafts", tags=["drafts"])

DATA_DIR = INTEGRATED_ROOT / "data"
DRAFTS_FILE = DATA_DIR / "drafts.json"
EXPORT_DIR = INTEGRATED_ROOT / "part2-empirical-research" / "deliverables" / "drafts"
_LOCK = threading.Lock()

# 章节键 → 中文名（英文刊用英文名）
SECTION_LABELS_ZH = {
    "abstract": "摘要",
    "introduction": "引言",
    "literature_review": "文献综述",
    "theory_hypotheses": "理论分析与研究假说",
    "data_sample": "研究设计与数据",
    "identification": "识别策略",
    "results": "实证结果",
    "mechanism": "机制分析",
    "heterogeneity": "异质性分析",
    "robustness": "稳健性检验",
    "policy": "结论与政策启示",
}
SECTION_LABELS_EN = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "literature_review": "Literature Review",
    "theory_hypotheses": "Theory and Hypotheses",
    "data_sample": "Data and Sample",
    "identification": "Identification",
    "results": "Results",
    "mechanism": "Mechanism",
    "heterogeneity": "Heterogeneity",
    "robustness": "Robustness",
    "policy": "Conclusion",
}

# 标题关键词 → 章节键（按顺序匹配，先具体后笼统）
KEYWORD_RULES: List[tuple] = [
    ("abstract", ("摘要", "abstract")),
    ("introduction", ("引言", "导论", "introduction")),
    ("literature_review", ("文献综述", "文献回顾", "literature")),
    ("theory_hypotheses", ("理论分析", "假说", "hypothes", "theory")),
    ("data_sample", ("研究设计", "数据来源", "样本", "变量说明", "data", "sample")),
    ("identification", ("识别策略", "识别", "identification", "empirical strategy")),
    ("results", ("实证结果", "基准回归", "回归结果", "results", "baseline")),
    ("mechanism", ("机制", "mechanism", "channel")),
    ("heterogeneity", ("异质性", "heterogeneity")),
    ("robustness", ("稳健", "robust")),
    ("policy", ("结论", "政策建议", "政策启示", "conclusion", "policy")),
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _load() -> List[Dict[str, Any]]:
    if not DRAFTS_FILE.exists():
        return []
    try:
        data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DRAFTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DRAFTS_FILE)


def _meta(d: Dict[str, Any]) -> Dict[str, Any]:
    content = d.get("content", "") or ""
    return {
        "id": d.get("id"),
        "title": d.get("title") or "未命名草稿",
        "journal": d.get("journal") or (available_journals()[0] if available_journals() else ""),
        "project_id": d.get("project_id", ""),
        "word_count": len(re.sub(r"\s", "", content)),
        "updated_at": d.get("updated_at"),
        "created_at": d.get("created_at"),
    }


def _find(items: List[Dict[str, Any]], draft_id: str) -> Dict[str, Any]:
    for d in items:
        if d.get("id") == draft_id:
            return d
    raise HTTPException(status_code=404, detail="草稿不存在")


def _split_sections(content: str) -> List[Dict[str, str]]:
    """按 markdown 标题切分（支持 # / ## / 一、 形式），返回 [{heading, body}]。"""
    lines = (content or "").replace("\r\n", "\n").split("\n")
    blocks: List[Dict[str, str]] = []
    cur = {"heading": "", "body": []}  # type: Dict[str, Any]
    heading_re = re.compile(r"^\s{0,3}(#{1,4})\s+(.*)$")
    zh_num_re = re.compile(r"^\s*([一二三四五六七八九十]+)[、.．]\s*(.+)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            if cur["heading"] or cur["body"]:
                blocks.append({"heading": cur["heading"], "body": "\n".join(cur["body"]).strip()})
            cur = {"heading": m.group(2).strip(), "body": []}
            continue
        m2 = zh_num_re.match(line)
        if m2 and len(line.strip()) <= 30:
            if cur["heading"] or cur["body"]:
                blocks.append({"heading": cur["heading"], "body": "\n".join(cur["body"]).strip()})
            cur = {"heading": line.strip(), "body": []}
            continue
        cur["body"].append(line)

    if cur["heading"] or cur["body"]:
        blocks.append({"heading": cur["heading"], "body": "\n".join(cur["body"]).strip()})
    return [b for b in blocks if b["heading"] or b["body"]]


def _match_key(heading: str) -> Optional[str]:
    low = (heading or "").lower()
    for key, words in KEYWORD_RULES:
        for w in words:
            if w.lower() in low:
                return key
    return None


class DraftIn(BaseModel):
    title: Optional[str] = "未命名草稿"
    journal: Optional[str] = ""
    content: Optional[str] = ""
    project_id: Optional[str] = ""


class DraftPatch(BaseModel):
    title: Optional[str] = None
    journal: Optional[str] = None
    content: Optional[str] = None


@router.get("")
async def list_drafts():
    with _LOCK:
        items = _load()
    return {"drafts": [_meta(d) for d in sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)]}


@router.post("")
async def create_draft(req: DraftIn):
    journals = available_journals()
    journal = req.journal or (journals[0] if journals else "")
    draft = {
        "id": f"draft-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}",
        "title": (req.title or "未命名草稿").strip() or "未命名草稿",
        "journal": journal,
        "content": req.content or "",
        "project_id": req.project_id or "",
        "created_at": _now(),
        "updated_at": _now(),
    }
    with _LOCK:
        items = _load()
        items.append(draft)
        _save(items)
    return {"draft": {**draft, **_meta(draft)}}


@router.get("/{draft_id}")
async def get_draft(draft_id: str):
    with _LOCK:
        d = _find(_load(), draft_id)
    return {"draft": d}


@router.put("/{draft_id}")
async def update_draft(draft_id: str, req: DraftPatch):
    with _LOCK:
        items = _load()
        d = _find(items, draft_id)
        if req.title is not None:
            d["title"] = req.title.strip() or "未命名草稿"
        if req.journal is not None:
            d["journal"] = req.journal
        if req.content is not None:
            d["content"] = req.content
        d["updated_at"] = _now()
        _save(items)
    return {"draft": d}


@router.delete("/{draft_id}")
async def delete_draft(draft_id: str):
    with _LOCK:
        items = _load()
        _find(items, draft_id)
        items = [d for d in items if d.get("id") != draft_id]
        _save(items)
    return {"status": "success", "deleted": draft_id}


@router.post("/{draft_id}/format")
async def format_draft(draft_id: str, journal: Optional[str] = None):
    """按目标期刊重排章节：返回该刊的章节顺序、编号与缺失章节。"""
    with _LOCK:
        d = _find(_load(), draft_id)
    target = journal or d.get("journal") or (available_journals()[0] if available_journals() else "")
    if target and target not in available_journals():
        raise HTTPException(status_code=400, detail=f"未知期刊：{target}")

    order = sections_for_journal(target) if target else []
    is_en = any(j.get("lang") == "en" for j in journal_catalog() if j.get("journal") == target)
    labels = SECTION_LABELS_EN if is_en else SECTION_LABELS_ZH

    blocks = _split_sections(d.get("content", ""))
    used: Dict[str, Dict[str, Any]] = {}
    leftovers: List[Dict[str, Any]] = []
    for b in blocks:
        key = _match_key(b["heading"])
        if key and key not in used:
            used[key] = {"key": key, "heading": b["heading"], "body": b["body"]}
        else:
            leftovers.append({"key": "", "heading": b["heading"], "body": b["body"]})

    sections: List[Dict[str, Any]] = []
    for i, key in enumerate(order, start=1):
        if key in used:
            item = used.pop(key)
            sections.append({
                "key": key,
                "label": labels.get(key, key),
                "heading": item["heading"],
                "body": item["body"],
                "number": _num(i, is_en),
                "matched": True,
            })
    # 未识别的章节按原顺序附在最后
    idx = len(sections)
    for b in leftovers:
        if not b["heading"] and not b["body"]:
            continue
        idx += 1
        sections.append({
            "key": "",
            "label": b["heading"] or "未命名章节",
            "heading": b["heading"],
            "body": b["body"],
            "number": _num(idx, is_en),
            "matched": False,
        })

    missing = [labels.get(k, k) for k in order if k not in {s["key"] for s in sections}]
    return {
        "journal": target,
        "lang": "en" if is_en else "zh",
        "title": d.get("title") or "未命名草稿",
        "sections": sections,
        "missing_sections": missing,
        "word_count": len(re.sub(r"\s", "", d.get("content", ""))),
    }


def _num(i: int, is_en: bool) -> str:
    if is_en:
        return f"{i}."
    zh = "一二三四五六七八九十"
    if i <= 10:
        return f"{zh[i - 1]}、"
    return f"{i}."


@router.post("/{draft_id}/export")
async def export_draft(draft_id: str, journal: Optional[str] = None):
    """按目标期刊格式导出 Word，返回可下载的 /deliverables 路径。"""
    with _LOCK:
        d = _find(_load(), draft_id)
    target = journal or d.get("journal") or ""
    fmt = await format_draft(draft_id, target)

    sections_md: Dict[str, str] = {}
    for s in fmt["sections"]:
        body = s["body"] or ""
        sections_md[s["label"]] = body

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\u4e00-\u9fa5-]+", "_", d.get("title") or "draft")[:40]
    out_path = EXPORT_DIR / f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    try:
        export_paper_docx(
            title=fmt["title"],
            sections=sections_md,
            out_path=str(out_path),
            journal=target,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"导出失败：{exc}")

    return {
        "status": "success",
        "path": out_path.name,
        "url": f"/deliverables/drafts/{out_path.name}",
        "journal": target,
    }
