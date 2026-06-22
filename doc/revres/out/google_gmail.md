# google_gmail (Google Gmail) — Architecture Brief

> Module `google_gmail`, display name **"Google Gmail"** (`odoo/addons/google_gmail/`).
> A thin authentication connector that lets Odoo's mail servers talk to Gmail over **OAuth2 +
> XOAUTH2** instead of a stored password — for both **outgoing SMTP** (`ir.mail_server`) and
> **incoming IMAP** (`fetchmail.server`). `depends = [mail]`. It owns no business object: one
> OAuth credential mixin (`google.gmail.mixin`) plus token/selection fields grafted onto
> `ir.mail_server`, `fetchmail.server`, `res.config.settings` and `res.users`. 2 routes,
> ~712 Python LOC, no JS, no views of its own. `application = false`, `auto_install = true`
> (it activates when `mail` is present so Gmail OAuth is offered out of the box). This is mail
> *plumbing* on top of the `mail` capability — the sibling of `microsoft_outlook` — not a
> capability of its own.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). Mail-infrastructure integration extending
  `mail`; it transforms nothing and produces no sellable output. Its job is to bridge Odoo's
  existing SMTP/IMAP servers to an external SaaS (Google Identity + Gmail) — a firm-infrastructure
  / support function.
- **activity_class: support.**
- **apqc_category: 8.0 Manage Information Technology.** The module's reason to exist is
  external-system integration (gap #7 — `accounts.google.com`, `oauth2.googleapis.com`,
  `googleapis.com/oauth2/v2/userinfo`, `gmail.api.odoo.com`) and OAuth credential/secret lifecycle
  management: identity & integration concerns, not business-capability development.
- **Why this departs from the baseline.** The auto-architect baseline tagged this thin module
  **13.0 Develop and Manage Business Capabilities** by default. But nothing here *develops* a
  capability — outbound/inbound email is the **`mail`** module's capability; this connector only
  swaps password auth for an OAuth Bearer token. That is exactly **8.0**. 13.0 was rejected (no new
  capability is built). **9.0 Acquire/Construct/Manage Assets** (and its **9.4** asset-maintenance
  band) was rejected: no physical or IT asset is constructed or maintained — only a renewing token
  credential and an API binding, which is identity/integration plumbing, not asset upkeep. This
  matches the `microsoft_calendar` sibling already classified 8.0.

## 2. IT Architecture

- **Application:** google_gmail — Gmail OAuth2 authentication connector for Odoo's outgoing SMTP
  and incoming IMAP mail servers.
- **Software services (routes):** 2, both `http`/`auth=user`. `/google_gmail/confirm` is the OAuth2
  redirect callback (exchanges the authorization code for tokens, verifies CSRF + the granted email,
  stores tokens on the mail-server record); `/google_gmail/iap_confirm` is the Enterprise IAP
  callback that receives tokens proxied by `gmail.api.odoo.com` so the DB never holds Google secrets.
- **Data objects:** `google.gmail.mixin` (AbstractModel), `ir.mail_server` / `fetchmail.server`
  (extended with the mixin + a Gmail selection value), `res.config.settings`, `res.users`.
- **Information flows:** outbound Odoo→`oauth2.googleapis.com/token` (authorization_code + refresh_token
  grants)→tokens on the server record; →`googleapis.com/oauth2/v2/userinfo` (email-ownership check);
  Enterprise fallback →`gmail.api.odoo.com`; mail transport via `AUTH/AUTHENTICATE XOAUTH2` to
  `smtp.gmail.com:587` (STARTTLS) and `imap.gmail.com:993` (SSL) with a Bearer token instead of a
  password; inbound browser redirect from `accounts.google.com`→`/google_gmail/confirm`.

## 3. Data Model (the ERM)

