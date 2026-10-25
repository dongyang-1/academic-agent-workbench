# -*- coding: utf-8 -*-
"""
中文文献通道

背景：part1 的 CNKI / 万方 / 维普 等中文源属于 MANUAL_SEARCH_CONFIG，
只拼跳转链接、不返回记录——做中文课题时等于主战场缺位。本模块补上三条真实路径：

1. 联网检索：OpenAlex + Crossref 支持中文检索式，能真实返回记录，
   但中文期刊收录不全（多数 CSSCI 期刊没有 DOI 或未进这两个库），
   因此返回值里一定会带 coverage_note 如实说明覆盖边界，不假装"搜全了"。
2. 手动库跳转：CNKI / 万方 / 维普 / 国家哲学社会科学文献中心，
   带预填检索式的一键直达（这些库有登录墙，程序化抓取既违规也不可靠）。
3. 回导：把从上述库导出的 RIS / BibTeX / EndNote 文件解析回统一记录结构，
   让手动检索的结果能进入同一个结果列表、一起导出与写入 Zotero。

设计原则：能真抓的真抓，抓不到就说清楚是抓不到，不用假数据充数。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

UA = "AcademicWorkflow/1.0 (mailto:user@example.com)"
TIMEOUT = 20

# 手动检索库：带登录墙，无法程序化抓取，只能跳转 + 导出后回导
MANUAL_LIBRARIES: List[Dict[str, str]] = [
    {
        "id": "cnki",
        "name": "中国知网 CNKI",
        "url": "https://kns.cnki.net/kns8s/defaultresult/index?kw={q}",
        "note": "中文期刊覆盖最全；需机构登录。导出 EndNote/RIS 后回导到本页。",
        "export_hint": "检索结果页 → 批量导出 → EndNote（.enw）或 RefWorks（.ris）",
    },
    {
        "id": "wanfang",
        "name": "万方数据",
        "url": "https://s.wanfangdata.com.cn/paper?q={q}",
        "note": "学位论文与会议论文较强；部分全文需登录。",
        "export_hint": "结果页 → 导出 → EndNote / BibTeX",
    },
    {
        "id": "cqvip",
        "name": "维普期刊",
        "url": "http://qikan.cqvip.com/Qikan/Search/Index?key={q}",
        "note": "中文期刊回溯较早，可与知网互为补充。",
        "export_hint": "结果页 → 导出题录",
    },
    {
        "id": "nssd",
        "name": "国家哲学社会科学文献中心",
        "url": "http://www.nssd.cn/search?q={q}",
        "note": "免费开放，社科类中文文献可在线阅读，注册后可导出。",
        "export_hint": "结果页 → 导出题录",
    },
]


def manual_links(query: str) -> List[Dict[str, str]]:
    """生成带预填检索式的中文库直达链接"""
    q = urllib.parse.quote(query or "")
    out = []
    for lib in MANUAL_LIBRARIES:
        out.append({
            "id": lib["id"],
            "name": lib["name"],
            "url": lib["url"].format(q=q),
            "note": lib["note"],
            "export_hint": lib["export_hint"],
        })
    return out


# ---------------------------------------------------------------------------
# 联网检索（OpenAlex / Crossref，支持中文检索式，覆盖有限）
# ---------------------------------------------------------------------------

def _get_json(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def _make_record(title: str, authors, year, venue, doi, url, abstract, source, query) -> Dict[str, Any]:
    title = (title or "").strip() or "[missing title]"
    digest = hashlib.sha1(f"{source}:{doi or title}".encode("utf-8")).hexdigest()[:16]
    return {
        "record_id": f"cnlit-{digest}",
        "title": title,
        "authors": authors or [],
        "year": year,
        "venue": (venue or "").strip() or None,
        "issn": [],
        "source": source,
        "doi": doi,
        "external_ids": {},
        "source_record_ids": {source: doi or digest},
        "url": url,
        "abstract": (abstract or "").strip() or None,
        "abstract_snippet": None,
        "jel_codes": [],
        "methods": [],
        "publication_types": [],
        "fields_of_study": [],
        "data_context": None,
        "citation_count": None,
        "reference_count": None,
        "influential_citation_count": None,
        "is_open_access": None,
        "open_access_pdf_url": None,
        "retrieval_source": source,
        "retrieval_sources": [source],
        "retrieval_query": query,
        "dedupe_key": (doi or "").lower() or re.sub(r"[^a-z0-9一-鿿]+", "", title.lower()),
        "relevance_note": None,
        "verification_status": "metadata-only",
        "source_specific": {},
    }


def _search_openalex(query: str, limit: int, mailto: str = "") -> List[Dict[str, Any]]:
    url = (
        "https://api.openalex.org/works?search="
        + urllib.parse.quote(query)
        + f"&per-page={min(limit, 50)}&select=id,doi,title,display_name,publication_year,"
          "authorships,primary_location,cited_by_count,open_access"
    )
    if mailto:
        url += f"&mailto={urllib.parse.quote(mailto)}"
    data = _get_json(url)
    out = []
    for item in (data or {}).get("results", []):
        title = item.get("title") or item.get("display_name") or ""
        authors = [
            a.get("author", {}).get("display_name")
            for a in (item.get("authorships") or [])
            if a.get("author", {}).get("display_name")
        ]
        loc = item.get("primary_location") or {}
        src = (loc.get("source") or {})
        oa = item.get("open_access") or {}
        out.append(_make_record(
            title=title,
            authors=authors,
            year=item.get("publication_year"),
            venue=src.get("display_name"),
            doi=(item.get("doi") or "").replace("https://doi.org/", "") or None,
            url=item.get("doi") or item.get("id"),
            abstract=None,
            source="openalex-cn",
            query=query,
        ))
    return out


def _search_crossref(query: str, limit: int) -> List[Dict[str, Any]]:
    url = (
        "https://api.crossref.org/works?query="
        + urllib.parse.quote(query)
        + f"&rows={min(limit, 50)}&select=DOI,title,author,issued,container-title,URL,abstract"
    )
    data = _get_json(url)
    out = []
    for item in ((data or {}).get("message") or {}).get("items", []):
        title = (item.get("title") or [""])[0]
        authors = [
            " ".join(x for x in (a.get("given"), a.get("family")) if x)
            for a in (item.get("author") or [])
        ]
        year = None
        issued = item.get("issued", {}).get("date-parts", [[None]])[0]
        if issued:
            year = issued[0]
        venue = (item.get("container-title") or [""])[0] or None
        abstract = item.get("abstract")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract)
        out.append(_make_record(
            title=title, authors=authors, year=year, venue=venue,
            doi=item.get("DOI"), url=item.get("URL"), abstract=abstract,
            source="crossref-cn", query=query,
        ))
    return out


def search_cn(query: str, limit: int = 20, sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    中文检索。真实调用 OpenAlex / Crossref，并如实标注覆盖边界。
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("请填写中文检索式。")
    use = sources or ["openalex", "crossref"]
    records: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []

    for src in use:
        try:
            if src == "openalex":
                got = _search_openalex(query, limit)
            elif src == "crossref":
                got = _search_crossref(query, limit)
            else:
                continue
            records += got
            logs.append({"source": src, "n": len(got), "status": "ok"})
        except Exception as exc:  # noqa: BLE001
            logs.append({"source": src, "n": 0, "status": "error", "error": str(exc)[:200]})

    # 去重（按 dedupe_key）
    seen = set()
    deduped = []
    for r in records:
        k = r.get("dedupe_key")
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    return {
        "records": deduped,
        "logs": logs,
        "manual_links": manual_links(query),
        "coverage_note": (
            "联网中文检索走的是 OpenAlex / Crossref，二者对中文期刊收录有限："
            "多数 CSSCI 期刊未分配 DOI 或未入库，因此本结果**不能**视为中文文献全貌。"
            "要覆盖《经济研究》《管理世界》《中国工业经济》等中文顶刊，"
            "请用下方「中文库直达」跳转检索，导出题录后回导到本页统一管理。"
        ),
        "import_note": "回导支持 CNKI/万方/维普导出的 .ris / .bib / .enw（EndNote）文件。",
    }


# ---------------------------------------------------------------------------
# 题录回导：RIS / BibTeX / EndNote
# ---------------------------------------------------------------------------

def _split_authors(raw: str) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"\s+and\s+|;|；", raw)
    out = []
    for p in parts:
        p = p.strip().strip(",")
        if p:
            out.append(p)
    return out


def parse_ris(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    authors: List[str] = []

    def flush():
        nonlocal cur, authors
        if cur.get("title"):
            cur["authors"] = authors
            records.append(cur)
        cur, authors = {}, []

    for line in (text or "").splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("ER "):
            flush()
            continue
        if len(line) < 6 or line[2:6] != "  - ":
            continue
        tag = line[0:2].strip().upper()
        val = line[6:].strip()
        if tag in ("TI", "T1", "CT"):
            cur["title"] = val
        elif tag in ("AU", "A1", "A2"):
            authors.append(val)
        elif tag in ("PY", "Y1", "DA"):
            m = re.search(r"(\d{4})", val)
            if m:
                cur["year"] = int(m.group(1))
        elif tag in ("JO", "JF", "T2", "JA"):
            cur.setdefault("venue", val)
        elif tag == "DO":
            cur["doi"] = val
        elif tag == "UR":
            cur["url"] = val
        elif tag in ("AB", "N2"):
            cur["abstract"] = (cur.get("abstract") or "") + val
    flush()
    return records


def parse_bibtex(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for m in re.finditer(r"@(\w+)\s*\{[^,]*,(.*?)\n\}", text or "", re.DOTALL):
        body = m.group(2)
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}(?:,|$)", body, re.DOTALL):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        title = fields.get("title", "")
        if not title:
            continue
        year = None
        ym = re.search(r"(\d{4})", fields.get("year", ""))
        if ym:
            year = int(ym.group(1))
        records.append({
            "title": title,
            "authors": _split_authors(fields.get("author", "")),
            "year": year,
            "venue": fields.get("journal") or fields.get("booktitle"),
            "doi": fields.get("doi"),
            "url": fields.get("url"),
            "abstract": fields.get("abstract"),
        })
    return records


def parse_endnote(text: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    authors: List[str] = []

    def flush():
        nonlocal cur, authors
        if cur.get("title"):
            cur["authors"] = authors
            records.append(cur)
        cur, authors = {}, []

    for line in (text or "").splitlines():
        line = line.strip()
        if not line or len(line) < 3:
            continue
        tag, val = line[:2], line[3:].strip()
        if tag == "%0":
            flush()
            continue
        if tag == "%T":
            cur["title"] = val
        elif tag in ("%A", "%E"):
            authors.append(val)
        elif tag == "%D":
            m = re.search(r"(\d{4})", val)
            if m:
                cur["year"] = int(m.group(1))
        elif tag in ("%J", "%B"):
            cur.setdefault("venue", val)
        elif tag == "%R":
            cur["doi"] = val
        elif tag == "%U":
            cur["url"] = val
        elif tag == "%X":
            cur["abstract"] = (cur.get("abstract") or "") + val
    flush()
    return records


def parse_import(text: str, fmt: str = "auto") -> List[Dict[str, Any]]:
    """
    解析题录文件文本为统一记录结构。fmt: auto | ris | bibtex | endnote
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("文件内容为空。")
    if fmt == "auto":
        if text.lstrip().startswith("@"):
            fmt = "bibtex"
        elif "%0" in text[:200] or re.search(r"^%[A-Z] ", text, re.M):
            fmt = "endnote"
        else:
            fmt = "ris"

    if fmt == "bibtex":
        raw = parse_bibtex(text)
    elif fmt == "endnote":
        raw = parse_endnote(text)
    else:
        raw = parse_ris(text)

    out = []
    for r in raw:
        out.append(_make_record(
            title=r.get("title"),
            authors=r.get("authors") or [],
            year=r.get("year"),
            venue=r.get("venue"),
            doi=r.get("doi"),
            url=r.get("url"),
            abstract=r.get("abstract"),
            source="imported",
            query="",
        ))
    return out
