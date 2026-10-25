# Open Public Source Adapters

## Crossref

- Endpoint: `GET https://api.crossref.org/v1/works`
- Authentication: none.
- Use for broad DOI and journal metadata discovery.
- Treat abstracts, citations, and publication dates as provider-supplied metadata that may be missing.

## NBER

- Metadata directory: `https://data.nber.org/nber_paper_chapter_metadata/tsv/`
- Authentication: none.
- Download `ref.tsv`, `abs.tsv`, `auths.tsv`, `date.tsv`, and `jel.tsv`; cache them in `_ai_temp` for seven days.
- Search locally so results remain reproducible and do not depend on scraping the website.

## DataCite

- Endpoint: `GET https://api.datacite.org/dois`
- Authentication: none for public reads.
- Use mainly for datasets, repository records, reports, preprints, and DOI enrichment.

## arXiv

- Endpoint: `GET https://export.arxiv.org/api/query`
- Authentication: none.
- Use for econometrics, quantitative economics, finance, and computing-adjacent preprints.
- Throttle repeated requests and acknowledge arXiv data use as required by its API guidance.

## Runtime

Run from the project root with `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python -m literature_search.cli "regulatory sandbox innovation" --limit 20 --start-year 2015
python -m literature_search.cli --plan examples/search-plan.open-public.json --output ..\_ai_temp\literature-search-output.json
python -m literature_search.download ..\_ai_temp\literature-search-output.json ..\_ai_temp\literature-pdfs --limit 5
```

Write raw or test output under the workspace `_ai_temp` directory.
