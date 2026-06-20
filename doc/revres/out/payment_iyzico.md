# payment_iyzico — Architecture Brief

> Payment Provider: Iyzico — an acquirer adapter that links an Odoo merchant to
> Iyzico, the Turkish PSP (card: Visa/Mastercard/Amex/Troy, plus bank transfer).
> `_inherit`-only over the `payment` engine: no own models, no own ACL, 2 added
> provider fields. A **hosted-redirect** flow that begins with a server-to-server
> Checkout-Form initialize and verifies callbacks by **re-fetching** the result.
> Odoo 19.0, LGPL-3.

## 1. Overview
payment_iyzico is a concrete realization of the generic `payment` engine for the
Iyzico PSP. It adds the `iyzico` provider code plus two credential fields (API
Key, Secret Key) and overrides the transaction/controller hooks to drive a
**hosted Checkout-Form (CF) flow**: a server-to-server `CF-initialize` POST
returns a `paymentPageUrl`, the browser is redirected there, and the inbound
webhook/return is verified not by a local signature but by **re-fetching**
`CF-detail` over the authenticated API. No client-side SDK. It is a
finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. IT Architecture
- **Application:** Iyzico acquirer adapter; inherits `payment.provider` /
  `payment.transaction`. No `payment.token` (no tokenization).
- **Services (routes):** `/payment/iyzico/return` (http POST, csrf=False,
  save_session=False — browser callbackUrl carrying `tx_ref`+`token`),
  `/payment/iyzico/webhook` (http POST, csrf=False — async notification carrying
  `paymentConversationId`+`token`; acknowledges with empty JSON).
- **Data objects:** `payment.provider` (+iyzico_key_id/iyzico_key_secret),
  `payment.transaction` (no new fields; 4 override methods).
- **Key relations:** tx → provider (`provider_code=='iyzico'` gates every
  override); external keys `reference==conversationId/paymentConversationId/
  tx_ref`, `provider_reference==paymentId`; transient CF `token` exchanged for
  detail. No token relation.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Initialize + redirect:** `_get_specific_rendering_values` builds the CF
  payload via `_iyzico_prepare_cf_initialize_payload` (dummy `Odoo purchase`
  basket item, billingAddress/buyer from the partner, callbackUrl with
  `?tx_ref=`, conversationId=reference, currency, locale, paidPrice/price,
  paymentSource=`ODOO`) and POSTs it to
  `payment/iyzipos/checkoutform/initialize/auth/ecom` via the parent
  `_send_api_request`. The returned `paymentPageUrl` is parsed into
  `api_url`+`url_params` → QWeb `redirect_form` GETs the browser to Iyzico's
  hosted Checkout Form. On error → `_set_error`, returns `{}`.
- **Outbound auth — IYZWSv2 HMAC-SHA256:** configured on `payment.provider`.
  `_build_request_url` → `https://api.iyzipay.com` (enabled) /
  `https://sandbox-api.iyzipay.com` (test). `_build_request_headers` mints an
  8-char `random_string`, computes `_iyzico_calculate_signature` =
  `hmac.new(iyzico_key_secret, '{rnd}/{endpoint}{json payload}', sha256).hexdigest()`,
  assembles `apiKey:…&randomKey:…&signature:…`, base64-wraps it →
  `Authorization: IYZWSv2 <b64>` + `x-iyzi-rnd`. `_parse_response_content`
  rejects unless `status=='success'`. **This signs Odoo's outbound requests; it
  is NOT a per-message webhook signature.**
- **Inbound — verify by re-fetch (no local signature):** both routes pull a
  one-time `token` and call `_verify_and_process(tx_ref, token)` →
  `_search_by_reference('iyzico', {'reference': tx_ref})` (Iyzico does **not**
  override `_extract_reference`; the base hook reads `payment_data['reference']`)
  → a **second** server call `POST payment/iyzipos/checkoutform/auth/ecom/detail`
  to retrieve the authoritative detail → `_process`. The callback body is never
  trusted; a failed re-fetch is logged and dropped.
