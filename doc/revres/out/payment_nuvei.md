# payment_nuvei — Architecture Brief

> Payment Provider: Nuvei — an acquirer adapter that links an Odoo merchant to
> Nuvei (SafeCharge), a PSP covering Latin America (cards, PIX, Boleto, OXXO,
> PSE, SPEI, Webpay, AstroPay…). `_inherit`-only over the `payment` engine: no
> own models, no own ACL, **three** added provider fields. **Uniquely thin:** a
> signed browser **form-POST redirect** with *no* server-to-server REST call.
> Odoo 19.0, LGPL-3.

## 1. Overview
payment_nuvei is a concrete realization of the generic `payment` engine for the
Nuvei/SafeCharge PSP via its **PPP hosted Cashier**. It adds the `nuvei` provider
code plus three credentials (`nuvei_merchant_identifier`, `nuvei_site_identifier`,
`nuvei_secret_key` — the checksum key) and overrides the transaction/controller
hooks to drive a **redirect/form-POST flow**: it builds a flat parameter dict,
signs it with a **SHA-256 checksum**, and the browser auto-POSTs it to the
SafeCharge `purchase.do` Cashier. There is **no `_send_api_request` / `requests`**
— the only acquirer touchpoint is the signed form plus a checksum-verified
return/DMN. It is a finance/infrastructure support component, not an end-user app
(`application=false`). Tokenization, manual capture and refunds are explicitly
**not implemented** (README).

## 2. IT Architecture
- **Application:** Nuvei acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (no `payment.token` — no tokenization); redirect-form-POST
  only, no server-to-server REST.
- **Services (routes):** `/payment/nuvei/return` (http GET; verifies checksum or
  `error_access_token`), `/payment/nuvei/webhook` (http POST DMN, csrf=False;
  verifies `advanceResponseChecksum`, returns `'OK'`).
- **Data objects:** `payment.provider` (+merchant id / site id / secret key),
  `payment.transaction` (no new fields; 4 override methods).
- **Key relations:** tx → provider (`provider_code=='nuvei'` gates every
  override); external keys — reference == the `invoice_id` sent to Nuvei
  (`_extract_reference → data['invoice_id']`), `provider_reference == Nuvei
  TransactionID`.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Sign & redirect (form-POST, not API):** `_get_specific_rendering_values`
  builds `url_params` (merchant_id/merchant_site_id, currency, total_amount
  rounded DOWN — 0 decimals for `const.INTEGER_METHODS` like Webpay,
  invoice_id/item_name_1=reference, `payment_method` via
  `const.PAYMENT_METHODS_MAPPING` — card→cc_card, pix→apmgw_PIX,
  boleto→apmgw_BOLETO, oxxopay→apmgw_OXXO_PAY…, billing/phone, first/last name,
  success/pending/back/error/notify URLs), computes a `checksum`, returns
  `{api_url, checksum, url_params}`; the QWeb `redirect_form` auto-POSTs them to
  `purchase.do`. `const.FULL_NAME_METHODS` (boleto) require both names else
  `UserError`.
- **SHA-256 checksum auth (not Bearer):**
  `_nuvei_calculate_signature(data, incoming)` = `SHA256(nuvei_secret_key +
  concat(values))`. Outbound (`incoming=False`) concatenates **all** outgoing
  `data.keys()`; inbound verify (`incoming=True`) concatenates exactly
  `const.SIGNATURE_KEYS` = `[totalAmount, currency, responseTimeStamp,
  PPP_TransactionID, Status, productId]`. No `Authorization` header anywhere.
  `_nuvei_get_api_url` picks live (`secure.safecharge.com`) vs test
  (`ppp-test.safecharge.com`) by `provider.state`.
- **Verify BEFORE process:** both routes `_search_by_reference('nuvei', data)`
  (via `invoice_id`) then `_verify_signature` before `_process`. Payment branch:
  recompute over `SIGNATURE_KEYS`, `consteq`-compare `advanceResponseChecksum`,
  else **403 Forbidden** (missing checksum also rejected). Cancel/leave branch
  (Nuvei sends no checksum): validate `check_access_token(error_access_token,
  reference)`, else 403.
