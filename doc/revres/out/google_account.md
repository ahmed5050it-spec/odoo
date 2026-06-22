# google_account — Reverse-Engineering Brief

> Metamodel: `doc/revres/metamodel/google_account.metamodel.json`
> Facts: `doc/revres/facts/google_account.facts.json`
> Frontend/integration: `doc/revres/frontend/google_account.frontend.json`
> Odoo 19.0 · value_model **support** · APQC **8.0 Manage Information Technology**

google_account ("Google Users") is the shared Google OAuth2 base — the
token/credential plumbing that `google_calendar`, `google_gmail` and
`google_drive` (`cloud_storage_google`) build on. It owns no business object:
a single `AbstractModel` (`google.service`) with **zero persisted fields**, one
public route, no security groups, no views, no JS. It is the Google-side sibling
of `microsoft_account`.

## Role & Dependencies

- **Depends on:** `base_setup` (the Settings UI that hosts per-service client
  id/secret configuration).
- **Consumed by:** `google_calendar`, `google_gmail`, `google_drive`
  (`cloud_storage_google`) — each supplies a per-service `service` string
  (`'calendar'`, `'gmail'`, `'drive'`) plus its own `google_<service>_client_id`
  / `google_<service>_client_secret` ICP credentials and scopes.
- **Role:** generic, service-agnostic OAuth2 **token broker** + outbound Google
  API request wrapper. It does not persist tokens — storage and refresh live in
  the consuming module's `res.users.settings` extension.

## Data Model (the ERM)

- `google.service` — `AbstractModel`, no stored fields; a parameterized OAuth2 +
  REST client (5 methods).
- Credentials live as `ir.config_parameter`: `google_<service>_client_id`
  (public, even logged in clear) and `google_<service>_client_secret` (secret,
  read only inside a request, redacted from logs).
- Tokens are **not** stored here — downstream modules persist e.g.
  `google_calendar_rtoken` / `token` / `token_validity` on `res.users.settings`
  via `_set_google_auth_tokens`.

## Behaviour Beyond Metadata (code-reads)

- **OAuth2 flow (`google.service`):** `_get_authorize_uri` builds the consent URL
  against `accounts.google.com/o/oauth2/auth` (`response_type=code`,
  `access_type=offline` → Google returns a refresh_token). `_get_google_tokens`
  POSTs `grant_type=authorization_code` to
  `accounts.google.com/o/oauth2/token` → `(access_token, refresh_token,
  expires_in)`. `_refresh_google_token` POSTs `grant_type=refresh_token` to the
  same endpoint → `(access_token, expires_in)`. None of this is visible in
  metadata — the module exposes no fields.
- **`_do_request` (the choke-point):** every downstream Google call funnels
  through here. It **hard-asserts** the target host is `accounts.google.com` or
  `www.googleapis.com` (static SSRF/host allow-list), scrubs `client_secret`
  from debug logs (4 chars + 12 mask), returns `(status, json, ask_time)` with
  `ask_time` parsed from the Google `Date` header (clock-skew-tolerant expiry),
  maps HTTP 204 → `False`, swallows 204/404, re-raises other HTTPErrors. 20s
  timeout.
- **`/google_account/authentication` controller:** the public OAuth2
  `redirect_uri`. Decodes the round-tripped `state` (`{'s': service, 'f':
  url_return}`), validates it (`BadRequest` otherwise), exchanges the `code` via
  `_get_google_tokens`, then dispatches `(access_token, refresh_token, ttl)` to
  the current user's `res_users_settings_id._set_google_auth_tokens(...)` and
  redirects to `url_return`; on error appends `?error=<reason>`.
- **Downstream consumption:** `google_calendar/res_users_settings.py` defines
  `_set_google_auth_tokens` and calls `_refresh_google_token('calendar', ...)`,
  wiping tokens on failure. `google_gmail` reuses the same ICP convention and
  callback but hand-builds its own `oauth2/v2/auth` consent URL rather than
  calling `_get_authorize_uri`.
- **External integration (gap #7, static):** outbound HTTPS via `requests` to
  `accounts.google.com` (OAuth2) and `www.googleapis.com` (REST), admin-supplied
  per-service client id/secret, no vendored SDK. This SaaS dependency is the
  module's defining trait and is invisible to model/field metadata.

## IT Architecture

- **Application:** shared Google OAuth2 / identity base component.
- **Software services:** `/google_account/authentication` (http, public) —
  OAuth2 redirect callback that exchanges the auth code and hands tokens to the
  downstream `res.users.settings`.
- **Data objects:** `google.service` (AbstractModel only).
- **Information flows:** outbound Odoo → `accounts.google.com/o/oauth2/token`
  (exchange + refresh) and → `www.googleapis.com` (all downstream REST, host
  allow-listed); inbound Google → callback → `_get_google_tokens` → downstream
  `_set_google_auth_tokens`.

## Business Architecture

- **Capabilities (inferred):** provide Google OAuth2 authorization-code flow;
  broker the shared OAuth2 redirect callback; manage per-service Google API
  credentials; mediate (host-allow-listed, secret-scrubbed) outbound Google API
  requests.
- **Value stream (inferred):** *Connect-Google-Account* — admin configures
  client id/secret → user grants consent → Google calls back → `google.service`
  exchanges the code → tokens handed to the downstream module for storage +
  refresh.
- **Information concepts (auto):** `google.service` (no business data).
- **Organization / products:** none (no groups, no `product.*`).
- **Policies (inferred):** secret never returned in clear / redacted in logs;
  `_do_request` host allow-list; `access_type=offline` for a refresh_token; the
  public callback acts only on a valid `state` + auth code.
- **Stakeholders:** admin (configures the Google Cloud project), internal user
  (grants consent), Google identity/APIs (token authority), downstream Google
  modules.
- **Strategy:** `null` (human).

## Classification

- **value_model:** `support` — shared OAuth/identity infrastructure for Google
  integrations; no business object of its own; sibling of `microsoft_account`.
- **activity_class:** `support` (firm-infrastructure, Stabell & Fjeldstad).
- **apqc_category:** **8.0 Manage Information Technology** — external-system
  integration + OAuth2 credential lifecycle. Mirrors `microsoft_account` and the
  8.0 classification of the downstream connectors. **13.0** (Develop & Manage
  Business Capabilities) rejected — nothing here develops a business capability,
  it operates an external auth interface; **9.0** (Manage Assets) rejected — no
  asset is managed, only API credentials and a token exchange.

## Fit-to-Standard & Open Questions

- **Standard:** reusable Google OAuth2 authorization-code flow; offline consent →
  refresh_token; code→token exchange + refresh; one public callback dispatching
  to the right downstream store; per-service client id/secret via ICP;
  host-allow-listed, secret-redacting outbound HTTP wrapper.
- **Typical fits:** downstream Google modules reuse one OAuth2 base; self-
  registered Google Cloud project; tokens persisted/refreshed by the consumer.
- **Common gaps:** no token storage of its own (consumer must implement
  `_set_google_auth_tokens` + token fields); no built-in UI; no automatic
  refresh scheduling; `google_gmail` bypasses `_get_authorize_uri`; single
  per-service credentials (no multi-tenant isolation); no token-revocation call.
- **Open questions:** exact set of downstream `service` strings and which still
  route through this callback; whether `google_gmail`'s bespoke consent URL is
  intentional divergence; cross-service clock-skew handling vs. per-consumer
  token-validity math.
