# onboarding — Architecture Brief

> Module: `onboarding` (Onboarding Toolbox) · Category: Hidden · Depends: `web` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/onboarding.facts.json` · Frontend: `doc/revres/frontend/onboarding.frontend.json`

## 1. Summary

`onboarding` is the **reusable onboarding-panel framework** behind Odoo's step-by-step
"getting started" banners shown in Sales, Invoicing and other app dashboards. It owns
no business document and exposes **0 HTTP routes**: it is firm infrastructure that other
modules build on. The whole module is four small models (`onboarding.onboarding`,
`onboarding.onboarding.step`, `onboarding.progress`, `onboarding.progress.step` —
~11/15/5/4 fields), ~850 Python LOC, a single thin JS controller and some SCSS theming.
Its substance is a **definition-vs-state design** plus a **registration/extension contract**
that downstream apps consume, not data it stores.

## 2. Structure (evidence)

- **Models (4):** a *definition* pair — `onboarding.onboarding` (a named panel,
  `route_name` unique, linking ordered `step_ids`) and `onboarding.onboarding.step`
  (presentation + an opening action) — and a *state* pair — `onboarding.progress`
  (per panel+company) and `onboarding.progress.step` (per step+company).
- **Routes:** none. The framework renders into host dashboards; it serves nothing itself.
- **Security:** 12 access rules, **0 record rules, 0 groups**. CRUD on all four models is
  restricted to `base.group_system`; `base.group_user` has **no read** via ACL — end users
  only ever see the rendered banner.
- **Views:** 2 form + 2 list (the admin maintenance views under *Settings ▸ Technical*).

## 3. Frontend (gap #3)

Minimal and **non-OWL**. extract_frontend reports **present, 1 JS / 0 XML**, **0 OWL
components, 0 registry adds, 0 patches, 0 services**. The frontend is SCSS theming
(`onboarding.scss`, `onboarding.variables[.dark].scss` → `web.assets_backend`,
`web.dark_mode_variables`, `web._assets_primary_variables`) plus one controller:
`static/src/views/form/onboarding_step_form_controller.js` extends the `@web` `FormController`
and overrides `save()` to RPC `action_validate_step` after a step dialog saves, then
reload/close per its `stepConfig`. The banner itself is **server-rendered QWeb**
(`onboarding_templates.xml`: `onboarding_panel` / `onboarding_container` / `onboarding_step`)
driven by generic `data-model`/`data-method` web action handlers — not a bespoke widget.

## 4. Behavior (beyond metadata)

- **Definition vs state:** the panel/step records hold only presentation data; a
  `@api.constrains` (`check_step_on_onboarding_has_action`) blocks linking any step to a
  panel unless it names a `panel_step_open_action_name` opening action. (code-read)
- **Per-company state machine:** completion lives in `onboarding.progress` /
  `onboarding.progress.step` (`not_done`/`just_done`/`done`), unique per
  `COALESCE(company_id,0)`; `onboarding.progress.onboarding_state` is a **stored** rollup
  that is `done` only when every linked step is `just_done`/`done`. (code-read)
- **Lazy materialization:** `_search_or_create_progress` / `_create_progress` (and step-side
  `_create_progress_steps`) create trackers **on first render/action** — a new company has
  no rows until then. (code-read)
- **Completion path:** `action_set_just_done` → `action_validate_step` (the JS entry point);
  `_get_and_update_onboarding_state` is the only place `just_done`→`done` is consolidated
  (one-shot completion message) and the only place the synthetic `'closed'` state (not in
  `ONBOARDING_PROGRESS_STATES`) is injected when `is_onboarding_closed`. (code-read)
- **How others register:** consumers ship `onboarding.onboarding`/`.step` **data records**
  (e.g. `account/data/onboarding_data.xml`), `_inherit` to add `action_open_step_*` actions
  and override `_prepare_rendering_values` for auto-completion (e.g. mark "create invoice"
  done when an `out_invoice` exists), and render `onboarding.onboarding_panel` into their own
  dashboard (`account_journal_dashboard._prepare_rendering_values`). (code-read)

## 5. IT architecture

- **Application:** a reusable getting-started panel/step framework embedded in app
  dashboards; **no HTTP surface of its own**.
- **Software services:** none (0 routes).
- **Data objects:** `onboarding.onboarding`, `onboarding.onboarding.step`,
  `onboarding.progress`, `onboarding.progress.step`.
- **Information flows:** depends `web`; definition (`step_ids`) → ordered action-bearing
  steps; state (`progress`/`progress.step`) with a stored rollup; completion via
  `action_validate_step` → `_get_and_update_onboarding_state`; consumption by host modules
  rendering `onboarding_panel`.

## 6. Business architecture

- **Capabilities (inferred):** define a panel + ordered steps; track per-company/per-step
  setup progress; render a getting-started banner in any dashboard; drive each step to a
  config action and mark it done; auto-complete/close/hide a panel; provide a reusable
  registration/extension contract for downstream apps.
- **Value streams (inferred):** New-app-setup (first render → trackers → pending steps);
  Step-to-Done (click → configure → validate → rollup → completed/closed).
- **Information concepts (auto):** the four onboarding models.
- **Organization / Products (auto):** none (0 groups, no `product.*`).
- **Policies (inferred):** step-needs-action constraint; one tracker per (panel/step, company);
  `is_per_company` scoping with cascade delete; manager-only ACLs.
- **Metrics (inferred):** `onboarding_state` per company, `step_state` per step,
  `is_onboarding_closed`.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** A cross-cutting UI/enablement framework — firm infrastructure
  reused by many apps, with no chain/shop/network document flow of its own (Stabell &
  Fjeldstad "support"; Porter support activity). 0 routes, 0 demo data, four tiny models.
- **APQC: 13.0 Develop and Manage Business Capabilities.** Onboarding is
  capability-enablement / user-adoption tooling: guided configuration, adoption checklists
  and completion tracking — it operationalizes how the firm brings users into ERP
  capabilities. **8.0 Manage Information Technology** was considered (it is code-shipped
  scaffolding) but rejected: unlike `web` (the runtime/asset/RPC platform that *is* IT
  delivery), onboarding runs no infrastructure and hosts no UI runtime — it sits on top of
  `web` and addresses the human/business-capability adoption layer, which is governance/
  enablement (13.0), not IT operations (8.0).

## 8. Fit-to-Standard

- **Standard:** reusable panel + ordered steps; per-company/per-step
  `not_done`/`just_done`/`done` tracking; server-rendered banner QWeb embeddable via
  `_prepare_rendering_values`; per-step opening action + `action_validate_step`;
  close/hide/auto-complete with one-shot completion message and synthetic `closed`;
  multi-company scoping (`is_per_company`).
- **Typical fits:** standard "getting started" banner in Sales/Invoicing dashboards with no
  bespoke UI plumbing; add/remove a step via `step_ids` (progress recomputes); auto-check a
  step from real data by overriding `_prepare_rendering_values`.
- **Common gaps:** embedding the panel in a **new** app's dashboard needs JS/QWeb in that
  host (no route, gap #3); non-trivial step actions/validation must be coded via `_inherit`;
  no out-of-box analytics over progress; editing panels/steps needs `base.group_system`.
- **Drive hints:** `env['onboarding.onboarding'].search([]).mapped(...)` (route_name + state);
  `env.ref('account.onboarding_onboarding_account_invoice')._prepare_rendering_values()`
  (banner payload + materializes progress); `step.action_set_just_done()` then read
  `current_onboarding_state` to watch the rollup; `env['onboarding.progress'].search_read(...)`.

---

*Provenance: facts via `doc/revres/extract_module.py addons/onboarding`; behavior via direct
code-read of `addons/onboarding/models/*.py`; frontend via `extract_frontend.py`; narrative per
`doc/revres/PROMPT.md` / metamodel workflow. Odoo 19.0.*
