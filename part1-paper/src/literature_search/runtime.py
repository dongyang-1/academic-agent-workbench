from __future__ import annotations

import ast
import csv
import hashlib
import html
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .journal_ranking import enrich_journal_rankings
from .quality import distribution_advisories, enrich_records, merge_records


AUTOMATED_SOURCES = ("crossref", "nber", "datacite", "arxiv", "core", "openalex", "econbiz", "world-bank")
MANUAL_SOURCES = (
    "google-scholar", "ssrn", "ideas-repec", "econpapers", "cepr", "iza", "cnki", "wanfang",
    "bfi", "siepr", "lse-cep",
)
AVAILABLE_SOURCES = AUTOMATED_SOURCES + MANUAL_SOURCES
USER_AGENT = "economics-research-agent/0.2 (non-commercial research prototype)"
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = WORKSPACE_ROOT / "_ai_temp" / "economics-research-agent-cache"
HttpGet = Callable[[str, int], bytes]


import ssl
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CONTEXT = ssl._create_unverified_context()

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_get(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_SSL_CONTEXT) as response:
                return response.read()
        except Exception as exc:  # Network failures vary by platform.
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (2**attempt))
    assert last_error is not None
    raise last_error


def _url(base: str, params: dict[str, Any]) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text or None


def _year(value: Any) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def _doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip().lower()
    if doi in {"null", "none", "na", "n/a"}:
        return None
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    return doi or None


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _author_names(value: Any) -> list[str]:
    names: list[str] = []

    def collect(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                collect(child)
            return
        if isinstance(item, dict):
            lowered = {str(key).lower(): child for key, child in item.items()}
            for key in ("name", "display_name", "fullname", "full_name", "author"):
                if key in lowered:
                    collect(lowered[key])
                    return
            return

        text = str(item).strip()
        if not text or text.lower() in {"null", "none", "n/a", "na", "unknown"}:
            return
        if text[:1] in {"{", "["}:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                parsed = None
            if parsed is not None and parsed != text:
                collect(parsed)
                return
        names.append(text)

    collect(value)
    return list(dict.fromkeys(names))


def _record(source: str, source_id: str, query: str, **values: Any) -> dict[str, Any]:
    title = _clean_text(values.get("title")) or "[missing title]"
    digest = hashlib.sha1(f"{source}:{source_id}".encode("utf-8")).hexdigest()[:16]
    doi = _doi(values.get("doi"))
    return {
        "record_id": f"lit-{digest}",
        "title": title,
        "authors": _author_names(values.get("authors", [])),
        "year": _year(values.get("year")),
        "venue": _clean_text(values.get("venue")),
        "issn": _string_list(values.get("issn")),
        "source": source,
        "doi": doi,
        "external_ids": values.get("external_ids", {}),
        "source_record_ids": {source: str(source_id)},
        "url": values.get("url"),
        "abstract": _clean_text(values.get("abstract")),
        "abstract_snippet": None,
        "jel_codes": values.get("jel_codes", []),
        "methods": [],
        "publication_types": values.get("publication_types", []),
        "fields_of_study": values.get("fields_of_study", []),
        "data_context": None,
        "citation_count": values.get("citation_count"),
        "reference_count": values.get("reference_count"),
        "influential_citation_count": None,
        "is_open_access": values.get("is_open_access"),
        "open_access_pdf_url": values.get("open_access_pdf_url"),
        "retrieval_source": source,
        "retrieval_sources": [source],
        "retrieval_query": query,
        "dedupe_key": doi or re.sub(r"[^a-z0-9]+", "", title.lower()),
        "relevance_note": None,
        "verification_status": "metadata-only",
        "source_specific": values.get("source_specific", {}),
    }


def _date_parts(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = item.get(key, {}).get("date-parts", []) if isinstance(item.get(key), dict) else []
        if parts and parts[0]:
            return _year(parts[0][0])
    return None


def search_crossref(query: str, limit: int, start_year: int | None, end_year: int | None,
                    http_get: HttpGet = _http_get, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {
        "query.bibliographic": query,
        "rows": min(max(limit * 3, 20), 100),
        "sort": "published",
        "order": "desc",
    }
    filters = []
    if start_year:
        filters.append(f"from-pub-date:{start_year}-01-01")
    if end_year:
        filters.append(f"until-pub-date:{end_year}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    contact_email = os.environ.get("LITERATURE_SEARCH_CONTACT_EMAIL")
    if contact_email:
        params["mailto"] = contact_email
    url = _url("https://api.crossref.org/v1/works", params)
    items = json.loads(http_get(url, timeout))["message"]["items"]
    records = []
    for item in items:
        authors = [" ".join(filter(None, (a.get("given"), a.get("family")))) for a in item.get("author", [])]
        title = (item.get("title") or [None])[0]
        venue = (item.get("container-title") or [None])[0]
        records.append(_record(
            "crossref", item.get("DOI") or item.get("URL") or title, query,
            title=title, authors=authors, year=_date_parts(item), venue=venue,
            issn=item.get("ISSN"),
            doi=item.get("DOI"), url=item.get("URL"), abstract=item.get("abstract"),
            citation_count=item.get("is-referenced-by-count"), reference_count=item.get("reference-count"),
            publication_types=[item.get("type")] if item.get("type") else [],
            source_specific={"publisher": item.get("publisher"), "score": item.get("score")},
        ))
    return records[:limit], url


def search_datacite(query: str, limit: int, start_year: int | None, end_year: int | None,
                    http_get: HttpGet = _http_get, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    clauses = [query]
    if start_year or end_year:
        clauses.append(f"publicationYear:[{start_year or '*'} TO {end_year or '*'}]")
    params = {"query": " AND ".join(clauses), "page[size]": min(max(limit * 3, 20), 100), "sort": "-published"}
    url = _url("https://api.datacite.org/dois", params)
    items = json.loads(http_get(url, timeout)).get("data", [])
    records = []
    for item in items:
        attrs = item.get("attributes", {})
        titles = attrs.get("titles") or []
        descriptions = attrs.get("descriptions") or []
        abstract = next((d.get("description") for d in descriptions if d.get("descriptionType") == "Abstract"), None)
        creators = [c.get("name") or " ".join(filter(None, (c.get("givenName"), c.get("familyName")))) for c in attrs.get("creators", [])]
        container = attrs.get("container") or {}
        records.append(_record(
            "datacite", item.get("id") or attrs.get("doi"), query,
            title=titles[0].get("title") if titles else None, authors=creators,
            year=attrs.get("publicationYear") or attrs.get("published"),
            venue=container.get("title") or attrs.get("publisher"), doi=attrs.get("doi"),
            issn=container.get("issn") or attrs.get("issn"),
            url=attrs.get("url"), abstract=abstract,
            citation_count=attrs.get("citationCount"),
            publication_types=[(attrs.get("types") or {}).get("resourceTypeGeneral")],
            source_specific={"subjects": attrs.get("subjects", []), "state": attrs.get("state")},
        ))
    return records[:limit], url


def search_arxiv(query: str, limit: int, start_year: int | None, end_year: int | None,
                 http_get: HttpGet = _http_get, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    tokens = [token for token in re.findall(r"[A-Za-z0-9-]+", query) if len(token) > 1]
    search_query = " AND ".join(f"all:{token}" for token in tokens) or f'all:"{query}"'
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": min(max(limit * 3, 20), 100),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = _url("https://export.arxiv.org/api/query", params)
    root = ET.fromstring(http_get(url, timeout))
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    records = []
    for entry in root.findall("atom:entry", ns):
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = _year(published)
        if start_year and year and year < start_year:
            continue
        if end_year and year and year > end_year:
            continue
        entry_id = entry.findtext("atom:id", default="", namespaces=ns)
        links = {link.get("type"): link.get("href") for link in entry.findall("atom:link", ns)}
        categories = [node.get("term") for node in entry.findall("atom:category", ns) if node.get("term")]
        records.append(_record(
            "arxiv", entry_id.rsplit("/", 1)[-1], query,
            title=entry.findtext("atom:title", namespaces=ns),
            authors=[a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)],
            year=year, venue="arXiv", doi=entry.findtext("arxiv:doi", namespaces=ns),
            url=entry_id, abstract=entry.findtext("atom:summary", namespaces=ns),
            is_open_access=True, open_access_pdf_url=links.get("application/pdf"),
            publication_types=["preprint"], fields_of_study=categories,
            source_specific={"published": published, "updated": entry.findtext("atom:updated", namespaces=ns)},
        ))
    return records[:limit], url


def search_core(query: str, limit: int, start_year: int | None, end_year: int | None,
                http_get: HttpGet | None = None, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    # CORE search results can embed full text, references, and related outputs.
    # Request only the records the caller needs to keep response reads bounded.
    params = {"q": query, "limit": min(max(limit, 1), 100), "stats": "false"}
    url = _url("https://api.core.ac.uk/v3/search/works/", params)
    if http_get is not None:
        content = http_get(url, timeout)
    else:
        api_key = os.environ.get("CORE_API_KEY")
        if not api_key:
            raise RuntimeError("CORE_API_KEY is not configured")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        attempts = (
            ("direct", urllib.request.build_opener(urllib.request.ProxyHandler({})), max(45, timeout)),
            ("system-proxy", urllib.request.build_opener(), max(60, timeout)),
        )
        errors = []
        for route, opener, route_timeout in attempts:
            started = time.perf_counter()
            try:
                with opener.open(request, timeout=route_timeout) as response:
                    content = response.read()
                break
            except Exception as exc:
                elapsed = time.perf_counter() - started
                errors.append(f"{route} failed after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
                if getattr(exc, "code", None) in {400, 401, 403}:
                    raise RuntimeError(errors[-1]) from None
        else:
            raise RuntimeError("; ".join(errors))
    items = json.loads(content).get("results", [])
    records = []
    for item in items:
        year = _year(item.get("yearPublished") or item.get("publishedDate"))
        if start_year and year and year < start_year:
            continue
        if end_year and year and year > end_year:
            continue
        authors = [author.get("name") for author in item.get("authors", []) if isinstance(author, dict)]
        journals = item.get("journals") or []
        venue = next((journal.get("title") for journal in journals if isinstance(journal, dict) and journal.get("title")), None)
        issn = [identifier for journal in journals if isinstance(journal, dict)
                for identifier in _string_list(journal.get("issn") or journal.get("identifiers"))]
        links = item.get("links") or []
        if isinstance(links, dict):
            links = [links]
        display_url = next((link.get("url") for link in links if isinstance(link, dict) and link.get("type") == "display"), None)
        source_urls = item.get("sourceFulltextUrls") or []
        if isinstance(source_urls, str):
            source_urls = [source_urls]
        direct_pdf = next((value for value in source_urls if isinstance(value, str) and ".pdf" in value.lower()), None)
        download_url = direct_pdf or item.get("downloadUrl") or None
        field_of_study = item.get("fieldOfStudy") or []
        if isinstance(field_of_study, str):
            field_of_study = [value.strip() for value in field_of_study.split(";") if value.strip()]
        records.append(_record(
            "core", item.get("id"), query, title=item.get("title"), authors=authors, year=year,
            venue=venue or item.get("publisher"), issn=issn, doi=item.get("doi"), url=display_url,
            abstract=item.get("abstract"), citation_count=item.get("citationCount"),
            reference_count=len(item.get("references") or []),
            is_open_access=bool(download_url or source_urls), open_access_pdf_url=download_url,
            publication_types=[item.get("documentType")] if item.get("documentType") else [],
            fields_of_study=field_of_study,
            external_ids={"arxiv": item.get("arxivId"), "pubmed": item.get("pubmedId")},
            source_specific={"data_providers": item.get("dataProviders", []), "source_fulltext_urls": source_urls},
        ))
    return records[:limit], url


def _openalex_abstract(inverted_index: Any) -> str | None:
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    words = []
    for word, positions in inverted_index.items():
        for position in positions or []:
            words.append((int(position), word))
    return " ".join(word for _, word in sorted(words)) or None


def search_openalex(query: str, limit: int, start_year: int | None, end_year: int | None,
                    http_get: HttpGet | None = None, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, Any] = {
        "search": query,
        "per_page": min(max(limit * 3, 20), 100),
    }
    filters = []
    if start_year:
        filters.append(f"from_publication_date:{start_year}-01-01")
    if end_year:
        filters.append(f"to_publication_date:{end_year}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    safe_url = _url("https://api.openalex.org/works", params)
    if http_get is not None:
        content = http_get(safe_url, timeout)
    else:
        api_key = os.environ.get("OPENALEX_API_KEY")
        if api_key:
            request_params = dict(params)
            request_params["api_key"] = api_key
            request_url = _url("https://api.openalex.org/works", request_params)
            try:
                content = _http_get(request_url, timeout)
            except Exception as exc:
                raise RuntimeError(str(exc).replace(api_key, "[redacted]")) from None
        else:
            content = _http_get(safe_url, timeout)
    items = json.loads(content).get("results", [])
    ranked_records = []
    stopwords = {"and", "the", "of", "a", "an", "to", "in", "on", "for", "with", "relationship"}
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9-]+", query) if len(term) > 1 and term.lower() not in stopwords]
    for item in items:
        primary = item.get("primary_location") or {}
        best_oa = item.get("best_oa_location") or {}
        source = primary.get("source") or {}
        open_access = item.get("open_access") or {}
        authors = []
        for authorship in item.get("authorships") or []:
            author = authorship.get("author") or {}
            if author.get("display_name"):
                authors.append(author["display_name"])
        topics = [topic.get("display_name") for topic in item.get("topics") or [] if topic.get("display_name")]
        pdf_url = best_oa.get("pdf_url") or primary.get("pdf_url") or None
        landing_url = primary.get("landing_page_url") or item.get("doi") or item.get("id")
        source_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        record = _record(
            "openalex", source_id, query, title=item.get("title") or item.get("display_name"),
            authors=authors, year=item.get("publication_year"), venue=source.get("display_name"),
            issn=(source.get("issn") or []) + ([source.get("issn_l")] if source.get("issn_l") else []),
            doi=item.get("doi"), url=landing_url,
            abstract=_openalex_abstract(item.get("abstract_inverted_index")),
            citation_count=item.get("cited_by_count"),
            reference_count=item.get("referenced_works_count") or len(item.get("referenced_works") or []),
            is_open_access=open_access.get("is_oa"), open_access_pdf_url=pdf_url,
            publication_types=[item.get("type")] if item.get("type") else [],
            fields_of_study=topics,
            external_ids=item.get("ids") or {},
            source_specific={
                "oa_status": open_access.get("oa_status"),
                "language": item.get("language"),
                "is_retracted": item.get("is_retracted"),
                "best_oa_location": best_oa,
            },
        )
        searchable = " ".join(filter(None, [record["title"], record.get("abstract"), " ".join(topics)])).lower()
        matched_terms = sum(1 for term in terms if term in searchable)
        if matched_terms >= min(2, len(terms)):
            record["source_specific"]["local_match_terms"] = matched_terms
            ranked_records.append(record)
    ranked_records.sort(key=lambda record: (record.get("year") or 0, record.get("citation_count") or 0), reverse=True)
    return ranked_records[:limit], safe_url


def search_econbiz(query: str, limit: int, start_year: int | None, end_year: int | None,
                   http_get: HttpGet = _http_get, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    params = {"q": query, "size": min(max(limit * 3, 20), 100), "sort": "date desc"}
    url = _url("https://api.econbiz.de/v1/search", params)
    items = (json.loads(http_get(url, timeout)).get("hits") or {}).get("hits") or []
    records = []
    for item in items:
        year = _year(item.get("date") or item.get("econbiz_created"))
        if start_year and year and year < start_year:
            continue
        if end_year and year and year > end_year:
            continue
        urls = _string_list(item.get("identifier_url"))
        doi_url = next((value for value in urls if "doi.org/" in value.lower()), None)
        doi = doi_url.split("doi.org/", 1)[1] if doi_url else item.get("doi")
        pdf_url = next((value for value in urls if value.lower().split("?", 1)[0].endswith(".pdf")), None)
        venue = (_string_list(item.get("series")) or _string_list(item.get("publisher")) or [None])[0]
        types = _string_list(item.get("type_genre")) or _string_list(item.get("type"))
        records.append(_record(
            "econbiz", item.get("id") or doi or item.get("title"), query,
            title=item.get("title"), authors=item.get("creator") or item.get("person") or [],
            year=year, venue=venue, issn=item.get("issn"), doi=doi,
            url=doi_url or (urls[0] if urls else None),
            abstract=item.get("abstract"), is_open_access=bool(pdf_url), open_access_pdf_url=pdf_url,
            publication_types=types, fields_of_study=_string_list(item.get("subject")),
            source_specific={"econbiz_source": item.get("source"), "identifier_urls": urls, "score": item.get("_score")},
        ))
    return records[:limit], url


def _world_bank_authors(item: dict[str, Any]) -> list[str]:
    raw = item.get("authors") or item.get("author") or item.get("authr") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    if isinstance(raw, str):
        raw = re.split(r";|\band\b", raw)
    return _author_names(raw)


def search_world_bank(query: str, limit: int, start_year: int | None, end_year: int | None,
                      http_get: HttpGet = _http_get, timeout: int = 30) -> tuple[list[dict[str, Any]], str]:
    params = {
        "qterm": query, "format": "json", "rows": min(max(limit * 3, 20), 100),
        "sort": "docdt desc",
    }
    url = _url("https://search.worldbank.org/api/v3/wds", params)
    payload = json.loads(http_get(url, timeout))
    documents = payload.get("documents") or {}
    items = [value for key, value in documents.items() if key != "facets" and isinstance(value, dict)]
    records = []
    for item in items:
        year = _year(item.get("docdt"))
        if start_year and year and year < start_year:
            continue
        if end_year and year and year > end_year:
            continue
        abstract = item.get("abstracts") or item.get("abstract")
        if isinstance(abstract, dict):
            abstract = abstract.get("cdata!") or next(iter(abstract.values()), None)
        doi_values = _string_list(item.get("dois") or item.get("doi"))
        pdf_url = item.get("pdfurl") or item.get("pdf_url")
        records.append(_record(
            "world-bank", item.get("id") or item.get("guid") or item.get("display_title"), query,
            title=item.get("display_title") or item.get("title"), authors=_world_bank_authors(item),
            year=year, venue=item.get("majdocty") or item.get("docty") or "World Bank Documents & Reports",
            issn=item.get("issn"), doi=doi_values[0] if doi_values else None,
            url=item.get("url"), abstract=abstract, is_open_access=bool(pdf_url),
            open_access_pdf_url=pdf_url,
            publication_types=_string_list(item.get("docty") or item.get("majdocty")),
            fields_of_study=_string_list(item.get("admreg")),
            source_specific={"language": item.get("lang"), "guid": item.get("guid")},
        ))
    return records[:limit], url


NBER_FILES = ("ref.tsv", "abs.tsv", "auths.tsv", "date.tsv", "jel.tsv")


def _nber_table(name: str, cache_dir: Path, http_get: HttpGet, timeout: int) -> list[dict[str, str]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / name
    stale = not path.exists() or time.time() - path.stat().st_mtime > 7 * 24 * 60 * 60
    if stale:
        url = f"https://data.nber.org/nber_paper_chapter_metadata/tsv/{name}"
        path.write_bytes(http_get(url, timeout))
    text = path.read_text(encoding="utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def search_nber(query: str, limit: int, start_year: int | None, end_year: int | None,
                http_get: HttpGet = _http_get, timeout: int = 30,
                cache_dir: Path = DEFAULT_CACHE_DIR / "nber") -> tuple[list[dict[str, Any]], str]:
    tables = {name: _nber_table(name, cache_dir, http_get, timeout) for name in NBER_FILES}
    by_paper: dict[str, dict[str, Any]] = {}
    for row in tables["ref.tsv"]:
        by_paper[row["paper"]] = dict(row)
    for filename, target in (("abs.tsv", "abstract"), ("auths.tsv", "authors"), ("date.tsv", "issue_date")):
        for row in tables[filename]:
            paper = row.get("paper")
            if paper in by_paper:
                by_paper[paper][target] = next((v for k, v in row.items() if k != "paper"), "")
    for row in tables["jel.tsv"]:
        paper = row.get("paper")
        if paper in by_paper:
            by_paper[paper].setdefault("jel_codes", []).append(row.get("jel", ""))

    stopwords = {"and", "the", "of", "a", "an", "to", "in", "on", "for", "with", "relationship"}
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9-]+", query) if len(t) > 1 and t.lower() not in stopwords]
    ranked = []
    for paper, item in by_paper.items():
        year = _year(item.get("issue_date"))
        if start_year and year and year < start_year:
            continue
        if end_year and year and year > end_year:
            continue
        title = (item.get("title") or "").lower()
        abstract = (item.get("abstract") or "").lower()
        matched_terms = sum(1 for term in terms if term in title or term in abstract)
        score = sum(3 * title.count(term) + abstract.count(term) for term in terms)
        if matched_terms >= min(2, len(terms)):
            ranked.append((year or 0, score, paper, item))
    ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
    records = []
    for _, score, paper, item in ranked[:limit]:
        doi = _doi(item.get("doi")) or (f"10.3386/{paper}" if paper.startswith("w") else None)
        records.append(_record(
            "nber", paper, query, title=item.get("title"),
            authors=re.split(r",\s*|\s+and\s+", item.get("authors") or item.get("author") or ""),
            year=item.get("issue_date"), venue="NBER Working Paper",
            doi=doi, url=f"https://www.nber.org/papers/{paper}", abstract=item.get("abstract"),
            jel_codes=[code for code in item.get("jel_codes", []) if code],
            publication_types=["working-paper"], source_specific={"local_match_score": score},
        ))
    return records, "https://data.nber.org/nber_paper_chapter_metadata/tsv/"


SOURCE_FUNCTIONS = {
    "crossref": search_crossref,
    "nber": search_nber,
    "datacite": search_datacite,
    "arxiv": search_arxiv,
    "core": search_core,
    "openalex": search_openalex,
    "econbiz": search_econbiz,
    "world-bank": search_world_bank,
}

MANUAL_SEARCH_CONFIG = {
    "google-scholar": ("https://scholar.google.com/scholar", "q"),
    "ssrn": ("https://papers.ssrn.com/sol3/results.cfm", "txtKey_Words"),
    "ideas-repec": ("https://ideas.repec.org/cgi-bin/htsearch", "q"),
    "econpapers": ("https://econpapers.repec.org/scripts/search.pf", "ft"),
    "cepr": ("https://cepr.org/search", "query"),
    "iza": ("https://www.iza.org/publications/dp", "term"),
    "cnki": ("https://kns.cnki.net/kns8s/defaultresult/index", "kw"),
    "wanfang": ("https://s.wanfangdata.com.cn/paper", "q"),
    "bfi": ("https://bfi.uchicago.edu/", "s"),
    "siepr": ("https://siepr.stanford.edu/search", "search"),
    "lse-cep": ("https://cep.lse.ac.uk/_new/publications/results/default.asp", "keyword"),
}


def manual_search_url(source_id: str, query: str) -> str:
    base, parameter = MANUAL_SEARCH_CONFIG[source_id]
    params = {parameter: query}
    if source_id == "iza":
        params["search"] = "keywords"
    return _url(base, params)


def _merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return merge_records(records)[0]


def search_literature(query: str, sources: list[str] | None = None, limit: int = 20,
                      start_year: int | None = None, end_year: int | None = None,
                      timeout: int = 30, concept_blocks: list[dict[str, Any]] | None = None,
                      requested_methods: list[str] | None = None, ranking: str = "latest",
                      mode: str = "exploratory", inclusion_criteria: list[str] | None = None,
                      exclusion_criteria: list[str] | None = None) -> dict[str, Any]:
    source_ids = sources or list(AVAILABLE_SOURCES)
    unknown = sorted(set(source_ids) - set(AVAILABLE_SOURCES))
    if unknown:
        raise ValueError(f"Unsupported source ids: {', '.join(unknown)}")
    all_records: list[dict[str, Any]] = []
    logs = []
    gaps = []
    for source_id in source_ids:
        executed_at = _utc_now()
        if source_id in MANUAL_SOURCES:
            search_url = manual_search_url(source_id, query)
            logs.append({
                "search_log_id": f"log-{source_id}-{hashlib.sha1(executed_at.encode()).hexdigest()[:10]}",
                "source_id": source_id, "source_adapter_version": "0.1", "query": query,
                "query_parameters": {"search_url": search_url, "mode": "manual-web"},
                "executed_at": executed_at, "execution_status": "manual-check-needed", "records_returned": 0,
                "records_kept": 0, "error_message": None,
                "notes": "Open the official search URL and manually verify or export records; no scraping was performed.",
            })
            continue
        try:
            records, request_url = SOURCE_FUNCTIONS[source_id](query, limit, start_year, end_year, timeout=timeout)
            all_records.extend(records)
            logs.append({
                "search_log_id": f"log-{source_id}-{hashlib.sha1(executed_at.encode()).hexdigest()[:10]}",
                "source_id": source_id, "source_adapter_version": "0.1", "query": query,
                "query_parameters": {"limit": limit, "start_year": start_year, "end_year": end_year, "request_url": request_url},
                "executed_at": executed_at, "execution_status": "success", "records_returned": len(records),
                "records_kept": len(records), "error_message": None, "notes": None,
            })
        except Exception as exc:
            gaps.append(f"{source_id} failed: {exc}")
            logs.append({
                "search_log_id": f"log-{source_id}-{hashlib.sha1(executed_at.encode()).hexdigest()[:10]}",
                "source_id": source_id, "source_adapter_version": "0.1", "query": query,
                "query_parameters": {"limit": limit, "start_year": start_year, "end_year": end_year},
                "executed_at": executed_at, "execution_status": "failed", "records_returned": 0,
                "records_kept": 0, "error_message": str(exc), "notes": None,
            })
    records, dedupe_reasons = merge_records(all_records)
    records = enrich_records(records, query, concept_blocks, requested_methods, ranking)
    records = enrich_journal_rankings(records)
    advisories = distribution_advisories(records)
    return {
        "module_id": "literature-search", "version": "0.6", "created_at": _utc_now(),
        "input_summary": query, "source_ids": source_ids, "records": records,
        "search_logs": logs,
        "search_protocol": {
            "mode": mode,
            "working_query": query,
            "concept_blocks": concept_blocks or [],
            "requested_methods": requested_methods or [],
            "inclusion_criteria": inclusion_criteria or [],
            "exclusion_criteria": exclusion_criteria or [],
            "ranking": ranking,
        },
        "search_metrics": {
            "records_retrieved": len(all_records),
            "records_after_deduplication": len(records),
            "duplicates_removed": len(all_records) - len(records),
            "dedupe_reasons": dedupe_reasons,
            "records_screened": 0,
            "records_included": 0,
            "records_excluded": 0,
            "records_maybe": 0,
        },
        "coverage_advisories": advisories,
        "coverage_notes": ["Results are scored metadata candidates and require explicit downstream screening."],
        "verification_gaps": gaps,
        "handoff": {
            "next_modules": ["literature-screening", "literature-synthesis", "citation-management"],
            "notes": ["Deduplicated by DOI, external ids, normalized title, or high-similarity title plus first author."],
        },
    }


def search_plan(plan: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    """Execute the shared SearchPlan contract with the enabled no-key adapters."""
    concept_terms = []
    for block in plan.get("concept_blocks", []):
        terms = block.get("terms") or []
        if terms:
            concept_terms.append(terms[0])
    query = " ".join(concept_terms[:3]).strip()
    if not query:
        query = plan["research_question"]

    years = [int(value) for value in re.findall(r"(?:19|20)\d{2}", str(plan.get("scope", {}).get("time_range") or ""))]
    start_year = min(years) if years else None
    end_year = max(years) if years else None
    policy = plan.get("source_policy") or {}
    limit = policy.get("max_records_per_source") or 20
    sources = [source for source in plan.get("sources", []) if source in AVAILABLE_SOURCES]
    if not sources:
        sources = list(AUTOMATED_SOURCES)

    scope = plan.get("scope") or {}
    screening = plan.get("screening") or {}
    output = search_literature(
        query, sources, limit, start_year, end_year, timeout,
        concept_blocks=plan.get("concept_blocks") or [],
        requested_methods=scope.get("methods") or [],
        ranking=(policy.get("ranking") or "latest"),
        mode=plan.get("mode") or "exploratory",
        inclusion_criteria=screening.get("inclusion_criteria") or [],
        exclusion_criteria=screening.get("exclusion_criteria") or [],
    )
    output["input_summary"] = plan["research_question"]
    for log in output["search_logs"]:
        if log["source_id"] in {"cnki", "wanfang"}:
            chinese_query = plan["research_question"]
            log["query"] = chinese_query
            log["query_parameters"]["search_url"] = manual_search_url(log["source_id"], chinese_query)
    output["handoff"]["notes"].append(f"Working query: {query}")
    return output