- **Status mapping (`_apply_updates`):** `provider_reference=paymentId`; brand PM
  from `cardAssociation` (`const.PAYMENT_METHODS_MAPPING`: amex→american_express,
  mastercard→master_card) when `cardType` set, else `bank_transfer` (bankName) or
  `unknown`; `paymentStatus`: INIT_THREEDS/CALLBACK_THREEDS/INIT_BANK_TRANSFER/
  INIT_CREDIT/PENDING_CREDIT → pending; SUCCESS → done; FAILURE/unknown → error.

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **Outbound**
server-to-server REST to `api.iyzipay.com` (sandbox `sandbox-api.iyzipay.com`) —
`…/checkoutform/initialize/auth/ecom` (CF-initialize) and
`…/checkoutform/auth/ecom/detail` (CF-detail/retrieve) — authenticated with the
**IYZWSv2 HMAC-SHA256** header (public `apiKey` + secret-keyed HMAC + `x-iyzi-rnd`).
**Client-side** is only a browser redirect to Iyzico's hosted Checkout Form (no
SDK). **Inbound** settlement via a webhook + return that carry no verifiable
signature and are trusted only via the **CF-detail re-fetch**. `uses_api_keys=true`;
no python SDK (HTTP via the parent engine).

## 5. Frontend (gap #3)
None. `frontend.present=false` — 0 JS, 0 OWL, 0 patches, no asset bundles.
Iyzico ships no browser code; the only client artifact is the server-rendered
QWeb `redirect_form` (a GET form re-emitting the decoded `paymentPageUrl` params)
that lands the browser on Iyzico's hosted Checkout Form. Card data is entered on
Iyzico's pages, never in Odoo.

## 6. Business Architecture
- **Capabilities (inferred):** accept Turkish-market payments via Iyzico's
  hosted Checkout Form; Card (Visa, Mastercard, Amex, Troy) + bank transfer; 3DS
  on Iyzico's hosted form; multi-currency (CHF/EUR/GBP/IRR/NOK/RUB/TRY/USD).
- **Value streams (inferred):** Collect-Payment (CF-initialize → hosted
  redirect), Verify-and-Settle (re-fetch CF-detail → `_process`), Settle
  (SUCCESS → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; `iyzico_key_secret` gated by
  `base.group_system`; API Key unrestricted.
- **Policies (inferred):** inbound authenticity by re-fetch (callbacks not
  trusted on face); outbound IYZWSv2 HMAC; response gate `status=='success'`;
  pending/done/error state mapping; currency bounded.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Iyzico's Turkish
  card network (network promotion/contract mgmt = API Key + Secret Key + method/
  currency enablement; service provisioning = initialize the Checkout Form and
  confirm by re-fetching CF-detail; infrastructure operation = the api.iyzipay.com
  link + hosted redirect + token-re-fetch settlement loop). Inherits the parent
  `payment` engine's model exactly. Mirrors siblings payment_xendit /
  payment_stripe (network/support); distinctive in verifying callbacks by
  **re-fetch** rather than a local signature.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted redirect via the Iyzico Checkout Form; card with brand
  mapping + bank-transfer recognition; 3DS on Iyzico's form; webhook + return
  settlement verified by CF-detail re-fetch; multi-currency (8 currencies).
- **Common gaps:** no tokenization/saved cards; no in-module refund override; no
  manual capture/authorize-then-capture, no void; webhook/return need a public
  URL + a set `iyzico_key_secret` (the verifying re-fetch needs the signing
  secret); callbacks carry no independent signature so trust rests on the
  re-fetch (a missed/failed re-fetch is silently dropped); currency bounded; no
  self-onboarding (manual API Key + Secret Key).
- **Open questions:** full CF-initialize/CF-detail payloads; runtime state/
  method/currency-mix distribution; how refunds/chargebacks are handled
  operationally; robustness of re-fetch-as-verification when the CF-detail call
  fails/times out (error only logged, tx left unprocessed).
