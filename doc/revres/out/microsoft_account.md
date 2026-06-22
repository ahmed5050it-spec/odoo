# microsoft_account — Reverse-Engineering Brief

> Metamodel: `doc/revres/metamodel/microsoft_account.metamodel.json`
> Facts: `doc/revres/facts/microsoft_account.facts.json`
> Frontend/integration: `doc/revres/frontend/microsoft_account.frontend.json`
> Odoo 19.0 · value_model **support** · APQC **8.0 Manage Information Technology**

microsoft_account ("Microsoft Users") is the shared Microsoft OAuth2 base — the
token/credential plumbing that `microsoft_calendar` and `microsoft_outlook` build
on. It owns no business object: a single `AbstractModel` (`microsoft.service`)
with **zero persisted fields**, one public route, no security groups, no views,
no JS. Its only persisted state is three OAuth token fields it grafts onto
`res.users`. It is the Microsoft-side sibling of `google_account`.

## Role & Dependencies

- **Depends on:** `base_setup` (the Settings UI that hosts per-service client
  id/secret configuration).
- **Consumed by:** `microsoft_calendar`, `microsoft_outlook` — each supplies a
  per-service `service` string plus its own `microsoft_<service>_client_id` /
  `microsoft_<service>_client_secret` ICP credentials and scopes.
- **Role:** generic, service-agnostic OAuth2 **token broker** + outbound
  Microsoft Graph request wrapper. Unlike `google_account`, it *does* keep the
  base per-user token store on `res.users` (set via `_set_microsoft_auth_tokens`).

## Data Model (the ERM)

- `microsoft.service` — `AbstractModel`, no stored fields; a parameterized
  OAuth2 + REST client (8 methods).
- `res.users` (extension) — `microsoft_calendar_rtoken` / `microsoft_calendar_token`
  (both `groups=base.group_system`) + `microsoft_calendar_token_validity`; the
  base token store written by `_set_microsoft_auth_tokens`.
- Credentials live as `ir.config_parameter`: `microsoft_<service>_client_id`
  (public, leakable in clear in the authorize URI) and
  `microsoft_<service>_client_secret` (secret, read only inside a request).
- Auth/token endpoints overridable via `microsoft_account.auth_endpoint` /
  `microsoft_account.token_endpoint` ICPs (sovereign clouds).

## Behaviour Beyond Metadata (code-reads)

- **OAuth2 flow (`microsoft.service`):** `_get_authorize_uri` builds the consent
  URL against `login.microsoftonline.com/common/oauth2/v2.0/authorize`
  (`response_type=code`, `access_type=offline` → Microsoft returns a
  refresh_token) with a JSON `state` carrying `{d:dbname, s:service, f:from_url,
  u:db.uuid}`. `_get_microsoft_tokens` POSTs `grant_type=authorization_code`
  (default scope `offline_access openid Calendars.ReadWrite`) to the v2.0 token
  endpoint → `(access_token, refresh_token, ttl)`; on `HTTPError` it raises
  `res.config.settings.get_config_warning`. `_refresh_microsoft_token` POSTs
  `grant_type=refresh_token` → `(access_token, expires_in)`. None of this is
  visible in metadata.
- **`_do_request` (the choke-point):** every token call and downstream Graph
  call funnels through here. It **hard-asserts** the target host is
  `login.microsoftonline.com` or `graph.microsoft.com` (static SSRF/host
  allow-list), returns `(status, json, ask_time)` with `ask_time` parsed from the
  response `Date` header (clock-skew-tolerant expiry), maps 204/404 → empty body
  and swallows them, re-raises other HTTPErrors. 20s timeout.
- **`/microsoft_account/authentication` controller:** the public OAuth2
  `redirect_uri`. JSON-decodes the round-tripped `state` (`BadRequest` if no
  service / a code without a return url), reconstructs `redirect_uri` from
  `url_root`, exchanges the `code` via `_get_microsoft_tokens`, then hands
  `(access_token, refresh_token, ttl)` to `request.env.user._set_microsoft_auth_tokens`
  and redirects to `url_return`; on error appends `?error=<reason>`.
- **Downstream consumption (`_set_microsoft_auth_tokens` convention):**
  `res.users._set_microsoft_auth_tokens` writes the three token fields, computing
  validity as `now + timedelta(seconds=ttl)`. It is the callback the controller
  invokes and the seam downstream modules extend: `microsoft_calendar` reuses
  these fields + the callback for calendar OAuth/refresh; `microsoft_outlook`
  reuses `microsoft.service` + the `microsoft_<service>_client_*` ICP convention
  for SMTP/IMAP OAuth on mail servers. The per-service `service` string lets one
  generic helper serve every integration with distinct credentials and scopes.
