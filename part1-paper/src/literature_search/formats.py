from __future__ import annotations

import re
from typing import Any


def _year(record: dict[str, Any]) -> str:
    return str(record.get("year") or "")


def _cite_key(record: dict[str, Any], index: int) -> str:
    authors = record.get("authors") or []
    surname = re.sub(r"[^A-Za-z0-9]", "", str(authors[0]).split(",")[0].split()[-1]) if authors else "paper"
    word = next(iter(re.findall(r"[A-Za-z0-9]+", record.get("title") or "paper")), "paper")
    return f"{surname}{_year(record) or 'nd'}{word}".lower() + (str(index) if index else "")


def to_ris(records: list[dict[str, Any]]) -> str:
    entries = []
    for record in records:
        lines = ["TY  - JOUR", f"TI  - {record.get('title') or ''}"]
        lines += [f"AU  - {author}" for author in record.get("authors") or []]
        for tag, value in (("PY", _year(record)), ("JO", record.get("venue")), ("DO", record.get("doi")),
                           ("UR", record.get("url")), ("AB", record.get("abstract"))):
            if value:
                lines.append(f"{tag}  - {value}")
        lines.append("ER  -")
        entries.append("\r\n".join(lines))
    return "\r\n\r\n".join(entries) + "\r\n"


def _bib_escape(value: Any) -> str:
    return str(value or "").replace("{", "\\{").replace("}", "\\}")


def to_bibtex(records: list[dict[str, Any]]) -> str:
    entries = []
    used: set[str] = set()
    for index, record in enumerate(records):
        key = _cite_key(record, 0)
        if key in used:
            key = _cite_key(record, index + 1)
        used.add(key)
        fields = [
            ("title", record.get("title")), ("author", " and ".join(record.get("authors") or [])),
            ("year", _year(record)), ("journal", record.get("venue")), ("doi", record.get("doi")),
            ("url", record.get("url")),
        ]
        body = ",\n".join(f"  {name} = {{{_bib_escape(value)}}}" for name, value in fields if value)
        entries.append(f"@article{{{key},\n{body}\n}}")
    return "\n\n".join(entries) + "\n"


def to_enw(records: list[dict[str, Any]]) -> str:
    entries = []
    for record in records:
        lines = ["%0 Journal Article", f"%T {record.get('title') or ''}"]
        lines += [f"%A {author}" for author in record.get("authors") or []]
        for tag, value in (("%D", _year(record)), ("%J", record.get("venue")), ("%R", record.get("doi")),
                           ("%U", record.get("url")), ("%X", record.get("abstract"))):
            if value:
                lines.append(f"{tag} {value}")
        entries.append("\r\n".join(lines))
    return "\r\n\r\n".join(entries) + "\r\n"


def export_records(records: list[dict[str, Any]], format_name: str) -> tuple[str, str, str]:
    exporters = {
        "ris": (to_ris, "text/plain; charset=utf-8", "ris"),
        "bibtex": (to_bibtex, "application/x-bibtex; charset=utf-8", "bib"),
        "enw": (to_enw, "text/plain; charset=utf-8", "enw"),
    }
    if format_name not in exporters:
        raise ValueError("不支持的引用格式。")
    exporter, content_type, extension = exporters[format_name]
    return exporter(records), content_type, extension
