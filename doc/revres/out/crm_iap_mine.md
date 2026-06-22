# crm_iap_mine — Reverse-Engineering Brief

The **crm_iap_mine** module ("Lead Generation", category *Sales/CRM*, `version 1.2`) lets a sales user **mine new leads from an external data provider**: it frames a request by country, industry, company size and contact role/seniority, calls Odoo's **IAP "reveal" service** (Dun & Bradstreet data, default endpoint `https://iap-services.odoo.com`), and materializes the returned companies/contacts as `crm.lead` records that flow into the standard CRM pipeline. It is `auto_install: true`, **not** an `application` (a bolt-on that activates once both its dependencies are present), and `application: false`. It sits on just two modules: **iap_crm** (the IAP↔CRM glue, source of the `reveal_id` dedup field on `crm.lead`) and **iap_mail** (mail templates: the per-lead enrichment note and the no-credit warning). Unlike base `crm`, the leads here are not captured from inbound demand — they are **purchased on demand** from an external service, metered in IAP credits.

## Role & Dependencies

- **iap_crm** — provides the `crm.lead.reveal_id` technical field (IAP request id) used to deduplicate; the IAP-CRM bridge this module specializes into a full mining wizard.
- **iap_mail** — supplies the `iap_mail.enrich_company` template posted on each created lead, plus the mail used by `_notify_no_more_credit`.

Capability added on top: an **outbound lead-acquisition pipeline** — criteria wizard → external IAP request → bulk lead/opportunity creation → company/contact enrichment → credit metering and top-up — feeding the parent CRM pipeline.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `crm.iap.lead.mining.request` | CRM Lead Mining Request | 26 | lead_ids→crm.lead, team_id→crm.team, user_id→res.users, country_ids→res.country, industry_ids→crm.iap.lead.industry, role_ids/preferred_role_id→crm.iap.lead.role, seniority_id→crm.iap.lead.seniority |
| `crm.iap.lead.industry` | CRM IAP Lead Industry | 4 | — (carries `reveal_ids` provider codes) |
| `crm.iap.lead.role` | People Role | 3 | — (`reveal_id`) |
| `crm.iap.lead.seniority` | People Seniority | 2 | — (`reveal_id`) |
| `crm.iap.lead.helpers` | Helper methods (no-store) | 0 | — |
| `crm.lead` *(inherit)* | Lead | +1 | lead_mining_request_id→crm.iap.lead.mining.request |

`crm.iap.lead.mining.request` is the central aggregate (23 methods, 26 fields); the three small `industry`/`role`/`seniority` models are **reference/lookup tables** mapping human labels to provider `reveal_id`(s). `crm.iap.lead.helpers` is a model with **no fields** (a method bag, no-access in security). The module also has **one inherit-only extension** (`crm.lead`, no `_name`) adding only the back-link Many2one and folding it into `_merge_get_fields`. Field-type distribution on the request is **filter-heavy**: 5 Selection + 5 Many2many + 5 Integer + 4 Many2one + 4 Char + 2 One2many + 1 Boolean — i.e. a configuration form whose fields are search criteria, not transactional lines.

## Behavior & Surfaces

- **Routes:** **0** controller routes — no web/RPC surface of its own. All interaction is through the backend wizard; the only outbound HTTP is the IAP JSON-RPC call (`iap_tools.iap_jsonrpc`), not an Odoo route.
- **Views:** form 1, list 1, search 1 (no kanban/pivot/graph/calendar). A single wizard-style form (the request) plus a list — a configure-and-submit UX, not an analytical one. Frontend is minimal: 1 JS file, 0 OWL components, bundled in `web.assets_backend`.
- **Security posture:** **5 access rules, 0 record rules, 0 groups.** Industry/role/seniority/request are all read-write for `sales_team.group_sale_manager`; `crm.iap.lead.helpers` has no access (internal-only). Lead generation is thus a **manager-gated** capability.

## Value-Configuration Classification

**Value model: `shop`** (Stabell & Fjeldstad value-shop), **activity_class: primary**. This module is the **lead-acquisition front of the CRM shop**: a value shop solves a customer-finding problem cyclically (problem-finding/acquisition → solving → choice → execution), and `crm_iap_mine` performs exactly the **acquisition** step — the user frames an acquisition problem (criteria), the system mobilizes an external knowledge resource (IAP Reveal / D&B), and emits prospects as `crm.lead` records that re-enter the qualify/convert loop owned by parent `crm`. It is **not a chain**: there is no inbound-order-to-outbound-product transform, no inventory/BOM; the output is *information* (leads), value rests on the data source's quality/reputation, and the activity is iterative (re-run with refined criteria, dedup against prior results via `reveal_id`). It is a **primary** activity because it directly creates the pipeline input that downstream `sale` (chain) monetizes. **`support` was considered and rejected:** structurally it is a thin auto-install add-on with no routes, but its *business function* is value-creating customer acquisition, not internal enablement (IT/HR/finance) — the support flavor here is architectural only.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — specifically **3.1 / 3.5.1 Generate and manage leads**. The `apqc_odoo_map` ties `crm.lead` (value_model `shop`) to research/qualify tasks; this module is the lead-*generation* upstream of that loop, sourcing leads externally before scoring/conversion (handled by `crm`) and order capture (3.5.3+, handled by `sale`).

## How to Drive It

Use the **run-odoo** skill (`odoo shell`). There are no routes to `curl`:

- `r = env['crm.iap.lead.mining.request'].create({'name':'Demo','lead_number':3,'search_type':'companies'}); r._prepare_iap_payload()` — inspect the outbound IAP payload **without** spending credits.
- `env['iap.account'].get('reveal').account_token` — confirm the reveal credit wallet is configured.
- `env['ir.config_parameter'].sudo().get_param('reveal.endpoint','https://iap-services.odoo.com')` — the external endpoint actually used.
- `env['crm.iap.lead.industry'].search([], limit=5).mapped(('name','reveal_ids'))` — see the label→provider-code mapping.
- UI: from a CRM pipeline, **Generate Leads** (`crm.lead.action_generate_leads`) opens the wizard as a modal.

## Open Questions

- **Remote contract (external API):** the result schema, partial-result and pagination behavior of `/api/dnb/1/search_by_criteria` — only the client side is in-repo.
- **Real credit cost:** authoritative debit happens server-side on IAP; `CREDIT_PER_COMPANY`/`CREDIT_PER_CONTACT` and `_compute_tooltip` are local *estimates* only.
- **Multi-contact enrichment (inferred):** `lead_vals_from_response` attaches only the first contact to the lead — whether/how additional `people_data` is surfaced is not in static facts.
- **Provider coverage:** state filtering is whitelisted to a few countries (`_STATES_FILTER_COUNTRIES_WHITELIST`); real-world result quality per country is unverifiable from code.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/crm_iap_mine.facts.json) + `extract_frontend.py`; behavioral notes from reading `addons/crm_iap_mine/models/{crm_iap_lead_mining_request,crm_iap_lead_helpers,crm_lead}.py`. Odoo 19.0.*
