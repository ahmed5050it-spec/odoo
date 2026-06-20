# payment_ecpay — Architecture Brief

> Payment Provider: ECPay — an acquirer adapter that links an Odoo merchant to
> ECPay, the Taiwanese PSP (card, WeChat Pay, convenience-store cash, ATM/WebATM,
> mobile wallet, TWQR), TWD only. `_inherit`-only over the `payment` engine: no
> own models, no own ACL, 3 added provider fields. Distinctively a **redirect-only**
> acquirer — no server-to-server API call. Odoo 19.0, LGPL-3.

## 1. Overview
payment_ecpay is a concrete realization of the generic `payment` engine for the
ECPay PSP. It adds the `ecpay` provider code plus three credential fields
(Merchant ID, Secure Hash Key, Secure Hash IV) and overrides the
transaction/controller hooks to drive a single **hosted-redirect flow**: a
CheckMacValue-signed QWeb form the browser auto-submits to ECPay's AioCheckOut V5
cashier. There is **no outbound HTTP from Odoo** (no `requests`, no
`_send_api_request`) and **no client-side SDK**. It is a finance/infrastructure
support component, not an end-user app (`application=false`).

## 2. IT Architecture
- **Application:** ECPay acquirer adapter; inherits `payment.provider` /
  `payment.transaction`. No `payment.token` (no tokenization).
- **Services (routes):** `/payment/ecpay/webhook` (http POST, csrf=False —
  ECPay's authoritative server-to-server ReturnURL callback, replies `1|OK`),
  `/payment/ecpay/return` (http GET+POST, csrf=False — browser
  ClientBackURL/OrderResultURL; processes a POST payload, plain GET only
  redirects to `/payment/status`).
- **Data objects:** `payment.provider` (+ecpay_merchant_id/ecpay_hash_key/
  ecpay_hash_iv), `payment.transaction` (no new fields; 5 override methods).
- **Key relations:** tx → provider (`provider_code=='ecpay'` gates every
  override); external keys `reference==MerchantTradeNo` (≤20 alnum chars),
  `provider_reference==TradeNo`. No token relation.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` builds the AioCheckOut
  field set (MerchantID, MerchantTradeNo=reference, MerchantTradeDate in
  Asia/Taipei, PaymentType=`aio`, TotalAmount=int(amount), ChoosePayment=`ALL`,
  IgnorePayment = diff of `const.PAYMENT_METHODS_MAPPING` so only the chosen
  method set is offered), signs it into `CheckMacValue`, adds `api_url` from
  `_ecpay_get_api_url` → QWeb `redirect_form` auto-POSTs to ECPay. No
  server-to-server call.
- **Signature scheme:** `_ecpay_calculate_signature` →
  `CheckMacValue = SHA256(URLEncode(HashKey + sorted-data + HashIV)).upper()`
  (case-insensitive key sort, `quote_plus` safe=`-_.!*()`, lowered before
  hashing). `EcpayController._verify_signature` runs on **every** inbound
  message *before* `_process`: pops `CheckMacValue`, 403 Forbidden if missing,
  recomputes and `consteq`-compares. Shared secret = HashKey + HashIV
  (`base.group_system`). No HTTP auth header, no bearer token.
- **Inbound:** webhook (POST) processes only when `SimulatePaid=='0'` (real
  payment), verifies, `_process`, returns `1|OK`. Return route works only on a
  POST that carries data. `_search_by_reference('ecpay', data)` →
  `_extract_reference` → `data['MerchantTradeNo']`.
- **Status mapping (`_apply_updates`):** `provider_reference=TradeNo`; brand PM
  refined via `PAYMENT_METHODS_RESPONSE_MAPPING` (CVS_OK/CVS_HILIFE/CVS_FAMILY/
  DigitalPayment_IPASS); `RtnCode ∈ ('1','2','10100073')` → `_set_done`, else
  `_set_error(RtnMsg)`. **Strictly done-or-error** — no pending, no cancel.
- **Reference policy:** `_compute_reference` caps MerchantTradeNo at 20 chars,
  alphanumeric only (singularize_reference_prefix, no separator).

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata — **redirect-only
variant**. **Outbound** is a CheckMacValue-signed AioCheckOut form POST submitted
by the customer's **browser** to `https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5`
(stage: `payment-stage.ecpay.com.tw`), declared in `_ecpay_get_api_url` —
**not** an Odoo→ECPay HTTP call (`uses_api_keys=false`, `http_call_sites=0`, no
`requests`, no SDK; the parent `_send_api_request` is never invoked).
**Inbound** settlement via ECPay's CheckMacValue-signed server-to-server webhook
(`1|OK` ack) plus the browser return. Integrity rests entirely on the shared
Secure Hash Key + Hash IV via SHA-256.

## 5. Frontend (gap #3)
None. `frontend.present=false` — 0 JS, 0 OWL, 0 patches, no asset bundles.
Unlike client-tokenizing acquirers, ECPay ships no browser code; the only client
artifact is the server-rendered QWeb `redirect_form`. Card/CVS/ATM/wallet data
is entered on ECPay's hosted pages, never in Odoo (no client-side PCI surface).

## 6. Business Architecture
- **Capabilities (inferred):** accept TWD payments via the ECPay AioCheckOut
  hosted cashier; Card/Credit, WeChat Pay, CVS+Barcode convenience-store cash
  (OK Mart, Hi-Life, FamilyMart), ATM/WebATM, DigitalPayment wallet (incl. iPASS
  MONEY), TWQR; method gating via IgnorePayment.
- **Value streams (inferred):** Collect-Payment (hosted redirect), Confirm-on-
  return, Settle (webhook → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; HashKey/HashIV gated by
  `base.group_system`; Merchant ID unrestricted.
- **Policies (inferred):** inbound CheckMacValue authenticity (403 on mismatch);
  simulation guard (`SimulatePaid != '0'` skipped); ≤20-char alnum references;
  TWD-only (hard constraint); strictly done-or-error states.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to ECPay's Taiwanese
  payment network (network promotion/contract mgmt = Merchant ID + HashKey/IV +
  method enablement; service provisioning = render/sign/confirm the AioCheckOut
  order; infrastructure operation = the browser-submitted redirect + the
  CheckMacValue-verified webhook loop). Inherits the parent `payment` engine's
  model exactly. Mirrors siblings payment_xendit / payment_stripe (network/
  support); distinctive in being a **redirect-only** mediator (no API).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted redirect via AioCheckOut V5 (CheckMacValue-signed);
  multi-method (Card, WeChat, CVS/Barcode, ATM/WebATM, wallet, TWQR) with
  IgnorePayment gating; brand-PM refinement from the response; webhook + return
  settlement; TWD-only.
- **Common gaps:** no tokenization/saved cards; no in-module refund override; no
  manual capture/authorize-then-capture, no void; **no server-to-server API at
  all** (depends on the browser submitting the form and ECPay reaching the public
  webhook URL); single currency (TWD only); no self-onboarding (manual Merchant
  ID + Hash Key/IV).
- **Open questions:** full AioCheckOut field set (incl. CVS/Barcode payment-info
  notifications); runtime state/method-mix distribution; how refunds/chargebacks
  are handled operationally; whether instances reliably expose the public webhook
  URL (the return route never compensates for a missed webhook).
