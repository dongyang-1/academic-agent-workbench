# Zotero access and portability

Read this reference on first use in a new environment or when library access fails.

## What this package supplies

This package supplies research and evidence-verification instructions. It has no executable extraction pipeline, Python environment, connector installation, account credentials, library database, article PDFs, Word template, or CSL file. Configure the available tools for the recipient's environment; do not assume tools from the originating project exist.

## Choose an available source route

Use a working Zotero connector/API when available. Establish the intended library, collection identity, direct-versus-recursive membership, and whether attachment contents are available. Metadata access does not prove full-text access. A group library may require separate access rights. Never put access tokens into the skill or ordinary output files.

If no connector is available, proceed with an explicitly supplied collection export plus readable attachments. Suitable bibliographic exports may include Zotero RDF, CSL JSON, BibTeX or RIS, depending on the reader. Verify which fields and collection relationships survive the chosen export. Prefer retaining library IDs and item keys; do not invent them when absent. Ask for the missing scope mapping only when it cannot be established from the supplied material.

An authorized local database route is another option. Locate the recipient's actual data directory; do not copy the originating user's path. Open the source read-only. If making a database snapshot, use a consistent SQLite backup or a quiescent copy that preserves committed WAL state. Do not treat an immutable read that skips active WAL changes as a current library view. Resolve attachment paths for that machine and preserve the source database and attachments.

## Reconcile scope and identity

- Establish the user's requested collection and whether to include descendants; do not inherit collection names or child-folder preferences from another project.
- Count parent studies separately from PDFs, notes and snapshots. Report raw records and deduplicated studies separately when duplicates occur.
- Use library identity plus item key when available. A matching title alone is a candidate duplicate, not proof of identical versions; check author, year, DOI and version before merging evidence.
- Record read coverage accurately: metadata, abstract, searchable full text, and passages/tables actually checked. Having extracted an entire PDF does not mean every page was read.
- If an attachment is scanned, use the environment's available OCR if needed and verify the cited passage. Keep PDF physical page and printed page distinct.

## Capability-dependent outputs

For prose and evidence matrices, readable metadata and source text are sufficient. PDF extraction tools are needed only when the chosen input route requires them; there is no mandatory Python package list for this instruction-only skill.

For editable Word or Excel output, use the recipient's available document/spreadsheet tooling. If required skills or renderers are absent, disclose the missing capability and produce an authorized supported format; do not claim rendering or visual checks were performed.

For Zotero-managed Word citations, also read [zotero-word-integration.md](zotero-word-integration.md). Desktop Word, the actual Zotero Word integration, access to the intended library, an appropriate CSL style, and a way to operate and verify the plugin are necessary. Successful ordinary DOCX generation is not dynamic citation integration. Item keys from an export or copied document may differ after import into a new library; resolve identities before insertion.

Use an institution's formatting guide only when it applies to the recipient's requested deliverable. No original project's university formatting rules are bundled here.
