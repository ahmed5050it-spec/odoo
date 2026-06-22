# mail_plugin — Architecture Brief

*Odoo 19.0 · category Sales/CRM · depends: web, contacts, iap · LGPL-3 · Odoo S.A.*
*Record: `doc/revres/metamodel/mail_plugin.metamodel.json` · Facts: `doc/revres/facts/mail_plugin.facts.json`*

## 1. Overview
`mail_plugin` is the **server-side backend for the Odoo Outlook and Gmail mail
add-ins**. It is an external-integration module: no OWL/JS ships here (the UI is
the third-party add-in), and almost all weight (1145 Python LOC) sits in two
controllers exposing a JSON API. It lets a user, from their inbox, resolve the
sender to an Odoo contact, enrich/create the contact's company via IAP, and log
the email back onto the record. It owns one technical model (`res.partner.iap`)
and adds two computed fields to `res.partner`.

## 2. IT Architecture
- **Application:** mail_plugin — a route-heavy integration boundary, not a UI app.
- **Software services (12 routes):** contact `get`/`search`/`create`,
  `enrich_and_create_company`, `enrich_and_update_company`, `log_mail_content`,
  `get_translations`, plus the auth trio `auth` / `auth/confirm` /
  `auth/access_token` and `auth/check_version`. Data routes use a custom
  `auth="outlook"` method; legacy `/mail_client_extension/*` aliases are kept.
- **Data objects:** `res.partner.iap` (own), `res.partner` (+2 fields), `ir.http`
  (auth method). ERM: `res.partner.iap → res.partner` (1:1, UNIQUE).
- **External integrations:** outbound to the **IAP enrichment web service**
  (`iap.enrich.api._request_enrich`) and to third-party **logo URLs** via
  `requests.get`; inbound auth via **`res.users.apikeys`** (scope
  `odoo.plugin.outlook`).

## 3. Behavioral Notes (code-read)
- **IAP enrichment:** unknown senders trigger a paid IAP RPC for company
  name/address/phone/logo; free-mail/blacklisted domains are skipped;
  `InsufficientCreditError` is caught and reported to the add-in.
- **Logo egress:** a second outbound `requests.get(logo_url, timeout=2)` fetches
  the logo into `image_1920`; failures are swallowed.
- **Custom auth:** `_auth_method_outlook` validates the Bearer token via
  `res.users.apikeys._check_credentials` and impersonates the key's user. A
  2-leg flow mints tokens: HMAC-signed auth code (3-min TTL) → 1-day apikey.
- **Email logging:** `log_mail_content` calls `message_post` on the record,
  restricted to `_mail_content_logging_models_whitelist()` (res.partner only).
- **Enrichment cache:** `res.partner.iap` caches IAP responses keyed by domain to
  avoid double-enrichment; `res.partner.create/write` upsert the side-table.

## 4. Business Architecture
- **Capabilities (inferred):** Expose Contacts/CRM to email clients; inbox
  contact lookup & search; IAP company enrichment; log emails to records;
  external-app authorization (token issuance).
- **Value stream (inferred):** *Email-to-CRM* — open email → resolve/enrich
  contact → create partner/company → log message back to the record.
- **Information concepts (auto):** res.partner, res.partner.iap, res.users.apikeys,
  mail.message.
- **Organization (auto):** `base.group_system` is the sole ACL on res.partner.iap.
- **Policies (inferred):** outlook-token gate on all data routes; logging
  whitelist; free-mail enrichment exclusion. **Strategy:** null (human).

## 5. Classification
- **Value model:** `support` · **Activity class:** `support`
- **APQC:** **8.0 Manage Information Technology**
- **Rationale:** This is an IT-enablement integration backend, not a primary
  sell activity. It ships no business documents/products — only auth, a JSON API
  surface and an enrichment cache — and merely **re-exposes** data owned by the
  contacts/CRM (3.0) subsystems to a third-party email client. Develop/operate an
  external integration ⇒ APQC 8.0, not 3.0 *Market and Sell*. The IAP enrichment
  is the one business-leaning feature but is delivered as a technical service over
  the integration boundary, confirming the support classification.

## 6. Fit-to-Standard
- **Standard:** official Outlook/Gmail add-in JSON API; OAuth-style token flow;
  custom `outlook` Bearer auth; IAP enrichment with domain de-dup; email logging;
  add-in translation feed.
- **Typical fits:** install the Odoo-published add-in as-is; auto-create/enrich
  contacts from the inbox using IAP credits; user-company-scoped lookup.
- **Common gaps:** whitelist more log targets (override
  `_mail_content_logging_models_whitelist` — crm.lead, helpdesk.ticket); return
  extra record context (override `_get_contact_data`); swap IAP for another data
  provider; tighten token lifetime/scope beyond the 1-day apikey.

## 7. Drive Hints
- `curl -X POST $ODOO/mail_plugin/auth/check_version` (auth=none) → `1` if installed.
- `curl -X POST $ODOO/mail_plugin/partner/search -H 'Authorization: Bearer <apikey>' -d '{"params":{"search_term":"odoo"}}'`.
- `odoo shell: env['res.partner.iap'].search([], limit=5).read(['partner_id','iap_search_domain'])`.
- `odoo shell: env['res.users.apikeys']._check_credentials(scope='odoo.plugin.outlook', key='<token>')`.

## 8. Open Questions
- Exact IAP enrich payload/contract and per-call credit consumption.
- Which downstream modules extend `_get_contact_data` /
  `_mail_content_logging_models_whitelist` (crm, helpdesk) and what they add.
- Token lifecycle: revocation, 1-day expiry handling, add-in refresh behavior.

*Confidence: information_concepts/organization/products = auto; capabilities/
value_streams/policies/metrics = inferred; strategy = human.*
