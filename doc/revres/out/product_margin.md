# product_margin — Architecture Brief

> Module: `product_margin` · Category: Sales/Sales · Depends: `account` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **9.0 Manage Financial Resources** (cost/profitability analysis; 2.0 Products secondary)
> Odoo 19.0 · Facts: `doc/revres/facts/product_margin.facts.json` · Frontend: `doc/revres/frontend/product_margin.frontend.json`

## 1. Summary

`product_margin` is a **read-only product-profitability report computed live from
the accounting ledger**. It adds a *Product Margins…* entry under the Accounting
Reporting menu: a small wizard collects a date range + invoice-state filter, then
re-opens `product.product` in list/form/graph "margin mode", where 17 non-stored
computed fields aggregate posted customer invoices and vendor bills into per-product
KPIs — turnover, average prices, total/expected margin and the gaps between them.
It owns **no business object and stores no results**: **1 TransientModel
(`product.margin`, 3 fields), 1 inherit (`product.product`, +17 compute-only
fields), 0 routes, 1 access rule, ~612 py LOC**. Its entire substance is the
**raw SQL aggregation** over `account.move.line` plus the **margin arithmetic** —
neither visible in metadata.

## 2. Structure (evidence)

- **Models (1 own + 1 inherit):** `product.margin` (`TransientModel`,
  `wizard/product_margin.py` — `from_date`, `to_date`, `invoice_state`, default
  `open_paid`; method `action_open_window`); `product.product`
  (`models/product_product.py` — 17 fields, **all `store=False`**, all
  `compute='_compute_product_margin_fields_values'`; no new column).
- **Routes:** **0** — no web/RPC surface; reached purely via the backend ORM/views.
- **Security:** 1 `ir.model.access` row — `model_product_margin` read/write/create
  (no unlink) to `account.group_account_user`; 0 record rules, 0 groups. The menu
  lives under `account.account_reports_management_menu`.
- **Views:** 2 forms (the wizard form; `view_product_margin_form` — a `product.product`
  *Margins* notebook page with Sales/Purchases/Margins sections), 1 list
  (`view_product_margin_tree` — column **sums** on turnover/sales gap/total cost/
  total margin + progressbar on the two rate fields), 1 graph
  (`view_product_margin_graph` — `total_margin` measure by `product_tmpl_id`).

## 3. Frontend (gap #3)

**None.** `frontend.present = false` — 0 JS, 0 XML templates, 0 OWL components, 0
registry adds. The UI is entirely server-rendered backend views (wizard form +
the three `product.product` margin views); the `progressbar` and `graph` widgets
are stock web widgets, not module assets.

## 4. Behavior (beyond metadata)

- **Raw-SQL aggregation (code-read):** `product.product._compute_product_margin_fields_values`
  runs **one parametrised SQL statement twice** — `('out_invoice','out_refund')`
  for sales, then `('in_invoice','in_refund')` for purchases — over
  `account_move_line l JOIN account_move i JOIN product_product JOIN product_template pt`,
  inside a `MATERIALIZED currency_rate` CTE (`res.currency._select_companies_rates()`)
  that normalises every line to company currency. Refunds are netted by a
  `CASE move_type IN ('out_invoice','in_invoice') THEN 1 ELSE -1` sign. Per product
  it yields `avg_unit_price` (→ `sale_/purchase_avg_price`), `num_qty`
  (→ `*_num_invoiced`), signed `-balance` total (→ `turnover` / `total_cost`), and
  `SUM(qty*pt.list_price*sign)` (→ `sale_expected`). The `invoice_state` context key
  selects the `(state, payment_state)` sets (`paid` / `open_paid` /
  `draft_open_paid`); `invoice_date BETWEEN date_from AND date_to`, `company_id` and
  `display_type='product'` scope the rest.
- **Margin formulas — the metadata gap (code-read):** after the SQL, Python derives
  the headline KPIs: `normal_cost = standard_price * purchase_num_invoiced`;
  `sales_gap = sale_expected − turnover`; `purchase_gap = normal_cost − total_cost`;
  `total_margin = turnover − total_cost`; `expected_margin = sale_expected −
  normal_cost`; `total_margin_rate = total_margin*100/turnover`;
  `expected_margin_rate = expected_margin*100/sale_expected` (both /0-guarded). So
  **"expected" = theoretical** (catalog `list_price` × cost `standard_price`) and
  **"total/turnover" = realised** (what invoices booked); the report's whole point
  is the gap — pure arithmetic the schema can't show.
- **Wizard → contextual report (code-read):** `product.margin.action_open_window`
  (`ensure_one`) looks up the product search view + the three `product_margin.*`
  views by xml_id, copies the context with `create=False/edit=False`, injects
  `date_from`, `date_to`, `invoice_state`, and returns an `act_window` on
  `product.product` (`list,form,graph`). Those keys are exactly what the compute
  reads — the wizard is a **parameter form that re-launches `product.product` in
  margin mode**; there is no result table.
