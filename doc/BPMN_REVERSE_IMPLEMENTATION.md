# Reverse-Engineering BPMN 2.0 into an Odoo Module

> **Goal.** Take the OMG **BPMN 2.0** schemas (`Semantic.xsd`, `BPMN20.xsd`,
> `BPMNDI.cmof`) and show how to implement a BPMN workflow engine as an Odoo module —
> **reusing the `base` module** (`ir.*` models) and the **messaging subsystem** (`mail.*`)
> documented in `BASE_MODULE.md` and `MESSAGING_SUBSYSTEM.md`.
>
> This is a two-way reverse-engineering exercise:
> 1. **Reverse the spec** → distil the BPMN XSD into its core object model.
> 2. **Reverse Odoo** → find the existing primitives (`base.automation`,
>    `ir.actions.server`, `mail.activity`, `ir.cron`) that already implement BPMN's
>    runtime semantics, and map onto them instead of reinventing.

---

## 1. What the BPMN Schemas Actually Define

The three files are layered exactly like Odoo separates **data** from **presentation**:

| File | Layer | BPMN role | Odoo analogy |
|------|-------|-----------|--------------|
| `Semantic.xsd` | **Model** | The process semantics: processes, tasks, events, gateways, flows. | `ir.model` data models (the `mail.message` of the process world). |
| `BPMN20.xsd` | **Container** | The `<definitions>` root that holds rootElements + diagrams. | A `mail.thread`-style aggregate root. |
| `BPMNDI.cmof` | **Diagram Interchange** | Pure visuals: `BPMNShape`, `BPMNEdge`, `BPMNLabel`, x/y/width/height. | `ir.ui.view` / web client rendering — *separate from* the model. |

