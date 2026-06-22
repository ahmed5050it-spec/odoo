# board — Architecture Brief

> Module: `board` · Category: Productivity · Depends: `spreadsheet_dashboard` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/board.facts.json` · Frontend: `doc/revres/frontend/board.frontend.json`

## 1. Summary

`board` is the **"My Dashboard"** framework: it lets any user pin an existing
view/action — a filtered list, pivot, graph, kanban — as a customizable personal
dashboard of live widgets. It is structurally tiny and **frontend-heavy**: a
single virtual model (`board.board`), exactly **1 route** (`/board/add_to_dashboard`),
~144 Python LOC and ~171 XML LOC, against **4 JS files / 3 QWeb templates** of OWL
that implement the actual dashboard. It owns no business data of its own — each
user's dashboard is persisted as an `ir.ui.view.custom` arch. It is firm IT/UI
infrastructure layered on `web` (via `spreadsheet_dashboard`).

## 2. Structure (evidence)

- **Models:** 1 — `board.board`, an `AbstractModel` with `_auto = False` (no SQL
  table). Its only field is `id = fields.Id()`; `create()` is a no-op returning
  `self`.
- **Routes (1):** `/board/add_to_dashboard` (jsonrpc, auth=user) — pins the
  current action/view+context as a dashboard widget. It also reuses
  `/web/action/load` (load each widget) and `/web/view/edit_custom` (persist).
- **Security:** 1 ACL only — `access_board_board_all` grants **read-only** on
  `board.board` to `base.group_user`; no write/create/unlink, no record rules,
  no groups. Persistence is delegated to per-user `ir.ui.view.custom` rows.
- **Views:** 1 form — `board_my_dash_view` (`<board style="2-1"><column/></board>`)
  wired to the `open_board_my_dash_action` act_window under the Spreadsheet
  Dashboards menu.

## 3. Frontend (gap #3)

The interactive dashboard lives entirely in OWL/JS under `static/src` and is
invisible to Python metadata. extract_frontend reports **present, 4 JS / 3 XML**,
3 catalogued components (`AddToBoard`, `BoardAction`, `BoardController`) and one
registry add (`views:board`). `BoardController` provides the layout engine:
`useSortable` drag-and-drop across columns (`moveAction`), `selectLayout`
(e.g. `2-1`, `1-1-1`), `toggleAction` fold/unfold, `closeAction` remove. Each
mutation calls `saveBoard()`, which re-renders the `board.arch` template to XML
and POSTs it to `/web/view/edit_custom`. `BoardArchParser` (board_view.js) parses
the saved arch into column/action descriptors. **None of this is reverse-engineerable
from Python metadata** — it is the substance of the module (gap #3).

## 4. Behavior (beyond metadata)

- **`board.board` virtual model:** `_auto = False` → no table; the lone `id`
  field exists only so the web client can init a dummy form record via
  `onchange()`. `create()` is a no-op. The dashboard has no business record.
  (code-read)
- **`get_view` per-user arch injection:** after `super().get_view()`, it looks up
  `ir.ui.view.custom` for `(user_id=env.uid, ref_id=view_id)` and swaps in the
  user's saved arch. `_arch_preprocessing` then sets `js_class='board'` (so a
  `BoardController` is instantiated, not a `FormController`) and strips invisible/
  unauthorized `<action>` children. (code-read)
- **`/board/add_to_dashboard` (pin):** resolves `open_board_my_dash_action`, loads
  the user's board arch, inserts a new `<action>` (name=action_id, view_mode,
  context, domain) into the first `<column>`, and creates an `ir.ui.view.custom`
  row for the user. `allowed_company_ids` is stripped from the saved context so
  multi-company filtering still applies. (code-read)
- **`BoardAction` render:** each saved `<action>` becomes a live mini-view —
  `rpc('/web/action/load')` then an embedded `<View>` with the control panel
  hidden, re-fetching current data. Widgets are live, not snapshots. (static)

## 5. IT architecture

- **Application:** `board` — My Dashboard framework: a virtual form-view shell +
  OWL dashboard widget host, layered on `web`/`spreadsheet_dashboard`.
- **Services:** `/board/add_to_dashboard`; reuses `/web/action/load`,
  `/web/view/edit_custom`.
- **Data objects:** `board.board` (virtual). Real persistence:
  `ir.ui.view.custom(user_id, ref_id, arch)`.
- **Flows:** *pin* (AddToBoard cogMenu → add_to_dashboard → create custom view) ·
  *render* (get_view swaps user arch → js_class='board' → BoardController →
  per-widget BoardAction → /web/action/load) · *edit* (drag/layout/fold/remove →
  saveBoard → /web/view/edit_custom → CLEAR-CACHES).

## 6. Business architecture

- **Capabilities (inferred):** compose a personal dashboard from pinned
  views/actions; pin any non-form act_window view with its context+domain;
  arrange widgets (layout, drag-and-drop, fold, remove); render saved widgets as
  live mini-views; persist each user's dashboard independently.
- **Value streams (inferred):** *Pin-to-Dashboard* (open view → Add to my
  dashboard → saved as widget) and *Open-to-Render* (open My Dashboard → load
  user arch → mount BoardController → live per-widget render).
- **Information concepts (auto):** `board.board` (shell), `ir.ui.view.custom`
  (per-user persistence), pinned `<action>` widget.
- **Organization (auto):** `base.group_user` (read access for all internal users).
- **Policies (inferred):** read-only ACL on the model; `get_view` scopes arch to
  `env.uid` (strictly personal); `_arch_preprocessing` trims unauthorized
  actions; `allowed_company_ids` removed from saved context.
- **Strategy:** null (human).

## 7. Classification

- **Value model: support.** A personal-dashboard UI framework — firm IT
  infrastructure with no business object of its own (Stabell & Fjeldstad
  "support"; Porter support activity). The substance is frontend; the model is
  virtual and persistence is delegated.
- **Activity class: support.** Cross-cutting tooling every app reuses; produces
  no primary value-chain output.
- **APQC: 13.0 Develop and Manage Business Capabilities.** board's purpose is
  personal performance/management dashboards — each user assembling their own
  management view of KPIs/data under the Spreadsheet Dashboards menu — mapping to
  13.0's performance-/capability-management intent. **8.0 Manage Information
  Technology** was considered (board is UI plumbing like `web`) but rejected:
  unlike `web` (a concrete runtime/application platform = IT delivery), board
  delivers no IT service of its own; it is a thin self-service capability for
  business users.

## 8. Fit-to-Standard

- **Standard:** per-user "My Dashboard"; "Add to my dashboard" cog-menu on any
  non-form act_window view (captures context+domain); multi-column layouts with
  drag-and-drop; fold/remove; live embedded view widgets; per-user persistence
  via `ir.ui.view.custom`.
- **Typical fits:** power users building a personal KPI/working-set dashboard;
  pinning a filtered+grouped list or pivot/graph as a recurring widget;
  lightweight personal alternative to a bespoke dashboard view.
- **Common gaps:** shared/team dashboards (per-user only); bespoke widget types
  beyond embedding a view (OWL/JS dev, gap #3); computed cross-record KPIs (use
  `spreadsheet_dashboard`); pinning form/non-act_window actions (gated out).
- **Drive hints:** `env.ref('board.open_board_my_dash_action').read()`;
  `env['ir.ui.view.custom'].search([('ref_id','=',env.ref('board.board_my_dash_view').id)])`;
  POST `/board/add_to_dashboard` then confirm a new `ir.ui.view.custom` row;
  browser: list view → cog → "Add to my dashboard" → open My Dashboard.
