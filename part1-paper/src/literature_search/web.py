from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import ssl
import urllib.parse
import urllib.request
try:
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
except Exception:
    ssl._create_default_https_context = ssl._create_unverified_context
from datetime import datetime, timezone
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .runtime import (
    AUTOMATED_SOURCES,
    AVAILABLE_SOURCES,
    MANUAL_SOURCES,
    WORKSPACE_ROOT,
    _record,
    manual_search_url,
    search_literature,
)
from .formats import export_records
from .journal_ranking import enrich_journal_rankings, load_scheme
from .quality import distribution_advisories, enrich_records, merge_records
from .sessions import list_sessions, load_session, save_session, update_screening
from .zotero import save_records_to_zotero, zotero_configuration


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "web"
LATEST_RESULT = WORKSPACE_ROOT / "_ai_temp" / "literature-search-web-latest.json"
SAMPLE_RESULT = WORKSPACE_ROOT / "_ai_temp" / "literature-search-with-openalex.json"
MAX_REQUEST_BYTES = 8 * 1024 * 1024

ECONOMICS_TRANSLATION_TERMS = {
    "监管沙盒": "regulatory sandbox",
    "最低工资政策": "minimum wage policy",
    "最低工资": "minimum wage",
    "金融科技": "fintech",
    "技术创新": "technological innovation",
    "企业创新": "firm innovation",
    "创新": "innovation",
    "监管": "regulation",
    "经济增长": "economic growth",
    "生产率": "productivity",
    "融资约束": "financing constraints",
    "数字经济": "digital economy",
    "人工智能": "artificial intelligence",
    "关系": "relationship",
    "影响": "impact",
    "机制": "mechanism",
}

SOURCE_LABELS = {
    "crossref": "Crossref",
    "nber": "NBER",
    "datacite": "DataCite",
    "arxiv": "arXiv",
    "core": "CORE",
    "openalex": "OpenAlex",
    "econbiz": "EconBiz",
    "world-bank": "世界银行文献库",
    "google-scholar": "Google Scholar",
    "ssrn": "SSRN",
    "ideas-repec": "IDEAS/RePEc",
    "econpapers": "EconPapers",
    "cepr": "CEPR",
    "iza": "IZA",
    "cnki": "CNKI",
    "wanfang": "万方",
    "bfi": "芝加哥大学 BFI",
    "siepr": "斯坦福 SIEPR",
    "lse-cep": "LSE CEP",
}


def load_user_environment(names: tuple[str, ...] = (
    "CORE_API_KEY", "OPENALEX_API_KEY",
)) -> None:
    """Load named Windows user variables without exposing their values."""
    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in names:
                if not os.environ.get(name):
                    try:
                        value, _ = winreg.QueryValueEx(key, name)
                    except FileNotFoundError:
                        continue
                    if value:
                        os.environ[name] = str(value)
    except OSError:
        return


def public_config() -> dict[str, Any]:
    scheme = load_scheme()
    return {
        "module_id": "literature-search",
        "version": "0.6-web",
        "sources": [
            {
                "id": source_id,
                "label": SOURCE_LABELS[source_id],
                "mode": "automated" if source_id in AUTOMATED_SOURCES else "manual-web",
                "configured": (
                    bool(os.environ.get("CORE_API_KEY")) if source_id == "core" else True
                ),
            }
            for source_id in AVAILABLE_SOURCES
        ],
        "zotero": zotero_configuration(),
        "journal_ranking": {
            "scheme_id": scheme["scheme_id"],
            "scheme_name": scheme["scheme_name"],
            "levels": scheme["levels"] + ["待核验"],
        },
        "defaults": {
            "research_question": "监管沙盒与创新的关系",
            "working_query": "regulatory sandbox innovation",
            "start_year": 2015,
            "end_year": 2026,
            "limit": 20,
            "mode": "exploratory",
            "ranking": "combined",
            "concept_blocks": [
                {"concept": "policy", "terms": ["监管沙盒", "regulatory sandbox", "innovation sandbox"]},
                {"concept": "outcome", "terms": ["创新", "innovation", "fintech innovation"]},
            ],
            "requested_methods": [],
            "inclusion_criteria": ["文献直接研究监管沙盒或高度相关的试验性监管制度", "文献报告创新相关结果或分析其作用机制"],
            "exclusion_criteria": ["仅将沙盒作为软件测试概念使用", "缺少可识别的基本学术元数据"],
            "sources": list(AVAILABLE_SOURCES),
        },
    }


