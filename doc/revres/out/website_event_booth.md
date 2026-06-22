# website_event_booth — Architecture Brief

## 1. Purpose & classification
`website_event_booth` ("Online Event Booths") is the public storefront bridge that
lets a prospective exhibitor register and book an event booth online. It is a small,
route-heavy `auto_install=True` module (0 new models, 3 inherited, 329 Python LOC)
sitting on top of two parents: `website_event` (the public event-website channel) and
`event_booth` (the booth-capacity mediation layer).

- **value_model:** `network` — mediating technology (Stabell & Fjeldstad). It connects an
  open population of website visitors to a fixed pool of event booth capacity and matches
  them, rather than transforming inputs to outputs (chain) or solving cases (shop).
- **activity_class:** `primary` — customer-facing online exhibitor acquisition.
- **apqc_category:** `3.0 Market and Sell Products and Services` — the public market/sell
  motion for booth space; paid checkout lives downstream in `event_booth_sale`.

## 2. The bridge (website_event ⇄ event_booth)
The module exposes backend `event.booth` / `event.booth.category` records (from `event_booth`)
as a public web page, and reuses `website_event`'s per-event menu machinery to add a
"Become exhibitor" navigation entry. A public visitor browses available booths and books
one, which flips a real `event.booth` to `unavailable` — no new persistent model is needed.

## 3. IT architecture (software services)
Six routes, all `auth=public`, defined in `controllers/event_booth.py`:
- `/event/<event>/booth` (http) — booth storefront, catalog of available categories.
- `/event/<event>/booth/register` (http POST) — capture checkbox selection, PRG redirect.
- `/event/<event>/booth/register_form` (http GET) — exhibitor contact form (prefilled).
- `/event/<event>/booth/confirm` (http POST) — find/create partner + `action_confirm` (book).
- `/event/booth/check_availability` (jsonrpc) — flag race-lost booths in a selection.
- `/event/booth_category/get_available_booths` (jsonrpc) — list available booths for a category.

Data objects: `event.event`, `event.type`, `website.event.menu` (inherited) plus
`event.booth`, `event.booth.category`, `res.partner`, `website.visitor` (touched).

## 4. Key behaviors (code-read — beyond metadata)
- **Storefront assembly** (`event_booth_main` / `_prepare_booth_main_values`): reads
  `event.sudo().event_booth_category_available_ids` (categories that still have free booths)
  and `event_booth_ids`, picks a default/selected category. `has_access('read')` gate + the
  public `ir.rule` (`event_id.website_published=True`) make booths browsable anonymously.
- **Two-hop selection** (`booth/register` → `booth/register_form`): the POST re-parses
  `form.getlist('event_booth_ids')` (params keeps only the first checkbox) and PRG-redirects
  with `booth_ids` + `booth_category_id`; the GET prefills `default_contact` from the logged
  `user.partner_id` or the anonymous `website.visitor` (by email).
- **Confirm = the core write** (`event_booth_registration_confirm`): `_get_requested_booths`
  re-queries booths as sudo with `state='available'` and rejects the order if any id is gone
  or booths span >1 category (anti-tamper / race guard). For public users
  `_partner_find_from_emails_single` finds/creates a `res.partner` from `contact_email`;
  `booths.action_confirm(...)` then flips state `available→unavailable` and posts a booked
  note on the event chatter (in `event_booth`). Returns a JSON success payload.
- **Live availability protocol** (jsonrpc): `check_availability` returns the unavailable
  subset of a selection; `get_available_booths` repopulates the booth list on category switch
  without a page reload.
- **Menu wiring** (`event.event`): adds `exhibition_map` (Image), `booth_menu` (Boolean),
  `booth_menu_ids`; `_get_website_menu_entries` appends the `('Become exhibitor', '/event/<slug>/booth', …, 'booth')`
  entry and the generic menu-sync creates/unlinks the per-event website menu.

## 5. Frontend (static, gap #3)
1 JS file, 1 client XML template, no OWL. A `public.interactions` component
`website_event_booth.booth_registration` (`BoothRegistration` on `.o_wbooth_registration`,
3 `web.assets_frontend` entries) drives the whole UX: category radio → cached
`get_available_booths` rpc → client `renderAt` of the booth checkbox list; submit disabled
until a booth is checked; pre-submit `check_availability` rpc flags race-lost booths in red;
the contact step posts `FormData` to `booth/confirm` via `http_service.post` and renders the
completion template inline (or shows `boothError`/`boothCategoryError`/`existingPartnerError`).

## 6. Integrations (static, gap #7)
None. 0 HTTP call sites, no SDK imports, no API keys, no external endpoints — the module
introduces no outbound integration surface of its own.

## 7. Business architecture & policies
- **Capabilities (inferred):** publish booths to the website; browse catalog by category;
  self-service booth selection; capture exhibitor contact; confirm & book online; live
  availability checking.
- **Value stream:** Browse-to-Booked-Booth (open `/booth` → pick category → pick booth →
  contact form → confirm books the booth → inline success).
- **Organization (auto):** `base.group_public` and `base.group_portal` (read).
- **Policies (inferred):** 1 record rule (public/portal read booths only where
  `event_id.website_published=True`); 4 access rules (public/portal/employee read, no public
  write/create — booking runs sudo); anti-tamper guard on confirm; existing-partner-email
  refusal (`existingPartnerError` → sign-in); auto-managed booth menu.
- **strategy:** null (human).

## 8. Fit-to-standard & gaps
Out-of-box: public "Become exhibitor" page with exhibition map and category catalog,
auto booth menu, live available-booth list, two-step self-service booking, anonymous
partner find/create, race-loss checking. Typical fits: trade shows / conferences taking
online stand reservations with sold-out enforcement. Common gaps: paid booth
checkout/invoicing and pricing (needs `event_booth_sale`); a visual floor-plan stand picker
(only a checkbox list); custom exhibitor onboarding fields; an approval workflow before
booking (confirm is immediate `available→unavailable`).
