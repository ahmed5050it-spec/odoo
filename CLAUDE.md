# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Two things live here:

1. **Odoo 19.0** — the full open-source ERP/web framework (a fork of the upstream `odoo/odoo` master). Standard Odoo layout.
2. **`doc/revres/`** — a custom **reverse-engineering catalog** that maps every Odoo module to an Enterprise-Architecture metamodel record. This is bespoke to this fork and is where most of the non-upstream work happens. Plus a set of EA/methodology essays under `doc/*.md` (many in Arabic, `_AR.md` suffix) that the revres workflow references.

`cd` does not persist between Bash calls — prefix commands with `cd /home/user/odoo &&`. Develop on the branch the task specifies (commonly `claude/adoring-albattani-jxeal7`), not the default branch.

## Running / building Odoo

Use the **`run-odoo` skill** (`.claude/skills/run-odoo/SKILL.md`) — it has the exact, battle-tested Postgres setup, the `pip install` lines that work around this container's broken setuptools/`cryptography`/`docopt`, DB init, and launch. Key facts that bite if you don't know them:

- **Launch only in background** (`nohup ./odoo-bin … & disown`). The foreground watchdog kills long-lived listeners with **exit 144**. Then drive from a *separate* call.
- **No Chromium / no screenshots** in this container. Drive the running server through `odoo shell` (most reliable — programmatic ORM, no server needed) or HTTP/JSON-RPC via `curl`. `.claude/skills/run-odoo/smoke.sh {init|smoke|shell|stop}` wraps all of it.
- DB `odoo_run`, PG role `odoo`/`odoo`, `--data-dir /tmp/odoo-data`, login `admin`/`admin`.

## Lint & tests (Odoo)

```bash
ruff check                      # config in ruff.toml (target py310; isort known-first-party = odoo)
```

Odoo has no pytest harness — tests run **inside a booted module** via the ORM test runner:

```bash
# Run a module's whole test suite (boots, installs, tests, exits):
./odoo-bin -d odoo_run -i <module> --test-enable --stop-after-init \
  --db_host localhost -r odoo -w odoo --data-dir /tmp/odoo-data

# Narrow to a class / single method with --test-tags (slash = module, colon = class, dot = method):
#   --test-tags /<module>            only that module
#   --test-tags :TestClass           one class (any module)
#   --test-tags :TestClass.test_x    one method
./odoo-bin -d odoo_run -u <module> --test-enable --test-tags ':TestClass.test_x' --stop-after-init …
```

`-i` installs, `-u` upgrades (use `-u` to re-run tests on an already-installed module).

## Odoo architecture (big picture)

A modular monolith driven by an ORM registry, not a conventional MVC app. To understand any feature you trace it across these layers:

- **Framework core** lives in `odoo/` (not `odoo/addons/`): `odoo/models.py`, `odoo/fields.py`, `odoo/api.py` (ORM), `odoo/http.py` (routing/sessions/dispatch), `odoo/modules/` (loader/registry), `odoo/service/` (RPC). `odoo/addons/` holds only the ~24 **base** modules (`base`, `web`, …); the other ~625 application modules are under top-level `addons/`.
- **A module** = a directory with `__manifest__.py` (name, `depends`, `data`, `assets`) plus: `models/*.py` (Python classes with `_name`/`_inherit` registering ORM models), `views/*.xml` (declarative UI + actions + menus), `security/` (`ir.model.access.csv` + `ir.rule` record rules + `res.groups`), `controllers/*.py` (`@http.route` HTTP/JSON-RPC endpoints), `static/src/**` (the **OWL** JavaScript frontend — a separate SPA framework, invisible to Python), `data/*.xml` (seed/config records), `report/` (QWeb PDF + `_auto=False` SQL-view analytics models).
- **Behavior is cross-model and method-level.** Records flow via side-effects you only see by reading methods: e.g. `sale.order.action_confirm` creates `stock.picking` + `account.move`. Models extend each other by `_inherit` (in-place graft) and share behavior via mixins (`mail.thread` chatter, `mail.activity.mixin`, `analytic.mixin`, `website.published.mixin`). Metadata shows *what/how*; the *why/side-effects* are in Python.
- **Localizations** are `l10n_*` modules; payment acquirers are `payment_*` (all share the `payment.provider`/`payment.transaction` engine shape); POS, mrp, hr, etc. each form a dependency cluster off a hub module.

## `doc/revres/` — the reverse-engineering catalog

One **metamodel record per module** (`doc/revres/metamodel/<m>.metamodel.json`, 649 of them) plus a narrative brief (`out/<m>.md`). The schema is `doc/revres/metamodel.schema.json`; **`metamodel/sale.metamodel.json` is the reference shape** every record matches.

**Three evidence layers** feed each record (the project's core thesis: metadata alone can't capture behavior):
- `extract_module.py <module_path>` → structural facts (manifest, models, fields, relations, routes, security, views, LOC) into `facts/<m>.facts.json`.
- `extract_frontend.py <module_path>` → OWL/JS components + outbound HTTP/SDK/api-key usage into `frontend/<m>.frontend.json` (closes the "gap #3 frontend" and "gap #7 integrations" that Python metadata misses).
- `extract_runtime.sh <module>` → live row counts via `odoo shell` (optional).

**Two tiers** of records:
- **baseline** — auto-generated: `sweep_all.py` runs the extractors, `auto_classify.py` infers a value-model/APQC by name/category, `gen_thin.py` writes a schema-valid stub. Correct shape, shallow classification.
- **deep** — agent-reviewed via the **two-agent workflow in `AGENT_WORKFLOW.md`**: a *code-explorer* gathers facts + reads key methods for ≥3 `code-read` `behavioral_notes`, then a *code-architect* fills the IT/Business architecture, the Stabell & Fjeldstad **value_model** (chain/shop/network/support), the **APQC PCF** category, and the Fit-to-Standard view. A record is "deep" iff it has ≥1 `behavioral_note` with `"source": "code-read"`.

**When upgrading a record (baseline → deep):** match `sale.metamodel.json` exactly; copy `frontend_gap3`→`evidence.frontend` and `integrations_gap7`→`evidence.integrations` verbatim from the frontend facts; use **only real model/method/field names read from the actual source** — facts files sometimes name files that don't exist (e.g. `models/ir_module.py` not `ir_module_module.py`), so read the real file rather than trust the prompt; never fabricate. Set `strategy: null` and a confidence tag per BA domain.

**After any record change**, refresh the derived artifacts (all stdlib, no Odoo import):
```bash
python3 doc/revres/validate_metamodel.py     # asserts all 649 records valid; prints coverage
python3 doc/revres/assignments.py            # rewrites ASSIGNMENTS.md + assignments.tsv (tier/TODO ledger)
python3 doc/revres/rollup.py                 # rewrites ROLLUP.md + rollup.tsv (value-model × APQC × layer)
```
`assignments.tsv` is the work ledger: the prioritized TODO queue of baseline records to deepen (priority = models×2 + routes; `l10n_*` and `test_*` are kept baseline). `AGENT_WORKFLOW.md`, `PROMPT.md`, `REVRES_WORKFLOW.md`, and `RUN_PLAN.md` document the methodology; `apqc_odoo_map.tsv` maps APQC activities to Odoo operations.
