# Agent Workflow — code-explorer + code-architect
# Build architecture & fulfill the metamodel for each Odoo subsystem

> A two-agent workflow an orchestrating agent **references** to produce, for each
> Odoo subsystem module, a filled **architecture metamodel record**
> (`metamodel.schema.json`) plus a narrative brief. It pairs a fact-finding role
> with a synthesis role, and is the agent-facing front end of the revres engine.
>
> - **code-explorer** → gathers ground-truth *evidence* (structure + behavior).
> - **code-architect** → fulfills the *metamodel* (IT + Business Architecture)
>   and the Fit-to-Standard view.
>
> Output per subsystem: `doc/revres/metamodel/<module>.metamodel.json`
> (schema-valid) and `doc/revres/out/<module>.md` (brief).

---

## 0. Orchestrator loop

```
pick subsystems from doc/revres/facts/index.tsv  (hubs first: base, account,
  mail, stock, sale, purchase, mrp, product, payment, website, hr, project)
for each module M:
    facts   = code-explorer(M)        # Stage 1
    record  = code-architect(facts)   # Stage 2
    validate(record, metamodel.schema.json)
    write doc/revres/metamodel/M.metamodel.json
    write doc/revres/out/M.md
```

Run modules independently → the two stages can be dispatched as parallel
sub-agents per module. code-architect **must not** start until that module's
code-explorer evidence exists (data dependency).

---

## 1. Agent: **code-explorer**

**Goal:** produce the `evidence` block of the metamodel — *facts only, no
interpretation*. Covers both what metadata shows AND what it cannot
(`METADATA_LIMITS_AR.md`).

**Suggested subagent type:** `Explore` (read-only, fan-out search).

**Inputs:** `module_path` (e.g. `addons/sale`).

**Procedure:**
1. **Structural facts (auto):** run the engine —
   `python3 doc/revres/extract_module.py <module_path> --pretty`
   → manifest, models, fields, relations, routes, security, views, LOC.
2. **Behavioral facts (the metadata gap):** for the 3-5 most important models,
   read the key methods (compute, `action_*`, constraints, `_notify`/`_create`)
   and record **side-effects** metadata can't show — e.g. "`sale.order.action_confirm`
   creates `stock.picking` + `account.move`". Use Grep/Read. Tag `source: code-read`.
