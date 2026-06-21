# pos_online_payment_self_order — Architecture Brief

> Module: `pos_online_payment_self_order` · Category: Sales/Point of Sale · Depends: `pos_online_payment`, `pos_self_order` · `auto_install: true`
> Value model: **chain** · Activity class: **primary** · APQC: **3.0 Market and Sell Products and Services**
> Odoo 19.0 · Facts: `doc/revres/facts/pos_online_payment_self_order.facts.json` · Frontend: `doc/revres/frontend/pos_online_payment_self_order.frontend.json` · DEEP record.

## 1. Summary

`pos_online_payment_self_order` is the **double-bridge** that lets a self-order / kiosk customer
**pay their `pos.order` online** and reconciles the confirmed transaction back into the live POS
session. It owns **no model** — **6 `_inherit` extensions** (`ir.http`, `payment.transaction`,
`pos.config`, `pos.order`, `pos.payment.method`, `res.config.settings`), **2 routes** (overrides
of the parent `/pos/pay/<id>` and `/pos/pay/confirmation/<id>`), 1 settings view, **683 py LOC**,
and **4 JS patches**. The flow it stitches: the self-order client opens the public `/pos/pay`
portal (a **scan-to-pay QR** in kiosk, `window.open` in mobile); the parent
`pos_online_payment` portal creates the `payment.transaction` and, on confirmation, settles it
into an online `pos.payment` + `account.payment` and finalises the order; **this module** then
fires a real-time `ONLINE_PAYMENT_STATUS` bus signal (`progress`/`success`/`fail`) so the diner's
SPA confirms and the cashier terminal auto-prints the prep/receipt, and it auto-emails the
customer their receipt. It also **routes which online method** a self-order uses
(`self_order_online_payment_method_id`) and kicks the post-process cron for prompt settlement.
`auto_install=true` — it switches on when both `pos_online_payment` and `pos_self_order` are
present. No acquirer of its own (`uses_api_keys` is inherited from the payment engine).

## 2. Structure (evidence)

- **Models (0 own, 6 inherit):** `pos.config` (+`self_order_online_payment_method_id` →
  `pos.payment.method`); `pos.order` (+`use_self_order_online_payment` Boolean, computed);
  `payment.transaction`, `pos.payment.method`, `res.config.settings`
  (+`pos_self_order_online_payment_method_id` related), `ir.http` (frontend-translation registration).
- **Routes (2):** `PaymentPortalSelfOrder` subclasses `pos_online_payment.PaymentPortal` and
  re-decorates `pos_order_pay` (`/pos/pay/<int:pos_order_id>`, `http`, **public**) and
  `pos_order_pay_confirmation` (`/pos/pay/confirmation/<int:pos_order_id>`, `http`, **public**) with
  bare `@http.route()` — same paths/auth, wrapped for bus feedback.
- **Security:** 0 own ACLs/rules/groups — reuses the parent's `auth='public'` + `access_token`
  gating and `pos_self_order`'s anonymous-to-POS-user impersonation.
- **Views:** 1 inherited (`views/res_config_settings_views.xml`, 36 xml_loc) adding the "Online
  Payment" method selector under the self-order pay-after block (mobile only) + a Payment Methods
  shortcut. No standalone views.

## 3. Frontend (gap #3)

**4 JS files / 1 XML template, no new OWL components or registry services — 4 prototype patches**
(`SelfOrder`, `PaymentPage`, `OrderDisplay`, `PosStore`) across `pos_self_order.assets` (2) and
`point_of_sale._assets_pos` (1) plus test bundles. The request/QR/await-confirmation/auto-print
journey lives entirely in this client code. `integrations_gap7.uses_api_keys=true` is **indirect** —
the acquirer credentials live in `payment`/`payment_<provider>`; this module adds no endpoint or SDK.

## 4. Behavior (beyond metadata)

- **The 2 route overrides + `_send_notification_payment_status` (code-read):** `pos_order_pay` fires
  `'progress'` **before** `super()` so the client shows "payment in progress" the instant the pay page
  opens; `pos_order_pay_confirmation` runs `super()` (the real settlement) then fires `'fail'` if the
  `payment.transaction` is not in `('authorized','done')`. `_send_notification_payment_status` sudo-browses
  the order, calls `_send_notification_online_payment_status(status)` (the bus push) and, on `'success'`,
  `_send_order()` (the kitchen/prep-display hook).
