# payment_authorize — Reverse-Engineering Brief

**Module:** `payment_authorize`
**Full name:** Payment Provider: Authorize.Net
**Odoo version:** 19.0
**Category:** Accounting/Payment Providers
**LOC (Python):** 1,119
**Tier:** deep (≥3 code-read behavioral notes)

---

## 1. Purpose and Scope

`payment_authorize` is the Odoo adapter for the **Authorize.Net** payment acquirer, covering merchants in the **US, Australia, and Canada**. It is a pure `_inherit`-only extension of the `payment` engine — no new top-level models, no own ORM tables — that plugs the Authorize.Net XML/JSON API into Odoo's provider/transaction/token state machine.

The module supports:
- **Credit/debit card** acceptance (Visa, Mastercard, Amex, Discover) via client-side Accept.js tokenization (SAQ A-EP)
- **ACH/eCheck bank-account** acceptance via the same Accept.js inline form
- **Manual authorize-then-capture** split (`support_manual_capture='full_only'`)
- **Full refunds** with a stateful void-or-refund decision (`support_refund='full_only'`)
- **Saved-payment-method tokenization** using Authorize.Net Customer Profiles (`support_tokenization=True`)

---

## 2. IT Architecture

### Models inherited

| Model | New fields |
|---|---|
| `payment.provider` | `authorize_login`, `authorize_transaction_key` (system-only), `authorize_signature_key` (system-only), `authorize_client_key`; `code` selection_add `'authorize'` |
| `payment.token` | `authorize_profile` (Authorize.Net `customerProfileId`) |
| `payment.transaction` | none (9 method overrides) |

### Routes

| Path | Auth | Type | Purpose |
|---|---|---|---|
| `/payment/authorize/payment` | public | jsonrpc | Receive Accept.js opaqueData nonce, row-lock tx, create/capture on Authorize.Net, process response |

### External integration

