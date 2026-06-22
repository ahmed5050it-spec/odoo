# link_tracker — Tracked Short Links / UTM Click Tracking

## 1. Overview
`link_tracker` is cross-cutting marketing infrastructure that wraps any URL into a
trackable short link (`/r/<code>`), counts clicks, attributes them to UTM
campaign/medium/source, and geo-locates each click by country. It is not used
standalone in practice: it is the click-tracking engine consumed by `utm`,
`mass_mailing` and `website`. Manifest: category **Marketing**, version 1.1,
depends `['utm', 'mail']`, LGPL-3, `auto_install=false`, `application=false`.
1373 Python LOC / 234 XML LOC.

## 2. Data model (information concepts)
Three own models (plus inherit-only extensions of `utm.campaign` and
`mail.render.mixin`):
- **link.tracker** (14 fields, `_inherit=utm.mixin`, `_order="count DESC"`) — the
  tracked link: `url`, computed `short_url`/`redirected_url`/`absolute_url`,
  `code`, stored `count`, `link_code_ids`, `link_click_ids`, UTM
  campaign/medium/source (all `ondelete='set null'`).
- **link.tracker.click** (4 fields) — one row per recorded click: `link_id`,
  stored-related `campaign_id`, `ip`, `country_id`.
- **link.tracker.code** (2 fields) — `code` (unique SQL constraint) + `link_id`;
  separates the public short code from the link so codes can be rotated.

Key relations: `code -> link.tracker`, `click -> link.tracker`,
`link.tracker -> utm.campaign`, `click -> res.country`.

## 3. Routes / services
One public HTTP route (in `controller/main.py`, outside `models/`, so the
models-only facts extractor reported `route_count=0` — the route is real):
- **`GET /r/<string:code>`** (`type=http`, `auth=public`, `website=True`) —
  resolves the code, records a click, and 301-redirects to the destination.

## 4. Behavioral notes (code-read — the metadata gap)
- **Short-code generation:** `link.tracker.create` mints a random
  `ascii_letters+digits` code via `link.tracker.code._get_random_code_strings`
  (min length 3; widens size on collision), guarded by a `unique('code')`
  constraint. `short_url = base_url + '/r/' + code`.
- **Redirect + click side-effect:** `full_url_redirect` calls
  `link.tracker.click.add_click` (CREATING a `link.tracker.click`) then 301s to
  `redirected_url`, or raises 404 if the code is unknown.
- **GeoIP on click:** controller forwards `request.geoip.country_code` +
  `remote_addr`; `_prepare_click_values_from_route` maps the country code to a
  `res.country`. `is_a_bot()` gates logging so crawler hits are not counted.
- **UTM attribution:** `_compute_redirected_url` appends `utm.mixin`
  tracking fields as `utm_*` GET params on the target; system param
  `link_tracker.no_external_tracking` limits injection to local destinations.
- **Mass-mailing integration:** `tools/html.find_links_with_urls_and_labels`
  walks an lxml body and absolutizes/labels each `<a>`, so mailing links are
  wrapped into tracked short links; `convert_links` now lives on
  `mail.render.mixin`. `utm.campaign` gains a `click_count` aggregate.

## 5. Frontend (static)
No OWL/JS (`extract_frontend: present=false`; 0 JS files, 0 templates, no
registry adds/patches). UI is server-rendered backend views only:
list/form/graph for `link.tracker` and a country-grouped **pie** "Click
Statistics" graph for `link.tracker.click`. The menu is parented under
`utm.menu_link_tracker_root` and gated to `base.group_no_one` (technical users).

## 6. Integrations
No outbound HTTP/SDK/api-key usage (`integrations_gap7`: `http_call_sites=0`,
`sdk_imports=[]`, `uses_api_keys=false`). External coupling is inbound (the
public redirect) and intra-Odoo (utm/mail consumers); GeoIP comes from the
host's `request.geoip` provider, not an external API call site.

## 7. Classification
- **value_model: support** — click-tracking infrastructure with no primary
  value-creating document chain; consumed by marketing/mass_mailing/utm.
- **activity_class: support.**
- **apqc_category: 3.0 Market and Sell Products and Services** (specifically
  **3.4 Measure and evaluate marketing performance** — clicks, UTM attribution,
  geo).
- *Rationale:* its business contribution is marketing measurement, not order or
  cash flow; it exposes a single redirect service rather than an operational
  pipeline. `strategy=null` (human).

## 8. Fit-to-Standard
- **Standard:** URL shortening with unique codes, click capture (IP + GeoIP,
  bot filtering), UTM tagging of destinations, link/campaign click counters,
  auto-conversion of mailing links into tracked links.
- **Typical fits:** tracking email-campaign clicks, measuring UTM reach by
  country, shortening + counting any backend URL.
- **Common gaps:** no per-click timestamp/session or unique-visitor dedup
  beyond ip+country; no public dashboard (backend graphs only, menu hidden);
  city/device/referrer analytics need customization.
- **Drive hints:** `env['link.tracker'].create({'url':'https://odoo.com'}).short_url`;
  `curl -i http://localhost:8069/r/<code>` (expect 301 + a new click row);
  `env['link.tracker.click'].search([],limit=5).mapped(('link_id.short_url','country_id.name'))`.