**Key reverse-engineering insight:** BPMN deliberately splits *semantics* (what runs)
from *diagram interchange* (how it's drawn). Your Odoo module should do the same — store
the executable model in ORM records and keep the `BPMNDI` coordinates in a separate
field/model used only by the JS diagram editor. Never let layout pollute execution.

### 1.1 The BPMN type hierarchy (distilled from `Semantic.xsd`)

Every BPMN element descends from `tBaseElement` (just like every Odoo record has
`ir.model.data`/XML-ID identity):

```
tBaseElement (id, documentation, extensionElements)
├── tRootElement                     ← top-level, lives in <definitions>
│   ├── tProcess                     ← the executable container
│   ├── tCollaboration               ← pools + message flows
│   ├── tMessage                     ← a message definition
│   ├── tError / tEscalation / tSignal / tEscalation
│   ├── tInterface / tOperation
│   └── tItemDefinition / tDataStore
│
├── tFlowElement                     ← anything inside a process
│   ├── tFlowNode (incoming[], outgoing[])
│   │   ├── tActivity (abstract)
│   │   │   ├── tTask
│   │   │   │   ├── tUserTask         ← human work
│   │   │   │   ├── tServiceTask      ← automated/web-service
│   │   │   │   ├── tScriptTask       ← run a script
│   │   │   │   ├── tSendTask / tReceiveTask   ← messaging
│   │   │   │   ├── tBusinessRuleTask
│   │   │   │   └── tManualTask
│   │   │   ├── tSubProcess / tTransaction / tAdHocSubProcess
│   │   │   └── tCallActivity         ← invoke another process
│   │   ├── tEvent
│   │   │   ├── tStartEvent
│   │   │   ├── tEndEvent
│   │   │   ├── tIntermediateCatchEvent / tIntermediateThrowEvent
│   │   │   └── tBoundaryEvent        ← attached to an activity
│   │   └── tGateway
│   │       ├── tExclusiveGateway     (XOR)
│   │       ├── tParallelGateway      (AND)
│   │       ├── tInclusiveGateway     (OR)
│   │       ├── tEventBasedGateway
│   │       └── tComplexGateway
│   ├── tSequenceFlow (sourceRef, targetRef, conditionExpression)
│   └── tDataObject / tDataStoreReference
│
├── tLaneSet / tLane                 ← swimlanes (who owns the node)
└── tArtifact (tGroup, tTextAnnotation, tAssociation)
```

### 1.2 Event definitions (the "trigger" taxonomy)

`tCatchEvent` / `tThrowEvent` carry `eventDefinition` children — this is BPMN's trigger
vocabulary, and it maps almost 1:1 onto Odoo's `base.automation.trigger`:

| BPMN `eventDefinition` | Meaning | Odoo equivalent |
|------------------------|---------|-----------------|
| `tMessageEventDefinition` | Wait for / throw a message | `mail.thread.message_post` + `on_message_received` |
| `tTimerEventDefinition` (timeDate/timeDuration/timeCycle) | Time-based | `ir.cron` + `on_time` automation |
| `tSignalEventDefinition` | Broadcast signal | `bus` broadcast / custom signal model |
| `tErrorEventDefinition` | Error caught | Python exception → boundary handler |
| `tConditionalEventDefinition` | Condition becomes true | `on_create_or_write` + domain filter |
| `tEscalationEventDefinition` | Escalate | `mail.activity` reassign / notify |
| `tTerminateEventDefinition` | Kill the process instance | set instance `state='cancelled'` |

---

## 2. The Mapping: BPMN → Odoo Models

The whole engine sits on **two record layers**, mirroring `mail`'s `mail.thread`
(definition/behavior) vs `mail.message` (data) split:

```
DESIGN-TIME (the model)            RUN-TIME (the instance / tokens)
─────────────────────────         ────────────────────────────────
bpmn.definitions   (root)         bpmn.process.instance   (a running process)
bpmn.process       (template)     bpmn.token              (execution pointer)
bpmn.flow.node     (task/event/gw) bpmn.activity.log      (audit, via mail.thread)
bpmn.sequence.flow (edges)
bpmn.lane          (swimlanes)
```

### 2.1 Design-time models (built on `base`)

| Model | Inherits | BPMN source | Notes |
|-------|----------|-------------|-------|
| `bpmn.definitions` | `mail.thread` | `tDefinitions` | The imported `<definitions>` root; one per `.bpmn` file. Stores raw XML + `exporter`. |
| `bpmn.process` | `mail.thread` | `tProcess` | An executable process; `isExecutable`, `processType`. Targets an Odoo `res_model` (the document the process runs on). |
| `bpmn.flow.node` | — | `tFlowNode` subclasses | One row per task/event/gateway. A `node_type` Selection enumerates the BPMN subtypes. |
| `bpmn.sequence.flow` | — | `tSequenceFlow` | `source_node_id`, `target_node_id`, `condition_expression`. |
| `bpmn.lane` | — | `tLane` | Maps a node to a `res.groups` / `res.users` owner. |
| `bpmn.di.shape` | — | `BPMNShape`/`BPMNEdge` | x/y/w/h for the editor — **execution ignores this**. |

`bpmn.flow.node.node_type` Selection (straight from the XSD substitution groups):

```python
node_type = fields.Selection([
    ('start_event',        'Start Event'),
    ('end_event',          'End Event'),
    ('intermediate_catch', 'Intermediate Catch Event'),
    ('intermediate_throw', 'Intermediate Throw Event'),
    ('boundary_event',     'Boundary Event'),
    ('user_task',          'User Task'),
    ('service_task',       'Service Task'),
    ('script_task',        'Script Task'),
    ('send_task',          'Send Task'),
    ('receive_task',       'Receive Task'),
    ('business_rule_task', 'Business Rule Task'),
    ('manual_task',        'Manual Task'),
    ('sub_process',        'Sub-Process'),
    ('call_activity',      'Call Activity'),
    ('exclusive_gateway',  'Exclusive Gateway (XOR)'),
    ('parallel_gateway',   'Parallel Gateway (AND)'),
    ('inclusive_gateway',  'Inclusive Gateway (OR)'),
    ('event_based_gateway','Event-Based Gateway'),
])
```

### 2.2 The crucial reuse — map BPMN behavior onto existing Odoo primitives

This is where reverse-engineering Odoo pays off. **Do not write an execution engine from
scratch** — Odoo already ships the runtime pieces:

| BPMN node | Reuse this Odoo primitive | Why it fits |
|-----------|---------------------------|-------------|
| **User Task** | **`mail.activity`** (+ `mail.activity.mixin`) | A user task *is* an assigned to-do with a deadline on a record — exactly `mail.activity`. Completion (`action_done`) advances the token. |
| **Service Task** | **`ir.actions.server`** (`state='code'/'object_write'/'object_create'/'webhook'`) | Server actions already run automated logic on a record with `env`, `record`, `model` in scope. |
| **Script Task** | `ir.actions.server` (`state='code'`) | Same engine; the `code` field is the BPMN `<script>`. |
| **Send Task / Message Throw** | **`mail.thread.message_post`** / `mail.template` | Sending a message is the messaging subsystem's core verb. |
| **Receive Task / Message Catch** | **`base.automation`** `on_message_received` | Inbound mail gateway already routes messages to records; the automation resumes the token. |
| **Business Rule Task** | `ir.actions.server` (`multi`) or a decision table model | Sequence of conditioned actions. |
| **Timer Event** | **`ir.cron`** + `base.automation` `on_time` | Cron is Odoo's scheduler; `timeDuration`/`timeCycle` → cron interval. |
| **Conditional Event** | `base.automation` `on_create_or_write` + domain | Fires when a record's fields satisfy a condition. |
| **Gateways** | `bpmn.sequence.flow.condition_expression` evaluated via `safe_eval` | Reuse Odoo's sandboxed expression evaluator (same one `ir.actions.server` uses). |
| **Lane / assignment** | **`res.groups`** + `mail.followers` | Swimlane ownership = group membership; participants = followers. |
| **Audit / history** | **`mail.thread`** chatter + `mail.tracking.value` | Every state change is a tracked message on the instance's chatter — free audit trail. |

> **The headline:** `base.automation` is Odoo's *de facto* event-condition-action engine
> and already `_inherit = ['mail.thread', 'mail.activity.mixin']`. BPMN's
> event→gateway→task triple is the same shape as automation's trigger→filter→action. You
> are essentially giving `base.automation` a **graph structure** (sequence flows) and a
> **token** to walk it.

---

## 3. The Runtime: a Token Engine on `base` + `mail`

BPMN execution semantics are **token-based**: a token is created at a start event and
flows along sequence flows; gateways split/merge tokens; the instance completes when no
tokens remain.

### 3.1 Runtime models

```python
class BpmnProcessInstance(models.Model):
    _name = 'bpmn.process.instance'
    _inherit = ['mail.thread']                      # ← free audit chatter
    _description = 'BPMN Process Instance'

    process_id = fields.Many2one('bpmn.process', required=True)
    res_model  = fields.Char(related='process_id.res_model', store=True)
    res_id     = fields.Many2oneReference('Record', model_field='res_model')  # the business doc
    state      = fields.Selection([('running','Running'),('done','Done'),
                                   ('cancelled','Cancelled')], default='running',
                                   tracking=True)    # ← tracked on chatter
    token_ids  = fields.One2many('bpmn.token', 'instance_id')

class BpmnToken(models.Model):
    _name = 'bpmn.token'
    _description = 'BPMN Execution Token'

    instance_id = fields.Many2one('bpmn.process.instance', ondelete='cascade', required=True)
    node_id     = fields.Many2one('bpmn.flow.node', required=True)   # where the token sits
    status      = fields.Selection([('active','Active'),('waiting','Waiting'),
                                    ('consumed','Consumed')], default='active')
    activity_id = fields.Many2one('mail.activity')   # set when waiting on a user task
```

### 3.2 The execution loop

```
start(process, record):
    inst  = bpmn.process.instance.create({process_id, res_id})
    start = process.flow_node_ids.filtered(node_type='start_event')
    token = bpmn.token.create({instance_id: inst, node_id: start})
    _execute(token)

_execute(token):
    node = token.node_id
    handler = NODE_HANDLERS[node.node_type]      # dispatch table
    handler(token)                               # may consume token / spawn new ones
    if not inst.token_ids.filtered(status != 'consumed'):
        inst.state = 'done'                      # no live tokens ⇒ process complete
```

### 3.3 Per-node handlers (each reuses an Odoo primitive)

| Handler | Action | Token effect |
|---------|--------|--------------|
| `start_event` | nothing | move token along its single outgoing flow |
| `service_task` / `script_task` | run the node's `ir.actions.server` with `record` in context | continue |
| `user_task` | create a `mail.activity` on the business record, assigned via the lane's group; **park the token** (`status='waiting'`) | wait; resumed by activity-done hook |
| `send_task` / message throw | `record.message_post(...)` or send a `mail.template` | continue |
| `receive_task` / message catch | park token; a `base.automation` `on_message_received` resumes it | wait |
| `exclusive_gateway` (XOR) | evaluate each outgoing flow's `condition_expression` (`safe_eval`); take the **first true** (or `default`) | one outgoing token |
| `parallel_gateway` (AND) | **split:** spawn a token per outgoing flow; **join:** consume until all incoming arrived | fan-out / barrier |
| `inclusive_gateway` (OR) | spawn tokens for every flow whose condition is true | fan-out subset |
| `timer event` | schedule an `ir.cron` (one-shot) that resumes the token at the due date | wait |
| `end_event` | consume token; if `terminateEventDefinition`, cancel all sibling tokens | terminate |

### 3.4 Resuming waiting tokens — the messaging bridge

The two "wait" states are resumed **by the messaging subsystem**, which closes the loop
back to `MESSAGING_SUBSYSTEM.md`:

```
USER TASK completion:
   mail.activity.action_done()  ──(override / hook)──▶  resume token.activity_id → _execute(next)

RECEIVE TASK / message catch:
   incoming email → mail.thread.message_process()
        └─ base.automation(on_message_received) ──▶ find waiting token on record → _execute(next)

TIMER:
   ir.cron fires ──▶ _execute(parked token)
```

---

## 4. Importing a `.bpmn` File (parsing the XSD instances)

A `.bpmn` file is XML validating against these XSDs. Parse it with `lxml` (already an Odoo
dependency, used throughout `mail`):

```python
NS = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
      'di':   'http://www.omg.org/spec/BPMN/20100524/DI'}

def import_bpmn(self, xml_bytes):
    root = etree.fromstring(xml_bytes)
    defs = self.env['bpmn.definitions'].create({'raw_xml': xml_bytes})
    for proc in root.findall('bpmn:process', NS):
        p = self.env['bpmn.process'].create({
            'definition_id': defs.id,
            'bpmn_id': proc.get('id'),
            'name': proc.get('name'),
            'is_executable': proc.get('isExecutable') == 'true',
        })
        node_map = {}
        # 1. flow nodes  (tasks, events, gateways) — element tag → node_type
        for el in proc:
            ntype = TAG_TO_NODE_TYPE.get(etree.QName(el).localname)
            if ntype:
                node_map[el.get('id')] = self.env['bpmn.flow.node'].create({
                    'process_id': p.id, 'bpmn_id': el.get('id'),
                    'name': el.get('name'), 'node_type': ntype,
                })
        # 2. sequence flows — wire sourceRef → targetRef
        for sf in proc.findall('bpmn:sequenceFlow', NS):
            cond = sf.findtext('bpmn:conditionExpression', namespaces=NS)
            self.env['bpmn.sequence.flow'].create({
                'process_id': p.id,
                'source_node_id': node_map[sf.get('sourceRef')].id,
                'target_node_id': node_map[sf.get('targetRef')].id,
                'condition_expression': cond,
            })
    # 3. (optional) BPMNDI coordinates → bpmn.di.shape for the editor only
    return defs
```

The XSD substitution groups tell you exactly which tags are flow nodes: anything whose
element has `substitutionGroup="flowElement"` in `Semantic.xsd` (e.g. `userTask`,
`exclusiveGateway`, `startEvent`). Build `TAG_TO_NODE_TYPE` directly from that list.

---

## 5. Module Skeleton (`base` + `mail` reuse made concrete)

```
bpmn_engine/
├── __manifest__.py
│     {'name': 'BPMN Engine',
│      'depends': ['base', 'mail', 'base_automation'],   # ← the three pillars
│      'data': ['security/ir.model.access.csv',
│               'views/bpmn_process_views.xml',
│               'data/bpmn_cron.xml']}                    # token sweeper cron
│
├── models/
│   ├── bpmn_definitions.py        # _inherit mail.thread
│   ├── bpmn_process.py            # _inherit mail.thread; res_model target
│   ├── bpmn_flow_node.py          # node_type + link to ir.actions.server / activity type
│   ├── bpmn_sequence_flow.py      # condition_expression (safe_eval)
│   ├── bpmn_process_instance.py   # _inherit mail.thread (audit trail)
│   ├── bpmn_token.py              # the execution pointer + handlers
│   └── bpmn_import.py             # lxml parser (§4)
│
├── data/
│   └── bpmn_cron.xml              # ir.cron: resume timer tokens (§3.3)
│
└── wizard/
    └── bpmn_import_wizard.py      # upload .bpmn (reuses base.language.import pattern)
```

**What you did NOT have to build** (because `base`/`mail` already provide it):
- ✅ Persistence, schema, XML-IDs, security → `base` ORM + `ir.model.access` + `ir.rule`.
- ✅ Automated actions / scripting sandbox → `ir.actions.server` + `safe_eval`.
- ✅ Human tasks, assignment, deadlines, reminders → `mail.activity`.
- ✅ Notifications, message send/receive, inbound routing → `mail.thread` / `mail.message`.
- ✅ Scheduling / timers → `ir.cron`.
- ✅ Audit trail of every transition → `mail.thread` chatter + `mail.tracking.value`.
- ✅ Event/condition triggers → `base.automation`.

You only wrote: the **graph model**, the **token**, and the **dispatch handlers**.

---

## 6. Side-by-Side: BPMN Spec ↔ Odoo Implementation

| BPMN 2.0 (`Semantic.xsd`) | Odoo model / primitive | Doc reference |
|---------------------------|------------------------|---------------|
| `tDefinitions` | `bpmn.definitions` (`mail.thread`) | BASE_MODULE §3 (ir.model.data XML-IDs) |
| `tProcess` (isExecutable) | `bpmn.process` (`mail.thread`) | BASE_MODULE §9 |
| `tUserTask` | `mail.activity` + `mail.activity.mixin` | MESSAGING §6 |
| `tServiceTask`/`tScriptTask` | `ir.actions.server` (`code`/`object_*`/`webhook`) | BASE_MODULE §3.3 |
| `tSendTask` / message throw | `mail.thread.message_post` / `mail.template` | MESSAGING §3.2 |
| `tReceiveTask` / message catch | `base.automation` `on_message_received` + mail gateway | MESSAGING §3.5 |
| `tTimerEventDefinition` | `ir.cron` + `base.automation` `on_time` | BASE_MODULE §3.4 (ir.cron) |
| `tConditionalEventDefinition` | `base.automation` `on_create_or_write` + domain | — |
| `tExclusive/Parallel/InclusiveGateway` | `safe_eval` on `condition_expression` + token split/join | PROFILING §n/a |
| `tSequenceFlow` (conditionExpression) | `bpmn.sequence.flow` | — |
| `tLane` / `tLaneSet` | `res.groups` + `mail.followers` | BASE_MODULE §4.2 |
| `tError`/`tEscalation`/`tSignal` | Python exceptions / `bus` broadcast | — |
| audit & history | `mail.thread` chatter + `mail.tracking.value` | MESSAGING §3.4 |
| `BPMNShape`/`BPMNEdge` (DI) | `bpmn.di.shape` (editor only) | — (kept out of execution) |

---

## 7. Summary — The Reverse-Engineering Method

1. **Reverse the spec into an object model.** The XSD's inheritance
   (`tBaseElement → tFlowElement → tFlowNode → {Activity, Event, Gateway}`) *is* your ORM
   model hierarchy. Substitution groups tell you the concrete node types.
2. **Separate semantics from diagram** exactly as BPMN does (`Semantic.xsd` vs
   `BPMNDI`) — and as Odoo does (`ir.model` vs `ir.ui.view`). Execution touches only the
   semantic layer.
3. **Reverse Odoo to find existing runtime primitives.** BPMN's *event-condition-action*
   core already exists as `base.automation`; tasks already exist as `ir.actions.server`
   (automated) and `mail.activity` (human); timers as `ir.cron`; messages as
   `mail.thread`. Map onto them — don't reinvent.
4. **Add only what's missing:** a **graph** (`bpmn.sequence.flow`), a **token**
   (`bpmn.token`), and a **dispatch loop**. Everything else — persistence, security,
   scheduling, notifications, audit — is inherited from `base` + `mail`.
5. **Close the loop through messaging.** Human tasks and message events suspend tokens;
   `mail.activity` completion, the inbound mail gateway, and `ir.cron` resume them. The
   messaging subsystem is both the *notification channel* and the *resumption trigger*.

The result is a BPMN 2.0 engine that is mostly *configuration of existing Odoo machinery*,
which is exactly why building it on the `base` module and the messaging subsystem is the
right architecture.

---

*Cross-references: `BASE_MODULE.md` (ir.* framework models, ir.cron, ir.actions.server),
`MESSAGING_SUBSYSTEM.md` (mail.thread, mail.activity, mail gateway), `ARCHITECTURE.md`
(ORM & service layers). Grounded in Odoo 19.0 `base`, `mail`, and `base_automation`.*
