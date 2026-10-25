# Zotero Word integration

Read this reference before attempting to create, convert, edit, refresh, or validate Zotero-managed citations in Word.

## Integrity principle

Only the actual Zotero Word integration may create a citation or bibliography that is reported as Zotero-managed. Do not manufacture Zotero fields by editing DOCX XML or assembling `ADDIN` field instructions.

## Preflight gate

Before modifying the source document, verify all of the following:

1. the task runs in a local desktop environment supported by Word and Zotero;
2. Microsoft Word desktop is accessible;
3. Zotero is running and the intended library is accessible;
4. the Zotero Word add-in is installed and enabled;
5. Add/Edit Citation can be invoked, completed, and verified;
6. Add/Edit Bibliography can be invoked, completed, and verified;
7. Refresh can be executed and its result verified;
8. the required CSL style exists or the user has authorized installation or creation of it.

Installation or macro visibility alone is insufficient. The environment must be able to complete the interactive operation and verify the resulting field through Zotero.

If any condition fails, stop before conversion. Do not create a “dynamic” output file and do not alter the source document.

## Conversion workflow

When the preflight passes:

1. create a recoverable backup;
2. work from the first citation to the last in document order;
3. locate the pending marker or ordinary citation;
4. resolve it only by verified Zotero library ID and item key;
5. invoke Add/Edit Citation through the Zotero Word plugin;
6. put multiple sources from one citation occurrence into one Zotero citation field;
7. preserve locators, prefixes, suffixes, and narrative-author handling;
8. remove the original marker only after Zotero recognizes the inserted citation;
9. remove the temporary manual bibliography;
10. invoke Add/Edit Bibliography under the reference heading;
11. apply the authorized CSL style through Document Preferences;
12. execute Refresh;
13. save to a new filename rather than overwriting the source unless the user explicitly requests replacement.

## Verification

Confirm:

- expected citation count equals active Zotero citation-field count;
- Add/Edit Citation recognizes every sampled field and all exceptional fields;
- multi-source citations remain single fields;
- locators and narrative forms display correctly;
- the bibliography is Zotero-managed;
- Refresh succeeds;
- no orphaned citation exists;
- no pending marker or ordinary citation remains;
- no duplicate manual bibliography remains;
- every field points to the intended library item.

## Required report

Report:

- number converted successfully;
- number not converted;
- each failure position and reason;
- whether all citations are genuine Zotero fields;
- whether the bibliography is a genuine Zotero field;
- whether Refresh was tested successfully;
- whether the document is maintainable through the Zotero Word plugin.

Never count a visually correct citation as successful unless Zotero itself recognizes and refreshes it.
