# base_vat — Reverse-Engineering Brief

`base_vat` (manifest name "VAT Number Validation", category Accounting/Accounting,
v2.0, LGPL-3) adds tax-identification-number correctness to Odoo. It is **not** an
application and **not** auto_install; it depends only on `account`. It owns **zero
own `_name` models** — it is pure cross-cutting infrastructure that extends
`res.partner`, `res.company`, `res.country` and `res.config.settings` to validate,
format and (for the EU) VIES-verify the partner `vat` field that downstream
invoicing and tax determination rely on.

## Role & Dependencies
- **account** — provides the partner-level VAT plumbing this module completes: the
  `_check_vat` constraint and `_build_vat_error_message`/`_run_vat_checks` hooks are
  declared in `account`; `base_vat` overrides `_run_vat_checks` to supply the real
  per-country logic and EU/VIES handling. The Accounting category and this single
  dependency anchor it as financial support, not a standalone app.

Capability added on top: a comprehensive VAT/TIN validation + formatting engine
(~30 national algorithms plus python-stdnum), and an online EU VIES check wired
through Odoo IAP with an async cron + signed inbound webhook.

## Data Model (the ERM)
No new entity is introduced. The module is four `_inherit`-only extensions
(mixin/extension = `_inherit` without `_name`):

| Model (_inherit) | Adds | Key relation |
|------------------|------|--------------|
| `res.partner`    | `vies_valid`, `perform_vies_validation`; inverse on `vat`, `country_id` | `country_id->res.country` (inverse `_inverse_vat`); `parent_id` VIES inheritance |
| `res.company`    | `vat_check_vies` | — |
| `res.config.settings` | `vat_check_vies` | — |
| `res.country`    | `has_foreign_fiscal_position` (computed) | `<- account.fiscal.position.foreign_vat` |

Field-type distribution is tiny and attribute-only: 5 Boolean, 1 Many2one, 1 Char
across all extensions. There is no aggregate/central model — the "logic mass" is in
methods (64 on the `res.partner` extension), not in fields. Information concepts are
therefore the **extended** models (it owns no business entity of its own).

## Behavior & Surfaces
- **Routes:** exactly 1 — `/base_vat/1/webhook_update_vies` (auth=public, type=http).
  It is an inbound IAP callback, not a user-facing surface; trust comes from a
  server-signed `vies_check` token verified by `verify_hash_signed`.
- **Views:** none (0 of every type). All UI is the inherited partner/company/settings
  forms owned by base/account.
- **Frontend:** none — `present=false`, 0 JS/OWL/XML, no asset bundles, no registry
  adds or patches. Entirely server-side.
- **Security:** 0 access rules, 0 record rules, 0 groups — it adds no objects to
  secure, only behaviour on existing ones.
- **Integrations (gap #7):** 2 outbound HTTP call sites (`models/res_partner.py`,
  SDK `requests`) to `https://vies.api.odoo.com` (prod) / `https://vies.test.odoo.com`
  (demo); `uses_api_keys=false` (IAP auth is db_uuid + per-db client token).

Behavioral facts metadata cannot show (code-read): (1) `check_vat_<cc>` per-country
checksum/regex validators dispatched by `_check_vat_number`; (2) python-stdnum as the
default validator/formatter, with overrides patching where stdnum lags; (3) the VIES
online check (`_compute_vies_valid`/`_check_vies_iap`) plus cron `_cron_check_vies_iap`
and the signed webhook for `pending` results; (4) the `_check_vat` constraint bound on
`commercial_partner_id` via inverse `_inverse_vat`.

## Value-Configuration Classification
**Support** (Stabell & Fjeldstad), **activity_class = support**. It is firm-
infrastructure — like accounting/legal — that guarantees the correctness of one
master-data attribute (the Tax ID) consumed by primary activities. It transforms no
document (not chain), solves no engagement (not shop) and mediates no exchange between
parties (not network); it is a compliance control feeding the financial backbone.

## APQC PCF Hint
**9.0 Manage Financial Resources.** It underpins 9.x tax/AR/AP correctness by
validating the VAT used on invoices and fiscal positions. **11.0 Manage Enterprise
Risk/Compliance** was a real candidate — the EU-VIES check is a regulatory control —
but it was rejected as primary: the code sits in Accounting/Accounting, depends only on
`account`, and exists to keep financial documents legally valid, so the compliance
angle is a facet of the financial-resource management it supports.

## How to Drive It
Use the **run-odoo** skill (`odoo shell`):
- `env['res.partner'].check_vat_be('BE0477472701')` → True (try a malformed one to see
  it return False).
- `env['res.partner'].create({'name':'X','country_id': env.ref('base.fr').id, 'vat':'FR23334175221'})`
  — a bad `vat` raises `ValidationError` via `_inverse_vat`.
- `env['res.company'].search([]).mapped(('name','vat_check_vies'))` — is VIES enabled?
- `curl -X POST http(s)://host/base_vat/1/webhook_update_vies -d 'webhook_token=...&status=valid'`
  — rejected without a valid signed token (auth=public).

## Open Questions
- Exact IAP VIES request/response contract and the full status set beyond
  valid/pending/fault/unassigned.
- Which countries rely on the ~30 in-module `check_vat_*` overrides vs. python-stdnum.
- When `_get_vat_required_valid` actually *blocks* (EU membership × foreign fiscal
  position × `vies_valid`).
- Behaviour when IAP is unreachable / cron disabled, and whether 7-day token expiry can
  silently drop a pending update.

---
*Provenance: structural facts from `extract_module.py` (`facts/base_vat.facts.json`);
frontend/integration facts from `extract_frontend.py` (`frontend/base_vat.frontend.json`);
behavioral notes from code-read of `models/res_partner.py`, `models/res_country.py`,
`controllers/webhook.py`. Odoo 19.0.*