- **External integration (gap #7, static):** outbound HTTPS via `requests` to
  `login.microsoftonline.com` (OAuth2) and `graph.microsoft.com` (Graph REST),
  admin-supplied per-service client id/secret (Azure app registration), no
  vendored SDK. A seed ICP `microsoft_redirect_uri = urn:ietf:wg:oauth:2.0:oob`
  ships in data. This SaaS dependency is the module's defining trait and is
  invisible to model/field metadata.

## IT Architecture

- **Application:** shared Microsoft OAuth2 / identity base component.
- **Software services:** `/microsoft_account/authentication` (http, public) —
  OAuth2 redirect callback that exchanges the auth code and stores tokens on
  `res.users` via `_set_microsoft_auth_tokens`.
- **Data objects:** `microsoft.service` (AbstractModel) + `res.users` (token
  store extension).
- **Information flows:** outbound Odoo → `login.microsoftonline.com/.../v2.0/token`
  (exchange + refresh) and → `graph.microsoft.com` (all downstream Graph calls,
  host allow-listed); inbound Microsoft → callback → `_get_microsoft_tokens` →
  `_set_microsoft_auth_tokens`.

## Business Architecture

- **Capabilities (inferred):** provide the Microsoft OAuth2 authorization-code
  flow; broker the shared OAuth2 redirect callback; store + refresh per-user
  tokens on `res.users`; manage per-service API credentials; mediate
  host-allow-listed outbound Microsoft API requests.
- **Value stream (inferred):** *Connect-Microsoft-Account* — admin configures
  client id/secret → user grants consent on the Microsoft identity platform →
  Microsoft calls back → `microsoft.service` exchanges the code → tokens stored
  on `res.users` for the consuming module to use and refresh.
- **Information concepts (auto):** `microsoft.service` (no business data),
  `res.users` (OAuth token store).
- **Organization / products:** none (no groups, no `product.*`).
- **Policies (inferred):** token fields guarded by `base.group_system`; secret
  never returned in clear (read only inside a request); `_do_request` host
  allow-list; `access_type=offline` for a refresh_token; the public callback acts
  only on a valid `state` + auth code; overridable endpoints for sovereign clouds.
- **Stakeholders:** admin (configures the Azure app registration), internal user
  (grants consent; tokens on their `res.users`), Microsoft identity/Graph (token
  authority), downstream Microsoft modules.
- **Strategy:** `null` (human).

## Classification

- **value_model:** `support` — shared OAuth/identity infrastructure for Microsoft
  integrations; no business object of its own; sibling of `google_account`.
- **activity_class:** `support` (firm-infrastructure, Stabell & Fjeldstad).
- **apqc_category:** **8.0 Manage Information Technology** — external-system
  integration + OAuth2 credential/token lifecycle. Mirrors `google_account` and
  the 8.0 classification of the downstream connectors. A deliberate departure
  from the inherited/baseline **13.0** (Develop & Manage Business Capabilities),
  rejected because nothing here develops a business capability — it operates an
  external auth interface and brokers tokens; **9.0** (Manage Assets) rejected —
  no asset is managed, only API credentials and a token exchange.

## Fit-to-Standard & Open Questions

- **Standard:** reusable Microsoft OAuth2 authorization-code flow; offline consent
  → refresh_token; code→token exchange + refresh; one public callback that
  exchanges and stores tokens; base `res.users` token store + `_set_microsoft_auth_tokens`
  seam; per-service client id/secret via ICP; overridable sovereign-cloud
  endpoints; host-allow-listed outbound HTTP wrapper.
- **Typical fits:** downstream Microsoft modules reuse one OAuth2 base;
  self-registered Azure app registration; one shared `res.users` token store
  consumed and refreshed by the consumer.
- **Common gaps:** token fields are calendar-named (effectively single-credential,
  not cleanly per-service); no built-in UI; no automatic refresh scheduling; no
  token-revocation call; single per-service credentials (no multi-tenant
  isolation); `_get_calendar_scope` hard-defaults the exchange scope to
  `Calendars.ReadWrite`, biasing the generic base toward calendar.
- **Open questions:** exact set of downstream `service` strings and which still
  route through this callback; whether `microsoft_outlook` reuses the
  calendar-named token fields or keeps its own store on mail servers;
  cross-service clock-skew handling vs. the `now + expires_in` validity math.
