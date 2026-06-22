# Defining Value & Service in Odoo — the Product-Management View

> From a **product-management** role, two questions matter most when you create an offering
> in Odoo:
> 1. **Value** — how is the offering *priced*, what does it *cost*, and how is *margin* (the
>    captured value) defined?
> 2. **Service** — when the offering is *intangible*, how is it *configured, delivered,
>    tracked, and invoiced*?
>
> Both are configured on **`product.template`** (the catalog product) and its sale-side
> extensions. This doc maps the exact fields a PM uses, grounded in
> `addons/product/models/product_template.py` and `addons/sale/models/product_template.py`.
> It also connects to the value-configuration methodology already on this branch
> (`VALUE_CONFIGURATION_METHODOLOGY.md`).

---

## 1. The Product Type — Goods vs Service vs Combo

The first decision a PM makes. `product.template.type`:

```python
type = fields.Selection([
    ('consu',   "Goods"),     # tangible materials / merchandise
    ('service', "Service"),   # non-material product you provide
    ('combo',   "Combo"),     # a bundle / choice of products
], required=True, default='consu')
```

| Type | Meaning | PM uses it for |
|------|---------|----------------|
| **Goods** (`consu`) | Tangible, can be tracked in inventory. | Physical products; enables `stock`, `mrp`, purchasing. |
| **Service** (`service`) | Intangible deliverable. | Consulting, subscriptions, support, hours, fees. |
| **Combo** (`combo`) | A meal-deal/bundle: customer picks among `combo_ids`. | Packages, menus, configurable bundles (`product.combo` / `product.combo.item`). |

> A **Service** is just a `product.template` with `type='service'` — the same record that
> represents goods, so it flows through quotations, orders, and invoices identically. What
> changes is the **delivery & invoicing configuration** (§3).

---

## 2. Defining VALUE — Price, Cost, Margin

Value in Odoo is captured on the product through a **price / cost / margin** triad, plus
contextual pricing.

### 2.1 The core value fields (`product.template`)

| Field | Label | Meaning |
|-------|-------|---------|
| `list_price` | **Sales Price** | The catalog price offered to customers (the *value proposition* number). |
| `standard_price` | **Cost** | Product cost (auto-computed under AVCO/FIFO, or set manually). Used to compute **margin**. |
| `currency_id` / `cost_currency_id` | — | Currencies for price vs cost. |
| `uom_id` | **Unit** | The unit value is expressed in (hours, units, kg…). Critical for services priced per hour/day. |
| `taxes_id` / `supplier_taxes_id` | — | Tax treatment of the value. |

**Margin = `list_price − standard_price`** — the captured value, surfaced on sale order
lines and the *Margin* analysis (the `sale_margin` module). This is the PM's primary
profitability lever.

### 2.2 Contextual value — pricelists

A single `list_price` is rarely enough. **`product.pricelist`** + `product.pricelist.item`
let a PM define value **per segment / quantity / period / currency**:

| Mechanism | Value-management use |
|-----------|----------------------|
| Pricelist rules | Volume discounts, customer-tier pricing, promotional periods. |
| `compute_price` (`fixed`/`percentage`/`formula`) | Markup on cost, discount off list, fixed price. |
| `min_quantity`, `date_start/end` | Quantity breaks and time-boxed pricing. |

So **value is defined at two levels**: the *intrinsic* value (`list_price`/`standard_price`
→ margin) and the *contextual* value (pricelists by who/when/how-much).

### 2.3 Value drivers (link to the methodology)

In `VALUE_CONFIGURATION_METHODOLOGY.md` terms, these fields *are* the value/cost drivers:
- **Cost drivers** (scale, capacity) → `standard_price`, analytic costs, BoM costs.
- **Value drivers** (buyer purchasing criteria, reputation) → `list_price`, pricelists,
  `description_sale`, optional/cross-sell products, ratings.

---

## 3. Defining SERVICE — Delivery, Tracking, Invoicing

When `type='service'`, three extra fields (added by `sale` and friends) define **how the
service creates and captures value**.

### 3.1 `service_tracking` — what to create when the service is ordered

```python
service_tracking = fields.Selection([('no', 'Nothing'), ...], default='no')
```
The base option is `'no'`; modules extend it. With `sale_project` / `sale_timesheet`
installed, a PM gets:

| `service_tracking` | On sale-order confirmation, Odoo… |
|--------------------|-----------------------------------|
| **Nothing** | Just an invoiceable line (e.g. a flat fee). |
| **Create a task** | Spawns a `project.task` in an existing project. |
| **Create a project & task** | Spawns a dedicated `project.project` + task. |
| **Create a project only** | Spawns a project to track the engagement. |

This is how a *sold* service becomes *deliverable work* — the bridge from `sale.order`
to `project` (the **value-shop** logic of the methodology doc).

### 3.2 `service_type` — how delivered quantity is measured

```python
service_type = fields.Selection([('manual', "Manually set quantities on order")], ...)
```
Extended by `sale_timesheet` to add **timesheet tracking**:

| `service_type` | Delivered quantity comes from… |
|----------------|--------------------------------|
| **Manual** | Quantities you type on the order (no analytic tracking). |
| **Timesheets on contract** | Hours logged on the linked project's timesheets. |
| **Milestones** | Completed project milestones (`sale_project`). |

### 3.3 `invoice_policy` — when the value is billed

```python
invoice_policy = fields.Selection([
    ('order',    "Ordered quantities"),     # invoice what was ordered (prepaid)
    ('delivery', "Delivered quantities"),   # invoice what was delivered/done
], tracking=True)
```

