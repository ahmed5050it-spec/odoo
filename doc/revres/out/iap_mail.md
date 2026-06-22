# iap_mail — Reverse-Engineering Brief

`iap_mail` ("IAP / Mail", category Hidden/Tools, `auto_install=true`,
`application=false`) is a thin glue module that bridges Odoo's IAP credit
framework (`iap`) and its messaging engine (`mail`). It owns no business object
of its own: it re-opens `iap.account` to add `mail.thread` chatter + field
tracking, ships two reusable QWeb "enrichment card" templates
(`enrich_company`, `enrich_company_by_dnb`), and provides the shared toast
helpers (`_send_success/_error/_no_credit_notification`) plus the
`iapNotification` JS service that renders them. Sitting at the junction of `iap`
and `mail`, it is the shared notification-template + UX layer that the whole
paid-feature suite (crm_iap_enrich, crm_iap_mine, website_crm_iap_reveal,
partner_autocomplete, mail_plugin, snailmail, sms) reuses so each module does
not re-implement the IAP-branded "result card" and "buy more credits" prompt.

## Role & Dependencies

- **iap** — supplies the credit account (`iap.account`) and `get_credits_url`
  (the hashed buy-more deep-link) that the no-credit toast reuses.
- **mail** — supplies `mail.thread` (chatter, followers, field tracking) and
  `message_post_with_source`, the mechanism that renders the enrich templates
  into a record's chatter.

**Capability added:** a shared presentation/notification layer over IAP results
— styled enrichment chatter cards, success/error/no-credit bus toasts (with a
one-click top-up link), and chatter/audit on the credit account itself.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|-------------|---------|---------------|
| `iap.account` | IAP Account (extended) | 3 added | `_inherit`=[`iap.account`,`mail.thread`]; `company_ids`->res.company (tracking), `warning_user_ids`->res.users (tracking) |

The only model is an **extension** (`_inherit` with the same `_name`) of the
parent `iap.account`, mixed with `mail.thread`. It adds no new model — it just
re-declares `company_ids`, `warning_threshold`, `warning_user_ids` with
`tracking=True`. Field-type distribution (2 Many2many, 1 Float) is purely the
tracking overlay; this is a relational-glue module, not a data-bearing one.

## Behavior & Surfaces

- **Routes:** none (0). No web/RPC surface of its own.
- **Views:** 0 own views; 1 inherited form xpaths a `<chatter/>` into
  `iap.iap_account_view_form`. Plus 2 QWeb data templates (the enrich cards).
- **Security:** 0 access rules, 0 record rules, 0 groups — reuses `iap`'s
  existing rules on `iap.account`.
- **Frontend (static):** 1 JS file, 0 OWL components, 1 registry add
  (`services:iapNotification`); bundles `web.assets_backend`,
  `web.dark_mode_assets_backend`. 2 SCSS files (icon min-width fix + dark mode).
- **Integrations (static):** 0 HTTP call sites, no SDKs, no API keys, no
  endpoints — all network egress stays in the parent `iap` module.
- **Key behaviors (code-read):**
  - `_send_status_notification(message, status, title)` → `env.user._bus_send('iap_notification', {...})`; `_send_success_notification` / `_send_error_notification` wrap it ('success'/'danger'). `@api.model`, called as `env['iap.account']._send_*`.
  - `_send_no_credit_notification(service_name, title)` → resolves `get_credits_url(service_name)` and pushes `type:'no_credit'` so the JS renders a "Buy more credits" button.
  - `iapNotification` JS service subscribes the `iap_notification` bus channel and renders toasts (`markup`` HTML-safe link for the no-credit case).
  - `enrich_company` (Clearbit/reveal) and `enrich_company_by_dnb` (D&B, inline base64 logo) are posted via `message_post_with_source(..., subtype_xmlid='mail.mt_note')` by consumers.

## Value-Configuration Classification

**value_model = support**, **activity_class = support**. Against Stabell &
Fjeldstad: not a chain (no document transform), not a shop (no problem-solving
case), not a network (the actual mediation lives in `iap`/`mail`, not here).
`iap_mail` is cross-cutting **support** infrastructure — shared IAP
notification-template and UX plumbing consumed by many paid features, owning no
business object of its own. `auto_install=true` + Hidden/Tools confirm
invisible, ubiquitous glue.

## APQC PCF Hint

**8.0 Manage Information Technology** — the work is IT/IAP enablement:
presenting and notifying the outcomes of external paid IT services (credit
status, vendor enrichment). 9.4 "internal communications" was considered (it
rides the mail/notification channel) but the content is technical IAP
enablement for the operator of a paid feature, not organisational comms — and
8.0 keeps it aligned with its parent `iap`.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['iap.account']._send_success_notification('Done', title='IAP')` — bus toast to current user.
- `env['iap.account']._send_no_credit_notification('reveal', 'Out of credits')` — no-credit toast with buy-credits link.
- `env.ref('iap_mail.enrich_company')` / `env.ref('iap_mail.enrich_company_by_dnb')` — the shared QWeb templates.
- `rec.message_post_with_source('iap_mail.enrich_company', render_values={'name':'ACME','flavor_text':'demo'}, subtype_xmlid='mail.mt_note')` — post a styled enrich card to any `mail.thread` record.

No routes to curl (the module exposes none).

## Open Questions

- Full catalogue of downstream consumers and which helper/template each uses is
  spread across the IAP suite, not declared inside `iap_mail`.
- Whether a non-Clearbit/non-D&B provider would extend these templates or ship
  its own card (not decidable from this module).
- The exact enrichment payload shape (keys the templates expect) is set by the
  IAP server, not reverse-engineerable here (gap #7).

---
*Provenance: extract_module.py + extract_frontend.py + code-read
(models/iap_account.py, data/mail_templates.xml,
static/src/js/services/iap_notification_service.js, views/iap_views.xml). Odoo 19.0.*
