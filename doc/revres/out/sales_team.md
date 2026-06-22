# sales_team — Reverse-Engineering Brief

The **Sales Teams** module (`sales_team`, category *Sales/Sales*, `application=false`,
`auto_install=false`) is the sales-organization foundation the rest of the sales stack is
built on. It defines the sales team (`crm.team`), its membership (`crm.team.member`), the
salesman/all-documents/manager security tier, a reusable default-team-assignment heuristic,
the Sales dashboard scaffolding, and CRM tags (`crm.tag`). It depends only on `base` and
`mail`, yet sits **upstream of crm, sale and pos**, which all hang their pipelines, orders
and invoices off `crm.team` and inherit its `team_id` scoping. It is foundation, not feature.

## Role & Dependencies
- **base** — core ORM, `res.users` (extended here), `res.company`, `res.currency`, groups/`ir.rule`.
- **mail** — `mail.thread` mixin gives `crm.team` and `crm.team.member` chatter + field tracking.

On top of these it adds: a **sales team** concept with leader + members, an **explicit
membership model** with archive semantics, a centralized **`_get_default_team_id`** helper that
every downstream sales document reuses, a **Sales dashboard** kanban, and the **three-tier sales
security** model (own docs / all docs / manager) other modules key their record rules to.

## Data Model (the ERM)
| _name | _description | #fields | key relations / role |
|-------|--------------|---------|----------------------|
| `crm.team` | Sales Team | 16 | central aggregate; `user_id`→res.users (leader), `member_ids`→res.users, `crm_team_member_ids`→crm.team.member, `company_id`/`currency_id` |
| `crm.team.member` | Sales Team Member | 13 | through-model `crm_team_id`→crm.team + `user_id`→res.users, carries `active` |
| `crm.tag` | CRM Tag | 2 | standalone label (name, color), unique name |
| `res.users` *(inherit)* | Users (extension) | 3 | mixin adds `crm_team_ids`, `crm_team_member_ids`, `sale_team_id` |

`crm.team` is the **central/aggregate** model; `res.users` is the **mixin/extension**
(`_inherit` without `_name`). Field mix is **relational-heavy** (Many2one 7, Many2many 6,
One2many 3 vs Char 6, Boolean 5) — this is an organizational graph (teams↔users↔companies),
not a transactional document. Membership is modelled as a first-class join object precisely so
members can be archived without losing history.

## Behavior & Surfaces
- **Routes:** none (0). No web/RPC surface of its own — purely backend ORM + views.
- **Views:** 4 kanban, 3 form, 3 list, 2 search (no pivot/graph/calendar). The kanban bias
  reflects the **dashboard** focus; one kanban (`crm_team_view_kanban_dashboard`,
  `o_crm_team_kanban`) is the Sales dashboard card with a View/New/Reporting manage menu.
- **Security:** 9 access rules, 2 record rules, 3 groups
  (`group_sale_salesman` → `group_sale_salesman_all_leads` → `group_sale_manager`, chained via
  `implied_ids`). Record rules: `crm_rule_all_salesteam` (all-leads group sees every team) and
  `sale_team_comp_rule` (multi-company). Downstream sales docs add `team_id`-scoped rules **keyed
  to these same groups**, so this tier governs visibility across the whole sales suite.

**Behavior metadata can't show (code-read):**
- *Membership:* `member_ids` is computed from **active** `crm.team.member` rows; the inverse
  creates/(de)activates rows rather than deleting. `sales_team.membership_multi` toggles
  mono/multi-team; in mono mode `_synchronize_memberships` auto-archives a user's competing teams.
- *`_get_default_team_id(user_id, domain)`:* a 5-step, multi-company-aware fallback (my teams
  matching domain → my teams → context default → company teams matching domain → any company
  team) reused by crm/sale/pos default methods to stamp `team_id`. Deliberately not in `default_get`.
- *Dashboard:* `action_primary_channel_button` and `_compute_dashboard_button_name` are
  **skeletons** (return False / placeholder label) overridden by crm & sale to wire the pipeline
  action and KPI counts. `is_favorite`/`favorite_user_ids` decide which teams show on the dashboard.
- *`res.users.sale_team_id`* = the **oldest** active membership (main team); `action_archive`
  cascades to archive memberships; `_check_company_auto` + constraints keep member↔team company aligned.

## Value-Configuration Classification
**Support** (firm infrastructure), **activity_class = support**. Against Stabell & Fjeldstad it is
none of chain/shop/network: it has no document flow, no state machine, no transform/solve/mediate
loop and no value stream of its own (`value_streams = []`). It is a **cross-cutting reference/
foundation** that defines the sales *organization* and security, then is **consumed** by the real
value modules — crm (shop) builds its pipeline on `crm.team`; sale and pos (chain) inherit its
`team_id` scoping and security tiering for their documents.

## APQC PCF Hint
**3.0 Market and Sell Products and Services** — specifically sales-force / sales-organization
*administration* (the team + role + visibility backbone), rather than any concrete 3.5.x selling
activity, which live in the consuming modules (crm/sale).

## How to Drive It
Use the **run-odoo** skill (`odoo shell`); there are no routes to curl.
- `env['crm.team'].search([]).mapped(lambda t: (t.name, t.user_id.name, t.member_ids.mapped('name')))`
- `env['crm.team']._get_default_team_id(user_id=env.uid)` — watch the default-team heuristic resolve.
- `env['res.users'].browse(env.uid).read(['sale_team_id','crm_team_ids'])`
- `env['ir.rule'].search([('model_id.model','=','crm.team')]).mapped(('name','domain_force'))`

## Open Questions
- Exact downstream override of `action_primary_channel_button` / `_compute_dashboard_button_name`
  in crm vs sale (which action and which KPI count each wires).
- How `sale_team_id` (oldest-membership main team) behaves when that earliest membership is archived
  while crm round-robin reassigns the user.
- Whether any consumer uses `crm.tag` outside CRM (it lives here but is named/used chiefly by crm).

*Provenance: facts from `extract_module.py` + `extract_frontend.py`; behavior from code-read of
`addons/sales_team/models/{crm_team,crm_team_member,res_users,crm_tag}.py`. Odoo 19.0.*
