# sms (SMS gateway) — Architecture Brief

> Module `sms`, display name **"SMS gateway"** (`odoo/addons/sms/`). Odoo's SMS
> text-messaging channel: send SMS from any record, SMS templates, a composer
> (single/numbers/mass), and delivery tracking — all delivered through Odoo IAP.
> `depends = [base, iap_mail, mail, phone_validation]`, `auto_install = True`.
> 9 own models, 1 route (`/sms/status`), ~2.5k Python LOC. It is the SMS sibling of
> `mail`: it plugs into `mail.thread`'s notification pipeline rather than standing alone.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). sms is cross-cutting messaging
  infrastructure — an SMS delivery channel — not a primary value chain. `auto_install=True`
  alongside `mail` confirms it is shared plumbing consumed by marketing, CRM, and
  transactional notifications.
- **activity_class: support.**
- **apqc_category:** best fit **9.4 internal communications** (the firm-wide
  communication-infrastructure category that also houses `mail`); the concrete anchor in
  `apqc_odoo_map.tsv` is **3.5.4.8 Handle sales order inquiries (post-order)** =
  SMS chatter (`_message_sms`) on a `sale.order` (tagged support).
- **Why 9.4 over 3.x:** sms *itself* is channel infrastructure, not a selling act. A
  3.x Market-and-Sell code applies only derivatively, when the SMS happens to notify on a
  sales record — so 9.4 (internal/operational communication) is the home category and
  3.5.4.8 is the representative downstream application.
