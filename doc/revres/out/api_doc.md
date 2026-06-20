# api_doc — Reverse-Engineering Brief

`api_doc` ("API Documentation", category *Hidden*, `auto_install=true`, not an
application) is a developer-enablement subsystem that serves an **auto-generated
external API reference** at `/doc`. It owns no business data — `model_count=0`
(only an `ir.attachment` extension) — and instead **reflects the live registry**
(`ir.model`, fields, public methods) into a browsable, live-runnable schema. It
sits one hop above `web` in the dependency graph and is the documentation
counterpart to the `rpc` module's `/json/2` execution surface: both gate on the
same `get_public_method`, so the page documents exactly what RPC can run.

## Role & Dependencies

- **web** (only dependency): provides the OWL framework, asset bundling, the
  `json2` request/response envelope, HTTP routing and `res.users.apikeys`
  (transitively from base) used for the bearer endpoints and the playground.

Capability added: a standalone OWL single-page app that turns Python model
metadata + docstrings into an interactive, access-scoped API reference with an
in-browser playground that POSTs live calls to `/json/2`.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|--------------|---------|---------------|
| `ir.attachment` (extension, `_inherit` only) | adds `@api.autovacuum _gc_doc_index` to purge stale cached index attachments | 0 | none |

The module is a **pure mixin/extension** — no own model, no fields, so the
field-type distribution is empty. The "data" it serves is computed at request
time by reflecting the whole registry, then cached as an `ir.attachment` row
(`odoo-doc-index-<seq>-<hmac>.json`).

## Behavior & Surfaces

- **Routes (5):** `/doc`, `/doc/<model_name>`, `/doc/index.html` (http, `auth=user`,
  renders the OWL SPA); `/doc/index.json` and `/doc/<model_name>.json`
  (`json2`, `auth=user`, the reflection endpoints); `/doc-bearer/index.json`
  and `/doc-bearer/<model_name>.json` (`json2`, `auth=bearer`) — API-key twins
  that re-call the same builders for the playground / external clients.
- **Views (0):** no backend views. The entire UI is a **standalone OWL app**
  (17 JS / 8 XML, 10 components: `DocClient`, `DocSidebar`, `DocModel`,
  `DocMethod`, `DocTable`, `DocRequest`, `ApiKeyModal`, `SearchModal`,
  `DocLoadingIndicator`, `DocErrorDialog`) mounted on `document.body` by
  `start_doc_client.js` (a dedicated `api_doc.assets` bundle, not the WebClient).
- **Security:** 0 access rules, 0 record rules, **1 group**
  `api_doc.group_allow_doc` (implied by `base.group_system`) — by default only
  the system/admin user can view the reference; user routes `raise AccessError`
  otherwise. Field/method visibility is further scoped to the viewer's own
  `has_access('read')` / `_has_field_access('read')`.

## Value-Configuration Classification

- **Value model: support.** This is firm IT/developer infrastructure (Porter
  support activity; Stabell & Fjeldstad *support*), not a primary value-creating
  activity of any chain/shop/network. It has no business object — just routes
  and a reflection SPA producing documentation *about* the system.
- **Activity class: support.** Cross-cutting developer tooling consumed by
  integrators, with no document flow of its own.

## APQC PCF Hint

**13.0 Develop and Manage Business Capabilities** (developer enablement: it
generates and publishes the technical reference + self-service playground that
let developers build *on* the platform). **8.0 Manage Information Technology**
was the runner-up — it is IT plumbing like its siblings `rpc`/`web` — but unlike
`rpc` (a running gateway = IT service delivery), `api_doc` is the *knowledge
surface about* the interface, so 13.0 is the primary fit. (inferred)

## How to Drive It

Use the **run-odoo** skill. As an admin (holds `group_allow_doc`):

- `GET /doc` → confirm the OWL `DocClient` SPA renders the module/model sidebar.
- `curl $URL/doc/index.json -H 'Cookie: session_id=...'` → `{modules, models[...]}`.
- `curl $URL/doc/res.partner.json -H 'Cookie: session_id=...'` → `fields_get` +
  parsed method signatures/docstrings.
- `odoo shell`: `env['res.users.apikeys']._generate('rpc', 'doc', None)` to mint
  a key, then `curl $URL/doc-bearer/res.partner.json -H 'Authorization: Bearer <key>'`.
- `odoo shell`: `env['ir.attachment']._gc_doc_index()` to purge stale cached indexes.

## Open Questions

- Exact `/json/2` wire shape the playground emits per method (ids-vs-kwargs split
  is owned by the `rpc` module, not `api_doc`).
- Whether the `'doc': None` model-level docstring (marked TODO) will be populated.
- Real-world practice for granting `group_allow_doc` to developers beyond admins.
- Effect of re-enabling the commented-out `sort_key_field`/`sort_key_method`
  ordering helpers.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts
(`doc/revres/facts/api_doc.facts.json`), code-read of `controllers/api_doc.py`,
`models/ir_attachment.py`, `security/res_groups.xml`, and the
`static/src` OWL client. Odoo 19.0.*
