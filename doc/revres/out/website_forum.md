# website_forum — Architecture Brief (Q&A Forum)

> Odoo 19.0 subsystem record produced by the code-explorer + code-architect workflow.
> Evidence: `doc/revres/facts/website_forum.facts.json`, `doc/revres/frontend/website_forum.frontend.json`,
> and code-reads of `models/forum_post.py`, `models/forum_forum.py`, `controllers/website_forum.py`.
> Metamodel: `doc/revres/metamodel/website_forum.metamodel.json` (schema-valid).

## 1. Overview

`website_forum` (manifest name **Forum**, category **Website/Website**, version 1.2, LGPL-3, author Odoo S.A.)
adds a Stack-Overflow-style **Q&A / FAQ community forum** to an Odoo website. It depends on
`auth_signup`, `website_mail`, and `website_profile`, is not auto-installed, and is not flagged as an
application. The module is substantial for its model count: **5 own models**, **40 `/forum/*` routes**,
~3,700 Python LOC and ~4,350 XML LOC. Its defining trait is that **questions and answers are the same
self-referential model** (`forum.post`), and every user action is **gated by a per-forum karma
(reputation) economy** enforced in Python, with **gamification badges/challenges** layered on top.

## 2. Evidence (facts — code-explorer)

**Models (5 own + inherited extensions):**
- `forum.forum` — the forum container (~60 fields, mostly Integer `karma_*` thresholds + computed
  statistics); inherits `mail.thread`, `image.mixin`, `website.seo.metadata`, `website.multi.mixin`,
  `website.searchable.mixin`.
- `forum.post` — **Forum Post**: both questions (`parent_id=False`) and answers (`parent_id` set,
  `child_ids`); 58 fields incl. `state`, `is_correct`, `vote_count`, `relevancy`, and ~16 computed
  `can_*` permission booleans. Inherits `mail.thread`, `website.seo.metadata`, `website.searchable.mixin`.
- `forum.post.vote` — a (post, user, vote ∈ {-1,0,1}) record.
- `forum.tag` — tags (many2many to posts), with `posts_count`.
- `forum.post.reason` — closing/offensive reasons.
- Inherited (no new `_name`): `gamification.challenge` (+`challenge_category='forum'`),
  `gamification.karma.tracking`, `res.users`, `website` (`forum_count`), `ir.attachment`.

**Routes:** 40 routes under `/forum/*` (controller extends `website_profile.WebsiteProfile`): public
browse (`/forum`, `/forum/all`, `/forum/<forum>`, `/forum/<forum>/faq`, `/forum/get_tags`); authenticated
ask/answer/edit (`/ask`, `/new`, `/question/<question>`, `…/edit`, `…/save`); jsonrpc actions
(`…/upvote`, `…/downvote`, `…/toggle_correct`, `…/toggle_favourite`, `…/flag`, `…/comment/<…>/convert_to_answer`);
and moderation queues (`/validation_queue`, `/flagged_queue`, `/offensive_posts`, `/closed_posts`,
`…/validate`, `…/refuse`, `…/mark_as_offensive`).

**Security:** 15 ir.model.access rules, 12 record rules, **0 new groups** — access reuses
`base.group_public / portal / user / erp_manager`; real authorisation is the karma economy + record rules
(website-domain + `can_view`).

**Views:** 15 form, 5 list, 1 kanban, 2 search, 1 graph.

