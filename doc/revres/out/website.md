# website — Reverse-Engineering Brief

`website` is Odoo's enterprise **website builder** and web-presence platform: an in-browser, drag-and-drop CMS that turns QWeb templates into public pages, menus and themes, with multi-website / multi-language routing, SEO tooling and visitor analytics. It is an `application` (top-level app), **not** `auto_install`. It sits high in the dependency graph, building on `web`, `html_editor`/`html_builder` (the editor), `http_routing` (frontend URL dispatch), `portal`, `auth_signup`, `mail`, `social_media`, `utm`, `google_recaptcha` and `digest`. 35 models (27 are pure `_inherit` extensions), 57 routes, ~21k Python LOC and ~24k XML LOC — but its real mass is the frontend: ~350 JS files and 152 XML templates.

## Role & Dependencies
- **web** — base web client/asset framework the builder UI and backend views run on.
- **html_editor** / **html_builder** — the WYSIWYG editor and snippet/builder engine that `website` skins into the page editor (`website.assets_wysiwyg`, `website.assets_editor`).
- **http_routing** — frontend URL dispatch, slugs and language URL codes; `website` overrides `ir.http` to make routing multi-website-aware.
- **portal** — authenticated customer-facing pages and account area extended by website pages.
- **auth_signup** — public visitor self-signup (`auth_signup_uninvited` on `website`).
- **mail** / **utm** / **social_media** — messaging, campaign tracking and social links surfaced on the site.
Capability added on top: a full CMS layer — `website`, `website.page`, `website.menu` plus the QWeb rendering, SEO, redirect and visitor-tracking machinery — that none of the dependencies provide alone.

## Data Model (the ERM)
| _name | _description | #fields | key relations |
|-------|--------------|---------|---------------|
| `website` | Website | 44 | company_id→res.company, user_id→res.users (public user), theme_id→ir.module.module, menu_id→website.menu |
| `website.page` | Page | 13 | view_id→ir.ui.view (_inherits), website_id→website, menu_ids→website.menu |
| `website.menu` | Website Menu | 15 | page_id→website.page, parent_id→website.menu, website_id→website |
| `website.controller.page` | Model Page | 9 | view_id/record_view_id→ir.ui.view |
| `website.visitor` | Website Visitor | 21 | website_id→website, partner_id→res.partner, website_track_ids→website.track |
| `website.track` | Visited Pages | 4 | visitor_id→website.visitor, page_id→website.page |
| `website.rewrite` | Website rewrite | 8 | website_id→website, route_id→website.route |
| `website.snippet.filter` | Website Snippet Filter | 8 | action_server_id→ir.actions.server, filter_id→ir.filters |

The **central/aggregate** model is `website`, with **111 methods** — it owns routing resolution, caching, theming and configuration. The **content core** is `website.page`, which `_inherits` `ir.ui.view` (its `view_id`): a page is a thin URL/SEO wrapper whose `arch` is a related field on the QWeb view. Many entries are **mixins/extensions** (`_inherit` without `_name`): `website.published.mixin`, `website.seo.metadata`, `website.multi.mixin`, plus extensions of `ir.http`, `ir.qweb`, `ir.ui.view`, `res.users`, `res.config.settings`. The `theme.*` models mirror the live models to ship installable themes. Field types are **attribute-heavy** (Char 96, Boolean 56) with a strong relational spine (Many2one 51) — consistent with a configuration/content platform rather than a transactional ledger.

## Behavior & Surfaces
- **Routes (57):** a wide public web surface — page listing (`/pages`), site search (`/website/search`), SEO crawler endpoints (`/robots.txt`, `/sitemap.xml`, `/favicon.ico`), responsive images (`/website/image/...`), website forms (`/website/form/...`), and switching (`/website/force/<id>`, `/website/lang/<lang>`). Authoring/customization endpoints (`/website/add`, `/website/save_xml`, `/website/configurator`, `/website/theme_customize_data*`) are `auth="user"` JSON-RPC; snippet data feeds (`/website/snippet/*`) are mostly `public` JSON-RPC.
- **Views:** form (14) and list (11) dominate the backend, with kanban (4), search (7) and graph (3) — but the **primary UX is the frontend builder**, not backend views.
- **Security posture:** 44 access rules, **8 record rules**, 5 groups (`group_website_designer`, `group_website_restricted_editor`, `group_multi_website`, `group_website_publisher`, public user). Record rules enforce website scoping (`website_id in [False, current]`) plus published/visibility-group page access.

