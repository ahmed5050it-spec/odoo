# base_import — Architecture Brief

> Module: `base_import` · Category: Hidden/Tools · Depends: `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/base_import.facts.json` · Frontend: `doc/revres/frontend/base_import.frontend.json`

## 1. Summary

`base_import` is Odoo's **CSV/XLSX data-import framework** — the "Import Records"
wizard plus the matching/mapping/coercion/loading engine reused by **every** list
and kanban view. It is structurally a framework, not a data module: just **2 own
models** (`base_import.import`, a transient wizard; `base_import.mapping`, saved
column→field mappings), **1 HTTP route**, ~1977 Python LOC and ~460 XML LOC. It
owns no business object of its own — it acts **on** every other model via a
dynamic `res_model` + `env[model].load()`. Most of the UI is OWL/JS (gap #3): the
wizard is a client action, not a Python view.

## 2. Structure (evidence)

- **Models (2 own + 2 extensions):** `base_import.import` (TransientModel, fields
  `res_model`/`file`/`file_name`/`file_type`, ~31 methods = the engine,
  `_transient_max_hours=12.0`); `base_import.mapping` (persistent: `res_model`
  indexed, `column_name`, `field_name`). Extensions: `base.get_import_templates()`
  hook and `res.users._can_import_remote_urls()` gate.
- **Routes (1):** `/base_import/set_file` (HTTP POST) — uploads raw file bytes onto
  the wizard record.
- **Security:** 2 access rules, 0 record rules, 0 groups.
- **Views:** none in Python/XML — the wizard is an OWL client action (tag `import`).

## 3. Frontend (gap #3 — emphasized)

This is where the wizard lives. extract_frontend reports **present, 10 JS / 8 XML**,
with 8 OWL components: `ImportAction` (the client action, registered via
`registry.category("actions").add("import", …)`), `ImportRecords` (injects the
"Import records" entry into the cogMenu of every list/kanban view, gated on the
view's `import=`/`create=` attributes), `ImportDataContent` (per-column field
pickers sorted Basic/Suggested/Additional/Relational from `get_fields_tree`),
`ImportDataSidepanel` (CSV options: encoding, separator, quoting, date/datetime/
thousands/decimal formats, skip, limit, sheet), `ImportDataProgress` (batched
progress + pause/resume), `ImportDataColumnError`, `ImportDataOptions`,
`ImportBlockUI`. `BaseImportModel` (`import_model.js`) is the client-side engine
driving the round-trips (upload → `parse_preview` → chunked `execute_import`),
translating human date formats to Python strftime and back. **None of this is in
Python metadata** — zero business views, all behaviour in static assets.

## 4. Behavior (beyond metadata)

- **`parse_preview` (file sniffing + mapping):** `_read_file` dispatches by guessed
  mimetype → user type → extension; `_read_csv` auto-detects encoding via
  `chardet` (BOM rectification) and auto-detects the delimiter by trying
  `,`/`;`/tab/space/`|`/unit-sep and keeping the one yielding uniform ≥2-col rows.
  Then `get_fields_tree` (recursive depth 3) + per-column type heuristics
  (`_extract_header_types`). (code-read)
- **Fuzzy column→field matching:** three tiers — saved `base_import.mapping`
  (distance −1, always wins) → exact case-fold on technical name / `@string` /
  en_US label → fuzzy word-distance (`difflib` ratio) below
  `FUZZY_MATCH_DISTANCE=0.2`, then dedup to one column per simple field. (code-read)
- **Type coercion (`_convert_import_data` + `_parse_import_data`):** drops unmapped
  columns, validates row width (else "change the separator" error), coerces dates
  via `strptime`, floats via currency-symbol stripping + separator inference
  (`()`-negatives, scientific notation), binary as URL/base64/filename. Errors
  carry `field`+`field_type` to attach to the right column. (code-read)
- **`execute_import` → `model.load()`:** savepoint-wrapped; runs
  `_handle_multi_mapping` (concatenate multi-mapped char/text/html by sep,
  many2many by comma) and `_handle_fallback_values`, then
  `env[res_model].load(fields, data)` with `import_file=True`,
  `name_create_enabled_fields` (resolve unknown relations by name-search / create
  on the fly), and `_import_limit` batching. `dryrun=True` rolls back + clears
  caches so "Test" surfaces every row error without writing; success persists the
  mapping. Returns `{ids, messages, nextrow, name, binary_filenames}`. (code-read)

## 5. IT architecture

- **Application:** CSV/XLS/XLSX/ODS import framework — sniffing parser, fuzzy
  matcher, coercion engine, transactional loader, and the OWL "Import Records" UI.
- **Software services:** `/base_import/set_file` (upload); RPC `parse_preview`,
  `execute_import`, `get_fields_tree`, `get_import_templates`.
- **Data objects:** `base_import.import`, `base_import.mapping`.
- **Information flows:** browser → `set_file` upload → `parse_preview` (readers +
  field tree + matcher) → `execute_import` → `env[res_model].load()`; optional
  outbound `requests.get(url)` for remote binary columns (admin-gated). Depends on
  `web` (OWL action, registries, orm service, FileInput/dropzone).

## 6. Business architecture

- **Capabilities (inferred):** ingest tabular files with auto encoding/delimiter
  detection; auto-suggest & remember mappings; coerce/validate values; resolve
  relations on load; dry-run with error reporting; batched/resumable bulk load;
  the reusable "Import Records" UI on every list/kanban.
- **Value streams (inferred):** File-to-Records (upload → preview → map → Test →
  fix → commit → open records); Map-Reuse (saved mapping auto-applies next time).
- **Information concepts (auto):** import session, saved mapping, field tree,
  import options, import result.
- **Organization/Products (auto):** none (no groups, no `product.*`).
- **Policies (inferred):** admin-only remote-URL import; file size/timeout/pixel
  caps; Test-before-commit rollback; readonly/magic fields excluded from the tree.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** A cross-cutting data-management framework — firm IT
  infrastructure (Porter support activity; Stabell & Fjeldstad "support"). It
  creates no primary value in any chain/shop/network, owns no business object, and
  acts on every model via dynamic `res_model` + `load()`; `auto_install=true` and
  the cogMenu entry make it ubiquitous.
- **APQC: 8.0 Manage Information Technology.** The work is data management /
  master-data loading — ingesting, cleansing, mapping and loading data into the
  application platform. 13.0 "Develop and Manage Business Capabilities" was
  considered (it underpins onboarding of every other capability) but rejected:
  base_import is a concrete running data-loading utility, not a governance/
  portfolio capability — squarely 8.0. Mirrors the `web` classification.

## 8. Fit-to-Standard

- **Standard:** import CSV/XLS/XLSX/ODS into any model; auto encoding + delimiter
  detection; exact/translation/fuzzy mapping with saved-mapping reuse; type
  coercion (dates, floats/currency, booleans, selection fallbacks); relational
  resolution (External ID, Database ID, name-search, name_create); multi-column
  concatenation; Test (dryrun) with per-column/per-row errors; batched/resumable
  load; admin-gated URL/base64 binary import.
- **Typical fits:** initial data migration/onboarding; recurring loads from a
  third-party system (saved mappings); bulk updates via id/External ID columns.
- **Common gaps:** complex transforms/cleansing (needs ETL); dedup/upsert beyond
  id-matching; custom OWL wizard steps (JS dev, gap #3); scheduled/unattended
  imports; very large files vs worker memory/timeout. External integrations are
  not in base_import (gap #7) — only the optional remote-URL fetch via `requests`.
- **Drive hints:** `odoo shell` create a `base_import.import`, `write` a CSV,
  `parse_preview(...)` to see the mapping; `execute_import(..., dryrun=True)` to
  Test; UI: any list view → cog → "Import records"; `curl -F ufile=@p.csv -F
  id=<import_id> /base_import/set_file`.
