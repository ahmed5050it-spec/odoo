# payment_redsys — Architecture Brief

> Payment Provider: Redsys — an acquirer adapter that links an Odoo merchant to
> Redsys, the Spanish banking sector's card-acquiring network (card + Bizum).
> `_inherit`-only over the `payment` engine: no own models, no own ACL, 4 added
> provider fields. Odoo 19.0, `version 1.0`, LGPL-3. Pure hosted-redirect
> (no server-to-server API, no tokenization).

## 1. Overview
payment_redsys is a concrete realization of the generic `payment` engine for the
Redsys PSP (Spanish market). It adds the `redsys` provider code plus three
credential fields (merchant code, merchant terminal, secret key) and overrides
the transaction/controller hooks to drive a single **hosted-redirect SIS flow**:
the browser auto-POSTs a signed, Base64-enveloped merchant-parameters form to
Redsys' `realizarPago` SIS page; Redsys collects the card/Bizum payment (with EMV
3-D Secure) and returns the signed result to Odoo's return + webhook routes. It is
a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. IT Architecture
- **Application:** Redsys acquirer adapter; inherits `payment.provider` /
  `payment.transaction`. No `payment.token` (no tokenization).
- **Services (routes):** `/payment/redsys/return` (http GET, signature-verified,
  → `/payment/status`), `/payment/redsys/webhook` (http POST, csrf=False,
  signature-verified, returns `OK`). Both Base64-decode `Ds_MerchantParameters`.
- **Data objects:** `payment.provider`
  (+redsys_merchant_code/merchant_terminal/secret_key), `payment.transaction`
  (no new fields; 7 override methods).
- **Key relations:** tx → provider (`provider_code=='redsys'` gates every
  override); external keys `reference == DS_MERCHANT_ORDER/Ds_Order` (9-12
  alphanumeric chars) and `provider_reference == reference` (stamped at create()).

## 3. Behavioral Notes (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` →
  `_redsys_prepare_merchant_parameters` (DS_MERCHANT_AMOUNT in minor units,
  DS_MERCHANT_CURRENCY=`currency.iso_numeric`, merchant code/terminal,
  DS_MERCHANT_ORDER=reference, DS_MERCHANT_MERCHANTURL=webhook,
  DS_MERCHANT_URLOK/URLKO=return, DS_MERCHANT_PAYMETHODS from
  `const.PAYMENT_METHODS_MAPPING`, and a DS_MERCHANT_EMV3DS billing/cardholder
  block) → JSON → Base64 → sign → returns `api_url`,
  `merchant_parameters`, `signature`, `signature_version='HMAC_SHA256_V1'` into
  the 3-input redirect form. **No S2S call.**
- **Signature (`_redsys_calculate_signature`, both directions):** Base64-decode
  `redsys_secret_key` → master 3DES key → **derive a per-order key** by 3DES-CBC
  (zero IV) encrypting the order/reference padded to 16 bytes →
  `hmac.new(derived_key, merchant_parameters, sha256)` → urlsafe-Base64. It is an
  HMAC-SHA256 *keyed by a per-order key*, not a plain HMAC over the secret.
- **Inbound (both routes):** Base64-decode `Ds_MerchantParameters` →
  `_search_by_reference('redsys', data)` (via `_extract_reference` → `Ds_Order`)
  → `_verify_signature` (reads `Ds_Signature`, constant-time
  `hmac.compare_digest` vs the recomputed signature, else HTTP 403 Forbidden)
  **before** `_process`. Verification only runs when a tx is found.
- **Status mapping (`_apply_updates`):** `Ds_Response` `0000`-`0099`/`400`/`900`
  → done; `9915` → cancel; a ~35-code error list (carrying `Ds_ErrorCode`) →
  error; anything else → error ("Unknown status code").
- **No tokenization / refund / capture / void** in this module.

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **No outbound REST
client and no transport API key:** the only endpoints are the Redsys SIS pages —
`https://sis.redsys.es/sis/realizarPago` (live) and
`https://sis-t.redsys.es:25443/sis/realizarPago` (test), chosen by
`provider.state` in `_redsys_get_api_url`. Redsys is reached purely by the browser
POSTing the signed hidden-field form; settlement returns to
`/payment/redsys/return` and pushes to `/payment/redsys/webhook` (the
`DS_MERCHANT_MERCHANTURL`). `uses_api_keys=true` is misleading — the
`redsys_secret_key` is the Base64 seed for the per-order 3DES key behind the
HMAC-SHA256 signature, not a bearer token.

## 5. Frontend (gap #3)
0 JS files, 0 OWL components, 0 registry adds, 0 patches. The entire buyer
interaction is the server-rendered `redirect_form` QWeb template
(`payment_redsys_templates.xml`) with three hidden inputs
(`Ds_MerchantParameters` / `Ds_Signature` / `Ds_SignatureVersion`) auto-POSTing to
the SIS page. Card / Bizum data are collected on Redsys' hosted page (3-D Secure
via `DS_MERCHANT_EMV3DS`), never in Odoo.

## 6. Business Architecture
- **Capabilities (inferred):** accept card + Bizum (Visa/Mastercard/Amex/Diners/
  JCB) via the hosted SIS page; EMV 3-D Secure; signed-redirect settlement;
  multi-currency (ISO-numeric).
- **Value streams (inferred):** Collect-Payment (redirect), Settle (`Ds_Response`
  success band → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; `redsys_secret_key` gated by
  `base.group_system`.
- **Policies (inferred):** inbound authenticity (403 on signature mismatch);
  outbound form signed (`HMAC_SHA256_V1`); references forced alphanumeric 9-12
  chars; minor-unit amounts + ISO-numeric currency.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects Spanish payer and merchant by linking the merchant to Redsys'
  card-acquiring network (network promotion/contract mgmt = merchant code/terminal
  + signing secret; service provisioning = build/sign/confirm the SIS redirect;
  infrastructure operation = the SIS handoff + signed return/webhook loop).
  Inherits the parent `payment` engine's model exactly. Mirrors sibling
  payment_stripe / payment_xendit (network/support); like APS/Buckaroo it is
  redirect-only, distinctively signed with a **per-order 3DES-derived-key
  HMAC-SHA256**.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-redirect card/Bizum via SIS `realizarPago` (authorization
  transaction type); per-brand routing via `DS_MERCHANT_PAYMETHODS`; EMV 3-D
  Secure; per-order 3DES+HMAC-SHA256 signing; webhook + return settlement;
  multi-currency (ISO-numeric).
- **Common gaps:** no S2S API; no tokenization/saved cards; no manual capture/
  void/refund override; signature scheme fixed (`HMAC_SHA256_V1`); webhook needs a
  public URL + a set secret; verification skipped when no tx matches the reference.
- **Open questions:** full SIS request/response field sets; runtime state/
  method-mix distribution; how refunds/chargebacks are handled operationally;
  whether instances rely on the webhook vs the (also signed) return route.
