# web_tour — Architecture Brief

> Module: `web_tour` · Category: Hidden · Depends: `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/web_tour.facts.json` · Frontend: `doc/revres/frontend/web_tour.frontend.json`

## 1. Summary

`web_tour` is Odoo's **guided onboarding-tour framework** and **headless
integration-test tour engine**: step-by-step interactive walkthroughs that point
at the live UI, plus the macro runner that drives the UI in automated tests. Like
`web`, its substance is **frontend, not data** — a thin Python tail (~396 LOC, 2
real models `web_tour.tour` / `web_tour.tour.step`, 0 routes) over a ~16-file
OWL/JS subsystem. It auto-installs on top of `web` and is reused by virtually
every app for both user adoption and QA.

## 2. Structure (evidence)

- **Models:** `web_tour.tour` (8 fields) 1—n `web_tour.tour.step` (6 fields), plus
  inherit-only extensions of `ir.http` (session_info) and `res.users`
  (`tour_enabled`). `web_tour.tour` n—n `res.users` via `user_consumed_ids`.
- **Routes:** none — interaction is entirely RPC (`@api.model` methods) + JS.
- **Security:** 4 access rules, 0 record rules — `group_system` writes
  tours/steps, `group_user` is read-only.
- **Views:** 1 form, 2 list, 1 search (tour authoring backend).

## 3. Frontend (gap #3 — strongly emphasized)

This is where `web_tour` lives. extract_frontend reports **present, 16 JS / 5 XML**,
3 OWL components (`OnboardingItem`, `TourPointer`, `TourRecorder`), 3 registry
adds (`services:tour_service`, `fields:tour_start_widget`, `views:tour_list`), a
`TourHelpers.prototype` patch, and 8 asset bundles. The core is the **`tour_service`**:
it exposes `odoo.startTour`, validates each step against a `StepSchema`, persists
run-state in **localStorage** (`tour_state.js`) so a tour survives reloads/redirects,
and lazily `loadBundle()`s one of two engines by mode:

- **Interactive (manual):** `TourInteractive` drives the `TourPointer` OWL overlay
  pointing at the live DOM trigger, wires real DOM consume-events
  (click/input/keydown/pointerdown/pointerup/drop), and a `MacroMutationObserver`
  re-resolves triggers on every mutation (even stepping `backward()` if an anchor
  vanishes).
- **Automatic (auto):** `TourAutomatic` compiles steps into a `@web/core/macro`
  Macro and synthesises events headlessly via `hoot-dom` — **the runner
  `HttpCase.start_tour` executes in tests**.

A run-command mini-language (`click`, `fill(text)`, `edit`, `drag_and_drop(sel)`,
chained with `&&`) is parsed into low-level actions. `TourRecorder` records live
interactions into replayable steps. **None of this is in Python metadata.**

## 4. Behavior (beyond metadata)

- **Per-user consumed-state:** `consume(tourName)` links the (internal) user into
  `user_consumed_ids` via `Command.link`+`sudo()`; `get_current_tour()` returns the
  first `custom=False` tour NOT IN the user — the engine that chains onboarding.
  (code-read)
- **Onboarding toggle:** `res.users.tour_enabled` is computed TRUE only for an
  admin on a **non-demo, non-test** DB; `switch_tour_enabled` flips it (debug menu).
  (code-read)
- **Bootstrap wiring + registration:** `ir.http.session_info()` injects
  `tour_enabled` + `current_tour` so the client auto-starts at page load. Tours
  register via JS registry `web_tour.tours` OR DB rows (exportable to a `.js`
  attachment via `export_js_file`). (code-read)
- **Frontend dual engine:** interactive pointer overlay vs headless hoot-dom macro
  runner, with localStorage resume. (static)

## 5. IT architecture

- **Application:** onboarding-tour framework + headless test tour engine on `web`.
- **Software services:** `consume`, `get_current_tour`, `get_tour_json_by_name`,
  `export_js_file`, `switch_tour_enabled`, extended `ir.http.session_info`; client
  `odoo.startTour` / `startTourRecorder`.
- **Data objects:** `web_tour.tour`, `web_tour.tour.step`.
- **Information flows:** `session_info` → client auto-start; `onTourEnd` →
  rainbow_man + `consume` → next tour; `HttpCase.start_tour` → `TourAutomatic` →
  hoot-dom; localStorage persists current_tour/index/config.

## 6. Business architecture

- **Capabilities (inferred):** author & store tours; run interactive onboarding
  walkthroughs; track per-user completion; run tours headlessly as tests; record
  interactions into tours; gate/toggle onboarding.
- **Value streams (inferred):** Onboard-a-User; Author-to-Run.
- **Information concepts (auto):** `web_tour.tour`, `web_tour.tour.step`,
  `tour_enabled`, `user_consumed_ids`.
- **Organization (auto):** `group_system` (CRUD), `group_user` (read-only).
  **Products:** none.
- **Policies (inferred):** admins write / users read; onboarding auto-enabled only
  on non-demo non-test DB; consume restricted to internal users; custom tours
  excluded from auto-run.
- **Metrics (inferred):** per-user completion (`user_consumed_ids`); test
  pass/fail + per-step timeout logs.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `web_tour` is cross-cutting firm IT infrastructure
  with **no business object of its own** — its models describe the guidance tooling
  itself, not any customer/product/order (Porter support activity; Stabell &
  Fjeldstad "support"). It creates no primary value in any chain/shop/network; it
  is the user-adoption + test-automation framework `auto_install`ed on `web`.
- **APQC 8.0 Manage Information Technology.** Two counts: user-adoption / app
  onboarding tooling (deploy/operate IT solutions, support users) and the headless
  tour runner = test automation (develop & test software / IT quality). **13.0
  Develop and Manage Business Capabilities** was considered (tours teach how to
  operate capabilities) but rejected — 13.0 is capability governance/portfolio,
  whereas `web_tour` is a concrete running IT runtime; its work is application
  delivery and quality, i.e. IT execution → 8.0.

## 8. Fit-to-standard

- **Standard:** declarative `web_tour.tours` registry tours; interactive pointer
  overlay with mutation-aware re-triggering; headless `start_tour` test engine;
  per-user consumed-state + onboarding chaining; enable/disable toggle; DB tours
  with `.js` export; tour recorder; run-command mini-language.
- **Typical fits:** register a product onboarding tour; write `self.start_tour(...)`
  integration tests; author a simple custom tour as data rows.
- **Common gaps:** custom run-commands/assertions beyond the macro vocabulary
  (JS, gap #3); onboarding analytics/dashboards beyond raw `user_consumed_ids`;
  branching/conditional flows; localized tour-content management at scale.
- **Drive hints:** `env['web_tour.tour'].get_current_tour()`;
  `env['res.users'].switch_tour_enabled(True)` then inspect
  `session_info()['current_tour']`; browser `GET /odoo?tour=<name>`;
  `HttpCase.start_tour('/odoo','<tour>',login='admin')`.
