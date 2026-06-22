# survey — Reverse-Engineering Brief

The **survey** module (`Surveys`, category *Marketing/Surveys*, `application=True`,
`auto_install=False`) is Odoo's horizontal **assessment / feedback engine**. It lets
users design surveys, scored assessments, certifications and real-time *live sessions*,
share them by public link or invitation, collect and validate answers, score them and
publish per-question statistics. It sits on top of `mail` (threads, invitations, templates),
`http_routing` + `auth_signup` (public/portal answering, signup), `web_tour` (onboarding)
and `gamification` (certification badges/challenges). It ships no `product.*` model and
creates no accounting/stock documents — it is consumed *by* other apps (recruitment,
eLearning/slides, rating, marketing) rather than driving a document chain.

## Role & Dependencies

- **mail** — `survey.survey`/`survey.user_input` are `mail.thread`/`mail.activity.mixin`; invitations and certification mails use `mail.template`; `survey.invite` is a `mail.composer.mixin`.
- **auth_signup** — token-gated public answering with optional login/signup for invited respondents (`users_can_signup`, signup URL flow in the controller).
- **http_routing** — website-enabled public routes (`website=True`) for taking/printing surveys.
- **web_tour** — onboarding tour (`web_tour.tours:survey_tour`).
- **gamification** — certifications can award a `gamification.badge` via a generated `gamification.challenge`/goal.

Capability added on top: a complete questionnaire designer + token-secured public answer
runtime + scoring/certification + live-session quiz with leaderboard.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|-------------|--------|---------------|
| survey.survey | Survey | 57 | question_and_page_ids→survey.question, user_input_ids→survey.user_input, certification_badge_id→gamification.badge |
| survey.question | Survey Question | 56 | survey_id→survey.survey, suggested_answer_ids/matrix_row_ids→survey.question.answer, triggering_answer_ids (conditional) |
| survey.question.answer | Survey Label | 11 | question_id / matrix_question_id→survey.question |
| survey.user_input | Survey User Input | 27 | survey_id→survey.survey, partner_id→res.partner, user_input_line_ids→survey.user_input.line |
| survey.user_input.line | Survey User Input Line | 18 | user_input_id→survey.user_input, question_id→survey.question, suggested_answer_id→survey.question.answer |
| survey.invite | Survey Invitation Wizard | 17 | survey_id→survey.survey, partner_ids→res.partner (mixin: mail.composer.mixin) |

The **central aggregate** is `survey.survey`; the **definition** side is `survey.question`
(self-referential — pages reuse the same model via `is_page`) + `survey.question.answer`;
the **response** side is `survey.user_input` → `survey.user_input.line`. Mixin/extension
records (`_inherit` only): `gamification.badge`, `gamification.challenge`, `ir.http`,
`res.lang`, `res.partner` (certifications_count). Field distribution is heavily
**attribute/config** oriented (Boolean 40, Integer 26, Selection 20) — reflecting the many
scoring/validation/session toggles — with a solid relational core (Many2one 24, *2many 19).

## Behavior & Surfaces

- **Routes (22):** a mix of public `http` (take/start/print/retry, background & question images), public `jsonrpc` AJAX navigation (`/survey/begin|next_question|submit`), `user`-auth management (test, certification download, results, full live-session host API) and short links `/s/<code>` for session join. This is a large, mostly **public-facing web surface** guarded by tokens, not by ACLs.
- **Views:** list (9) and form (7) dominate for back-office design, plus kanban (2), search (5), pivot/graph (1 each) and activity (1) for the results/analytics side.
- **Security posture:** 22 access rules, 12 record rules, **2 groups** (`group_survey_user`, `group_survey_manager`). Record rules scope officers by `survey.restrict_user_ids` and partition `survey.user_input`/`.line` on `survey_type ∈ (assessment, custom, live_session, survey)` so embedding apps keep their own responses. Public answering bypasses ACLs through sudo + a two-token (survey `access_token` + per-attempt `answer_token`) scheme re-validated on every call.

Behavioral facts not in metadata (code-read): scoring is fully Python-computed
(`_compute_answer_score`, with live-session time-decay), `_mark_done` fires certification
email + gamification badge cron + follower notification, `validate_question` implements
per-type server-side validation for all 9 question types, and live sessions broadcast the
next question over `bus.bus` choosing it from the audience's most-voted answers.

## Value-Configuration Classification

**Support** (Stabell & Fjeldstad). Survey is a reusable, cross-cutting capability: it
transforms no material (not **chain**), its core is not a per-case solution loop (not
**shop**), and it provides no matching/mediation layer (not **network**). It is consumed by
primary activities — recruitment screening, eLearning quizzes/certifications, marketing/NPS,
the rating module — which the `survey_type`-scoped record rules make explicit. Its
**activity_class is support** (infrastructure, not a line of business).

## APQC PCF Hint

Best fit **13.0 Develop and Manage Business Capabilities** — it is a capability/competency
measurement, knowledge-assessment and certification tool. Secondary fits: **3.5.x** customer
& market feedback (manifest category *Marketing/Surveys*) and **7.x** human-capital
competency assessment when driven by HR/eLearning.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['survey.survey'].search([], limit=5).mapped(('title','survey_type','scoring_type','certification'))`
- `env['survey.user_input'].search([('state','=','done')], limit=5).mapped(('survey_id','scoring_percentage','scoring_success'))`

Web: `curl` a public take-survey at `GET /survey/start/<survey access_token>` (auth=public),
then drive AJAX with jsonrpc `POST /survey/submit/<survey_token>/<answer_token>`; download a
certificate via `GET /survey/<id>/get_certification` (auth=user, only if passed).

## Open Questions

- Which downstream apps (recruitment / slides / rating) actually embed survey in this install — facts cover the survey module only.
- Whether certification surveys award real `gamification.badge` records at runtime (no runtime row counts were captured).
- How "most-voted-answer" conditional branching scales in large live sessions.
- Which `scoring_type` modes are used in practice and how `scoring_success_min` is tuned.

*Provenance: facts from `extract_module.py` (`doc/revres/facts/survey.facts.json`) +
`extract_frontend.py`; behavioral notes from reading `models/survey_survey.py`,
`survey_question.py`, `survey_user_input.py`, `controllers/main.py`. Odoo 19.0.*
