# snailmail — Architecture Brief

> Module: `snailmail` · Category: Hidden/Tools · Depends: `iap_mail`, `mail` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **9.4 Manage internal communications**
> Odoo 19.0 · Facts: `doc/revres/facts/snailmail.facts.json` · Frontend: `doc/revres/frontend/snailmail.frontend.json`

## 1. Summary

`snailmail` is a **physical-mail egress channel** — the postal sibling of `mail` and
`sms`. It lets any printable Odoo document (canonically an invoice or payment
follow-up) be **printed and posted** through Odoo's IAP Snail Mail service. The unit
of work is a `snailmail.letter`: a queued record holding the recipient address, the
rendered PDF, and a delivery state machine. Sending POSTs the PDF to
`https://iap-snailmail.odoo.com/iap/snailmail/1/print` via the IAP broker; postage is a
metered IAP credit ("Stamps"). It owns **1 model + 7 inherits**, **0 routes**, ~1166
py LOC, and is `auto_install: true` with `mail`, so it plugs into the chatter of every
`mail.thread` model with no schema change.

## 2. Structure (evidence)

- **Models (1 own + 7 inherit):** `snailmail.letter` (24 fields, 20 methods — the
  queued letter); inherits on `ir.actions.report` (force postal re-render), `mail.message`
  (`snailmail_error` flag + `'snailmail'` message_type), `mail.notification` (`'snail'`
  notification_type + 6 `sn_*` failure_types), `mail.thread` (`notify_cancel_by_type`),
  `res.company` / `res.config.settings` (color/cover/duplex print defaults), `res.partner`
  (address propagation + postal formatting).
- **Routes:** **0** — no web surface of its own; the only HTTP is *outbound* through `iap`.
- **Security:** 2 access rules (`base.group_user` r/w/c no-unlink; `base.group_system`
  full), 0 record rules, 0 groups. Attachment confidentiality is enforced in Python via
  `attachment_id.check_access('read')` in `create`/`write`.
- **Views:** 1 list + 1 form on `snailmail.letter` under `base.menu_email`. The real UX
  is the chatter message + `SnailmailNotificationPopover`, not a dedicated app.

## 3. Frontend (gap #3) & Integrations (gap #7)

