---
name: zotero-literature-review
description: Build evidence-traceable academic literature reviews from a user-scoped Zotero collection, including literature inventory, thematic viewpoint–literature matrices, synthesis, research gaps, citation verification, and thesis-ready Word/Excel deliverables. Use when the user asks to review, classify, synthesize, or audit literature stored in Zotero; do not use for ordinary web-only literature searches.
---

# Zotero Literature Review

Use the user's scoped Zotero collection as the evidence boundary. Produce a literature review whose claims, citations, and bibliography can be traced back to real collection items and, when available, their full text.

## Non-negotiable evidence rules

- Treat Zotero item metadata and attached originals as the primary evidence.
- Record whether each item was read as full text, abstract only, or metadata only.
- Never infer methods, samples, mechanisms, results, pages, DOI, volume, issue, or page range from a title.
- Do not turn correlations into causal effects or remove limitations stated by the source.
- Do not add outside literature unless the user explicitly authorizes expansion beyond the collection.
- Keep any collection-level research-gap claim scoped to the reviewed collection; do not imply an exhaustive field-wide search.
- Preserve user-confirmed classifications, core conclusions, and matrices unless new primary evidence requires a correction. Explain corrections explicitly.

## Choose the current stage

Respect staged requests. Do not jump ahead when the user asks for only one stage.

1. **Inventory** — enumerate collection items and create evidence cards.
2. **Classification** — group by research problem, mechanism, object, or method rather than geography alone.
3. **Viewpoint matrix** — connect claims to multiple sources and expose consensus, disagreement, evolution, method differences, and unresolved questions.
4. **Formal synthesis** — write around viewpoints using the pattern “claim → multi-source evidence → relationship among studies → subsection conclusion or limitation.”
5. **Research review** — state supported gaps without diminishing prior work; lead naturally to the user's research question.
6. **Citation audit** — verify every cited author, year, claim, source passage, page, and bibliography entry.
7. **Artifacts** — create editable Word and Excel outputs only when requested.
8. **Zotero Word integration** — create dynamic fields only through the actual Zotero Word plugin and only when the integration can be operated and verified end to end.

For stages 1–6, read [references/research-workflow.md](references/research-workflow.md). For editable deliverables, also read [references/deliverables.md](references/deliverables.md). For dynamic Zotero citation or bibliography requests, read [references/zotero-word-integration.md](references/zotero-word-integration.md) before changing the document.

## Core workflow

### Establish scope and access

For first use on another machine, or if Zotero access is unavailable, read [references/access-and-portability.md](references/access-and-portability.md). This skill provides workflow instructions; it does not install a Zotero connector or provide library credentials.

- Confirm the collection name or key and the user's research question.
- Check whether Zotero is reachable and whether attachments can be read.
- Count parent bibliographic items separately from PDF attachments, notes, and snapshots.
- Reconcile the collection count before analysis.

### Build source-grounded evidence

- Normalize author, year, title, publication, volume, issue, pages, DOI, Zotero item key, and attachment status.
- Extract the research object, question, mechanism, data/sample, method, result, limitations, relevance, theme, and core-literature status.
- Attach a source location to every substantive result used later.
- Mark missing or unresolved fields instead of guessing.

### Synthesize relationships

- Organize literature around research questions and theoretical logic.
- Combine studies that support the same viewpoint.
- Explain whether apparent disagreement comes from samples, variables, identification, objects, periods, or mechanisms.
- Trace how later studies extend earlier work.
- Separate stable findings from open questions.
- Distinguish direct evidence for the user's object from mechanisms merely transferable from another market or population.

### Draft and audit

- Write paragraphs with a clear topic sentence and logical transitions.
- Cite multiple compatible studies together where appropriate.
- Avoid one-paper-per-paragraph summaries and author-by-author lists.
- Keep language proportional to the evidence.
- Run a final bidirectional check: every in-text citation appears in the bibliography, and every bibliography entry is actually cited unless the user requests a broader reading list.
- Put uncertain citations, missing pages, strong causal wording, incomplete metadata, and multi-purpose reuse into the audit table with an appropriate risk level.

## Artifact requirements

When the user provides an institutional formatting document, read it before generating the final artifact and treat it as the highest formatting authority.

When creating a Word review and citation-audit workbook:

- use the document and spreadsheet artifact skills available in the environment;
- keep outputs editable;
- render and visually inspect the latest Word document and every workbook sheet;
- verify references structurally after rendering;
- disclose any rendering or integration limitation accurately.

## Zotero field integrity

Never describe plain text, bookmarks, content controls, manually assembled Word fields, or directly edited DOCX XML as Zotero-managed citations.

Only report a conversion as successful when the actual Zotero Word plugin created the citation, Add/Edit Citation recognizes it, Add/Edit Bibliography manages the bibliography, and Refresh succeeds. If the environment cannot complete and verify those actions, stop before conversion and preserve the source document.
