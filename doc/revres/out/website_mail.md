# website_mail — Website Follow Widget (Visitor-to-Record Subscription on mail.thread)

## 1. Overview
`website_mail` is the website-facing **Follow widget**: a small QWeb snippet + OWL public
interaction that lets a web visitor follow (or unfollow) any published `mail.thread` record
and, in doing so, captures their email as a contact. It owns **no business model** — only two
inherit-only tweaks (`ir.http`, `publisher_warranty.contract`) and two public jsonrpc routes.
Manifest: name **Website Mail**, category **Website/Website**, summary "Website Module for
Mail", depends `['website', 'mail']`, LGPL-3, **`auto_install=true`**, `application=false`.
150 Python LOC / 31 XML LOC, 0 own models, 2 routes, 0 ACL rules.

## 2. Data model (information concepts)
No new model is declared. The widget operates on existing `mail` data:
- **mail.followers** — the follower link `(res_model, res_id, partner_id)` that the routes
  read (`_read_group`) and write (`message_subscribe` / `message_unsubscribe`).
- **res.partner** — the follower; created on demand from a visitor email (captcha-gated).
- **the followed `mail.thread` record** — any published business document carrying the widget.

Inherit-only models: `ir.http` (adds `mail` to the frontend translation export) and
`publisher_warranty.contract` (flags `website=True` in the update ping). Key relation:
`mail.followers -> res.partner` + `(res_model, res_id) -> target record`.

## 3. Routes / services
Two routes (`controllers/main.py`), both `auth=public`, `website=True`:
- **`POST /website_mail/follow`** (jsonrpc) — toggle follower state of a record:
  `message_subscribe` / `message_unsubscribe` of a partner; recaptcha-gated partner
  find-or-create for public visitors. Returns `True` (now following) / `False`.
- **`/website_mail/is_follower`** (jsonrpc, **readonly**) — given `{model:[res_ids]}`,
  returns `[{is_user, email}, {model:[followed_res_ids]}]` so the widget renders
  Follow vs Unfollow on load.

## 4. Behavioral notes (code-read — the metadata gap)
- **`/website_mail/follow` -> `message_subscribe`/`message_unsubscribe`:** browses the
  `object`+`id` record, enforces `record.check_access('read')` (a visitor can only follow
  what they may read), resolves a partner (logged-in user's `partner_id`, or
  `_partner_find_from_emails_single([email])` for a visitor), then **inverts on
  `message_is_follower`**: unsubscribe+return False if already following, else stash
  `session['partner_id']` and subscribe+return True. One route both subscribes and unsubscribes.
- **recaptcha gate (`website_mail_follow`):** for public visitors the captcha does **not**
  block the follow — it only sets `no_create`, deciding whether an unknown email may mint a
  **new `res.partner`**. Fail/absent captcha ⇒ find-only (anti-spam contact creation).
- **`/website_mail/is_follower` (readonly):** resolves the visitor's partner from the user or
  from `session['partner_id']` (set by a prior follow — this is how an anonymous follower is
  remembered), `_read_group`s `mail.followers` per model, returns followed res_ids +
  `{is_user, email}`. No write side-effects.
- **Two inherit-only side-effects:** `publisher_warranty.contract._get_message` adds
  `website=True` to the update ping (telemetry); `ir.http._get_translation_frontend_modules_name`
  appends `mail` so the widget's terms are translatable on public pages.

## 5. Frontend (static)
Entirely client-side (metadata gap #3): **2 JS files, 0 XML templates, 0 OWL components**.
The **Follow** `public.interaction` (`static/src/interactions/follow.js`, selector
`#wrapwrap`/`.js_follow`) fetches `/website_mail/is_follower` on load, validates the email
regex, gets a `google_recaptcha` token for action `website_mail_follow` (plus a
`turnstile_captcha` input if present), RPCs `/website_mail/follow`, and flips the DOM.
`follow.edit.js` is the website-builder edit-mode variant. Bundles: `web.assets_frontend` ×2,
`web.assets_inside_builder_iframe` ×1. Registry: `public.interactions:website_mail.follow`
and its `.edit` sibling.

## 6. Integrations
None outbound: `http_call_sites=0`, no SDK imports, no API keys. `google_recaptcha` (via
`website`) verifies the follow token server-side; all other coupling is internal Odoo
(`mail.followers`, `res.partner`, website session/request).

## 7. Classification
- **value_model: network** — mediating-technology layer connecting web visitors to a
  published record; worth grows with participants (more visitors following more records).
- **activity_class: primary** — the follow widget is a demand-side audience-capture/engagement
  service the public website delivers, turning anonymous traffic into opted-in contacts.
- **apqc_category: 3.0 Market and Sell Products and Services** — a marketing/audience-relationship
  channel (subscribe to a record's updates, harvest contact emails), mirroring `website_links`
  and `mass_mailing`. The mail notification engine is support infrastructure; `website_mail` is
  the public-facing tool that recruits the audience, hence primary.

## 8. Fit-to-Standard
**Standard (out of box):** drop-in Follow widget on any `mail.thread` record; public
subscribe/unsubscribe toggle; per-visitor follow-state lookup; recaptcha-gated res.partner
find-or-create from an email; session-based anonymous follower memory; mail terms exported to
the website translations.
**Typical fits:** 'follow this page' opt-in on blogs/products/events; turning visitors into
followers who get chatter notifications; lightweight email capture into `res.partner`.
**Common gaps:** no double opt-in / confirmation email; no unsubscribe landing page or audit;
captcha gates only partner creation, not the follow itself; no list/segmentation semantics
(that is `mass_mailing`); session-bound anonymous identity.
**Drive (run-odoo):**
`curl jsonrpc POST /website_mail/is_follower {records:{'res.partner':[1]}}` ·
`curl jsonrpc POST /website_mail/follow {id,object,message_is_follower:'off',email}` (needs a recaptcha token to create the partner) ·
`env['mail.followers'].search_count([('res_model','=','<model>')])` ·
`rec.message_subscribe(env.user.partner_id.ids); rec.message_partner_ids`.
