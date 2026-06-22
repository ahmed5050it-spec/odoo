# website_slides — Reverse-Engineering Brief

The **eLearning** application (`Website/eLearning`, v2.7, `application=true`,
`auto_install=false`) turns Odoo's website into an online course platform. A
**course** (`slide.channel`) is a container of **content** (`slide.slide`):
videos, documents, articles, infographics and quizzes. Learners are **attendees**
(`slide.channel.partner`) whose per-content **progress** (`slide.slide.partner`)
drives completion tracking, karma gamification and community ratings. It sits on
top of `website` (public pages + builder), `website_mail` (notifications),
`website_profile` (karma/ranks/leaderboards) and `portal_rating` (reviews) — the
infrastructure of a two-sided learning community. 12 models, 39 routes, 8540 LOC
Python / 7549 LOC XML, 50 JS files.

## Role & Dependencies

- **website** — publishes courses as public web pages; provides the website
  builder, search and multi-website scoping (`website.published.multi.mixin`).
- **website_mail** — email notifications: new-content publish, course share,
  completion mail (`completed_template_id`).
- **website_profile** — karma economy, user ranks and leaderboards that the
  gamification side of eLearning plugs into.
- **portal_rating** — star ratings + reviews on courses (`rating.mixin`).
- (transitively pulls `website`, `mail`, `portal`, `gamification`.)

**Adds on top:** course catalog, enrollment/membership mediation, multi-format
content authoring, quiz assessment, completion tracking and a karma/leaderboard
engagement loop — plus an embeddable standalone slide player.

## Data Model (the ERM)

| Model | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `slide.channel` | Course | 67 | user_id, slide_ids, channel_partner_ids, tag_ids, prerequisite_channel_ids |
| `slide.slide` | Slides | 69 | channel_id, category_id, slide_partner_ids, question_ids, embed_ids |
| `slide.channel.partner` | Channel / Partners (Members) | 15 | channel_id, partner_id, next_slide_id |
| `slide.slide.partner` | Slide / Partner decorated m2m | 7 | slide_id, channel_id, partner_id |
| `slide.question` | Content Quiz Question | 8 | slide_id, answer_ids |
| `slide.answer` | Slide Question's Answer | 5 | question_id |
| `slide.channel.tag` | Channel/Course Tag | 6 | group_id, channel_ids |
| `slide.embed` | Embedded Slides View Counter | 4 | slide_id |

- **Central/aggregate model:** `slide.channel` (the course; 66 methods) with
  `slide.slide` (the content; 64 methods) as its child aggregate.
- **Association objects:** `slide.channel.partner` (enrollment) and
  `slide.slide.partner` (progress) are decorated many-to-many tables — the heart
  of the platform's mediation. `slide.slide.category_id` is self-referential
  (slides group under category slides).
- **Mixins / extensions:** `_inherit`-only files extend `gamification.challenge`
  (adds 'slides' category), `gamification.karma.tracking`, `res.partner`,
  `res.users`, `mail.message`, `website`, `res.config.settings`.
- **Field distribution:** relational-heavy — 26 Many2one, 14 One2many,
  12 Many2many. Many Integer (57) and Boolean (35) fields are computed
  statistics/flags (counts, completion %, can_review/can_vote), signalling a lot
  of derived, behavior-driven state rather than raw data entry.

## Behavior & Surfaces

- **Routes (39):** website/RPC-heavy. Public `http` catalog pages (`/slides`,
  `/slides/all`, `/slides/tag/...`), public `jsonrpc` learner actions
  (`/slides/channel/join|leave`, `/slides/slide/set_completed`, `.../like`,
  `/slides/slide/quiz/{get,submit}`), authoring `jsonrpc` (`/slides/add_slide`,
  `/slides/slide/quiz/question_add_or_update`), and standalone `http` embed
  endpoints (`/slides/embed/<id>`). Public auth dominates — anonymous browsing is
  a first-class surface.
- **Views (47):** list (18) and form (10) dominate for backend authoring/admin;
  3 kanban; 4 pivot + 4 graph give attendee/quiz analytics. Most learner UX is
  the website front end (12 OWL components, 15 public.interactions), not backend
  views.
- **Security posture:** 41 access rules, 21 record rules, 2 groups
  (`group_website_slides_officer`, `group_website_slides_manager`). Record rules
  enforce published/visibility + membership scoping (portal/users see only
  published, attendee- or link-accessible content); karma thresholds gate
  review/comment/vote.

**Behavioral facts (code-read, beyond metadata):**
- `slide.channel._action_add_members` mediates enrollment: 'invited' makes the
  course visible but not its slides until self-enroll; invite links are
  HMAC-signed and expire after 3 months (autovacuum).
- `slide.channel.partner._recompute_completion` recomputes completion % and
  member_status (joined→ongoing→completed); crossing 100% awards
  `karma_gen_channel_finish` karma and sends the completion email; un-completing
  reverses the karma.
- `slide.slide._action_set_quiz_done` awards attempt-tiered karma
  (`quiz_first…fourth_attempt_reward` indexed by `quiz_attempts_count`).
- `slide.channel.message_post` karma-gates reviews (one per author/course) and
  demotes publish-reply messages to internal notes.

## Value-Configuration Classification

**Network (mediating), primary activity.** This is a two-sided platform
connecting content providers (instructors/officers) with consumers (learners):
value grows with catalog size and community engagement (Metcalfe-style effects
via ratings, karma ranks, leaderboards, shared/embedded content). The
infrastructure is *membership mediation* (`slide.channel.partner`) plus
engagement services (enroll/like/quiz/review) — not a sequential document
*transform*, ruling out **chain**; the heavy public web surface and
`website_profile`/`portal_rating` deps are mediation infrastructure, ruling out
**shop**/**support**. Classed **primary** because course delivery is the core
offering of an eLearning business.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — the platform is the
demand-generation / content-distribution channel that attracts and converts an
audience (website-adjacent, like the marketing entries in `apqc_odoo_map.tsv`);
the optional `website_sale_slides` / certification bridges push it toward 3.5
Sell. *(Secondary, inferred:* an internal-academy use, `channel_type='training'`,
maps to **7.x** corporate L&D — but the out-of-box module is a public-facing
offering, so Market & Sell is the primary fit.)

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):
- `env['slide.channel'].search([], limit=5).mapped(('name','channel_type','enroll','visibility','total_slides'))`
- `env['slide.slide'].read_group([('is_category','=',False)], ['id:count'], ['slide_category'])`
- `env['slide.channel.partner'].search([], limit=5).mapped(('partner_id','member_status','completion'))`

Curl: public `GET /slides` and `GET /slides/all` (catalog); jsonrpc
`POST /slides/channel/join {channel_id}` then `POST /slides/slide/quiz/submit`.

## Open Questions

- Real karma amounts (channel rank/finish, quiz attempt rewards) ship as
  per-course-configurable defaults — need runtime inspection.
- Whether certification is active depends on the `website_slides_survey` bridge
  (`module_website_slides_survey`), outside this module's code.
- Live catalog size / engagement metrics not captured (runtime
  `models_with_data = 0`).
- External video-metadata API behavior (YouTube/Vimeo/Google Drive quota &
  failure handling via `requests`).

---
*Provenance: structural facts from `extract_module.py`
(`facts/website_slides.facts.json`); frontend/integrations from
`extract_frontend.py`; behavioral notes from reading
`models/slide_channel.py`, `models/slide_slide.py`,
`models/slide_channel_partner.py`. Odoo 19.0.*
