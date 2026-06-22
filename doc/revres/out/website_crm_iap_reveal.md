# website_crm_iap_reveal — Reverse-Engineering Brief

The **website_crm_iap_reveal** module ("Lead Generation From Website Visits", category *Sales/CRM*, `version 1.1`) **identifies the company behind anonymous website traffic and auto-creates CRM leads**. On every public page view it passively captures the visitor's IP (via a `ir.http._serve_page` override), matches it against configurable `crm.reveal.rule` records (GeoIP country/state, URL regex, website, company size, industry), and queues the IP as a `crm.reveal.view`. A scheduled cron then batches those IPs to Odoo's **IAP "reveal" service** (Clearbit / D&B IP-to-company data, default endpoint `https://iap-services.odoo.com`, path `/iap/clearbit/1/reveal`) and materializes the returned companies as `crm.lead` records that flow into the standard CRM pipeline. It is `auto_install: false`, `application: false` — an opt-in bolt-on. Unlike `crm_iap_mine` (which mines leads from a user-framed criteria *request*), here demand is **inferred from real traffic**: the trigger is a page render, not a wizard, and the whole acquisition is an outbound HTTP round-trip metered in IAP credits.

## Role & Dependencies

- **crm_iap_mine** — supplies the `crm.iap.lead.industry/role/seniority` lookup models (provider `reveal_id` codes), the shared `crm.iap.lead.helpers.lead_vals_from_response` mapper, and `_notify_no_more_credit`.
- **iap_crm** — provides the `crm.lead.reveal_id` technical field used for global deduplication of already-acquired companies.
- **iap_mail** — supplies the `iap_mail.enrich_company` template posted on each created lead, plus the no-credit warning mail.
- **website_crm** — provides `website.visitor` (used to skip IP capture when the visitor already produced a lead) and the web-to-lead context.

Capability added on top: a **passive, traffic-driven lead-acquisition pipeline** — IP harvest → rule match → queued reveal view → batched external reveal → lead/opportunity creation + enrichment → credit metering — feeding the parent CRM pipeline.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `crm.reveal.rule` | CRM Lead Generation Rules | 26 | country_ids→res.country, state_ids→res.country.state, website_id→website, industry_tag_ids→crm.iap.lead.industry, preferred_role_id/other_role_ids→crm.iap.lead.role, seniority_id→crm.iap.lead.seniority, team_id→crm.team, user_id→res.users, tag_ids→crm.tag, lead_ids→crm.lead |
| `crm.reveal.view` | CRM Reveal View | 4 | reveal_rule_id→crm.reveal.rule |
| `crm.lead` *(inherit)* | Lead | +3 | reveal_rule_id→crm.reveal.rule (+ reveal_ip, reveal_iap_credits) |
| `ir.http` *(inherit)* | HTTP Routing | 0 | — (overrides `_serve_page`) |

`crm.reveal.rule` is the central configuration aggregate (26 fields, ~19 methods): a **filter-heavy** form whose fields are matching criteria (traffic filter, company filter, contact filter) plus lead-output routing (type, team, user, tags, priority, suffix). `crm.reveal.view` is a lightweight **work queue** — one row per (rule, IP), with a `reveal_state` (to_process / not_found), a `UNIQUE(reveal_rule_id, reveal_ip)` index and a `(reveal_state, create_date)` index for batch selection and aging. The `crm.lead` inherit adds only `reveal_ip`, `reveal_iap_credits`, `reveal_rule_id` (folded into `_merge_get_fields` so they survive merges); the `ir.http` inherit is **inherit-only** with no fields — pure behavior.

## Behavior & Surfaces

