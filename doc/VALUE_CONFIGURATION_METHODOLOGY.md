# Implementing the Value-Configuration Methodology in Odoo

> **Source paper:** Charles B. Stabell & Øystein D. Fjeldstad, *"Configuring Value for
> Competitive Advantage: On Chains, Shops, and Networks"*, **Strategic Management Journal
> 19(5): 413–437 (1998)**.
>
> The paper generalizes Porter's **value chain** into **three** generic *value
> configuration models* — **Chain, Shop, Network** — each rooted in one of Thompson's
> (1967) technologies. This document explains the methodology and shows **how to implement
> it in Odoo**: classify a business, model its primary activities, wire the cost/value
> drivers, and build a reusable *value-configuration analysis* capability on the Odoo
> metadata + automation foundation documented earlier in this branch.

---

## 1. The Methodology (distilled from the PDF)

A firm's value-creation **logic** is one of three "technologies" (Thompson 1967). Each has
its own primary-activity set, interdependence pattern, and drivers — summarized in the
paper's **Table 1**:

| Dimension | **Value Chain** | **Value Shop** | **Value Network** |
|-----------|-----------------|----------------|-------------------|
| **Technology** | Long-linked | Intensive | Mediating |
| **Value-creation logic** | Transform **inputs → products** | Resolve **unique customer problems** | Enable **exchanges between customers** |
| **Primary activities** | Inbound logistics · Operations · Outbound logistics · Marketing & sales · Service | Problem-finding & acquisition · Problem-solving · Choice · Execution · Control/evaluation | Network promotion & contract mgmt · Service provisioning · Infrastructure operation |
| **Interactivity logic** | **Sequential** | **Cyclical, spiralling** | **Simultaneous, parallel** |
| **Activity interdependence** | Pooled & Sequential | Pooled & Sequential & **Reciprocal** | Pooled & **Reciprocal** |
| **Key cost drivers** | Scale · Capacity utilization | (per-engagement) | Scale · Capacity utilization |
| **Key value drivers** | Buyer purchasing criteria | **Reputation** | Scale · Capacity utilization (network size) |
| **Business value system** | Interlinked chains | Referred shops | Layered & interconnected networks |
| **Typical firms** | Manufacturing, distribution | Consulting, medicine, law, engineering, R&D | Banks, telecom, insurance, marketplaces |

**Method (value configuration analysis):** to diagnose competitive advantage you
(1) identify which configuration a firm/unit *is*, (2) lay out its primary activities,
(3) analyze cost & value drivers per activity, and (4) choose strategic positioning within
that configuration's logic.

---

## 2. Why This Maps to Odoo

Odoo is a multi-app ERP, and **its apps already embody all three logics**. Implementing
the methodology means recognizing which Odoo modules realize which configuration, then
modelling the primary activities as Odoo processes (the `base.automation` EPC /
`mail.activity` machinery from the earlier docs).

```
   VALUE CHAIN  ───────────  VALUE SHOP  ───────────  VALUE NETWORK
   (transform)               (solve)                  (mediate)
        │                        │                         │
   purchase→mrp→stock→       project / helpdesk /      payment / website /
   →sale→delivery→invoice    consulting (timesheet)    marketplace / subscription
```

---

## 3. Mapping Each Configuration to Odoo Modules

### 3.1 Value Chain → the make-to-sell backbone

| Primary activity (paper) | Odoo module / model |
|--------------------------|---------------------|
| Inbound logistics | `purchase`, `stock` (receipts) |
| Operations | `mrp` (manufacturing orders, BoM, work orders) |
| Outbound logistics | `stock` (delivery orders, `stock.picking`) |
| Marketing & sales | `crm`, `sale` (`sale.order`) |
| Service | `repair`, `helpdesk`, after-sales on `sale.order` |
| **Cost drivers** (scale, capacity) | `mrp_workorder` capacity, `stock` valuation, analytic costs |
| **Interdependence: Sequential** | the document flow SO → MO → picking → invoice (the chain) |

The chain's **sequential** logic is exactly Odoo's procurement/manufacturing document
pipeline — each step's output is the next step's input.

### 3.2 Value Shop → the problem-solving / engagement apps

