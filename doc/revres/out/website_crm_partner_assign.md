# website_crm_partner_assign — Reverse-Engineering Brief

The **website_crm_partner_assign** module ("Resellers", category *Website/Website*) is Odoo's **partner-program mediation layer**: it publishes a vendor's resellers/partners on a public directory and routes incoming leads/opportunities to them. It is `application: false`, non-`auto_install`, and sits on `crm` (the lead/opportunity it forwards), `partnership` (the `res.partner.grade` "Level"), `account` (invoiced turnover for channel reporting), `base_geolocalize` (GPS matching), `website_partner` + `website_google_map` (the published directory and its map), and `portal` (the reseller self-service pages). Rather than transforming inputs (chain) or solving one client's problem (shop), it **intermediates** — connecting customers to a network of third-party resellers and those resellers back to the vendor.

## Role & Dependencies

- **crm** — provides `crm.lead`; this module extends it with `partner_assigned_id`, `partner_declined_ids`, geo coordinates and the forward/portal behaviour.
- **partnership** — owns `res.partner.grade` (Partner Level) and `res.partner.grade_id`; this module adds `partner_weight` + publishability on top.
- **account** — `account.invoice.report` feeds the `crm.partner.report.assign` turnover column (channel KPI).
- **base_geolocalize** — `res.partner._geo_localize` turns lead/partner addresses into latitude/longitude for spatial matching.
- **website_partner / website_google_map** — supply the published-partner page machinery and the Google-Maps reseller map.
- **portal** — graded partners log in as portal users to accept/decline and manage forwarded leads.

Capability added on top: publish + rank resellers, geo-match and weighted-distribute leads to them, and let partners self-serve their pipeline.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `crm.lead.forward.to.partner` | Lead forward to partner (wizard) | 4 | partner_id→res.partner, assignation_lines→crm.lead.assignation |
| `crm.lead.assignation` | Lead Assignation (wizard line) | 6 | lead_id→crm.lead, partner_assigned_id→res.partner |
| `crm.partner.report.assign` | CRM Partnership Analysis (`_auto=False`) | 10 | partner_id→res.partner, grade_id→res.partner.grade, activation→res.partner.activation |
| `res.partner.activation` | Partner Activation | 3 | — |
| `res.partner.grade` | Partner Level (+ `website.published.mixin`) | 1 | adds `partner_weight` |

Plus three **inherit-only extensions** (no `_name`): `crm.lead` (+5 fields: `partner_assigned_id`, `partner_declined_ids`, `partner_latitude/longitude`, `date_partner_assign`), `res.partner` (+9 fields: `partner_weight`, `grade_sequence`, `activation`, partnership/review dates, `assigned_partner_id`/`implemented_partner_ids`), and `website` (one `/partners` suggested controller). The relational core is **lead ↔ partner**: a lead carries an *assigned* partner and a set of *declined* partners, and a partner carries a level (`grade_id`) whose `partner_weight` drives both directory rank and assignment contention.

## Behavior & Surfaces

- **Routes (6 controllers):** portal `auth=user` — `/my/leads`, `/my/opportunities`, `/my/lead/<lead>`, `/my/opportunity/<opp>` (the reseller's own pipeline); public `auth=public` — `/partners` (+ `/grade/<grade>`, `/country/<country>`, paged, sitemapped) and `partners_detail` (`/partners/<partner>`). The public pair is the mediating directory; the `/my/*` pair is the reseller workspace.
- **Geographic assignment (code-read):** `assign_partner` → `assign_geo_localize` (address → lat/long) → `search_geo_partner`, a cascade of widening same-country bounding boxes, then all-in-country, then a raw-SQL nearest-neighbour fallback. Candidates need `partner_weight>0` and must not be in `partner_declined_ids`; the winner is `random.choices` weighted by `partner_weight`.
- **Forward + portal (code-read):** `crm.lead.forward.to.partner.action_forward` emails resellers a portal deep-link and stamps `partner_assigned_id`. On the portal, `partner_interested` → `convert_opportunity`, `partner_desinterested` → clears assignment + adds to `partner_declined_ids`, `create_opp_portal` lets a graded partner self-create an opportunity. All portal writes pass `_assert_portal_write_access`.
- **Views & security:** form 7, list 1, search 1 (no kanban/pivot/graph — analytics live in the SQL report). 11 access rules, **4 record rules**, 0 new groups; record rules scope a portal partner to leads `child_of` its commercial partner and gate public/portal reads to `website_published` grades.

## Value-Configuration Classification

**Value model: `network`** (Stabell & Fjeldstad value-network), **activity_class: primary**. The module's reason to exist is **mediation**: a published partner directory that lets customers and resellers find each other, geo-spatial matching of a lead to the nearest eligible partner, and weighted distribution where a partner's *level* (`grade`/`partner_weight`) sets its share of the routed flow. Value scales with the **size and quality of the partner network** and with the intermediation infrastructure (directory, forward wizard, partner portal), not with input transformation (chain) or recursive problem-solving for one client (shop). It deliberately does not own the sell — `crm` (shop) qualifies the lead and `sale` (chain) fulfils it; this module sits between them, routing demand to third parties and measuring the channel.

## APQC PCF Hint

**3.0 Market and Sell Products and Services**, specifically the **3.x channel / partner-management** band (manage the partner program, distribute leads to channel partners, analyse channel performance). It is upstream of order capture: a forwarded lead the partner accepts becomes a partner **opportunity** (handed back into `crm`/`sale`), and `crm.partner.report.assign` ties forwarded opportunities to invoiced turnover per reseller — the channel KPI for 3.0.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['res.partner.grade'].search([]).mapped(('name','partner_weight','website_published'))` — inspect partner levels, their assignment weight and publication state.
- `l = env['crm.lead'].search([('country_id','!=',False)], limit=1); l.assign_partner(); l.partner_assigned_id.display_name` — run the geo + weighted match and see who won.
- `env['crm.partner.report.assign'].read_group([], ['nbr_opportunities','turnover'], ['grade_id'])` — the channel scorecard by level.

Public route: `curl http://localhost:8069/partners` (auth=public) renders the reseller directory; `/partners/grade/<id>` and `/partners/country/<id>` filter it.

## Open Questions

- **Geocoding provider (inferred):** which backend `base_geolocalize` uses at runtime (Nominatim vs Google) and whether a Google Maps API key is set for the directory map — `uses_api_keys` is true but no endpoint/key is hard-coded here.
- **Assignment fairness:** real-world behaviour of weighted-random geo assignment under volume and overlapping territories; no capacity cap is enforced in code, so a high-weight partner can dominate.
- **Program lifecycle automation:** what (if anything) drives `date_review_next` / `activation` transitions — no cron for this was found in the module.
- **Cron interplay:** how the base CRM lead-assignment cron (`crm.ir_cron_crm_lead_assign`) interacts with this module's partner-assignment path.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/website_crm_partner_assign.facts.json) + `extract_frontend.py`; behavioral notes from reading `addons/website_crm_partner_assign/{models/crm_lead.py,models/res_partner.py,report/crm_partner_report.py,controllers/main.py,wizard/crm_forward_to_partner.py,models/res_partner_grade.py}`. Odoo 19.0.*