- **External integration (gap #7):** all sending routes through **Odoo IAP**
  (`https://sms.api.odoo.com`) via `iap_tools.iap_jsonrpc`, with an inbound `/sms/status`
  webhook for delivery reports.

## 2. IT Architecture

- **Application:** sms — an SMS delivery channel layered on mail's notification pipeline.
- **Software services (routes):** `/sms/status` (public `jsonrpc`) — the IAP
  delivery-report webhook. That is the module's only HTTP surface; sending is outbound to IAP.
- **Core data objects:** `sms.sms` (outgoing SMS), `sms.template` (per-model template),
  `sms.composer` (send wizard), `sms.tracker` (SMS↔notification/trace bridge keyed by uuid),
  `sms.template.preview` / `sms.template.reset`, and three IAP account wizards
  (`sms.account.phone` / `.code` / `.sender`). Plus inherit-only extensions of
  `mail.thread`, `mail.message`, `mail.notification`, `mail.followers`, `iap.account`,
  `ir.actions.server`, `ir.model`, `res.company`.
- **Key ERM:** `sms.sms → mail.message (mail_message_id)`, `→ res.partner (partner_id)`,
  `→ sms.tracker` (via shared `uuid`); `sms.tracker → mail.notification`;
  `sms.template → ir.model (is_mail_thread_sms only)`; `sms.composer → sms.template`;
  `iap.account` (extended with `sender_name`) → external IAP SMS service.

## 3. Behavioral Notes (code-read, the metadata gap)

1. **`sms.sms.send` / `_send_with_api`** (`sms_sms.py:99`) locks `outgoing` rows, groups by
   API + batch, groups by body, and calls `SmsApi._send_sms_batch` → POST to the external
   IAP endpoint `https://sms.api.odoo.com /api/sms/3/send`. The docstring warns it contacts
   an external server and a failed transaction may be **retried, sending duplicate SMS**.
   IAP states map via `IAP_TO_SMS_STATE_SUCCESS` / `PROVIDER_TO_SMS_FAILURE_TYPE`.
2. **Queue + state machine.** `create()` triggers the `sms.ir_cron_sms_scheduler_action`
   cron; `_process_queue` (`:151`) batch-sends (`sms.session.batch.size`, default 500) and
   calls `_commit_progress`. State flows `outgoing → process → pending(=Sent) →
   sent(=Delivered)` or `error`/`canceled`; sent rows are marked `to_delete` and an
   `@api.autovacuum` GC hard-deletes them, while the `mail.notification` persists for the icon.
3. **`sms.template`** (`sms_template.py`) is thin: `body` is a `Char` rendered against the
   related model via `mail.render.mixin`; `model_id` is domain-limited to models flagged
   `is_mail_thread_sms`. `action_create_sidebar_action` generates a contextual
   `ir.actions.act_window` so "Send SMS (<tpl>)" opens the composer. Formulas live in Python.
4. **`mail.thread._notify_thread_by_sms`** — SMS is a `mail` notification channel. For
   recipients with `notif=='sms'` it creates `sms.sms` (sudo) + `mail.notification(type='sms')`
   + an `sms.tracker`, then sends immediately unless `put_in_queue`. `message_post` with
   `message_type='sms'` keeps the raw body for the SMS and renders HTML for the chatter — any
   `mail.thread` model gains SMS with no schema change (sibling of the email channel).
5. **Phone formatting + blacklist.** Numbers are sanitized to international format via
   `record._phone_format` (phone_validation); the composer raises `UserError` on invalid.
   Mass mode (`_prepare_mass_sms_values`) marks recipients `canceled` with `sms_blacklist`
   (against `phone.blacklist`), `sms_duplicate`, `sms_optout`, or `sms_number_*` **before**
   any IAP call. Opt-out is a no-op hook here (delegated to SMS Marketing).
6. **`/sms/status` webhook** (`controllers/main.py`) receives batched delivery reports from
   IAP keyed by `sms.uuid`, validates uuid/status format, updates `sms.tracker` →
   `mail.notification` status (sent/bounce/exception), then marks the SMS `to_delete`. This
   inbound callback from the external service is invisible to model metadata.

## 4. Business Architecture

- **Capabilities (inferred):** Outbound SMS Sending (transactional + batch via IAP); SMS
  Notification Channel on records; SMS Templates; SMS Composer (single/numbers/mass);
  Delivery Tracking & Failure Handling; Phone Validation & Blacklist/Opt-out; IAP Account
  Registration & Sender-Name management.
- **Value streams (inferred):** Notify-by-SMS (post → `_notify_thread_by_sms` → `sms.sms` →
  IAP → delivery report → notification status); Compose-and-Send; Mass-SMS
  (`_message_sms_schedule_mass` → filter blacklist/dup/optout → queue + cron).
- **Information concepts (auto):** sms.sms, sms.template, sms.tracker, sms.composer,
  mail.notification(type='sms'), iap.account.
- **Organization (auto):** sms defines **no own groups** (facts: `groups: 0`); 1 record rule
  + 13 access rules reuse base groups (`base.group_user` / `base.group_system`).
- **Policies (inferred):** `phone.blacklist` exclusion (default on) → `sms_blacklist`;
  per-batch de-dup → `sms_duplicate`; `_phone_format` validation gate; template `model_id`
  restricted to `is_mail_thread_sms`; IAP auth via `account_token` + `database.uuid` (not
  user-held API keys), unreachable during module install.
- **Metrics (inferred):** `sms.sms.state` distribution; `mail.notification` SMS delivery
  status (drives the `message_has_sms_error` flag); composer valid/invalid recipient counts;
  IAP credit balance.
- **Strategy:** human (none derivable).

## 5. Fit-to-Standard

- **Out-of-box:** send SMS from any record (patched phone field `sms_widget`, composer); SMS
  as a chatter channel alongside email; per-model templates; single/numbers/mass modes with
  validation; delivery state machine + IAP webhook reports; phone sanitization + blacklist +
  duplicate guard; queued cron sending + autovacuum; IAP account registration/verification/
  sender name.
- **Typical fits:** add an SMS notification on a transition via
  `_message_sms_with_template` / `sms.template`; ad-hoc click-to-SMS from a phone field;
  mass SMS over a recordset with blacklist + de-dup; surface SMS failures in Discuss.
- **Common gaps:** a non-Odoo provider needs subclassing `SmsApi`/`SmsApiBase` (default is
  hard-wired to IAP); consent/marketing opt-out beyond raw `phone.blacklist` is delegated to
  SMS Marketing; no throttling/scheduling UI beyond the batch-size parameter; inbound/two-way
  SMS (replies) is not modeled (one-way + status webhook only); IAP credits/country support/
  sender registration depend on external Odoo service state.

## 6. Drive Hints (run-odoo)

```
odoo shell: env['sms.sms'].read_group([], ['id'], ['state'])   # delivery state distribution
odoo shell: p=env['res.partner'].search([('phone','!=',False)], limit=1); \
            p._message_sms('hello from odoo')                   # -> sms.sms + mail.notification(sms)
odoo shell: env['sms.template'].search([], limit=5).mapped(('name','model','body'))
odoo shell: env['iap.account'].get('sms').read(['account_token','sender_name'])
curl jsonrpc /sms/status (auth=public) {message_statuses:[{sms_status,uuids}]}  # simulate IAP report
```

## 7. Open Questions

- Exact IAP wire contract / retry semantics of `/api/sms/3/send` and how partial-batch
  failures map back to per-uuid states (only the result dicts are visible from code).
- Clean single APQC leaf for a cross-cutting comms channel — 9.4 internal communications vs
  12.x external relationships vs derivative 3.5.4.8; none is exact (mirrors `mail`).
- How downstream modules (`mass_mailing_sms`, `marketing_sms`) extend the composer opt-out
  (`_get_optout_record_ids`) and revoked-SMS filtering.
- Live IAP-dependent behavior (credit checks, country support, sender registration) cannot be
  observed without an activated database + credits.

## 8. Provenance

- Facts: `doc/revres/facts/sms.facts.json` (9 models); frontend/integrations:
  `doc/revres/frontend/sms.frontend.json`.
- Tools: `extract_module.py`, `extract_frontend.py`; code-read of `sms_sms.py`,
  `sms_template.py`, `wizard/sms_composer.py`, `models/mail_thread.py`, `tools/sms_api.py`,
  `controllers/main.py`, `sms_tracker.py`, `iap_account.py`; `doc/MESSAGING_SUBSYSTEM.md`.
- Odoo 19.0. Record: `doc/revres/metamodel/sms.metamodel.json` (schema-valid).
