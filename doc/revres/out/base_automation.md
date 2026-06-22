# base_automation — Architecture Brief

> Module: `base_automation` · Category: Sales/Sales · Depends: `base` · `digest` · `resource` · `mail` · `sms` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/base_automation.facts.json` · Frontend: `doc/revres/frontend/base_automation.frontend.json`

## 1. Summary

`base_automation` is the **Automation Rules engine** — a cross-cutting, no-code
event-condition-action (ECA) framework. A `base.automation` record says "when *event*
happens on *model* and *condition* holds, run these server actions". Events span record
lifecycle (create / write / unlink / archive / stage-set / tag-set / state-set /
priority-set / user-set), live UI on-change, inbound webhook, mail in/out, and time-based
schedules. It owns **no business object of its own**: 1 real model (`base.automation`,
26 fields), plus extensions of `ir.actions.server` (the executable effect) and `ir.cron`
(the scheduler), **1 public route** (`/web/hook/<uuid>`), ~1716 Python LOC. It is *not*
`auto_install`, but once present it is firm IT infrastructure that primary modules
(sale, crm, project…) bolt automated behaviour onto.

## 2. Structure (evidence)

- **Models:** `base.automation` (inherits `mail.thread`, `mail.activity.mixin`; 26 fields:
  `trigger`, `filter_pre_domain`, `filter_domain`, `trg_date_id`, `trg_date_range`,
  `trg_date_range_mode/type`, `trg_date_calendar_id`, `trigger_field_ids`,
  `on_change_field_ids`, `webhook_uuid`, `record_getter`, `action_server_ids`…) — the
  only real model. Plus extensions: `ir.actions.server` (`usage='base_automation'`,
  `base_automation_id`) and `ir.cron` (`action_open_automation`).
- **Routes (1):** `/web/hook/<string:rule_uuid>` (public — inbound webhook).
- **Security:** 1 access rule (`base.automation` read/write to `base.group_system`),
  0 record rules, 0 own groups.
- **Views:** 1 form + 1 list + 1 kanban + 1 search.

## 3. Frontend (gap #3) & Integrations (gap #7)

Small backend client footprint: **5 JS files, 3 XML templates, 1 OWL component**
(`ActionsOne2ManyField` — inline editor for the rule's server actions). **4 registry
adds:** `fields:base_automation_actions_one2many`, `fields:base_automation_trigger_selection`,
`error_dialogs:base_automation` (renders the `_add_postmortem` rule id/name when an action
throws), `group_config_items:open_automations`. **1 patch:** `GroupConfigMenu.prototype`
(adds an "open automations" entry). Services referenced: `model_is_mail_thread`, `name`,
`state`. Bundles: `web.assets_backend` (=1), `web.assets_unit_tests` (=1). None of this
trigger/condition UI wiring is visible in Python metadata. Integrations (gap #7):
**0 outbound HTTP call sites, 0 SDK imports, `uses_api_keys: false`, no endpoints** — the
only external surface is the *inbound* `/web/hook` webhook; outbound effects are delegated
to `ir.actions.server`.

## 4. Behavior (beyond metadata)

- **Runtime monkey-patching** (`_register_hook`): for each rule's `model_name`, patches the
  live registry class — `create`, `write` + `_compute_field_value`, `unlink`, `message_post`,
  and injects per-rule methods into `Model._onchange_methods`. Each patched method stores
  `method.origin`, calls it, then routes records into `_process()`. `_update_registry()`
  (fired from `base.automation` create/write/unlink on CRITICAL_FIELDS) re-installs patches
  and sets `registry_invalidated=True` so other workers reload. One new rule thus rewires an
  **unrelated** model's create/write/unlink at runtime, no static dependency. (code-read)
- **Pre/post conditions** (`_filter_pre` / `_filter_post`): on write, `make_write()`
  snapshots `old_values`, evaluates `filter_pre_domain` *before* the super() write (e.g.
  "was unpaid before"), runs the original write, then evaluates `filter_domain` (post);
  only survivors reach `_process`. `_check_trigger_fields()` diffs watched
  `trigger_field_ids` against `old_vals` to skip no-op writes. `filter_pre_domain` is never
  checked on create. (code-read)
- **Execution + loop guard** (`_process` → `ir.actions.server.run`): subtracts records in
  the context `__action_done` dict (automation → recordset) to stop recursive/duplicate
  firing, builds `active_model/active_id/active_ids` per record, then runs each linked
  `action_server_ids` under sudo. The actual effect (mail/follower/activity/Python/field
  update) lives in `ir.actions.server`; exceptions pass through `_add_postmortem`. (code-read)
- **Time scheduler** (`_cron_process_time_based_actions` / `_update_cron`): time triggers
  are NOT hooked into write — the cron `ir_cron_data_base_automation_check` scans them.
  `_search_time_based_automation_records(until=now)` computes a relative window from
  `last_run` + `trg_date_range` (before/after) + type, optionally honouring
  `trg_date_calendar_id` working days (`calendar.plan_days`); `_update_cron` auto-activates
  and shrinks the cron interval to ~10% of the smallest delay (1 min floor, 4 h ceiling). (code-read)
- **Webhook + on-change UI** (`/web/hook`, `make_onchange`): `_execute_webhook()`
  safe_evals `record_getter` against the JSON/query payload to resolve the record (optional
  `ir.logging`), then `_process`; on_change rules register live form-view onchange methods. (static)

## 5. IT architecture

- **Application:** Automation Rules engine — ECA triggers that monkey-patch target models
  and fire `ir.actions.server`.
- **Software services:** `/web/hook/<uuid>` (inbound webhook → `_execute_webhook` → `_process`).
- **Data objects:** `base.automation`; `ir.actions.server` (extended); `ir.cron` (extended).
- **Information flows:** rule CUD → `_update_registry` → `_register_hook` patches target
  `Model.create/write/unlink/_compute_field_value/message_post` + `_onchange_methods`;
  record event → patched method → `_filter_pre/_filter_post` → `_process` →
  `ir.actions.server.run`; cron → `_cron_process_time_based_actions`; external POST →
  `/web/hook` → `record_getter` → `_process`; loop-guard via `__action_done`.

## 6. Business architecture

- **Capabilities (inferred):** define ECA rules (no-code); react to record lifecycle events;
  evaluate pre/post conditions; schedule time-based automations (calendar-aware); fire live
  on-change automations; ingest inbound webhooks; execute linked server actions.
- **Value streams (inferred):** Rule-to-Effect (configure → patch → event → condition →
  action); Time-to-Effect (timed rule → cron scan → matched records → action);
  Webhook-to-Effect (POST → record resolve → condition → action).
- **Information concepts (auto):** `base.automation`, `ir.actions.server`, `ir.cron`,
  `trigger`/`filter_pre_domain`/`filter_domain`.
- **Organization (auto):** `base.group_system` (Settings) — sole access group. Products: none.
- **Policies (inferred):** rules ARE the policy layer (ECA across any model);
  `_check_trigger` / `_check_trigger_state` / `_check_action_server_model` enforce valid
  trigger-action combos; `__action_done` loop-guard; `filter_pre_domain` not checked on create.
- **Metrics (inferred):** `last_run` per timed rule; `ir.logging` webhook call log
  (`log_webhook_calls`, `action_view_webhook_logs`).
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Cross-cutting workflow-automation framework — firm IT
  infrastructure (Porter support activity; Stabell & Fjeldstad "support"). Its one real
  model holds rule *definitions*, not business documents; the work is `_register_hook`
  monkey-patching any target model and dispatching `ir.actions.server`. It creates no
  chain/shop/network value of its own — it is the trigger plumbing primary modules bolt
  onto (hence category "Sales/Sales" yet `application=false`, `auto_install=false`).
- **APQC: 8.0 Manage Information Technology.** Business-process-automation tooling — a
  concrete running engine (workflow runtime + scheduler + webhook endpoint) that IT
  develops, delivers and operates. **13.0 "Develop and Manage Business Capabilities"** was
  considered (rules arguably configure business behaviour) but rejected: 13.0 is the
  governance/portfolio/change-management capability, whereas `base_automation` is the IT
  solution being built and run — squarely 8.0. Mirrors the sibling `web` record.

## 8. Fit-to-Standard

- **Standard:** no-code ECA rules on any model (create/write/unlink/archive/stage/tag/
  state/priority/user-set); pre- and post-update domain conditions with old-value diffing;
  time-based triggers (date field / after-creation / after-update) with before/after delay
  and working-calendar support; live on-change (UI) automations; inbound webhook
  (`/web/hook/<uuid>`) with configurable `record_getter` + optional call logging; mail
  triggers; delegation to `ir.actions.server` effects (email, followers, activity, Python,
  field updates).
- **Typical fits:** auto-assign salesperson / set follower / send confirmation on stage;
  reminder activity N days before/after a date field; third-party webhook updating a record;
  field-derived defaults/validation via on_change code automations.
- **Common gaps:** complex/branching workflows need custom Python or a dedicated module;
  rule ordering on the same model is implicit; heavy `on_time` rules pressure the shared
  cron (auto-shrinks to 1 min); recursion needs care despite `__action_done`; **no outbound
  integrations** here (gap #7: 0 HTTP call sites) — only inbound webhook + server-action effects.
- **Drive hints:** `env['base.automation'].create({'name':'demo','model_id':env.ref('base.model_res_partner').id,'trigger':'on_create'})`
  then check the cron/registry updated; inspect `env.registry['res.partner'].create.origin`
  to confirm monkey-patching; `curl -X POST <base_url>/web/hook/<uuid>` with
  `{'_model':'res.partner','_id':1}`; `env['base.automation']._cron_process_time_based_actions()`.

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/base_automation.py`, `models/ir_actions_server.py`,
`security/ir.model.access.csv`. Odoo 19.0.*
