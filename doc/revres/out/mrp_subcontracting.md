# mrp_subcontracting — Subcontracted Manufacturing — Architecture Brief

> Odoo 19.0 subsystem brief produced by the code-explorer + code-architect
> workflow. Evidence: `doc/revres/facts/mrp_subcontracting.facts.json` +
> `doc/revres/frontend/mrp_subcontracting.frontend.json` + code-read of
> `addons/mrp_subcontracting/models/`. Record:
> `doc/revres/metamodel/mrp_subcontracting.metamodel.json`.

## 1. Overview

`mrp_subcontracting` is the **outsourced-production** extension of Manufacturing.
A vendor (the *subcontractor*) produces a finished good from components you
supply; the single act of **receiving** that finished good both resupplies the
vendor and records the production. Manifest: `name=MRP Subcontracting`,
`category=Supply Chain/Manufacturing`, `summary=Subcontract Productions`,
`application=false`, `depends=[mrp]`. It is a pure-extension module: ~3.5k LOC
Python, **0 own models, 19 inherited models**, 3 portal routes. The defining
trait is that it adds no new document type — it reuses `mrp.production` and
`stock.move`, wiring them so an inbound receipt auto-creates a backing MO.

## 2. Domain Model

No new `_name`s; key inherited models (real names):

- **mrp.bom** — `+type='subcontract'` and `subcontractor_ids` (Many2many
  res.partner). A subcontract BoM is the recipe used at the vendor.
- **mrp.production** — `+subcontractor_id` (res.partner), `incoming_picking`
  (related), `bom_product_ids`, `move_line_raw_ids`. The backing MO.
- **stock.move** — `+is_subcontract` flag; the receipt move that triggers and
  back-links the MO.
- **stock.warehouse** — `+subcontracting_route_id`, `subcontracting_pull_id`,
  `subcontracting_mto_pull_id`, `subcontracting_type_id`,
  `subcontracting_resupply_type_id`, `subcontracting_to_resupply`.
- **res.partner** — `+property_stock_subcontractor`, `is_subcontractor`,
  `bom_ids`, `production_ids`, `picking_ids`.
- **res.company** `+subcontracting_location_id`; **stock.location**
  `+subcontractor_ids`; **product.supplierinfo** `+is_subcontractor`;
  **stock.quant** `+is_subcontract`.

Key relations: `mrp.bom -> res.partner` (subcontractors); `mrp.production ->
res.partner` (subcontractor_id) and `-> stock.picking` (incoming_picking);
`stock.move(is_subcontract) -> mrp.production` via `move_orig_ids.production_id`.

## 3. Behavioral Notes (the metadata gap)

Side-effects in Python, not derivable from fields (source: code-read unless noted):

- **mrp.bom.type='subcontract' + `_bom_subcontract_find`** — a subcontract BoM
  carries `subcontractor_ids`; `_check_subcontracting_no_operation` forbids
  operations/by-products. `_bom_subcontract_find` matches a (product,
  subcontractor) pair via `('subcontractor_ids','parent_of',subcontractor.ids)`.
- **stock.move._action_confirm -> picking._subcontracted_produce** — an incoming
  move from a supplier location matching a subcontract BoM is flagged
  `is_subcontract`, its source rewritten to the subcontracting location, and a
  backing **mrp.production** is created (`_prepare_subcontract_mo_vals`),
  confirmed, and back-linked (finished `move_dest_ids` -> receipt move).
- **stock.warehouse resupply routes + stock.rule** — MTS/MTO pull rules ship
  supplied components from `lot_stock` to the subcontracting location via the
  internal *Resupply Subcontractor* operation type; `_get_partner_id` stamps the
  vendor; `_should_bypass_reservation` is True for receipt moves (vendor holds
  the stock).
- **stock.picking._action_done -> production.button_mark_done** — validating the
  receipt consumes the components and produces the finished good in the
  subcontracting location, dating production moves before the receipt for
  traceability; `_sync_subcontracting_productions` reconciles MO qty/lots.
- **Subcontracting Portal (static)** — 10 JS files, `mrp_subcontracting.webclient`
  bundle (84 entries), `SubcontractingPortalWebClient`, routes `/my/productions`;
  the vendor records components/lots as a gated portal user.

## 4. IT Architecture

Application component: `mrp_subcontracting`. Software services = 3 portal HTTP
routes (`/my/productions` family). Data objects = the inherited models above.
Information flows: receipt-confirm -> backing MO; warehouse resupply rules ->
component transfer to vendor; receipt-done -> consume/produce + valuation;
component/lot recording (backend wizard or portal) -> MO sync. Frontend: the
portal web client plus backend patches to BoM Overview and `SMLX2ManyField`.

## 5. Business Architecture

- **Capabilities** (inferred): subcontracting BoMs, designate subcontractors,
  auto-create backing MO on receipt, resupply components, record production
  (components/lots), vendor self-service portal, track stock at vendor.
- **Value stream** (inferred): *Outsource-to-Receive* — demand -> resupply
  components -> vendor produces -> receive finished good -> backing MO -> record
  -> validate -> consume/produce/value.
- **Information concepts** (auto): subcontract `mrp.bom`, backing
  `mrp.production`, subcontractor `res.partner`, subcontract `stock.move`/quant.
- **Organization** (auto): no new groups; reuses `group_mrp_user`/`_manager`;
  portal subcontractor gated by `is_subcontractor` + record rules.
- **Policies** (inferred): 13 record rules scope to `subcontractor_id`;
  no-operation constraint; portal writeable-field whitelist; resupply toggle.
- **Strategy**: null (human).

## 6. Classification

- **value_model = chain** — outsourced segment of the Make/manufacturing value
  chain: supplied components are transformed into finished goods, but at the
  vendor; still real raw/finished `stock.move`s + valuation.
- **activity_class = primary**.
- **apqc_category = 4.3 Produce/Manufacture/Deliver Product** (subcontracted
  production) — maps to 4.3.1.4 (backing MO created/scheduled) and 4.3.1.7
  (`action_confirm` release). No work orders / finite scheduling.

## 7. Fit-to-Standard

Out-of-box: subcontract BoMs with vendor partners, automatic back-linked MO on
receipt, component resupply (MTS/MTO routes), lot/serial recording, vendor
portal, stock at a dedicated location, component cost rolled into the received
good, augmented BoM Overview. Typical gaps: purchase/cost flow lives in
`mrp_subcontracting_purchase`; dropship variants in
`mrp_subcontracting_dropshipping`; quality checks in `quality_mrp`; no
work-order execution for the outsourced step; multi-step receipt routes need
config.

## 8. Open Questions

- Split/merge of backing MOs vs receipt lines for partial tracked receipts
  (`_sync_subcontracting_productions`).
- Where the subcontracting *service* cost/valuation is captured (in
  `mrp_subcontracting_purchase`, not here).
- Subcontract returns (`_is_subcontract_return`) and cancellation cascades onto
  the backing production.

*Record: `doc/revres/metamodel/mrp_subcontracting.metamodel.json`. Odoo 19.0.*
