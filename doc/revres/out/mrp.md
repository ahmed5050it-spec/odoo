# mrp — Manufacturing — Architecture Brief

> Odoo 19.0 subsystem brief produced by the code-explorer + code-architect
> workflow. Evidence: `doc/revres/facts/mrp.facts.json` + code-read of
> `addons/mrp/models/`. Record: `doc/revres/metamodel/mrp.metamodel.json`.

## 1. Overview

`mrp` (Manufacturing) is the **transform** subsystem of Odoo's supply chain. It
takes raw-material inputs and, via routed work-center operations, converts them
into finished-goods output — the Operations step between procurement (inbound)
and stock delivery (outbound). Manifest: `name=Manufacturing`,
`category=Supply Chain/Manufacturing`, `application=true`,
`depends=[product, stock, resource]`. The hard dependency on `stock` is the
defining trait: every consume/produce action is a `stock.move`, so MRP is a
behavioral layer on top of inventory, not a standalone ledger. ~31k LOC Python,
26 own models, 27 inherited models, 0 web routes (back-office only).

## 2. Domain Model

Core information concepts (real `_name`s):

- **mrp.bom** / mrp.bom.line / mrp.bom.byproduct — the recipe: what components
  (lines), what co-/byproducts, and which operations build the product. BoMs can
  be `phantom` (kits) for recursive explosion.
- **mrp.routing.workcenter** (Operation) — an operation on a work center, with
  time mode/cost and operation dependencies (`blocked_by_operation_ids`).
- **mrp.workcenter** + mrp.workcenter.capacity / .productivity — the resource
  (inherits `resource.mixin`); productivity logs feed OEE.
- **mrp.production** (Manufacturing Order) — the central document (78 fields,
  161 methods): links a BoM, product qty, raw moves, finished moves and work
  orders.
- **mrp.workorder** — a shop-floor task of an MO at one work center.
- **mrp.unbuild** — reverse operation (disassemble a finished good back to
  components).

Key relations: `mrp.production -> mrp.bom`, `-> product.product`,
`-> stock.move` (move_raw_ids / move_finished_ids), `-> mrp.workorder`;
`mrp.bom -> mrp.bom.line` and `-> mrp.routing.workcenter`;
`mrp.workorder -> mrp.workcenter -> mrp.workcenter.productivity`.

## 3. Behavioral Notes (the metadata gap)

These side-effects are in Python, not derivable from fields (source: code-read):

- **stock.rule._run_manufacture** — the `manufacture` rule (wired on
  `stock.warehouse.manufacture_pull_id`) reacts to a procurement, finds the
  matching BoM (`_get_matching_bom`) and creates an `mrp.production`
  (`_prepare_mo_vals`). This is how a sale order, reordering rule or MTO demand
  auto-spawns a production order.
- **mrp.bom.explode** — recursively resolves phantom sub-BoMs to build the
  component + operation lists that seed an MO.
- **mrp.production.action_confirm** (APQC 4.3.1.7 *release*) — confirms raw and
  finished `stock.move`s, adjusts procure_method, confirms work orders and
  component pickings, runs the scheduler for forecast-short components, and moves
  draft MOs to `confirmed`. This *reserves components via stock*.
- **mrp.production.button_plan / _plan_workorders** — explodes operations into
  work orders, links operation/work-order dependencies, and reserves finite
  work-center capacity (allocates `resource.calendar.leaves` back-to-front),
  setting MO `date_start`/`date_finished`.
- **mrp.production.button_mark_done / _post_inventory** — *consumes raw
  materials and produces finished goods, updating valuation*: raw moves are
  done (decrementing component quants), finished/byproduct moves produced, work-
  order durations finalized, and `_cal_price` assigns manufacturing cost
  (material + work-center cost) to output; MO becomes `done` and locks.
- **work-order time** — button_start/button_finish write
  `mrp.workcenter.productivity` (productive vs. loss buckets) feeding OEE; that
  duration drives the labor-cost portion applied at post-inventory.

## 4. IT Architecture

- **Application:** mrp application component.
- **Software services:** none — no controllers/routes; interaction is ORM +
  back-office views (12 form, 17 list, 8 kanban, plus pivot/graph/calendar).
- **Data objects:** the 9 core models above (+ many `stock.*` / `product.*`
  inherited extensions).
- **Information flows:** depends product/stock/resource; the document chain
  procurement → MO → confirmed (component reservation) → work orders → done
  (consume/produce + valuation) is realized entirely through `stock.move`.

## 5. Business Architecture

- **Capabilities (inferred):** define BoMs (kits/byproducts); define routings,
  work centers & operations; plan/schedule with finite capacity; release &
  execute MOs; execute & track work orders; backorder/split; unbuild;
  manufacturing cost roll-up; BOM/MO overview reporting.
- **Value stream (inferred):** **Plan-to-Produce** — demand → MO created →
  scheduled → released (reserve components) → executed → marked done
  (consume raw, produce finished, value output).
- **Organization (auto):** group_mrp_user, group_mrp_manager, group_mrp_routings,
  group_mrp_byproducts, group_mrp_workorder_dependencies,
  group_mrp_reception_report, group_unlocked_by_default.
- **Policies (inferred):** 9 record rules (multi-company scoping); consumption
  policy flexible/warning/strict (`mrp.consumption.warning`); BoM ready_to_produce;
  warehouse manufacture_steps (1/2/3-step with PBM/SAM locations).
- **Metrics (inferred):** report.mrp.report_mo_overview, report_bom_structure,
  work-center OEE/performance/load, productivity logs.
- **Strategy:** null (human).

## 6. Classification

- **value_model: chain** — Operations transform step of the value chain.
- **activity_class: primary.**
- **apqc_category: 4.3 Produce/Manufacture/Deliver Product**, refs
  **4.3.1.4** schedule production orders & create lots (mrp.production
  create/schedule) and **4.3.1.7** release production orders
  (mrp.production.action_confirm), per `apqc_odoo_map.tsv`.

## 7. Fit-to-Standard

- **Out-of-box:** multi-level BoMs + kits + byproducts; routings & finite
  scheduling; 1/2/3-step manufacturing; reservation & consumption policies;
  backorder/split/scrap/unbuild; lot/serial tracking; cost roll-up into
  valuation; OEE; MO/BoM overview reports.
- **Typical fits:** make-to-stock & make-to-order, kit assembly, shop-floor
  execution, standard cost capture.
- **Common gaps (separate modules / dev):** MPS (mrp_mps), PLM/ECO (mrp_plm),
  subcontracting (mrp_subcontracting), quality (quality_control), advanced APS
  optimization, custom yield/co-product cost-share.
- **Drive hints:** `env['mrp.production'].search([],limit=5).mapped(('name','state'))`;
  create + `action_confirm()` an MO and watch component moves confirm;
  `button_mark_done()` under `sql_db:DEBUG` to trace consume/produce valuation.

## 8. Open Questions

- Full MO state machine (draft→confirmed→progress→to_close→done) and every
  transition trigger.
- Exact `_cal_price` cost split across components, work-center `costs_hour` and
  byproduct `cost_share`.
- How `manufacture_steps` generates intermediate PBM/SAM pickings/locations.