| Policy | For services means… | Typical offering |
|--------|---------------------|------------------|
| **Ordered** | Bill up-front on the order (prepaid). | Fixed-price packages, retainers, subscriptions. |
| **Delivered** | Bill what was actually performed (hours, milestones). | Time & materials consulting, support by usage. |

### 3.4 `expense_policy` — re-invoicing costs into the service

```python
expense_policy = fields.Selection([('no','No'), ('cost','At cost'), ('sales_price','Sales price')])
```
Lets a PM pass through validated expenses / vendor bills (travel, subcontracting) onto the
customer invoice — extending the captured value of a service engagement.

### 3.5 The service configuration cheat-sheet

| PM wants… | Set |
|-----------|-----|
| A flat advisory fee | `type=service`, `invoice_policy=order`, `service_tracking=no` |
| Time-and-materials consulting | `type=service`, `service_type=timesheet`, `invoice_policy=delivery`, `service_tracking=create task/project` |
| Fixed-price project with milestones | `type=service`, `service_type=milestones`, `invoice_policy=delivery` |
| Support that re-bills travel | + `expense_policy=cost` (or `sales_price`) |

---

## 4. Structuring the Catalog (PM organization tools)

Beyond a single product, a PM shapes the **offering portfolio**:

| Tool | Model | Product-management use |
|------|-------|------------------------|
| **Categories** | `product.category` | Group offerings; drives reporting, accounting, routing. |
| **Tags** | `product.tag` | Cross-cutting labels (e.g. "premium", "eco"). |
| **Variants** | `product.attribute` → `product.product` | One template, many sellable variants (size/color/plan). |
| **Optional products** | `optional_product_ids` | Cross-sell suggestions at *Add to Cart*. |
| **Combos** | `product.combo` / `product.combo.item` | Bundled offerings / choice menus. |
| **Sales/Purchase descriptions** | `description_sale` / `description_purchase` | The value narrative shown to customers / vendors. |
| **Documents** | `product.document` | Spec sheets, contracts attached to the offering. |

> **Template vs variant:** `product.template` is the *catalog concept* (what the PM
> manages); `product.product` is the *sellable variant* (what's actually ordered/stocked).
> Value (price) is set at the template and adjusted per variant via attribute extra-prices.

---

## 5. The Product-Management Workflow in Odoo

```
1. CREATE the offering
   └─ product.template: name, type (goods/service/combo), category, UoM

2. DEFINE VALUE
   ├─ list_price (what customers pay)         ← value proposition
   ├─ standard_price (cost)                    ← margin = price − cost
   ├─ pricelists (segment/qty/period pricing)  ← contextual value
   └─ taxes, currency

3. IF SERVICE — DEFINE DELIVERY & CAPTURE
   ├─ service_tracking  (create task/project on sale)
   ├─ service_type      (manual / timesheet / milestones)
   ├─ invoice_policy    (ordered=prepaid / delivered=performed)
   └─ expense_policy    (re-invoice costs)

4. STRUCTURE the portfolio
   └─ variants, optional/combo products, tags, descriptions, documents

5. MEASURE
   └─ sales_count, margin analysis, pricelist performance
      (+ the value-configuration drivers from the methodology doc)
```

---

## 6. Mapping to the Value-Configuration Methodology

Tying back to `VALUE_CONFIGURATION_METHODOLOGY.md` — the *type* and *service config* a PM
chooses reflect the firm's value logic:

| Value configuration | Typical product setup |
|---------------------|-----------------------|
| **Value Chain** (transform) | `type=consu` (Goods), `invoice_policy=delivery`, inventory-tracked; value = margin over BoM/standard cost. |
| **Value Shop** (solve) | `type=service`, `service_tracking=create project`, `service_type=timesheet`; value driver = reputation, billed by delivered effort. |
| **Value Network** (mediate) | `type=service` subscriptions/fees, `invoice_policy=order` (recurring); value = network access/usage. |

So "defining value and service" at the product level is the **operational expression** of
the strategic value-configuration choice: the PM encodes *how the firm creates and captures
value* directly in `product.template` fields.

---

## 7. Summary

- **A product = `product.template`**, typed **Goods / Service / Combo**. A *service* is the
  same record with intangible delivery/invoicing config.
- **Value** is defined by the **price/cost/margin** triad (`list_price`, `standard_price`,
  margin) plus **contextual pricing** (`product.pricelist`). Margin is the captured value;
  pricelists tailor value by segment, quantity, and time.
- **Service** is defined by **three levers**: `service_tracking` (what work to create on
  sale), `service_type` (how delivered quantity is measured — manual/timesheet/milestones),
  and `invoice_policy` (ordered=prepaid vs delivered=performed), plus `expense_policy` for
  cost pass-through.
- **Portfolio tools** (categories, variants, optional/combo products, tags, descriptions)
  let the PM shape the whole offering — and the choices map directly onto the firm's
  value-chain / shop / network logic.

In short: a Product Manager defines **value** through pricing & margin, and **service**
through the delivery/tracking/invoicing fields — all on `product.template`, the single
record that carries an offering from catalog to cash.

---

*Source: `addons/product/models/product_template.py` (type, price, cost, UoM, combos),
`addons/sale/models/product_template.py` (service_type, invoice_policy, expense_policy),
`product.pricelist`, `product.category`/`product.tag`/`product.combo`. Cross-references
`VALUE_CONFIGURATION_METHODOLOGY.md`. Odoo 19.0.*