**5 JS / 1 XML**, 1 OWL component (`SnailmailNotificationPopover`), 0 registry adds, 3
patches (`Failure.prototype`, `MessagingMenu.prototype`, `Notification.prototype`);
bundles `web.assets_backend`=1, `snailmail.report_assets_snailmail`=5,
`web.assets_unit_tests`=1. The JS **decorates the existing Discuss/notification UI**
(red failure badge, Send/Cancel actions, address popover) — it adds no new screen.
Integrations (gap #7): **0 raw http call sites, 0 SDK imports**; the only egress is the
print call brokered by `iap_tools.iap_jsonrpc` to `https://iap-snailmail.odoo.com`
(overridable via `ir.config_parameter 'snailmail.endpoint'`). `uses_api_keys: false` —
auth is the per-account `iap.account('snailmail').account_token` + `database.uuid`.
`reportlab` is a local PDF dependency, not a network SDK.

## 4. Behavior (beyond metadata)

- **Egress (code-read):** `_snailmail_print` partitions letters by `_is_valid_address`
  (needs street/city/zip/country); valid ones go to `_snailmail_print_valid_address`,
  which `iap_jsonrpc`-POSTs `_snailmail_create('print')` to `/iap/snailmail/1/print` and
  **commits after each letter** so a rollback never re-sends. `sent==True` +
  `request_code==200` → `state='sent'` + tracking id; else the per-doc error maps to
  `state='error'`.
- **Create side-effects (code-read):** `create` (`@api.model_create_multi`)
  `message_post`s a `'snailmail'` message on the **source record**, snapshots the
  partner address onto the letter (frozen), and bulk-creates a `mail.notification`
  (`type='snail'`, `is_read=True`) — the row the delivery icon reads. So creating a
  letter mutates an unrelated document's chatter.
- **Credit gate (code-read):** no local ledger. `CREDIT_ERROR` →
  `iap.account._send_no_credit_notification` + `get_credits_url`. `_get_failure_type`
  maps wire codes to `mail.notification.failure_type` (`sn_credit`/`sn_trial`/`sn_price`/
  `sn_fields`/`sn_format`/`sn_error`), driving `mail.message.snailmail_error`.
- **Queue/retry (code-read):** `ir.cron snailmail_print` (24h) → `_snailmail_cron`
  re-sends `pending` + *recoverable*-error letters and **breaks on the first
  `CREDIT_ERROR`** ("avoid spam"); terminal errors (FORMAT/NO_PRICE) are not retried.
- **Postal PDF (code-read):** `_fetch_attachment` renders the report under
  `snailmail_layout`, enforces A4 (`UserError` otherwise), swaps unsupported layouts to
  standard, then `_overwrite_margins` (white-masks the 5mm postal margins + franking
  square) and `_append_cover_page` (window-envelope address frame, blank page if duplex).
- **Address (code-read):** `res.partner.write` propagates address edits to in-flight
  letters; `_get_country_name` returns English names (carrier requirement) and
  `_get_address_format` has a DE/Pingen single-line branch.

## 5. IT architecture

- **Application:** physical-letter egress channel layered on `mail`'s notification
  pipeline, posting via Odoo IAP.
- **Data objects:** `snailmail.letter` + inherits on report/message/notification/thread/
  company/settings/partner.
- **Key relations:** letter → `mail.message` (status), `mail.notification` (`snail`),
  `ir.attachment` (PDF), `res.partner` (recipient, frozen address), `(model,res_id)`
  generic source ref, `iap.account('snailmail')` (remote postage).
- **Flows:** create → `message_post` + notification + address snapshot; `_snailmail_print`
  → `iap_jsonrpc` → print service; cron retry; CREDIT_ERROR → no-credit notification.

## 6. Business architecture

- **Capabilities (inferred):** send a document by post; postal-PDF prep; delivery
  tracking & failure handling; address validation/freezing; IAP credit gate; per-company
  print defaults.
- **Value streams (inferred):** Send-by-Post (letter → render → IAP print → sent/error);
  Queued-Retry (cron); Address-Correction (edit partner → propagate to in-flight letters).
- **Information concepts (auto):** `snailmail.letter`, `mail.message` (`snailmail`),
  `mail.notification` (`snail`), `ir.attachment` (PDF), `iap.service 'snailmail'`.
- **Organization (auto):** `base.group_user` / `base.group_system` (no own groups).
- **Policies (inferred):** address-completeness gate; attachment ACL; credit-spam guard +
  per-letter commit; A4 paper compliance; recoverable-vs-terminal error retry.
- **Metrics (inferred):** letter state distribution; `sn_*` failure counts;
  `snailmail_error` badge; IAP "Stamps" balance.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** A cross-cutting physical-mail **channel**, not part of any
  single primary value chain (Stabell & Fjeldstad "support"). It plugs into
  `mail.thread`'s notification pipeline and reuses `mail.message`/`mail.notification`, so
  any document can be posted with no schema change; `auto_install=true` with `mail`
  confirms shared communication infrastructure. Hence not chain/shop/network.
- **APQC: 9.4 Manage internal communications.** The firm-wide communication-channel
  category that also houses `mail`/`sms`. Chosen over an **8.x IT** code (the substance is
  a *delivery channel*, not IT plumbing) and over a **9.x finance** code (it merely carries
  finance documents; it owns no ledger). Numbering 9.4 = "Manage internal communications"
  matches the name.

## 8. Fit-to-Standard

- **Standard:** mail any Odoo document by post; postal-PDF prep (A4/euro, margin mask,
  window-envelope cover, duplex blank); address validation + freezing; English
  country-name + DE/Pingen formatting; delivery state machine + tracking id; 24h retry
  cron with credit-spam guard; IAP "Stamps" credit + buy-more redirect; per-company
  color/cover/duplex defaults.
- **Typical fits:** posting invoices & follow-ups physically; sending a record's report by
  post from the chatter; centralising print defaults; surfacing postal failures in Discuss.
- **Common gaps:** hard-wired to the Odoo IAP endpoint (no other carrier); only A4/euro
  (+ DIN5008) paperformats; one-way delivery (no inbound/return mail); postage pricing,
  coverage and the 8-page limit are remote; no mass UI beyond the cron.
- **Drive:** `env['snailmail.letter'].read_group([], ['id'], ['state'])`;
  `env['iap.account'].get_credits('snailmail')`;
  `env['ir.config_parameter'].sudo().get_param('snailmail.endpoint','https://iap-snailmail.odoo.com')`.

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/snailmail_letter.py`, `models/mail_message.py`, `models/mail_notification.py`,
`models/mail_thread.py`, `models/res_partner.py`, `models/res_company.py`,
`models/res_config_settings.py`, `models/ir_actions_report.py`, `data/snailmail_data.xml`,
`data/iap_service_data.xml`. Odoo 19.0.*