- **`payment.transaction._process_pos_online_payment` / `_process` (code-read):** wraps the parent
  settlement (which `_create_payment`s the `account.payment`, calls `pos_order.add_payment` to write the
  online `pos.payment` linked via `online_account_payment_id`, and finalises a draft order via
  `_process_saved_order`). After `super()`, for confirmed txs it (a) if the order **was** draft, calls
  `_send_self_order_receipt()` to email the customer via the preset mail template, and (b) always fires
  `_send_notification_online_payment_status('success')`. `_process` separately triggers the
  `payment.cron_post_process_payment_tx` cron immediately for confirmed `mobile`/`kiosk` txs
  (`_is_self_order_payment_confirmed`) — prompt settlement instead of waiting for the scheduler.
- **`pos.order` online-method routing (code-read):** `use_self_order_online_payment` (= `bool(config.
  self_order_online_payment_method_id)`) is system-managed — `write()` honours it only on draft orders
  whose config still has a self-order method, else silently strips it (never raises).
  `_compute_online_payment_method_id` is overridden so that when the flag is set the order's
  `online_payment_method_id` resolves to the **self-order** method (not the cashier method from
  `super()`), which is what makes the portal's `_get_allowed_providers_sudo` offer the right providers.
  `get_and_set_online_payments_data(0)` flips the flag back on (fall back to self-order pay) when a
  cashier online tender is cancelled.
- **Bus + concurrency (code-read):** `_send_notification_online_payment_status` calls
  `config._notify('ONLINE_PAYMENT_STATUS', {status, data})` where `data` carries the order + its
  `pos.payment` lines read with the extended `_load_pos_self_data_fields` (adds
  `online_payment_method_id` + `next_online_payment_amount`) so the client reconciles without a full
  reload. `get_order_to_print` takes `SELECT ... FOR UPDATE NOWAIT` and refuses to print twice
  (`nb_print>0` guard) — the receipt prints exactly once across concurrent bus listeners.
  `pos.payment.method._load_pos_self_data_domain` gates which online methods reach the client (kiosk:
  all `is_online_payment` on the config; mobile: exactly `self_order_online_payment_method_id`).
  *(Note: the module's `_get_self_ordering_data` / `_get_self_ordering_payment_methods_data` overrides
  call `super()` but have no parent of those names in the current `pos_self_order` tree — the live
  exposure runs through the `_load_pos_self_data_*` family.)*
- **Frontend (static, gap #3):** `SelfOrder.setup` opens an `ONLINE_PAYMENT_STATUS` listener (merges
  pushed data via `models.connectNewData`, routes to confirmation on `success`); `PaymentPage.startPayment`,
  for an online method, `sendDraftOrderToServer()` then shows a kiosk QR (`generateQRCodeDataUrl`) or
  `window.open`s the `/pos/pay` URL; `OrderDisplay.buttonToShow` relabels Order/Pay/Pay-at-cashier;
  `PosStore.setup` (cashier, mobile) listens to the **same** channel and on `success` prints the
  prep+receipt once, queuing while the tab is hidden.

## 5. IT architecture

- **Application:** auto-install double-bridge — self-order/kiosk customer pays their `pos.order` online;
  confirmed transaction reconciled into the live session with bus feedback + auto-receipt.
- **Data objects:** `pos.config` (+self-order online method), `pos.order` (+routing/bus/receipt),
  `pos.payment.method`, `payment.transaction`, `res.config.settings`, `ir.http`.
- **Key relations:** `pos.config → pos.payment.method` (`self_order_online_payment_method_id`,
  domain `is_online_payment=True`); `pos.order → pos.payment.method` (`online_payment_method_id`,
  re-pointed to the self-order method); `payment.transaction → pos.order` (`pos_order_id`);
  `pos.payment → account.payment` (`online_account_payment_id`, written on settlement).
- **Flows:** inbound `startPayment → sendDraftOrderToServer → /pos/pay (QR/window.open) → parent
  jsonrpc /pos/pay/transaction → payment.transaction`; settlement `tx authorized|done →
  _process_pos_online_payment (super: account.payment + online pos.payment + finalise) +
  _send_self_order_receipt + status 'success'`; bus `config._notify('ONLINE_PAYMENT_STATUS') → SPA
  confirms + cashier auto-prints once`; cron `_process → trigger cron_post_process_payment_tx` for
  mobile/kiosk.

## 6. Business architecture

- **Capabilities (inferred):** pay a self-order/kiosk order online; configure a self-order online
  method per till (mobile) and expose online methods to kiosks; settle the confirmed transaction into
  the live session; real-time progress/success/fail feedback; auto-email + once-only auto-print receipt.
- **Value streams (inferred):** *Self-Order-Pay-Online* — build cart in the SPA → choose online method
  → `sendDraftOrderToServer` → open `/pos/pay` (QR/window.open) → confirm transaction → settle
  `account.payment` + `pos.payment` + finalise → bus `success` → SPA confirms, cashier prints, customer
  emailed.