All Authorize.Net API calls go through `AuthorizeAPI` (`models/authorize_request.py`) using the **Python `requests` library directly** (not via the payment engine's `_send_api_request`). The endpoint URL switches at runtime:
- **Live:** `https://api.authorize.net/xml/v1/request.api`
- **Sandbox:** `https://apitest.authorize.net/xml/v1/request.api`

Every request body includes a `merchantAuthentication` block: `{name: authorize_login, transactionKey: authorize_transaction_key}`.

A parallel **client-side channel** uses the **Accept.js** SDK (loaded lazily from `js.authorize.net` or `jstest.authorize.net`) to tokenize card/bank details in the browser — card numbers never reach the Odoo server (SAQ A-EP PCI scope).

---

## 3. Behavioral Notes (code-read)

### 3.1 AuthorizeAPI._make_request: direct requests.post with merchantAuthentication

All Authorize.Net API calls route through `AuthorizeAPI._make_request`. The URL is set in `__init__` based on `provider.state`. Every request body wraps a `merchantAuthentication` block. The raw `requests.post` is used with a 60-second timeout; error detection reads `messages.resultCode=='Error'` plus `transactionResponse.errors`. This dual-URL test/live pattern and the raw `requests` usage are invisible from field metadata.

### 3.2 authorize vs auth_and_capture split, plus billTo / profile data routing

Both the inline-form path (`_authorize_create_transaction_request`) and the off-session token path (`_send_payment_request`) branch on `provider.capture_manually`: `True` → `authOnlyTransaction` (authorized state); `False` → `authCaptureTransaction` (done state). Validation always uses `authOnlyTransaction`. For tokens, `_prepare_tx_data` builds a `profile` block (`customerProfileId`/`paymentProfileId`); for new card/ACH it uses `payment.opaqueData`. A `billTo` block (partner name/address, length-capped) is included only for non-profile requests. `_apply_updates` decodes `x_response_code`/`x_type` to drive the state machine: `auth_capture` → `_set_done`; `auth_only` → `_set_authorized` (then `_void` for validation); `void` → `_set_done` (refund/validation) or `_set_canceled`; `refund` → `_set_done` + trigger cron; code `2` → `_set_canceled`; code `4` → `_set_pending`; else → `_set_error`.

### 3.3 Stateful refund-or-void in _send_refund_request

`_send_refund_request` first calls `getTransactionDetailsRequest` to fetch the source transaction's current `transactionStatus`. The status is matched against `const.TRANSACTION_STATUS_MAPPING`: `voided` → `_set_canceled` (no API call); `refunded` → `_set_done` + trigger cron; `authorized` (not yet settled) → `void()` instead of refund; `captured` (settled) → `refund()` (`refundTransaction` with masked `cardNumber` from tx details, `expirationDate='XXXX'`). The void path creates no child transaction.

### 3.4 Two-call Customer Profile creation for tokenization

After a successful charge with `tokenize=True`, `_extract_token_values` calls `AuthorizeAPI.create_customer_profile(partner, provider_reference)`. This makes two sequential calls: (1) `createCustomerProfileFromTransactionRequest` (merchantCustomerId = `'ODOO-{partner.id}-{uuid4()[:8]}'[:20]`); (2) `getCustomerPaymentProfileRequest` to retrieve the masked last-4 digits. Results: `authorize_profile` (→ `payment.token.authorize_profile`), `provider_ref` (→ `payment.token.provider_ref`), `payment_details` (last 4). Subsequent off-session charges re-use both IDs in the `profile` block.

### 3.5 Accept.js client-side tokenization + row-lock anti-concurrent pattern in the controller

`PaymentForm.prototype` is patched (JS): on 'authorize' selection, `_prepareInlineForm` loads Accept.js lazily. `_processDirectFlow` assembles `secureData` (authData with `apiLoginID`/`clientKey` + `cardData` or `bankData`) and calls `Accept.dispatchData()` to get a single-use `opaqueData` nonce. The nonce is POSTed to `/payment/authorize/payment` with an HMAC `access_token`. In the controller, `check_access_token` validates the token, then `SELECT FOR NO KEY UPDATE` locks the transaction row before `_authorize_create_transaction_request` — preventing the single-use nonce from being consumed twice by concurrent cron jobs.

---

## 4. Business Architecture

### Capabilities
1. Card payment (Visa/MC/Amex/Discover) via Accept.js inline tokenization (SAQ A-EP)
2. ACH/eCheck bank-account payment via Accept.js inline tokenization
3. Manual authorize-then-capture with separate `_send_capture_request` / `_send_void_request`
4. Stateful refund-or-void (full only)
5. Saved-card/ACH tokenization (Authorize.Net Customer Profiles) for off-session recurring charges
6. Merchant self-setup: `action_update_merchant_details` fetches `authorize_client_key` and available currencies from Auth.Net API

### Value streams
- **Collect-Payment (new card/ACH):** Accept.js tokenize → opaqueData nonce → `/payment/authorize/payment` (row-locked) → `auth_and_capture` or `authorize` → done/authorized
- **Collect-Payment (off-session token):** `_send_payment_request` with profile block → `auth_and_capture` or `authorize` → done/authorized
- **Authorize-then-Capture:** authorized → `_send_capture_request` → `priorAuthCaptureTransaction` → done
- **Refund:** `_send_refund_request` → `getTransactionDetails` → void or `refundTransaction` → done/canceled
- **Tokenize:** successful charge + tokenize flag → two Auth.Net API calls → `payment.token` vault

### Policies
- One currency per Authorize.Net account: `_limit_available_currency_ids` raises `ValidationError` if >1 currency is selected while enabled
- Validation amount = $0.01 (auth-only, then voided)
- Row-lock in controller prevents double-spend of single-use OTS nonce
- `authorize_transaction_key` and `authorize_signature_key` restricted to `base.group_system`

---

## 5. Classification

| Dimension | Value |
|---|---|
| Value model | **network** (Stabell & Fjeldstad mediating-technology: links payer to merchant via Authorize.Net card/ACH network) |
| Activity class | **support** (Accounting/Payment Providers; application=False) |
| APQC category | 9.0 Manage Financial Resources — 9.5 process payments / collect cash |

---

## 6. Fit-to-Standard Assessment

### What fits out of the box
- Inline card and ACH acceptance (US/AU/CA merchants) via Accept.js
- Authorize-then-capture workflow for ship-then-bill merchants
- Recurring / subscription billing via tokenized Customer Profiles
- Refund flow with automatic void-for-unsettled transactions

### Common gaps
- **Single currency only:** one Authorize.Net account handles one currency; multi-currency requires multiple provider records
- **No inbound webhook:** all state transitions are synchronous; Held-for-Review (`status_code=4`) maps to `pending` but is never auto-resolved
- **No partial capture/refund** (`full_only` support only)
- **`authorize_signature_key` stored but unused** in current code — no webhook signature verification is implemented
- **Accept.js CDN dependency** requires internet access during checkout

---

## 7. Open Questions

1. `authorize_signature_key` is stored but never used for any signing or verification — is a webhook/Silent Post notification path planned, or is this field legacy?
2. Held-for-Review (`x_response_code='4'`) maps to `_set_pending` but nothing resolves it automatically; what is the operational process?
3. How multi-currency merchants configure this (multiple provider records) given the single-currency constraint.
4. Whether the `authorize_client_key` fetch (`action_update_merchant_details`) is expected to be run manually by the admin on setup, or triggered automatically.

---

## 8. Provenance

- Facts: `doc/revres/facts/payment_authorize.facts.json`
- Frontend: `doc/revres/frontend/payment_authorize.frontend.json`
- Source read: `models/payment_provider.py`, `models/payment_transaction.py`, `models/payment_token.py`, `models/authorize_request.py`, `controllers/main.py`, `const.py`, `static/src/interactions/payment_form.js`
- Odoo version: 19.0