| Primary activity (paper) | Odoo module / model |
|--------------------------|---------------------|
| Problem-finding & acquisition | `crm` lead qualification, `helpdesk` ticket intake |
| Problem-solving | `project` tasks, `helpdesk` investigation |
| Choice | task stage decisions, approval (`approvals`) |
| Execution | `hr_timesheet` (work delivered), `project` task completion |
| Control / evaluation | `project` review stages, `rating`, `survey` feedback |
| **Value driver: Reputation** | `rating`, `website_reviews`, customer ratings |
| **Interdependence: Reciprocal** | cyclic task ↔ subtask ↔ review loops (`mail.activity`) |

The shop's **cyclical, spiralling** logic = the iterative task/review loop. Note the
"primary activities" here are *not* a fixed line — they recur until the problem is solved,
which is precisely how `project`/`helpdesk` stages + `mail.activity` work.

### 3.3 Value Network → the mediation / platform apps

| Primary activity (paper) | Odoo module / model |
|--------------------------|---------------------|
| Network promotion & contract mgmt | `website`, `sign`, `subscription` (membership/contracts) |
| Service provisioning | `payment` (connect payer↔payee), `event`, `appointment` (connect parties) |
| Infrastructure operation | the platform itself: `website`, `bus` (real-time), `payment` acquirers |
| **Value driver: network size / capacity** | number of participants, `pos`/marketplace volume |
| **Interdependence: Reciprocal/parallel** | many simultaneous mediated exchanges |

The network's **simultaneous, parallel** logic = many concurrent mediated transactions
(payments, bookings, messages) running in parallel — Odoo's request-per-transaction model.

---

## 4. Implementing the Methodology as an Odoo Capability

Rather than just classifying, build a small **value-configuration analysis** module on the
same metadata/automation foundation used throughout this branch
(`ARIS_METHODOLOGY.md`, `BPMN_REVERSE_IMPLEMENTATION.md`).

### 4.1 Data model (the methodology made into ORM records)

```python
class ValueConfiguration(models.Model):
    _name = 'value.configuration'
    _inherit = ['mail.thread']               # audit per ARIS/LOGS docs
    _description = 'Value Configuration (Stabell & Fjeldstad)'

    name = fields.Char(required=True)        # the business unit analysed
    config_type = fields.Selection([
        ('chain',   'Value Chain (long-linked / transform)'),
        ('shop',    'Value Shop (intensive / solve)'),
        ('network', 'Value Network (mediating / mediate)'),
    ], required=True, tracking=True)
    interactivity_logic = fields.Selection([
        ('sequential', 'Sequential'),
        ('cyclical',   'Cyclical, spiralling'),
        ('parallel',   'Simultaneous, parallel'),
    ], compute='_compute_logic', store=True)   # derived from config_type
    activity_ids = fields.One2many('value.activity', 'configuration_id')

class ValueActivity(models.Model):
    _name = 'value.activity'
    _description = 'Primary Activity'

    configuration_id = fields.Many2one('value.configuration', ondelete='cascade')
    name      = fields.Char(required=True)     # e.g. "Problem-solving"
    sequence  = fields.Integer(default=10)
    odoo_model_id = fields.Many2one('ir.model', string='Realised by Odoo model')  # ← metadata link
    cost_driver  = fields.Selection([('scale','Scale'),('capacity','Capacity utilization'),
                                     ('learning','Learning'),('config','Configuration')])
    value_driver = fields.Selection([('bpc','Buyer purchasing criteria'),
                                     ('reputation','Reputation'),('network_size','Network size')])
    interdependence = fields.Selection([('pooled','Pooled'),('sequential','Sequential'),
                                        ('reciprocal','Reciprocal')])
```

The **`odoo_model_id → ir.model`** link is the key move: it binds each abstract primary
activity to the **actual Odoo model** that realizes it — making the analysis
*data-driven from the running system's metadata* (the ARIS principle).

### 4.2 Seed data — the three reference templates

Ship the paper's Table 1 as `data/value_configuration_templates.xml`: three
`value.configuration` records (chain/shop/network), each with its standard
`value.activity` lines, default drivers, and interdependence — so a user starts from the
canonical model and just attaches their Odoo models.