3. **Frontend + integration facts (static, closes gaps #3/#7):** run
   `python3 doc/revres/extract_frontend.py <module_path>` → OWL components,
   registry adds, patches, asset bundles (gap #3 JS/OWL) and outbound HTTP/SDK/
   api-key usage (gap #7 external integrations). These are NOT in Python metadata.
4. **Runtime facts (live, closes gap #5 + part of #6):** run
   `doc/revres/extract_runtime.sh <module>` (uses the **`run-odoo`** `odoo shell`)
   → real row counts + samples per model + per-count query cost. For deeper
   document-chain capture use `--log-handler=odoo.sql_db:DEBUG`. Tag
   `source: runtime|log-trace`.

**Output (returned to orchestrator):**
```json
{ "subsystem": "<m>",
  "evidence": { "manifest": …, "models": …, "routes": …, "security": …,
                "views": …, "behavioral_notes": [ {element, observation, source} ] },
  "provenance": { "explorer_facts": "doc/revres/facts/<m>.facts.json", "tools": […] } }
```

**Done when:** `evidence` is filled, including ≥3 `behavioral_notes` that go
beyond metadata (the whole point — see METADATA_LIMITS_AR).

**Must NOT:** classify value models, name capabilities, or judge Fit/Gap — that
is code-architect's job. Explorer states facts; architect interprets.

---

## 2. Agent: **code-architect**

**Goal:** consume the explorer's evidence and **fulfill the metamodel** —
`it_architecture`, `business_architecture`, `classification`,
`fit_to_standard` — marking confidence per element.

**Suggested subagent type:** `general-purpose` (or `Plan`).

**Inputs:** the code-explorer evidence JSON.

**Procedure (fill the schema):**

1. **IT architecture (auto, from evidence):**
   - `application` = the module; `software_services` = `routes[]`;
     `data_objects` = `models[]._name`; `logical_data_erm` = key relations;
     `information_flows` = `depends` + cross-model side-effects from
     `behavioral_notes`.
   (Mapping authority: the B&IT Metamodel Alignment whitepaper /
   `REVERSE_ENGINEERABLE_FROM_CODE_AR.md`.)

2. **Business architecture (Business Architecture Guild v3.0 domains —
   `BUSINESS_ARCHITECTURE_ODOO_AR.md`):**
   - `information_concepts` (**auto**) = the business models.
   - `organization` (**auto**) = security groups.
   - `products` (**auto**) = `product.*` models if present.
   - `capabilities` (**inferred**) = from `category` + models + value-model.
   - `value_streams` (**inferred**) = document-flow side-effects.
   - `policies` (**inferred**) = `ir.rule` / automation.
   - `strategy` (**human**) = usually `null`.
   Set `reverse_eng_confidence[domain]` = auto|inferred|human for each.

3. **Classification:**
   - `value_model` ∈ chain/shop/network/support (Stabell & Fjeldstad —
     `VALUE_MODELS_THREE_AR.md`), `activity_class` primary/support,
     `apqc_category` 1.0-13.0 (`APQC_PCF_VALUE_MODELS_AR.md`), with `rationale`.

4. **Fit-to-Standard (`EA_FIT_TO_STANDARD_AR.md`):**
   - `standard_capabilities`, `typical_fits`, `common_gaps`, `drive_hints`
     (concrete `odoo shell`/`curl` to demo the standard live via run-odoo).

5. **open_questions:** carry forward anything evidence couldn't resolve.

**Output:** a schema-valid `<module>.metamodel.json` + the narrative brief
(`out/<module>.md`, structure per `PROMPT.md`).

**Done when:** the record validates against `metamodel.schema.json`, every BA
domain has a confidence tag, and no element is fabricated beyond the evidence.

**Must NOT:** invent models/routes/fields not in the evidence; mark an inferred
capability as `auto`.

---

## 3. Handoff contract

```
code-explorer ──{ evidence + provenance }──▶ code-architect ──{ full metamodel record }──▶ orchestrator
                  (facts, no judgement)         (interpretation, classification)        (validate + write)
```

- The boundary is **fact vs interpretation** — it mirrors the project's core
  finding: metadata/AST give *what/how*; a person (here, the architect role)
  supplies *capability/value/why* (`METADATA_LIMITS_AR.md`).
- Confidence tags make the human-needed parts explicit, so a reviewer knows
  which fields to trust vs. confirm.

---

## 4. Tooling map

| Need | Tool / artifact |
|------|-----------------|
| Structural extraction | `doc/revres/extract_module.py`, `run_revres.sh` |
| Triage / module list | `doc/revres/facts/index.tsv` |
| Behavior beyond metadata | Grep/Read on the module; `run-odoo` `odoo shell` + sql_db log |
| Live verification | `.claude/skills/run-odoo/smoke.sh` |
| Metamodel schema | `doc/revres/metamodel.schema.json` |
| Brief structure | `doc/revres/PROMPT.md` |
| Framework references | `BUSINESS_ARCHITECTURE_ODOO_AR`, `VALUE_MODELS_THREE_AR`, `APQC_PCF_VALUE_MODELS_AR`, `EA_FIT_TO_STANDARD_AR`, `REVERSE_ENGINEERABLE_FROM_CODE_AR`, `METADATA_LIMITS_AR` |

---

## 5. Example

`doc/revres/metamodel/sale.metamodel.json` is a complete worked record produced
by this workflow (explorer evidence from `facts/sale.facts.json` + architect
synthesis). Use it as the reference shape.

---

## 6. Why two agents

- **Separation of concerns:** explorer is read-only and parallelizable across
  hundreds of modules; architect is the reasoning bottleneck applied once per
  module on clean evidence.
- **Auditability:** the evidence/interpretation split means every architectural
  claim traces to a fact (or is flagged `inferred`/`human`).
- **Reuse:** explorer evidence feeds Fit-to-Standard workshops directly (the
  "Standard" catalog); architect output feeds the Business Architecture
  knowledgebase. One pass, both layers (`EA_FIT_TO_STANDARD_AR.md`).

---

*References the revres engine, the run-odoo skill, and the metamodel/value/EA
docs on this branch. Odoo 19.0.*