- **Non-stored group-sum shim (code-read):** because the 17 fields are `store=False`,
  the SQL layer can't `SUM` them. `_SPECIAL_SUM_AGGREGATES` flags the 13 numeric
  `'<field>:sum'` specs; `_read_group_select` returns `SQL("NULL")` for them, then
  `_read_group`/`_read_grouping_sets` fetch the matching records (`id:recordset`),
  force-compute via `self._fields['turnover'].compute_value(all_records)` to bypass
  `PREFETCH_MAX`, and replace each NULL with `sum(records.mapped(field))`. This is
  how the list `sum=` columns and the graph measure total fields that have no column.
- **External integration (static, gap #7):** none — 0 HTTP call sites, no SDKs, no
  API keys. The only data source is the local `account.*` ledger.

## 5. IT architecture

- **Application:** analytical margin-reporting overlay on `account` invoices.
- **Data objects:** `product.margin` (wizard), `product.product` (computed fields).
- **Key relations:** `product.product → account.move.line` (raw SQL on `product_id`)
  `→ account.move` (state/payment_state/move_type/date/company filters);
  `→ product.template` (`list_price`); `account.move → res.currency` (rate CTE).
- **Flows:** wizard `product.margin` → `action_open_window` injects
  `date_from/date_to/invoice_state` → `product.product` views →
  `_compute_product_margin_fields_values` fires SQL twice → 17 KPIs; list-sum /
  graph-measure → `_read_group` Python shim. No routes, no outbound calls, no
  persisted results.

## 6. Business architecture

- **Capabilities (inferred):** compute product sale/purchase margins from invoices;
  compare realised vs expected (catalog/standard-cost) margin; parameterise by
  date + invoice state; quantify sales/purchase gaps; visualise via list-sum/graph.
- **Value streams (inferred):** *Analyse-Margin* — pick period + invoice state →
  aggregate invoice/bill lines per product → derive turnover, costs, expected vs
  realised margins/rates → present (list/form/graph) for decision-making.
- **Information concepts (auto):** `product.product`, `product.template`
  (`list_price`), `account.move.line`, `account.move`, `res.currency`.
- **Organization (auto):** `account.group_account_user` (only group with access).
- **Products (auto):** `product.product`, `product.template`.
- **Policies (inferred):** `invoice_state` → included `(state, payment_state)` sets;
  expected (catalog/standard-cost) vs realised (invoiced); `env.company`/`force_company`
  scoping with currency normalisation; only `display_type='product'` lines, refunds
  netted.
- **Metrics (inferred):** turnover, total_cost, sale_expected, normal_cost,
  total_margin, expected_margin, total/expected margin **rate %**, sales_gap,
  purchase_gap, avg sale/purchase price, sale/purchase qty invoiced.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: support** — a read-only management-accounting overlay. It creates
  no business object (`product.margin` is a throwaway parameter form) and stores
  nothing; it just aggregates existing `account.move.line` into KPIs. That is
  firm-infrastructure **support** (Stabell & Fjeldstad / Porter management-accounting),
  feeding decisions in the primary chain rather than performing them.
- **Activity class: support.**
- **APQC: 9.0 Manage Financial Resources** — the work is product
  **profitability / cost-and-margin analysis** computed entirely off posted invoices
  and standard cost, gated to `account.group_account_user` under the Accounting
  Reporting menu (8.x management/cost accounting). **2.0 Develop & Manage Products**
  was weighed (manifest category *Sales/Sales*; the subject is the product) but the
  module measures margin, it does not develop/price/manage products — so 2.0 is at
  most secondary.

## 8. Fit-to-Standard

- **Standard:** per-product margin from posted invoices/bills; configurable
  date + invoice-state scope; realised vs expected KPIs and gaps; multi-currency
  normalisation + multi-company scoping; list-sum / KPI form / margin graph.
- **Typical fits:** quick profitability review off the ledger without a BI tool;
  spotting realised-vs-catalog margin divergence; period checks via the wizard dates.
- **Common gaps:** invoice-based only (no `sale.order`/`purchase.order`/POS/stock-
  valuation, no unbilled); expected margin uses *current* `standard_price`/`list_price`
  (no historical layering); no landed costs/analytic dimension; non-stored fields
  can't feed arbitrary BI pivots (only the built-in list-sum/graph via the read-group
  shim); single company-currency conversion.
- **Drive:** `env['product.product'].browse(id).with_context(date_from='2024-01-01',
  date_to='2024-12-31', invoice_state='open_paid').mapped(('turnover','total_cost',
  'total_margin','expected_margin'))`; `env['product.margin'].create({'invoice_state':
  'open_paid'}).action_open_window()['context']`; Accounting ▸ Reporting ▸
  *Product Margins…*.
