# base — Architecture Brief (revres)

> The Odoo **kernel**. `auto_install=true`, `depends=[]`, `category=Hidden`,
> version 1.3. The root of the dependency graph: every other module builds on it.
> Value model **support** · activity class **support** · APQC **8.0 Manage IT**.

## 1. Overview

`base` (`odoo/addons/base/`) is the firm-infrastructure layer of Odoo expressed as
software. It supplies the ORM and its self-describing metamodel (`ir.model`,
`ir.model.fields`), the security/access engine (`ir.model.access`, `ir.rule`,
`res.groups`), the identity and organization primitives (`res.users`,
`res.company`), the central contact master (`res.partner`), world reference data
(currencies, countries, states, languages), module lifecycle management, the cron
scheduler, attachment store and QWeb engine. 124 models, 66,392 Python LOC,
12,940 XML LOC, 65 data files, 0 HTTP routes (it is a pure server kernel).

## 2. Structural facts (evidence — auto)

- **Models:** 124 (2 inherit-only). Two families: `ir.*` (framework/Information
  Repository) and `res.*` (business resources). Field totals dominated by Char
  (260), Many2one (106), Boolean (97).
- **Security:** 146 model-access ACLs, 32 record rules, 12 groups — base defines
  the privilege lattice the whole platform inherits.
- **Views:** 66 form, 67 list, 39 search, 9 kanban, 1 calendar. **Routes:** none.
- **Manifest:** `depends=[]`, `auto_install=true` — the only true root module.

## 3. Frontend & integrations (evidence — static)

- **Frontend:** effectively none — 0 JS, 0 OWL/XML templates, 0 registry adds, 0
  patches; only one `web.assets_tests` bundle entry. All client UI lives in the
  separate `web` module. base is server/ORM/data only.
- **Integrations:** 1 outbound HTTP call site, imports `requests`, uses API keys.
  Endpoints are mostly XML namespaces/placeholders; the real outbound call is an
  open question (likely a webhook server action or avatar fetch).

## 4. Runtime (evidence — live, source: runtime)

On a freshly initialized DB, base alone populates **43 of 67** probed models. Top
rows: `ir.model.data`=**6828** (the XML-ID registry), `res.country.state`=2131,
`ir.model.fields`=1645, `ir.module.module.dependency`=1400,
`ir.model.fields.selection`=854, `ir.module.module`=670, `ir.model.constraint`=376,
`res.country`=**251**, `ir.ui.view`=229, `ir.model.access`=152, `ir.model`=129.
Singletons seeded: 1 `res.company` (My Company), 1 `res.currency` (USD), 1
`res.lang` (en_US), 1 `res.users` (Administrator). This is the substrate every
other module starts from.

## 5. Behavioral notes (evidence — code-read)

- **XML-ID resolution** (`ir.model.data._xmlid_lookup`): `module.name` → SQL on
  `ir_model_data` → `(res_model, res_id)`. Powers `ref=`, modular upgrade, and
  clean uninstall — pure data, invisible to field metadata.
- **`res.users._inherits = {'res.partner': 'partner_id'}`**: delegation, not
  classical inheritance — a user IS-A partner; name/email/lang/avatar live on the
  partner. `SELF_READABLE_FIELDS`/`SELF_WRITEABLE_FIELDS` gate self-service.
- **Self-describing metamodel** (`ir.model` / `ir.model.fields`): the ORM persists
  its own schema, enabling runtime introspection, Studio custom fields, and
  security attachment via `model_id`.
- **`res.company` hierarchy** (`root_id`/`parent_ids`, `_check_company_domain`):
  self-referential company tree underpinning multi-company record isolation
  across the entire ERP.

## 6. IT architecture (synthesis)

`application` = the kernel. No software services as HTTP routes — the ORM/registry
*is* the in-process service layer plus `ir.http` routing hooks consumed by others.
Key ERM: `ir.model.fields → ir.model`; `ir.model.access`/`ir.rule → ir.model +
res.groups`; `res.users -inherits→ res.partner`; `res.company → res.partner +
res.currency` and self-referential `parent_id`; `ir.model.data → any model`
(polymorphic `res_id`). Information flows radiate outward: every module depends on
base and extends its `ir.*`/`res.*` models; `ir.cron` drives scheduled
`ir.actions.server` across all installed modules.

## 7. Business architecture (synthesis)

- **Information concepts (auto):** res.partner, res.company, res.currency,
  res.country(.state), res.lang, res.bank — base *defines* these primitives.
- **Organization (auto):** base is special — it DEFINES the Organization domain
  itself: `res.users` and `res.groups` (plus `res.groups.privilege`) are declared
  here, with the seeded admin user, My Company, and base groups.
- **Capabilities (inferred):** persist the data model; access control & record
  rules; manage users/auth; multi-company; master contact data; reference data;
  module lifecycle; scheduling; file storage.
- **Policies (inferred):** 146 ACLs, 32 record rules (incl. multi-company
  isolation), 12-group privilege lattice, autovacuum/portal-deletion crons.
- **Products:** none. **Strategy:** null (human). **Metrics (inferred):** module
  reference report, `ir.profile`, `ir.logging`.

## 8. Classification & Fit-to-Standard

- **value_model = support · activity_class = support · APQC = 8.0 Manage IT.**
  Stabell & Fjeldstad: pure firm infrastructure / technology development, never a
  primary value activity. `auto_install=true`, `depends=[]` confirm it is the
  kernel. APQC 8.0 (application platform, data management, security admin) is the
  dominant character; **13.0 Develop & Manage Business Capabilities** is a
  secondary read because base also defines the Organization and Information-Concept
  primitives.
- **Standard capabilities:** self-describing ORM, XML-ID registry, ACL + record
  rules, users/groups/multi-company, reference data, module lifecycle, cron,
  attachments, QWeb.
- **Common gaps:** custom groups/record rules, extra reference/rate data,
  `_inherit` extensions of res.partner/res.users, external SSO / password policy.
- **Drive hints:** `env['ir.model'].search_count([])`,
  `env['res.country'].search_count([])` (~251),
  `env.ref('base.user_admin').partner_id` (delegation demo).

*Sources: facts/base.facts.json, frontend/base.frontend.json,
runtime/base.runtime.json, code-read of ir_model.py / res_users.py /
res_company.py, doc/BASE_MODULE.md. Odoo 19.0.*
