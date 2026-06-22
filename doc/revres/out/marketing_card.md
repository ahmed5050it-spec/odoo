# marketing_card — Marketing Card (Dynamic Social Share Cards)

*Odoo 19.0 · category Marketing/Marketing Card · application · LGPL-3 · facts/marketing_card*

## 1. Overview
`marketing_card` lets a marketing team turn a record (a partner, an event talk, a
booth, a registration) into a **personalized, shareable social card**. A campaign
defines a design template plus static and record-bound dynamic content; the module
generates one image per recipient, mails advocates a link to "their" card, and serves
OpenGraph previews so that when they post it, social networks render a rich preview that
pulls more viewers in. It is a **reach-amplification** tool layered on `mass_mailing`,
`link_tracker` and `website`.

## 2. IT Architecture
- **Application:** marketing_card application component (4 own models, 1472 Py LOC).
- **Software services (routes, all public http):**
  - `/cards/<card>/card.jpg` — serves the rendered JPEG; crawler hit ⇒ `share_status=shared`.
  - `/cards/<card>/preview` — advocate share page; first hit ⇒ `share_status=visited`.
  - `/cards/<card>/redirect` — OpenGraph meta page for crawlers, redirect to short_url for humans.
- **Data objects:** `card.campaign`, `card.card`, `card.template`, `card.campaign.tag`.
- **Key relations:** `card.card → card.campaign`, `card.campaign → card.template`,
  `card.campaign → link.tracker`, `card.campaign → mailing.mailing`.
- **Information flows:** depends `link_tracker`, `mass_mailing`, `website`; render ⇒ JPEG;
  crawler/click ⇒ share/visit + link-tracker counts; share ⇒ guarded mass mailing.

## 3. Behavioral Notes (code-read)
- **Image generation** — `card.campaign._get_image_b64` renders the QWeb `body_html`
  (related to `card.template.body`) per record via `mail.render.mixin`, then rasterizes it
  with `ir.actions.report._run_wkhtmltoimage` at `TEMPLATE_DIMENSIONS` 600×315 (~2:1 OG ratio).
- **Per-recipient cards + tokens** — `card.card` is a unique `(campaign_id, res_id)` map;
  URLs use `ir.http._slug` tokens; `_update_cards` batch-renders (100/batch, optional commit);
  `_gc_card` autovacuums cards after 60 days (social nets cache the images).
- **Social preview / OpenGraph** — `controllers/marketing_card.py` branches on a social
  crawler user-agent list (Facebot, Twitterbot, LinkedInBot, WhatsApp, Pinterest…): crawlers
  get OG meta tags / get the card marked shared; humans get the page or a tracked redirect.
- **Campaign send** — `action_share` opens a prefilled `mailing.mailing`; the extended mailing
  forces model = campaign `res_model`, restricts recipients to records that have a card, and
  blocks `action_put_in_queue`/`action_send_mail` while `card_requires_sync_count > 0`.
- **Frontend (static):** no OWL/JS (0 js, 0 components, 0 registry/patches); only
  `web.assets_backend`. Public surface is server-rendered QWeb + the rasterized card.

## 4. Business Architecture
- **Capabilities (inferred):** Design Dynamic Share Cards · Run Marketing Card Campaigns ·
  Distribute Per-Recipient Share Cards · Measure Share/Click Amplification.
- **Value stream (inferred):** Amplify-Reach — design card → generate per-recipient cards →
  mail advocates → advocates share → crawlers fetch OG preview → clicks tracked.
- **Information concepts (auto):** card.campaign, card.card, card.template, card.campaign.tag.
- **Organization (auto):** `marketing_card_group_user`, `marketing_card_group_manager`.
- **Policies (inferred):** 2 record rules (own/responsible scoping); `_unrestricted_rendering`
  trust delegated to `card.template` (system-only); 60-day image autovacuum.
- **Metrics (inferred):** card_count / card_click_count / card_share_count; link-tracker clicks.
- **Stakeholders:** marketing user · recipient/advocate · social-network audience.
- **Strategy:** null (human).

## 5. Classification
- **Value model: `network`** — Stabell & Fjeldstad mediation logic. The module mediates and
  amplifies connections between marketing advocates and a wider social audience: it issues a
  unique tokenized card per recipient, recipients post it, and the OpenGraph routes serve
  previews that draw more viewers in. Value scales with reach, measured by share/click counts
  and the link tracker — not input→product transformation (chain) nor per-case buyer/seller
  matching (shop).
- **Activity class: `support`** — a promotion/amplification tool, not the primary demand→order chain.
- **APQC: `3.0 Market and Sell Products and Services`** (3.4 marketing communications).

## 6. Fit-to-Standard
- **Standard out-of-box:** dynamic card templates (static + record-bound fields); per-recipient
  OG-sized JPEG generation; public preview/redirect/image routes with crawler OG handling;
  distribution via mass mailing with card-sync guardrails; share/visit/click tracking.
- **Typical fits:** event/partner promotion where advocates share a personalized card;
  campaigns over the supported models; built-in post suggestion + reward/thank-you flow.
- **Common gaps:** new target model (selection hardcoded in `_get_model_selection`); card
  layout beyond template fields / 600×315 ratio; extra social networks (crawler UA list is in
  controller code); analytics beyond share/click counts.

## 7. Drive Hints (live demo via run-odoo)
- `odoo shell`: `env['card.campaign'].search([], limit=5).mapped(('name','res_model','card_count','card_share_count'))`
- `odoo shell`: `c = env['card.campaign'].search([], limit=1); c._fetch_or_create_preview_card()._get_path('preview')`
- `curl -A 'Twitterbot' http://localhost:8069/cards/1/redirect` → OpenGraph crawler page, marks shared.

## 8. Open Questions
- Robustness of the QWeb→image pipeline (wkhtmltoimage availability) in target deployments.
- Whether the hardcoded `res_model` selection is extended by other installed modules at runtime.
- Real share-vs-visit conversion rates (no runtime row data captured).
