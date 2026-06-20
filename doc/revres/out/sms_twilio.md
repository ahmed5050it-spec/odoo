# sms_twilio (Twilio SMS) — Architecture Brief

> Module `sms_twilio`, display name **"Twilio SMS"** (`odoo/addons/sms_twilio/`).
> An alternate SMS *gateway driver*: it swaps the `sms` module's Odoo-IAP delivery
> backend for the customer's own **Twilio** REST account, selected **per company**
> (`res.company.sms_provider = iap|twilio`). `depends = [sms]`, `auto_install = False`.
> Only 2 own models (`sms.twilio.number`, `sms.twilio.account.manage`); everything else
> is an `_inherit` extension. 1 route (`/sms_twilio/status/<uuid>`), ~1.3k Python LOC.
> No business object of its own — it is the Twilio sibling of the IAP-based `sms`.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). Messaging infrastructure — a
  delivery-backend swap with no primary value chain of its own. It plugs transparently into
  the `mail.thread` notification pipeline that `sms` already established.
- **activity_class: support.**
- **apqc_category:** best fit **9.4 Manage internal communications** (the firm-wide
  communication-infrastructure category that houses `mail`/`sms`). As a gateway swap it
  inherits its parent's APQC anchor; the concrete map anchor is **3.5.4.8 Handle sales order
  inquiries (post-order)** in `apqc_odoo_map.tsv`, applying only derivatively when an SMS
  notifies on a `sale.order`.
- **Why 9.4 (and not a 3.x selling code):** `sms_twilio` is *channel transport*, not a
  selling act. It owns only technical config models and redirects the wire; a 3.x
  Market-and-Sell leaf applies only when the SMS happens to notify on a sales record.