### 4.3 Wiring activities to live processes

Each `value.activity` can point at the `base.automation` rules / `ir.actions.server`
that *execute* it (the EPC link from `BPMN_REVERSE_IMPLEMENTATION.md` and
`ARIS_METHODOLOGY.md §3.4`). Then the chatter/log timeline (`LOGS_AND_MESSAGES.md`)
becomes the **measured** value-activity stream — you can compute real cost/value-driver
metrics from execution data instead of estimates.

### 4.4 Driver analytics (closing the loop to real data)

| Driver | Compute from Odoo data |
|--------|------------------------|
| **Scale** (cost) | volume of documents per activity model (`SELECT count(*)`) |
| **Capacity utilization** | `mrp_workorder` / `hr_timesheet` load vs. capacity |
| **Reputation** (shop value) | `rating.rating` averages, `survey` NPS |
| **Network size** (network value) | distinct participants in `payment`/marketplace tables |

These reuse the analytic and reporting layers Odoo already provides — the methodology
becomes a **reporting overlay**, not new infrastructure.

---

## 5. How to Apply It — the Procedure

```
1. CLASSIFY
   └─ Which logic dominates the unit? transform→chain, solve→shop, mediate→network.
      (A firm may be a mix: e.g. Odoo S.A. = network platform + shop services.)

2. LAY OUT PRIMARY ACTIVITIES
   └─ Instantiate the matching template (§4.2); list the activities from Table 1.

3. BIND TO ODOO MODELS  (metadata)
   └─ Set value.activity.odoo_model_id → the ir.model realizing each activity (§3).

4. WIRE TO PROCESSES  (EPC)
   └─ Link activities to base.automation / ir.actions.server that run them.

5. MEASURE DRIVERS  (runtime data)
   └─ Compute scale / capacity / reputation / network-size from live tables (§4.4).

6. DIAGNOSE & POSITION
   └─ Compare driver performance against the configuration's value logic to find
      competitive-advantage levers (the paper's goal).
```

---

## 6. Worked Classification — Odoo Itself

Applying the methodology to Odoo S.A. as an exercise:

| Unit | Dominant logic | Evidence in the product |
|------|----------------|-------------------------|
| Manufacturing/Inventory customer | **Chain** | `purchase→mrp→stock→sale` sequential pipeline |
| Consulting / implementation services | **Shop** | `project` + `hr_timesheet`, reputation via `rating` |
| Odoo Online / App Store / payments | **Network** | `website` platform mediating many users; value grows with participants |

This illustrates the paper's point that **one organization can run multiple
configurations** — and Odoo's modularity lets each be modelled and measured separately.

---

## 7. Summary

- **The methodology:** three generic value configurations — **Chain** (transform,
  sequential), **Shop** (solve, cyclical), **Network** (mediate, parallel) — each with its
  own primary activities and cost/value drivers (paper's Table 1).
- **Implementing it in Odoo** = (1) recognize which Odoo modules realize each
  configuration, (2) model the primary activities as `value.configuration` /
  `value.activity` records, (3) **bind each activity to its `ir.model`** so the analysis is
  metadata-driven, (4) wire activities to `base.automation`/`ir.actions.server` processes,
  and (5) compute the drivers from live Odoo data.
- **It reuses everything in this branch:** metadata (`ir.model`) per `ARIS_METHODOLOGY.md`,
  EPC/automation per `BPMN_REVERSE_IMPLEMENTATION.md`, and execution evidence per
  `LOGS_AND_MESSAGES.md` / `PROFILING_SUBSYSTEM.md`. The value-configuration model is the
  *strategy lens* on top of the *process and metadata layers* already documented.

The result: Stabell & Fjeldstad's strategic framework becomes a **living, data-driven
analysis** inside Odoo rather than a static diagram — the system classifies and measures
its own value-creation logic.

---

*Source: Stabell & Fjeldstad (1998), Strategic Management Journal 19(5):413–437 (uploaded
PDF). Odoo mapping grounded in modules `purchase/mrp/stock/sale` (chain),
`project/hr_timesheet/helpdesk` (shop), `website/payment/subscription` (network), and the
`ir.model` / `base.automation` foundation documented elsewhere on this branch.*
