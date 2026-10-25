from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in",
    "is", "of", "on", "or", "the", "to", "with", "relationship", "effect", "impact",
}
METHOD_KEYWORDS = {
    "difference-in-differences": ("difference in differences", "difference-in-differences", "diff-in-diff", " did "),
    "event study": ("event study",),
    "instrumental variables": ("instrumental variable", "two-stage least squares", "2sls"),
    "regression discontinuity": ("regression discontinuity", "rdd"),
    "randomized experiment": ("randomized", "randomised", "random assignment", "field experiment"),
    "panel regression": ("panel data", "fixed effects", "fixed-effects"),
    "synthetic control": ("synthetic control",),
    "structural model": ("structural model", "structural estimation"),
    "qualitative case study": ("case study", "interview", "qualitative"),
}
DATA_KEYWORDS = (
    "dataset", "data set", "panel", "survey", "sample", "administrative data", "patent",
    "firm-level", "country-level", "transaction", "registry", "database", "microdata",
)
FORMAL_PUBLICATION_TYPES = {"journal-article", "article", "book-chapter", "proceedings-article"}


def _stem_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("xes", "ses", "zes", "ches", "shes")) and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _tokens(value: str | None) -> list[str]:
    return [_stem_token(token) for token in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(token) > 1 and token not in STOPWORDS]


def normalized_title(value: str | None) -> str:
    return " ".join(_tokens(value))


def title_similarity(left: str | None, right: str | None) -> float:
    left_tokens, right_tokens = set(_tokens(left)), set(_tokens(right))
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def _first_author_surname(record: dict[str, Any]) -> str:
    authors = record.get("authors") or []
    if not authors:
        return ""
    value = re.sub(r"[^a-z\s,-]", "", str(authors[0]).lower()).strip()
    if "," in value:
        return value.split(",", 1)[0].strip()
    return value.split()[-1] if value.split() else ""


def records_match(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, str | None]:
    left_doi, right_doi = left.get("doi"), right.get("doi")
    if left_doi and right_doi and str(left_doi).lower() == str(right_doi).lower():
        return True, "doi"

    left_ids = {f"{key}:{value}" for key, value in (left.get("external_ids") or {}).items() if value}
    right_ids = {f"{key}:{value}" for key, value in (right.get("external_ids") or {}).items() if value}
    left_ids |= {f"{key}:{value}" for key, value in (left.get("source_record_ids") or {}).items() if value}
    right_ids |= {f"{key}:{value}" for key, value in (right.get("source_record_ids") or {}).items() if value}
    if left_ids & right_ids:
        return True, "external-id"

    left_title, right_title = normalized_title(left.get("title")), normalized_title(right.get("title"))
    if left_title and left_title == right_title:
        return True, "normalized-title"
    authors_match = _first_author_surname(left) and _first_author_surname(left) == _first_author_surname(right)
    if authors_match and title_similarity(left.get("title"), right.get("title")) >= 0.90:
        return True, "title-author-fuzzy"
    return False, None


def _completeness(record: dict[str, Any]) -> tuple[int, int, int]:
    fields = ("doi", "title", "authors", "year", "venue", "abstract", "citation_count", "url")
    complete = sum(bool(record.get(field)) for field in fields)
    formal = int(bool(set(record.get("publication_types") or []) & FORMAL_PUBLICATION_TYPES))
    return complete, formal, int(record.get("citation_count") or 0)


def merge_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    merged: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for incoming in records:
        match_index, match_reason = None, None
        for index, current in enumerate(merged):
            matched, reason = records_match(current, incoming)
            if matched:
                match_index, match_reason = index, reason
                break
        if match_index is None:
            merged.append(incoming)
            continue

        current = merged[match_index]
        if _completeness(incoming) > _completeness(current):
            primary, secondary = incoming, current
            merged[match_index] = primary
        else:
            primary, secondary = current, incoming
        primary["retrieval_sources"] = sorted(set((primary.get("retrieval_sources") or []) + (secondary.get("retrieval_sources") or [])))
        primary.setdefault("source_record_ids", {}).update(secondary.get("source_record_ids") or {})
        primary.setdefault("external_ids", {}).update(secondary.get("external_ids") or {})
        if not primary.get("abstract") and secondary.get("abstract"):
            primary["abstract"] = secondary["abstract"]
        if secondary.get("citation_count") is not None:
            primary["citation_count"] = max(primary.get("citation_count") or 0, secondary["citation_count"])
        if not primary.get("open_access_pdf_url") and secondary.get("open_access_pdf_url"):
            primary["open_access_pdf_url"] = secondary["open_access_pdf_url"]
            primary["is_open_access"] = secondary.get("is_open_access")
        primary["dedupe_key"] = primary.get("doi") or normalized_title(primary.get("title"))
        reasons[match_reason or "unknown"] += 1
    return merged, dict(reasons)


