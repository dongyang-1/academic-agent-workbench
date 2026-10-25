# Project Decisions

## 2026-07-17

| Item | Decision |
| --- | --- |
| Protocol synchronization | Changing the economics research question automatically regenerates the English query, concept blocks, suggested methods, inclusion criteria, and exclusion criteria; any prior protocol confirmation is cleared. |
| CORE network route | Prefer a direct connection to CORE, then fall back to the Windows system proxy with a longer timeout; never log the API key. |
| CORE result limit | Request exactly the user-selected count because CORE search results can embed full text, references, and related outputs; do not apply the three-times metadata overfetch used by lightweight sources. |
| On-demand translation | Preserve original titles and abstracts; request Chinese translations only on user action and cache them in the active web session. |
| Search modes | Support exploratory and systematic modes; systematic mode requires confirmed inclusion criteria. |
| Reproducibility | Persist each web search as a JSON snapshot plus SQLite index with a result SHA-256 hash. |
| Deduplication | Use DOI, external IDs, normalized title, and fuzzy title plus first author; retain all contributing sources. |
| Candidate scoring | Use a transparent six-dimension score totaling 100; scores prioritize reading and never replace academic judgment. |
| Coverage audit | Flag concentrated time, source, evidence-depth, and method distributions. |
| Screening | Support include, maybe, exclude, and unscreened states with a reason field. |
| User corpus | Accept JSON records and merge them through the same normalization, deduplication, scoring, and session pipeline. |
| Citation handoff | Add RIS, BibTeX, and ENW alongside JSON and CSV. |
| CNKI and manual web | Keep official search-link generation and `manual-check-needed`; interactive browser automation remains a future adapter. |

## 2026-07-14

| Item | Decision |
| --- | --- |
| Enabled no-key sources | Crossref, NBER metadata, DataCite, arXiv |
| Semantic Scholar | Adapter retained but disabled until API key approval. |
| NBER access | Use official weekly TSV metadata with a seven-day cache in workspace `_ai_temp`. |
| Runtime | Provide a standard-library Python CLI and keep output compatible with existing schemas. |
| Free-key candidates | OpenAlex and CORE remain planned until credentials are provided. |
| Manual web sources | Add Google Scholar, SSRN, IDEAS/RePEc, EconPapers, CEPR, IZA, CNKI, and Wanfang as link-generating manual adapters. |
| Full-text downloads | Download only explicit open-access PDF URLs; never bypass provider access controls. |
| CORE | Enable CORE v3 with `CORE_API_KEY` in the Authorization Bearer header; never persist the key. |
| OpenAlex | Enable the Works API with `OPENALEX_API_KEY`; strip `api_key` from logs and redact it from errors. |

## 2026-07-06

| Item | Decision |
| --- | --- |
| First research question | 监管沙盒与创新的关系 |
| English working query | regulatory sandbox and innovation |
| Default result count | 20 candidate papers |
| Can result count change later? | Yes. Change `source_policy.max_records_per_source` and adapter `limit`; schemas do not need changes. |
| Ranking preference | Latest literature first, with topical relevance as a required filter. |
| Active data source | Semantic Scholar only for now. |
| Semantic Scholar API key | Use an API key via environment variable `SEMANTIC_SCHOLAR_API_KEY`; never commit the key to this repository. |
| Downstream receiver | TBD. Keep handoff compatible with screening, synthesis, citation-management, or orchestrator modules. |

## Design implications

- The first eval case should focus on regulatory sandboxes, fintech regulation, and innovation.
- The default output is 20 records, but this is a runtime/config choice rather than a schema constraint.
- Ranking should not simply sort by year; records still need topical relevance and usable metadata.
- API key support belongs in the Semantic Scholar adapter configuration and runtime environment, not in shared schemas.