- **Status mapping (`_apply_updates`):** empty data → `_set_canceled('The
  customer left the payment page.')`; else store `TransactionID`, then
  `const.PAYMENT_STATUS_MAPPING`: `pending`→pending; `approved`/`ok`→done;
  `declined`/`error`/`fail`→error; missing/other→error.

## 4. External Integration (gap #7)
A real external acquirer link, but a **pure client-side redirect/form-POST** one
— no server-to-server REST (`http_call_sites=0`, no SDK). The browser auto-POSTs
the SHA-256-signed `url_params` + `checksum` to the SafeCharge `purchase.do`
Cashier (live `secure.safecharge.com` / test `ppp-test.safecharge.com`, by
`provider.state`), where card data is entered (module ships no `static/src`, only
description icons — PCI scope stays with Nuvei). Inbound settlement via a DMN
webhook + redirect-return, each gated by recomputing the checksum
(`SIGNATURE_KEYS`, `consteq` on `advanceResponseChecksum`) with a signed
access-token fallback for the cancel flow. Distinctive vs Mollie (Bearer +
re-fetch-by-id) and Stripe (Bearer + HMAC webhook): **Nuvei never calls the
acquirer server-side.** `uses_api_keys=true`; no python SDK.

## 5. Frontend (gap #3)
**Empty.** `extract_frontend.py` reports `present=false`: 0 JS, 0 OWL components,
0 registry adds, 0 patches, no asset bundles. The only template is the
server-side QWeb `redirect_form` that auto-POSTs the browser (checksum +
url_params) to Nuvei's hosted Cashier. The browser-side acquirer interaction
happens on Nuvei's page, not in Odoo-shipped JS.

## 6. Business Architecture
- **Capabilities (inferred):** accept LATAM card / local methods via the Nuvei
  hosted Cashier (card, PIX, Boleto, OXXO, PSE, SPEI, Webpay, AstroPay,
  MercadoPago/Naranja…); async settlement via DMN webhook + return; multi-currency
  (ARS/BRL/CLP/COP/MXN/PEN/USD/UYU/CAD); per-method amount-format & full-name
  handling.
- **Value streams (inferred):** Collect-Payment (sign → form-POST → return),
  Confirm-Settlement (DMN → checksum verify → status map), Abandon/Cancel
  (customer leaves → empty-data → `_set_canceled`), Settle (`approved`/`ok` →
  `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction (no
  payment.token).
- **Organization (auto):** no own groups; `nuvei_site_identifier` and
  `nuvei_secret_key` gated by `base.group_system` (merchant id is not).
- **Policies (inferred):** checksum authenticity (403 on mismatch/missing);
  access-token fallback for the cancel flow; live/test by `provider.state`;
  bounded currencies; round-DOWN with integer-method special case; full-name
  enforcement.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Nuvei's LATAM
  payment network (network promotion/contract mgmt = merchant/site ids + secret
  key + method enablement; service provisioning = sign/hand off & confirm the
  Cashier transaction; infrastructure operation = signed form-POST + checksum-
  verified DMN/return loop). Inherits the parent `payment` engine's model exactly.
  Mirrors siblings payment_stripe / payment_xendit (network/support). Uniquely
  thin: a signed redirect form-POST with **no** server-to-server REST.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-Cashier redirect via the PPP Payment Page (signed
  form-POST to `purchase.do`); DMN webhook + return settlement (checksum-verified,
  access-token fallback); multi-currency with integer-method / full-name handling;
  live/test by state; auto provider setup/teardown via the init hooks.
- **Common gaps:** **no tokenization** (with/without payment), **no manual
  capture/void**, **no refund** (all README 'Not implemented'); **no
  server-to-server API surface at all** (only the signed form-POST + verified
  webhook/return); no self-onboarding (manual merchant/site/secret); DMN webhook
  needs a public URL + correct `nuvei_secret_key`; currency bounded.
- **Open questions:** exact DMN field set & how `advanceResponseChecksum` is
  composed on Nuvei's side vs the `SIGNATURE_KEYS` recomputation; runtime
  state/method-mix distribution and how often the 'customer left' path fires; how
  refunds/captures/tokenization are handled operationally; whether instances rely
  on the DMN vs the return route and how duplicate notifications are de-duplicated.