- **External integration (gap #7):** direct `requests`-based HTTPS to **api.twilio.com**
  with HTTP **Basic auth** (account SID + auth token), replacing IAP's
  `https://sms.api.odoo.com` (`account_token` + `database.uuid`).

## 2. IT Architecture

- **Application:** an alternate SMS gateway driver layered on `sms`, chosen per
  `res.company`.
- **Software services (routes):** `/sms_twilio/status/<string:uuid>` (public `http`,
  `csrf=False`) — Twilio's signed **StatusCallback** webhook. The only HTTP surface; sending
  is outbound to Twilio.
- **Own data objects:** `sms.twilio.number` (sender number per company/country),
  `sms.twilio.account.manage` (transient config wizard). **Extensions:** `res.company`
  (provider + credentials + numbers), `sms.sms` (sid, record_company_id, +failure_type),
  `sms.tracker` (sid), `mail.notification` (+failure_type), `sms.composer`,
  `res.config.settings`.
- **Key ERM:** `res.company → sms.twilio.number (One2many)`, `sms.twilio.number →
  res.country (per-country From)`, `sms.sms → res.company (record_company_id ⇒ provider)`,
  `sms.sms.sms_twilio_sid → sms.tracker.sms_twilio_sid (related; SID survives the sms GC)`.
- **Information flows:** `_split_by_api` routes per-company Twilio SMS to `SmsApiTwilio` and
  IAP SMS to `super()`; outbound POST to Twilio `Messages.json`; inbound `/sms_twilio/status`
  webhook → tracker → notification → `to_delete`.

## 3. Behavioral Notes (code-read, the metadata gap)

- **`SmsApiTwilio._send_sms_batch` (tools/sms_api.py):** subclasses `SmsApiBase`; opens a
  `requests.Session` and loops **per message, per number**, POSTing to
  `https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json` with
  `{From, To, Body, StatusCallback}`, **Basic auth** `(account_sid, auth_token)`, 5s timeout.
  Success returns `{state:'sent', sms_twilio_sid: <sid>}`.
- **Error mapping (`_twilio_error_code_to_odoo_state` + `PROVIDER_TO_SMS_FAILURE_TYPE`):**
  Twilio codes → Odoo states (21211/21614/21265→wrong_number_format, 21604→sms_number_missing,
  21266→twilio_from_to, 21603→twilio_from_missing, 21608→twilio_acc_unverified,
  21609→twilio_callback, else `unknown`). Network/timeout → `server_error`. New failure types
  added via `selection_add` on `sms.sms` **and** `mail.notification`.
- **Per-company routing (`sms_sms.py`):** `_split_by_api` groups by `_get_sms_company()`;
  Twilio companies get `SmsApiTwilio`, rest fall to IAP. Batch size drops to
  `sms_twilio.session.batch.size` (default 10, sequential). Since the `sms.sms` row is GC'd
  post-send, `_handle_call_result_hook` persists the Twilio SID onto `sms.tracker`.
- **StatusCallback webhook (controllers/controllers.py):** validates 32-hex uuid, maps
  `SmsStatus` (delivered→sent, failed/undelivered→error, …), and **verifies HMAC-SHA1**
  (`generate_twilio_sms_callback_signature` keyed by `auth_token`) against the
  `X-Twilio-Signature` header via `hmac.compare_digest` before updating tracker/notification.
- **Credential storage (res_company.py + wizard):** `sms_twilio_account_sid` /
  `sms_twilio_auth_token` on `res.company`, both `groups='base.group_system'`;
  `_assert_twilio_sid` validates SID format. The wizard's `action_reload_numbers` GETs
  `IncomingPhoneNumbers.json`; `action_send_test` sends a real test SMS.

## 4. Business Architecture

- **Capabilities (inferred):** Twilio SMS gateway; per-company provider selection; sender-
  number management with per-country From selection; Twilio delivery tracking; error/failure
  mapping; credential config + connection test.
- **Value streams (inferred):** *Configure-Twilio* (set provider/SID → reload numbers → test
  → save); *Send-via-Twilio* (`_split_by_api` → `_send_sms_batch` → Messages.json → SID back);
  *Delivery-Report* (StatusCallback → signed webhook → tracker/notification → GC).
- **Information concepts (auto):** `sms.twilio.number`, `sms.twilio.account.manage`,
  `res.company.sms_provider`, `sms.sms.sms_twilio_sid`, `sms.tracker.sms_twilio_sid`,
  `mail.notification`.
- **Organization (auto):** `base.group_system` (admin configures credentials/numbers/provider;
  SID/token field-gated). No own groups; 2 access rules.
- **Policies (inferred):** per-company provider routing; SID-format validation;
  callback-signature authenticity (HMAC); sequential batch sizing; credential confidentiality.
- **Frontend:** none — `present:false` (0 JS/OWL). The UI is data-file views only (settings,
  sms list sid column, wizard form). **Strategy: null (human).**

## 5. Fit-to-Standard

- **Standard out-of-box:** drop-in alternate provider via `sms_provider='twilio'`; config
  wizard with SID validation + live test; auto sender-number import; per-message REST send
  returning the SID; signed StatusCallback into the existing delivery state machine; Twilio
  error → Odoo failure-type mapping surfaced through `message_has_sms_error`.
- **Typical fits:** customer with an existing Twilio account / regulated numbers wanting Odoo
  SMS without IAP credits; multi-company with a different backend per company; all existing
  SMS flows (chatter, templates, mass) keep working — only the transport swaps.
- **Common gaps:** StatusCallback needs a public base URL (ngrok for local); sending is
  sequential (per-recipient HTTP, 5s timeout) — slower than IAP batching at volume; grouping is
  by company only (code TODO); no inbound/two-way SMS; needs `requests` + egress to
  api.twilio.com; credentials are company-stored secrets.

## 6. Drive Hints (run-odoo)

- `env.company.write({'sms_provider':'twilio','sms_twilio_account_sid':'AC...','sms_twilio_auth_token':'...'}); env.company._assert_twilio_sid()`
- `list(env['sms.sms']._fields['failure_type'].selection)` — see `twilio_*` failure types.
- `from odoo.addons.sms_twilio.tools.sms_twilio import get_twilio_from_number; get_twilio_from_number(env.company, '+15551234567')` — per-country From pick.
- `env['sms.twilio.account.manage'].create({}).action_reload_numbers()` — import sender numbers.
- `curl -X POST '<base_url>/sms_twilio/status/<32-hex-uuid>' -d 'SmsStatus=delivered' -H 'X-Twilio-Signature: <hmac>'` — simulate a StatusCallback (signature must validate).

## 7. Open Questions

- Full Twilio Messages API contract beyond the fields used and full error-code coverage
  (unmapped codes fall to `unknown`).
- Same APQC ambiguity as parent `sms`: no single clean PCF leaf for a cross-cutting comms
  gateway (9.4 vs 12.x vs derivative 3.5.4.8).
- Live Twilio behavior (real delivery, number provisioning, signature round-trip) needs a
  configured account + public callback URL.
- Stated TODO/RIGR refactors (move `record_company_id` onto `SmsSms`; group by
  provider/account not company) not yet implemented in this stable version.

## 8. Provenance

- **explorer_facts:** `doc/revres/facts/sms_twilio.facts.json`;
  **frontend:** `doc/revres/frontend/sms_twilio.frontend.json`;
  **parent shape:** `doc/revres/metamodel/sms.metamodel.json`.
- **tools:** code-read (`tools/sms_api.py`, `tools/sms_twilio.py`, `models/sms_sms.py`,
  `models/res_company.py`, `models/sms_tracker.py`, `models/mail_notification.py`,
  `models/sms_composer.py`, `controllers/controllers.py`,
  `wizard/sms_twilio_account_manage.py`, `__manifest__.py`); `apqc_odoo_map.tsv`.
- **odoo_version:** 19.0.
