# payment_worldline — Architecture Brief

> Payment Provider: Worldline — an acquirer adapter that links an Odoo merchant to
> Worldline (French PSP, several European countries) via the Worldline Direct /
> Global Collect platform. `_inherit`-only over the `payment` engine: no own
> models, no own ACL, 5 added provider fields. Odoo 19.0, `version 1.0`, LGPL-3.
> A genuine S2S API (GCS v1HMAC) **plus** hosted-checkout redirect and
> tokenization.

## 1. Overview
payment_worldline is a concrete realization of the generic `payment` engine for
Worldline. It adds the `worldline` provider code plus five credential fields
(PSPID, API key, API secret, webhook key, webhook secret) and overrides the
transaction/provider/controller hooks to drive two flows: a **hosted-checkout
redirect** (S2S `POST hostedcheckouts` mints a `redirectUrl` the browser is sent
to) and a **direct S2S token flow** (`POST payments` with a saved card token). It
is a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. IT Architecture
- **Application:** Worldline Direct acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (+ `payment.token` vaulting).
- **Services (routes):** `/payment/worldline/return` (http GET — validates
  `provider_id`, **re-fetches** the result via S2S `GET hostedcheckouts/{id}`,
  then `/payment/status`), `/payment/worldline/webhook` (http POST, csrf=False,
  `X-GCS-Signature` HMAC verified, returns empty JSON).
- **Data objects:** `payment.provider` (+worldline_pspid/api_key/api_secret/
  webhook_key/webhook_secret), `payment.transaction` (no new fields; 10 override
  methods).
