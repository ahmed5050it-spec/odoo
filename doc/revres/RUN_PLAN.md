# Run Plan — execute the code-explorer + code-architect workflow per module

Executes `AGENT_WORKFLOW.md` to produce, per subsystem, a schema-valid
`metamodel/<module>.metamodel.json` + `out/<module>.md`.

## Order (hubs first, from facts/index.tsv)

| Wave | Modules | Value model covered | Status |
|------|---------|---------------------|--------|
| 0 | sale | chain (primary) | ✅ done (reference example) |
| 1 | account, stock, purchase, mrp | chain backbone + support | run |
| 2 | project, mail | shop, support | run |
| 3 | product, payment, website, hr, web, bus, base | mixed | optional |

## Per-module procedure (one agent plays explorer→architect)

1. Read `doc/revres/facts/<m>.facts.json` (structural evidence, already extracted).
2. **Explorer step:** read 3–5 key model files under the module for
   `behavioral_notes` (method side-effects metadata can't show).
3. **Architect step:** fulfill `metamodel.schema.json` —
   it_architecture, business_architecture (BA Guild domains, with confidence),
   classification (value_model + APQC activity-level via `apqc_odoo_map.tsv`),
   fit_to_standard.
4. Write `metamodel/<m>.metamodel.json` (schema-valid) + `out/<m>.md`.

## Validation

After each wave: `python3 doc/revres/validate_metamodel.py` checks every record
against the schema and prints a coverage table.

## Tools

`extract_module.py` (facts) · Grep/Read (behavior) · `run-odoo` skill (optional
live check) · `metamodel.schema.json` · `apqc_odoo_map.tsv` · framework docs.
