# partnership — Architecture Brief

> Module: `partnership` · Category: Sales/CRM · Depends: `crm`, `sale` · `auto_install: false`
> Value model: **chain** · Activity class: **primary** · APQC: **3.0 Market and Sell Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/partnership.facts.json` · Frontend: `doc/revres/frontend/partnership.frontend.json`

## 1. Summary

`partnership` is a **membership / partner-grade program** layered onto Sales. It
owns one model — `res.partner.grade` (a partner *level*: Gold / Silver / Bronze by
default) — and otherwise extends the order chain. Its defining act: when a
`sale.order` carrying a **"Membership / Partnership"** service product is
**confirmed**, the buying customer's *commercial* partner is automatically
**promoted to that product's grade**, and grading the partner in turn grants the
grade's **default pricelist**. So selling a membership both monetises affiliation
and **tiers the customer's pricing** in one document flow. Footprint: **1 own
model + 6 inherits (`res.partner`, `sale.order`, `product.template`,
`product.pricelist`, `res.company`, `res.config.settings`), 0 routes, 4 ACLs,
~265 py LOC, 0 JS**. The substance metadata misses lives in two Python
side-effects (confirm→grade, grade→pricelist) and a single-grade-per-order
constraint.

## 2. Structure (evidence)

- **Models (1 own + 6 inherit):** `res.partner.grade` (7 fields: `sequence`,
  `active`, `name` "Level Name", `company_id`, `default_pricelist_id`→
  `product.pricelist`, computed `partners_count`, `partners_label` related to
  `company.partnership_label`); `res.partner` (+`grade_id` "Partner Level",
  tracked); `sale.order` (+computed `assigned_grade_id`); `product.template`
  (+`service_tracking` option `'partnership'` and `grade_id` "Assigned Level");
  `product.pricelist` (+`partners_count`, `partners_label`); `res.company`
  (+`partnership_label` Char, default "Members"); `res.config.settings`
  (+`partnership_label` related).
- **Routes:** **0** — backend/ORM only, no web or RPC surface.
- **Security:** 4 ACLs, all on `res.partner.grade` — read for `base.group_user`;
  full CRUD for `base.group_system` and `sales_team.group_sale_manager`;
  create/read/write (no unlink) for `sales_team.group_sale_salesman`. 0 record
  rules, 0 new groups. Grades are managed under **CRM > Configuration**.
- **Views:** `res.partner.grade` form / list / search + a stat button
  (`partners_count` / `partners_label`) drilling into the level's members; inline
  extensions add `grade_id` to `res.partner`, the `'partnership'` tracking +
  `grade_id` to `product.template`, `partners_count` to `product.pricelist`, and
  `partnership_label` to Settings. The CRM config menu `crm_menu_partners` is
  labelled from `company.partnership_label`.

## 3. Frontend (gap #3)

**0 JS / 0 XML templates, no OWL components, no registry adds, no asset bundles.**
The module is entirely backend/ORM: its UI is plain XML views and a stat button.
There is no client-side widget, service, or patch — nothing in `web.assets_*`.
(Verbatim `frontend_gap3`: `present:false`, all counts 0.)

## 4. Behavior (beyond metadata)

- **Confirm → grade the customer (code-read):** `sale.order.action_confirm`
  calls `super()` then `_add_partnership`, which for each order with a non-empty
  `assigned_grade_id` writes `partner_id.commercial_partner_id.grade_id =
  assigned_grade_id`. The grade lands on the **commercial (top-level) partner**,
  not necessarily the order's contact. `assigned_grade_id` is computed by
  `_compute_partnership` (`@api.depends('order_line.product_id')`): it filters
  lines where `service_tracking == 'partnership'` and takes the first
  `product_id.grade_id`, so a non-partnership order is a no-op.
- **Grade → pricelist (code-read):** `res.partner.write` intercepts a `grade_id`
  change; if the grade has a `default_pricelist_id` it injects
  `vals['specific_property_product_pricelist'] = grade.default_pricelist_id.id`
  **before** `super().write` — so grading a partner (via the confirm flow above
  *or* a manual edit) silently re-points its specific pricelist. Setting a
  conflicting pricelist in the same write raises
  `UserError("...two different pricelists (one directly and one from grade ...)")`.
  The full chain is proven by `tests/test_partnership.test_sell_basic_partnership`:
  after confirm, `partner.grade_id == product.grade_id` **and**
  `partner.specific_property_product_pricelist == grade.default_pricelist_id`.
- **One grade per order (code-read):** `_constraint_unique_assigned_grade`
  (`@api.constrains('order_line')`) raises `ValidationError` if the order's line
  products reference more than one distinct `grade_id`, guaranteeing an
  unambiguous grade before `_add_partnership` runs
  (test `test_constrains_uniqueness_partnership_grade`).
- **Product flagging + counters (code-read):** `product.template` adds the
  Selection value `('partnership','Membership / Partnership')` (ondelete set
  default) and overrides `_get_saleable_tracking_types()` to append
  `'partnership'` so membership products pass the saleable-product domain
  (test `test_partnership_product_domain`). `sale.order.line.service_tracking` is
  a related on `product_id.service_tracking`, which is how partnership lines are
  detected. `res.partner.grade._compute_partners_count` and
  `product.pricelist._compute_partners_count` each `_read_group` `res.partner`
  (by `grade_id`, and by `specific_property_product_pricelist`) to count
  affiliates; `res.config.settings._onchange_partnership_label` live-renames the
  `partnership.crm_menu_partners` menu.
- **Frontend (static, gap #3):** 0 JS / 0 OWL — backend only.

## 5. IT architecture

- **Application:** membership / partner-grade program — selling a "Membership /
  Partnership" product on a confirmed `sale.order` grades the customer and grants
  a grade-based pricelist.
- **Data objects:** `res.partner.grade` (own) + inherits on `res.partner`,
  `sale.order`, `product.template`, `product.pricelist`, `res.company`,
  `res.config.settings`.
- **Key relations:** `res.partner.grade → product.pricelist`
  (`default_pricelist_id`); `res.partner → res.partner.grade` (`grade_id`);
  `product.template → res.partner.grade` (level a product confers);
  `sale.order → res.partner.grade` (`assigned_grade_id`); `sale.order →
  res.partner` (confirm writes the commercial partner's grade); `res.partner →
  product.pricelist` (forced specific pricelist).
- **Flows:** `action_confirm` → `_add_partnership` → partner `grade_id`;
  `res.partner.write(grade_id)` → `specific_property_product_pricelist`;
  single-grade-per-order constraint; `partnership_label` relabels the CRM menu and
  grade/pricelist counters.

## 6. Business architecture

- **Capabilities (inferred):** define partner levels (each optionally tied to a
  pricelist); sell a membership product that confers a grade; auto-assign the
  grade on order confirm; grant a grade-based pricelist (with conflict guard);
  count/drill into members per grade and per pricelist; relabel the affiliate
  vocabulary per company.
- **Value streams (inferred):** *Sell-Membership-to-Grade* (quote with a
  `'partnership'` product → `action_confirm` → `_add_partnership` → commercial
  partner graded → grade pricelist applied) and *Configure-Program* (create
  grades + default pricelist, flag products `service_tracking='partnership'` with
  a `grade_id`, set `partnership_label`).
- **Information concepts (auto):** `res.partner.grade`, `res.partner` (graded
  member), `sale.order` (membership-selling document), `product.template`
  (membership product), `product.pricelist`.
- **Organization (auto):** `base.group_user`, `base.group_system`,
  `sales_team.group_sale_manager`, `sales_team.group_sale_salesman`.
- **Products (auto):** `product.template` with `service_tracking='partnership'`
  and a `grade_id`.
- **Policies (inferred):** one grade per order; grading forces the grade pricelist
  and rejects conflicts; the grade lands on the commercial partner; applied only
  on confirm.
- **Metrics (inferred):** members per grade; members per pricelist.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: chain** — the module rides the **Quote-to-Cash** order document
  (Stabell & Fjeldstad *chain*; Porter primary *Marketing & Sales*). Its core
  effect is a **sale-document side-effect**: `sale.order.action_confirm` →
  `_add_partnership` monetises membership and tiers the customer, rather than
  passively maintaining master data as firm infrastructure.
- **Activity class: primary.**
- **APQC: 3.0 Market and Sell Products and Services** — the trigger is *selling*
  a membership/partnership product through the order pipeline (`depends crm+sale`;
  grade ACLs keyed to the `sales_team` salesperson/manager groups; the grade UI
  hangs under CRM Configuration). **Not** *support* / 13.0 master-data management:
  although the end artefact (partner grade + pricelist) *is* partner master data,
  `partnership` **generates** it as the outcome of a confirmed sale, not as a
  governance utility. 9.0 (Customer Service) and 11.0/13.0 were rejected — no
  service-request, finance, or pure data-governance object exists; the substance
  is sell-the-membership-then-grade-and-price-the-customer.

## 8. Fit-to-Standard

- **Standard:** partner levels (`res.partner.grade`) with sequence, per-company
  scope and an optional default pricelist; a `service_tracking='partnership'`
  membership product carrying the grade it confers; auto grade assignment to the
  commercial partner on confirm; auto grade-pricelist with conflict guard;
  single-grade-per-order constraint; members-per-grade / per-pricelist counters
  with drill-through; configurable affiliate label (Members / Partners / Alumni).
- **Typical fits:** sell a yearly membership SKU and auto-promote the buyer to
  Gold/Silver/Bronze; grant tiered pricelists purely by selling the right product;
  rename the affiliate concept per organisation (association "Members" vs reseller
  "Partners").
- **Common gaps:** **no grade expiry / renewal / downgrade** (grade and pricelist
  persist until manually changed); **no revocation** — cancelling/refunding the
  order does not remove the grade or pricelist; `assigned_grade_id` is computed /
  non-stored, so there is no record of *which* order conferred a grade beyond
  `grade_id` tracking; **no portal/website purchase flow** (backend `sale.order`
  only; gap #3 empty); one grade per order with first-match selection — stacked or
  multi-tier memberships need customisation.
- **Drive:**
  `env['res.partner.grade'].search([]).mapped(lambda g:(g.name,g.default_pricelist_id.display_name,g.partners_count))`;
  build a `service_tracking='partnership'` product with `grade_id`, put it on a
  `sale.order`, read `so.assigned_grade_id`, then `so.action_confirm()` and read
  `so.partner_id.commercial_partner_id.grade_id` and
  `…​.specific_property_product_pricelist` to see the grade + pricelist applied.
