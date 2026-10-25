# -*- coding: utf-8 -*-
"""
论文 Word 导出内核（CSSCI 排版取向）

产出 .docx，解决交付物只有 md/tex、无法直接进投稿系统的问题。排版约定：

- 正文：宋体 / Times New Roman 小四（12pt），1.5 倍行距，首行缩进 2 字符
- 一级标题：黑体 14pt 加粗，段前段后各 0.5 行
- 二级标题：黑体 12pt 加粗
- 表格：三线表（顶线 + 表头下线 + 底线），无竖线、无内部横线
- 表题与注释：宋体小五（9pt），表题在表上方、注释在表下方
- 参考文献：悬挂缩进 2 字符，[1] 编号，宋体小四

所有样式由本模块显式设置，不依赖 Word 默认模板，避免跨机器排版漂移。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

BODY_FONT_CN = "宋体"
BODY_FONT_EN = "Times New Roman"
HEAD_FONT_CN = "黑体"
BODY_SIZE = Pt(12)          # 小四
NOTE_SIZE = Pt(9)           # 小五
H1_SIZE = Pt(14)
H2_SIZE = Pt(12)

SECTION_LABELS: Dict[str, str] = {
    "abstract": "摘要",
    "keywords": "关键词",
    "introduction": "一、引言",
    "literature_review": "二、文献综述",
    "theory_hypotheses": "三、理论分析与研究假说",
    "data_sample": "四、研究设计与数据说明",
    "identification": "五、识别策略",
    "results": "六、实证结果分析",
    "mechanism": "七、机制检验",
    "heterogeneity": "八、异质性分析",
    "robustness": "九、稳健性检验",
    "conclusion": "十、结论与政策建议",
    "policy": "十、结论与政策建议",
    "fit": "研究定位与贡献",
    "inference": "统计推断",
    "submission": "投稿材料清单",
    "references": "参考文献",
}

# 表题里常见的"表 1"之类编号，用于自动补"表 N"
_TABLE_NO_RE = re.compile(r"^\s*表\s*(\d+)")


# ---------------------------------------------------------------------------
# 底层样式工具
# ---------------------------------------------------------------------------

def _set_run_font(run, cn: str, en: str, size: Pt, bold: bool = False):
    run.font.name = en
    run.font.size = size
    run.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    # 中文字形必须靠 eastAsia 指定，否则 Word 会用西文字体渲染汉字
    rfonts.set(qn("w:eastAsia"), cn)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)


def _configure_base_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT_EN
    normal.font.size = BODY_SIZE
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), BODY_FONT_CN)
    rfonts.set(qn("w:ascii"), BODY_FONT_EN)
    rfonts.set(qn("w:hAnsi"), BODY_FONT_EN)

    for sec in doc.sections:
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(3.17)
        sec.right_margin = Cm(3.17)


def _no_table_borders(table) -> None:
    """清掉 Word 默认的全框线，三线由 _cell_border 单独补"""
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tbl_pr.append(borders)


def _cell_border(cell, edges: Dict[str, Dict[str, Any]]) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.find(qn("w:tcBorders"))
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge, attrs in edges.items():
        el = tc_borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tc_borders.append(el)
        for k, v in attrs.items():
            el.set(qn(f"w:{k}"), str(v))


_TOP_RULE = {"val": "single", "sz": 12, "color": "000000"}     # 1.5pt 顶线
_MID_RULE = {"val": "single", "sz": 6, "color": "000000"}      # 0.75pt 表头下线
_BOT_RULE = {"val": "single", "sz": 12, "color": "000000"}     # 1.5pt 底线


def _apply_three_line_borders(table) -> None:
    _no_table_borders(table)
    n_rows = len(table.rows)
    for j, cell in enumerate(table.rows[0].cells):
        _cell_border(cell, {"top": _TOP_RULE, "bottom": _MID_RULE})
    for j, cell in enumerate(table.rows[-1].cells):
        _cell_border(cell, {"bottom": _BOT_RULE})


# ---------------------------------------------------------------------------
# Markdown 解析
# ---------------------------------------------------------------------------

def _is_table_separator(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|"):
        return False
    return bool(re.fullmatch(r"\|[\s:\-\|]+\|", s))


def _split_md_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_markdown_tables(md: str) -> List[Tuple[int, int, List[List[str]]]]:
    """返回 [(起始行号, 结束行号, 二维单元格)]，供按块切分正文使用"""
    lines = md.split("\n")
    blocks: List[Tuple[int, int, List[List[str]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            rows: List[List[str]] = [_split_md_row(lines[i])]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(_split_md_row(lines[j]))
                j += 1
            blocks.append((i, j - 1, rows))
            i = j
        else:
            i += 1
    return blocks


def _clean_inline(text: str) -> str:
    """
    去掉 markdown 强调标记，但**保留回归表里 ***/** 这类显著性星号**。
    只处理包裹式强调（**x** / *x*）与不影响星号语义的成对 ** 标记。
    """
    t = text.strip().replace("`", "")
    t = re.sub(r"^\*\*(.+)\*\*$", r"\1", t, flags=re.DOTALL)
    t = re.sub(r"^\*(.+)\*$", r"\1", t, flags=re.DOTALL)
    # 去掉孤立的 ** 强调，但不碰 *** 显著性标记
    t = re.sub(r"(?<!\*)\*\*(?!\*)", "", t)
    return t.strip()


# ---------------------------------------------------------------------------
# 段落与表格渲染
# ---------------------------------------------------------------------------

def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(12 if level == 1 else 8)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.5
    run = p.add_run(text)
    _set_run_font(run, HEAD_FONT_CN, BODY_FONT_EN, H1_SIZE if level == 1 else H2_SIZE, bold=True)


def _add_body_paragraph(doc: Document, text: str, indent: bool = True, size: Pt = BODY_SIZE) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(0)
    if indent:
        pf.first_line_indent = Pt(size.pt * 2)   # 首行缩进 2 字符
    run = p.add_run(text)
    _set_run_font(run, BODY_FONT_CN, BODY_FONT_EN, size)


def _add_note(doc: Document, text: str, align_left: bool = True) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.0
    pf.space_after = Pt(6)
    run = p.add_run(text)
    _set_run_font(run, BODY_FONT_CN, BODY_FONT_EN, NOTE_SIZE)


def _add_table_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    _set_run_font(run, HEAD_FONT_CN, BODY_FONT_EN, NOTE_SIZE, bold=True)


def _add_markdown_table(doc: Document, rows: Sequence[Sequence[str]], caption: str = "") -> None:
    if not rows:
        return
    n_cols = max(len(r) for r in rows)
    if caption:
        _add_table_caption(doc, caption)
    table = doc.add_table(rows=len(rows), cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    for i, row in enumerate(rows):
        for j in range(n_cols):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.0
            if i == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif j == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            val = _clean_inline(row[j]) if j < len(row) else ""
            run = p.add_run(val)
            _set_run_font(run, BODY_FONT_CN, BODY_FONT_EN, NOTE_SIZE, bold=(i == 0))
    _apply_three_line_borders(table)


def _render_markdown_block(doc: Document, md: str, table_no: List[int]) -> None:
    """把一段 markdown 正文渲染进 docx；遇到表格自动编号成三线表"""
    lines = md.split("\n")
    blocks = parse_markdown_tables(md)
    table_ranges = {(s, e): rows for s, e, rows in blocks}

    i = 0
    buf: List[str] = []
    while i < len(lines):
        hit = None
        for (s, e), rows in table_ranges.items():
            if s <= i <= e:
                hit = (s, e, rows)
                break
        if hit:
            s, e, rows = hit
            # 表格紧邻的上一行若是"表 1 xxx"之类的题注，取作表题。
            # 必须在 flush 之前判断并从缓冲里摘掉，否则题注会先被当正文输出一遍。
            caption = ""
            # 题注常被一个空行与表格隔开，所以向上跳过空行再找"表 N ..."
            k = s - 1
            steps = 0
            while k >= 0 and steps < 3:
                prev = lines[k].strip()
                if prev:
                    if not prev.startswith("|") and _TABLE_NO_RE.match(prev) and len(prev) <= 60:
                        caption = prev
                        for _ in range(s - k):
                            if buf:
                                buf.pop()
                    break
                k -= 1
                steps += 1
            _flush_paragraphs(doc, buf)
            buf = []
            if not caption:
                table_no[0] += 1
                caption = f"表 {table_no[0]}"
            _add_markdown_table(doc, rows, caption)
            # 表格后紧跟的 *注：...* 作为表注
            if e + 1 < len(lines) and lines[e + 1].strip().startswith("*注"):
                _add_note(doc, _clean_inline(lines[e + 1]))
            i = e + 1
            continue
        buf.append(lines[i])
        i += 1
    _flush_paragraphs(doc, buf)


def _flush_paragraphs(doc: Document, buf: List[str]) -> None:
    for raw in buf:
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            _add_heading(doc, stripped.lstrip("# ").strip(), level=1 if level <= 2 else 2)
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            _add_body_paragraph(doc, "· " + _clean_inline(stripped[2:]), indent=True)
            continue
        _add_body_paragraph(doc, _clean_inline(stripped), indent=True)


# ---------------------------------------------------------------------------
# 参考文献
# ---------------------------------------------------------------------------

def _format_reference(rec: Dict[str, Any]) -> str:
    """按中文期刊通行格式（近似 GB/T 7714）拼一条文献"""
    authors = rec.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in re.split(r"[,，;；]", authors) if a.strip()]
    authors = [a for a in authors if a][:6]
    author_txt = "，".join(authors) + ("，等" if len(authors) == 6 and len(rec.get("authors") or []) > 6 else "")
    if not author_txt:
        author_txt = "佚名"
    year = rec.get("year") or "n.d."
    title = (rec.get("title") or "").strip().rstrip(".")
    venue = (rec.get("venue") or rec.get("source") or "").strip()
    parts = [f"{author_txt}. {title}"]
    if venue:
        parts.append(f". {venue}")       # 中文期刊：题名. 刊名, 年
    parts.append(f", {year}")
    if rec.get("doi"):
        parts.append(f". DOI:{rec['doi']}")
    elif rec.get("url"):
        parts.append(f". {rec['url']}")
    return "".join(parts) + "."


def _add_references(doc: Document, records: Iterable[Dict[str, Any]]) -> None:
    recs = [r for r in records if r]
    if not recs:
        return
    _add_heading(doc, "参考文献", level=1)
    for idx, rec in enumerate(recs, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(0)
        # 悬挂缩进：左缩进 2 字符，首行反向缩进 2 字符
        pf.left_indent = Pt(BODY_SIZE.pt * 2)
        pf.first_line_indent = Pt(-BODY_SIZE.pt * 2)
        run = p.add_run(f"[{idx}] " + _format_reference(rec))
        _set_run_font(run, BODY_FONT_CN, BODY_FONT_EN, BODY_SIZE)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def export_paper_docx(
    title: str,
    sections: Dict[str, str],
    out_path: str,
    journal: str = "",
    references: Optional[List[Dict[str, Any]]] = None,
    extra_tables: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    把论文草稿导出为 CSSCI 取向的 Word 文档。

    :param sections: {章节键: markdown 正文}
    :param extra_tables: {表题: markdown 表格文本}，用于把实证交付物的三线表附在正文后
    """
    doc = Document()
    _configure_base_styles(doc)

    # 标题
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(title or "未命名论文")
    _set_run_font(run, HEAD_FONT_CN, BODY_FONT_EN, Pt(16), bold=True)

    if journal:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(12)
        run = p.add_run(f"—— 目标期刊：{journal}")
        _set_run_font(run, BODY_FONT_CN, BODY_FONT_EN, NOTE_SIZE)
        run.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    table_no = [0]
    for key, body in (sections or {}).items():
        heading = SECTION_LABELS.get(key, key)
        _add_heading(doc, heading, level=1)
        _render_markdown_block(doc, body or "", table_no)

    if extra_tables:
        _add_heading(doc, "附表：实证结果", level=1)
        for cap, md in extra_tables.items():
            for _s, _e, rows in parse_markdown_tables(md or ""):
                _add_markdown_table(doc, rows, cap)
                break

    _add_references(doc, references or [])

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return {
        "path": str(out),
        "file_name": out.name,
        "size_bytes": out.stat().st_size,
        "n_sections": len(sections or {}),
        "n_references": len(references or []),
    }


def build_extra_tables(deliverables: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """从实证交付物清单里抽出 markdown 表格文本"""
    out: Dict[str, str] = {}
    if not deliverables:
        return out
    tables = deliverables.get("tables") or {}
    labels = {
        "table1_descriptive_stats": "表 1 描述性统计",
        "descriptive_stats": "表 1 描述性统计",
        "table2_baseline_regression": "表 2 基准回归",
        "three_line_table": "表 3 回归结果（三线表）",
    }
    for name, info in tables.items():
        if not isinstance(info, dict):
            continue
        md_path = info.get("path") or info.get("markdown_path")
        if not md_path:
            continue
        try:
            text = Path(md_path).read_text(encoding="utf-8")
        except Exception:
            continue
        stem = Path(str(md_path)).stem
        out[labels.get(stem, f"表 {stem}")] = text
    return out
