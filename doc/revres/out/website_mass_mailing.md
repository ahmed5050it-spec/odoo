# website_mass_mailing — Newsletter Subscribe Button (Website Snippet → Mailing-List Opt-in)

## 1. Overview
`website_mass_mailing` is the **Newsletter Subscribe** snippet/popup: a website building block
that lets a visitor self-subscribe to a `mailing.list` managed in Email Marketing, in one click,
behind a recaptcha gate. It owns no business model — one inherit-only `res.company` tweak — and
two public jsonrpc routes plus a guard on the generic website Form controller. Manifest: name
**Newsletter Subscribe Button**, category **Website/Website**, summary "Attract visitors to
subscribe to mailing lists", depends `['website', 'mass_mailing', 'google_recaptcha']`, LGPL-3,
**`auto_install=['website','mass_mailing']`**, `application=false`. 221 Python LOC / 466 XML LOC
(snippet templates + builder options), 0 own models, 2 routes, 1 ACL rule.

## 2. Data model (information concepts)
No new model. Operates on `mass_mailing` data:
- **mailing.subscription** — the contact↔list join with an `opt_out` flag; the routes
  search/create it and the `is_subscriber` count is over it (`opt_out=False`).
- **mailing.contact** — the subscribing visitor; find-or-created from the entered email.
- **mailing.list** — the newsletter audience the designer wires to the snippet (1 ACL grants
  website designers read-only to pick it).

Inherit-only `res.company._get_social_media_links` overlays the current website's `social_*`
fields. Key relation: `mailing.subscription -> mailing.contact (contact_id) + mailing.list (list_id)`.

## 3. Routes / services
Two routes (`controllers/main.py`, extending `mass_mailing.MassMailController`), both
`auth=public`, `website=True`:
- **`POST /website_mass_mailing/subscribe`** (jsonrpc) — **recaptcha-gated** opt-in:
  `_verify_request_recaptcha_token('website_mass_mailing_subscribe')` (hard gate) then
  `subscribe_to_newsletter(...)`; returns a `{toast_type, toast_content}` success/danger toast.
- **`POST /website_mass_mailing/is_subscriber`** (jsonrpc) — returns `{is_subscriber, value}`
  by counting non-opted-out `mailing.subscription` rows for the visitor's email on the list.

Plus **`WebsiteNewsletterForm._handle_website_form`** (`controllers/website_form.py`) — a guard
on the generic website Form path for `model_name=='mailing.contact'`.

## 4. Behavioral notes (code-read — the metadata gap)
- **`/subscribe` recaptcha + `subscribe_to_newsletter`:** the captcha is a **hard gate** —
  a `UserError` returns a danger toast and never touches data (contrast `website_mail`, where
  captcha only gates partner creation). On success it find-or-creates a `mailing.contact` and a
  `mailing.subscription` on the list, with four branches: create-both / reuse-contact-create-sub /
  clear `opt_out` on an existing opted-out sub / no-op on an active sub. It then stores
  `session['mass_mailing_email']`. Net: a visitor self-joins a list, idempotently, without login.
- **`/is_subscriber` + `_get_value`:** resolves the visitor's email without a form (user email,
  or `session['mass_mailing_email']` from a prior subscribe), `search_count`s
  `mailing.subscription (opt_out=False)`, and echoes `value` so the snippet pre-fills + disables.
  An opted-out contact correctly shows as NOT subscribed and can re-join.
- **`_handle_website_form` private-list guard:** the generic Form's `create_mailing_contact`
  action requires `list_ids`, and **refuses any `is_public=False` mailing list** ("You cannot
  subscribe to the following list anymore"). This is the boundary stopping a crafted POST from
  enrolling visitors into private/internal lists.
- **`res.company._get_social_media_links`:** overlays the current website's
  facebook/linkedin/twitter/instagram/tiktok handles, making the newsletter/footer social icons
  multi-website aware.

## 5. Frontend (static)
The snippet UX is client-side (metadata gap #3): **13 JS files, 5 XML templates, 0 OWL
components**. The **Subscribe** `public.interaction` (`subscribe.js`, `.js_subscribe`) RPCs
`/is_subscriber` on load to toggle subscribe-vs-subscribed, validates the email, loads
`google_recaptcha` (and renders a Cloudflare **turnstile** widget when
`session.turnstile_site_key` is set), RPCs `/subscribe`, shows the toast and hides the
`.o_newsletter_modal` on success. The **`Popup.prototype`** patch (`popup.js`) suppresses the
newsletter popup when already subscribed and keeps it open on the subscribe click. The rest is
website-builder option UI (list picker, layout, recaptcha toggle, form editor). Registry adds:
`public.interactions:website_mass_mailing.subscribe`, the `.edit` `fix_newsletter_list_class`,
and `website.form_editor_actions:create_mailing_contact`. Patches: `FormOptionPlugin.prototype`,
`Popup.prototype`. Bundles incl. `web.assets_frontend` ×5, `website.website_builder_assets` ×4.

## 6. Integrations
None outbound: `http_call_sites=0`, no SDK, no API keys. `google_recaptcha` verifies the
subscribe token server-side; an optional Cloudflare turnstile renders client-side. All data
coupling is internal Odoo (`mass_mailing` subscription/contact/list, website current-website +
form controller).

## 7. Classification
- **value_model: network** — mediating-technology audience-acquisition front-end of the
  `mass_mailing` value network; worth grows with subscribers captured.
- **activity_class: primary** — the snippet is a demand-side lead/audience-capture service that
  directly grows the marketable audience.
- **apqc_category: 3.0 Market and Sell Products and Services** — converts website traffic into
  opted-in marketing contacts (3.4 marketing communications / subscriber capture), mirroring
  `website_mail`, `website_links` and `mass_mailing`. The recaptcha/turnstile gate and
  private-list guard are anti-abuse policies on that capture.

## 8. Fit-to-Standard
**Standard (out of box):** Newsletter inline block + popup snippets bound to a chosen list;
one-click public subscribe (find-or-create contact + subscription / clear opt_out); recaptcha
+ optional turnstile spam protection; already-subscribed detection (session + `is_subscriber`)
that pre-fills/disables and suppresses the popup; the `create_mailing_contact` Form action with
private-list protection; multi-website social fallback; builder options (list, layout, recaptcha).
**Typical fits:** footer/hero newsletter sign-up; exit-intent/timed popup; lead capture into an
Email Marketing audience; multi-site lists with per-site social handles.
**Common gaps:** no double opt-in/confirmation email; only email (+ a 'mobile' placeholder) types;
session-bound anonymous detection; unsubscribe is on `mass_mailing` pages, not this snippet;
list configured by a designer (no per-visitor list self-selection).
**Drive (run-odoo):**
`curl jsonrpc POST /website_mass_mailing/is_subscriber {list_id,subscription_type:'email'}` ·
`curl jsonrpc POST /website_mass_mailing/subscribe {list_id,value,subscription_type:'email'}` (needs a recaptcha token) ·
`env['mailing.subscription'].search_count([('list_id','=',<id>),('opt_out','=',False)])` ·
`env['mailing.contact'].search([('email','=','visitor@example.com')]).subscription_list_ids`.
