# base_geolocalize — Reverse-Engineering Brief

`base_geolocalize` (manifest name "Partners Geolocation", category Sales/Sales,
v2.1, LGPL-3) adds address-to-coordinates enrichment to Odoo. It is **not** an
application and **not** auto_install; it depends only on `base_setup`. It owns just
two technical objects — `base.geo_provider` (a provider record) and the
`base.geocoder` AbstractModel — and extends `res.partner` and `res.config.settings`.
It is master-data enrichment infrastructure: it calls an **external geocoding
service** (OpenStreetMap Nominatim by default, optionally Google Maps) to resolve a
partner's address to a `(latitude, longitude)` pair that downstream CRM/mapping
features consume. It owns no business entity of its own.

## Role & Dependencies
- **base_setup** — provides the general-settings (`res.config.settings`) surface this
  module extends to choose the geo provider and store the Google Maps API key. The
  Sales/Sales category reflects where the coordinates are *consumed* (partner maps,
  territory assignment), not a sales activity the module itself runs.

Capability added: a pluggable forward/reverse geocoder (provider chosen by an
`ir.config_parameter`) that stamps `partner_latitude`/`partner_longitude` and a
`date_localization` on partners over an outbound HTTP call.

## Data Model (the ERM)
Two own models plus two `_inherit` extensions:

| Model | Kind | Adds | Key relation |
|-------|------|------|--------------|
| `base.geo_provider` | own | `tech_name`, `name` | selected via `ir.config_parameter base_geolocalize.geo_provider` |
| `base.geocoder` | AbstractModel | 10 methods, 0 fields | `_get_provider()` -> `base.geo_provider` |
| `res.partner` (`_inherit`) | extension | `date_localization` (Date) | resets `partner_latitude/longitude` on address change |
| `res.config.settings` (`_inherit`) | extension | `geoloc_provider_id`, `geoloc_provider_techname`, `geoloc_provider_googlemap_key` | `geoloc_provider_id->base.geo_provider` |

Field footprint is tiny (4 Char, 1 Date, 1 Many2one); the logic mass is in
`base.geocoder`'s 10 methods, not in fields. `partner_latitude`/`partner_longitude`
themselves live on the base partner — this module adds only `date_localization` and
the invalidation rule.

## Behavior & Surfaces
- **Routes:** none (0). Exposed as ORM services: `res.partner.geo_localize()`,
  `base.geocoder.geo_find()` / `geo_query_address()`.
- **Views:** 1 form (the inherited settings provider + Google-key panel). No
  list/kanban/search/etc.
- **Frontend:** none — `present=false`, 0 JS/OWL/XML, no asset bundles, no registry
  adds or patches. Entirely server-side.
- **Security:** 1 access rule, 0 record rules, 0 groups (just the `base.geo_provider`
  ACL).
- **Integrations (gap #7):** 3 outbound HTTP call sites in `models/base_geocoder.py`,
  SDK `requests`, `uses_api_keys=true` (Google key via `ir.config_parameter`).
  Endpoints: `https://nominatim.openstreetmap.org/search` (forward),
  `.../reverse` (reverse), `https://maps.googleapis.com/maps/api/geocode/json`.

Behavioral facts metadata cannot show (code-read): (1) `geo_localize` -> `_geo_localize`
-> `geo_find` dispatches on the provider's `tech_name` to `_call_openstreetmap` /
`_call_googlemap`, does an outbound GET, and on success writes lat/long +
`date_localization` (on failure, a coarser city/state/country retry, then a `danger`
bus notification of unmatched partners); (2) provider + key come from
`ir.config_parameter` (`geo_provider`, `google_map_api_key`), Google raising a UserError
if no key; (3) `res.partner.write` resets `partner_latitude/longitude=0.0` whenever the
address changes, keeping coordinates consistent; (4) error handling — unknown provider
-> UserError, transport errors -> `_raise_query_error` UserError, other exceptions
swallowed to `None` so one bad address never aborts a batch; reverse OSM calls disabled
under tests.

## Value-Configuration Classification
**Support** (Stabell & Fjeldstad), **activity_class = support**. It is firm IT
infrastructure — a data-enrichment / external-integration utility that adds one derived
attribute (GPS coordinates) to master data. It transforms no document (not chain),
resolves no engagement (not shop) and mediates no party-to-party exchange (not network).

## APQC PCF Hint
**8.0 Manage Information Technology.** The module is a data-management / external-
integration service (provider configuration, API-key handling, outbound HTTP enrichment
of the partner record). The Sales/Sales manifest category reflects the *consumer* of the
coordinates, not the activity the module performs, so 8.0 is the dominant fit.

## How to Drive It
Use the **run-odoo** skill (`odoo shell`):
- `env['base.geo_provider'].search([]).mapped(('name','tech_name'))` — available providers.
- `env['ir.config_parameter'].sudo().get_param('base_geolocalize.geo_provider')` — selected provider id.
- `p = env['res.partner'].create({'name':'Geo Test','street':'1 Infinite Loop','city':'Cupertino','country_id':env.ref('base.us').id}); p.with_context(force_geo_localize=True).geo_localize(); (p.partner_latitude, p.partner_longitude, p.date_localization)` — geocode then read coordinates.
- `env['ir.config_parameter'].sudo().set_param('base_geolocalize.google_map_api_key','...')` — enable the Google provider.

## Open Questions
- Which downstream modules actually consume `partner_latitude/longitude` (CRM partner
  assignment, delivery routing, website map)?
- How are Nominatim rate limits / Terms of Use handled for production batch geocoding
  (no throttling or cron shipped here)?
- Exact set of seeded `base.geo_provider` records and their `tech_name`s loaded by the 5
  data files.
- Are `partner_latitude/longitude` defined here or in a base/CRM dependency (this module
  adds only `date_localization` and the reset rule)?

---
*Provenance: structural facts from `extract_module.py` (`facts/base_geolocalize.facts.json`);
frontend/integration facts from `extract_frontend.py` (`frontend/base_geolocalize.frontend.json`);
behavioral notes from code-read of `models/base_geocoder.py`, `models/res_partner.py`,
`models/res_config_settings.py`. Odoo 19.0.*
