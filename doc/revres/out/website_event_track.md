# website_event_track — Architecture Brief

> Odoo 19.0 · category *Marketing* · `application: false` · the **agenda/talks**
> layer that extends the **event network** with a programme of tracks, a public
> timetable, attendee wishlists and a call-for-papers. Depends on `website_event`
> (→ `event`, `website`, `website_partner`, `website_mail`, `html_builder`).

## 1. Purpose & classification

website_event_track adds the **conference programme** to events: a kanban-managed
talk record (`event.track`) published per stage to a public agenda, individual
talk pages with speaker bios and reminders, a per-location timetable, an attendee
wishlist, and an online talk-proposal intake. It owns 6 models and exposes 12
public routes; it adds no new payment or fulfillment object.

- **Value model:** `network` (Stabell & Fjeldstad mediating technology) — it
  extends the event value network with agenda/talks engagement: publishing a
  programme, operating the public timetable, letting attendees self-curate it
  (wishlist/favorite, reminders, add-to-calendar, install-as-PWA) and
  crowdsourcing content from an open population of speakers (call-for-papers).
  Not an input→output transformation (chain) or case work (shop).
- **Activity class:** `primary` — customer-facing demand/marketing motion around
  the marketed event, not back-office support.
- **APQC:** **3.0 Market and Sell Products and Services** — inherits the PCF home
  of its parents `event` and `website_event`; surfacing talks and capturing
  attendee interest/proposals is part of the public market/sell motion, not 6.0
  post-sale service.

## 2. The extension (event programme ⇄ website)

| Side | What website_event_track adds |
|------|-------------------------------|
| track models | `event.track` (talk: `mail.thread` + `mail.activity.mixin` + `website.seo.metadata` + `website.published.mixin` + `website.searchable.mixin`), `event.track.stage` (kanban pipeline), `event.track.tag(.category)`, `event.track.location`, `event.track.visitor` (wishlist link). |
| event side | `event.event` gains `track_ids`/`track_count`, `website_track` + `website_track_proposal` flags, `track_menu_ids`/`track_proposal_menu_ids`; `_get_website_menu_entries` injects **Talks**, **Agenda**, **Propose a talk** menu items and `_update_website_menus` builds them on toggle. |
| website side | `website` gains `events_app_name` + `app_icon` (PWA branding); `SearchBar` patched; `website.visitor` gains `event_track_wishlisted_ids`/`_count`. |

## 3. IT architecture (software services)

12 public routes (`auth=public`, `website=True`) across `controllers/event_track.py`
and `controllers/webmanifest.py`:

- **Talks list:** `/event/<event>/track` (+ `/track/tag/<tag>`) — content search +
  multi-category tag faceting, day-grouped (`tracks_session`).
- **Agenda:** `/event/<event>/agenda` — per-location timetable; the day is sliced
  into 15-minute slots and each track spans `duration/15min` rows.
- **Talk page:** `/event/<event>/track/<track>` — speaker bio, CTA "magic button",
  related-talk suggestions; `/.../ics` returns a per-talk iCal file.
- **Engagement (jsonrpc):** `/event/track/toggle_reminder` (favorite/wishlist),
  `/event/track/send_email_reminder` (email a reminder),
  `/event/track_tag/search_read` (public tag lookup for the proposal form).
- **Proposal:** `/event/<event>/track_proposal` (+ `/post`) — call-for-papers.
- **PWA:** `/event/manifest.webmanifest`, `/event/service-worker.js`,
  `/event/offline` — install the agenda as an offline app.

Data objects: `event.track`, `event.track.stage`, `event.track.tag`,
`event.track.tag.category`, `event.track.location`, `event.track.visitor`.

## 4. Key behaviors (code-read — beyond metadata)

1. **Publish-by-stage, not a manual toggle.** Moving a track to a stage runs
   `event.track._synchronize_with_stage`: a stage flagged `is_fully_accessible`
   auto-sets `is_published=True` (talk appears on the public agenda), `is_cancel`
   unpublishes. On `event.track.stage`, `is_visible_in_agenda` / `is_fully_accessible`
   are computed-stored and mutually constrained. The pipeline stage drives website
   visibility.
2. **Create → announcement + per-stage emails.** Creating a track posts
   `event_track_template_new` on the parent `event.event` (subtype `mt_event_track`),
   then `_track_template` attaches the stage's `mail_template_id` so the speaker is
   emailed on stage change; `_track_subtype` emits `mt_track_blocked`/`mt_track_ready`
   on kanban red/green. `_message_post_after_hook` back-fills `partner_id` from a
   chatter-created contact.