| _name | role | #fields | key relations |
|-------|------|---------|---------------|
| `google.gmail.mixin` | AbstractModel **mixin** (OAuth credentials) | 5 | — (`google_gmail_refresh_token`, `google_gmail_access_token`, `google_gmail_access_token_expiration`, computed `google_gmail_uri`, `active`) |
| `ir.mail_server` | extension, inherits the mixin (outgoing SMTP) | +1 | `smtp_authentication`+= `'gmail'` |
| `fetchmail.server` | extension, inherits the mixin (incoming IMAP) | +1 | `server_type`+= `'gmail'` |
| `res.config.settings` | extension (OAuth app credentials) | +2 | `google_gmail_client_id` / `google_gmail_client_secret` (ir.config_parameter) |
| `res.users` | extension (personal Gmail SMTP setup) | +1 | `outgoing_mail_server_type`+= `'gmail'` |

- The central abstraction is the **`google.gmail.mixin`**: it grafts the three OAuth tokens
  (refresh / access / access-expiration) plus the computed consent `google_gmail_uri` onto *both*
  the SMTP and IMAP server models, so one credential-and-refresh machinery serves both protocols.
  The tokens are stored **on the mail-server record itself** (`groups='base.group_system'`,
  `copy=False`) — there is no separate token table, and (unlike the calendar siblings) nothing lives
  on `res.users` except the personal `outgoing_mail_server_type` selection.
- Field distribution is attribute-heavy and tiny (a few Char/Integer/Boolean/Selection tokens and
  flags); the module's weight is in *behavior* (~712 LOC of OAuth + XOAUTH2 wiring), not in schema.

## 4. Behavior & Surfaces

- **OAuth2 token lifecycle (code-read).** `_compute_gmail_uri` builds the consent URL
  `accounts.google.com/o/oauth2/v2/auth` with `access_type=offline` + `prompt=consent` (both needed
  for a refresh_token) for scope `https://mail.google.com/ …/userinfo.email`, carrying a JSON
  `state` of `{model,id,csrf_token}`. The callback calls `_fetch_gmail_refresh_token(code)`, which
  POSTs `grant_type=authorization_code` to `oauth2.googleapis.com/token` and returns
  refresh+access tokens + an absolute expiration (`int(time.time())+expires_in`); a non-ok response
  raises a `UserError`. Tokens are written onto the server record under `base.group_system`.
- **XOAUTH2 bridge (code-read).** `_generate_oauth2_string(user, refresh_token)` is the single point
  joining OAuth to the mail protocols: if the cached access token is missing or within
  `GMAIL_TOKEN_VALIDITY_THRESHOLD` (10s) of expiry it calls `_fetch_gmail_access_token`
  (`grant_type=refresh_token`) and writes the fresh token back; then it returns the literal SASL
  string `user=<u>\x01auth=Bearer <tok>\x01\x01` — the Gmail XOAUTH2 protocol string. Refresh is
  **just-in-time at connect**, not a background cron.
- **SMTP override (code-read).** `ir.mail_server._smtp_login__`: for a Gmail server it
  base64-encodes the OAuth2 string and sends `EHLO` then `docmd('AUTH', 'XOAUTH2 <b64>')` instead of
  a login/password. Onchange pins `smtp.gmail.com` / STARTTLS / 587 and `from_filter=smtp_user`; a
  constraint forbids `smtp_pass`, forces STARTTLS, requires `smtp_user`. Leaving `'gmail'` clears the
  tokens.
- **IMAP override (code-read).** `fetchmail.server._imap_login__`: for a Gmail server it calls
  `connection.authenticate('XOAUTH2', lambda x: auth_string)` then `select('INBOX')` (imaplib
  base64-encodes the SASL response itself — hence no manual b64 here, unlike SMTP). Onchange pins
  `imap.gmail.com` / SSL / 993; a constraint requires `is_ssl`; `_get_connection_type` forces `imap`.