def validate_search_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("请求内容必须是 JSON 对象。")
    research_question = str(payload.get("research_question") or "").strip()
    working_query = str(payload.get("working_query") or "").strip()
    query = working_query or research_question
    if not query:
        raise ValueError("请填写研究问题或英文检索式。")

    try:
        limit = int(payload.get("limit", 20))
    except (TypeError, ValueError) as exc:
        raise ValueError("每个来源的结果数必须是整数。") from exc
    if not 1 <= limit <= 100:
        raise ValueError("每个来源的结果数应在 1 到 100 之间。")

    def optional_year(name: str) -> int | None:
        value = payload.get(name)
        if value in (None, ""):
            return None
        try:
            year = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("年份必须是四位整数。") from exc
        if not 1900 <= year <= 2100:
            raise ValueError("年份应在 1900 到 2100 之间。")
        return year

    start_year = optional_year("start_year")
    end_year = optional_year("end_year")
    if start_year and end_year and start_year > end_year:
        raise ValueError("起始年份不能晚于结束年份。")

    raw_sources = payload.get("sources") or list(AVAILABLE_SOURCES)
    if not isinstance(raw_sources, list):
        raise ValueError("数据源必须是数组。")
    sources = list(dict.fromkeys(str(value) for value in raw_sources))
    unknown = sorted(set(sources) - set(AVAILABLE_SOURCES))
    if unknown:
        raise ValueError(f"不支持的数据源：{', '.join(unknown)}")
    if not sources:
        raise ValueError("请至少选择一个数据源。")

    mode = str(payload.get("mode") or "exploratory")
    if mode not in {"exploratory", "systematic"}:
        raise ValueError("检索模式无效。")
    ranking = str(payload.get("ranking") or "combined")
    if ranking not in {"combined", "latest", "citations", "relevance"}:
        raise ValueError("排序策略无效。")

    def string_list(name: str, maximum: int = 30) -> list[str]:
        raw = payload.get(name) or []
        if not isinstance(raw, list):
            raise ValueError(f"{name} 必须是数组。")
        values = [str(value).strip() for value in raw if str(value).strip()]
        return values[:maximum]

    concept_blocks = payload.get("concept_blocks") or []
    if not isinstance(concept_blocks, list):
        raise ValueError("概念块必须是数组。")
    normalized_blocks = []
    for block in concept_blocks[:10]:
        if not isinstance(block, dict):
            continue
        terms = [str(value).strip() for value in block.get("terms", []) if str(value).strip()]
        if terms:
            normalized_blocks.append({"concept": str(block.get("concept") or "concept").strip(), "terms": terms[:20]})

    inclusion = string_list("inclusion_criteria")
    exclusion = string_list("exclusion_criteria")
    protocol_confirmed = bool(payload.get("protocol_confirmed"))
    if mode == "systematic" and (not protocol_confirmed or not inclusion):
        raise ValueError("系统检索需要填写纳入标准并确认检索协议。")
    return {
        "research_question": research_question or query,
        "query": query,
        "start_year": start_year,
        "end_year": end_year,
        "limit": limit,
        "sources": sources,
        "mode": mode,
        "ranking": ranking,
        "concept_blocks": normalized_blocks,
        "requested_methods": string_list("requested_methods"),
        "inclusion_criteria": inclusion,
        "exclusion_criteria": exclusion,
        "protocol_confirmed": protocol_confirmed,
    }


