# html_editor — Architecture Brief

> Module: `html_editor` · Category: Hidden · Depends: `base` · `bus` · `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/html_editor.facts.json` · Frontend: `doc/revres/frontend/html_editor.frontend.json`

## 1. Summary

`html_editor` is Odoo's shared **rich-text / WYSIWYG editor** — the OWL editor
engine and plugin framework embedded wherever an Html field is edited (mail,
website, knowledge, mass_mailing). Like `web`, it is the **inverse of a data
module**: only ~2 real own Python models (`html.field.history.mixin` + test
models) plus ~5 inherit-only ORM extensions, against a massive static frontend —
**~187 JS files** and **~58 XML templates** (~4.3k Python LOC, ~1.8k XML LOC),
~40 catalogued OWL components and an `Editor`-plus-**~50-plugin** engine. Its
substance lives in the browser, not the database.

## 2. Structure (evidence)

- **Models:** `html.field.history.mixin` (Html field version history) + 2 test
  models; the rest are inherit-only extensions of core infra — `ir.attachment`
  (editor media), `ir.qweb` / ~17 `ir.qweb.field.*` (editable-field rendering &
  back-conversion), `ir.ui.view` (inline save), `ir.http` (`?editable` context),
  `ir.websocket` (collaboration channel auth).
- **Routes (15):** attachment add/remove, image info/optimize (`modify_image`),
  recolored SVG `shape`/`image_shape`, `save_library_media` / `media_library_search`,
  `video_url/data` (oEmbed), `generate_text` (AI), `get_ice_servers` (WebRTC),
  `bus_broadcast` (collaboration), `link_preview_*`. Most are dual-mounted under
  `/web_editor/*` and `/html_editor/*`.
- **Security:** minimal (2 access rules, 0 record rules, 0 groups) — access is
  enforced per-document at the bus/route level, not via group ACLs.
- **Views:** none (it is a component library, not an app with screens).

## 3. Frontend (gap #3 — the substance)

This is where `html_editor` lives. extract_frontend reports **present, 187 JS /
58 XML**, ~40 OWL components (`HtmlField`, `HtmlViewer`, `Powerbox`, `MediaDialog`,
`FileSelector`, `ImageCrop`/`ImageTransformation`, `LinkPopover`, `ColorSelector`/
`GradientPicker`, `Font*Selector`, `ChatGPTDialog`, `HistoryDialog`, embedded
`TableOfContent`/`ToggleBlock`/`SyntaxHighlighting`/`Caption` components…), 11
registry adds (`fields:html`, `services:upload`, `main_components:ImageCropping`,
`public.interactions:html_editor.embedded_component`…) and ~18 asset bundles
(`html_editor.assets_editor`=14, `assets_readonly`=11, `assets_prism`,
`assets_media_dialog`, `assets_image_cropper`). The core is `static/src/editor.js`:
an `Editor` that attaches to a contenteditable, topologically sorts `Plugin`
subclasses and wires them via a frozen resources registry (`dispatchTo`,
`delegateTo`, `checkPredicates`). `plugin_sets.js` declares CORE / MAIN /
COLLABORATION / EMBEDDED plugin sets. **None of this is reverse-engineerable from
Python metadata** — it is exactly what gap #3 exists for.

## 4. Behavior (beyond metadata)

- **Editor + plugin framework (static):** `Editor.attachTo` sorts ~50 `Plugin`
  classes by dependency and exposes a resource bus — `dispatchTo` (events),
  `delegateTo` (first-truthy command override), `checkPredicates` (voting).
  `HtmlField`/`Wysiwyg` mount it; `getContent` runs `clean_for_save` before save.
- **`html.field.history.mixin.write` (code-read):** on write of a versioned,
  `sanitize=True` field it `generate_patch`-diffs old vs new and prepends a
  reverse patch into the `html_field_history` Json column (capped 300 revs), then
  `super().write` again; `apply_patch` replays to reconstruct any revision.
