# payment_xendit — Architecture Brief

> Payment Provider: Xendit — an acquirer adapter that links an Odoo merchant to
> Xendit, the Southeast-Asian PSP (Indonesia, Philippines + wider SEA: card,
> e-wallet, bank, QR). `_inherit`-only over the `payment` engine: no own models,
> no own ACL, 4 added provider fields. Odoo 19.0, `version 1.0`, LGPL-3.

## 1. Overview
payment_xendit is a concrete realization of the generic `payment` engine for the
Xendit PSP. It adds the `xendit` provider code plus three credential fields
(public key, secret key, webhook token), and overrides the transaction/controller
hooks to drive two flows: a **direct Card flow** (client-side Xendit.js
tokenization → server `credit_card_charges`) and a **hosted-redirect Invoice
flow** (`v2/invoices` → Xendit-hosted checkout) for every other method. It is a
finance/infrastructure support component, not an end-user app (`application=false`).

## 2. IT Architecture
- **Application:** Xendit acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (+ `payment.token` vaulting via the engine).
- **Services (routes):** `/payment/xendit/payment` (jsonrpc, tokenized Card
  charge), `/payment/xendit/webhook` (http POST, csrf=False, x-callback-token
  verified), `/payment/xendit/return` (http GET, draft→pending).
- **Data objects:** `payment.provider` (+xendit_public_key/secret_key/webhook_token),
  `payment.transaction` (no new fields; 10 override methods).
- **Key relations:** tx → provider (`provider_code=='xendit'` gates every
  override); tx → token (`token.provider_ref == Xendit credit_card_token_id`);
  external keys `external_id==reference`, `provider_reference==data['id']`.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Redirect/invoice flow:** `_get_specific_rendering_values` (non-card) →
  `_xendit_prepare_invoice_request_payload` → POST `v2/invoices` (Basic
  secret-key auth) → hands the hosted `invoice_url` to the QWeb redirect form.
  FPX selections expand to the full `const.FPX_METHODS` bank list.
- **Direct Card flow:** browser tokenizes via Xendit.js → jsonrpc
  `/payment/xendit/payment` → `_xendit_create_charge` POST `credit_card_charges`
  with `is_recurring=True` for tokenized/recurring (skips 3DS on later charges).
- **Outbound auth:** `_build_request_url` → `https://api.xendit.co/{endpoint}`;
  `_build_request_auth` → `(xendit_secret_key, '')` (HTTP Basic, secret as
  username); HTTP delegated to `payment.provider._send_api_request`.
- **Inbound webhook:** `_search_by_reference('xendit', data)` (via
  `_extract_reference` → `external_id`) → `_verify_notification_token`
  (constant-time `consteq` of `x-callback-token` vs `xendit_webhook_token`,
  else HTTP 403 Forbidden) → `_process`. The return route only flips draft→
  pending after `check_access_token`; the webhook is authoritative for the
  final state.
- **Status mapping (`_apply_updates`):** PENDING→pending; SUCCEEDED/PAID/CAPTURED
  →done; CANCELLED/EXPIRED→canceled; FAILED→error.
- **Tokenization:** `_extract_token_values` vaults `credit_card_token_id` + last4.

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **Outbound** server-
to-server REST to `api.xendit.co` — `v2/invoices` (Invoices API v2) and
`credit_card_charges` (Credit Charge API v1) — authenticated by HTTP Basic with
the secret key. **Client-side** the Xendit.js tokenization SDK (loaded lazily on
form submit) tokenizes card details in the browser (SAQ A-EP). **Inbound**
settlement via an `x-callback-token`-verified webhook plus a redirect-return
route. `uses_api_keys=true`; no python SDK (HTTP via the parent engine).

## 5. Frontend (gap #3)
3 JS files, 1 OWL component. Registers **AuthUI** (`main_components:AuthUI` +
`services:auth_ui`) to render the Xendit 3DS authentication UI, and patches
**PaymentForm.prototype** to drive the Xendit.js SDK on Card. Assets load into
`web.assets_frontend` (glob `static/src/**/*`). The SDK and these interactions
are not reachable from Python metadata.

## 6. Business Architecture
- **Capabilities (inferred):** accept Card (direct/tokenized); accept SEA
  e-wallet/bank/QR (DANA, OVO, QRIS, FPX, Touch'n Go, PromptPay, LinePay,
  ShopeePay, ZaloPay…); 3DS via AuthUI; tokenization/saved cards; multi-currency
  (IDR/MYR/PHP/THB/VND).
- **Value streams (inferred):** Collect-Payment (Card direct + redirect/invoice),
  Tokenize-and-Recharge, Settle (webhook → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction,
  payment.token.
- **Organization (auto):** no own groups; credential fields gated by
  `base.group_system`.
- **Policies (inferred):** webhook token authenticity (403 on mismatch); redirect
  trusted only for draft→pending; zero-decimal currency rounding DOWN; is_recurring
  skips 3DS.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Xendit's SEA
  payment network (network promotion/contract mgmt = keys + webhook token;
  service provisioning = create/confirm invoice or charge; infrastructure
  operation = api.xendit.co + Xendit.js + webhook loop). Inherits the parent
  `payment` engine's model exactly. Mirrors sibling payment_stripe (network/support).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** direct Card via credit_card_charges (3DS via AuthUI); hosted
  redirect for SEA methods; tokenization incl. off-session recurring; webhook +
  return settlement; multi-currency (5 SEA currencies).
- **Common gaps:** no manual capture/authorize-then-capture, no void, no in-module
  refund override; no self-onboarding (manual API keys); webhook needs a public
  URL + a set `xendit_webhook_token`; currency support bounded.
- **Open questions:** full API payloads; runtime state/method-mix distribution;
  how refunds/chargebacks are handled operationally; whether instances rely on
  the webhook vs only the (non-finalizing) return route.