- **Credentials + IAP fallback + callback hardening (code-read).** Admin sets
  `google_gmail_client_id`/`secret`; when unset, `open_google_gmail_uri` (Enterprise-only) proxies
  consent and refresh through `gmail.api.odoo.com` so the DB never holds Google secrets. The
  controller enforces: the `state` model must inherit `google.gmail.mixin`; a per-record HMAC CSRF
  token (`tools.misc.hmac`, scope `google_gmail_oauth`) verified with `consteq`; and, for a shared
  `ir.mail_server`, the granted **verified email** (from `googleapis.com/oauth2/v2/userinfo`) must
  equal the server's email. `open_google_gmail_uri` is admin-only.
- **External integration (gap #7, static).** Hand-rolled `requests` client to Google's OAuth/userinfo
  endpoints + the Odoo IAP proxy, with the actual mail transport (token-as-Bearer over XOAUTH2) to
  `smtp.gmail.com` / `imap.gmail.com`. No vendored SDK.
- **Frontend:** none — 0 JS files, 0 OWL components, no `web.assets_*` additions; the only template is
  a server-rendered OAuth error page (`google_gmail.google_gmail_oauth_error`). The connect UX lives
  in the inherited mail-server / Settings form views, not in this module's own JS.
- **Security posture:** 0 access rules, 0 record rules, 0 new groups; protection comes from the
  `base.group_system` field groups, the admin-only consent action, and the CSRF/HMAC + email-match
  guards on the callback.

## 5. Value-Configuration Classification

Support. `depends = [mail]`, no document chain, no sellable output. It mediates between Odoo's mail
servers and Google's identity + Gmail infrastructure — but as **infrastructure for one capability**
(sending/receiving mail), not as a multi-party marketplace, so it is "support", not "network".
Primary-vs-support role: **support** (it enables the `mail` capability to authenticate to Gmail).

## 6. APQC PCF Hint

**8.0 Manage Information Technology** — manage IT identity/security and external-system integration
(OAuth2 credential lifecycle + Gmail SMTP/IMAP XOAUTH2). Deliberately distinct from the inherited
baseline 13.0 (which would imply a business capability is being built here — it is not; `mail` owns
the email capability) and identical in spirit to the `microsoft_calendar` / `microsoft_outlook`
siblings.

## 7. How to Drive It

Use the **run-odoo** skill (`odoo shell`):

```python
env['ir.mail_server'].search([('smtp_authentication','=','gmail')])     # Gmail-authenticated outgoing servers
env['fetchmail.server'].search([('server_type','=','gmail')])           # Gmail-authenticated incoming servers
env['ir.config_parameter'].sudo().get_param('google_gmail_client_id')   # is the OAuth app configured?
srv = env['ir.mail_server'].search([('smtp_authentication','=','gmail')], limit=1)
srv._generate_oauth2_string(srv.smtp_user, srv.google_gmail_refresh_token)   # build the XOAUTH2 SASL string (refreshes token)
```

Route: `curl` http `/google_gmail/confirm?state=…&code=…` (auth=user) → the OAuth callback
(CSRF/HMAC-guarded; exchanges the code for tokens). External endpoint exercised:
`https://oauth2.googleapis.com/token`.

## 8. Open Questions

- When both `google_gmail_client_id`/`secret` are set **and** the DB is Enterprise, confirm the
  self-hosted credentials always win — `_fetch_gmail_access_token` only takes the IAP path when the
  client id/secret are missing.
- How concurrent SMTP/IMAP sends racing to refresh the *same* expiring access token reconcile (each
  connect writes `google_gmail_access_token` on the record; last-writer-wins, no explicit lock seen).
- Whether a revoked/invalid refresh token surfaces a clear admin-facing re-consent path or only a
  generic `UserError` ("An error occurred when fetching the access token.") at send time.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts (`facts/google_gmail.facts.json`,
`frontend/google_gmail.frontend.json`); behavioral notes from code-read of
`models/google_gmail_mixin.py`, `models/ir_mail_server.py`, `models/fetchmail_server.py`,
`models/res_config_settings.py`, `models/res_users.py`, `controllers/main.py`. Odoo 19.0.*
