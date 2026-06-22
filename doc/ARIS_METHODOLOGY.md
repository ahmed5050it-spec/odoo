# Reverse-Engineering Odoo with the ARIS Methodology

> **ARIS** (*Architecture of Integrated Information Systems*, A.-W. Scheer) models an
> enterprise system through **five interlocking views** sitting on a shared **metadata
> repository**. Odoo is unusually well-suited to ARIS reverse-engineering because its
> entire structure is **live metadata** — the `ir.model.*` tables *are* an ARIS-style
> repository you can query.
>
> This document maps Odoo onto ARIS, deriving each view **from Odoo's own metadata**
> (`ir.model`, `ir.model.fields`, `ir.model.relation`, …) and runtime metadata
> (`ir.logging.metadata`, the profiler `others` blob), so the model is *reverse-engineered
> from the running system*, not hand-drawn.

---

## 1. The ARIS Framework in One Picture (the "ARIS House")

```
                        ┌─────────────────────────────┐
                        │     ORGANIZATION VIEW        │   WHO
                        │  org units, roles, users     │
                        └──────────────┬──────────────┘
                                       │
        ┌──────────────┐      ┌────────┴────────┐      ┌──────────────┐
        │ FUNCTION VIEW│◀────▶│  CONTROL /      │◀────▶│  DATA VIEW   │
        │  WHAT (verbs)│      │  PROCESS VIEW   │      │ WHAT (nouns) │
        │  functions,  │      │   (EPC: events  │      │  entities,   │
        │  activities  │      │   ↔ functions)  │      │  attributes  │
        └──────────────┘      └────────┬────────┘      └──────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │   PRODUCT / SERVICE VIEW     │   OUTPUT
                        │  deliverables, documents     │
                        └─────────────────────────────┘
```

The **Control view** in the centre is the integrator: it ties *who* does *what function*
on *what data* to produce *what product*, in what order — expressed as **Event-driven
Process Chains (EPC)**: `Event → Function → Event → …`.

ARIS also has three **description levels** (the life-cycle): **Requirements Definition →
Design Specification → Implementation Description**. Odoo gives you all three at once,
because the implementation *is* described in queryable metadata.

---

## 2. Why Odoo Maps onto ARIS So Cleanly: Metadata as the Repository

ARIS stores every model in a **repository** with a strict **meta-model** (objects, types,
attributes, relationships). Odoo's `base` module **already is** such a repository — see
`BASE_MODULE.md §3`:

| ARIS repository concept | Odoo metadata model |
|-------------------------|---------------------|
| Object type | `ir.model` (one row per model) |
| Attribute / data element | `ir.model.fields` (one row per field) |
| Relationship type | `ir.model.fields` (Many2one/One2many/Many2many) + `ir.model.relation` (M2M tables) |
| Constraint | `ir.model.constraint` |
| Object occurrence / identity | `ir.model.data` (XML-IDs) |
| Model inheritance | `ir.model.inherit` |
| Access / responsibility assignment | `ir.model.access`, `ir.rule` |

> **The crucial point:** in classic ARIS you *draw* the meta-model in a tool. In Odoo the
> meta-model is **introspectable at runtime** — `SELECT * FROM ir_model_fields` returns
> your Data view. Reverse-engineering ARIS views becomes a set of **metadata queries**.

---

## 3. View-by-View Mapping (each derived from metadata)

### 3.1 Organization View — *WHO*

The actors and their responsibility structure.

| ARIS element | Odoo model | Notes |
|--------------|-----------|-------|
| Organizational unit | `res.company` | Multi-company hierarchy. |
| Position / role | `res.groups` (+ `res.groups.privilege`) | The unit of authority. |
| Person / user | `res.users` (a `res.partner`) | |
| Group/role assignment | `res.users ↔ res.groups` (M2M) | Who holds which role. |
| Responsibility for a process step | `mail.followers`, activity assignee (`mail.activity.user_id`) | Who is accountable per record. |

**Extract it from metadata:**
```python
# Org chart: which roles (groups) each user holds
for u in env['res.users'].search([]):
    print(u.name, '→', u.groups_id.mapped('full_name'))
```

### 3.2 Data View — *WHAT (nouns)* — the heart of the metadata mapping

This is the ARIS **ERM (Entity-Relationship Model)**, and it is **literally**
`ir.model` + `ir.model.fields`.

| ARIS data element | Odoo metadata |
|-------------------|---------------|
| Entity type | `ir.model` |
| Attribute | `ir.model.fields` (non-relational) |
| Relationship | `ir.model.fields` with `ttype in (many2one, one2many, many2many)` |
| Cardinality | the field type itself (m2o = N:1, o2m = 1:N, m2m = N:M) |
| Domain / data type | `ir.model.fields.ttype` |