3. **Wishlist via `event.track.visitor`.** `/event/track/toggle_reminder` resolves
   the current `website.visitor` (`_get_visitor_from_request`, creating one for
   public users) and flips `is_wishlisted`; for a `wishlisted_by_default` "key
   track" it instead flips `is_blacklisted` (key tracks can't be un-favorited, only
   muted). `_compute_is_reminder_on` derives per-visitor state.
4. **Agenda timetable + proposal write.** `_prepare_calendar_values` builds the
   per-location grid; `_get_track_suggestions` ranks related talks (live-first →
   start-time → wishlist → tag/location match → random). `/track_proposal/post`
   lets an anonymous visitor `sudo().create` a draft `event.track` with
   ACL-validated tags. `_get_event_tracks_domain` hides unpublished tracks unless
   the user is in `event.group_event_registration_desk`.

## 5. Frontend (static, gap #3)

9 JS files, 6 XML templates, **one OWL component**
(`WebsiteEventTrackProposalFormTagsWrapper`). The talks UX is built as website
**public.interactions**: `website_event_track` (talk page),
`website_event_track_proposal_form` + `_tags`, `website_event_track_reminder`
(favorite toggle), `website_event_track_timer` (countdown), `website_event_pwa`.
Editor glue patches `SearchBar.prototype`. The module ships a **Progressive Web
App** (service worker + `idb-keyval` offline cache). Asset bundles:
`web.assets_frontend` (10), `web.assets_tests`, `website.website_builder_assets`.

## 6. Integrations (static, gap #7)

No outbound HTTP call sites and **no API keys**. `event.track._get_track_calendar_urls`
emits an **add-to-calendar** link to `https://www.google.com/calendar/render?`
(plus a per-talk `/event/<id>/track/<track>/ics` iCal file via `vobject`). File:
`models/event_track.py`.

## 7. Business architecture & policies

- **Capabilities (inferred):** manage talks/tracks (kanban stages); publish talks
  & agenda to the website; online timetable; talk-proposal intake; attendee
  wishlist/favorites & reminders; speaker management & tagging; agenda PWA.
- **Value streams:** *Propose-to-Publish* — submit proposal → track in stage →
  fully-accessible stage auto-publishes → talk on agenda; *Engage-the-Agenda* —
  browse list/agenda → wishlist talks (`event.track.visitor`) → reminders /
  add-to-calendar.
- **Policies (inferred):** 2 record rules + `ir.model.access.csv` — public/portal
  read-only on `event.track`/`event.track.tag`, create/write reserved to
  event_user/manager; publish-by-stage automation; agenda shows only published
  tracks (registration-desk also sees `is_visible_in_agenda` preview stages);
  proposal accepts only valid tag ids behind a `can_access_from_current_website`
  guard.
- **Organization (auto):** reuses `event.group_event_user`,
  `event.group_event_manager`, `event.group_event_registration_desk`,
  `base.group_public`/`base.group_portal` — **0 own groups**. Security: 19 ACLs,
  2 record rules. Strategy: `null` (human).

## 8. Fit-to-standard & gaps

- **Standard:** talk records with a configurable kanban stage pipeline; auto
  publish-by-stage; public talk list with search + tag facets; per-location,
  time-slotted agenda; talk pages with suggestions/CTA/timer; attendee
  wishlist/reminders with key-track support; call-for-papers intake;
  Google/iCal add-to-calendar; offline agenda PWA.
- **Common gaps:** live video/streaming rooms, in-talk chat and quizzes (→
  `website_event_track_live` / `website_event_track_quiz`); paid/gated talk
  access; bespoke agenda layouts beyond the 15-min grid; advanced speaker/proposal
  review workflows.
- **Drive hints:**
  `env['event.track'].search([], limit=5).mapped(('name','stage_id','is_published','wishlist_visitor_count'))`;
  `env['event.track.stage'].search([]).mapped(('name','is_visible_in_agenda','is_fully_accessible','is_cancel'))`;
  `curl -s 'http://localhost:8069/event/1/agenda' | head`;
  `curl -s 'http://localhost:8069/event/manifest.webmanifest'`.

*Open questions:* downstream behavior once `website_event_track_live`/`_quiz` are
installed (live rooms, CTA timing, quiz scoring); how publish-by-stage interacts
with manual `is_published` overrides; runtime row counts for `event.track` and
`event.track.visitor` (wishlist adoption, not captured). Provenance:
`doc/revres/facts/website_event_track.facts.json` + code-read; tools
`extract_module.py`, `extract_frontend.py`, Grep/Read.
