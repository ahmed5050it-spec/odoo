# revres generation prompt

Feed this prompt + a module's `*.facts.json` (from `extract_module.py`) to a
model to generate a reverse-engineering document. The facts are ground truth;
the model supplies narrative, structure, and classification.

---

```text
You are a software archaeologist reverse-engineering an Odoo 19 module.

INPUT: a JSON "facts" object statically extracted from one module
(manifest, models, fields, relationships, security, routes, views, LOC).
Treat every value in it as ground truth — do not invent models, fields, or
routes that are not present. If something is absent, say so.

TASK: produce a Markdown reverse-engineering document, ~150-300 lines, with
EXACTLY these sections:

1. # <module> — Reverse-Engineering Brief
   One-paragraph intro: what the module does (infer from name/category/
   summary/models), whether it is auto_install/application, and its place in
   the dependency graph (use `depends`).

2. ## Role & Dependencies
   - Why it depends on each listed module (1 line each, top 6).
   - What capability it adds on top of them.

3. ## Data Model (the ERM)
   - Table of the main models (_name, _description, #fields, key relations).
   - Call out the central/aggregate model and the polymorphic or mixin ones
     (_inherit without _name = a mixin/extension).
   - Summarize the field-type distribution (what it implies: relational-heavy
     vs attribute-heavy).

4. ## Behavior & Surfaces
   - Routes: how many, auth/type mix, what web/RPC surface they expose.
   - Views: which view types dominate (form/list/kanban…) and what that says
     about the UX.
   - Security posture: access rules / record rules / groups counts.

5. ## Value-Configuration Classification
   Classify the module against Stabell & Fjeldstad's three models:
   - chain (transform: purchase/mrp/stock/sale-like document flow)
   - shop (solve: project/service/timesheet/helpdesk-like)
   - network (mediate: website/payment/portal/bus-like)
   - or "support" (cross-cutting: hr/account/security/technical).
   Justify from the facts (depends, models, routes). Map its primary vs
   support activity role.

6. ## APQC PCF Hint
   Name the most likely APQC PCF category (1.0-13.0) this module supports,
   one line of justification.

7. ## How to Drive It
   Reference the run-odoo skill: which models to query via `odoo shell`, which
   routes to curl. Give 1-2 concrete `env['<model>'].search(...)` examples
   using real model names from the facts.

8. ## Open Questions
   2-4 things the static facts can't answer that a reader should verify in code
   (e.g. compute methods, automation, external API calls).

RULES:
- Use real names from the facts verbatim (model _name, route paths).
- Prefer tables over prose for models/routes.
- No fabrication. Mark inferences as "(inferred)".
- End with a one-line provenance note citing extract_module.py.
```

---

## Batch variant

To generate docs for many modules, run the prompt once per `*.facts.json` and
write each result to `doc/revres/out/<module>.md`. Use `index.tsv` to
prioritize: start with high-`models`/high-`routes` hubs (the subsystems), skip
thin localization/bridge modules unless asked.
