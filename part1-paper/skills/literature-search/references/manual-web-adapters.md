# Manual Web Adapters

Use these adapters to generate official search URLs and record them in `SearchLog`. Do not parse result pages automatically unless the provider later offers a documented API or export interface.

| Source | Main use | Access boundary |
| --- | --- | --- |
| Google Scholar | Broad discovery and citation chasing | No supported public search API; manual only. |
| SSRN | Social-science and law working papers | Download only links exposed by SSRN. |
| IDEAS/RePEc | Economics metadata and working papers | Manual keyword search; RePEc API is restricted and has no general search. |
| EconPapers | Alternative RePEc search interface | Manual web search. |
| CEPR | Economics discussion papers | Manual web search and lawful downloads. |
| IZA | Labor-economics working papers | Manual search; direct PDFs are often available. |
| CNKI | Chinese academic literature | Login or institutional access may be required. |
| Wanfang | Chinese academic literature | Login or institutional access may be required. |

For every manual adapter, retain `query_parameters.search_url`, use `manual-check-needed`, and report zero automated records until a researcher imports or verifies results.
