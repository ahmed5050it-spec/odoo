# stock_sms — Delivery Confirmation SMS (Customer SMS on Outgoing Picking Validation)

## 1. Overview
`stock_sms` sends a **"your order has been shipped" SMS** to the customer when an outgoing
delivery order is validated. It layers an SMS branch onto `stock.picking`'s confirmation flow,
adds a per-company template + feature flags, and a one-time confirmation wizard. Manifest: name
**Stock - SMS**, category **Supply Chain/Inventory**, summary "Send text messages when final
stock move", depends `['stock', 'sms']`, LGPL-3, **`auto_install=true`**, `application=false`,
`post_init_hook=_assign_default_sms_template_picking_id`,
`uninstall_hook=_reset_sms_text_confirmation`. 179 Python LOC / 68 XML LOC, 1 own model
(`confirm.stock.sms` wizard) + 3 inherits, **0 routes**, 2 ACL rules + 1 record rule.

## 2. Data model (information concepts)
- **stock.picking** (extended, 4 methods) — the validated delivery order; the SMS trigger.
- **res.company** (extended) — adds `stock_sms_confirmation_template_id` (M2M-domain to
  `sms.template` on `stock.picking`, default `sms_template_data_stock_delivery`) and
  `has_received_warning_stock_sms` (Boolean, the 'warning already seen' flag). The on/off
  switch itself is the **parent stock** pair `stock_text_confirmation` + `stock_confirmation_type`
  (`='sms'`), read via `_get_text_validation('sms')`.
- **res.config.settings** (extended) — re-exposes the template (related) in Inventory Settings.
- **confirm.stock.sms** (`TransientModel`) — the confirmation wizard; `pick_ids -> stock.picking`.

Operated `sms` models: `sms.template` (the message) and `sms.sms` (the outgoing SMS, produced
via `_message_sms_with_template`). Key relation: `res.company -> sms.template`.

## 3. Routes / services
**None** — `stock_sms` exposes no HTTP routes. Its surface is server-side: the
`stock.picking` validation hooks (`_pre_action_done_hook`, `_send_confirmation_email`) and the
`confirm.stock.sms` wizard `ir.actions.act_window`.

## 4. Behavioral notes (code-read — the metadata gap)
- **`_send_confirmation_email` override = the real trigger:** the parent `stock` calls
  `_send_confirmation_email` inside `_action_done` (after `button_validate` →
  `_pre_action_done_hook==True` → `_action_done`), i.e. once a delivery is fully validated. The
  override super()s (keeps email) then, unless `skip_sms`/test, filters to pickings where
  `company._get_text_validation('sms')` **AND** `picking_type_id.code=='outgoing'` **AND**
  `partner_id.phone`, and calls `_message_sms_with_template(template=company.sudo().
  stock_sms_confirmation_template_id, partner_ids=partner_id.ids, put_in_queue=False)` — sent
  **immediately** (synchronously via the sms IAP gateway), not batched. The template is sudo-read.
- **The on/off gate is NOT `stock_move_sms_validation`:** it is `stock_text_confirmation`
  (Boolean) + `stock_confirmation_type` (`='sms'`) on the parent `res.company`;
  `_get_text_validation('sms')` returns `bool(stock_text_confirmation and
  stock_confirmation_type=='sms')`. `post_init` (`_assign_default_sms_template_picking_id`)
  turns it ON + sets the default template for companies lacking one; uninstall resets it OFF.
- **`_pre_action_done_hook` + `_check_warn_sms` + warn wizard:** before the SMS ever fires, the
  override returns `_action_generate_warn_sms_wizard` (the `confirm.stock.sms` modal, carrying
  `pick_ids` + the upstream `button_validate_picking_ids` context) the **first time** a company
  uses delivery SMS (`has_received_warning_stock_sms` still False). Returning an action aborts
  validation and pops the modal.
- **Wizard `send_sms` / `dont_send_sms`:** both set `has_received_warning_stock_sms=True` then
  re-run `button_validate` on `browse(context['button_validate_picking_ids'])`. `send_sms` lets
  validation proceed → SMS sent; `dont_send_sms` also writes `stock_text_confirmation=False`
  (globally disables delivery SMS) → no SMS. The human-confirmation handshake.
- **`sms_template_data_stock_delivery` body:** renders per picking — "`<company>`: We are glad
  to inform you that your order n° `<origin>` has been shipped." (or generic when no origin),
  appending " Your tracking reference is `<carrier_tracking_ref>`." only when that field exists
  (guarded by `hasattr`, since `carrier_tracking_ref` comes from a carrier module).

## 5. Frontend (static)
**None** (metadata gap #3): `present=false`, 0 JS, 0 XML templates, 0 OWL/registry/patches,
no asset bundles. All UI is server-rendered (the wizard form + the inherited settings xpath).

## 6. Integrations
None of its own: `http_call_sites=0`, no SDK, no API keys. The actual SMS delivery + IAP credit
consumption happen in the base `sms` module's IAP layer (`sms.sms.send -> SmsApi ->
https://sms.api.odoo.com`); `stock_sms` only produces the `sms.sms`. The settings view embeds
the sms IAP buy-credits widget.

## 7. Classification
- **value_model: chain** — the trigger is validation of an **outgoing** `stock.picking`
  (`button_validate` → `_action_done` → `_send_confirmation_email`), the shipment step of the
  outbound-logistics value chain. Unlike the cross-cutting base `sms` gateway (support / 9.4),
  this is a delivery-bound shipment notification with no audience/mediation semantics — it rides
  the goods-flow, hence chain not network.
- **activity_class: support** — an ancillary customer-notification step on the delivery; it
  informs the customer but does not itself move or transform goods (the `stock.move` ledger is
  untouched), mirroring `stock_delivery` in this corpus.
- **apqc_category: 4.0 Deliver Physical Products (4.4 Operate outbound transportation / ship)** —
  matches the name and the trigger; classed under Deliver (4.x), not the sms module's 9.4
  internal-communications code, because the message is an integral confirmation event of the shipment.

## 8. Fit-to-Standard
**Standard (out of box):** automatic SMS to the customer on outgoing-delivery validation;
default delivery template (company + order origin + optional carrier tracking ref); per-company
template configurable in Inventory Settings (gated by the stock text-confirmation toggle);
first-use confirmation wizard (Confirm / Disable SMS / Cancel); immediate (non-queued) send via
the sms IAP gateway with the buy-credits widget; stock-manager-scoped template editing
(record rule); post_init auto-enable + clean uninstall reset.
**Typical fits:** "order shipped" SMS to B2C/e-commerce customers on dispatch; adding a tracking
reference when a carrier (`stock_delivery`) is installed; delivery confirmations without writing
automation.
**Common gaps:** fires only on the outgoing picking type and only when `partner_id.phone` is set;
no per-order opt-out (not marketing-opt-out aware); one delivery template per company (no
per-warehouse/carrier choice); synchronous send (`put_in_queue=False`) inside validation; depends
on Odoo IAP credits/country support.
**Drive (run-odoo):**
`env.company.write({'stock_text_confirmation':True,'stock_confirmation_type':'sms'}); env.company._get_text_validation('sms')` ·
`env.ref('stock_sms.sms_template_data_stock_delivery').body` ·
`p=env['stock.picking'].search([('picking_type_id.code','=','outgoing'),('state','=','assigned')],limit=1); p.button_validate()` ·
`env['sms.sms'].search([], order='id desc', limit=5).mapped(('number','state','body'))`.
