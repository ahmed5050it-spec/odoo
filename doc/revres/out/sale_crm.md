# sale_crm — Architecture Brief

> Module: `sale_crm` · Category: Sales/Sales · Depends: `sale`, `crm` · `auto_install: true`
> Value model: **chain** · Activity class: **primary** · APQC: **3.0 Market and Sell Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/sale_crm.facts.json` · Frontend: `doc/revres/frontend/sale_crm.frontend.json`

## 1. Summary

`sale_crm` is the **sale ↔ crm bridge**: it lets a salesperson raise a
**quotation directly from a CRM opportunity** and feeds the resulting order data
back into the pipeline. It owns **one transient model** —
`crm.quotation.partner`, a customer-resolution wizard — and otherwise extends
three models. The load-bearing wire is a single field, `sale.order.opportunity_id`
(→`crm.lead`), plus its inverse `crm.lead.order_ids`. From there it adds: the
**"New Quotation"** button and **Quotations / Orders** stat buttons on the
opportunity form; a `_compute_sale_data` rollup (`quotation_count`,
`sale_order_count`, `sale_amount_total`); an `action_confirm` override that
**raises the opportunity's expected revenue** from a confirmed order; merge
handling so orders survive opportunity de-duplication; and a context-sensitive
**Sales Team dashboard** redirect. Footprint: **1 own model + 3 inherits
(`crm.lead`, `crm.team`, `sale.order`), 0 routes, 1 ACL, ~590 py LOC, 0 JS**. The
substance metadata misses lives in five Python behaviours (confirm→revenue,
the counts compute, the New-Quotation action, the wizard, and merge re-parenting).

## 2. Structure (evidence)

- **Models (1 own + 3 inherit):** `crm.quotation.partner` (TransientModel; fields
  `action` Selection create/exist/nothing, `lead_id`→`crm.lead`, `partner_id`→
  `res.partner`); `crm.lead` (+`order_ids` One2many `sale.order`/`opportunity_id`,
  computed `sale_amount_total` Monetary, `quotation_count` Integer,
  `sale_order_count` Integer); `crm.team` (no new fields — two dashboard method
  overrides); `sale.order` (+`opportunity_id`→`crm.lead`, `check_company=True`,
  `index='btree_not_null'`, domain `type='opportunity'`).
- **Routes:** **0** — backend/ORM only.
- **Security:** 1 ACL (on `crm.quotation.partner`), 0 record rules, 0 new groups.
  The `opportunity_id` field on the sale form is gated by
  `sales_team.group_sale_salesman`.
- **Views:** all via inheritance (counts reported as 0 own views): the
  "New Quotation" button + Quotations/Orders stat buttons on
  `crm.crm_lead_view_form`; `opportunity_id` added after `origin` on
  `sale.view_order_form`; a `sale_action_quotations_new` act_window; a
  "My Quotations" menu under the CRM app. `data/crm_lead_merge_template.xml`
  supplies the lead-merge mail template.

## 3. Frontend (gap #3)

**0 JS / 0 XML templates, no OWL components, no registry adds, no asset bundles.**
Entirely backend/ORM plus static XML view inheritance — the New-Quotation and
stat buttons are plain framework buttons. (Verbatim `frontend_gap3`:
`present:false`, all counts 0.)

## 4. Behavior (beyond metadata)

- **Confirm → bump pipeline revenue (code-read):** `sale.order.action_confirm`
  calls `super()` under a context with `default_tag_ids` stripped (so order tags
  don't leak as CRM defaults), then per order calls
  `opportunity_id._update_revenues_from_so(order)`. That raises the opportunity's
  `expected_revenue` to `order.amount_untaxed` **only** when the current value is
  lower **and** `order.currency_id == opportunity.company_id.currency_id`, logging
  a tracked chatter message. So confirming a quote back-propagates revenue;
  cross-currency orders are silently skipped.
- **Reciprocal counts (code-read):** `crm.lead._compute_sale_data`
  (`@api.depends('order_ids.state','order_ids.currency_id',
  'order_ids.amount_untaxed','order_ids.date_order','order_ids.company_id')`)
  splits `order_ids` by three helpers: `_get_lead_quotation_domain`
  (`state in (draft,sent)`) → `quotation_count`; `_get_lead_sale_order_domain`
  (`state not in (draft,sent,cancel)`) → `sale_order_count` and the basis for
  `sale_amount_total`, which sums each confirmed order's `amount_untaxed`
  **FX-converted** into the lead's `company_currency`. "Quotations" counts open
  quotes; "Orders"/"Sum of Orders" count only confirmed orders.
- **New Quotation action (code-read):** `action_sale_quotations_new` branches —
  **no partner** → opens the `crm.quotation.partner` wizard
  (`sale_crm.crm_quotation_partner_action`); **else** → `action_new_quotation`,
  opening `sale_crm.sale_action_quotations_new` with
  `_prepare_opportunity_quotation_context`: `default_opportunity_id`,
  `default_partner_id`, `default_origin=lead.name`, UTM defaults
  (campaign/medium/source), `default_company_id`, `default_tag_ids`, plus
  `default_team_id`/`default_user_id` when set. The quotation inherits the lead's
  customer, salesperson, team, UTM and tags and is auto-linked via
  `opportunity_id`. Button hidden for `type=='lead'` and inactive zero-probability
  leads.
- **Customer-resolution wizard (code-read):** `crm.quotation.partner.default_get`
  refuses unless `active_model=='crm.lead'` (`UserError`), prefills `partner_id`
  from `lead._find_matching_partner()` (email match, no create) and defaults
  `action` to `exist`/`create`. `action_apply`: `create` →
  `lead._handle_partner_assignment(create_missing=True)`; `exist` → force the
  chosen partner (`create_missing=False`); `nothing` → leave untouched; then
  return `lead.action_new_quotation()`. **NB:** the docstring ("Convert lead to
  opportunity or merge…") is misleading — the wizard only sets/creates the lead's
  `partner_id`, it does **not** convert the lead (confirmed by
  `tests/test_crm_lead_convert_quotation.py`, which asserts the wizard "does not
  create anything, just returns action" beyond the partner).
- **Merge survives orders (code-read):** `crm.lead._merge_get_fields_specific`
  adds `order_ids: lambda fname, leads: [(4, order.id) for order in
  leads.order_ids]`, so merging duplicate opportunities re-parents every linked
  `sale.order` onto the survivor instead of orphaning them.
- **Team dashboard redirect (code-read):** with context `in_sales_app` and
  `team.use_opportunities`, `crm.team._compute_dashboard_button_name` relabels the
  button to "Sales Analysis" and `action_primary_channel_button` returns
  `sale.action_order_report_so_salesteam` instead of the CRM pipeline action — the
  same team card opens the CRM forecast from CRM but the sales-order analysis from
  Sales.
- **Frontend (static, gap #3):** 0 JS / 0 OWL — backend only.

## 5. IT architecture

- **Application:** the sale↔crm bridge — quote from an opportunity and feed
  confirmed-order revenue back to the pipeline.
- **Data objects:** `crm.quotation.partner` (own) + inherits on `crm.lead`,
  `crm.team`, `sale.order`.
- **Key relations:** `sale.order → crm.lead` (`opportunity_id`); `crm.lead →
  sale.order` (`order_ids`, inverse); `crm.quotation.partner → crm.lead`
  (`lead_id`); `crm.quotation.partner → res.partner` (`partner_id`).
- **Flows:** `action_sale_quotations_new` → (wizard if no partner) →
  `action_new_quotation` → prefilled `sale.order`; `action_confirm` →
  `_update_revenues_from_so` → opportunity `expected_revenue` + chatter;
  `_compute_sale_data` → `quotation_count`/`sale_order_count`/`sale_amount_total`;
  lead merge → `order_ids` re-parented; `in_sales_app` → Sales Analysis dashboard.

## 6. Business architecture

- **Capabilities (inferred):** create a quotation from an opportunity (prefilled
  customer/UTM/team/salesperson/tags); resolve or create the quotation customer
  from lead data; link orders back to the source opportunity; roll up quotation
  count, order count and confirmed-order revenue onto the opportunity; feed
  confirmed-order revenue into expected revenue; preserve order links across
  merges; retarget the Sales Team dashboard to sales-order analysis in the Sales
  app.
- **Value streams (inferred):** *Opportunity-to-Quotation* (qualified opportunity
  → New Quotation → partner-resolution wizard → `sale.order` with `opportunity_id`
  + lead context) and *Quote-to-Pipeline feedback* (`action_confirm` →
  `expected_revenue` update + counts/`sale_amount_total` refresh).
- **Information concepts (auto):** `crm.lead` (opportunity), `sale.order`
  (quotation/order), `crm.quotation.partner` (wizard), `crm.team`, `res.partner`.
- **Organization (auto):** `sales_team.group_sale_salesman` (gates
  `opportunity_id` on the sale form).
- **Products (auto):** none (no `product.*` model).
- **Policies (inferred):** quotations counted in draft/sent, orders only when
  confirmed (not draft/sent/cancel); `expected_revenue` only raised and only for
  same-currency orders; New Quotation hidden for leads and inactive
  zero-probability opportunities; quotation tags excluded from CRM defaults on
  confirm; merging re-parents linked orders.
- **Metrics (inferred):** `quotation_count`, `sale_order_count`,
  `sale_amount_total` per opportunity; Sales Analysis by team
  (`sale.action_order_report_so_salesteam`).
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: chain** — the module operates on and advances the **sale order**
  at the Marketing-and-Sell → Sell handoff (Stabell & Fjeldstad *chain*; Porter
  primary *Marketing & Sales*). Its substance is the order-document linkage
  (`opportunity_id`) plus `action_confirm` → `expected_revenue` feedback and the
  reciprocal quote/order counts — advancing the linear quote-to-cash chain, not
  running crm's recursive diagnose/qualify loop (the value-shop, classified under
  `crm`) nor maintaining firm infrastructure.
- **Activity class: primary.**
- **APQC: 3.0 Market and Sell Products and Services** — the sell / manage-sales-
  orders leg (3.5), with New-Quotation-from-opportunity bridging 3.4/3.5.
  **9.0 Financial rejected:** `action_confirm` updates a CRM *forecast* figure
  (`expected_revenue`), not a financial ledger. The bridge inherits its sale
  side's value model (chain); the join point is chain/primary because it
  progresses the sales order. (APQC number matches name: 3.0 = Market and Sell,
  not 9.0 Financial / 13.0 master-data.)

## 8. Fit-to-Standard

- **Standard:** "New Quotation" on the opportunity (with customer-resolution
  wizard); `sale.order` ↔ `crm.lead` linkage with auto-prefill of customer, UTM,
  team, salesperson and tags; Quotations/Orders stat buttons + "Sum of Orders"
  drilling into related orders; confirmed-order revenue feedback into
  `expected_revenue`; order links preserved across opportunity merges; context-
  sensitive Sales Team dashboard (Sales Analysis inside the Sales app); a
  "My Quotations" menu in CRM.
- **Typical fits:** sell straight from the pipeline and keep the order traceable
  to its lead; auto-update opportunity forecast from confirmed orders; carry the
  same salesperson/team/UTM from opportunity to quotation; dedupe opportunities
  without losing their quotations/orders.
- **Common gaps:** `expected_revenue` is only ever **raised** and only for
  **same-currency** orders — multi-currency pipelines or downward revisions need
  customisation; **no automatic stage advance / won-marking** when a linked order
  confirms; `sale_amount_total`/counts are **non-stored** computes (no historical
  snapshot); customer matching is **email-only** (`_find_matching_partner`); no
  portal/website quote-from-lead flow (backend only; gap #3 empty).
- **Drive:**
  `l = env['crm.lead'].search([('type','=','opportunity')], limit=1);
  print(l.quotation_count, l.sale_order_count, l.sale_amount_total)`; then
  `act = l.action_sale_quotations_new()` (wizard vs new-quotation action depending
  on `l.partner_id`); then take a `sale.order` with `opportunity_id`, run
  `so.action_confirm()` and read `so.opportunity_id.expected_revenue` to see the
  pipeline figure move.
