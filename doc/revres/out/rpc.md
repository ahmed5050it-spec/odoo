# rpc — Architecture Brief

> Module: `rpc` · Category: Extra Tools · Depends: `base` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/rpc.facts.json` · Frontend: `doc/revres/frontend/rpc.frontend.json`

## 1. Summary

`rpc` is Odoo's **external programmatic API surface** — the documented endpoints
third-party clients and server-to-server callers use to drive the ORM over HTTP.
It is structurally the **inverse of a data module**: **0 models, 0 fields, 0
security rules, 0 views, 0 frontend assets** — just **6 routes** and **~662 Python
LOC** of controllers. Its substance is the modern **JSON-2** API
(`POST /json/2/<model>/<method>`, bearer-authenticated) plus the **legacy
XML-RPC / JSON-RPC** endpoints kept for back-compat (deprecated in 19, removal
scheduled for 22), and an unauthenticated `/web/version` discovery route. It owns
no business object — it exposes *other* modules' methods.

## 2. Structure (evidence)

- **Models:** none. `rpc` defines no models and no fields; it dispatches to any
  installed model via `request.env[model]`.
- **Routes (6):** the JSON-2 call (`/json/2/<__model__>/<__method__>`, `bearer`),
  the JSON-2 landing/404 (`/json/2`, `/json/2/<path:subpath>`, `public`), legacy
  `/jsonrpc` (`none`) and `/xmlrpc/<service>` + `/xmlrpc/2/<service>` (`none`), and
  version discovery `/web/version` + `/json/version` (`none`).
- **Security:** none (0 access rules, 0 record rules, 0 groups) — the security
  boundary is `get_public_method` + normal ORM access rights, not route ACLs.
- **Views:** none. No UI.

## 3. Frontend (gap #3)

`extract_frontend` reports **present: false** — 0 JS files, 0 XML/QWeb templates,
0 OWL components, 0 registry adds, 0 services, 0 asset bundles. `rpc` ships **no
UI whatsoever**; it is pure HTTP/RPC plumbing consumed by external clients and
never rendered. (static) The only "discovery" surface is the unauthenticated
`GET /web/version` (alias `/json/version`) returning `{version_info, version}`
from `odoo.release`.

## 4. Behavior (beyond metadata)

- **JSON-2 dispatch (`web_json_2_rpc`):** path components map directly onto an ORM
  call — `request.env[__model__].with_context(context)` →
  `get_public_method(Model, __method__)` (rejects `_`-prefixed, `@api.private`,
  classmethods/staticmethods) → `Model.browse(ids)` → `signature.bind` validation
  (422 on mismatch) → `func(records, **kwargs)`; a recordset result is coerced to
  `.ids`. No model/method allow-list — any public method on any model is
  reachable. (code-read)
- **Bearer auth (`ir.http._auth_method_bearer`):** parses `Authorization: Bearer
  <token>` → `res.users.apikeys._check_credentials(scope='rpc')` → `update_env(
  user=uid)`; invalid key = 401 with a `WWWAuthenticate('bearer')` challenge.
  Stateless (`save_session=False`, `can_save=False`). Token-less fallback to a
  session requires interactive `Sec-Fetch-*` headers (CSRF guard). (code-read)
- **JSON-2 envelope (`Json2Dispatcher`):** body must be `application/json`, merged
  with path args; success returns a **bare JSON value** via `make_json_response`
  (not a `{jsonrpc,id,result}` frame); `handle_error` serializes exceptions with
  the right HTTP status (UserError→`http_status`, HTTPException→`.code`, else 500).
  (code-read)
- **Legacy RPC:** `/jsonrpc`, `/xmlrpc[/2]/<service>` route through
  `dispatch_rpc(service, method, params)` over common/db/object services; a custom
  `OdooMarshaller` serializes Odoo types (bytes→base64, datetime→ISO, frozendict,
  Command, Markup); all three log `RPC_DEPRECATION_NOTICE`. (code-read)

## 5. IT architecture

- **Application:** the external API surface — JSON-2 REST-style API, legacy
  XML-RPC / JSON-RPC, version discovery.
- **Software services:** the 6 routes above (JSON-2 call + landing, `/jsonrpc`,
  `/xmlrpc[/2]`, `/web/version`).
- **Data objects:** none (owns no models).
- **Information flows:** client → `POST /json/2/<model>/<method>` (Bearer) →
  `_auth_method_bearer` → `get_public_method` → `browse(ids).<method>(**kwargs)` →
  JSON; legacy → `dispatch_rpc` → common/db/object; depends on `res.users.apikeys`
  (base) to resolve a token to a uid.

## 6. Business architecture

- **Capabilities (inferred):** Expose ORM methods as an external API (JSON-2);
  authenticate clients via bearer API keys; provide back-compat XML-RPC/JSON-RPC;
  enforce the public-method / access-right boundary; serialize ORM types to JSON
  and XML-RPC; advertise server version.
- **Value streams (inferred):** Integration request-to-result — client
  authenticates with an API key, invokes a method, receives a JSON result.
- **Information concepts (auto):** RPC request/response envelope; API-key
  credential (`res.users.apikeys`, scope `rpc`); server `version_info`.
- **Organization / Products (auto):** none (no groups, no `product.*`).
- **Policies (inferred):** `get_public_method` gate; bearer-required, stateless
  `/json/2`; `Sec-Fetch-*` CSRF check on session fallback; legacy endpoints
  deprecated for 22.0 removal.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `rpc` is firm IT infrastructure (Porter support
  activity; Stabell & Fjeldstad "support"). It owns no business object and creates
  no primary value in any chain/shop/network — its value is *enabling integration*
  with whatever business modules are installed. `auto_install=true` makes it
  ubiquitous plumbing.
- **APQC: 8.0 Manage Information Technology.** `rpc` is the IT-delivery capability
  for external application interfaces — operating the API gateway, managing
  credentials, maintaining protocol compatibility. 13.0 "Develop and Manage
  Business Capabilities" was considered (an API is an enabling capability others
  build on) but rejected: `rpc` is a concrete running interface/runtime, not a
  governance/portfolio capability — its work is IT service delivery, squarely 8.0
  (mirroring `web`).

## 8. Fit-to-Standard

- **Standard:** JSON-2 REST-style API to any public ORM method; bearer API-key
  auth (`res.users.apikeys`, scope `rpc`); automatic JSON/XML-RPC type
  serialization; back-compat XML-RPC/JSON-RPC; dynamic read-replica routing for
  `_readonly` methods; structured JSON error envelopes; version discovery.
- **Typical fits:** external system reads/writes records via `search_read` /
  `create` / `write` over `/json/2`; legacy client on `/xmlrpc/2` until migration;
  server-to-server automation invoking business methods remotely.
- **Common gaps:** no schema/OpenAPI discovery (clients must know model/method
  names out of band); no per-route allow-list or rate limiting; API keys are
  global-scope (`rpc` → NULL scope); no outbound webhook/push (inbound/pull only);
  22.0 removal of legacy RPC forces migration. External integrations: only the
  `xmlrpc` stdlib SDK; 0 outbound HTTP call sites; `uses_api_keys: true` (gap #7).
- **Drive hints:** `POST /json/2/res.partner/search_read` with `Authorization:
  Bearer <key>`; `GET /web/version` → `{version_info, version}`; `POST /json/2/`
  → 404 hint; `POST /json/2/res.partner/_invalid` → AccessError; `odoo shell:
  env['res.users.apikeys']._generate('rpc', 'demo key', None)` to mint a key.
