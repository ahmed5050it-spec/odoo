# http_routing — Architecture Brief

> Module: `http_routing` · Category: Hidden · Depends: `web` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/http_routing.facts.json` · Frontend: `doc/revres/frontend/http_routing.frontend.json`

## 1. Summary

`http_routing` is the **web URL-routing layer** — the thin, cross-cutting server
glue that turns pretty, multilingual URLs into controller calls and emits SEO-
friendly slug links back into rendered pages. It is structurally minimal: **0 own
models**, only **3 inherit-only extensions** (`ir.http`, `ir.qweb`, `res.lang`),
**~889 Python LOC / ~270 XML LOC**, **0 security**, and **no frontend/JS**. Its
entire substance is dispatch behavior in `models/ir_http.py`: slug generation/
parsing, language-prefix injection + 301/302 canonical redirects, request
rerouting, and branded frontend error pages. It owns no business object — it is
firm IT infrastructure every website/portal request transits.

## 2. Structure (evidence)

- **Models:** none of its own; 3 extensions — `ir.http` (22 methods: the routing/
  dispatch core), `ir.qweb` (2 methods: injects `slug`/`url_for`/`url_localized`
  into the render context), `res.lang` (1 method: `_get_frontend()`).
- **Routes (2):** `/website/translations` (public, `website=True`, `readonly`,
  translation bundle for the frontend) and `/web/session/logout` (website-aware
  override, `multilang=False`). Most behavior is in dispatch **hooks**, not routes.
- **Security:** none (0 access rules, 0 record rules, 0 groups).
- **Views:** no business views; ships QWeb error templates (`http_routing.4xx`,
  `.http_error`, per-code 404/500 pages) + a `res.lang` form extension.

## 3. Frontend (gap #3)

`extract_frontend.py` reports **present=false** — 0 JS files, 0 QWeb component
templates, 0 registry adds/patches/services/asset bundles. `http_routing` is a
**pure server-side routing/dispatch layer**; it ships no OWL widgets. Every
client-visible effect — slug URLs, `/<lang>/` prefixes, branded 404 pages — is
produced server-side via QWeb context helpers and HTTP redirects, not by browser
components. Integrations (gap #7): none — no outbound HTTP, SDKs, or API keys.

## 4. Behavior (beyond metadata)

- **`_slug`/`_unslug`/`ModelConverter`:** `_slug((14,'My Phone'))` → `my-phone-14`
  (falls back to bare id when the name is empty); `_unslug` reverse-parses via
  `_UNSLUG_RE`, tolerating no slug so `/foo/1` still resolves; `ModelConverter`
  browses the id (abs() fallback for negatives), letting `<model(...)>` routes
  accept human URLs. (code-read)
- **`_match` (9-case multilang dispatch):** resolves request lang (URL > cookie >
  context > website default) and applies 9 branches — inject `/<lang>` (302),
  strip default lang, normalize aliases (`fr_FR`→`fr`, 301), trailing-slash 301,
  bot pass-through, and `request.reroute(path_no_lang)` for a valid non-default
  lang. Sets `request.is_frontend`/`is_frontend_multilang`/`lang`. (code-read)
- **`_pre_dispatch` (SEO 301):** rebuilds the canonical path from rule+args; if the
  browser hit `/foo/1` but canonical is `/foo/egg-1` (or `/fr/foo/oeuf-1`), issues
  a 301 to the sluggified URL — comments name SEO as the reason. (code-read)
- **`_url_localized`/`_url_lang`/`_url_for`:** reverse direction — build lang-
  correct, slug-translated links for templates, optionally with a canonical
  domain; skip `/static/` and `/web/`. (code-read)
- **`_handle_error` + `url_rewrite`:** turns HTTPExceptions into branded
  `http_routing.<code>` pages (404/403 try `_serve_fallback()` CMS page first);
  `url_rewrite` is `ormcache(cache='routing.rewrites')` reverse routing. (code-read)

## 5. IT architecture

- **Application:** the web URL-routing layer (slug, multilang prefixing/redirects,
  pretty-URL reroute/dispatch, frontend error rendering).
- **Software services:** `/website/translations`, `/web/session/logout`, plus the
  dispatch hooks `_match`, `_pre_dispatch`, `_url_localized`, `_handle_error`,
  `url_rewrite`.
- **Data objects:** `ir.http`, `ir.qweb`, `res.lang` (all extensions).
- **Information flows:** inbound pretty/lang URL → `_match` → reroute/redirect →
  endpoint; outbound QWeb → `slug()`/`url_for()`/`url_localized()` → lang-prefixed
  slug links; errors → `_handle_error` → fallback/QWeb page.

## 6. Business architecture

- **Capabilities (inferred):** generate slug/SEO URLs; match & reroute pretty URLs
  to controllers; manage multilingual URL prefixes + canonical redirects; build
  lang-localized links; detect/select request language; render branded error pages.
- **Value streams (inferred):** URL-to-Controller (inbound dispatch);
  Record-to-Link (slug URL emission).
- **Information concepts (auto):** `ir.http`, `ir.qweb`, `res.lang`, per-request
  routing state (`request.lang`/`is_frontend`), the slug token.
- **Organization/Products (auto):** none.
- **Policies (inferred):** never lang-redirect non-GET (POST); bots keep un-
  prefixed default URL; `/static/` + `/web/` never translated; refresh
  `frontend_lang` cookie on every lang resolution.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Cross-cutting web-routing framework — Porter support
  activity / Stabell & Fjeldstad "support". It owns no business object (only
  abstract extensions, 0 fields, 0 security), creates no primary value of its own,
  and is firm IT infrastructure every website/portal request transits.
- **APQC: 8.0 Manage Information Technology.** This is concrete application-
  platform/runtime delivery — the URL-routing & localization layer of the
  application software, same bucket as the `web` framework analog. **13.0 Develop
  and Manage Business Capabilities** was considered (routing is plumbing other
  capabilities build on) but rejected: `http_routing` is a running runtime
  component doing IT-delivery work, not a governance/portfolio capability —
  squarely 8.0.

## 8. Fit-to-Standard

- **Standard:** slug pretty-URLs for any `<model(...)>` route; automatic multilang
  prefixing with 301/302 canonicalization; default-lang stripping + alias
  normalization; `/foo/1`→`/foo/egg-1` SEO 301; `url_for`/`url_localized`/`slug`
  QWeb helpers; branded 404/403/500 pages with CMS fallback; ormcache reverse
  routing.
- **Typical fits:** multilingual website/eCommerce with localized SEO URLs; portal
  pages reachable via readable record URLs; custom `website=True`/multilang routes.
- **Common gaps:** URL schemes beyond `display_name-id` (override `_slug`/
  `ModelConverter`); advanced redirect/lang-exception rules (in `website`); geoip/
  country-based lang detection (NOT here — lang is URL/cookie/context/default +
  bot, fed upstream by `website`/`website_geoip`); custom error-page design.
- **Drive hints:** `env['ir.http']._slug((14,'My Phone'))` → `my-phone-14`;
  `curl -sI /shop` → 30x `/<lang>/shop`; `curl -sI /fr/shop/1` → 301 to
  `/fr/shop/<slug>-1`; `curl -s /some-missing-page` → rendered `http_routing` 404.
