# spreadsheet_dashboard — Architecture Brief

> Module: `spreadsheet_dashboard` · Category: Productivity/Dashboard · Depends: `spreadsheet` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/spreadsheet_dashboard.facts.json` · Frontend: `doc/revres/frontend/spreadsheet_dashboard.frontend.json`

## 1. Summary

`spreadsheet_dashboard` is the **BI / analytics dashboard layer** built on Odoo's
spreadsheet engine. A "dashboard" is a stored o-spreadsheet workbook (pivots,
lists, charts, scorecards bound to business models via `ODOO()` formulas) rendered
in a dedicated **OWL viewer**. It is a frontend-heavy, infrastructure-style module:
only **3 thin Python models** (`spreadsheet.dashboard`, `.group`, `.share`) and
**4 routes** that mostly serialize a stored workbook, against **14 JS files / 7 XML
templates** (~664 Python LOC, ~509 XML LOC). The substance lives in the browser and
in the spreadsheet JSON, not in the database schema.

## 2. Structure (evidence)

- **Models (3):** `spreadsheet.dashboard` (10 fields, inherits `spreadsheet.mixin`)
  → `spreadsheet.dashboard.group` (4 fields, sectioning) and
  `spreadsheet.dashboard.share` (5 fields, frozen public copy, inherits the mixin).
- **Routes (4):** `/spreadsheet/dashboard/data/<dashboard>` (auth=user, readonly,
  serves the snapshot or a sample), plus the public-share trio
  `/dashboard/share|data|download/<id>/<token>`.
- **Security:** 5 access rules, **4 record rules**, 1 group (`Dashboard 'Admin'`
  under a `Dashboard` privilege) — visibility is rule-driven, not controller-driven.
- **Views:** 2 forms, 2 lists, 1 kanban (back-office authoring of dashboards/groups).

## 3. Frontend (gap #3 — the substance)

extract_frontend reports **present, 14 JS / 7 XML**. The viewer is a real OWL app,
not a view: **`SpreadsheetDashboardAction`** (action `action_spreadsheet_dashboard`,
registered `force:true`, lazy-loaded) renders a `ControlPanel` + a sidebar of
groups/sections + `SpreadsheetComponent` in `dashboard` mode, with global filters,
favorites, URL sync, and a mobile variant (`DashboardMobileSearchPanel`,
`MobileFigureContainer`, `DashboardSearchBar`, `DashboardFacet`,
`DashboardDateFilter`). A reactive **`spreadsheet_dashboard_loader`** service
`webSearchRead`s the published groups and lazily `http.get`s each dashboard's JSON,
building an o-spreadsheet `Model` with an `OdooDataProvider` that re-evaluates cells
on `data-source-updated`. Two o-spreadsheet **patches** add chart-granularity
controls (`ChartDashboardMenu`) and dashboard chart animations (`ChartJsComponent`).
Bundles: `spreadsheet.o_spreadsheet`, `spreadsheet.assets_print`,
`web.assets_backend`. **None of this is reverse-engineerable from Python metadata.**

## 4. Behavior (beyond metadata)

- **Stored workbook → snapshot (code-read):** `_get_serialized_readonly_dashboard()`
  `json.loads`es `spreadsheet_data`, injects the user locale
  (`res.lang._get_user_spreadsheet_locale`) and company currency, attaches empty
  revisions + translation namespace, and returns the snapshot the OWL client hydrates.
- **Sample fallback (code-read):** `main_data_model_ids` declares the reported-on
  models; if `_dashboard_is_empty()` finds any with `search_count([],limit=1)==0`,
  the controller serves a static demo workbook from `sample_dashboard_file_path`
  (`is_sample:true`) instead of blank figures.
- **Visibility (code-read):** record rule `ir_rule_spreadsheet_dashboard` filters
  `base.group_user` to `group_ids ∩ user.all_group_ids`; a company rule filters
  `company_ids`; `Dashboard Admin` bypasses with `[(1,'=',1)]`.
- **Public share (code-read):** `action_get_share_url()` creates a frozen
  `spreadsheet.dashboard.share`, zips xlsx into `excel_export`, returns a
  `.../share/<id>/<uuid-token>` URL; access is double-gated by `consteq()` token +
  the creator still having read access (else `Forbidden`); xlsx download needs
  `base.group_allow_export`.

## 5. IT architecture

- **Application:** BI/analytics dashboard layer on the spreadsheet engine (stored
  workbooks + OWL viewer).
- **Software services:** the 4 routes — readonly dashboard data (with sample
  fallback) and the public share/data/download endpoints.
- **Data objects:** `spreadsheet.dashboard`, `spreadsheet.dashboard.group`,
  `spreadsheet.dashboard.share`.
- **Information flows:** `depends: spreadsheet` (mixin supplies `spreadsheet_data`,
  binary copy, `action_edit_dashboard`, xlsx zipping); viewer → loader →
  `webSearchRead` groups → `http.get` snapshot → o-spreadsheet Model re-evaluating
  `ODOO()` formulas; cells bind to arbitrary business models (`main_data_model_ids`).

## 6. Business architecture

- **Capabilities (inferred):** author/store BI dashboards as spreadsheets; group &
  section them; render interactive read-only dashboards; bind figures to live data;
  serve sample dashboards on empty DBs; scope visibility by group/company; publicly
  share & export; per-user favorites.
- **Value streams (inferred):** Author-to-Publish; View-to-Insight; Share-to-External.
- **Information concepts (auto):** dashboard, dashboard group, share, the spreadsheet
  snapshot, the reported-on "main data model".
- **Organization (auto):** `Dashboard 'Admin'` group + `Dashboard` privilege.
  **Products (auto):** none.
- **Policies (inferred):** the 4 record rules (group / company / admin-bypass /
  share-owner) + token+creator-access share gating + group-delete guard.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Firm-infrastructure / BI tooling (Porter support;
  Stabell & Fjeldstad "support"). It creates no primary value in any one
  chain/shop/network — it is a horizontal analytics-presentation layer reused across
  apps (Finance, Sales, HR, Logistics, Services, Marketing, Website groups are all
  seeded) that binds to whatever models a dashboard's cells reference.
- **APQC: 13.0 Develop and Manage Business Capabilities.** The module delivers the
  analytics/KPI-dashboard capability that lets the organization measure and improve
  its other capabilities (business-performance management). **8.0 Manage Information
  Technology** was considered (it is technical platform code) but rejected: unlike
  `web` (a generic UI runtime = pure IT delivery), this module's purpose is
  business-performance visualization — packaged BI dashboards consumed by analysts to
  make decisions — a business-capability/performance concern sitting on top of the IT
  platform rather than IT delivery itself.

## 8. Fit-to-Standard

- **Standard:** spreadsheet BI dashboards (pivots/lists/charts), grouping + publish,
  interactive viewer (global/date filters, favorites, mobile), group/company-scoped
  visibility, sample fallback, public token sharing + xlsx export, locale/currency
  injection at serve time.
- **Typical fits:** shipping curated per-app dashboards (the `spreadsheet_dashboard_*`
  siblings drop account/sale/hr/pos/website dashboards into the seeded groups);
  restricting a dashboard to a group/company; sharing a frozen dashboard externally
  without backend access.
- **Common gaps:** authoring a dashboard's spreadsheet content/`ODOO()` formulas
  (editor + data modeling, not config); custom OWL widgets beyond the viewer (JS dev,
  gap #3); scheduled/push distribution (not here); no external BI/integration surface
  (gap #7 — 0 HTTP call sites, data stays inside Odoo).
- **Drive hints:** `env['spreadsheet.dashboard.group'].search_read([],['name','sequence'])`;
  `d._get_serialized_readonly_dashboard()[:200]`; `GET /spreadsheet/dashboard/data/<id>`
  (auth=user, cids cookie); `action_get_share_url({...})` to mint a public link then GET it.