def _concept_terms(query: str, concept_blocks: list[dict[str, Any]] | None) -> list[list[str]]:
    blocks = []
    for block in concept_blocks or []:
        terms = [str(term).strip().lower() for term in block.get("terms", []) if str(term).strip()]
        if terms:
            blocks.append(terms)
    if not blocks:
        blocks = [[term] for term in _tokens(query)]
    return blocks


def score_record(record: dict[str, Any], query: str,
                 concept_blocks: list[dict[str, Any]] | None = None,
                 requested_methods: list[str] | None = None) -> dict[str, Any]:
    title = str(record.get("title") or "").lower()
    abstract = str(record.get("abstract") or "").lower()
    searchable = f" {title} {abstract} "
    blocks = _concept_terms(query, concept_blocks)
    covered = sum(any(term in searchable for term in terms) for terms in blocks)
    title_hits = sum(any(term in title for term in terms) for terms in blocks)
    topic = min(30, round(20 * covered / max(1, len(blocks)) + 10 * title_hits / max(1, len(blocks))))

    detected_methods = [method for method, aliases in METHOD_KEYWORDS.items() if any(alias in searchable for alias in aliases)]
    requested = [method.lower() for method in requested_methods or []]
    if requested:
        method_hits = sum(any(method in candidate or candidate in method for candidate in detected_methods) for method in requested)
        methods = round(25 * method_hits / len(requested))
    else:
        methods = min(25, 8 * len(detected_methods))
    data = min(15, 3 * sum(keyword in searchable for keyword in DATA_KEYWORDS))
    source = min(10, 3 + 2 * bool(record.get("venue")) + 2 * bool(record.get("doi")) + 3 * (len(record.get("retrieval_sources") or []) > 1))
    evidence = min(10, 4 * bool(record.get("abstract")) + 2 * bool(record.get("authors")) + 2 * bool(record.get("year")) + 2 * (record.get("citation_count") is not None))
    open_materials = min(10, 7 * bool(record.get("open_access_pdf_url")) + 2 * bool(record.get("doi")) + bool(record.get("url")))
    scores = {
        "topic_relevance": topic,
        "method_value": methods,
        "data_relevance": data,
        "source_quality": source,
        "evidence_completeness": evidence,
        "open_materials": open_materials,
    }
    record["quality_scores"] = scores
    record["total_score"] = sum(scores.values())
    record["methods"] = sorted(set((record.get("methods") or []) + detected_methods))
    record["evidence_depth"] = (
        "fulltext-link" if record.get("open_access_pdf_url") else
        "abstract-available" if record.get("abstract") else "metadata-only"
    )
    record.setdefault("screening_status", "unscreened")
    record.setdefault("screening_reason", None)
    record["relevance_note"] = f"Covered {covered}/{len(blocks)} concept blocks; quality score {record['total_score']}/100."
    return record


def rank_records(records: list[dict[str, Any]], mode: str = "combined") -> list[dict[str, Any]]:
    if mode == "latest":
        key = lambda record: (record.get("year") or 0, record.get("total_score") or 0, record.get("citation_count") or 0)
    elif mode == "citations":
        key = lambda record: (record.get("citation_count") or 0, record.get("total_score") or 0, record.get("year") or 0)
    elif mode == "relevance":
        key = lambda record: ((record.get("quality_scores") or {}).get("topic_relevance") or 0, record.get("total_score") or 0, record.get("year") or 0)
    else:
        key = lambda record: (record.get("total_score") or 0, record.get("year") or 0, math.log1p(record.get("citation_count") or 0))
    return sorted(records, key=key, reverse=True)


def distribution_advisories(records: list[dict[str, Any]], threshold: float = 0.70) -> list[dict[str, Any]]:
    current_year = datetime.now(timezone.utc).year
    dimensions: dict[str, list[str]] = {
        "time": ["recent-5-years" if int(record["year"]) >= current_year - 4 else "older" for record in records if str(record.get("year") or "").isdigit()],
        "primary-source": [(record.get("retrieval_sources") or [record.get("source") or "unknown"])[0] for record in records],
        "evidence-depth": [record.get("evidence_depth") for record in records if record.get("evidence_depth")],
        "method": [method for record in records for method in (record.get("methods") or [])],
    }
    advisories = []
    for dimension, values in dimensions.items():
        if len(values) < 5:
            continue
        value, count = Counter(values).most_common(1)[0]
        share = count / len(values)
        if share >= threshold:
            advisories.append({
                "dimension": dimension,
                "value": value,
                "count": count,
                "known_count": len(values),
                "share": round(share, 3),
                "note": "Coverage concentration signal; review whether the research scope justifies this distribution.",
            })
    return advisories


def enrich_records(records: list[dict[str, Any]], query: str,
                   concept_blocks: list[dict[str, Any]] | None = None,
                   requested_methods: list[str] | None = None,
                   ranking: str = "combined") -> list[dict[str, Any]]:
    for record in records:
        score_record(record, query, concept_blocks, requested_methods)
    return rank_records(records, ranking)
