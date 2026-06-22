# crm — Reverse-Engineering Brief

The **crm** module is Odoo's lead and opportunity management application ("Track leads and close opportunities", category *Sales/CRM*). It is an `application: true`, non-`auto_install` module that turns inbound demand (web forms, email aliases, manual entry) into qualified opportunities flowing through a Kanban pipeline toward won/lost outcomes. It sits on `sales_team` (teams/members), `mail` + `calendar` + `phone_validation` (communication & activities), `utm` (source attribution), `contacts` (partners), and `digest` (KPIs). The central record is `crm.lead`, a single model that represents BOTH a lead and an opportunity (a `type` flip), enriched by predictive lead scoring and rule-based assignment. It is the problem-finding/customer-acquisition front-end that hands a won opportunity off to **sale**.

## Role & Dependencies

- **sales_team** — base `crm.team`/`crm.team.member`; crm extends teams with leads/opportunity toggles and assignment.
- **mail** — `crm.lead` mixes in `mail.thread.*` + `mail.activity.mixin`; chatter, email-alias lead creation, activity scheduling.
- **calendar** — opportunities link to `calendar.event` (meetings) via `opportunity_id`; drives next/last-meeting display.
- **utm** — `utm.mixin` adds campaign/medium/source attribution to every lead.
- **phone_validation** — `mail.thread.phone` mixin sanitizes/validates lead phone numbers (dedup key).
- **digest** — adds CRM KPIs (`kpi_crm_lead_created`, `kpi_crm_opportunities_won`) to periodic digests.

Capability added on top: a qualify-and-convert pipeline with predictive scoring, automated lead allocation, deduplication/merge, and lost-reason analytics.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `crm.lead` | Lead | ~75 | partner_id→res.partner, stage_id→crm.stage, team_id→crm.team, lost_reason_id→crm.lost.reason, calendar_event_ids→calendar.event |
| `crm.stage` | CRM Stages | 9 | team_ids→crm.team |
| `crm.team` | Sales Team | 12 | alias_id→mail.alias (extends sales_team) |
| `crm.lost.reason` | Opp. Lost Reason | 3 | — |
| `crm.lead.scoring.frequency` | Lead Scoring Frequency | 5 | team_id→crm.team |
| `crm.activity.report` | CRM Activity Analysis | 20 | lead_id→crm.lead, stage_id→crm.stage |

`crm.lead` is the central aggregate (119 methods, ~75 fields). The module also carries **9 inherit-only extensions** (mixins/extensions with `_inherit` and no `_name`): `res.partner`, `res.users`, `calendar.event`, `crm.team.member`, `digest.digest`, `utm.campaign`, `mail.activity`, `ir.config_parameter`, `res.config.settings` — these graft CRM behavior onto framework models. Conversion wizards (`crm.lead2opportunity.partner[.mass]`, `crm.merge.opportunity`, `crm.lead.lost`, `crm.lead.pls.update`) are transient. Field-type distribution is **relational-heavy** (38 Many2one + 12 Many2many + 2 One2many) with strong attribute/state texture (34 Boolean, 31 Char, 13 Selection, 6 Monetary) — consistent with a record that is both a CRM dossier and a workflow object rather than a transactional document with lines.

## Behavior & Surfaces

- **Routes:** 3 controller routes, all `auth=user`, all `type=http` — `/lead/case_mark_won`, `/lead/case_mark_lost`, `/lead/convert`. A thin backend-action surface (won/lost/convert shortcuts), not a public web API.
- **Views:** form 4, list 5, **kanban 2**, search 5, pivot 2, graph 2, calendar 1, activity 1. The pivot/graph/forecast-heavy mix plus Kanban pipeline signals an analytical, drag-the-card UX over data entry. Frontend adds OWL `CrmPlsTooltip`/`CrmPlsTooltipButton` (score breakdown) and forecast kanban/list/pivot/graph view registrations.
- **Security posture:** 32 access rules, **8 record rules**, 2 groups (`group_use_lead`, `group_use_recurring_revenues`). Record rules scope opportunity visibility by salesperson/team and company.

## Value-Configuration Classification

**Value model: `shop`** (Stabell & Fjeldstad value-shop), **activity_class: primary**. CRM solves the cyclical problem of *finding and acquiring a customer* rather than transforming inputs into outputs. Evidence from the facts/code: the core is an iterative diagnose-qualify-nurture loop — lead capture, predictive scoring (`_pls_get_naive_bayes_probabilities`), stage progression with rotting thresholds, conversion, then won/lost feedback that retrains the scoring-frequency table. Value rests on reputation/relationship and recursive problem-solving, the hallmarks of a shop. A defensible counter-argument is that crm is the value-**chain**'s marketing-and-sell front-end (it precedes and feeds `sale`); but the qualify/nurture recursion and reputation dynamics make **shop** the better fit. It is a primary activity whose won opportunity hands off downstream to `sale` (chain).

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — specifically **3.5.1 Manage leads** and **3.5.2 Manage opportunities** (the apqc_odoo_map ties `crm.lead` qualification to research/qualify tasks, value_model `shop`). The pipeline, scoring and assignment map directly to lead/opportunity management before order capture (3.5.3+) handled by `sale`.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['crm.lead'].search([], limit=5).mapped(('name','type','stage_id.name','probability'))` — inspect pipeline records and their scores.
- `l = env['crm.lead'].create({'name':'Demo','email_from':'a@b.com'}); l.convert_opportunity(l.partner_id); l.type` — observe the lead→opportunity type flip and partner creation.
- `env['crm.stage'].search([('is_won','=',True)]).mapped('name')` — list the won stages that drive `action_set_won`.

Routes (auth=user, http): `curl` `/lead/convert`, `/lead/case_mark_won`, `/lead/case_mark_lost` from an authenticated session to trigger the corresponding backend actions.

## Open Questions

- **PLS retraining cadence (inferred):** how/when `crm.lead.scoring.frequency` is rebuilt — `crm.lead.pls.update` wizard vs scheduled recompute — and which fields participate.
- **Assignment fairness:** real-world behavior of the weighted-random `crm.team._allocate_leads` + round-robin `_assign_and_convert_leads` across overlapping assignment domains under volume.
- **Downstream handoff:** the precise contract from a won opportunity to `sale.order`/`account.move` (e.g. `team_id` propagation), which lives outside crm's static facts.
- **Automation side-effects:** the `crm.ir_cron_crm_lead_assign` cron's dedup/merge (`_merge_opportunity` unlinking duplicates) is not visible in metadata and should be confirmed in code.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/crm.facts.json) + `extract_frontend.py`; behavioral notes from reading `addons/crm/models/{crm_lead,crm_stage,crm_team}.py`. Odoo 19.0.*