- **Routes:** **0** controller routes. There is no web/RPC surface of its own — the inbound trigger is the `ir.http._serve_page` dispatch override on anonymous 200 page views, and the only outbound HTTP is the IAP JSON-RPC reveal call.
- **Inbound capture (code-read):** `_serve_page` resolves the `website.visitor`, and *only if it has no lead yet*, reads GeoIP country/state + remote IP, then `crm.reveal.view._create_reveal_view` matches active rules (cached `_get_active_rules`, regex URL, country/state, website) and bulk-inserts queue rows (`ON CONFLICT DO NOTHING`). A `rule_ids` cookie prevents re-queueing. The block is wrapped in try/except so a page view never crashes.
- **Cron reveal (code-read):** `_process_lead_generation` cleans old views, drops IPs that produced a lead within 6 months (`reveal.lead_month_valid`), then loops in **batches of 25 IPs** — building the IAP payload (`_prepare_iap_payload` / `_get_rules_payload`) and calling `_iap_contact_reveal` → `iap_tools.iap_jsonrpc`. Each returned company becomes a `crm.lead` (`_create_lead_from_response`), its view is unlinked, `not_found` IPs are marked, and `autocommit` commits per batch.
- **Dedup & enrichment (code-read):** a `crm.lead.reveal_id` global check skips companies already in CRM; vals are stamped with `reveal_ip`, `reveal_rule_id`, `referred='Website Visitor'`, `reveal_iap_credits`; each lead gets an `iap_mail.enrich_company` note.
- **Views:** form 2, list 2, search 1 (no kanban/pivot/graph). A configure-the-rule + see-generated-leads UX. **Frontend: none** (0 JS, 0 OWL).
- **Security posture:** **4 access rules, 4 record rules, 0 groups** — reuses crm / sales_team groups; no module-specific group.

## Value-Configuration Classification

**Value model: `network`** (Stabell & Fjeldstad value-network), **activity_class: primary**. The module's core function is **mediation**: it sits between two populations — anonymous website visitors and the external IAP Reveal / Clearbit-D&B identity network — and creates value by **brokering an identity match** between an IP address and a real company, then routing the result into CRM as a lead. The network logic is explicit in the code: passive IP harvesting on every page render (`ir.http._serve_page`), a queue of would-be matches (`crm.reveal.view`), batched calls into the shared external data network keyed by `account_token`, and mediation/dedup so the same company/IP is matched only once. Value scales with the **reach and quality of the external network**, not with any internal transformation. It is **primary** because it directly produces the pipeline input (`crm.lead`) that downstream `sale` (chain) monetizes. **`shop` was considered** (it is a CRM-adjacent acquisition add-on, like the parent `crm` value-shop) but rejected: this module does not run the iterative diagnose/qualify/nurture problem-solving loop itself — it hands the lead to base `crm` for that; its own contribution is the network-mediated IP→company match. `support` was also rejected: a thin opt-in add-on with no routes, but its *business function* is value-creating customer acquisition, not internal enablement.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — specifically **3.1 / 3.5.1 Generate and manage leads**. The `apqc_odoo_map` ties `crm.lead`-centric work to lead generation/qualification; this module is the **lead-generation** upstream of that loop, sourcing leads from website traffic via an external network before scoring/conversion (handled by `crm`) and order capture (handled by `sale`).

## How to Drive It

Use the **run-odoo** skill (`odoo shell`). There are no routes to `curl`:

- `r = env['crm.reveal.rule'].create({'name':'Demo','regex_url':'/','lead_type':'opportunity','contact_filter_type':'role'}); env['crm.reveal.rule']._get_active_rules()` — inspect cached country/URL matching **without** spending credits.
- `env['crm.reveal.rule']._match_url(env['website'].search([],limit=1).id, 'https://x/', 'US', None, [])` — test rule matching for a country/URL.
- `env['ir.config_parameter'].sudo().get_param('reveal.endpoint','https://iap-services.odoo.com')` — the external endpoint actually used.
- `env['iap.account'].get('reveal').account_token` — confirm the reveal credit wallet is configured.
- `env['crm.reveal.view'].search_count([('reveal_state','=','to_process')])` — queued IPs awaiting reveal.
- UI: **Website > Configuration > Lead Generation Rules** to define a `crm.reveal.rule`.

## Open Questions

- **Remote contract (external API):** the result schema and `not_found` / per-IP credit semantics of `/iap/clearbit/1/reveal` — only the client side is in-repo.
- **Real credit cost:** authoritative debit happens server-side on IAP; `reveal_iap_credits` records what the response reports, not a locally computed estimate.
- **Visitor/lead interplay:** how `website.visitor.lead_ids` interacts with reveal dedup when a lead originates from `website_form` vs reveal in the same session.
- **Coverage/privacy:** real-world reveal hit-rate (residential/VPN IPs return `not_found`) and consent considerations are deployment-specific and unverifiable from code.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/website_crm_iap_reveal.facts.json) + `extract_frontend.py` (frontend/website_crm_iap_reveal.frontend.json); behavioral notes from reading `addons/website_crm_iap_reveal/models/{ir_http,crm_reveal_rule,crm_reveal_view,crm_lead}.py`. Odoo 19.0.*