- **Collaboration (code-read):** `ir.websocket` authorizes
  `editor_collaboration:<model>:<field>:<id>` channels only after read+write
  `check_access` and `_check_field_access`; `/bus_broadcast` re-checks then
  `bus.bus._sendone` fans peer ops to subscribers; `/get_ice_servers` → WebRTC.
- **Media & AI (code-read):** `ir.attachment` gains `image_src`/`original_id`;
  `/modify_image` writes optimized variants; `/shape` recolors SVG from the
  frontend CSS (injection-guarded); `/generate_text` proxies to the OLG IAP.

## 5. IT architecture

- **Application:** OWL rich-text editor engine + plugin framework, media/attachment
  pipeline, in-place QWeb field editing, real-time collaboration transport.
- **Software services:** the 15 routes above (attachments, image optimize/shape,
  media library, oEmbed, AI, ICE, bus broadcast, link preview).
- **Data objects:** `html.field.history.mixin`, `ir.attachment` (extension), test
  models.
- **Information flows:** OWL widget → `Editor` plugins → `clean_for_save` → ORM
  write; versioning via `generate_patch`/`apply_patch`; collaboration via the bus;
  media via `ir.attachment`/`image_process`; extends `ir.qweb.field.*`/`ir.ui.view`/
  `ir.http`/`ir.websocket`/`ir.attachment`.

## 6. Business architecture

- **Capabilities (inferred):** provide a reusable rich-text/WYSIWYG component;
  sanitize/edit/save HTML; manage editor media; version field content; enable
  real-time co-editing; render & back-convert editable QWeb fields; in-editor AI.
- **Value streams (inferred):** Compose-to-Persist; Insert-Media; Co-edit.
- **Information concepts (auto):** field history stack, editor media attachment,
  collaboration bus channel, editable QWeb field, editor asset bundle.
- **Organization / Products (auto):** none (no groups, no `product.*`).
- **Policies (inferred):** versioned fields must be `sanitize=True`; collaboration
  channels require document+field read/write access; SVG recolor injection guard;
  content sanitized before persistence.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `html_editor` is technical UI-framework
  infrastructure (Porter support activity; Stabell & Fjeldstad "support"). It
  creates no primary value in any chain/shop/network — it is the rich-text editing
  component **every** content-bearing module embeds, and `auto_install=true` makes
  it ubiquitous editor plumbing. Its substance is the FRONTEND (~187 JS / ~58 XML,
  the OWL editor + ~50 plugins), the inverse of a data module — exactly like `web`.
- **APQC: 8.0 Manage Information Technology.** It is an IT-delivery /
  application-platform capability: it delivers a reusable client UI component and
  its media/collaboration plumbing. 13.0 "Develop and Manage Business Capabilities"
  (the auto-architect baseline guess) was rejected — `html_editor` is a concrete
  running UI runtime/component, not a governance/portfolio capability; its work is
  IT delivery, squarely 8.0.

## 8. Fit-to-Standard

- **Standard:** OWL rich-text editor (HtmlField/Wysiwyg) + plugin framework;
  Powerbox/toolbar/tables/lists/links/fonts/colors; media (upload/optimize/crop,
  oEmbed video, SVG shapes, media library); field versioning; collaboration over
  the bus; in-place QWeb editing; embedded components; OLG-IAP AI text.
- **Typical fits:** drop an Html field with the editor into any model with zero
  plumbing; use the media dialog out of the box; enable history via
  `_get_versioned_fields` on a `sanitize=True` field.
- **Common gaps:** custom plugins/commands/embedded components (JS dev, gap #3);
  bespoke sanitization policies; alternative/self-hosted AI provider. External
  integrations are limited to Odoo IAP/media + public oEmbed/CDN hosts (gap #7) —
  `olg.api.odoo.com`, `media-api.odoo.com`, YouTube/Vimeo/Dailymotion/Instagram.
- **Drive hints:** inherit `html.field.history.mixin`, write a sanitized field
  twice, then `html_field_history_get_comparison_at_revision(field, 1)`; `POST
  /html_editor/video_url/data` with a YouTube url; `POST
  /html_editor/link_preview_external`; type `/` in any Html field for the Powerbox.
