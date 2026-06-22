# uom — Architecture Brief

> Module: `uom` · Category: Sales/Sales · Depends: `base` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **2.0 Develop and Manage Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/uom.facts.json` · Frontend: `doc/revres/frontend/uom.frontend.json`

## 1. Summary

`uom` is the **Units-of-Measure master-data foundation**: a single `uom.uom` model that
defines units and the math to **convert quantities and prices** between them. Every
quantity-bearing module (`product`, `stock`, `sale`, `purchase`, `mrp`, `account`)
converts through it. In **19.0 the model was refactored**: there is **no `uom.category`,
no `factor_inv`, no `uom_type`**. Instead each unit optionally points at a *Reference
Unit* (`relative_uom_id`, a self-referential `_parent_store` tree) and a
`relative_factor` ("Contains") says how many of the reference it holds; the absolute
`factor` is **computed recursively**. A "category" is now just the set of units sharing a
reference-chain root. ~349 py LOC, 0 routes, `auto_install: false` (but a hard dependency
of `product`).

## 2. Structure (evidence)

- **Model (1):** `uom.uom` (9 fields, 16 methods). Key fields: `relative_factor`
  ("Contains", `digits=0`), `relative_uom_id` (Reference Unit; `_parent_name`,
  `_parent_store`), computed stored `factor` ("Absolute Quantity"), computed non-stored
  `rounding`, `related_uom_ids` (inverse), `parent_path`, `active`, `sequence`.
- **Routes:** **0**.
- **Security:** 2 access rules (`base.group_user` read-only; `base.group_system` full
  CRUD) + 1 own group `group_uom` ("Manage Multiple Units of Measure" — a **UI capability
  flag, not a data ACL**). Master data is admin-curated, read-shared system-wide.
- **Views:** 1 form / 1 list / 1 search (Settings ▸ Technical ▸ Units of Measure). **No
  `uom.category` screen** — categories are implicit in the reference tree.

## 3. Frontend (gap #3) & Integrations (gap #7)

**2 JS / 2 XML**, 1 OWL component (`Many2OneUomField`), 2 registry adds
(`fields:many2one_uom`, `fields:many2many_uom_tags`), 0 patches; bundle
`web.assets_backend`=1. `Many2OneUomField` is a specialised many2one widget that renders
a unit inline next to a quantity field — **pure UI sugar** over the master data, no new
screen. Integrations (gap #7): **none** — 0 HTTP call sites, 0 SDK imports, 0 endpoints,
`uses_api_keys: false`. `uom` is self-contained reference data with no external service.

## 4. Behavior (beyond metadata)

- **v19 data model (code-read):** each `uom.uom` optionally references a parent
  (`relative_uom_id`); `relative_factor` = how many of the reference this unit contains;
  `_compute_factor` recursively yields `factor = relative_factor * relative_uom_id.factor`
  (or `relative_factor` at the root). `_check_factor` forces a root unit's
  `relative_factor` to be exactly `1.0` ("Reference unit of measure is missing."), and the
  `_factor_gt_zero` SQL CHECK forbids `relative_factor==0`. The **reference-unit invariant**
  is: every unit's `factor` expresses its size in its category's implicit base unit.
- **Conversion math (code-read):** `_compute_quantity(qty, to_unit, round=True,
  rounding_method='UP', ...)` returns `qty * self.factor / to_unit.factor` — it lifts both
  operands into the shared absolute base and rescales, rounding to `to_unit.rounding`
  (default **UP**). `_compute_price(price, to_unit)` is the **inverse** ratio
  `price * to_unit.factor / self.factor`. **Note:** in 19.0 `_compute_quantity` does **not**
  itself raise on a cross-category mismatch despite the `raise_if_failure` docstring —
  guarding moved to callers and to `_has_common_reference` (which compares `parent_path`
  prefixes).
- **Rounding (code-read):** `rounding` is a **non-stored compute** = `10 ** -precision`
  where `precision = decimal.precision.precision_get('Product Unit')` (seeded to 2). So
  **all units share one system-wide precision** (kept "for compatibility"). Helpers
  `round` / `compare` / `is_zero` delegate to `float_round`/`float_compare`/`float_is_zero`
  at that precision — the supported public arithmetic API.
- **Master-data protection (code-read):** `_filter_protected_uoms` finds seeded units via
  `ir.model.data(module='uom')` minus an allowlist (`product_uom_hour/dozen/pack_6`);
  `_unlink_except_master_data` raises `UserError` ("...cannot be deleted... archive them
  instead"); `_onchange_critical_fields` warns that changing a factor does **not
  retro-convert** stored quantities.

## 5. IT architecture

- **Application:** the reference-unit + conversion-factor master data quantity-bearing
  models convert through.
- **Data objects:** `uom.uom`.
- **Key relations:** `uom.uom → uom.uom` (`relative_uom_id` reference tree;
  `related_uom_ids` inverse); `uom.uom → decimal.precision 'Product Unit'` (shared
  rounding).
- **Flows:** `relative_factor` + `relative_uom_id` → `_compute_factor` → stored absolute
  `factor`; `_compute_quantity`/`_compute_price` expose unit↔unit conversion consumed by
  `product`/`stock`/`sale`/`purchase`/`mrp`/`account`.

## 6. Business architecture

- **Capabilities (inferred):** maintain UoM master data; convert quantities; convert
  prices; shared rounding precision; protect core units; test compatibility via common
  reference.
- **Value streams (inferred):** Define-Unit (reference unit → derived units →
  `_compute_factor`); Convert-Quantity (`qty * A.factor / B.factor`, round UP).
- **Information concepts (auto):** `uom.uom`; the implicit category (shared reference
  root via `parent_path`); `decimal.precision 'Product Unit'`.
- **Organization (auto):** `base.group_system` (curates), `base.group_user` (reads),
  `group_uom` (UI toggle).
- **Policies (inferred):** reference-unit invariant (root factor=1.0); non-zero factor;
  master-data protection (archive-not-delete); safe-edit warning (no retro-conversion);
  single shared rounding.
- **Metrics (inferred):** active vs archived unit count; `'Product Unit'` digits;
  reference-chain depth.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Master-data foundation / firm infrastructure (Stabell &
  Fjeldstad "support"). It owns one tiny model, runs no operational document flow, and
  transforms no demand — it is shared reference data feeding every primary activity. Hence
  not chain/shop/network.
- **APQC: 2.0 Develop and Manage Products and Services.** UoM is part of the
  product/master-data definition layer `product` sits in (the product record carries
  `uom_id`), and `uom` is a build-time dependency of `product`. A **13.0 "Develop and
  Manage Business Capabilities"** (generic reference-data management) reading is defensible,
  but 2.0 is preferred because UoM is specifically **product/quantity** reference data
  tightly coupled to the catalogue. Numbering 2.0 = "Develop and Manage Products and
  Services" matches the name.

## 8. Fit-to-Standard

- **Standard:** reference-unit tree (`relative_uom_id`) with per-unit factors
  (`relative_factor`); computed absolute `factor`; quantity conversion (`_compute_quantity`,
  default round **UP**) and price conversion (`_compute_price`); system-wide rounding via
  `decimal.precision 'Product Unit'` + `round`/`compare`/`is_zero`; common-reference test;
  seeded units (count/time/length/surface/volume/weight) with core-unit protection;
  `group_uom` toggle + inline UoM widgets.
- **Typical fits:** buy in Dozens / stock in Units; packaging multiples (Pack of 6) and
  working time (Days = 8 Hours); tuning the global quantity precision; single-unit
  deployments (leave `group_uom` off).
- **Common gaps:** **no per-unit rounding** any more (all share `'Product Unit'`);
  `_compute_quantity` no longer raises on cross-category conversion (callers must guard);
  changing a factor does not retro-convert stored quantities; categories are implicit
  (no explicit `uom.category` to group/report on).
- **Drive:** `env.ref('uom.product_uom_dozen')._compute_quantity(1, env.ref('uom.product_uom_unit'))`
  (→ 12.0); `env['decimal.precision'].precision_get('Product Unit')`;
  `env.ref('uom.product_uom_day')._has_common_reference(env.ref('uom.product_uom_hour'))` (True).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/uom_uom.py`, `data/uom_data.xml`, `security/uom_security.xml`,
`security/ir.model.access.csv`, `views/uom_uom_views.xml`. Odoo 19.0.*
