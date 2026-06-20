# website_links — Link Tracker (UTM-Tagged Trackable / Short-URL Builder on the Website)

## 1. Overview
`website_links` is the website-facing UI for minting **trackable short URLs**: a
marketer enters a destination URL, tags it with a UTM campaign/source/medium, and
gets a branded `/r/<code>` short link plus click statistics. It is a thin
route + OWL/JS layer over the `link_tracker` engine — it owns no new model, only an
inherit of `link.tracker`. Manifest: name **Link Tracker**, category
**Website/Website**, summary "Generate trackable & short URLs", depends
`['website', 'link_tracker']`, LGPL-3, **`auto_install=true`**, `application=false`.
280 Python LOC / 323 XML LOC, 1 inherit-only model, 5 routes, 3 ACL rules.

## 2. Data model (information concepts)
No new model is declared — the module only extends `link.tracker` (`models/link_tracker.py`,
2 methods, 0 new fields). The data objects it operates on live in `link_tracker`:
- **link.tracker** — the tracked link: `url`, computed `short_url` / `short_url_host` /
  `code`, aggregated click `count`, and UTM `campaign_id`/`source_id`/`medium_id`
  (via `utm.mixin`). website_links overrides `_compute_short_url_host` to be
  multi-website aware.
- **link.tracker.code** — short code(s) for a link; `UNIQUE(code)`, `ondelete=cascade`
  to `link_id`. One link can carry several codes.
- **link.tracker.click** — one click event; `link_id` + `campaign_id` (related, stored)
  + geoip `country_id`; the source of all `count` / chart statistics.

Key relations: `link.tracker -> utm.campaign/source/medium`,
`link.tracker.code -> link.tracker`, `link.tracker.click -> link.tracker`,
`link.tracker.click -> utm.campaign`.

## 3. Routes / services
Five routes (`controller/main.py`), all `auth=user`:
- **`POST /website_links/new`** (jsonrpc) — create-or-find a link via
  `link.tracker.search_or_create([post]).read()`; returns `{error:'empty_url'}` on blank.
- **`/website_links/recent_links`** (jsonrpc) — `link.tracker.recent_links(filter, limit)`,
  filters `newest` / `most-clicked` / `recently-used`, with click counts.
- **`/website_links/add_code`** (jsonrpc) — add an alternate `link.tracker.code` to a link.
- **`/r`** (http, website) — link-builder landing page (`website_links.page_shorten_url`).
- **`/r/<code>+`** (http, website) — per-link statistics page (`website_links.graphs`).

The click-recording redirect **`/r/<code>` is NOT here** — it lives in `link_tracker`
(see §4).

## 4. Behavioral notes (code-read — the metadata gap)
- **`/website_links/new` -> `search_or_create`:** the post dict (url + label +
  campaign/medium/source ids) is run through `link.tracker.search_or_create`, which
  validates/normalizes the URL and **dedups on `LINK_TRACKER_UNIQUE_FIELDS`** — the
  same URL+UTM combo returns the *existing* short link instead of a duplicate. The
  `read()` dict (`short_url`, `short_url_host`, `code`, `count`) is what the OWL UI renders.
- **`/website_links/recent_links` -> click stats:** proxies `recent_links(filter, limit)`,
  ordering by `create_date` (newest), or `count DESC` / `write_date DESC` restricted to
  `count != 0` (most-clicked / recently-used). `count` is aggregated from
  `link.tracker.click` rows, so the panel and the `/r/<code>+` charts surface live stats.
- **Short-code redirect dependency on `link_tracker`:** the public
  `/r/<string:code>` route is owned by the parent `link_tracker` controller; each hit
  calls `link.tracker.click.sudo().add_click(code, ...)` (geoip country, UTM) then
  redirects via `get_url_from_code -> redirected_url`. website_links adds only the
  authenticated `/r/<code>+` *stats* page — the `+` suffix is the convention separating
  a redirect from its statistics view. The link's value chain thus spans two modules:
  `link_tracker` captures+redirects, `website_links` mints and reports.
- **`/website_links/add_code`:** resolves a link from the init code's `link.tracker.code`,
  then creates a new code row (UNIQUE) pointing at the same `link_id` — multiple codes,
  one destination.
- **`_compute_short_url_host` override:** binds the short-URL host to the *current
  website's* base URL when it matches the company `website_id`, else the company base
  URL — making `/r/` links multi-website aware.

## 5. Frontend (static)
The whole builder UX is client-side (metadata gap #3): **5 JS files, 2 XML templates**,
one OWL component **WebsiteLinksTagsWrapper** (UTM campaign/medium/source autocomplete
with find-or-create), and three `public.interactions` — **WebsiteLinks** (create form +
recent-links list), **WebsiteLinksCharts** (Chart.js all-time/month/week clicks +
per-country pie charts), **WebsiteLinksCodeEditor** (inline short-code rename). A
`website.assets_editor` service registers the **Link Tracker** website custom menu
(`website_custom_menus:website_links.menu_link_tracker`). Bundles:
`web.assets_frontend` ×4, `web.assets_tests` ×1, `website.assets_editor` ×1.

## 6. Integrations
None outbound: `http_call_sites=0`, no SDK imports, no API keys, no external endpoints.
All "integration" is internal Odoo coupling — `website` (multi-website base URL,
custom menu) and `link_tracker`/`utm` (the link + UTM data engine).

## 7. Classification
- **value_model: network** — mediating-technology layer for marketing-link
  distribution. `/r/<code>` links mediate between a campaign and an open population of
  recipients/visitors, link the two parties, and capture each contact (click) for
  attribution; worth grows with links shared and audience reached.
- **activity_class: primary** — minting and operating the tracked-link channel
  (create / redirect / measure) is the value the module exists to deliver, not back-office.
- **apqc_category: 3.0 Market and Sell Products and Services** — the artifact is
  campaign reach/attribution tooling (UTM-tagged trackable links measuring marketing-channel
  effectiveness), squarely demand-side marketing measurement.
- Note: `utm` reference data is classed *support*; `website_links` is the public-facing
  operational tool distributing/measuring the links, hence *primary* here.

## 8. Fit-to-Standard
**Standard (out of box):** self-service `/r` page to generate UTM short links;
find-or-create dedup; click capture + redirect (`/r/<code>`, geoip); recent-links panel
(newest / most-clicked / recently-used); per-link stats page with click + per-country
charts; custom/alternate codes; multi-website-aware host.
**Typical fits:** marketers minting links for campaigns/ads/social; attributing inbound
traffic; sharing branded short links; feeding `utm.campaign.click_count`.
**Common gaps:** no QR-code / A/B rotation / expiry; analytics limited to count +
country/time-window (no device/referrer); designer-group gated (no public self-service);
no external-shortener / GA-event push; no bot/duplicate-click filtering or unique-visitor
metrics.
**Drive (run-odoo):**
`env['link.tracker'].search_or_create([{'url':'https://odoo.com','campaign_id':False}]).read(['short_url','code'])` ·
`env['link.tracker'].recent_links('most-clicked', 5)` ·
`curl -i 'http://localhost:8069/r/<CODE>'` (public redirect, registers a click) ·
`curl -s 'http://localhost:8069/r/<CODE>+'` (auth stats page).
