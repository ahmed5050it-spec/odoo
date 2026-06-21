# payment_paypal — Architecture Brief

> Payment Provider: PayPal — an acquirer adapter that links an Odoo merchant to
> PayPal, the worldwide PSP. `_inherit`-only over the `payment` engine: no own
> models, no own ACL, 6 added provider fields + one debug transaction field.
> Odoo 19.0, `version 2.0`, LGPL-3.

## 1. Overview
payment_paypal is a concrete realization of the generic `payment` engine for
PayPal. It adds the `paypal` provider code plus six credential fields (business
email, client id, client secret, cached OAuth access token + expiry, webhook id),
and overrides the transaction/controller hooks to drive a **direct/inline flow**:
a server-side **Orders v2** create (`intent=CAPTURE`) hands an `order_id` to the
client-side **PayPal JS SDK Buttons**, and on buyer approval the
`/payment/paypal/complete_order` jsonrpc route makes the server-side **capture**.
It is a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. IT Architecture
- **Application:** PayPal acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (one debug field `paypal_type`).
- **Services (routes):** `/payment/paypal/complete_order` (jsonrpc, captures then
  `_process`), `/payment/paypal/webhook/` (http POST, csrf=False, origin verified
  by re-POST to PayPal). **No redirect/return route** — PayPal is direct, not
  hosted-redirect.
- **Data objects:** `payment.provider` (+paypal_email_account/client_id/
  client_secret/access_token/access_token_expiry/webhook_id),
  `payment.transaction` (+paypal_type; 5 override methods).
- **Key relations:** tx → provider (`provider_code=='paypal'` gates every
  override); external keys `reference_id==reference`, `provider_reference==
  order/capture id`, `paypal_webhook_id==registered PayPal webhook`.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Create + SDK approval:** `_get_specific_processing_values` →
  `_paypal_prepare_order_payload` → POST `/v2/checkout/orders` (`intent=CAPTURE`,
  idempotency key) → returns `{order_id}`; the `PaymentForm` patch hands it to
  `paypal.Buttons` (createOrder), which renders the button and runs the buyer
  approval popup client-side.
- **Capture:** `onApprove` → jsonrpc `/payment/paypal/complete_order` →
  `_search_by_reference` → server POST `/v2/checkout/orders/{id}/capture` →
  `_normalize_paypal_data` → `_process`. The authoritative settlement is this
  SDK-triggered server capture, **not** a hosted-redirect return.
- **Outbound auth / endpoints:** `_build_request_url` →
  `https://api-m.paypal.com` (live) / `…sandbox.paypal.com`; `_build_request_auth`
  → `(paypal_client_id, paypal_client_secret)` for the token request (HTTP Basic),
  else `Authorization: Bearer <token>`. `_paypal_fetch_access_token` POSTs
  `grant_type=client_credentials` to `/v1/oauth2/token` and **caches** the token
  (`paypal_access_token`/`…_expiry`, 5-min skew). HTTP delegated to
  `payment.provider._send_api_request`.
- **Webhook verification:** `_verify_notification_origin` **re-POSTs back to
  PayPal** `/v1/notifications/verify-webhook-signature` with the
  `PAYPAL-TRANSMISSION-*` headers + `paypal_webhook_id` + raw event; HTTP 403
  Forbidden unless `verification_status == 'SUCCESS'`. **Not** a local HMAC. Only
  `const.HANDLED_WEBHOOK_EVENTS` are acted upon.
- **Status mapping (`_apply_updates`):** empty data → canceled ("customer left");
  missing id/txn_type → error; then PENDING/CREATED/APPROVED→pending;
  COMPLETED/CAPTURED→done; DECLINED/DENIED/VOIDED→canceled; FAILED/unknown→error.
- **Webhook registration:** `action_paypal_create_webhook` POSTs to
  `/v1/notifications/webhooks` and stores `paypal_webhook_id` (refuses on
  localhost).

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **Outbound** server-
to-server REST to `api-m[.sandbox].paypal.com` — `/v1/oauth2/token` (OAuth
client-credentials, HTTP Basic), `/v2/checkout/orders` + `…/{id}/capture`,
`/v1/notifications/webhooks` (register), `/v1/notifications/verify-webhook-signature`
(verify). **Client-side** the PayPal JS SDK (`www.paypal.com/sdk/js?…components=
buttons…intent=capture`) renders the Buttons and runs the approval popup, then
calls back into the `complete_order` jsonrpc route. **Inbound** settlement via a
webhook whose origin is verified by re-POSTing to PayPal. `uses_api_keys=true`; no
python SDK (HTTP via the parent engine).

## 5. Frontend (gap #3)
2 JS files, 0 OWL components. Patches **PaymentForm.prototype** (sets the `direct`
flow, lazily loads the PayPal JS SDK, renders `paypal.Buttons`; `onApprove` →
`/payment/paypal/complete_order` → `/payment/status`) and **PaymentButton.prototype**
(swaps disabled vs enabled Buttons, since the SDK has no post-render disable). Two
inline-form QWeb templates feed it (`payment.method_form`
`data-paypal-inline-form-values` + `payment.submit_button`
`o_paypal_button_container`). Assets load into `web.assets_frontend`
(glob `payment_paypal/static/src/**/*`). The SDK and these interactions are not
reachable from Python metadata.

## 6. Business Architecture
- **Capabilities (inferred):** accept PayPal-wallet payments worldwide via the JS
  SDK Buttons (Orders v2 CAPTURE); server create + client approval + server
  capture; self-service webhook registration + re-POST origin verification;
  multi-currency (24 ISO codes, CNY excluded).
- **Value streams (inferred):** Collect-Payment (create → SDK approval →
  capture), Register-Webhook, Settle (COMPLETED → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; `paypal_client_secret`/`access_token`/
  `access_token_expiry` gated by `base.group_system`.
- **Policies (inferred):** webhook origin via re-POST verify-webhook-signature
  (403 on failure); only handled events acted on; empty data → cancel;
  OAuth-cached bearer + idempotency keys; `intent=CAPTURE` → immediate capture.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to PayPal's worldwide
  network (network promotion/contract mgmt = email + client id/secret + webhook
  id + OAuth lifecycle; service provisioning = create order, render Buttons,
  capture on approval; infrastructure operation = api-m.paypal.com + PayPal JS SDK
  + verify-webhook loop). Inherits the parent `payment` engine's model exactly.
  Mirrors sibling payment_stripe / payment_xendit (network/support).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** direct/inline PayPal Buttons backed by Orders v2 (create +
  approval + immediate capture); webhook origin verified by re-POST to PayPal;
  self-service webhook registration; multi-currency (24 currencies).
- **Common gaps:** no tokenization/saved accounts; no separate authorize/capture,
  no void (`intent=CAPTURE`); no in-module refund (despite PayPal's refund API);
  webhook verification needs a registered `paypal_webhook_id` + public HTTPS URL;
  currency support bounded (CNY excluded).
- **Open questions:** full Orders v2 / webhook payloads; runtime state/currency
  mix; how refunds/chargebacks are handled operationally; whether instances
  register the webhook vs lean on the synchronous `complete_order` capture path.
