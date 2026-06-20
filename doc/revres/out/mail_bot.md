# mail_bot — OdooBot (Architecture Brief)

> Module: `addons/mail_bot` · Odoo 19.0 · DEEP record
> Facts: `doc/revres/facts/mail_bot.facts.json` · Metamodel: `doc/revres/metamodel/mail_bot.metamodel.json`

## 1. Summary
OdooBot is the scripted onboarding chatbot that greets a new internal user on their first
Discuss session and walks them through core messaging features. It is `auto_install` with
`mail`, depends only on `mail`, and ships ~446 Python LOC, one inherited form view, and one
SCSS asset. There is **no AI/NLU**: every reply is a hard-coded string chosen by matching the
user's `res.users.odoobot_state` against the content of their message. The module owns no
business object of its own — `mail.bot` is an `AbstractModel`.

## 2. IT Architecture
- **Application:** OdooBot, a thin behavioral layer on the Discuss/mail subsystem.
- **Data objects:** `mail.bot` (abstract reply engine), `discuss.channel` (inherited — hooks),
  `res.users` (inherited — adds `odoobot_state` Selection + `odoobot_failed` Boolean).
- **Service:** one route override — `mail.controllers.thread.ThreadController.mail_message_post`
  forwards `canned_response_ids` into the request context so the canned-response step can fire.
- **Flows:** `depends: mail`; user `message_post` → `discuss.channel._message_post_after_hook`
  → `mail.bot._apply_logic` → (if matched) OdooBot reply. `odoobot_state` is the thread of
  control across every step.

## 3. Behavioral Notes (code-read)
- **`_apply_logic` / `_get_answer` state machine** (`mail_bot.py:14/54`): short-circuits unless
  the message is a non-bot `comment` in a `chat` channel where `base.partner_root` is a member;
  replies keyed jointly on `odoobot_state` and content (emoji / `/help` command / `@OdooBot` ping
  in `partner_ids` / `attachment_ids` / `canned_response_ids`). Each match advances the state and
  clears `odoobot_failed`; mismatches set `odoobot_failed=True` and re-prompt.
- **`_message_post_after_hook` trigger** (`discuss_channel.py:13`): the inherited channel calls
  `_apply_logic` on **every** posted message before `super()`; the bot self-filters and answers
  via `channel.sudo().message_post(author_id=odoobot, silent=True)`. `execute_command_help`
  feeds `command='help'` for the `/help` step.
- **`_init_odoobot` / partner setup** (`res_users.py:28/33`): OdooBot **is** the existing
  `base.partner_root` partner (no dedicated bot user). `_on_webclient_bootstrap` fires onboarding
  the first time an internal user (`_is_internal`) loads the webclient with `odoobot_state` in
  {False, not_initialized}: opens the OdooBot chat, posts the greeting, sets `onboarding_emoji`.
- **Onboarding side-effects** (`mail_bot.py:89-118`): the attachment step **creates** a temporary
  `mail.canned.response`; the canned step **unlinks** it and sets `idle`. `mailbot_data.xml` hard-
  sets `base.user_root` to `odoobot_state='disabled'` (admin excluded).
- **Frontend (static):** 0 JS / 0 OWL components; the only asset is `odoobot_style.scss` in
  `web.assets_backend` (styles the `o_odoobot_command` span). All chat UI is inherited from mail.

## 4. Business Architecture
- **Capabilities (inferred):** user onboarding / product discovery; conversational assistance;
  onboarding-progress tracking; feature-walkthrough orchestration.
- **Value streams (inferred):** *Onboard-New-User* (first load → auto chat → guided steps → idle)
  and *Assist-On-Demand* (message / `/help` → scripted reply or doc/video links).
- **Information concepts (auto):** `mail.bot`, `res.users.odoobot_state`, `discuss.channel`.
- **Organization (auto):** `base.group_user` (audience), `base.group_no_one` (debug-only field
  exposure). No own groups.
- **Policies (inferred):** internal-only; root disabled; replies only in chat channels with the
  bot present; per-step gating on state + content.
- **Strategy:** null (human). **Metrics (inferred):** `odoobot_state` funnel, `odoobot_failed` counts.

## 5. Classification
- **value_model:** `support` · **activity_class:** `support`
- **apqc_category:** **9.4 Manage internal communications**
- **Rationale:** owns no business object and produces no product/revenue document; it is internal
  onboarding/assistance infrastructure on the messaging layer, consumed across all activities and
  never part of a primary value chain. 13.0 (knowledge/enablement) is a defensible alternative,
  but the deliverable is a guided internal conversation, so 9.4 fits closer.

## 6. Fit-to-Standard
- **Standard:** zero-config auto-launched onboarding chat; scripted emoji → `/command` → `@ping`
  → attachment → `::` canned → idle walkthrough; rule-based help/easter-egg replies; per-user
  progress in `odoobot_state` (re-runnable via "start the tour").
- **Typical fits:** OOTB new-employee Discuss onboarding; disable per user via
  `odoobot_state='disabled'`.
- **Common gaps:** no real NLU (hard-coded matches); script not UI-configurable; single fixed
  persona; static hard-coded emoji Unicode ranges can drift.

## 7. Drive Hints
- `env.ref('base.user_root').odoobot_state` → expect `'disabled'`.
- `env['res.users'].read_group([], ['id'], ['odoobot_state'])` → onboarding funnel.
- Force open: set a non-share user's `odoobot_state='not_initialized'` then `u._init_odoobot()`.
- Exercise reply: `_get_or_create_chat([partner_root, user.partner])` then `message_post(body='start the tour')`.

## 8. Open Questions
- Is onboarding completion/abandonment reported beyond the raw `odoobot_state` field? (no analytics view found)
- Interaction with any localized onboarding variants (none present in this module).
- Full set of slash commands routed via `execute_command_help` vs other channel command hooks.
