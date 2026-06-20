# website_customer — Reverse-Engineering Brief

`website_customer` ("Customer References") publishes a public **"Our References / Customers"**
directory on the Odoo website: a curated, faceted, map-enabled listing of customer companies
used as marketing social proof. It is **not** `auto_install` and **not** an `application` — it is a
thin website extension (1 new model, ~288 py LOC, ~590 xml LOC) sitting on top of three
website bridges. In the dependency graph it is a leaf marketing feature of the website
storefront, classified `Website/Website`.

## Role & Dependencies

- **website_crm_partner_assign** — supplies `assigned_partner_id`; a partner is only treated as a
  publishable reference if it has an assigned reseller/partner.
- **website_partner** — supplies `website_description` (sanitized Html body) and the partner
  publishing plumbing used on the detail page.
- **website_google_map** — supplies the `GoogleMap` controller the module subclasses to plot
  references as geolocated map markers.

Capability added: turns published `res.partner` records into a searchable, industry/country/tag
faceted public reference directory with a Google map and per-reference SEO pages.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|-------------|---------|---------------|
| `res.partner.tag` | Partner Tags (find customers by sector) | 4 | `partner_ids` ↔ `res.partner` (m2m); `_inherit website.published.mixin` |
| `res.partner` (extension) | adds `website_tag_ids` | +1 | `website_tag_ids` ↔ `res.partner.tag` (m2m) |
| `website` (extension) | adds `/customers` suggested controller | 0 | — |

`res.partner.tag` is the only new model; it is a **published mixin** record (publishing color-coded
sector tags). The other two entries are `_inherit`-only **extensions** (no `_name`). Field mix is
relational-light (a Char name, a Selection bootstrap `classname`, an `active` flag, one m2m) — the
module reuses `res.partner` / `res.partner.industry` / `res.country` rather than modelling new data.

## Behavior & Surfaces

- **Routes (2 controllers):** the `/customers` family (8 path variants: base, `/page/<n>`,
  `/industry/<industry>`, `/country/<country>`, combined, all paginated) plus `/customers/<partner_id>`
  detail. All `auth="public"`, `type="http"`, `website=True`, with a `sitemap_industry` generator.
- **Listing logic (code-read):** domain `[('website_published','=',True),('assigned_partner_id','!=',False)]`;
  optional search (name / website_description / industry name), `tag_id`, industry & country facets stack on.
  Two `_read_group` calls build sidebar counts; `pager(step=20, scope=7)` paginates; everything runs `sudo()`.
  Empty-country requests gracefully fall back to all countries instead of 404.
- **Map (code-read):** `_get_gmap_domains` override feeds the Google Maps JSON endpoint with
  `assigned_partner_id` + current industry/country filters; `website.google_maps_api_key` passed to the template.
- **Views:** 2 form, 1 list, 1 search (backend tag admin); the public UX is server-rendered QWeb
  (`website_customer.index` / `.details`) with Bootstrap offcanvas filters — no OWL.
- **Security:** 6 access rules, 1 record rule, 0 groups.

## Value-Configuration Classification

- **value_model: `network`** — a value network (Stabell & Fjeldstad mediating technology): it publishes
  the customer population as a directory that mediates between prospects and existing customers; its
  worth grows with the number of published references/industries/countries (directory network effect).
  Not a transformation (chain) nor a problem-solving cycle (shop).
- **activity_class: `primary`** — the module's whole reason to exist is the public-facing marketing
  artefact, not a back-office support function. It aligns with the parent `website` (network/primary).

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — publishing curated customer references is a
demand-side marketing / social-proof activity that supports selling, not post-sale service (6.0).

## How to Drive It

Use the **run-odoo** skill. Curl the public pages and query the gating models:

- `curl -s 'http://localhost:8069/customers'` and `.../customers/page/2`
- `env['res.partner'].sudo().search_count([('website_published','=',True),('assigned_partner_id','!=',False)])`
- `env['res.partner.tag'].search([('website_published','=',True)]).mapped('name')`
- `env['res.partner'].sudo()._read_group([('website_published','=',True),('assigned_partner_id','!=',False)], ['industry_id'], ['__count'])`

## Open Questions

- Live row counts for `res.partner.tag` / published references (extract_runtime.sh not run).
- Whether the Google map degrades gracefully when `google_maps_api_key` is unset.
- Exact ACL/record-rule scope enabling public `sudo()` reads of reference data.

---
*Provenance: facts from `extract_module.py` + `extract_frontend.py`; behavioral notes from code-read of
`controllers/main.py`, `models/res_partner.py`, `models/website.py`, `website/models/mixins.py`. Odoo 19.0.*
