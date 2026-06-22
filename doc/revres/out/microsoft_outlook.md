# microsoft_outlook (Microsoft Outlook) — Architecture Brief

> Module `microsoft_outlook`, display name **"Microsoft Outlook"** (`odoo/addons/microsoft_outlook/`).
> Mail-infrastructure plumbing that lets Odoo's outgoing **SMTP** (`ir.mail_server`) and incoming
> **IMAP** (`fetchmail.server`) authenticate to Outlook / Microsoft 365 with **OAuth2 + XOAUTH2**
> instead of a password. `depends = [mail]`, `auto_install = true`. It owns no business object: one
> AbstractModel **mixin** (`microsoft.outlook.mixin`) holding OAuth token state, two `'outlook'`
> Selection options + protocol-login overrides grafted onto the inherited mail servers, and two
> credential `ir.config_parameter`s on `res.config.settings`. 3 models of substance, 2 routes,
> ~708 Python LOC, no frontend. `application = false`. This is integration plumbing on top of the
> `mail` transport — the sibling of `google_gmail` (Gmail XOAUTH2) and `microsoft_calendar`.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). Mail-infrastructure integration extending `mail`;
  it transforms nothing and produces no sellable output. Its job is to bridge an existing capability
  (sending/receiving email) to an external SaaS — a firm-infrastructure / support function.