**Frontend (gap #3, static):** 17 JS files, 6 XML templates, 2 OWL components
(`FlagMarkAsOffensiveDialog`, `WebsiteForumTagsWrapper`), 5 registry adds (4 `public.interactions`
for the forum / share / spam / profile-activity widgets + view `website_forum_add_form`), patch
`NewContentSystrayItem.prototype` (adds "Forum Post" to the website New-content menu). Asset bundles
include `web.assets_frontend` (7) and `website.assets_editor`.

**Integrations (gap #7, static):** 1 HTTP call site, `requests` imported; endpoints
`https://schema.org` (QAPage microdata vocabulary) and `https://www.odoo.com/app/forum`; no API keys.

**Runtime (gap #5/#6):** not captured (`models_with_data = 0`).

## 3. Behavioral notes (what metadata cannot show — code-read)

1. **Question/answer hierarchy is one model.** `parent_id=False` ⇒ question; `parent_id` set ⇒ answer
   (`child_ids`). Comments are `mail.message` on the post; `convert_answer_to_comment` /
   `convert_comment_to_answer` move content between forms. The single self-referential `forum.post`
   implements the whole Q&A tree (`_order = is_correct DESC, vote_count DESC, last_activity_date DESC`).
2. **Accept-answer is a dual-karma side-effect.** `write({'is_correct': True})` awards the answer author
   `karma_gen_answer_accepted` (default 15) **and** the acceptor `karma_gen_answer_accept` (default 2),
   reverses on un-accept, and is refused below `karma_answer_accept_own/all`. `has_validated_answer`
   recomputes on the question.
3. **Every action is karma-gated.** `_compute_post_karma_rights` derives ~16 `can_*` booleans by
   comparing `res.users.karma` to per-forum thresholds (`karma_edit_own=1` vs `karma_edit_all=300`,
   `karma_close_own=100`/`_all=500`, `karma_upvote=5`, `karma_downvote=50`, `karma_flag=500`,
   `karma_moderate=1000`, …). `create`/`write`/`vote`/`message_post` re-check and raise `AccessError`;
   `_update_content` strips links to `rel=nofollow` and blocks images/links below `karma_dofollow`/`karma_editor`.
4. **Vote → reputation → ranking loop.** `vote()` writes a `forum.post.vote`; `vote_count` (stored sum)
   feeds `relevancy` (time-decayed score) and the default ordering, and casting a vote generates karma on
   the post author (`karma_gen_question_upvote=5`, `karma_gen_answer_upvote=10`, downvotes negative).
5. **Moderation state machine.** `state ∈ {active, pending, close, offensive, flagged}`. Questions from
   users below `karma_post` (default 100) are forced `pending` and routed to moderators; `validate()`
   activates and awards deferred karma; `close()` / `_mark_as_offensive()` / `_flag()` apply penalties
   (`karma_gen_answer_flagged=-100`, ×10 for a spammer's first post). `_notify_state_update` posts
   threaded notifications to followers and tag-followers.
6. **Gamification badges + karma tracking.** Inherits `gamification.challenge`/`gamification.karma.tracking`
   and ships ~29 `gamification.badge` records across 4 files — question (Student, Nice/Good/Great Question,
   Popular/Notable/Famous, Scholar…), answer (Teacher, Enlightened, Guru, Self-Learner…), participation
   (Autobiographer, Commentator, Pundit, Taxonomist…), moderation (Cleanup, Critic, Editor, Supporter…).
   Awards are computed by the gamification engine, not by website_forum metadata.
7. **SEO microdata + related posts.** `_get_microdata` emits schema.org **QAPage / Question / Answer**
   JSON-LD (acceptedAnswer + suggestedAnswer); `_get_related_posts` runs a raw-SQL **Jaccard tag-similarity**
   query.
8. **Frontend (static).** 2 OWL components + 4 `public.interactions` widgets drive the public forum UI;
   `NewContentSystrayItem` patch surfaces "Forum Post" in the website editor.

## 4. IT architecture (code-architect)

- **Application:** `website_forum` Q&A forum website component.
- **Software services:** 40 `/forum/*` routes — public browse (http), authenticated ask/answer/edit (http),
  jsonrpc actions (upvote/downvote/toggle_correct/flag/favourite), and moderation queues.
- **Data objects:** `forum.forum`, `forum.post`, `forum.post.vote`, `forum.tag`, `forum.post.reason`.
- **Logical ERM:** `forum.post → forum.forum`; `forum.post → forum.post` (parent/child question-answer tree);
  `forum.post.vote → forum.post`, `→ res.users`; `forum.post ↔ forum.tag`; `forum.post → forum.post.reason`.
- **Information flows:** depends on `auth_signup`, `website_mail`, `website_profile`; cross-model
  side-effects = accept/vote/close/flag → `res.users.karma` via `gamification.karma.tracking`; pending-queue
  moderation via `mail.thread`; QAPage microdata for SEO; outbound `requests` (schema.org, odoo.com).
- **Frontend components:** `FlagMarkAsOffensiveDialog`, `WebsiteForumTagsWrapper`.

## 5. Business architecture (code-architect; Business Architecture Guild v3.0)

- **Capabilities (inferred):** Host Q&A/FAQ Community Forums · Ask Questions & Post Answers (accept best) ·
  Reputation/Karma Management · Community Moderation · Tagging & Content Discovery (search, related, SEO).
- **Value streams (inferred):** *Question-to-Answer* (ask → peers answer → community votes → asker accepts
  best → reputation distributed); *Content moderation* (post → pending/flagged queue → validate/close/mark
  offensive → karma adjusted).
- **Information concepts (auto):** forum.forum, forum.post (question/answer), forum.post.vote, forum.tag,
  res.users (member/karma).
- **Organization (auto):** base.group_public / portal / user (read) + base.group_erp_manager (forum admin).
- **Products (auto):** none (no `product.*`).
- **Policies (inferred):** karma thresholds gate every action; 12 record rules (website-domain + `can_view`
  own-or-positive-karma scoping) + forum `privacy` public/connected/private(group).
- **Stakeholders:** Asker, Answerer, Moderator (high-karma), public website/SEO reader.
- **Strategy (human):** null.
- **Metrics (inferred):** forum statistics (`total_posts/views/answers/favorites`); per-post
  `vote_count/favourite_count/child_count/relevancy/views`; user karma + badges.

## 6. Classification

| Field | Value |
|------|-------|
| **value_model** | **network** |
| **activity_class** | **primary** |
| **apqc_category** | **3.0 Market and Sell Products and Services** (alt: 6.0 Manage Customer Service) |

**Rationale.** *Network* (Stabell & Fjeldstad): website_forum is **mediating technology** — it links members
who want to be interdependent (askers seeking answers, answerers seeking reputation) and creates value by
**enabling and orchestrating their exchanges**, not by transforming inputs (chain) or matching a problem to a
stored solution (shop). Platform value **grows with the size/activity of the community and the accumulated
content**: the self-referential question/answer tree, the vote→karma→badge reputation loop, and tag-based
discovery are textbook network-mediation infrastructure (membership via `auth_signup`, capacity utilisation
via relevancy/ranking). *Primary*: the forum is the customer-facing value-producing website asset itself, not
an internal enabling function. *APQC 3.0*: the manifest category is **Website/Website** and the out-of-box
welcome message frames the forum as a marketing/community asset ("build your professional profile and become
a better marketer together"); it drives SEO (QAPage microdata), brand community, top-of-funnel engagement and
sign-up — Market-and-Sell rather than transactional sales. The equally-defensible alternative is **6.0 Manage
Customer Service** (self-service / community knowledge-base deflection) when deployed as post-sale peer
support; 3.0 was chosen because the default framing, Website category, and SEO/community-marketing mechanics
weight it toward marketing/community engagement.

## 7. Fit-to-Standard

- **Standard (out-of-box):** multi-forum Q&A + FAQ (Questions=1 answer / Discussions=many); karma engine
  with per-forum, per-action thresholds; voting, accept-best-answer, favorites, tags & related posts;
  moderation workflow (pending validation, flagging, close-with-reason, mark-offensive); ~29 badges +
  challenges; SEO (QAPage microdata, sitemap, website-builder integration).
- **Typical fits:** public community/support forum embedded in an Odoo website; reputation-gated
  self-moderating community (tune `karma_*` in the forum form); private/members-only forum
  (`privacy=connected/private` + `authorized_group_id`); branded FAQ/knowledge-base.
- **Common gaps:** custom karma/badge rules beyond defaults; external SSO/federated identity beyond
  `auth_signup`; ML/anti-spam beyond manual flag+karma; cross-site syndication / publishing API; bespoke
  reputation analytics/leaderboards.
- **Drive hints:**
  - `odoo shell`: `env['forum.forum'].search([]).mapped(('name','total_posts','total_answers'))`
  - `odoo shell`: `env['forum.post'].search([('is_correct','=',True)], limit=5).mapped(('name','vote_count','forum_id.name'))`
  - `curl -s http://localhost:8069/forum` (public HTML forum index)
  - jsonrpc `POST /forum/<forum_id>/post/<post_id>/upvote` (auth=user) → `{'vote_count','user_vote'}`

## 8. Open questions

- Exact gamification **challenge** definitions mapping karma/activity to each of the ~29 badges (live in
  gamification config, not website_forum code).
- Whether a given deployment runs the forum as **marketing/community (APQC 3.0)** or **post-sale self-service
  support (APQC 6.0)** — a business-intent decision, not code.
- Real distribution of post **states and karma levels** (runtime not captured;
  `runtime.models_with_data = 0`).

---
*Confidence: information_concepts/organization/products = auto; capabilities/value_streams/policies/metrics/
stakeholders = inferred; strategy = human. Provenance: `doc/revres/facts/website_forum.facts.json`,
`extract_frontend.py`, `extract_module.py`, code-read. Odoo 19.0.*
