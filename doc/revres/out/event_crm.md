# event_crm — Reverse-Engineering Brief

The **event_crm** module is Odoo's bridge that auto-generates CRM leads/opportunities from event registrations — it turns attendees into sales leads (category *Marketing/Events*). It is an `auto_install: true`, non-application module that loads whenever both **event** and **crm** are present, grafting a rule-driven lead-generation pipeline onto event registrations. Its reason to exist is mediation: convert the audience an event gathers into qualified CRM pipeline, routed to a sales team/salesperson. The central new record is `event.lead.rule`, a declarative rule deciding HOW (per attendee / per order) and WHEN (at create / confirm / attend) a `crm.lead` is spun out of an `event.registration`, with `event.lead.request` queuing large batch backfills.

## Role & Dependencies

- **event** — supplies `event.event`, `event.registration` (the trigger source) and `event.type` (a rule filter); event groups gate rule access.
- **crm** — supplies `crm.lead` (the output document), plus `crm.team`, `res.users` and `crm.tag` used as lead defaults; the generated lead enters CRM's standard lead→opportunity→won pipeline.

Capability added on top: rule-based, quality-gated, deduplicated conversion of registrations into leads — pure backend automation with **no routes and no frontend**.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `event.lead.rule` | Event Lead Rules | 13 | lead_ids→crm.lead, event_id→event.event, event_type_ids→event.type, lead_sales_team_id→crm.team, lead_user_id→res.users, lead_tag_ids→crm.tag |
| `event.lead.request` | Event Lead Request | 3 | event_id→event.event, event_lead_rule_ids→event.lead.rule |
| `crm.lead` *(ext)* | source provenance | +4 | event_lead_rule_id→event.lead.rule, event_id→event.event, registration_ids→event.registration |
| `event.registration` *(ext)* | lead hooks | +2 | lead_ids→crm.lead |
| `event.event` *(ext)* | leads from event | +2 | lead_ids→crm.lead |
| `event.question.answer` *(ext)* | answers→description | — | — |

Two new models plus four inherit-only extensions (`crm.lead`, `event.registration`, `event.event`, `event.question.answer`). `event.lead.rule` is the configuration aggregate; `crm.lead` is enriched with back-references (`event_lead_rule_id`, `event_id`, `registration_ids`) so every generated lead traces to its source. Field texture is relational-heavy (7 Many2one, 5 Many2many, 2 One2many) with 3 Selections carrying the rule semantics (basis, trigger, lead type).

## Behavior & Surfaces

- **Routes:** none (0). Pure backend automation; rules are configured via standard form/list/search views (1 each).
- **Lead generation (`event.registration.create`/`write`):** `create()` runs `_apply_lead_generation_rules`, which searches `event.lead.rule` for the `create` trigger (plus `confirm` if any reg is open, `done` if any is done) and fires them; `write(state=open|done)` re-fires the matching confirm/done-trigger rules. So attendees become leads at creation, confirmation or attendance — later triggers signal higher intent.
- **Rule engine (`event.lead.rule._run_on_registrations`):** batched `crm.lead.create`. Per-**attendee** basis = one lead per registration (B2C); per-**order** basis = one lead per `(event, create_date)` group (B2B), updating an existing group lead in place rather than re-creating. `_filter_registrations` narrows by stored domain, company match, and event OR event-type match. **All matching active rules fire** — a registration can intentionally yield several leads.
- **Dedup:** before creating, the engine searches existing leads (incl. lost) already linked to those registrations for the same rule and excludes them, so re-triggering (e.g. a status change) never duplicates.
- **Field mapping (`_get_lead_values` / `_get_lead_contact_values`):** stamps type/user/team/tags from the rule; event_id, `referred=event.name`, registration_ids, and first-non-null UTM campaign/source/medium; resolves the contact partner (kept only if email+phone match in single-attendee mode, else raw contact_name/email/phone); names the lead `"<event> - <contact>"` and builds an HTML participant list as description. `crm.lead._merge_dependences` carries registration_ids/event_id/rule across merged opportunities.
- **Batch backfill:** `event.event.action_generate_leads` (Event Manager only) re-generates synchronously under a batch-size threshold, else enqueues `event.lead.request` rows and triggers the daily `ir_cron_generate_leads` cron.
- **Security posture:** 5 access rules, 1 record rule (Event CRM Multi-Company on `event.lead.rule`), 0 new groups. No frontend (0 JS / 0 OWL; only a test-tour asset bundle).

## Value-Configuration Classification

**Value model: `network`** (Stabell & Fjeldstad mediating technology), **activity_class: primary**. event_crm is a bridge whose sole purpose is to mediate between the **event** network (which gathers an attendee audience) and the **crm** shop (which qualifies and converts customers), converting event audience into CRM pipeline. It owns no transformation chain and no standalone problem-solving loop — it is glue whose economic logic is matching/membership: rule-based mediation that turns a registration into a `crm.lead` and routes it onward. It is **primary** because event-driven lead generation is a customer-facing demand activity feeding the sell motion, not back-office support. (One could argue it is merely a CRM extension and thus a shop adjunct, but its dual-population mediating role between two subsystems makes `network` the better fit — matching `website_event`'s bridge classification.)

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — specifically lead generation (~**3.5.1 Manage leads**), inheriting the placement of its **crm** parent (`apqc_odoo_map` ties `crm.lead` qualification to 3.x market-and-sell tasks). The generated `crm.lead` enters the same lead→opportunity→won pipeline, with the won opportunity later handed off to **sale** (chain).

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['event.lead.rule'].search([]).mapped(('name','lead_creation_basis','lead_creation_trigger','event_id.name'))` — inspect configured rules.
- `r = env['event.registration'].create({'event_id': env['event.event'].search([],limit=1).id, 'name':'Demo','email':'a@b.com'}); r.lead_ids.mapped(('name','type'))` — watch a registration spawn a lead.
- `env['crm.lead'].search([('event_lead_rule_id','!=',False)],limit=5).mapped(('name','event_id.name','registration_count'))` — trace leads back to their source event/registrations.
- `env['event.event'].search([],limit=1).action_generate_leads()` — trigger backfill (sync or via the cron).

No routes to `curl` — event_crm is headless automation.

## Open Questions

- **Batch threshold (inferred):** the value of `event.lead.request._REGISTRATIONS_BATCH_SIZE` and how the cron advances its `processed_registration_id` watermark under load.
- **Order grouping with event_sale:** how per-order grouping shifts from the base `(event, create_date)` heuristic to sale-order-based grouping when `event_sale` is installed.
- **Runtime volumes:** generated-lead vs registration counts were not captured (`extract_runtime.sh` not run).
- **Cross-rule dedup:** deduplication is per-rule; behavior against pre-existing non-event CRM leads or across multiple rules is not enforced.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/event_crm.facts.json) + `extract_frontend.py` (frontend/event_crm.frontend.json); behavioral notes from reading `addons/event_crm/models/{event_lead_rule,event_registration,crm_lead,event_event}.py`. Odoo 19.0.*