### Behavior metadata cannot show (code-read)
- **Multi-website routing:** `website.get_current_website()` resolves the active site by precedence (session `force_website_id` → context → request-domain match via `_get_current_website_id` → first-website fallback); `website_domain()` returns `Domain('website_id','in',[False,*ids])` so every scoped query transparently merges generic and site-specific records.
- **QWeb page rendering:** `ir.http._serve_fallback → _serve_page → website.page._get_response` looks up the page by URL (specific-website-first) and renders its `ir.ui.view` via `request.render()`; public GETs are memoised in an ORM cache (`templates.cached_values`, 3600s TTL) with CSRF re-injection on hits.
- **Visitor tracking side-effect:** `_post_dispatch → _register_website_track → website.visitor._handle_webpage_dispatch` silently creates/updates a `website.visitor` and appends a `website.track` row on every tracked 200 response (geoip-derived country/timezone, written via `FOR NO KEY UPDATE SKIP LOCKED`).
- **Frontend (gap #3):** ~350 JS files / 152 XML templates, 40 OWL components (`Configurator`, page/menu dialogs, fullscreen editor), 40+ `public.interactions.edit` snippet behaviours, 20+ editor prototype patches, 22 asset bundles — almost the entire UX lives client-side.
- **External integrations (gap #7):** outbound to `geoip2`, `plausible.io` / Google Analytics, Google fonts & maps, and odoo.com (`website.api.odoo.com`, `olg.api.odoo.com`) for the configurator/IAP.

## Value-Configuration Classification
**Value model: `network` (mediating technology).** `website` is the platform/infrastructure that mediates between the organization and an open population of visitors, and between visitors and published content / forms / other apps (shop, blog, event, livechat). Its value is mediating-and-infrastructure — routing requests to the right site, rendering pages, linking parties via menus/forms — and it **grows with participants** (visitors, published pages, connected apps). That is a network, not a sequential transform (chain) or a problem-solving cycle (shop). **Activity class: `primary`** — operating that mediating infrastructure (the request → render → track service and the web presence itself) *is* the service the module delivers, not a back-office support function.

## APQC PCF Hint
**3.0 Market and Sell Products and Services.** The platform's primary purpose is the public-facing market presence — content publishing, SEO and lead/visitor capture (a demand-side marketing channel). It was weighed against **6.0 Manage Customer Service**, but customer-service flows (livechat, helpdesk) are optional add-on modules, whereas web-presence/marketing is `website`'s reason to exist; hence 3.0 is the better fit.

## How to Drive It
Use the **run-odoo** skill. Query the core models via `odoo shell`:
- `env['website'].search([]).mapped(('name','domain'))`
- `env['website'].get_current_website().website_domain()`
- `env['website.page'].search([], limit=5).mapped(('url','is_published'))`
- `env['website.visitor'].search_count([])`

Curl the public surface: `curl -s http://localhost:8069/sitemap.xml | head` and `curl -s http://localhost:8069/robots.txt`.

## Open Questions
- Which `ir.ui.view` templates carry `track=True` and therefore actually trigger visitor creation in a live DB (static facts can't tell).
- How `website.rewrite` redirect rules interact at scale with module-specific routes (shop/blog/event).
- Live row counts for `website.visitor` / `website.track` — `extract_runtime.sh` was not run.
- The full ~350-file snippet/interaction catalog; only a representative subset was statically captured.

---
*Provenance: extract_module.py + extract_frontend.py facts (`facts/website.facts.json`, `frontend/website.frontend.json`) plus code-read of `models/website.py`, `models/ir_http.py`, `models/website_page.py`, `models/website_visitor.py`. Odoo 19.0.*