The field-type distribution **is** the Data view's vocabulary. From the `base` models
alone the relational backbone dominates:

```
 Char       253     ← attributes
 Many2one   114     ← N:1 relationships  ┐
 One2many    37     ← 1:N relationships  ├─ the ERM edges
 Many2many   33     ← N:M relationships  ┘
 Selection   57     ← enumerated domains
 Boolean     91 ,  Integer 60 ,  Date 51 ,  Text 43 , ...
```

**Reverse-engineer the ERM of any model from metadata:**
```python
# Entity + its relationships (ARIS data view for one entity)
model = env['ir.model'].search([('model', '=', 'sale.order')])
for f in model.field_id:
    if f.ttype in ('many2one', 'one2many', 'many2many'):
        print(f"sale.order --{f.ttype}--> {f.relation}   ({f.name})")
```

This emits exactly the edges of an ARIS entity-relationship diagram — generated, not drawn.

### 3.3 Function View — *WHAT (verbs)*

The functions/activities the system can perform, in a functional hierarchy.

| ARIS element | Odoo model/metadata |
|--------------|--------------------|
| Function / activity | model **methods**, `ir.actions.server` (automated functions) |
| Function tree (decomposition) | `ir.ui.menu` hierarchy → `ir.actions.act_window` |
| Application function | `ir.actions.*` (window/server/report/client) |
| Scheduled function | `ir.cron` |

**Extract the function hierarchy from metadata** (menus = the ARIS function tree):
```python
for menu in env['ir.ui.menu'].search([('parent_id', '=', False)]):
    print(menu.complete_name, '→', menu.action and menu.action.type)
```

