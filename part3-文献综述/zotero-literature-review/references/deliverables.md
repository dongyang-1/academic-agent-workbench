# Editable deliverables

Read this reference when the user requests Word, Excel, or institution-formatted final files.

## Formatting authority

If the workspace contains a university or publisher formatting guide:

1. read it before authoring;
2. extract page, heading, body, spacing, header/footer, citation, and bibliography rules;
3. use those rules instead of generic Word defaults;
4. record any requirement that cannot be implemented or verified.

Do not silently substitute a familiar citation style for an institution-specific style.

## Word literature review

The editable Word file should normally contain:

- literature-review title or chapter heading;
- thematic synthesis sections;
- a separate research-review section;
- references or a clearly labeled temporary reference list;
- required headers, footers, page numbers, margins, typography, spacing, and heading hierarchy.

Quality gates:

- use real Word styles for repeatable formatting;
- preserve first-line indentation and paragraph spacing consistently;
- keep reference hanging indents stable;
- ensure headings are not stranded at page bottoms;
- render every page and inspect for clipping, overlap, missing glyphs, and awkward page breaks;
- structurally verify citation counts, reference counts, and field types after rendering.

## Citation states in Word

Use explicit language for the actual state:

- **Zotero dynamic citation** — created and recognized by the Zotero Word plugin.
- **Ordinary citation text** — formatted author–year or numeric text without Zotero management.
- **Pending Zotero insertion marker** — a unique marker intended for later plugin insertion.

If dynamic integration is unavailable, a pending marker may include author, year, and optionally the verified Zotero item key. Label the bibliography as temporary and state that Refresh does not manage it.

## Citation-audit workbook

Create a filterable, editable table with:

- one row per citation occurrence;
- section, paragraph, and citation position;
- displayed citation;
- Zotero author, year, title, library ID, and item key;
- supported prose and viewpoint;
- source evidence and page;
- read status;
- verification result and risk;
- whether a Zotero dynamic field exists;
- whether human Zotero insertion is required;
- notes.

Recommended usability:

- freeze the header and key locator columns;
- use wrapped text and deliberate column widths;
- enable filters;
- use validation lists for status and risk;
- use conditional formatting for medium/high risk;
- include a compact summary sheet driven by formulas;
- keep a separate reference-metadata sheet with one row per cited item.

Render and inspect every worksheet. Scan formulas for errors and verify that Zotero keys are present and unique.

## Cross-artifact consistency

Before delivery, reconcile:

- number of citation occurrences in Word and Excel;
- set of cited Zotero item keys;
- author/year/title metadata;
- dynamic-versus-pending citation status;
- bibliography entries;
- unresolved risks and human-review flags.

The Word document and audit workbook must describe the same citation state.
