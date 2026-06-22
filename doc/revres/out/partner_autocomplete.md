# partner_autocomplete — Architecture Brief

> Module: `partner_autocomplete` · Category: Hidden/Tools · Depends: `iap_mail` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **13.0 Develop and Manage Business Capabilities**
> Odoo 19.0 · Facts: `doc/revres/facts/partner_autocomplete.facts.json` · Frontend: `doc/revres/frontend/partner_autocomplete.frontend.json`

## 1. Summary

`partner_autocomplete` is a **type-ahead company master-data enrichment utility**.
As you type a partner name (or VAT/GST/DUNS/domain), it queries Odoo's external
**Dun & Bradstreet (DnB)** data service via the IAP broker and maps the returned
payload — name, VAT, address, industry, language, logo — onto `res.partner`.
It owns no business object of its own: **1 declared AbstractModel
(`iap.autocomplete.api`, no table), 4 inherits, 0 routes, 0 security records,
~791 py LOC**. `auto_install: true` + category *Hidden/Tools* mark it as invisible
plumbing layered on top of `iap`/`iap_mail`. Its substance is the **inbound
payload→record mapping** plus the **outbound DnB call** (gap #7).

## 2. Structure (evidence)

- **Models (1 own + 4 inherit):** `iap.autocomplete.api` (AbstractModel, 0 fields
  — the egress wrapper); `res.partner` (+autocomplete/enrich query + mapping
  methods); `res.company` (+`iap_enrich_auto_done` Boolean, auto-enrich on create);
  `res.config.settings` (+`partner_autocomplete_insufficient_credit`); `ir.http`
  (+`session_info` flag).
- **Routes:** **0** — no web/RPC surface of its own; the backend methods are
  reached via ORM from OWL, and the only HTTP is *outbound* through `iap`.
- **Security:** 0 access rules, 0 record rules, 0 groups — relies on the inherited
  models' security and on `iap.account`'s `group_system` token protection.
- **Views:** **0** declared — widgets are injected at render time via `_get_view`,
  not via XML view records.

## 3. Frontend (gap #3)

**5 JS / 1 XML**, bundled in `web.assets_backend` (+`web.jsvat_lib`,
`web.assets_unit_tests`). One OWL component, `PartnerAutoCompleteMany2one`, plus
registry adds `fields:field_partner_autocomplete`, `fields:res_partner_many2one`,
and the `services:partner_autocomplete.companyAutocomplete` service.
`usePartnerAutocomplete` (core) debounces typing with `KeepLast`, loads the
**jsvat** lib to detect VAT/GST format, and ORM-calls `autocomplete_by_name` /
`autocomplete_by_vat` as the user types, rendering a suggestion dropdown
(name, VAT, logo, address). `res.partner._get_view` / `res.company._get_view`
inject `widget="field_partner_autocomplete"` onto the `name`/`vat`/`duns` fields,
so no XML view edits are needed.

## 4. Behavior (beyond metadata)

- **DnB call (code-read):** `iap.autocomplete.api._contact_iap` lazily provisions
  `iap.account.get('partner_autocomplete')`, injects `account_token` + `db_uuid` +
  company `country_code`/`zip`, and `iap_jsonrpc`-POSTs to
  `partner-autocomplete.odoo.com/api/dnb/1/<action>` (`search_by_name`,
  `search_by_vat`, `enrich_by_duns`, `enrich_by_gst`, `enrich_by_domain`). Endpoint
  is overridable via `ir.config_parameter 'iap.partner_autocomplete.endpoint'`; in
  test mode it raises `ValidationError('Test mode')` so it never bills.
- **Payload mapping (code-read):** `_format_data_company` runs three resolvers —
  `_iap_replace_location_codes` (country/state, and city when
  `base_address_extended` + `enforce_cities`), `_iap_replace_industry_code`
  (DnB code → `base.res_partner_industry_<code>`), `_iap_replace_language_codes`
  (→ installed `res.lang`) — turning provider codes into `{id, display_name}`
  dicts. The **logo** flows through as `image_1920`; `res.company._enrich` writes
  only empty partner fields (image_1920 always overwrites). VAT is re-checked via
  `base_vat _run_vat_checks(setnull)`, and `autocomplete_by_vat` falls back to
  **VIES** (`stdnum check_vies`) when IAP returns nothing.
- **Auto-enrich (code-read):** `res.company.create` → `iap_enrich_auto` → `_enrich`
  derives the company domain from email/website and calls `enrich_by_domain`,
  one-shot per company (`iap_enrich_auto_done` guard); `ir.http.session_info`
  exposes `iap_company_enrich` to admins.
- **Credit (code-read):** no local ledger — `res.config.settings` probes
  `iap.account.get_credits('partner_autocomplete') <= 0` for the insufficient-credit
  warning and `get_credits_url` for the buy-more redirect; `InsufficientCreditError`
  surfaces as `error_message: 'Insufficient Credit'`.
- **External integration (static, gap #7):** 0 direct call sites; egress is
  brokered by `iap_tools.iap_jsonrpc`. Auth is the per-account token, not an API
  key. Provider: DnB behind `partner-autocomplete.odoo.com`, plus VIES.

## 5. IT architecture

- **Application:** type-ahead company master-data enrichment over the IAP DnB
  service.
- **Data objects:** `iap.autocomplete.api`, and inherits on `res.partner`,
  `res.company`, `res.config.settings`, `ir.http`.
- **Key relations:** `iap.autocomplete.api → iap.account` (token);
  `res.partner → res.country/state/city/industry/category`;
  `res.company → res.partner` (enriched write).
- **Flows:** OWL typing → ORM `autocomplete_by_*` → `_contact_iap` → `iap_jsonrpc`
  → DnB → `_format_data_company` → partner fields; `res.company.create` →
  `iap_enrich_auto` → `enrich_by_domain`; credit-gate via `iap.account`.

## 6. Business architecture

- **Capabilities (inferred):** lookup company by name/VAT/GST/DUNS/domain; map
  payload onto `res.partner`; auto-enrich new company from its domain; validate
  VAT (setnull + VIES); credit-gate + buy-more; chatter enrichment note.
- **Value streams (inferred):** *Type-to-Enrich* (type → DnB suggestions → select
  → fields written) and *Create-Company-to-Enriched* (create → domain → populate).
- **Information concepts (auto):** `iap.autocomplete.api`, `res.partner`,
  `res.company`, IAP credit/token, external DnB company record.
- **Policies (inferred):** one-shot enrich guard; test-mode no-bill; write only
  empty fields (image_1920 excepted); VAT re-validation.
- **Strategy:** `null` (human). **Organization/Products:** none.

## 7. Classification

- **Value model: support** — shared firm IT infrastructure (Stabell & Fjeldstad
  *support*; Porter support activity). It owns no chain/shop/network business
  object; it enriches existing partner master data via the `iap` broker.
- **Activity class: support.**
- **APQC: 13.0 Develop and Manage Business Capabilities** — the work is
  **master-data management** (populating/maintaining the partner master that
  sale/purchase/account/crm reuse). `8.0 Manage Information Technology` was
  considered (the sibling `iap` lives there as the egress broker) but
  `partner_autocomplete` adds no IT plumbing of its own — it *consumes* iap's
  broker, and its substance is enriching business master data.

## 8. Fit-to-Standard

- **Standard:** name/VAT/GST/DUNS/domain autocomplete; payload→partner mapping;
  one-shot domain self-enrichment; VIES fallback + VAT re-validation;
  credit-aware UX; configurable provider endpoint; chatter enrichment note.
- **Typical fits:** faster partner creation in Sales/Purchase/CRM; bootstrapping
  the user's own company from its domain; pointing autocomplete at a private proxy.
- **Common gaps:** needs IAP credit + outbound HTTPS (no air-gapped enrichment);
  DnB-centric coverage; no local audit/spend ledger (metered remotely);
  one-shot auto-enrich; unresolved location/industry codes silently dropped.
- **Drive:** `env['res.partner'].autocomplete_by_name('Odoo', env.company.country_id.id)`;
  `env['res.partner'].enrich_by_domain('odoo.com')`;
  `env['iap.account'].get_credits('partner_autocomplete')`.
