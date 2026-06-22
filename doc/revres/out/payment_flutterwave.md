# payment_flutterwave — Architecture Brief

> Flutterwave payment acquirer for Odoo 19. A thin `_inherit`-only adapter on the
> base `payment` engine that connects an Odoo merchant to Flutterwave's African
> card / mobile-money network. Value model: **network** (mediating technology) ·
> Activity class: **support** · APQC **9.0 Manage Financial Resources**.

## 1. Overview
- Module: `payment_flutterwave` (category *Accounting/Payment Providers*, v1.0, `depends: [payment]`, `application=false`, `auto_install=false`).
- Purpose: accept card, mobile-money (M-Pesa), and bank-transfer payments via Flutterwave across 22 supported currencies, mostly African markets.
- Shape: no own models — inherits `payment.provider`, `payment.transaction`, `payment.token`. 777 py LOC, 47 xml LOC, 3 public routes, 0 security rules.
- Author: Odoo S.A., LGPL-3.

## 2. IT Architecture
- **Application:** Flutterwave acquirer adapter; every override is gated on `provider_code == 'flutterwave'`.
- **Software services (routes):** `/payment/flutterwave/return` (redirect-return), `/payment/flutterwave/auth_return` (3DS return), `/payment/flutterwave/webhook` (csrf=False, verif-hash).
- **Data objects:** `payment.provider` (+public/secret/webhook keys), `payment.transaction` (no new fields), `payment.token` (+`flutterwave_customer_email`).
- **Key relations:** tx→provider (gate), tx→token (off-session charge), token→provider. Cross-system keys: `reference == tx_ref`, `provider_reference == Flutterwave transaction id` (or the 3DS auth URL while pending).

## 3. External Integration (gap #7)
- One outbound endpoint: `https://api.flutterwave.com/v3/` (direct REST), Bearer `<flutterwave_secret_key>` auth — built by `_build_request_url` / `_build_request_headers`; HTTP delegated to the parent `payment.provider._send_api_request` (no `requests` import here, no python SDK).
- Outbound calls: `POST payments` (hosted payment link), `POST tokenized-charges` (saved-token charge), `GET transactions/verify_by_reference` (authoritative re-verify).
- **No client-side acquirer SDK** — payment is collected on Flutterwave's HOSTED checkout page (browser is redirected to `data['link']`). The only channels are server-to-server REST + the redirect/webhook return loop.
- Inbound webhook trust: `verif-hash` header compared to `flutterwave_webhook_secret` with constant-time `hmac.compare_digest` → HTTP 403 Forbidden on mismatch/missing.

## 4. Behavioral Notes (code-read)
- `_get_specific_rendering_values`: POSTs `payments` with tx_ref/amount/currency/customer/customizations, embeds returned `link` as a self-submitting redirect form to the hosted checkout.
- `_send_payment_request`: POSTs `tokenized-charges` (token, email, amount, country, ip, auth redirect_url) then `_process`.
- `_get_specific_processing_values`: when `_flutterwave_is_authorization_pending()`, renders `redirect_form_view_id` with the bank's 3DS `auth_url` (stashed in `provider_reference`) to bounce the payer to the issuer page.
- Controller `_verify_and_process`: never trusts the redirect payload — re-fetches via `GET transactions/verify_by_reference` before `_process`.
- `_compute_reference`: singularizes the prefix with the datetime (Flutterwave requires per-merchant-unique tx_ref).
- Status mapping (`_apply_updates` via `const.PAYMENT_STATUS_MAPPING`): pending/'pending auth'→pending, successful→done, cancelled→canceled, failed/unknown→error.

## 5. Business Architecture
- **Capabilities (inferred):** accept card/mobile-money/online payments; multi-currency African acceptance; 3-D Secure; tokenization / saved cards; server-side result verification.
- **Value streams (inferred):** Collect-Payment (hosted checkout → verify → state machine); Tokenize-and-Recharge (off-session tokenized-charges); Authorize-3DS (issuer redirect → auth_return).
- **Information concepts (auto):** payment.provider (credentials), payment.transaction (= Flutterwave payment/charge), payment.token (card token + email).
- **Organization (auto):** no own groups; secret & webhook keys gated by `base.group_system`.
- **Policies (inferred):** webhook verif-hash check; redirect never trusted (re-verify); Flutterwave excluded from validation ops; currency allow-list; unique tx_ref.
- **Stakeholders:** payer, merchant/company, Flutterwave (PSP), card issuer (3DS), accountant (downstream). **Strategy:** null (human). **Metrics:** inherited from parent pivot/graph.

## 6. Classification
- **value_model = network** — a mediating-technology acquirer linking payer and merchant via Flutterwave's network; inherits the parent payment engine's mediation. Not chain (no input→output transform), not shop (no bespoke problem-solving).
- **activity_class = support** — payment acceptance is an infrastructure/finance support function (Accounting/Payment Providers, no end-user app).
- **apqc_category = 9.0 Manage Financial Resources** (9.5 process payments / collect cash; manage external payment provider).
- Mirrors sibling `payment_stripe` (network/support) and parent `payment` (network/support).

## 7. Fit-to-Standard
- **Standard:** hosted-checkout card/mobile-money/bank-transfer, multi-currency, tokenization + off-session charges, 3DS via redirect, server-side re-verification, verif-hash webhook + redirect-return settlement.
- **Typical fits:** shop/portal checkout in supported African markets; save-card recurring; pay-invoice-online; 22-currency acceptance.
- **Common gaps:** no manual/partial capture, authorize-only, or void; hosted-redirect only (no inline card Element); webhook needs a public URL; static currency list (last refreshed Nov 2022); manual API-key entry (no Connect-style onboarding); reconciliation chains live downstream.
- **Drive hints:** `odoo shell` provider/tx searches; `print([m for m in dir(env['payment.transaction']) if '_flutterwave' in m])`; `curl` the webhook with a bad `verif-hash` → expect 403.

## 8. Open Questions
- Real-world distribution of transaction states, tokenization usage, refund rates (no runtime counts).
- Exact refund payload/response and whether partial refunds are exercised (no refund-request override in the read files).
- Which downstream modules consume settled transactions (account_payment, sale, subscription).
- Whether instances register the webhook (`flutterwave_webhook_secret` set) vs rely on the redirect-return + verify_by_reference path.
