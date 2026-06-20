# website_event — Architecture Brief

> Odoo 19.0 · category *Marketing/Events* · `application: true` · the **bridge**
> that turns the **website** (network) into the public online registration
> channel for **event** (network). Depends on `event`, `website`,
> `website_partner`, `website_mail`, `html_builder`.

## 1. Purpose & classification

website_event is a **bridge module**: it does not own a new business object so
much as weld two existing value networks together. It publishes each backend
`event.event` as an SEO website page, runs the public events catalog, and exposes
a self-service registration flow that writes real `event.registration` rows from
anonymous website visitors.

- **Value model:** `network` (Stabell & Fjeldstad mediating technology) — its
  worth is connecting an open population of website visitors to events and
  letting them join (online seat sign-up, visitor matching, add-to-calendar),
  not an input→output transformation (chain) or case work (shop).
- **Activity class:** `primary` — customer-facing online event marketing &
  registration, not back-office support.
- **APQC:** **3.0 Market and Sell Products and Services** — inherits the same
  PCF home as both modules it bridges; the motion is publish-and-register-to-a-
  marketed-event (demand side), not 6.0 post-sale service.

## 2. The bridge (website ⇄ event)

| Side | What website_event adds |
|------|-------------------------|
| event side | `event.event` gains `website.published.multi.mixin`, `website.seo.metadata`, cover/visibility/searchable mixins; `website_visibility` (public/link/logged_users); per-event `menu_id` + `website.event.menu` pages. |
| website side | `models/website.py` extends `website`: `_search_get_details` surfaces events in site search, `get_cta_data`/`get_suggested_controllers` add the `/event` CTA, `new_page` wraps `event/*` pages in `website_event.layout`. |
| join models | `website.event.menu` (event ⇄ website.menu ⇄ ir.ui.view), `event.registration.visitor_id → website.visitor`, and `website.visitor.event_registration_ids`. |

## 3. IT architecture (software services)

8 public route groups (all `auth=public`, `website=True`) in
`controllers/main.py`:

- **Catalog:** `/event`, `/events`, `/event/page/<int>`, `/event/tags/<slug>` —
  fuzzy search + date/tag/type/country facets, 12/page, renders
  `website_event.index`.
- **Landing/register:** `/event/<event>` (redirects to register or menu child),
  `/event/<event>/register` (renders `event_description_full`).
- **Modals (jsonrpc, POST):** `/registration/slot/<id>/tickets`,
  `/registration/new` — slot/ticket and attendee detail forms.
- **Write + confirm:** `/event/<event>/registration/confirm` (POST) and
  `/registration/success` (GET).

Data objects: `event.event`, `website.event.menu`, `event.registration`,
`website.visitor`, `event.tag(.category)`, `event.type`.

## 4. Key behaviors (code-read — beyond metadata)

1. **`registration_confirm` is the core write.** It verifies the
   `website_event_registration` reCAPTCHA, parses the attendee form
   (`_process_attendees_form`: name/email/phone/company_name + `event.question`
   answers), re-checks seats via `event._verify_seats_availability`
   (`ValidationError → ?registration_error_code=insufficient_seats`), then
   `_create_attendees_from_registration_post` calls
   `env['event.registration'].sudo().create(...)` stamping `event_id`,
   `partner_id` and `visitor_id`. **An anonymous visitor creates event rows.**
2. **`_update_website_menus` mutates the live nav tree.** Toggling
   `website_menu` (or introduction/register/community sub-flags) creates/unlinks
   a root `website.menu` plus `website.event.menu` rows and their `ir.ui.view`
   pages on the fly.
3. **`is_participating` personalizes the page** via
   `_fetch_is_participating_events`: reads the current `website.visitor` and/or
   logged partner, `_read_group`s registrations in state `open/done`.
4. **Catalog facets** come from `website._search_with_fuzzy('events', …)` +
   `_read_group`; multi-tag GET URLs are 301-redirected to `/event` to stop
   crawler combinatorial explosion.

## 5. Frontend (static, gap #3)

17 JS files, 5 XML templates, **no OWL components** — the registration UX is
built as website **public.interactions**: `events` (list filtering),
`event_page`, `modal_registration`, `slot_details`, `ticket_details`,
`display_timer` (countdown), `register_toaster`. Editor glue patches
`NewContentSystrayItem` (create an event from the builder), `SearchBar`, and
`EventAdditionalTourSteps`. Asset bundles: `web.assets_frontend` (6),
`website.assets_editor`, `website.website_builder_assets`.

## 6. Integrations (static, gap #7)

No outbound HTTP call sites and **no API keys**. `event._get_event_resource_urls`
emits an **add-to-calendar** link to `https://www.google.com/calendar/render?`
(plus a local `/event/<id>/ics` iCal URL); the manifest references
`https://www.odoo.com/app/events`. Files: `__manifest__.py`,
`models/event_event.py`.

## 7. Business architecture & policies

- **Capabilities (inferred):** publish events to the website; online discovery
  (catalog + facets); self-service registration (anonymous & logged); per-event
  menu/page management; visitor↔registration linking + add-to-calendar.
- **Value stream:** *Discover-to-Register* — browse `/event` → open event page →
  pick slot/ticket → submit attendee form → `event.registration` created →
  success.
- **Policies (inferred):** 8 record rules (website-scoped + published/visibility
  gating of events/tags/menus); `website_visibility` selection; reCAPTCHA gate on
  confirm; seat re-check before online create.
- **Organization (auto):** `event.group_event_registration_desk`. Security: 27
  ACLs, 8 record rules, 1 group. Strategy: `null` (human).

## 8. Fit-to-standard & gaps

- **Standard:** public catalog with search/facets; published per-event SEO page;
  auto per-event menu/pages; online registration with slot/ticket modals +
  questions; anonymous registration linked to `website.visitor`; Google/iCal
  add-to-calendar.
- **Common gaps:** paid online ticketing/checkout (→ `website_event_sale`);
  tracks/agenda/exhibitors (→ `website_event_track*`, `website_event_exhibitor`);
  bespoke form steps; custom catalog layouts.
- **Drive hints:** `curl -s http://localhost:8069/event | head`;
  `env['event.event'].search([('website_published','=',True)]).mapped(('name','website_url','website_visibility'))`;
  `env['event.registration'].search([('visitor_id','!=',False)], limit=5).mapped(('name','event_id','visitor_id'))`.

*Open questions:* downstream chain once `website_event_sale` is installed (cart
vs. direct create); whether `link`/`logged_users` fully hide events from search;
runtime online-vs-backend registration counts (not captured). Provenance:
`doc/revres/facts/website_event.facts.json` + code-read; tools `extract_module.py`,
`extract_frontend.py`, Grep/Read.
