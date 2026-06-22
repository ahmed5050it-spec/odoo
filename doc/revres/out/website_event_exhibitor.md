# website_event_exhibitor — Architecture Brief

> Odoo 19.0 · category *Marketing/Events* · `application: false` · extends
> **website_event** to publish **sponsors & exhibitors** as live booth pages with
> a "meet the sponsor" connect flow. Depends on `website_event`.

## 1. Purpose & classification

website_event_exhibitor adds an **exhibitor/sponsor showcase** on top of the
event website: each sponsor becomes a publishable booth page, grouped by
sponsorship level, discoverable through a faceted directory, with a live,
opening-hours-gated "Connect" action that links an attendee to the sponsor.

- **Value model:** `network` (Stabell & Fjeldstad mediating technology) — it
  connects two populations, sponsors/exhibitors and attendees, on the website;
  the logic is matching/mediation, not an input→output transformation (chain) or
  case work (shop).
- **Activity class:** `primary` — customer-facing event marketing & sponsor
  engagement, not back-office support.
- **APQC:** **3.0 Market and Sell Products and Services** — inherits the PCF home
  of website_event/event; the motion is promoting sponsors and engaging attendees
  around a marketed event (visibility, lead/contact generation), not 6.0 service.

## 2. The extension (sponsor ⇄ event ⇄ website)

| Object | What website_event_exhibitor adds |
|--------|-----------------------------------|
| `event.sponsor` | new booth model on `website.published.mixin` + `website.searchable.mixin`; `exhibitor_type` (footer-logo `sponsor` / `exhibitor` / `online`); `website_url` → `/event/<slug>/exhibitor/<slug>`; mirrors name/email/phone/image/url/description from `partner_id` (never writes back); `is_in_opening_hours` live flag; `show_on_ticket`. |
| `event.sponsor.type` | new sponsorship-tier catalog: `sequence`, `display_ribbon_style` (Gold/Silver/Bronze) — drives directory grouping + ribbon badge. |
| `event.event` | gains `sponsor_ids`, `sponsor_count`, `exhibitor_menu` flag, `exhibitor_menu_ids`; adds the "Exhibitors list" `website.event.menu` (`menu_type='exhibitor'`) at `/event/<slug>/exhibitors`. |
| `website` / `event.type` / `website.event.menu` | `_search_get_details` surfaces sponsors in site search; `event.type.exhibitor_menu` template flag; new `exhibitor` menu_type. |

## 3. IT architecture (software services)

3 route groups in `controllers/exhibitor.py` (`ExhibitorController` extends
`WebsiteEventController`), all `auth=public`, `website=True`:

- **Directory:** `/event/<event>/exhibitors` (alias `/exhibitor`) — free-text +
  country + sponsorship-level facets, grouped by tier, randomised within tier
  (published-first for desk users); renders `event_exhibitors`.
- **Booth detail:** `/event/<event>/exhibitor/<sponsor>` — matched only when
  `exhibitor_menu=True`; `has_access('read')` → `Forbidden`, then `sudo()`;
  renders `event_exhibitor_main` with an `is_in_opening_hours`/country-sorted
  "other exhibitors" sidebar.
- **Connect modal data:** `/event_sponsor/<id>/read` (jsonrpc) — marshals
  sponsor + sponsor_type + event timing for the "not available" dialog.

Data objects: `event.sponsor`, `event.sponsor.type`, `event.event`,
`event.type`, `website`, `website.event.menu`.

## 4. Key behaviors (code-read — beyond metadata)

1. **`event.sponsor` is a published booth.** It inherits
   `website.published.mixin`; `_compute_website_url` repoints `website_url` to
   `/event/<slug>/exhibitor/<slug>`. `exhibitor_type` splits footer-logo-only
   `sponsor` (excluded from the directory + search) from `exhibitor`/`online`.
   name/email/phone/image/url/description are mirrored from `partner_id` and
   **never written back** (event-specific).
2. **Sponsorship levels drive the page.** `event.sponsor.type` (`sequence`,
   ribbon style) groups and orders booths in the directory and renders the
   Gold/Silver/Bronze badge; `sponsor_count` is a `_read_group` on `event.event`.
