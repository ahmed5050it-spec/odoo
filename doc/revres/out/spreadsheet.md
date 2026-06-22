# spreadsheet — Architecture Brief

> Module: `spreadsheet` · Category: Productivity/Dashboard · Depends: `bus` · `web` · `portal` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/spreadsheet.facts.json` · Frontend: `doc/revres/frontend/spreadsheet.frontend.json`

## 1. Summary

`spreadsheet` is the **o-spreadsheet engine foundation** — the reusable layer that
turns any Odoo record into a stored, data-bound spreadsheet workbook. It ships two
things: the **`spreadsheet.mixin`** storage contract (a workbook persisted as a JSON
attachment) and a **massive OWL/JS application** (~100 JS / 15 XML) that wraps the
bundled `@odoo/o-spreadsheet` library with an Odoo layer — pivots, lists, charts,
global filters, `ODOO()` formulas re-evaluated against live models, plus a standalone
public read-only app. The Python side is a thin skirt: **1 abstract model**, **1
telemetry route** (`/spreadsheet/log`), and **5 read-only helper extensions**
(`res.lang` / `res.currency` / `res.currency.rate` / `ir.model` / `ir.http`). The
substance is the browser engine and the workbook JSON — not the database schema.

## 2. Structure (evidence)

- **Models (1 real + 5 extensions):** `spreadsheet.mixin` (`AbstractModel`,
  `_auto=False`, 4 fields: `spreadsheet_binary_data`, `spreadsheet_data`,
  `spreadsheet_file_name`, `thumbnail`). Extensions add read-only helper RPCs to
  `res.lang`, `res.currency`, `res.currency.rate`, `ir.model`, and an `ir.http`
  `session_info` flag (`can_insert_in_spreadsheet`).
- **Routes (1):** `/spreadsheet/log` (jsonrpc, auth=user) — export/copy/freeze/print
  telemetry only. The substantive server surface is `@api.readonly @api.model`
  helpers batched over `call_kw`, not bespoke routes.
- **Security:** 0 access rules, 0 record rules, 0 groups — access is governed by the
  **host model** that inherits the mixin (e.g. `spreadsheet.dashboard`).
- **Views:** none (no back-office views of its own; the engine is mounted by hosts).

## 3. Frontend (gap #3 — the substance)

extract_frontend reports **present, ~100 JS / 15 XML**. The product is an OWL app
fronted by the bundled `@odoo/o-spreadsheet` library, wrapped by
**`OdooSpreadsheetModel`** (`model.js`) and the **`SpreadsheetComponent`** action root.
On top of the generic grid it adds: `data_sources/` (the `OdooDataProvider` +
`ServerData` RPC batcher), `pivot/` & `list/` (`OdooPivot`/`OdooPivotModel`,
`ListDataSource`, reusing `@web`'s `pivot_model.js`), `chart/` (odoo charts, geo via
`chartjs-chart-geo` + treemap), `global_filters/` (date/relation/text/numeric),
`ir_ui_menu/` (clickable cells opening Odoo views/menus), `helpers/` (`migration.js`,
`geo_json_service`, **`freezeOdooData`** which snapshots a live workbook to literals +
rasterizes charts to PNG), and a standalone **`public_readonly_app/`** that boots its
own OWL `App` (`PublicReadonlySpreadsheet`) from a dedicated
`spreadsheet.public_spreadsheet` bundle (52 includes). Registry: `actions:action_download_spreadsheet`,
`fields:binary_spreadsheet`, `services:geo_json_service` + `spreadsheetLinkMenuCell`.
Patches: `Grid`/`Spreadsheet` prototypes + chart components. **None of this is
reverse-engineerable from Python metadata.**

## 4. Behavior (beyond metadata)

- **Workbook persistence (code-read):** `spreadsheet_binary_data` is an `ir.attachment`
  blob (base64 JSON); `spreadsheet_data` is **not stored** — `_compute_spreadsheet_data`
  reads the attachment's raw bytes and `_inverse_spreadsheet_data` writes them back.
  A fresh record defaults to `_empty_spreadsheet_data()` (one translated `Sheet1`,
  user locale, `revisionId:'START_REVISION'`).
- **Referential integrity (code-read):** `_check_spreadsheet_data` (`@api.constrains`,
  test mode) walks every model/field-chain (`fields_in_spreadsheet`) and menu xml-id
  (`menus_xml_ids_in_spreadsheet`) referenced in the JSON and raises `ValidationError`
  on dangling references — the BI content is a typed reference into the data model.
- **xlsx export (code-read):** `_zip_xslx_files` zips client-produced parts; image
  parts are resolved from `data:` URIs or `/web/image/<id>` via `ir.binary`.
- **ODOO formula engine (static):** `OdooDataProvider` (EventBus) + `ServerData`
  coalesce cell requests into batched `read_group`/`web_search_read` RPCs and fire
  `data-source-updated` to drive re-evaluation; a dashboard/document is a stored
  workbook whose figures are **computed in the browser**.
- **Scope note (code-read):** collaborative editing (`dispatch_spreadsheet_message`,
  `save_spreadsheet_snapshot`, revisions) and the `/spreadsheet/data/<model>/<id>`
  load+save routes the JS references are **not in this community module** — they ship
  in `spreadsheet_edition` (enterprise). This module is engine + storage + public surface.

## 5. IT architecture

- **Application:** the o-spreadsheet engine foundation — `spreadsheet.mixin` storage
  contract + the OWL spreadsheet client with Odoo data sources + a public read-only app.
- **Software services:** `/spreadsheet/log` (telemetry) plus the `call_kw` helpers
  (`get_locales_for_spreadsheet`, `get_company_currency_for_spreadsheet`,
  `get_rates_for_spreadsheet`, `has_searchable_parent_relation`,
  `get_display_names_for_spreadsheet`).
- **Data objects:** `spreadsheet.mixin` (abstract).
- **ERM / flows:** mixin → `ir.attachment` (workbook blob) / `ir.binary` (xlsx images);
  workbook JSON → any business model/field + `ir.ui.menu`; `res.lang`/`res.currency`
  inject locale & currency at render. `depends: bus, web, portal`; **inherited-by**
  `spreadsheet.dashboard`, `documents.document`, `spreadsheet.template`, ….

## 6. Business architecture

- **Capabilities (inferred):** reusable spreadsheet storage contract; in-browser
  spreadsheet engine; live data binding via `ODOO()` formulas; global filters;
  reference validation; locale/currency injection; freeze & xlsx export; public
  read-only rendering; data-export audit.
- **Value streams (inferred):** Author-to-Persist; Open-to-Insight; Freeze-to-Share/Export.
- **Information concepts (auto):** the spreadsheet record, the workbook snapshot, an
  ODOO data source (pivot/list/chart), a global filter, the locale/currency.
- **Organization / Products (auto):** none (governed by host models).
- **Policies (inferred):** `_check_spreadsheet_data` integrity; `/spreadsheet/log`
  egress audit; `@api.readonly` read-replica routing; no own `ir.rule` (host-governed).
- **Stakeholders:** analyst, module developer (inherits/extends the engine), host app,
  external recipient. **Strategy:** null (human). **Metrics:** the export telemetry +
  "infrastructure FOR metrics" (the engine, not the KPIs).

## 7. Value-Configuration Classification

**support / support · APQC 13.0 Develop and Manage Business Capabilities.** Firm
BI-tooling infrastructure (Porter support; Stabell & Fjeldstad "support"): no primary
value in any chain/shop/network — a horizontal analytics-and-document engine reused
across apps. Its substance is the **frontend** (~100 JS) plus a thin server skirt (1
abstract model, 1 telemetry route, 5 helper extensions). **13.0** is chosen over
**8.0 Manage Information Technology** because — unlike `web`, a generic UI runtime that
is pure IT delivery — `spreadsheet`'s purpose is **data-bound analytics** (pivots/lists/
charts over business models, KPI dashboards, frozen reports) consumed for decision-
making, i.e. business-intelligence tooling sitting on top of the IT platform rather
than IT delivery itself. The sibling `spreadsheet_dashboard` is classified identically.

## 8. How to Drive It

- `odoo shell`: confirm `env['spreadsheet.mixin']._auto` is `False` (abstract storage
  contract, not a table).
- `odoo shell`: `rec = env['spreadsheet.dashboard'].search([], limit=1); rec.spreadsheet_data[:200]`
  to see the stored o-spreadsheet workbook JSON behind a concrete record.
- `odoo shell`: `env['res.lang']._get_user_spreadsheet_locale()` and
  `env['res.currency'].get_company_currency_for_spreadsheet()` — the locale/currency
  structs injected into a workbook.
- `odoo shell`: `env['ir.model'].has_searchable_parent_relation(['res.partner'])` —
  the hierarchy-support helper the client batches.

## Open Questions

- Per-workbook data binding (which models/fields each workbook queries) lives inside
  the `spreadsheet_data` JSON, not in ORM metadata.
- Collaborative editing (revisions/snapshots/bus dispatch) + `/spreadsheet/data`
  load+save routes are referenced by the JS but defined in `spreadsheet_edition`
  (enterprise) — out of scope here.
- Runtime row counts not captured (the mixin is abstract; counts live on host models).
- Full inventory of the bundled `@odoo/o-spreadsheet` engine beyond catalogued components.
