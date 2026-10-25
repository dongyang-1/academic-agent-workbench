# Add Source Adapter

Use this process when adding a new literature data source.

## Adapter checklist

1. Assign a lowercase source id, for example `ideas-repec`.
2. Add the source to `config/sources.example.yaml`.
3. Create a reference file under `skills/literature-search/references/`.
4. Describe official docs, supported query types, limits, and authentication.
5. Map provider fields to `schemas/literature-record.schema.json`.
6. Define how to write `SearchLog` entries for this source.
7. Add at least one eval case that uses the source.
8. Run schema validation after changing JSON files.

## Required adapter sections

- Source identity.
- Query design.
- API or manual search shape.
- Normalization mapping.
- Verification rules.
- Known limitations.

## Compatibility rules

- Do not add provider-specific required fields to `LiteratureRecord`.
- Put provider-only fields under `source_specific`.
- Keep `source_id` stable after it is used by other modules.
- Use `source_record_ids` to store provider paper ids.
- Preserve `external_ids` for DOI, CorpusId, arXiv id, PubMed id, SSRN id, or other identifiers.

## Future source examples

| Source id | Expected role |
| --- | --- |
| `ideas-repec` | Economics working papers and author/series metadata. |
| `nber` | NBER working paper discovery and version tracking. |
| `econlit` | Curated economics indexing when access is available. |
| `openalex` | Open metadata and cross-source enrichment. |
