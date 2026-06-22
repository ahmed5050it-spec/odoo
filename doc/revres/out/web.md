# web — Architecture Brief

> Module: `web` · Category: Hidden · Depends: `base` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/web.facts.json` · Frontend: `doc/revres/frontend/web.frontend.json`

## 1. Summary

`web` is THE frontend framework of Odoo — the WSGI web client, asset bundler, and
the entire OWL (Odoo Web Library) component/registry/service runtime that every
other module renders and dispatches through. It is structurally the **inverse of a
data module**: only ~2 real Python models (`base.document.layout`,
`res.users.settings.embedded.action`) but **68 routes** and a massive static
frontend — **~526 JS files** and **~257 XML/QWeb templates** (~10.8k Python LOC,
~12.4k XML LOC). Its substance lives in the browser, not the database.

## 2. Structure (evidence)

- **Models:** 2 own models + 13 inherit-only extensions of core infra
  (`ir.http`, `ir.ui.view`, `ir.ui.menu`, `ir.model`, `ir.qweb.field.image`,
  `res.users`, `res.company`, `res.config.settings`).
- **Routes (68):** the universal RPC bridge (`/web/dataset/call_kw`,
  `/web/dataset/call_button`), the client bootstrap (`/web`, `/odoo`), session
  (`/web/session/*`), actions (`/web/action/*`), menus, asset/content/image
  serving, report rendering/export, database manager, and a bearer JSON API
  (`/json/1`).
- **Security:** minimal (2 access rules, 2 record rules, 0 groups) — gating is
  done in the bootstrap controller, not via group ACLs.
- **Views:** 3 forms only (document-layout config). No business views.

## 3. Frontend (gap #3 — the prime example)

This is where `web` lives. extract_frontend reports **present, 526 JS / 257 XML**,
40+ catalogued OWL components (`WebClient`, `ActionContainer`, `Breadcrumbs`,
`ActionMenus`, the full field-widget set `CharField`/`BooleanField`/`BinaryField`/
`ColorField`/`AceField`, `CalendarController`, `AutoComplete`, `CodeEditor`, …),
dozens of registry categories (`actions`, `fields`, `services`, `dialogs`,
`error_handlers`, `error_notifications`, `color_picker_tabs`), core services
(`orm_service`, `name_service`, `field_service`, `rpc`, `registry`) and ~30 asset
bundles (`web.assets_backend`=66, `web.assets_frontend`=67,
`web.report_assets_common`=52). `static/src/start.js` mounts the `WebClient` OWL
root onto `document.body`. **None of this is reverse-engineerable from Python
metadata** — it is the entire reason gap #3 exists.

## 4. Behavior (beyond metadata)

- **`call_kw` (RPC dispatch):** every model method the browser invokes flows
  through one jsonrpc route → `registry[model]` → `odoo.service.model.call_kw`.
  `readonly` is resolved dynamically by walking the model MRO for a `_readonly`
  flag, routing to a read-replica cursor when possible. (code-read)
- **`web_client` bootstrap:** `/web`|`/odoo` runs `ensure_db()`, session +
  `security.check_session` gating, `_on_webclient_bootstrap()`, then renders
  `web.webclient_bootstrap` (Cache-Control: no-store, X-Frame-Options: DENY) —
  the page that loads the OWL asset bundle and becomes the SPA. (code-read)
- **Session handling:** `authenticate()` opens a fresh Registry cursor/Env, calls
  `request.session.authenticate`, persists `session.db`, returns
  `ir.http.session_info()`; `/web/session/account` builds an Odoo OAuth2 URL.
  (code-read)

## 5. IT architecture

- **Application:** the Web Client framework — WSGI app, asset bundler, OWL SPA host.
- **Software services:** the 68 routes above (RPC bridge, bootstrap, session,
  actions, assets, reports, database manager, JSON API).
- **Data objects:** `base.document.layout`, `res.users.settings.embedded.action`.
- **Information flows:** browser OWL → `call_kw` → ORM; bootstrap →
  `webclient_rendering_context` → bundle mount; extends `ir.http`/`ir.ui.view`/
  `ir.ui.menu`/`ir.model`/`ir.qweb.field.*`.

## 6. Business architecture

- **Capabilities (inferred):** Render the Application UI (OWL SPA); Dispatch
  client→server RPC; Manage web session/auth bootstrap; Serve & bundle static
  assets; Provide the field/view/service/registry framework all modules extend;
  Render & export reports; Administer databases.
- **Value streams (inferred):** Request-to-Render; Action-to-View.
- **Information concepts (auto):** document layout, embedded-action settings,
  session_info, asset bundle.
- **Organization/Products (auto):** none (no groups, no `product.*`).
- **Policies (inferred):** session/`check_session`/`is_user_internal` gating;
  no-store + DENY headers on the client page.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `web` is technical / firm infrastructure (Porter
  support activity; Stabell & Fjeldstad "support"). It creates no primary value in
  any single chain/shop/network — it is the UI + HTTP/RPC plumbing **every** module
  renders through, and `auto_install=true` makes it ubiquitous.
- **APQC: 8.0 Manage Information Technology.** `web` is the IT-delivery /
  application-platform capability — it delivers the running UI runtime, asset
  pipeline, and client framework. 13.0 "Develop and Manage Business Capabilities"
  was considered (web is the platform others build on) but rejected: web is a
  concrete running runtime/application platform, not a governance/portfolio
  capability — its work is IT delivery, which is squarely 8.0.

## 8. Fit-to-Standard

- **Standard:** OWL SPA client, universal RPC bridge, registry/widget framework,
  session + OAuth bootstrap, asset bundling, report export, database manager,
  bearer JSON API.
- **Typical fits:** standard backend client with zero per-module UI plumbing;
  adding a field widget/view via registry; patching OWL components.
- **Common gaps:** custom OWL components/services (JS dev, gap #3); white-label
  theming; bespoke caching/offline beyond the PWA worker. External integrations
  are NOT in web (gap #7) — only Odoo OAuth + CDN libs (`accounts.odoo.com`,
  `cdn.jsdelivr.net` speedscope, `odoo.com/buy`).
- **Drive hints:** `POST /web/dataset/call_kw` (res.partner.search_read);
  `env['ir.http'].session_info()` in odoo shell; `GET /web` → view source →
  confirm `web.assets_backend` bundle; `GET /web/manifest.webmanifest`.
