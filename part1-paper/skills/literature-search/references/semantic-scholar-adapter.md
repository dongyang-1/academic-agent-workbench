# Semantic Scholar Adapter

This adapter is the first data-source implementation for the literature-search module.

## Source identity

| Field | Value |
| --- | --- |
| Source id | `semantic-scholar` |
| Provider | Semantic Scholar |
| Official API docs | https://api.semanticscholar.org/api-docs/graph |
| Current role | Broad discovery and metadata retrieval |
| Merge rule | Normalize all provider fields into `LiteratureRecord`; keep provider-only fields in `source_specific`. |
| API key | Read from environment variable `SEMANTIC_SCHOLAR_API_KEY`; do not store the key in files. |

## Query design

Use Semantic Scholar as a broad discovery source. Build several focused keyword queries from the same `SearchPlan` instead of one oversized query.

Recommended query variants:

- Main concept query: treatment or mechanism plus outcome.
- Method query: topic plus empirical method.
- Field query: topic plus economics field.
- Known-author or seed-paper query when available.

## API shape

The stable adapter target is the Semantic Scholar Academic Graph API paper search endpoint.

```text
GET https://api.semanticscholar.org/graph/v1/paper/search
```

Common parameters to model in the adapter:

| Parameter | Purpose |
| --- | --- |
| `query` | Search string generated from concept blocks. |
| `limit` | Number of results requested. |
| `offset` | Pagination offset when needed. |
| `fields` | Comma-separated metadata fields requested from the API. |

When authenticated requests are enabled, read the API key from `SEMANTIC_SCHOLAR_API_KEY` and send it according to the current official documentation. The adapter config currently records the expected header as `x-api-key`, but production execution should verify this against the official docs.

Recommended fields to request when available:

```text
paperId,title,authors,year,venue,publicationVenue,abstract,url,externalIds,citationCount,referenceCount,influentialCitationCount,fieldsOfStudy,publicationTypes,publicationDate,openAccessPdf,isOpenAccess
```

Verify parameter and field availability against the official docs before production execution.

## Normalization mapping

| Semantic Scholar field | LiteratureRecord field |
| --- | --- |
| `paperId` | `source_record_ids.semantic-scholar` |
| `title` | `title` |
| `authors[].name` | `authors` |
| `year` | `year` |
| `venue` | `venue` |
| `url` | `url` |
| `externalIds.DOI` | `doi` |
| `externalIds` | `external_ids` |
| `abstract` | `abstract` and `abstract_snippet` |
| `citationCount` | `citation_count` |
| `referenceCount` | `reference_count` |
| `influentialCitationCount` | `influential_citation_count` |
| `fieldsOfStudy` | `fields_of_study` |
| `publicationTypes` | `publication_types` |
| `openAccessPdf.url` | `open_access_pdf_url` |
| `isOpenAccess` | `is_open_access` |

## Verification rules

- Use `verified` only when key metadata is checked against the source page or a reliable identifier such as DOI.
- Use `metadata-only` when the record comes from API metadata but the full source was not inspected.
- Use `inferred` when economics relevance, method, or JEL code is inferred from title or abstract.
- Use `needs-check` when title, author, year, DOI, or publication venue is missing or inconsistent.

## Known limitations

- Semantic Scholar is a broad scholarly index, not an economics-only curated database.
- Some economics working papers may appear as duplicates across preprint and journal versions.
- Field classification may not map cleanly to JEL categories.
- API availability, rate limits, and fields may change, so production runs should log docs date and query parameters.
