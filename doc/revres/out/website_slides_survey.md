# website_slides_survey — Reverse-Engineering Brief

The **Course Certifications** module (`Website/eLearning`, v1.0,
`application=false`, `auto_install=true`) is a thin bridge that marries Odoo's
**eLearning** platform (`website_slides`) to its **Surveys** engine (`survey`).
It adds nothing new to the catalog model — instead it introduces a
**certification** slide content-type whose completion is *gated on passing a
scored survey*, and on success marks the learner **Certified** for the course and
grants the survey's certification badge. 0 new models (6 `_inherit` extensions),
2 routes, ~900 LOC Python / ~930 LOC XML, 3 JS files. It auto-installs whenever
both `website_slides` and `survey` are present.

## Role & Dependencies

- **website_slides** — the host eLearning platform; this module extends
  `slide.slide`, `slide.slide.partner`, `slide.channel`, `slide.channel.partner`
  and rides their existing completion / karma / membership machinery.
- **survey** — the assessment engine; certifications are `survey.survey` records
  (`certification=True`), attempts are `survey.user_input`, scoring/pass-fail and
  the certificate PDF + `gamification.badge` come from survey.

**Adds on top:** a `certification` slide category linking a slide to a survey;
attempt-pool bookkeeping per enrollment; a pass→complete→certify cascade; a
fail→un-enroll ("re-purchase") flow; and certificate/badge surfacing on learner
profiles and the ranks/badges page.

## Data Model (the ERM)

| Model (`_inherit`) | What it adds | #fields | Key relations |
|--------------------|--------------|--------:|---------------|
| `slide.slide` | `survey_id`, `certification` category/type | 6 | survey_id→survey.survey |
| `slide.slide.partner` | `user_input_ids`, `survey_scoring_success` | 2 | user_input_ids→survey.user_input |
| `slide.channel` | `nbr_certification`, `members_certified_count` | 2 | — |
| `slide.channel.partner` | `survey_certification_success` ("Certified") | 2 | — |
| `survey.survey` | `slide_ids`, `slide_channel_ids`, count | 3 | slide_ids→slide.slide |
| `survey.user_input` | `slide_id`, `slide_partner_id` | 2 | →slide.slide, →slide.slide.partner |

- **Bridge key:** `slide.slide.survey_id` (the certification behind a slide) and
  the reverse `survey.user_input.slide_partner_id` (an attempt tied to one
  enrollment's attempt-pool). No standalone tables — the value is in the join.
- **Constraints:** SQL CHECK that a `certification` slide *must* have a
  `survey_id` and *cannot* be a preview.

## Behavior & Surfaces

- **Routes (2):** `GET /slides_survey/slide/get_certification_url` (auth=user,
  http) launches/resumes an attempt and 302-redirects into the survey;
  `POST /slides_survey/certification/search_read` (auth=user, jsonrpc) lists
  `certification=True` surveys for the upload dialog. Take-the-survey itself runs
  on the parent `survey` `/survey/*` routes.
- **Views (1 form) / Security:** 5 access rules, 5 record rules, **0 new groups**
  — it reuses `group_website_slides_officer/manager` and `group_survey_user`.
- **Frontend:** no new OWL components; it **patches** the eLearning upload UI
  (`SlideUploadCategory.prototype`, `SlideUploadDialog.prototype`) to add the
  Certification category + survey picker, plus a fullscreen-player script. Assets
  on `web.assets_frontend` (4) and `survey.survey_assets` (1).

**Behavioral facts (code-read, beyond metadata):**
- `slide.slide.create()` auto-flips any slide given a `survey_id` to
  `slide_category='certification'`; `_compute_mark_complete_actions` forbids
  self-marking it done — completion is earned *only* by passing the survey.
- `slide.slide._generate_certification_url` `_create_answer`s a
  `survey.user_input` with a fresh `invite_token` (a new per-enrollment attempt
  pool), or resumes an unfinished one; non-members get a `test_entry`.
- Pass cascade: `survey.user_input.scoring_success` →
  `slide.slide.partner.survey_scoring_success` → `_compute_field_value` writes
  `completed=True` → `_recompute_completion` sets
  `slide.channel.partner.survey_certification_success=True` (attendee Certified).
- `survey.user_input._check_for_failed_attempt`: a failed *last* attempt emails
  the candidate and calls `slide.channel._remove_membership` — un-enrolling them
  so they must re-enroll to retry (the in-code "re-purchase" flow).
- `survey.survey._unlink_except_linked_to_course` blocks deleting a survey still
  used as a course certification; `_ensure_challenge_category` retags the
  badge's challenge to `'slides'` so it surfaces on the eLearning badges page.

## Value-Configuration Classification

**Network (mediating), primary activity.** As a thin extension of
`website_slides`, it inherits the parent's value configuration: the eLearning
platform mediates between certification authors (officers) and learners, and a
credible, badge-backed credential raises membership value for both sides
(network/community effect via certificates, badges, leaderboards, profiles).
Its contribution — gating completion on a passed assessment and issuing a
certification — is an engagement/credentialing service on that network, not a
sequential transform (**not chain**); and although it consumes the `survey`
support engine, the certified-course offering is itself a core, monetizable line
(the code literally frames the fail-flow as letting a user "re-purchase" the
certification), so it is **primary**, not support.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — matching the parent
`website_slides`: certification is part of the public-facing eLearning product
and a conversion/retention lever. *(Secondary, inferred:* **7.0 Develop and
Manage Human Capital** — assess employee competency / corporate L&D credentialing
— when the academy is an internal training portal; but the out-of-box surface is
the external website, so Market & Sell is the primary fit.)*

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):
- `env['slide.slide'].search([('slide_category','=','certification')], limit=5).mapped(('name','channel_id','survey_id'))`
- `env['slide.channel.partner'].search([('survey_certification_success','=',True)], limit=5).mapped(('partner_id','channel_id'))`
- `env['survey.user_input'].search([('slide_id','!=',False),('state','=','done')], limit=5).mapped(('scoring_success','slide_id'))`

Curl (member, logged in): `GET /slides_survey/slide/get_certification_url?slide_id=<id>`
→ 302 to `/survey/start/<token>`.

## Open Questions

- Auto-created certification defaults (`attempts_limit=1`,
  `scoring_success_min=70`) are per-survey configurable — real values need
  runtime inspection.
- Live counts of issued certifications / certified attendees not captured
  (runtime `models_with_data = 0`).
- Whether the fail→un-enroll "re-purchase" flow is paired with paid courses
  (`website_sale_slides`) in a given install is outside this module.
- Exact karma/badge amounts depend on the linked survey's `gamification.badge` +
  challenge config (parent `survey`/`gamification`).

---
*Provenance: structural facts from `extract_module.py`
(`facts/website_slides_survey.facts.json`); frontend/integrations from
`extract_frontend.py`; behavioral notes from reading `models/slide_slide.py`,
`models/slide_channel.py`, `models/survey_survey.py`, `models/survey_user.py`,
`controllers/slides.py`, `controllers/survey.py`. Odoo 19.0.*
