# revres Workflow — Reverse-Engineering Engine for Odoo Modules

> A repeatable **two-stage workflow** that generates a reverse-engineering
> ("revres") document for **each Odoo subsystem module**, automating the manual
> analysis done by hand for `base`, `mail`, and the profiling subsystem earlier
> on this branch.
>
> **Stage 1 (engine — deterministic):** `extract_module.py` statically mines a
> module into a JSON facts object. **Stage 2 (narrative — model):** `PROMPT.md`
> turns those facts into a structured Markdown brief. The split keeps facts
> ground-truth and reproducible while letting a model handle prose + classification.

```
 module dir ─▶ extract_module.py ─▶ <module>.facts.json ─┐
                                                          ├─▶ (PROMPT.md + model) ─▶ out/<module>.md
 run_revres.sh ─▶ facts/*.json + index.tsv  (triage) ─────┘
```

## Files

| File | Role |
|------|------|
| `extract_module.py` | **The engine.** Stdlib-only static extractor: manifest, models, fields, relations, security, routes, views, LOC → JSON. No Odoo import, no DB. |
| `run_revres.sh` | **Batch runner.** Runs the engine over many modules → `facts/*.json` + `index.tsv`. |
| `PROMPT.md` | **The generator prompt.** Facts JSON → reverse-engineering Markdown (8 fixed sections incl. value-model + APQC classification). |
| `out/<module>.md` | **Output docs.** One brief per module. `out/sale.md` is a worked example. |
| `facts/index.tsv` | **Triage index.** One row/module: category, depends, #models, #routes, LOC — to pick which subsystems to document first. |

## Stage 1 — extract facts (verified)

Per module:

```bash
python3 doc/revres/extract_module.py odoo/addons/base --pretty
python3 doc/revres/extract_module.py addons/mail > /tmp/mail.facts.json
```

All modules (writes `doc/revres/facts/*.json` + `index.tsv`):

```bash
doc/revres/run_revres.sh                 # every module in addons/ + odoo/addons/
doc/revres/run_revres.sh base mail sale  # or a chosen subset
```

Verified extractor output (this session):

| module | models | routes | py LOC | notable |
|--------|-------:|-------:|-------:|---------|
| base | 124 | 0 | 66392 | 146 access rules, 32 record rules |
| mail | 58 | 64 | 41728 | jsonrpc surface, kanban/activity views |
| account | 57 | 12 | 96690 | largest subsystem |
| stock | 51 | 1 | 44942 | inventory backbone |
| sale | 7 | 14 | 17901 | configurator routes |

## Stage 2 — generate the brief

Feed `PROMPT.md` + one `*.facts.json` to a model; write the result to
`out/<module>.md`. Each brief has 8 fixed sections, including:

- **Data Model (ERM)** — models, key relations, field-type distribution.
- **Behavior & Surfaces** — routes (auth/type), views, security posture.
- **Value-Configuration Classification** — chain / shop / network / support
  (ties to `VALUE_MODELS_THREE_AR.md`, `PRIMARY_ACTIVITIES_AR.md`).
- **APQC PCF Hint** — likely category 1.0–13.0
  (ties to `APQC_PCF_VALUE_MODELS_AR.md`).
- **How to Drive It** — concrete `odoo shell` / `curl` calls via the
  **`run-odoo`** skill.

See `out/sale.md` for a complete worked example.

## Recommended run order (subsystem-first)

Use `index.tsv` to prioritize. Document the **hub subsystems** first, then their
satellites:

1. **Kernel:** `base`, `web`, `bus`.
2. **Backbones:** `account`, `mail`, `stock`, `sale`, `purchase`, `mrp`,
   `product`, `payment`, `website`, `hr`, `project`.
3. **Bridges/satellites:** the `*_*` combination modules (e.g. `sale_stock`,
   `account_edi_*`) — usually thin; document on demand.
4. **Localizations (`l10n_*`):** skip unless specifically requested.

## How this composes with the rest of the branch

- The **engine** mines the same metadata the `ARIS_METHODOLOGY.md` doc treats as
  an ARIS repository (`ir.model`/`ir.model.fields` equivalents, statically).
- The **classification** sections reuse the value-model and APQC frameworks
  documented in `VALUE_*` and `APQC_PCF_*`.
- The **"How to Drive It"** section points every brief at the `run-odoo` skill,
  so a reader can immediately validate the static facts against a live server.

## Extending the engine

`extract_module.py` is intentionally small. Natural additions:
- compute-method / `@api.depends` extraction (needs deeper AST walk),
- `base.automation` / `ir.cron` discovery from data XML,
- cross-module relation graph (join all `facts/*.json` on `relation`).

Each is a pure-Python addition to the engine; the prompt/output contract stays
stable.

---

*Stage-1 engine and batch runner verified in-container on base/mail/account/
sale/stock (Odoo 19.0). Stage-2 example: `out/sale.md`.*
