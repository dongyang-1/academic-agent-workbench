# OpenAlex Adapter

- Endpoint: `GET https://api.openalex.org/works`.
- Authentication: add `api_key` from `OPENALEX_API_KEY` to the live request only.
- Never return, log, persist, or display the keyed URL. Replace the key in any exception message.
- Use `search` to retrieve relevance-ranked candidates, require local concept overlap, then apply the current latest-first policy.
- Reconstruct abstracts by sorting `abstract_inverted_index` tokens by position.
- Prefer `best_oa_location.pdf_url` for lawful open PDF downloads.
- Normalize OpenAlex topics to `fields_of_study`; keep the complete OA location object in `source_specific`.