def _local_economics_translation(question: str) -> str | None:
    remaining = question
    terms: list[str] = []
    for chinese, english in sorted(ECONOMICS_TRANSLATION_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
        if chinese in remaining:
            terms.append(english)
            remaining = remaining.replace(chinese, " ")
    return " ".join(dict.fromkeys(terms)) or None


def translate_research_question(question: str, timeout: int = 15) -> dict[str, str]:
    question = re.sub(r"\s+", " ", str(question or "")).strip()
    if not question:
        raise ValueError("请先填写经济学问题。")
    if len(question) > 500:
        raise ValueError("经济学问题不能超过 500 个字符。")

    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({
        "q": question,
        "langpair": "zh-CN|en",
    })
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "economics-research-agent/0.3"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
        translated = html.unescape(str(payload.get("responseData", {}).get("translatedText") or "")).strip()
        if translated and not re.search(r"[\u4e00-\u9fff]", translated):
            return {"translation": translated, "source": "public-translation-service"}
    except Exception:
        pass

    fallback = _local_economics_translation(question)
    if fallback:
        return {"translation": fallback, "source": "local-economics-glossary"}
    raise ValueError("自动翻译暂时不可用，请稍后重试或手动填写英文检索式。")


def _translation_chunks(text: str, maximum: int = 450) -> list[str]:
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        while len(sentence) > maximum:
            if current:
                chunks.append(current)
                current = ""
            split_at = sentence.rfind(" ", 0, maximum)
            split_at = split_at if split_at > maximum // 2 else maximum
            chunks.append(sentence[:split_at].strip())
            sentence = sentence[split_at:].strip()
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= maximum:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


@lru_cache(maxsize=512)
def _translate_chunk_to_chinese(text: str) -> str:
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({
        "q": text,
        "langpair": "en|zh-CN",
    })
    request = urllib.request.Request(url, headers={"User-Agent": "economics-research-agent/0.5"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    translated = html.unescape(str(payload.get("responseData", {}).get("translatedText") or "")).strip()
    if not translated:
        raise ValueError("翻译服务没有返回结果。")
    return translated


def translate_text_to_chinese(text: Any) -> dict[str, str]:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        raise ValueError("没有可翻译的文本。")
    if len(value) > 5000:
        raise ValueError("单次翻译文本不能超过 5000 个字符。")
    if len(re.findall(r"[\u4e00-\u9fff]", value)) >= max(2, len(value) // 5):
        return {"translation": value, "source": "original-chinese"}
    try:
        translated = " ".join(_translate_chunk_to_chinese(chunk) for chunk in _translation_chunks(value))
    except Exception as exc:
        raise ValueError(f"中文翻译暂时不可用：{exc}") from None
    return {"translation": translated, "source": "public-translation-service"}


def _question_concepts_chinese(question: str) -> tuple[str, str] | None:
    question = re.sub(r"[？?。.]$", "", question.strip())
    patterns = (
        r"^(.+?)对(.+?)(?:的)?(?:影响|作用|效应|机制)$",
        r"^(.+?)与(.+?)(?:之间)?(?:的)?(?:关系|关联|联系)$",
        r"^(.+?)和(.+?)(?:之间)?(?:的)?(?:关系|关联|联系)$",
    )
    return next((match.groups() for pattern in patterns if (match := re.match(pattern, question))), None)


def _question_concepts(question: str, translated: str) -> tuple[str, str]:
    def clean(value: str) -> str:
        return re.sub(r"^(?:the|a|an)\s+", "", value.strip(" ,"), flags=re.IGNORECASE)

    chinese_parts = _question_concepts_chinese(question)

    translated = re.sub(r"[?.]$", "", translated.strip())
    english_patterns = (
        r"(?:the )?(?:relationship|association) between (.+?) and (.+)$",
        r"(?:the )?(?:effect|impact) of (.+?) on (.+)$",
        r"how does (.+?) (?:affect|influence) (.+)$",
        r"(.+?) and (.+?)(?: relationship| association)$",
    )
    english_parts = next((match.groups() for pattern in english_patterns if (match := re.match(pattern, translated, re.IGNORECASE))), None)
    if english_parts:
        return clean(english_parts[0]), clean(english_parts[1])
    if chinese_parts:
        return tuple(_local_economics_translation(part) or part.strip() for part in chinese_parts)  # type: ignore[return-value]

    terms = [term for term in re.split(r"\s+(?:and|versus|vs\.?|on)\s+", translated, maxsplit=1, flags=re.IGNORECASE) if term]
    if len(terms) == 2:
        return clean(terms[0]), clean(terms[1])
    return translated, translated


def generate_search_protocol(question: str) -> dict[str, Any]:
    translated = translate_research_question(question)
    working_query = translated["translation"]
    policy, outcome = _question_concepts(str(question), working_query)
    chinese_parts = _question_concepts_chinese(str(question))
    policy_zh, outcome_zh = chinese_parts or (policy, outcome)
    policy_terms = list(dict.fromkeys([policy_zh, policy]))
    outcome_terms = list(dict.fromkeys([outcome_zh, outcome]))
    causal = bool(re.search(r"影响|效应|因果|作用|effect|impact|causal|affect", str(question), re.IGNORECASE))
    relational = bool(re.search(r"关系|关联|联系|relationship|association", str(question), re.IGNORECASE))
    methods = ["双重差分法 (difference-in-differences)", "事件研究法 (event study)", "工具变量法 (instrumental variables)"] if causal else (["面板回归 (panel regression)"] if relational else [])
    return {
        "research_question": re.sub(r"\s+", " ", str(question)).strip(),
        "working_query": working_query,
        "translation_source": translated["source"],
        "concept_blocks": [
            {"concept": "policy_or_treatment", "terms": policy_terms},
            {"concept": "outcome_or_mechanism", "terms": outcome_terms},
        ],
        "requested_methods": methods,
        "inclusion_criteria": [
            f"文献直接研究“{policy_zh}”或与其高度相关的政策、处理与制度安排",
            f"文献报告“{outcome_zh}”相关结果，或分析其与“{policy_zh}”之间的作用机制",
            "文献具有可识别的学术元数据，并提供足够的标题、摘要或全文信息用于筛选",
        ],
        "exclusion_criteria": [
            f"仅偶然提及“{policy_zh}”或“{outcome_zh}”，或者属于无关研究领域",
            f"未实际考察“{policy_zh}”与“{outcome_zh}”之间的关系",
            "缺少可识别的题名、作者、年份或来源等基本学术元数据",
        ],
        "protocol_confirmed": False,
    }


def run_search(payload: Any) -> dict[str, Any]:
    parameters = validate_search_payload(payload)
    result = search_literature(
        parameters["query"],
        parameters["sources"],
        parameters["limit"],
        parameters["start_year"],
        parameters["end_year"],
        concept_blocks=parameters["concept_blocks"],
        requested_methods=parameters["requested_methods"],
        ranking=parameters["ranking"],
        mode=parameters["mode"],
        inclusion_criteria=parameters["inclusion_criteria"],
        exclusion_criteria=parameters["exclusion_criteria"],
    )
    result["input_summary"] = parameters["research_question"]
    result["search_parameters"] = {key: value for key, value in parameters.items() if key != "research_question"}
    for log in result["search_logs"]:
        if log["source_id"] in {"cnki", "wanfang"}:
            log["query"] = parameters["research_question"]
            log["query_parameters"]["search_url"] = manual_search_url(
                log["source_id"], parameters["research_question"]
            )
    save_session(result, parameters)
    LATEST_RESULT.parent.mkdir(parents=True, exist_ok=True)
    LATEST_RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _corpus_authors(item: dict[str, Any]) -> list[str]:
    raw = item.get("authors") or item.get("author") or []
    if isinstance(raw, str):
        return [value.strip() for value in re.split(r";|\band\b", raw) if value.strip()]
    authors = []
    for author in raw if isinstance(raw, list) else []:
        if isinstance(author, dict):
            authors.append(" ".join(filter(None, (author.get("given"), author.get("family")))) or str(author.get("literal") or ""))
        elif author:
            authors.append(str(author))
    return [author.strip() for author in authors if author.strip()]


def _corpus_year(item: dict[str, Any]) -> Any:
    if item.get("year"):
        return item["year"]
    issued = item.get("issued") or {}
    parts = issued.get("date-parts") or [] if isinstance(issued, dict) else []
    return parts[0][0] if parts and parts[0] else None


def import_corpus(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("已有语料必须包含 records 数组。")
    if len(payload["records"]) > 500:
        raise ValueError("单次最多导入 500 条已有文献。")
    parameters = validate_search_payload(payload.get("search_context") or {})
    imported = []
    rejected = []
    for index, item in enumerate(payload["records"]):
        if not isinstance(item, dict) or not str(item.get("title") or "").strip():
            rejected.append({"index": index, "reason": "missing-title"})
            continue
        source_id = str(item.get("source") or "user-corpus")
        source_record_id = str(item.get("id") or item.get("record_id") or f"import-{index}")
        imported.append(_record(
            source_id, source_record_id, parameters["query"], title=item.get("title"),
            authors=_corpus_authors(item), year=_corpus_year(item),
            venue=item.get("venue") or item.get("container-title") or item.get("journal"),
            issn=item.get("issn") or item.get("ISSN"),
            doi=item.get("doi") or item.get("DOI"), url=item.get("url") or item.get("URL"),
            abstract=item.get("abstract"), citation_count=item.get("citation_count"),
            open_access_pdf_url=item.get("open_access_pdf_url"),
            is_open_access=bool(item.get("open_access_pdf_url")),
            publication_types=item.get("publication_types") or [],
            fields_of_study=item.get("fields_of_study") or [],
            source_specific={"imported_from_user_corpus": True, "original_record": item},
        ))
    existing = payload.get("existing_records") or []
    if not isinstance(existing, list) or len(existing) > 500:
        raise ValueError("现有候选集格式无效或数量过多。")
    merged, dedupe_reasons = merge_records(existing + imported)
    records = enrich_records(merged, parameters["query"], parameters["concept_blocks"], parameters["requested_methods"], parameters["ranking"])
    records = enrich_journal_rankings(records)
    created_at = datetime.now(timezone.utc).isoformat()
    result = {
        "module_id": "literature-search", "version": "0.6", "created_at": created_at,
        "input_summary": parameters["research_question"],
        "source_ids": list(dict.fromkeys(parameters["sources"] + ["user-corpus"])),
        "records": records,
        "search_logs": [{
            "search_log_id": f"log-user-corpus-{created_at}", "source_id": "user-corpus",
            "source_adapter_version": "0.1", "query": parameters["query"],
            "query_parameters": {"mode": "user-corpus-import", "items_received": len(payload["records"])},
            "executed_at": created_at, "execution_status": "success", "records_returned": len(imported),
            "records_kept": len(imported), "error_message": None,
            "notes": f"Rejected {len(rejected)} malformed entries; original corpus was not modified.",
        }],
        "search_protocol": {
            "mode": parameters["mode"], "working_query": parameters["query"],
            "concept_blocks": parameters["concept_blocks"], "requested_methods": parameters["requested_methods"],
            "inclusion_criteria": parameters["inclusion_criteria"], "exclusion_criteria": parameters["exclusion_criteria"],
            "ranking": parameters["ranking"],
        },
        "search_metrics": {
            "records_retrieved": len(existing) + len(imported), "records_after_deduplication": len(records),
            "duplicates_removed": len(existing) + len(imported) - len(records), "dedupe_reasons": dedupe_reasons,
            "records_screened": sum(item.get("screening_status") != "unscreened" for item in records),
            "records_included": sum(item.get("screening_status") == "include" for item in records),
            "records_excluded": sum(item.get("screening_status") == "exclude" for item in records),
            "records_maybe": sum(item.get("screening_status") == "maybe" for item in records),
        },
        "coverage_advisories": distribution_advisories(records),
        "coverage_notes": [f"Imported {len(imported)} user-owned corpus entries; {len(rejected)} entries were rejected with reasons."],
        "verification_gaps": [f"Corpus item {item['index']} rejected: {item['reason']}" for item in rejected],
        "handoff": {"next_modules": ["literature-screening", "literature-synthesis", "citation-management"],
                    "notes": ["User corpus was read-only; the same scoring model was applied to imported and external records."]},
        "search_parameters": parameters,
    }
    save_session(result, parameters)
    LATEST_RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


class LiteratureSearchHandler(BaseHTTPRequestHandler):
    server_version = "EconLitWorkspace/0.5"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    def send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if path == "/api/health":
            self.send_json({"status": "ok"})
            return
        if path == "/api/config":
            self.send_json(public_config())
            return
        if path == "/api/sessions":
            self.send_json({"sessions": list_sessions()})
            return
        if path.startswith("/api/sessions/"):
            try:
                self.send_json(load_session(path.rsplit("/", 1)[-1]))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if path == "/api/sample":
            source = LATEST_RESULT if LATEST_RESULT.exists() else SAMPLE_RESULT
            if source.exists():
                sample = json.loads(source.read_text(encoding="utf-8"))
                enrich_journal_rankings(sample.get("records") or [])
                self.send_json(sample)
            else:
                self.send_json({"records": [], "search_logs": [], "verification_gaps": []})
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/search", "/api/translate", "/api/translate-text", "/api/protocol", "/api/import", "/api/export", "/api/screen", "/api/zotero"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("请求大小无效。")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/translate":
                if not isinstance(payload, dict):
                    raise ValueError("请求内容必须是 JSON 对象。")
                self.send_json(translate_research_question(payload.get("research_question", "")))
            elif path == "/api/translate-text":
                if not isinstance(payload, dict):
                    raise ValueError("请求内容必须是 JSON 对象。")
                self.send_json(translate_text_to_chinese(payload.get("text", "")))
            elif path == "/api/protocol":
                if not isinstance(payload, dict):
                    raise ValueError("请求内容必须是 JSON 对象。")
                self.send_json(generate_search_protocol(payload.get("research_question", "")))
            elif path == "/api/import":
                self.send_json(import_corpus(payload))
            elif path == "/api/export":
                if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                    raise ValueError("导出请求必须包含 records 数组。")
                content, content_type, extension = export_records(payload["records"][:500], str(payload.get("format") or "ris"))
                self.send_json({"content": content, "content_type": content_type, "extension": extension})
            elif path == "/api/screen":
                if not isinstance(payload, dict):
                    raise ValueError("筛选请求格式无效。")
                self.send_json(update_screening(str(payload.get("session_id") or ""), str(payload.get("record_id") or ""),
                                                str(payload.get("status") or ""), payload.get("reason")))
            elif path == "/api/zotero":
                if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                    raise ValueError("Zotero 请求必须包含 records 数组。")
                self.send_json(save_records_to_zotero(payload["records"]))
            else:
                self.send_json(run_search(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": f"操作失败：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, requested_path: str) -> None:
        relative = "index.html" if requested_path in {"", "/"} else requested_path.lstrip("/")
        target = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT.resolve() not in target.parents and target != STATIC_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the literature-search visual workspace.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_user_environment()
    server = ThreadingHTTPServer((args.host, args.port), LiteratureSearchHandler)
    print(f"Literature search workspace: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
