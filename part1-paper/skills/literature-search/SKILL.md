---
name: literature-search
description: Economics literature search workflow for turning a research question into pluggable source-adapter queries, open academic searches, coverage notes, deduplicated candidate papers, and verification logs. Use when the user asks to find, map, update, or audit economics literature, especially when results must remain traceable and merge-compatible with other research-agent modules.
---

# Literature Search

## Core workflow

1. Restate the research question and define the search boundary.
2. Split the topic into concept blocks: outcome, treatment or mechanism, population, context, method, and field.
3. Expand terms with synonyms, economic terminology, JEL codes, known datasets, policies, institutions, and author names.
4. Select source adapters from `config/sources.example.yaml`. Current automated sources: `crossref`, `nber`, `datacite`, `arxiv`, authenticated `core`, and authenticated `openalex`.
5. Build source-specific queries without changing the shared `SearchPlan` schema.
6. Execute or prepare searches through the selected adapter.
7. Normalize results to `schemas/literature-record.schema.json`.
8. Record each search attempt in `schemas/search-log.schema.json`.
9. Deduplicate by DOI, external ids, normalized title, and fuzzy title plus first-author surname; preserve every contributing source id.
10. Score candidates across topic relevance, method value, data relevance, source quality, evidence completeness, and open materials.
11. Check distribution skew across time, source, evidence depth, and methods; report concentration rather than silently accepting it.
12. In systematic mode, require an explicit protocol and record include, maybe, or exclude decisions with reasons.
13. Save reproducible search sessions and offer JSON, CSV, RIS, BibTeX, and ENW handoffs.
14. Package final output according to `schemas/literature-search-output.schema.json`.

## Required outputs

- Search boundary.
- Concept blocks and keywords.
- Search strings by source.
- Candidate literature table.
- Search logs.
- Coverage notes.
- Verification gaps and next actions.
- Search protocol, deduplication audit, quality scores, and distribution advisories.
- Screening decisions and a reproducible session id when the web runtime is used.

## Reference routing

- Read `references/search-workflow.md` when designing or auditing a search process.
- Read `references/source-map.md` when selecting sources for economics literature.
- Read `references/open-public-adapters.md` when running the current no-key adapters.
- Read `references/manual-web-adapters.md` when generating official search links for sources without supported APIs.
- Read `references/core-adapter.md` when using CORE metadata or open-access downloads.
- Read `references/openalex-adapter.md` when using OpenAlex discovery, citation metadata, or OA links.
- Read `references/semantic-scholar-adapter.md` when using the current Semantic Scholar source.
- Read `references/add-source-adapter.md` before adding any new source such as RePEc, NBER, EconLit, Google Scholar, or OpenAlex.

## Guardrails

- Do not copy full copyrighted articles.
- Do not infer paper findings from the title alone.
- Do not treat a working paper and its published version as separate final records unless both versions matter.
- Preserve the original retrieval source and query for each candidate paper.
- Keep source-specific metadata inside `source_specific` so downstream modules are not tied to one provider.
- If an API response is incomplete, mark the record as `metadata-only` or `needs-check`.
- Write NBER caches, raw responses, and test outputs only under workspace `_ai_temp`.
- Download only records with an explicit `open_access_pdf_url`; never bypass authentication, paywalls, CAPTCHA, or provider controls.
- Treat CNKI, Wanfang, Google Scholar, and other manual-web adapters as traceable search launchers until an approved interactive browser adapter exists.
- Treat quality scores as prioritization aids, not as substitutes for reading or research-design assessment.
