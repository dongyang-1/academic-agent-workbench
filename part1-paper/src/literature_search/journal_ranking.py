from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEME = PROJECT_ROOT / "config" / "journal-rankings" / "zufe-2024.json"
LEVEL_ORDER = {"TOP": 0, "一级A": 1, "一级B": 2, "二级A": 3, "二级B": 4, "三级": 5}


def normalize_journal_title(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)


def normalize_identifier(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


@lru_cache(maxsize=4)
def load_scheme(path: str | Path = DEFAULT_SCHEME) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _indexes(path: str | Path = DEFAULT_SCHEME) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_title: dict[str, list[dict[str, Any]]] = {}
    by_identifier: dict[str, list[dict[str, Any]]] = {}
    for entry in load_scheme(path).get("entries", []):
        title_key = normalize_journal_title(entry.get("title"))
        if title_key:
            by_title.setdefault(title_key, []).append(entry)
        for identifier in entry.get("identifiers") or []:
            identifier_key = normalize_identifier(identifier)
            if identifier_key:
                by_identifier.setdefault(identifier_key, []).append(entry)
    return by_title, by_identifier


def _highest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return min(entries, key=lambda item: LEVEL_ORDER.get(item.get("level"), 99))


def classify_journal(venue: str | None, identifiers: list[str] | None = None,
                     path: str | Path = DEFAULT_SCHEME) -> dict[str, Any]:
    scheme = load_scheme(path)
    by_title, by_identifier = _indexes(path)
    matched: dict[str, Any] | None = None
    match_method: str | None = None
    matched_value: str | None = None

    for identifier in identifiers or []:
        key = normalize_identifier(identifier)
        if key and key in by_identifier:
            matched = _highest(by_identifier[key])
            match_method = "identifier-exact"
            matched_value = identifier
            break

    if matched is None:
        title_key = normalize_journal_title(venue)
        if title_key and title_key in by_title:
            matched = _highest(by_title[title_key])
            match_method = "title-exact"
            matched_value = venue

    common = {
        "scheme_id": scheme["scheme_id"],
        "scheme_name": scheme["scheme_name"],
        "source_document": scheme["source_document"],
    }
    if matched:
        return {
            **common,
            "level": matched["level"],
            "category": matched.get("category"),
            "scope": matched.get("scope"),
            "status": "matched-explicit-list",
            "match_method": match_method,
            "matched_title": matched.get("title"),
            "matched_value": matched_value,
            "note": "已与学校 2024 年修订办法附件中的明确期刊清单匹配。",
        }

    return {
        **common,
        "level": "待核验",
        "category": None,
        "scope": None,
        "status": "unmatched",
        "match_method": None,
        "matched_title": None,
        "matched_value": None,
        "note": scheme["matching_policy"]["note"],
    }


def enrich_journal_rankings(records: list[dict[str, Any]], path: str | Path = DEFAULT_SCHEME) -> list[dict[str, Any]]:
    for record in records:
        record["journal_ranking"] = classify_journal(record.get("venue"), record.get("issn") or [], path)
    return records
