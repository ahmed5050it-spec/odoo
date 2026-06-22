# website_event_track_quiz — Architecture Brief

> Odoo 19.0 · category *Marketing/Events* · `application: false` · gamified
> **quizzes on event tracks**: attendees answer a quiz on a talk/track, earn
> points, and get ranked on a per-event community leaderboard. Depends on
> `website_profile`, `website_event_track`.

## 1. Purpose & classification

website_event_track_quiz is a **community-engagement extension** on the
website_event value network. It bolts an optional multiple-choice quiz onto each
`event.track` (a talk/session), lets anonymous and logged visitors answer it,
**scores the answers server-side**, stamps the result on the visitor, and rolls
the points up into an event-wide **leaderboard**. It owns the quiz authoring
objects (`event.quiz` / `.question` / `.answer`) and the per-visitor result
state.

- **Value model:** `network` (Stabell & Fjeldstad mediating technology) — it
  inherits its parents' logic: its worth is deepening the link between an open
  pool of attendees and the event's content via gamified scoring and ranking,
  not an input→output transformation (chain) or case work (shop).
- **Activity class:** `primary` — a customer-facing audience-engagement /
  event-marketing feature on the public website, not back-office support.
- **APQC:** **3.0 Market and Sell Products and Services** — same PCF home as
  `website_event` / `website_event_track`; the motion is engaging/retaining a
  marketed event's audience (demand side), not 6.0 post-sale service.

## 2. Data model (what it owns vs. extends)

| Model | Role |
|-------|------|
| `event.quiz` | a quiz attached to one `event.track` (`event_track_id`); `event_id` related/stored; `repeatable` = "Unlimited Tries". |
| `event.quiz.question` | gradeable question; `awarded_points` (compute = Σ answer points), `correct_answer_id` (compute = answers `is_correct`); cascade off the quiz. |
| `event.quiz.answer` | an option carrying `is_correct` + `awarded_points` (Integer) + explanatory `comment`; cascade off the question. |
| `event.track` *(extend)* | adds `quiz_id`/`quiz_ids`, `quiz_questions_count`, and the per-viewer `is_quiz_completed` / `quiz_points`. |
| `event.track.visitor` *(extend)* | the result row: `quiz_completed` (Boolean) + `quiz_points` (Integer) per attendee per track. |
| `event.event` *(extend)* | `_compute_community_menu` sync only. |

## 3. IT architecture (software services)

Routes (`controllers/event_track_quiz.py` extends `EventTrackController`;
`controllers/community.py` extends `EventCommunityController`):

- **Score (jsonrpc, public):** `/event_track/quiz/submit` — the core write;
  scores answers and writes the `event.track.visitor`.
- **Reset (jsonrpc, public):** `/event_track/quiz/reset` — zeroes the result,
  gated by `repeatable` / `event.group_event_manager`.
- **Leaderboard (http, public):** `/event/<event>/community/leaderboard`
  (+ `/results`, `/results/page/<int>`) and the overridden `/event/<event>/community`.

Data objects: `event.quiz`, `event.quiz.question`, `event.quiz.answer`,
`event.track`, `event.track.visitor`, `event.event`.

## 4. Key behaviors (code-read — beyond metadata)

