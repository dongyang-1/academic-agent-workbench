from __future__ import annotations

import ast
import json
import re
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable


USER_AGENT = "economics-research-agent/0.3 (non-commercial research prototype)"
LOCAL_CONNECTOR_URL = "http://127.0.0.1:23119"
MAX_PDF_BYTES = 100 * 1024 * 1024
HttpPost = Callable[[str, bytes, dict[str, str], int], tuple[int, bytes]]
PdfDownload = Callable[[str, int], bytes]
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def _local_opener() -> urllib.request.OpenerDirector:
    # Local Zotero requests must not be routed through a system HTTP proxy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def local_zotero_status(timeout: int = 2) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{LOCAL_CONNECTOR_URL}/connector/ping",
        headers={"User-Agent": USER_AGENT, "X-Zotero-Connector-API-Version": "3"},
    )
    try:
        with _local_opener().open(request, timeout=timeout) as response:
            return {
                "available": response.status == 200,
                "version": response.headers.get("X-Zotero-Version"),
                "connector_api_version": response.headers.get("X-Zotero-Connector-API-Version"),
            }
    except Exception:
        return {"available": False, "version": None, "connector_api_version": None}


def zotero_configuration() -> dict[str, Any]:
    status = local_zotero_status()
    return {
        "configured": status["available"],
        "mode": "local-connector",
        "version": status["version"],
        "connector_api_version": status["connector_api_version"],
        "collection_policy": "current-zotero-selection",
    }


def _http_post(url: str, body: bytes, headers: dict[str, str], timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with _local_opener().open(request, timeout=timeout) as response:
        return response.status, response.read()


def _download_pdf(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
    errors = []
    for opener in (
        urllib.request.build_opener(urllib.request.ProxyHandler({})),
        urllib.request.build_opener(),
    ):
        try:
            with opener.open(request, timeout=timeout) as response:
                length = int(response.headers.get("Content-Length") or 0)
                if length > MAX_PDF_BYTES:
                    raise ValueError("PDF 文件超过 100 MB 限制。")
                body = response.read(MAX_PDF_BYTES + 1)
                if len(body) > MAX_PDF_BYTES:
                    raise ValueError("PDF 文件超过 100 MB 限制。")
                if b"%PDF-" not in body[:1024]:
                    content_type = response.headers.get("Content-Type") or "unknown"
                    raise ValueError(f"开放全文地址未返回 PDF（Content-Type: {content_type}）。")
                return body
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def _creators(authors: Any) -> list[dict[str, str]]:
    names: list[str] = []

    def collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)
            return
        if isinstance(value, dict):
            lowered = {str(key).lower(): item for key, item in value.items()}
            for key in ("name", "display_name", "fullname", "full_name", "author"):
                if key in lowered:
                    collect(lowered[key])
                    return
            return

        text = str(value).strip()
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

    collect(authors)
    return [{"creatorType": "author", "name": name} for name in dict.fromkeys(names)]


def _tags(record: dict[str, Any]) -> list[dict[str, str]]:
    values = ["EconLit Agent"]
    values.extend(f"来源:{source}" for source in record.get("retrieval_sources") or [])
    ranking = record.get("journal_ranking") or {}
    if ranking.get("level") and ranking.get("level") != "待核验":
        values.append(f"浙财大期刊等级:{ranking['level']}")
    return [{"tag": value} for value in dict.fromkeys(values)]


def _normalized_doi(value: Any) -> str | None:
    doi = urllib.parse.unquote(str(value or "")).strip()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.IGNORECASE)
    doi = doi.strip().rstrip(".,;")
    return doi if DOI_PATTERN.fullmatch(doi) else None


def _safe_http_url(value: Any) -> str | None:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _zotero_item_type(record: dict[str, Any]) -> str:
    publication_types = {str(value).strip().lower() for value in record.get("publication_types") or []}
    source = str(record.get("source") or "").strip().lower()
    venue = str(record.get("venue") or "").strip().lower()
    if "preprint" in publication_types or source == "arxiv" or venue == "arxiv":
        return "preprint"
    if publication_types & {"report", "working-paper", "working paper", "discussion paper"}:
        return "report"
    return "journalArticle"


def _preprint_archive_id(record: dict[str, Any]) -> str:
    external_ids = record.get("external_ids") or {}
    for key in ("arxiv", "arXiv", "ArXiv"):
        if external_ids.get(key):
            return str(external_ids[key]).strip()
    url = str(record.get("url") or record.get("open_access_pdf_url") or "")
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", url, flags=re.IGNORECASE)
    return match.group(1).removesuffix(".pdf") if match else ""


