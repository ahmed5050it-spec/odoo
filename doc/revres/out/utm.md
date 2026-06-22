# utm — UTM Trackers (Campaign/Source/Medium Attribution Backbone)

## 1. Overview
`utm` is cross-cutting marketing infrastructure: it owns the campaign/source/medium
reference data and the `utm.mixin` trait that stamps attribution onto any record
that inherits it (leads, mailings, tracked links, social posts). It is not run
standalone in practice — it is the attribution backbone consumed by `mass_mailing`,
`crm`, `sale` and `link_tracker`. Manifest: category **Marketing**, version 1.1,
depends `['base', 'web']`, LGPL-3, `auto_install=false`, `application=false`.
900 Python LOC / 458 XML LOC, 7 models, 0 routes.

## 2. Data model (information concepts)
Seven models — five concrete reference tables plus two abstract mixins (and an
`ir.http` inherit-only extension):
- **utm.campaign** (8 fields) — the campaign: translatable `title` (`_rec_name`),
  unique computed `name`, `user_id` (Responsible), `stage_id`->utm.stage,
  `tag_ids`->utm.tag, `is_auto_campaign`, `color`. SQL `UNIQUE(name)`.
- **utm.source** (1 field, `+ utm.source.mixin`) — link source; `UNIQUE(name)`.
- **utm.medium** (2 fields, `_order='name'`) — delivery method; `UNIQUE(name)`.
- **utm.tag** (2 fields) / **utm.stage** (2 fields, `_order='sequence'`) — campaign
  categorization and Kanban pipeline columns.
- **utm.mixin** (AbstractModel, 3 m2o) — `campaign_id`/`source_id`/`medium_id`
  (all `index='btree_not_null'`); the attribution trait inherited downstream.
- **utm.source.mixin** (AbstractModel) — `source_id` + related `name`; auto-creates
  a `utm.source` per host record (mailing/social post).

Key relations: `utm.mixin -> {campaign,source,medium}`, `campaign -> stage`,
`campaign -> tag`, `campaign -> res.users`, `source.mixin -> source`.

## 3. Routes / services
No own HTTP routes (`route_count=0`). Coupling is via the `ir.http` dispatch hook,
not a controller: `ir.http._post_dispatch -> _set_utm` runs on every request and
sets attribution cookies (see §4). All UI is backend ORM views.

## 4. Behavioral notes (code-read — the metadata gap)
- **Cookie + query-param attribution:** `ir.http._set_utm` reads `utm_campaign`/
  `utm_source`/`utm_medium` GET params and writes them into long-lived (31-day,
  host-scoped) optional cookies `odoo_utm_*`. On create, `utm.mixin.default_get`
  walks `tracking_fields()` and back-fills `campaign_id/source_id/medium_id` from
  those cookies, resolving strings via `_find_or_create_record`. Skipped for
  internal salespeople (`group_sale_salesman`) unless superuser.
- **find_or_create_record / _find_or_create_record:** frontend wrapper (website_links)
  returns `{'id','name'}` because `call_kw`'s create magic is bypassed. For the
  UTM comodels (`_tracking_models()`) it does a case-insensitive
  `('name','=ilike')` `active_test=False` search and creates only if missing,
  flagging `is_auto_campaign=True` for campaigns; other models do a plain create.
- **Uniqueness backbone (`_get_unique_names`):** campaign/source/medium all route
  `create()` through it; it appends a bracketed counter (`test` -> `test [2]`) so
  duplicates never collide with the `UNIQUE(name)` constraint. `utm.campaign.name`
  is computed from `title` with `utm_check_skip_record_ids=self.ids` so a record
  never bumps its own counter. Pure-Python (regex `_split_name_and_count`).
- **Kanban stages + source-name generation + delete guards:** `utm.campaign` uses
  `utm.stage` (`ondelete='restrict'`, default = first stage) with
  `_group_expand_stage_ids` so empty stages still render. `utm.source.mixin`
  derives source names from the host `_rec_name` via `_generate_name`. Six
  reference mediums (Email/Direct/Website/X/Facebook/LinkedIn) and the 'Referral'
  source are delete-protected via `@api.ondelete`.

## 5. Frontend (static)
Effectively none (`frontend.present=true` but trivial): 1 JS file
(`utm_campaign_kanban_examples.js`), 0 XML templates, 0 OWL components, 0 patches,
1 registry add `kanban_examples:utm_campaign`, single bundle
`['web.assets_backend']`. The JS only seeds Kanban "examples" (starter stage
layouts) for the campaign board; there are no client components or services.

## 6. Integrations
No outbound HTTP/SDK/api-key usage (`integrations_gap7`: `http_call_sites=0`,
`sdk_imports=[]`, `uses_api_keys=false`, no endpoints/files). External coupling is
inbound only — `utm_*` query params on incoming web requests — and otherwise
intra-Odoo (the mixin is consumed by mass_mailing/crm/sale/link_tracker/social).

## 7. Classification
- **value_model: support** — cross-cutting marketing-attribution mixin + reference
  data used by many primary marketing/sales modules; foundational, owns no
  value-creating document chain of its own.
- **activity_class: support.**
- **apqc_category: 3.0 Market and Sell Products and Services** (campaign
  attribution / marketing administration).
- *Rationale:* its business contribution is marketing measurement/administration,
  not order or cash flow; it exposes no operational service, only a trait other
  modules inherit. `strategy=null` (human).

## 8. Fit-to-Standard
- **Standard:** campaign/source/medium/tag/stage reference data with enforced
  unique names; the `utm.mixin` attribution trait; cookie+URL-param attribution via
  `ir.http`; campaign Kanban with configurable stages; free-text find-or-create.
- **Typical fits:** attributing leads/mailings/links to campaign/source/medium;
  last-touch web attribution via `utm_*` params; campaign pipeline with tags/owner.
- **Common gaps:** no multi-touch/weighted attribution (last cookie wins); no
  campaign budget/spend/ROI; no analytics views of its own (pivot/graph 0 — reporting
  comes from consumers); backend-only, no portal/public UI.
- **Drive hints:**
  `env['utm.campaign'].search([],limit=5).mapped(('name','title','stage_id.name'))`;
  `env['utm.mixin']._get_unique_names('utm.campaign',['Promo','Promo','Promo'])`
  (→ `['Promo','Promo [2]','Promo [3]']`);
  `env['utm.source']._find_or_create_record('utm.source','Newsletter')`;
  `curl 'http://localhost:8069/web/login?utm_campaign=Promo&utm_source=newsletter' -c jar.txt`
  (sets `odoo_utm_*` cookies).
