# payment_mollie — Architecture Brief

> Payment Provider: Mollie — an acquirer adapter that links an Odoo merchant to
> Mollie, the Dutch PSP covering several European countries (cards, iDEAL,
> Bancontact, SEPA, Przelewy24, Apple Pay…). `_inherit`-only over the `payment`
> engine: no own models, no own ACL, **one** added provider field (the API key).
> Odoo 19.0, `version 1.0`, LGPL-3.

## 1. Overview
payment_mollie is a concrete realization of the generic `payment` engine for the
Mollie PSP. It adds the `mollie` provider code plus a single credential field
(`mollie_api_key`, Test or Live) and overrides the transaction/controller hooks
to drive a **hosted-redirect flow**: it creates a Mollie payment server-to-server
(`POST /payments` on `api.mollie.com/v2`), redirects the browser to the
Mollie-hosted checkout, and confirms settlement by **re-fetching the payment by
id**. It is a finance/infrastructure support component, not an end-user app
(`application=false`). Tokenization, manual capture and refunds are explicitly
**not implemented** (README).

## 2. IT Architecture
- **Application:** Mollie acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (no `payment.token` — no tokenization).
- **Services (routes):** `/payment/mollie/return` (http GET/POST, csrf=False,
  save_session=False), `/payment/mollie/webhook` (http POST, csrf=False). Both
  call the same `_verify_and_process`.
- **Data objects:** `payment.provider` (+`mollie_api_key`),
  `payment.transaction` (no new fields; 5 override methods).
- **Key relations:** tx → provider (`provider_code=='mollie'` gates every
  override); external keys — reference carried as the `?ref=` URL param
  (`_extract_reference → data['ref']`), `provider_reference == Mollie payment id`
  (used to re-fetch `GET /payments/<id>`).

## 3. Behavioral Notes (code-read — the metadata gap)
- **Create / redirect:** `_get_specific_rendering_values` →
  `_mollie_prepare_payment_request_payload` (description, amount in
  `CURRENCY_MINOR_UNITS` decimals, locale clamped to `const.SUPPORTED_LOCALES`,
  method via `const.PAYMENT_METHODS_MAPPING` — card→creditcard, p24→przelewy24,
  sepa_direct_debit→directdebit, etc., `redirectUrl`/`webhookUrl` both carrying
  `?ref=`) → `POST /payments`. Stores `provider_reference = payment_data['id']`,
  then hands the hosted `_links.checkout.href` (+ split-out query params) to the
  QWeb `redirect_form` (method=get auto-submit).
- **Re-fetch-by-id verification:** Mollie posts only an opaque payment `id`; the
  Odoo reference rides in `?ref=`. **Neither the webhook nor the return body is
  trusted** — `_verify_and_process` re-fetches `GET /payments/<provider_reference>`
  over the Bearer key and only then `_process('mollie', verified_data)`.
  Authenticity comes from the trusted API re-fetch, **not** an HMAC/checksum.
- **Outbound auth:** no `requests` import; HTTP delegated to
  `payment.provider._send_api_request`. `_build_request_url` →
  `https://api.mollie.com/v2/<endpoint>`; `_build_request_headers` →
  `Authorization: Bearer <mollie_api_key>` + a Mollie partner `User-Agent`;
  `_parse_response_error` → `response.json()['detail']`. Single key, **no**
  separate webhook secret.
- **Status mapping (`_apply_updates`):** `pending`/`open`→pending;
  `authorized`→authorized; `paid`→done; `expired`/`canceled`/`failed`→canceled;
  else→error. For `creditcard` it back-resolves the brand via
  `details.cardLabel`.

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **Outbound**
server-to-server REST to `api.mollie.com/v2` — `POST /payments` (create hosted
payment) and `GET /payments/<id>` (re-fetch authoritative status) — authenticated
by HTTP **Bearer** with the single API key. **No client-side SDK**: card data is
entered on Mollie's own hosted checkout after redirect (the module ships no
`static/src`, only description icons), keeping PCI scope with Mollie. **Inbound**
settlement via a webhook + redirect-return, both re-fetching by id.
`uses_api_keys=true`; no python SDK (HTTP via the parent engine).

## 5. Frontend (gap #3)
**Empty.** `extract_frontend.py` reports `present=false`: 0 JS, 0 OWL components,
0 registry adds, 0 patches, no asset bundles. The only template is the
server-side QWeb `redirect_form` that auto-submits the browser to Mollie's hosted
checkout. The browser-side acquirer interaction happens on Mollie's page, not in
Odoo-shipped JS.

## 6. Business Architecture
- **Capabilities (inferred):** accept European card / local methods via Mollie
  hosted checkout (cards, Apple Pay, Bancontact/KBC-CBC, iDEAL, Przelewy24, SEPA,
  bank transfer…); async settlement via webhook + return; multi-currency
  (~30 in `const.SUPPORTED_CURRENCIES`); locale-aware checkout.
- **Value streams (inferred):** Collect-Payment (redirect → re-fetch),
  Confirm-Settlement (webhook → re-fetch → status map), Settle (`paid` →
  `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction (no
  payment.token).
- **Organization (auto):** no own groups; `mollie_api_key` gated by
  `base.group_system`.
- **Policies (inferred):** notification trust by re-fetch (no signature);
  bounded currencies/locales; minor-unit amount formatting; single Test/Live key.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Mollie's European
  payment network (network promotion/contract mgmt = the API key + method/locale
  enablement; service provisioning = create/confirm the Mollie payment;
  infrastructure operation = api.mollie.com link + webhook/return re-fetch loop).
  Inherits the parent `payment` engine's model exactly. Mirrors siblings
  payment_stripe / payment_xendit (network/support).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted redirect via Payments API v2; webhook + return settlement
  (both re-fetch by id, no signature); multi-currency; locale-aware checkout;
  auto provider setup/teardown via the init hooks.
- **Common gaps:** **no tokenization**, **no manual capture/void**, **no
  in-module refund** (all README 'Not implemented'); no self-onboarding (manual
  API key); webhook needs a public HTTPS URL; authenticity rests on the
  Bearer-authenticated re-fetch + a correct `provider_reference`; currency/locale
  bounded.
- **Open questions:** full API payloads; runtime state/method-mix distribution
  and how often the interim `authorized` state occurs; how refunds/chargebacks
  are handled operationally; whether instances rely on the webhook vs the return
  route (both re-fetch the same payment).