3. **The directory + detail controller** filters on `is_published` unless the
   viewer is in `event.group_event_registration_desk`, facets by
   content/country/level, and `sudo()`s to read partner info; the detail sidebar
   sorts "other" booths by published / opening-hours / same-country / tier.
4. **`is_in_opening_hours` gates the live "Connect".** A TZ-aware compute
   (event ongoing + `hour_from`/`hour_to` clamped to the event window) decides
   whether the connect button redirects to the sponsor URL or opens the
   not-available modal (data via `/event_sponsor/<id>/read`).

## 5. Frontend (static, gap #3)

3 JS files, 2 XML templates, **one OWL component** —
`ExhibitorConnectClosedDialog` (extends web `Dialog`, rpc-loads
`/event_sponsor/<id>/read`, renders a luxon countdown to start) — plus one
website **public.interaction** `website_event_exhibitor.exhibitor_connect` on
`.o_wesponsor_connect_button` (debounced click → redirect to sponsor URL when
live, else open the closed dialog). No registry patches. Asset bundles:
`web.assets_frontend` (4), `web.report_assets_common` (full-page ticket report
css, tied to `show_on_ticket`), `website.website_builder_assets` (event-page
option snippet).

## 6. Integrations (static, gap #7)

No outbound HTTP call sites and **no API keys**. The only external endpoint is the
manifest reference `https://www.odoo.com/app/events`. The "connect" action stays
on-platform (redirect to the sponsor's own `url` or an info modal). Files:
`__manifest__.py`.

## 7. Business architecture & policies

- **Capabilities (inferred):** publish exhibitor/sponsor booths; manage
  sponsorship levels & ribbons; online exhibitor discovery (faceted directory);
  live "meet the sponsor" connect availability; exhibitor↔attendee mediation.
- **Value stream:** *Showcase-to-Connect* — organizer registers a sponsor (tier,
  booth) → booth published to `/event/<id>/exhibitors` → attendee browses/searches
  → opens the booth page → connects (redirect or not-available modal).
- **Policies (inferred):** 1 record rule + `website.published.mixin` (only
  `is_published` booths shown unless registration-desk); directory restricted to
  `exhibitor_type in [exhibitor, online]`; detail route gated on
  `exhibitor_menu=True` + `has_access('read')`; `is_in_opening_hours` gates the
  live connect.
- **Organization (referenced):** `event.group_event_registration_desk`,
  `event.group_event_user`. Security: 5 ACLs, 1 record rule, 0 groups. Strategy:
  `null` (human).

## 8. Fit-to-standard & gaps

- **Standard:** per-event sponsors with tiers/ribbons; publishable booth pages;
  faceted exhibitor directory; footer-logo vs. on-site vs. online exhibitor;
  opening-hours-gated connect with not-available modal; auto "Exhibitors list"
  menu + builder option; sponsor logos on the ticket report and in site search.
- **Common gaps:** live video/chat "meet the sponsor" rooms (connect only
  redirects/modals → live-room integration); exhibitor self-service booth editing
  (gated to `event.group_event_user`); per-booth lead/scan analytics; paid
  sponsorship packages / e-commerce checkout.
- **Drive hints:** `curl -s 'http://localhost:8069/event/1/exhibitors' | head`;
  `env['event.sponsor'].search([('is_published','=',True)]).mapped(('name','sponsor_type_id','exhibitor_type','website_url'))`;
  `env['event.sponsor.type'].search([]).mapped(('name','sequence','display_ribbon_style'))`.

*Open questions:* whether a chat/live-session connect path appears once a
live-room module is installed (vs. URL-redirect-only here); runtime booth counts
(published / exhibitor vs. online vs. footer-logo) not captured; interplay of
booth `is_published` with the parent event's `website_visibility` on a live
directory. Provenance: `doc/revres/facts/website_event_exhibitor.facts.json` +
code-read; tools `extract_module.py`, `extract_frontend.py`, Grep/Read.
