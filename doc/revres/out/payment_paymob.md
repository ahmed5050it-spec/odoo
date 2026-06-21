# payment_paymob — Architecture Brief

> Payment Provider: Paymob — an acquirer adapter that links an Odoo merchant to
> Paymob, the Egyptian/MENA PSP (Egypt, UAE, Oman, Pakistan, Saudi Arabia: card,
> mobile wallet, kiosk, BNPL/instalments). `_inherit`-only over the `payment`
> engine: no own models, no own ACL, 5 added provider fields. Odoo 19.0,
> `version 1.0`, LGPL-3.

## 1. Overview
payment_paymob is a concrete realization of the generic `payment` engine for the
Paymob PSP. It adds the `paymob` provider code plus five credential fields
(account country, public key, secret key, HMAC key, API key), and overrides the
transaction/controller hooks to drive a **hybrid flow**: a real server-to-server
**Intention** call (`/v1/intention/`) mints a `client_secret`, then the browser
is GET-redirected to Paymob's **hosted Unified Checkout** for every method. It is
a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. IT Architecture
- **Application:** Paymob acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (no own models/views).
- **Services (routes):** `/payment/paymob/return` (http GET, HMAC-SHA-512
  verified, draft→state then `/payment/status`), `/payment/paymob/webhook`
  (http POST, csrf=False, reads JSON `obj`, normalizes, HMAC-SHA-512 verified).
- **Data objects:** `payment.provider`
  (+paymob_account_country_id/public_key/secret_key/hmac_key/api_key),
  `payment.transaction` (no new fields; 6 override methods).
- **Key relations:** tx → provider (`provider_code=='paymob'` gates every
  override); `paymob_account_country_id → res.country` (drives the API host and
  the single currency); external keys `special_reference/merchant_order_id==
  reference`, `provider_reference==intention id`.

## 3. Behavioral Notes (code-read — the metadata gap)
- **Create + redirect:** `_get_specific_rendering_values` →
  `_paymob_prepare_payment_request_payload` → POST `/v1/intention/`
  (`is_client_request=True` → `Authorization: Bearer paymob_secret_key`) → stores
  `provider_reference=id`, reads `client_secret`, returns
  `api_url={base}/unifiedcheckout/` + `url_params={publicKey, clientSecret}`; the
  QWeb `redirect_form` (method=`get`) auto-submits the browser to Paymob's hosted
  checkout.
- **Outbound auth / endpoints:** `_build_request_url` →
  `https://{API_MAPPING[account_country]}.paymob.com` (uae/accept/oman/pakistan/
  ksa); `_build_request_headers` sends `Bearer paymob_secret_key` for client
  requests, else a short-lived OAuth token minted by `_paymob_fetch_access_token`
  (POST `/api/auth/tokens` with `paymob_api_key`). `action_sync_paymob_payment_methods`
  uses GET/PUT `/api/ecommerce/integrations[/{id}]` to align gateway
  `integration_name`s with Odoo methods. HTTP delegated to
  `payment.provider._send_api_request`.
- **Inbound verification:** both routes → `_search_by_reference` (via
  `_extract_reference` → `merchant_order_id`) → `_verify_signature` **before**
  `_process`. The webhook first runs `_normalize_response` (flattens the nested
  `obj` onto `const.SIGNATURE_FIELDS`). `_compute_signature` **concatenates the 20
  `SIGNATURE_FIELDS` values in their fixed list order** (no separator, missing →
  `'false'`) then `hmac.new(paymob_hmac_key, …, sha512).hexdigest()`; mismatch →
  HTTP 403 Forbidden (constant-time `compare_digest`). This is **HMAC SHA-512**,
  list-ordered (not sorted, not SHA-256).
- **Status mapping (`_apply_updates`):** `pending=='true'`→pending;
  `success=='true'`→done; else→error (`data.message`). **No cancel branch.**
- **Currency:** exactly one currency per account, pinned to the account country
  via `const.CURRENCY_MAPPING` (AED/EGP/OMR/PKR/SAR) — enforced by
  `_inverse_paymob_account_country_id` + the `_check_available_country_currency_ids`
  constraint.

## 4. External Integration (gap #7)
A real external acquirer link, invisible to Python metadata. **Outbound** server-
to-server REST to the per-country `{prefix}.paymob.com` — `/api/auth/tokens`
(OAuth from `paymob_api_key`), `/v1/intention/` (Bearer secret key), and
`/api/ecommerce/integrations` (method sync) — then a **browser GET redirect** to
`{base}/unifiedcheckout/` (publicKey + clientSecret) where card/wallet data are
collected on Paymob's hosted page. **Inbound** settlement via an
HMAC-SHA-512-verified return route plus a JSON webhook. `uses_api_keys=true`; no
python or browser SDK (HTTP via the parent engine). Unlike pure-redirect
acquirers (APS, Buckaroo) Paymob makes a genuine S2S call; unlike Stripe/Xendit it
captures no card in Odoo and stores no token.

## 5. Frontend (gap #3)
0 JS files, 0 OWL components, 0 patches, no `web.assets_frontend` bundle. The
entire buyer interaction is the server-rendered `redirect_form` QWeb template
(`payment_paymob_templates.xml`) auto-submitting (GET) to Paymob's hosted Unified
Checkout. No browser SDK, no inline card form — nothing card-related runs in the
Odoo client.

## 6. Business Architecture
- **Capabilities (inferred):** accept Card via Paymob hosted Unified Checkout
  across Egypt/UAE/Oman/Pakistan/Saudi; MENA local methods (mobile wallet, kiosk,
  BNPL — valU/Aman/Souhoola/Forsa/Tabby/Tamara/Halan/Sympl/Contact/STC Pay/
  OmanNet/EasyPaisa/JazzCash); single-currency-per-account
  (AED/EGP/OMR/PKR/SAR); portal method sync.
- **Value streams (inferred):** Collect-Payment (Intention → hosted checkout →
  HMAC-verified return/webhook), Configure-Methods (sync gateways), Settle
  (`success` → `_set_done` → downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; only `paymob_secret_key` gated by
  `base.group_system` (HMAC/API/secret keys also password-masked).
- **Policies (inferred):** HMAC-SHA-512 callback authenticity (403 on mismatch);
  one currency per account pinned to country; minor-unit amounts; secret-vs-OAuth
  bearer split; no tokenization/capture/saved-card (filtered out at sync).
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. The module
  interconnects payer and merchant by linking the merchant to Paymob's MENA
  payment network (network promotion/contract mgmt = account country + keys +
  portal sync; service provisioning = S2S Intention + confirm signed feedback;
  infrastructure operation = `{prefix}.paymob.com` + hosted checkout + HMAC
  webhook loop). Inherits the parent `payment` engine's model exactly. Mirrors
  siblings payment_stripe / payment_xendit / payment_aps (network/support).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** S2S Intention then hosted-redirect Unified Checkout; MENA method
  routing; HMAC-SHA-512 signed-redirect settlement (return + webhook);
  single-currency-per-account; portal method sync.
- **Common gaps:** no tokenization/saved cards; no manual capture/authorize, no
  void; no in-module refund; no cancel-state mapping (falls through to error); no
  Apple/Google Pay; one currency per provider; webhook needs a public URL + a set
  HMAC key.
- **Open questions:** full Intention/Unified-Checkout payloads; runtime
  state/method-mix across the five countries; how refunds/cancellations are
  handled operationally; whether instances rely on the webhook vs the (also
  HMAC-verified) GET return route.