- **activity_class: support.**
- **apqc_category: 8.0 Manage Information Technology.** The module's reason to exist is external-system
  integration (gap #7 — it talks to `login.microsoftonline.com` and Office 365 SMTP/IMAP), OAuth2
  credential lifecycle, and adapting mail auth to a third party: IT-management concerns.
- **Why this departs from the parent/baseline.** `mail` is classified **13.0 Develop and Manage
  Business Capabilities**, and the auto-architect baseline for this module inherited 13.0. This child
  develops *no* new capability — it operates an external authentication interface for an existing one,
  which is exactly **8.0**. 13.0 is rejected on that ground. **9.4 / IT-security** was the closest
  alternative (CSRF guard, `group_system`-scoped secrets, id_token email-match anti-spoof) but is too
  narrow: those are protective details of the integration, not its purpose. Matches the
  `google_gmail` / `microsoft_calendar` siblings.

## 2. IT Architecture

- **Application:** microsoft_outlook — Outlook / Microsoft 365 XOAUTH2 connector for outgoing SMTP +
  incoming IMAP mail servers.
- **Software services (routes):** 2, both `http`/auth=user. `/microsoft_outlook/confirm` is the OAuth2
  redirect callback (exchanges the authorization code for refresh/access tokens, verifies the email,
  stores them on the mail-server record); `/microsoft_outlook/iap_confirm` receives tokens brokered by
  Odoo IAP (`outlook.api.odoo.com`) on Enterprise.
- **Data objects:** `microsoft.outlook.mixin` (AbstractModel, OAuth token store), `ir.mail_server` /
  `fetchmail.server` (extended with `smtp_authentication`/`server_type` = `'outlook'`),
  `res.config.settings` (client id/secret), `res.users` (`outgoing_mail_server_type='outlook'`).
- **Information flows:** outbound Odoo→`login.microsoftonline.com /common/oauth2/v2.0/{authorize,token}`
  (authorization_code + refresh_token grants); Odoo→`smtp.outlook.com:587` STARTTLS `AUTH XOAUTH2`;
  Odoo→`imap.outlook.com:993` SSL `AUTHENTICATE XOAUTH2`; Enterprise fallback Odoo→`outlook.api.odoo.com`
  IAP proxy (keeps `client_secret` off-DB); inbound Microsoft→`/microsoft_outlook/confirm|/iap_confirm`.

## 3. Data Model (the ERM)

| _name | role | #fields | key elements |
|-------|------|---------|--------------|
| `microsoft.outlook.mixin` | AbstractModel **mixin** (OAuth state) | 5 | `microsoft_outlook_refresh_token` / `_access_token` / `_access_token_expiration` / `_uri` (+`active`), all `groups=base.group_system`, `copy=False` |
| `ir.mail_server` | extension, inherits the mixin | +1 | `smtp_authentication='outlook'`; `_OUTLOOK_SCOPE = SMTP.Send` |
| `fetchmail.server` | extension, inherits the mixin | +1 | `server_type='outlook'`; `_OUTLOOK_SCOPE = IMAP.AccessAsUser.All` |
| `res.config.settings` | extension (credentials) | +2 | `microsoft_outlook_client_id` / `client_secret` config parameters |
| `res.users` | extension (personal server) | +1 | `outgoing_mail_server_type='outlook'` |

- The central abstraction is the **`microsoft.outlook.mixin`**: it grafts the refresh/access-token
  fields + lazy-refresh logic onto *both* mail-server models, so one OAuth implementation serves SMTP
  and IMAP alike — they differ only by their `_OUTLOOK_SCOPE`. Unlike `microsoft_calendar` (tokens on
  `res.users`), here **OAuth tokens live on each mail-server record** (a server is a credential holder).
- Schema is tiny and attribute-heavy (Char tokens + an Integer expiry + a couple of Selections); the
  module's weight is entirely in *behavior*, not in its data model.

## 4. Behavior & Surfaces

- **OAuth2 token fetch + refresh (code-read).** `_fetch_outlook_refresh_token` POSTs
  `grant_type=authorization_code` to `…/oauth2/v2.0/token`; `_fetch_outlook_access_token` POSTs
  `grant_type=refresh_token` for a rotated `(refresh_token, access_token, id_token, expiration)`. Endpoint
  is overridable via `microsoft_outlook.endpoint`. Tokens persist on the record (`base.group_system`,
  `copy=False`); a non-OK response surfaces the JSON `error_description` as a `UserError`.
- **Lazy refresh + XOAUTH2 string (code-read).** `_generate_outlook_oauth2_string(login)` refreshes the
  access token if it is within ~10s of expiry (else reuses it), and returns the SASL argument
  `user=<login>\x01auth=Bearer <token>\x01\x01`. No refresh_token ⇒ "Please connect with your Outlook
  account…". This is the single auth primitive shared by both transports.
- **Protocol login overrides (code-read).** `ir.mail_server._smtp_login__` base64-encodes that string and
  issues `connection.docmd('AUTH', 'XOAUTH2 …')` (forcing `starttls`, empty `smtp_pass`,
  `smtp.outlook.com:587`, `from_filter=smtp_user`, and a low spam-safe send cap). `fetchmail.server.
  _imap_login__` calls `connection.authenticate('XOAUTH2', …)` then selects INBOX (forcing SSL,
  `imap.outlook.com:993`, connection type `imap`). XOAUTH2 replaces the inherited password path.
- **OAuth redirect/IAP config flow (code-read).** `open_microsoft_outlook_uri` (admin-only) returns an
  `act_url` to Microsoft's `authorize` endpoint; the `/microsoft_outlook/confirm` controller re-checks an
  **hmac CSRF token** (`consteq`), exchanges the code, and for `ir.mail_server` re-reads the id_token
  `email` claim and **refuses a mismatched send-as link**. With no client_id/secret, Enterprise falls back
  to IAP (`outlook.api.odoo.com`) so the secret never leaves Odoo's proxy; Community raises a `UserError`.
- **External integration (gap #7, static).** Hand-rolled `requests` client (3 call sites, no SDK) to
  `login.microsoftonline.com` (OAuth) + Office 365 SMTP/IMAP (XOAUTH2 bearer). Admin supplies
  `microsoft_outlook_client_id` (public) + `client_secret` (`ir.config_parameter`, never in clear); the
  external SaaS dependency on **Microsoft Entra ID + Office 365** is the defining trait of the module.
- **Frontend:** none — 0 JS, 0 OWL components; the UX is plain mail-server/settings form views.
- **Security posture:** 0 access rules / 0 record rules / 0 new groups. Guards are imperative: admin-only
  linking, `group_system`-scoped token fields, `@api.constrains` enforcing STARTTLS/SSL + empty password,
  CSRF token, and id_token email-match.

## 5. Value-Configuration Classification

Support. `depends = [mail]`, no document chain, no sellable output. It mediates between Odoo and an
external mail/identity service — but as **infrastructure for one capability** (email transport), not as a
multi-party marketplace, so it is "support", not "network". Primary-vs-support role: **support** (it
enables the existing mail capability to interoperate with Microsoft 365 under Modern Authentication).

## 6. APQC PCF Hint

**8.0 Manage Information Technology** — manage external-system integration / data interoperability and the
OAuth2 credential lifecycle (authorization-code + refresh-token against the Microsoft identity platform,
XOAUTH2 to Office 365). Deliberately distinct from the parent's 13.0 (which owns the messaging capability
itself); 9.4 IT-security was considered but is too narrow. Identical posture to `google_gmail` /
`microsoft_calendar`.

## 7. How to Drive It

Use the **run-odoo** skill (`odoo shell`):

```python
env['ir.mail_server'].search([('smtp_authentication','=','outlook')])     # linked outgoing Outlook servers
env['fetchmail.server'].search([('server_type','=','outlook')])           # linked incoming Outlook servers
srv = env['ir.mail_server'].search([('smtp_authentication','=','outlook')], limit=1)
srv._generate_outlook_oauth2_string(srv.smtp_user)                        # mint/refresh the XOAUTH2 SASL string
env['ir.config_parameter'].sudo().get_param('microsoft_outlook_client_id')  # is the Azure app configured?
```

Route: `curl` http `/microsoft_outlook/confirm?code=…&state=…` (auth=user) → OAuth callback that stores the
refresh/access tokens on the mail-server record. External endpoints exercised:
`https://login.microsoftonline.com/common/oauth2/v2.0/token`, `smtp.outlook.com:587`, `imap.outlook.com:993`.

## 8. Open Questions

- Behavior when a refresh_token is revoked Microsoft-side (password change / consent withdrawal): the
  user-visible failure path beyond the `UserError` raised at next send/fetch.
- Whether the IAP broker (`outlook.api.odoo.com`) rotates/persists the refresh_token symmetrically with
  the direct-credential path, and how `_fetch_outlook_access_token_iap` behaves when its response omits the
  `id_token` used by the email-match check.
- How send-as for a shared mailbox / alias is intended to be configured given `from_filter` is pinned to
  `smtp_user` and the id_token email-match guard rejects mismatched addresses.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts (`facts/microsoft_outlook.facts.json`,
`frontend/microsoft_outlook.frontend.json`); behavioral notes from code-read of
`models/microsoft_outlook_mixin.py`, `models/ir_mail_server.py`, `models/fetchmail_server.py`,
`models/res_config_settings.py`, `models/res_users.py`, `controllers/main.py`. Odoo 19.0.*