1. **`event_track_quiz_submit` is the core write & scorer.** It resolves the
   caller via `track._get_event_track_visitors(force_create=True)`
   (force-creating a `website.visitor` + `event.track.visitor` for anonymous
   users), reads `answer_ids` **as sudo** (answers aren't public-readable),
   checks completeness (`len(answers.question_id) == quiz_questions_count` else
   `quiz_incomplete`), computes `points = sum(answer.awarded_points)`, then
   writes `quiz_completed=True, quiz_points=points` and returns the per-question
   correction. **An anonymous attendee earns real points.**
2. **Anti-cheat / one attempt.** Submit short-circuits with
   `{'error':'track_quiz_done'}` once `quiz_completed` is True (no point
   farming); the score is computed server-side as sudo, never trusted from the
   browser (client only POSTs `answer_ids`). `quiz/reset` raises
   `Forbidden` unless the user is an **event manager** *or* the quiz is
   `repeatable`.
3. **Scoring data model & integrity.** Points live on
   `event.quiz.answer.awarded_points`; the question's points/`correct_answer_id`
   are computes. `@api.constrains _check_answers_integrity` enforces **exactly 1
   correct answer and ≥2 answers** per question at write time — every question
   is gradeable.
4. **`event.track._compute_quiz_data` (`@api.depends_context('uid')`)**
   personalizes the page: it sudo `search_read`s `event.track.visitor` for the
   current visitor/partner and projects `is_quiz_completed`/`quiz_points` onto
   the track so the widget knows whether to lock itself.
5. **Leaderboard roll-up (`_get_leaderboard`).** Sudo `_read_group`s
   `event.track.visitor` over the event's tracks (`visitor_id` set,
   `quiz_points>0`) summing `quiz_points:sum` per visitor DESC, builds positions
   + top-3, highlights the current visitor; paginated 30/page (≤5 pager pages).

## 5. Frontend (static, gap #3)

2 JS files, 1 XML template, **no OWL components** — built as website
**public.interactions**. `Quiz` (`.o_quiz_main`) extracts questions/answers from
the server-rendered DOM, POSTs checked radio `answer_ids` to
`/event_track/quiz/submit`, then decorates each answer (check/cross icon,
points badge, comment) and re-renders the karma/validation box from the JSON
correction; reset POSTs `/event_track/quiz/reset`. `Leaderboard`
(`.o_wevent_quiz_scroll_to`) smooth-scrolls the current visitor's row into view.
Client templates: `quiz.badge` / `quiz.comment` / `quiz.validation`. Asset
bundle: `web.assets_frontend` (3).

## 6. Integrations (static, gap #7)

No outbound HTTP call sites and **no API keys**. The only endpoint is the
manifest's `https://www.odoo.com/app/events` reference (file: `__manifest__.py`).
All gamification logic is internal.

## 7. Business architecture & policies

- **Capabilities (inferred):** author track quizzes; gamified self-assessment on
  a talk; attendee points accumulation per track; one-attempt / repeatable
  gating; event community leaderboard.
- **Value stream (inferred):** *Engage-and-Score* — open track → answer quiz →
  server scores → `event.track.visitor` stamped → correction shown → points roll
  into the leaderboard.
- **Organization (auto):** `event.group_event_user` (authoring),
  `event.group_event_manager` (privileged reset).
- **Policies (inferred):** 3 ACLs restrict quiz authoring to event staff;
  server-side single-attempt anti-cheat; exactly-1-correct/≥2-answers integrity
  constraint; retake only if `repeatable`; only `quiz_points>0` visitor rows are
  ranked.
- **Metrics (inferred):** `quiz_points` per attendee/track, completion per
  track, max attainable points, leaderboard `quiz_points:sum` per visitor.
- **Strategy:** `null` (human).

## 8. Fit-to-Standard

- **Standard (out-of-box):** quiz attached to any track; per-answer point
  weighting with one-correct validation; public single-attempt taking with
  instant scored correction (icons, badges, comments); per-attendee points for
  anonymous + logged users; optional unlimited retries with manager reset;
  paginated per-event leaderboard with current-visitor highlight.
- **Typical fits:** conferences/trainings adding knowledge-check quizzes to
  talks; gamified engagement with a competitive leaderboard; free post-session
  self-assessment with feedback.
- **Common gaps:** karma/badge depth (awarding lives in
  `website_profile`/gamification glue, not here); per-question success-rate
  analytics; richer question types (multi-select/free-text/ordering);
  certification thresholds & time limits.
- **Drive hints:** `env['event.track.visitor'].sudo()._read_group([('quiz_points','>',0)],['visitor_id'],['quiz_points:sum'])`;
  `curl -s 'http://localhost:8069/event/1/community/leaderboard' | head`.
