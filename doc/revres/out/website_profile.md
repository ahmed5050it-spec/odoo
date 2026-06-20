# website_profile — Reverse-Engineering Brief

The **website_profile** module exposes Odoo's community members on the public website ("Access the website profile of the users", category *Website/Website*). It is a non-`application`, non-`auto_install` module that renders a public `/profile` space — per-user profile pages, a karma leaderboard, and a ranks-and-badges catalog — on top of the **gamification** engine. It sits on `gamification` (karma, ranks, badges ledger it reads but does not own), `website_partner` (partner↔website link for member identity), and `html_editor` (rich profile description editing). It owns almost no data of its own: a single re-declared model plus two inherit-only extensions. It is the member-facing reputation surface that **website_forum** and **website_slides (eLearning)** build their community pages on.

## Role & Dependencies

- **gamification** — provides `gamification.karma.rank`, `gamification.badge`, and the `res.users` karma ledger/`_recompute_rank` engine that this module renders publicly.
- **website_partner** — links `res.partner`/`res.users` to the website (publishable member identity) so profiles can be served on the front-end.
- **html_editor** — powers in-page editing of `website_description` (the profile bio) and is pulled into the frontend asset bundle.

Capability added on top: a privacy-gated public profile page, an all-time/weekly/monthly karma leaderboard, a published-badge + rank catalog, and a self-service profile editor with one-time email validation.

## Data Model (the ERM)

| _name | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `gamification.badge` | (extension) badge + `website.published.mixin` | 0 (mixin) | `_inherit`: gamification.badge, website.published.mixin |
| `res.users` | (extension) | 0 new | rank_id→gamification.karma.rank, partner_id→res.partner |
| `website` | (extension) | 1 | `karma_profile_min` (Integer, default 150) |

There is **no new central model** — the module is almost entirely controller + view logic. The only schema change is `website.karma_profile_min` (the minimum karma to view *other* users' profiles). `gamification.badge` is re-declared purely to graft `website.published.mixin` onto it (so individual badges become publishable), and `res.users` is widened (exposes `karma` for read; allows self-edit of `country_id/city/website/website_description/website_published`). Field-type distribution is therefore trivially **non-relational** (1 Integer) — the value of this module is behavioral, not structural.

## Behavior & Surfaces

- **Routes:** 8 routes — 5 public `http` profile pages (`/profile/user/<id>`, `/profile/avatar/<id>`, `/profile/users[/page/<n>]`, `/profile/ranks_badges`, `/profile/validate_email`) and 3 `auth=user`/`public` `jsonrpc` actions (`/profile/user/save`, `/profile/send_validation_email`, `/profile/validate_email/close`). A read-heavy public web surface, not an RPC API.
- **Views:** form 2 only (no backend list/kanban/search). The UX lives entirely in QWeb website templates rendered by the controller (profile page, podium leaderboard, ranks/badges grid), plus the OWL `ProfileDialog` and 4 website public-interactions.
- **Security posture:** 1 access rule (karma ranks editable by `website.group_website_restricted_editor`), **0 record rules, 0 groups**. Access control is enforced in *controller code* (`website_published` + karma threshold), not via ORM record rules.

## Value-Configuration Classification

**Value model: `network`** (Stabell & Fjeldstad value-network), **activity_class: primary**. website_profile mediates *member visibility and reputation* — it neither transforms inputs (chain) nor matches buyers/sellers (shop). Its value is the network of published members and the karma/rank/badge reputation linking them, surfaced through public profile pages, a leaderboard ranked by karma gain, and per-member rank progression. It is the primary member-facing activity of the community stack and underpins forum + eLearning. This is distinct from the `gamification` engine it consumes, which is HR-support (value-support) reward machinery; here that ledger is repurposed as a public community/reputation layer.

## APQC PCF Hint

**3.0 Market and Sell Products and Services** — building and managing the customer/member community (audience and reputation building). The public profiles, leaderboard, and ranks/badges are community-marketing engagement surfaces, distinct from the gamification engine's HR mapping (7.0 Develop and Manage Human Capital).

## How to Drive It

Use the **run-odoo** skill (`odoo shell`):

- `env['res.users'].search([('karma','>',1),('website_published','=',True)], order='karma desc', limit=5).mapped(('login','karma','rank_id.name'))` — inspect the leaderboard population.
- `env['gamification.karma.rank'].search([], order='karma_min desc').mapped(('name','karma_min'))` — list the rank thresholds rendered on `/profile/ranks_badges`.
- `env['website'].browse(1).karma_profile_min` — read the privacy threshold (default 150) gating cross-member profile views.

Routes (public `http`): `curl` `/profile/ranks_badges` and `/profile/users` (only `website_published` users with `karma>1` appear); `/profile/user/<id>` is denied unless the target is published and the viewer's karma ≥ `karma_profile_min`.

## Open Questions

- **Karma point values (inferred):** the karma awards that drive ranks/leaderboard are defined by consumer modules (forum/website_slides), not website_profile — confirm in those addons.
- **Profile extension hooks:** how `website_forum`/`website_slides` extend the page (`badge_category` filters, extra tabs) via the `_prepare_*` controller hooks.
- **Leaderboard SQL semantics:** the period ranking comes from `res.users._get_user_ids_ranked_by_karma` (raw SQL summing `gamification.karma.tracking`); behavior under large/empty tracking sets is not visible in metadata.
- **Deployment tuning:** whether `karma_profile_min` is commonly retuned from its 150 default.

---
*Provenance: facts from `doc/revres/extract_module.py` (facts/website_profile.facts.json) + `extract_frontend.py`; behavioral notes from reading `addons/website_profile/controllers/main.py`, `addons/website_profile/models/{res_users,gamification_badge,website}.py`, `addons/website_profile/controllers/portal.py`, and `addons/gamification/models/{gamification_karma_rank,res_users}.py`. Odoo 19.0.*