- **Information concepts (auto):** `pos.order` (source mobile/kiosk), `pos.config`, `pos.payment.method`,
  `payment.transaction`, `pos.payment`/`account.payment`.
- **Organization (auto):** none (reuses POS groups + public/portal access of the pay routes and
  `self_ordering_default_user_id`).
- **Products (auto):** none.
- **Policies (inferred):** `auto_install=true`; `use_self_order_online_payment` system-managed (draft +
  configured only, silent strip); mobile+pay-each self-order method must support the config currency;
  mode-gated method exposure (kiosk all / mobile one); receipt prints exactly once
  (`FOR UPDATE NOWAIT` + `nb_print` guard); inherited settlement invariants (online `pos.payment` 1:1
  with `account.payment`; online lines never trusted from a draft client).
- **Metrics (inferred):** share of self-order/kiosk orders paid online vs at cashier; progress→success
  vs fail per config; `payment.transaction` state distribution for self-order-linked txs.
- **Strategy:** `null` (human).

## 7. Classification

- **Value model: chain — primary activity.** The mission is the **settlement of a retail self-order**:
  let the diner pay the order they just built on their phone/kiosk, then drive that confirmed
  transaction back into the live POS session as a real `pos.payment` + `account.payment` and finalise
  the order — the Market-and-Sell "tender and complete the sale" step (3.5 manage-sales-orders) on the
  customer's own device, then fire the kitchen hook (`_send_order`) and receipt. It inherits the
  `chain`/`primary` class of both parents (`pos_online_payment` is chain/primary; `pos_self_order`,
  itself network-flavoured, is classed primary/3.0 as a customer order-capture channel).
- **APQC: 3.0 Market and Sell Products and Services.** It carries clear **network** overtones — it
  brokers buyer + acquirer through public mediation routes (`/pos/pay`) and a real-time bus — but, as
  the `pos_online_payment` record argues, the value it actually completes is the chain sell, with the
  buyer/acquirer brokering being the mechanism. **9.0 (finance) was rejected:** the confirmed tx does
  feed an `account.payment` (a 9.x collect-cash effect), but that accounting settlement is a triggered
  downstream consequence of finishing the POS sale; the module exists to complete the self-order
  checkout, so its home is 3.0, mirroring its payment-side parent rather than the `account_payment` engine.

## 8. Fit-to-Standard

- **Standard:** online payment of a self-order/kiosk order via the public `/pos/pay` portal (phone
  `window.open` or kiosk scan-to-pay QR); one configurable self-order online method per mobile till,
  all online methods in kiosk; automatic settlement into online `pos.payment` + `account.payment` +
  order finalise (reused from `pos_online_payment`); real-time progress/success/fail feedback to client
  and cashier; auto-emailed receipt + once-only cashier prep/receipt auto-print; immediate cron
  post-processing.
- **Typical fits:** restaurant mobile QR table-ordering with online pay; fast-food kiosk scan-to-pay;
  pay-each self-order that must settle and notify the kitchen on payment; any provider already supported
  by an installed `payment_<provider>` module.
- **Common gaps:** **ships no acquirer** (a `payment_<provider>` must be installed and published, sharing
  the config currency); kiosk **in-person card-reader** payment is `pos_self_order`'s
  `_payment_request_from_kiosk` path, not this online portal; the self-order online method is **single**
  per mobile config; QR/redirect UX is standard (bespoke presentation is OWL dev); no per-provider
  fee/reconciliation beyond `account_payment`.
- **Drive:**
  `env['pos.config'].search([('self_order_online_payment_method_id','!=',False)]).mapped(lambda c:(c.name, c.self_ordering_mode, c.self_order_online_payment_method_id.name))`;
  `env['pos.order'].search([('source','in',('mobile','kiosk')),('use_self_order_online_payment','=',True)], limit=5).mapped(('name','state','online_payment_method_id.name'))`;
  `curl GET /pos/pay/<pos_order_id>?access_token=...&exit_route=...` (auth=public) renders the form and
  triggers the `'progress'` bus push; browse `/pos-self/<config_id>` (mobile), build an order, choose the
  online method → the client opens `/pos/pay` and awaits `ONLINE_PAYMENT_STATUS`.

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`addons/pos_online_payment_self_order` (controllers + 6 models + `static/src/**` + the settings view),
plus the parents `addons/pos_online_payment` (portal + transaction settlement) and
`addons/pos_self_order` (`pos_order`/`pos_config`). Odoo 19.0.*
