# crm_mail_plugin — Reverse-Engineering Brief

The **crm_mail_plugin** module is the CRM backend for Odoo's Outlook/Gmail mail add-in ("Turn emails received in your mailbox into leads and log their content as internal notes", category *Sales/CRM*). It is a small (`299` Python LOC), `application: false`, **`auto_install: true`** bridge that activates whenever both **crm** and **mail_plugin** are present. It owns no new models; instead it grafts a lead-acquisition layer onto the inbox sidebar: from an open email a salesperson can create a `crm.lead` in one click, log the email body onto an existing lead, and see the sender's open leads (revenue + probability) inside the add-in contact card. All the heavy mail-plugin plumbing — outlook bearer-token auth, the email-to-partner lookup, and IAP company enrichment — lives in the parent **mail_plugin**; this module only adds the CRM-specific routes and the contact-card lead list.

## Role & Dependencies

- **crm** — supplies `crm.lead` (the record this module creates/reads), `crm.group_use_recurring_revenues`, default team/stage/PLS scoring, and the standard lead form (`crm.crm_lead_view_form`).
- **mail_plugin** — supplies the JSON-RPC controller base, the `outlook` auth method (`ir_http._auth_method_outlook`), the auth-code → access-token exchange (`authenticate.py`), the partner resolution route (`res_partner_get`), and IAP enrichment (`_iap_enrich`). This module subclasses `mail_plugin.MailPluginController` and extends its hooks.

Capability added on top: inbox-to-lead capture and a contact-context lead list, gated by CRM access rights.

## Data Model (the ERM)

| _name / _inherit | _description | #fields | Key relations |
|------------------|--------------|--------:|---------------|
| `_inherit crm.lead` | Lead (mail-plugin auto-fill extension) | 0 new | partner_id→res.partner |

The module defines **0 new models** and exactly **1 inherit-only extension** of `crm.lead`, adding a single method `_form_view_auto_fill()` (a deprecated saas-14.3 helper that opens a lead form pre-filled with `default_partner_id`). There is no security data (0 access rules, 0 record rules, 0 groups) — it relies entirely on `crm.lead`'s own ACLs, checked at runtime via `crm.lead.has_access('create')`. The only stored datum is one `ir.actions.server` record (`lead_creation_prefilled_action`). Value flows across two information concepts it does not own — `crm.lead` and `res.partner` — plus `res.users.apikeys` as the outlook token identity.

## Behavior & Surfaces

Five HTTP routes (4 JSON-RPC `auth="outlook"`, 1 `auth="user"`); only **`/mail_plugin/lead/create`** is current — the other four are explicitly "deprecated as of saas-14.3" shims kept for older add-in clients.

- **`/mail_plugin/lead/create`** (`crm_lead_create`): `exists()`-validates `partner_id` (else `{'error': 'partner_not_found'}`), then `crm.lead.with_company(partner.company_id).create({name: html2plaintext(subject), partner_id, description: email_body})`, returning `{'lead_id': id}`. No stage/team set → CRM defaults + PLS apply.
- **`_get_contact_data` / `_fetch_partner_leads` override**: appends a `leads` key to the sidebar contact card (search `crm.lead` by `partner_id`, limit 5: name/expected_revenue/probability, plus recurring fields when `crm.group_use_recurring_revenues`). The key is only added when `crm.lead.has_access('create')`, so the section silently disappears for users who cannot create leads.
- **Auth**: `_auth_method_outlook` (parent) reads the `Authorization` header, strips `Bearer `, and validates against `res.users.apikeys._check_credentials(scope='odoo.plugin.outlook')`. The token is a 1-day API key minted from a 3-minute HMAC-signed auth code.
- **Enrichment** is NOT here: `mail_plugin._iap_enrich` → `iap.enrich.api._request_enrich` resolves/creates the partner *before* this module attaches its lead list.
- **Frontend**: no OWL/JS (0 js files); the 2 XML templates are backend data. The real UI is the external Outlook/Gmail add-in.

## Value-Configuration Classification

**Value model: `shop` · Activity class: `primary`.** crm_mail_plugin is a thin lead-acquisition extension of CRM, itself a value-shop. Its work is capturing and qualifying prospects from inbox interactions — feeding the CRM diagnose-qualify-nurture loop rather than transforming inputs into outputs along a chain. It is a feeder/bridge (auto_install) onto `crm.lead` rather than a standalone value stream, but the activity it performs is lead capture at the very front of the shop, so `shop`/`primary` rather than `support`.

## APQC PCF Hint

**3.0 Market and Sell Products and Services**, specifically **3.5.1 Manage leads** — turning an inbound email into a qualified `crm.lead`. Maps to the `crm.lead` lead-qualification row in `apqc_odoo_map.tsv` (value_model `shop`). The created lead then enters CRM's standard 3.5 lead/opportunity management flow.

## How to Drive It

- `odoo shell`: `p = env['res.partner'].search([('email','!=',False)], limit=1); l = env['crm.lead'].with_company(p.company_id).create({'name':'Inbox subject','partner_id':p.id,'description':'email body'}); (l.id, l.type, l.team_id.name)`
- `odoo shell`: `env['crm.lead'].search([('partner_id','=',p.id)], limit=5).mapped(lambda r:(r.name,r.expected_revenue,r.probability))`
- `curl -X POST .../mail_plugin/lead/create -H 'Authorization: Bearer <apikey>' -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"call","params":{"partner_id":1,"email_subject":"Hi","email_body":"body"}}'`
- `odoo shell`: `env['res.users.apikeys']._check_credentials(scope='odoo.plugin.outlook', key='<token>')`

## Open Questions

- Exact `crm.lead` defaults (team_id/stage_id/user_id) for a plugin-created lead with no salesperson context beyond `with_company`.
- Whether any current add-in client still calls the four saas-14.3-deprecated routes or only `/mail_plugin/lead/create`.
- Whether `email_body`/`description` is HTML-sanitized beyond the `html2plaintext` applied to the subject.
