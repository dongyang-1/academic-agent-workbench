# Semantic Scholar Search Cases

These cases test whether the first source adapter can produce useful economics literature candidates while preserving merge-compatible output.

## Case 1: Regulatory sandbox and innovation

Input focus:

- Field: financial economics, regulation, innovation economics.
- Concepts: regulatory sandbox, fintech regulatory sandbox, innovation, financial innovation.
- Preferred source: `semantic-scholar`.
- Default count: 20 candidate papers.
- Ranking: latest literature first.

Expected checks:

- Generates query variants for regulatory sandbox, fintech, and innovation.
- Keeps `source_id` as `semantic-scholar` in search logs.
- Reads API key from `SEMANTIC_SCHOLAR_API_KEY` when executing live searches.
- Returns no more than 20 records by default.
- Ranks newer literature first after filtering for topical relevance.
- Notes whether retrieved records focus specifically on fintech sandboxes or broader regulatory experimentation.

## Case 2: Minimum wage and employment

Input focus:

- Field: labor economics.
- Concepts: minimum wage, employment.
- Preferred source: `semantic-scholar`.

Expected checks:

- Generates at least three query variants.
- Keeps `source_id` as `semantic-scholar` in search logs.
- Normalizes `paperId` into `source_record_ids.semantic-scholar`.
- Marks records as `metadata-only` unless metadata is externally verified.

## Case 3: Air pollution and labor productivity

Input focus:

- Field: environmental economics and labor economics.
- Concepts: air pollution, productivity, labor supply.
- Preferred source: `semantic-scholar`.

Expected checks:

- Includes field terms and method terms in query variants.
- Preserves abstract snippets when available.
- Notes coverage gaps for economics-specific databases not yet connected.

## Case 4: Cash transfers and household welfare

Input focus:

- Field: development economics.
- Concepts: cash transfer, household welfare, poverty.
- Preferred source: `semantic-scholar`.

Expected checks:

- Separates general discovery results from economics-specific verification needs.
- Flags possible duplicate working paper and journal versions.
- Produces handoff notes for screening or synthesis modules.