`ir.actions.server.state` enumerates the *kinds* of automated function (the Function
view's leaf types): `object_write`, `object_create`, `code`, `webhook`, `multi`, plus
`mail_post` / `next_activity` from `mail`.

### 3.4 Control / Process View — *the integrator* — ARIS EPC ↔ Odoo events

This is where ARIS shines and where Odoo's **event metadata** comes in. An **EPC** chains:

```
(Event) ──▶ [Function] ──▶ (Event) ──▶ ◇XOR◇ ──▶ [Function] ──▶ (Event)
```

Odoo expresses the same `Event → Function` semantics through **`base.automation`**
(see `BPMN_REVERSE_IMPLEMENTATION.md §2.2`), which is structurally an EPC rule:

| ARIS EPC element | Odoo equivalent |
|------------------|-----------------|
| **Event** (state change that triggers) | `base.automation.trigger` (`on_create`, `on_write`, `on_stage_set`, `on_time`, `on_message_received`, …) |
| **Function** (the activity performed) | `base.automation.action_server_ids` → `ir.actions.server` |
| **Connector** (XOR/AND/OR) | server-action conditions / `safe_eval` filters |
| **Process interface / message** | `mail.message` events (`on_message_received`/`sent`) |
| **Resource (org unit on a function)** | activity assignee / followers (links to Org view) |

**Reverse-engineer the live EPCs from metadata:**
```python
# Each automation rule is an EPC fragment: Event --> Function(s)
for rule in env['base.automation'].search([]):
    funcs = rule.action_server_ids.mapped('name')
    print(f"(EVENT: {rule.trigger} on {rule.model_name}) --> [FUNCTIONS: {funcs}]")
```

The chatter timeline (`mail.message` rows, `MESSAGING_SUBSYSTEM.md`) is, in effect, the
**executed EPC instance log**: each message/tracking entry is an event occurrence on a
record, in order — a per-record process trace.

### 3.5 Product / Service View — *OUTPUT*

The deliverables the processes produce.

| ARIS element | Odoo model |
|--------------|-----------|
| Product / service | `product.template` / `product.product` |
| Output document | business documents: `sale.order`, `account.move`, `stock.picking`, … |
| Document as report | `ir.actions.report` (QWeb → PDF) |

---

## 4. "Metadata and Other" — the Runtime Metadata Layer

Beyond the static repository, Odoo carries **runtime metadata** that feeds the ARIS
Control view with *actual execution data* (closing the loop from model to instance):

| Source | Field | ARIS use |
|--------|-------|----------|
| `ir.logging` | **`metadata`** (JSON column) | Per-log-record structured context (e.g. test info). Attaches execution metadata to each logged function call — EPC instance evidence. |
| `ir.profile` | **`others`** (JSON) | Non-standard profiler collectors stored as a metadata blob; `_store = "others"` routes any custom collector here. Process-timing metadata. |
| `mail.message` | `message_type`, `subtype_id`, `tracking_value_ids` | The event-type metadata of each process occurrence on a record. |
| `mail.tracking.value` | field old→new | The data-view delta produced by each function execution. |

So the ARIS picture has **two strata**:
- **Type level** (the repository): `ir.model`, `ir.model.fields`, `base.automation` →
  the *models* (ARIS Requirements/Design).
- **Instance level** (runtime metadata): `ir.logging.metadata`, `ir.profile.others`,
  `mail.message`/`mail.tracking.value` → the *occurrences* (ARIS Implementation evidence).

This mirrors ARIS's own distinction between **model types** and **model occurrences**, and
between the **description levels** (concept → implementation).

---

## 5. The Reverse-Engineering Procedure (metadata-driven)

To reconstruct an ARIS model of any Odoo area **from the running system**:

```
1. DATA VIEW (ERM)
   └─ query ir.model + ir.model.fields → entities + relationships
   └─ ir.model.relation → M2M junctions ; ir.model.constraint → integrity rules

2. ORGANIZATION VIEW
   └─ res.company / res.groups / res.users (+ M2M) → org & role chart
   └─ ir.model.access + ir.rule → who-may-do-what overlay

3. FUNCTION VIEW
   └─ ir.ui.menu tree → function hierarchy
   └─ ir.actions.server.state + ir.cron → automated function catalogue

4. CONTROL VIEW (EPC)
   └─ base.automation (trigger → action) → Event→Function chains
   └─ mail.message / mail.tracking.value timeline → executed EPC instances

5. PRODUCT VIEW
   └─ product.* + business documents + ir.actions.report (outputs)

6. RUNTIME METADATA (evidence / occurrence level)
   └─ ir.logging.metadata , ir.profile.others → bind functions to real executions
```

Every step is a **metadata query**, not a manual drawing — which is the whole point of
using ARIS against a metadata-driven platform like Odoo.

---

## 6. Side-by-Side: ARIS ↔ Odoo Metadata

| ARIS view | ARIS core element | Odoo metadata source | Doc ref |
|-----------|-------------------|----------------------|---------|
| Organization | org unit / role / person | `res.company` / `res.groups` / `res.users` | BASE §4 |
| Data (ERM) | entity / attribute / relationship | `ir.model` / `ir.model.fields` / `ir.model.relation` | BASE §3.1 |
| Function | function / app function | model methods / `ir.actions.server` / `ir.cron` | BASE §3.3 |
| Control (EPC) | event → function → event | `base.automation` trigger→action ; `mail.message` events | BPMN §2.2, MESSAGING §3 |
| Product/Service | product / output document | `product.*` / `sale.order`,`account.move` / `ir.actions.report` | — |
| Repository (meta) | model type / occurrence | `ir.model.data` (XML-IDs) / `ir.model.inherit` | BASE §3.1 |
| Runtime metadata | execution occurrence | `ir.logging.metadata` / `ir.profile.others` / `mail.tracking.value` | LOGS_AND_MESSAGES, PROFILING |

---

## 7. Summary

- **ARIS needs a metadata repository; Odoo *is* one.** `ir.model`, `ir.model.fields`,
  `ir.model.relation`, `ir.model.data` form a live, queryable meta-model — so each ARIS
  view can be **generated from metadata** rather than hand-modelled.
- **The five views map cleanly:** Organization → `res.*` security models; Data → the
  `ir.model.*` ERM; Function → menus/actions/cron; Control → `base.automation` EPCs +
  the `mail.message` event timeline; Product → products & report documents.
- **"Metadata and other" = two strata.** The *type level* (repository: `ir.model.*`,
  `base.automation`) gives ARIS Requirements/Design; the *instance level* (runtime
  metadata: `ir.logging.metadata`, `ir.profile.others`, `mail.tracking.value`) gives ARIS
  Implementation evidence — the executed EPC occurrences.
- **Control view is the integrator**, and in Odoo it is realized by the same
  event-condition-action machinery (`base.automation`) and message timeline used by the
  BPMN mapping — so the ARIS, BPMN, and logs/messages views are three lenses on one
  metadata-driven core.

Reverse-engineering Odoo with ARIS therefore reduces to **querying its metadata** and
arranging the results into the five views — the system documents itself.

---

*Cross-references: `BASE_MODULE.md` (ir.* metadata repository), `MESSAGING_SUBSYSTEM.md`
(mail.message event timeline), `LOGS_AND_MESSAGES.md` (ir.logging.metadata),
`PROFILING_SUBSYSTEM.md` (ir.profile.others), `BPMN_REVERSE_IMPLEMENTATION.md`
(base.automation as EPC). Grounded in Odoo 19.0 metadata.*
