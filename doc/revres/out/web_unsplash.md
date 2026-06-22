# web_unsplash — Unsplash Image Library

## 1. Overview
`web_unsplash` ("Unsplash Image Library", v1.1, Odoo S.A., LGPL-3) lets editors
search and insert free high-resolution stock photos from **Unsplash** directly
in the HTML editor and website. It is a thin **external-integration bridge**:
`auto_install=true`, `category=Hidden`, `depends=[base_setup, html_editor]`,
0 own business models (3 inherit-only extensions), 4 jsonrpc routes, ~355 Python
LOC + ~115 XML LOC. Its real substance is outbound HTTP to the Unsplash API plus
an OWL/JS image-picker UI — neither visible in ORM metadata.

## 2. IT Architecture
- **Application:** Unsplash search/insert integration for the editor & website;
  a server-side proxy to the Unsplash REST API.
- **Software services (routes):**
  - `/web_unsplash/fetch_images` (jsonrpc, user) — proxy Unsplash search.
  - `/web_unsplash/attachment/add` (jsonrpc, user) — download chosen image to `ir.attachment`.
  - `/web_unsplash/get_app_id` (jsonrpc, public) — return `unsplash.app_id`.
  - `/web_unsplash/save_unsplash` (jsonrpc, user) — set app id / access key.
- **Data objects (extensions):** `ir.qweb.field.image`, `res.config.settings`
  (adds `unsplash_access_key`, `unsplash_app_id`), `res.users`.
- **Key relations:** downloaded image → `ir.attachment` (url `/unsplash/<id>/<query>`);
  credentials → `ir.config_parameter` (`unsplash.access_key`, `unsplash.app_id`).

## 3. Behavioral notes (code-read — the metadata gap)
- **fetch_images** reads the api-key/app-id from `ir.config_parameter` (sudo),
  injects `client_id`, and relays `requests.get(api.unsplash.com/search/photos)`
  JSON to the browser; the key never leaves the server. Missing keys →
  `{'error':'key_not_found'|'no_access'}`.
- **attachment/add** validates the host (`images.`/`plus.unsplash.com`), fetches
  the binary, `image_process(verify_resolution)`, then `HTML_Editor._attachment_create`
  → `ir.attachment`; it deliberately sudo-sets `attachment.url='/unsplash/...'`
  to bypass `_check_serving_attachments`, and returns `_get_media_info()`.
- **_notify_download** pings the Unsplash `download_url` with `client_id` after
  each save — a **mandatory Unsplash API-terms callback** (download counter);
  errors are swallowed.
- **Credentials** are runtime `ir.config_parameter`, settable only by privileged
  users (`_can_manage_unsplash_settings`: ERP manager OR website restricted editor).
- **ir.qweb.field.image.from_html** resolves saved `/unsplash/` images back to the
  local public attachment's `datas` for normal rendering.

## 4. Frontend (gap #3 — OWL/JS, static/src)
6 JS / 3 XML. OWL components **UnsplashCredentials**, **UnsplashError**; registry
adds **services:unsplash** and the public **unsplash_beacon** interaction; **patches
MediaDialog.prototype + ImageSelector.prototype** to add the Unsplash tab into the
editor's media picker. Bundles: `html_editor.assets_media_dialog` (4),
`web.assets_frontend` (1), `web.assets_unit_tests` (1). The whole image-picker UX
is client-side and not reverse-engineerable from Python metadata.

## 5. Integrations (gap #7 — external)
Outbound third-party integration via `requests`: `api.unsplash.com/search/photos/`
(search), `api.unsplash.com/photos/` (download notify), binaries from
`images.unsplash.com` / `plus.unsplash.com`. Auth = Unsplash **Access Key**
(`client_id`) held in `ir.config_parameter`. 3 HTTP call-sites, all in
`controllers/main.py`.

## 6. Business Architecture
- **Capabilities (inferred):** search free stock imagery; insert/download a photo
  as a managed attachment; configure & secure media-API credentials; honour the
  provider's download-attribution compliance.
- **Value streams (inferred):** *Find-to-Insert media* (search → pick → download
  → embed); *Configure-integration* (enter keys → stored as params → enabled).
- **Information concepts (auto):** `ir.attachment`, `ir.config_parameter`,
  `res.config.settings`.
- **Policies (inferred):** privileged-only credential management; host allow-listing;
  mandatory Unsplash download callback.
- **Stakeholders:** content author/editor; ERP manager / website restricted editor;
  Unsplash (external provider). **Strategy:** null (human).

## 7. Classification
- **value_model: support** · **activity_class: support** ·
  **apqc_category: 8.0 Manage Information Technology**
- **Rationale:** firm IT/content infrastructure (Porter/Stabell-Fjeldstad support),
  not a primary activity of any chain/shop/network. It is editor plumbing that
  integrates an external content/media service into the platform (0 business models;
  substance is gap #7 external integration + gap #3 OWL UI). APQC 8.0 fits as
  IT-delivery / application-software work; operations/marketing categories rejected
  (no primary operating activity — it only equips other UIs with a media source).

## 8. Fit-to-Standard
- **Standard:** Unsplash tab in the MediaDialog picker; one-click download to a
  local attachment; keys in General Settings (system params); auto download-notify;
  public beacon + QWeb rendering of `/unsplash/` images.
- **Typical fits:** royalty-free imagery on website/blog/product/mail; one Unsplash
  account per DB; no-code enablement via Settings.
- **Common gaps:** other providers need JS dev (patch MediaDialog/ImageSelector);
  keys/quota/terms are external; no caching/dedup or usage governance.
- **Drive hints:** set `unsplash.app_id`/`unsplash.access_key` via odoo shell then
  `GET /web_unsplash/get_app_id`; POST `/web_unsplash/fetch_images {query:'lion'}`;
  in editor open Insert Media → Unsplash → pick → inspect the `/unsplash/` attachment.

*Provenance: facts/web_unsplash.facts.json + code-read (controllers/main.py,
models/*). Odoo 19.0.*