def record_to_zotero_item(record: dict[str, Any], connector_item_id: str | None = None) -> dict[str, Any]:
    item_type = _zotero_item_type(record)
    item: dict[str, Any] = {
        "itemType": item_type,
        "title": str(record.get("title") or "").strip(),
        "creators": _creators(record.get("authors") or []),
        "abstractNote": str(record.get("abstract") or "").strip(),
        "date": str(record.get("year") or ""),
        "url": str(record.get("url") or record.get("open_access_pdf_url") or "").strip(),
        "language": str((record.get("source_specific") or {}).get("language") or "").strip(),
        "tags": _tags(record),
    }
    doi = _normalized_doi(record.get("doi"))
    if doi:
        item["DOI"] = doi
    if connector_item_id:
        item["id"] = connector_item_id
    issn = ", ".join(record.get("issn") or [])
    if item_type == "preprint":
        item.update({
            "repository": str(record.get("venue") or record.get("source") or "").strip(),
            "archiveID": _preprint_archive_id(record),
            "genre": "Preprint",
        })
    elif item_type == "report":
        item.update({"reportType": "; ".join(record.get("publication_types") or []), "institution": str(record.get("venue") or "")})
    else:
        item.update({"publicationTitle": str(record.get("venue") or ""), "ISSN": issn})
    pdf_url = _safe_http_url(record.get("open_access_pdf_url"))
    if pdf_url:
        item["attachments"] = [{
            "title": "Full Text PDF",
            "mimeType": "application/pdf",
            "url": pdf_url,
            "proxy": False,
        }]
    return item


def save_records_to_zotero(records: list[dict[str, Any]], http_post: HttpPost = _http_post,
                           pdf_download: PdfDownload = _download_pdf, timeout: int = 30,
                           require_available: bool = True) -> dict[str, Any]:
    if require_available and not local_zotero_status()["available"]:
        raise RuntimeError("未检测到本机 Zotero，请启动 Zotero 并启用“允许本机其他应用与 Zotero 通信”。")
    if not records:
        raise ValueError("请至少选择一条文献。")
    if len(records) > 100:
        raise ValueError("单次最多保存 100 条文献到 Zotero。")

    session_id = f"econlit-{uuid.uuid4().hex}"
    items = [record_to_zotero_item(record, f"record-{index}-{uuid.uuid4().hex[:10]}") for index, record in enumerate(records)]
    attachment_jobs = []
    for record, item in zip(records, items):
        for attachment in item.pop("attachments", []):
            attachment_jobs.append({"record": record, "parent_id": item["id"], **attachment})
    source_uri = next((str(record.get("url")) for record in records if record.get("url")), "about:blank")
    payload = {"items": items, "uri": source_uri, "sessionID": session_id}
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "X-Zotero-Connector-API-Version": "3",
    }
    status, response_body = http_post(
        f"{LOCAL_CONNECTOR_URL}/connector/saveItems",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers, timeout,
    )
    if status not in {200, 201}:
        detail = response_body.decode("utf-8", errors="replace")
        raise RuntimeError(f"本机 Zotero 拒绝保存（HTTP {status}）：{detail}")

    attachments_saved = 0
    attachment_failures = []
    for attachment in attachment_jobs:
        try:
            pdf_body = pdf_download(attachment["url"], timeout)
            metadata = {
                "sessionID": session_id,
                "parentItemID": attachment["parent_id"],
                "title": attachment["title"],
                "url": attachment["url"],
            }
            attachment_status, attachment_response = http_post(
                f"{LOCAL_CONNECTOR_URL}/connector/saveAttachment",
                pdf_body,
                {
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(pdf_body)),
                    "X-Metadata": json.dumps(metadata, ensure_ascii=True, separators=(",", ":")),
                    "X-Zotero-Connector-API-Version": "3",
                },
                timeout,
            )
            if attachment_status not in {200, 201}:
                detail = attachment_response.decode("utf-8", errors="replace")
                raise RuntimeError(f"Zotero 返回 HTTP {attachment_status}: {detail}")
            attachments_saved += 1
        except Exception as exc:
            attachment_failures.append({
                "title": str((attachment["record"] or {}).get("title") or ""),
                "url": attachment["url"],
                "error": str(exc),
            })
    return {
        "requested": len(records),
        "saved": len(records),
        "failed_count": 0,
        "failed": [],
        "attachments_requested": len(attachment_jobs),
        "attachments_saved": attachments_saved,
        "attachment_failed_count": len(attachment_failures),
        "attachment_failures": attachment_failures,
        "mode": "local-connector",
        "zotero_version": local_zotero_status()["version"] if require_available else None,
        "collection_policy": "current-zotero-selection",
    }