- **Key relations:** tx → provider (`provider_code=='worldline'` gates every
  override); tx → token (`token.provider_ref == Worldline card token`); external
  keys `reference == merchantReference` (≤30 chars), `provider_reference ==
  payment id without trailing `_<seq>``.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` →
  `_worldline_create_checkout_session` → S2S `POST /v2/<pspid>/hostedcheckouts`
  (full order/customer/references payload; `redirectPaymentMethodSpecificInput`
  for `const.REDIRECT_PAYMENT_METHODS`, else `cardPaymentMethodSpecificInput`
  SALE+tokenize) → returns `{api_url: redirectUrl}`; the **empty** redirect form
  auto-POSTs the browser there.
- **Outbound auth (`_build_request_*` + `_worldline_calculate_signature`):** every
  S2S call carries `Authorization: GCS v1HMAC:<api_key>:<sig>` where `sig =
  Base64(HMAC-SHA256(worldline_api_secret, "<method>\n<content-type>\n<rfc1123
  date>\n[x-gcs-idempotence-key:<k>\n]/v2/<pspid>/<endpoint>\n"))`; URL is
  `<host>/v2/<pspid>/<endpoint>`. HTTP delegated to the engine's
  `_send_api_request`.
- **Direct/token flow:** `_send_payment_request` → S2S `POST payments`
  (`token=token_id.provider_ref`, `merchantInitiated` / `subsequent` unscheduled
  card-on-file, `SALE`), idempotency-keyed → `_process`.
- **Inbound (dual model):** the **return GET** doesn't trust the browser — it
  validates `provider_id` (else 403) and re-fetches via S2S `GET
  hostedcheckouts/{id}`. The **webhook POST** verifies `X-GCS-Signature =
  Base64(HMAC-SHA256(worldline_webhook_secret, raw body))` (a *separate* secret
  from the api-secret) with `hmac.compare_digest` (else 403) **before**
  `_process`.
- **Status mapping (`_apply_updates`):** CREATED/REDIRECTED/AUTHORIZATION_
  REQUESTED/PENDING_CAPTURE/CAPTURE_REQUESTED → pending; CAPTURED → done;
  CANCELLED → cancel; REJECTED/REJECTED_CAPTURE → error(declined). Special cases:
  `AUTHORIZATION_REQUESTED` on a token/offline op → error; a `validation` op with
  token data at PENDING/CAPTURE_REQUESTED → done.
- **3DS fallback:** the `AUTHORIZATION_REQUESTED`→error on a token charge is
  caught by `_get_specific_processing_values`, which resets the tx to draft,
  switches to `online_redirect`, and returns `force_flow='redirect'` — the
  `PaymentForm._processTokenFlow` JS patch then redirects the saved-card payment
  to the hosted checkout so 3-D Secure completes.
- **Tokenization:** `_extract_token_values` vaults `provider_ref = token` + last4
  of `card.cardNumber`; `support_tokenization` force-enabled.

## 4. External Integration (gap #7)
A real external acquirer link with a genuine outbound REST channel (unlike the
pure-redirect APS/Buckaroo/Redsys). **Outbound** S2S REST to the Worldline Direct
API — `https://payment.direct.worldline-solutions.com` (live) /
`...preprod...` (preprod), paths `/v2/<pspid>/{hostedcheckouts,
hostedcheckouts/<id>, payments}` — authenticated by a **GCS v1HMAC** HMAC-SHA256
request signature (`worldline_api_key`/`secret`). **Inbound** webhooks
authenticated by a **separate** `worldline_webhook_secret` HMAC (`X-GCS-Signature`)
plus a return route that re-fetches the authoritative result via S2S. No python
SDK; `uses_api_keys=true`. This sits between Stripe/Xendit (full S2S) and
APS/Buckaroo/Redsys (redirect-only).

## 5. Frontend (gap #3)
1 JS file, 0 OWL components, 1 patch. `payment_form.js` patches
`PaymentForm.prototype._processTokenFlow`: when `force_flow==='redirect'` for
worldline, it calls `_processRedirectFlow` instead — transparently switching a
saved-card payment to the hosted-checkout redirect for 3-D Secure (docstring still
names the legacy "Ogone" flow). No inline card form, no browser SDK — card entry
is on Worldline's hosted checkout. Assets load into `web.assets_frontend`.

## 6. Business Architecture
- **Capabilities (inferred):** accept card (Visa/Mastercard/Amex/Discover) via
  hosted checkout; many European/international redirect methods (iDEAL, Bancontact,
  EPS, P24, Klarna, PayPal, TWINT, MB WAY, Multibanco, Bizum, PostFinance Pay,
  Alipay+, WeChat Pay, FLOA…); tokenization + merchant-initiated recurring; 3-D
  Secure with redirect fallback; multi-currency.
- **Value streams (inferred):** Collect-Payment (redirect + token/direct),
  Tokenize-and-Recharge, Settle (CAPTURED → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction,
  payment.token.
- **Organization (auto):** no own groups; note the five credential fields are
  **not** pinned to `base.group_system` (only password-masked in the view).
- **Policies (inferred):** webhook authenticity (X-GCS-Signature, 403 on
  mismatch); return re-fetches rather than trusts the browser; outbound GCS-HMAC
  signing + idempotency; forced captures; references ≤30 chars; token-3DS
  redirect fallback.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Worldline's card /
  European-method network (network promotion/contract mgmt = PSPID + api/webhook
  keys; service provisioning = create/confirm hosted-checkout or payment;
  infrastructure operation = the GCS-HMAC S2S link + hosted-checkout redirect +
  webhook-verified settlement). Inherits the parent `payment` engine's model
  exactly. Mirrors sibling payment_stripe / payment_xendit (network/support); a
  richer variant than APS/Buckaroo/Redsys — genuine S2S API plus redirect and
  tokenization, like Xendit's dual shape.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-checkout redirect minted via S2S `hostedcheckouts`;
  European-method routing; direct S2S token `payments` (merchant-initiated,
  idempotency-keyed); tokenization with 3-D Secure redirect fallback; webhook
  (X-GCS-Signature) + S2S-re-fetching return settlement; multi-currency.
- **Common gaps:** no manual capture/void (captures forced), no in-module refund
  override; no self-onboarding (manual credentials); the credential fields are not
  `base.group_system`-restricted (only password-masked); webhook needs a public
  URL + a set webhook secret; webhook verification skipped when no tx matches.
- **Open questions:** full hostedcheckouts/payments payloads; runtime state/
  method-mix + tokenization distribution; how refunds/chargebacks are handled
  operationally; whether the unrestricted credential fields are intentional;
  webhook vs S2S-re-fetch reliance and real-world 3DS-fallback behavior.
