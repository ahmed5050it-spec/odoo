# pos_adyen — Reverse-Engineering Brief

**Module:** pos_adyen  
**Category:** Sales/Point of Sale  
**Odoo version:** 19.0  
**Auto-install:** no  
**Tier:** deep (≥3 code-read behavioral notes)

---

## What it does in one sentence

`pos_adyen` integrates Odoo POS with Adyen physical payment terminals using the Nexo Retailer Protocol (cloud async architecture): the POS JS client sends payment requests through an Odoo CORS proxy, Adyen notifies Odoo via a public webhook, and a WebSocket bus event resolves the pending payment Promise in the POS frontend.

---

## Architecture

### Python side (454 LOC, 3 model extensions, 1 route)

**`pos.payment.method` extension** — the core of the integration:

- Fields: `adyen_api_key` (Char, erp_manager only), `adyen_terminal_identifier` (Char, e.g. `P400Plus-123456789`), `adyen_test_mode` (Boolean), `adyen_latest_response` (Char — async notification buffer), `adyen_event_url` (Char, readonly, computed from base URL).
- **`proxy_adyen_request`** — Odoo acts as a CORS proxy because Adyen's Terminal API does not have CORS headers. The method validates incoming request data against a strict allowlist of permitted shapes (payment, cancel/abort, and optionally capture/adjust from extended modules) using a recursive `_is_valid_adyen_request_data` validator with an `UNPREDICTABLE_ADYEN_DATA` sentinel for dynamic fields. For payment requests, it injects a `pos_hmac` HMAC (via `odoo.tools.hmac`, scope `pos_adyen_payment`, message tuple `(SaleID, ServiceID, POIID, TransactionID)`) into `SaleToAcquirerData` before forwarding to `https://terminal-api-{live|test}.adyen.com/async`.
- **`_proxy_adyen_request_direct`** — sends the POST request with `x-api-key` header, handles 401 as a structured error dict, and passes the raw `requests.Response` JSON back to the caller. Returns `True` on `'ok'` text response (Adyen's acknowledge).
- **`_is_write_forbidden` override** — excludes `adyen_latest_response` from the write-forbidden field set, so the webhook handler can buffer notifications even when the payment method record is otherwise locked during a POS session.
- **`_check_adyen_terminal_identifier`** — `@api.constrains` validator enforcing unique terminal identifiers across all companies (sudo search); raises `ValidationError` with a different message depending on whether the conflict is within or across companies.

**`pos.config` extension** — adds `adyen_ask_customer_for_tip` (Boolean) with a `@api.constrains` validator that requires `tip_product_id` and `iface_tipproduct` to be configured when tipping is enabled.

**`res.config.settings` extension** — exposes `pos_adyen_ask_customer_for_tip` as a proxy field to `pos.config`.

### Webhook controller (`/pos_adyen/notification`, auth=public)

Receives asynchronous `SaleToPOIResponse` messages from Adyen's cloud:

1. Validates `ProtocolVersion=3.0`, `MessageClass=Service`, `MessageType=Response`, `MessageCategory=Payment`.
2. Looks up `pos.payment.method` by `POIID` (terminal identifier).
3. Extracts `metadata.pos_hmac` from `AdditionalResponse` (URL-encoded query string), validates it via `consteq` against the re-computed HMAC.
4. Strips the HMAC from the payload (security: prevent replay with Odoo's own HMAC).
5. Writes the sanitized JSON to `adyen_latest_response`, then calls `pos_session.config_id._notify('ADYEN_LATEST_RESPONSE', config_id)` to push a WebSocket event to the POS frontend.
6. Returns `'[accepted]'` — required by Adyen's cloud guarantee protocol regardless of processing result.

### JS/Frontend side (4 files, 3 patches)

**`PaymentAdyen`** (extends `PaymentInterface`, registered as `'adyen'` via `register_payment_method`):

- `sendPaymentRequest` → `_adyenPay` → builds `SaleToPOIRequest` with `MessageCategory=Payment`, includes `tenderOption=AskGratuity` in `SaleToAcquirerData` when tipping is enabled → calls `proxy_adyen_request` via ORM RPC.
- `_adyenHandleResponse` — on Adyen's async `'ok'` acknowledgement, sets payment line status to `'waitingCard'` and returns `waitForPaymentConfirmation()` (a Promise stored in `paymentLineResolvers[line.uuid]`).
- `handleAdyenStatusResponse` — called when the WebSocket event fires; fetches `adyen_latest_response` via `get_latest_adyen_status` ORM call; validates `ServiceID` matches pending line's `terminalServiceId`; on success, sets receipt info (cashier + customer receipts from `PaymentReceipt`), `transaction_id` (pspReference), `card_type`, `cardholder_name`; handles tip amount via `pos.setTip()`.
- `sendPaymentCancel` → `_adyenCancel` → sends `AbortRequest` with the previous `ServiceID`.

**`PosStore.prototype` patch** — in `setup`, subscribes to `ADYEN_LATEST_RESPONSE` WebSocket channel via `data.connectWebSocket`; on event, delegates to `handleAdyenStatusResponse` on the pending Adyen payment line's terminal object.

**`PaymentScreen.prototype` patch** — on mount, recovers the `most_recent_service_id` from any pending (non-done, non-pending-status) Adyen payment line to handle browser refresh during payment.

**`PosPayment.prototype` patch** — adds `setTerminalServiceId(id)` to store the `ServiceID` on the payment line for matching with webhook responses.

---

## Async payment flow (end-to-end)

```
Cashier clicks Pay
  → PaymentAdyen._adyenPay()
  → ORM RPC: proxy_adyen_request (with HMAC injection)
  → Adyen terminal-api-live.adyen.com/async  (returns 'ok')
  → line.status = 'waitingCard'
  → Promise stored in paymentLineResolvers[uuid]

Customer taps card on terminal
  → Adyen → POST /pos_adyen/notification (HMAC validated)
  → adyen_latest_response updated
  → pos_bus ADYEN_LATEST_RESPONSE event
  → PosStore WebSocket handler
  → handleAdyenStatusResponse()
  → ORM RPC: get_latest_adyen_status
  → Promise resolved → payment line marked done
```

---

## Value model & APQC

**Value model:** chain — closes the payment step of the POS revenue chain, converting a completed order into an authorized card transaction.  
**APQC:** 3.0 Market and Sell Products and Services.

---

## Key behavioral facts not visible in metadata

1. **CORS proxy with shape whitelist + HMAC injection**: `proxy_adyen_request` is not a transparent passthrough — it validates request structure against a strict allowlist and injects a server-computed HMAC into every payment request before forwarding.
2. **Public webhook with HMAC validation**: `/pos_adyen/notification` is `auth=public` but cryptographically authenticated via `consteq` HMAC check; the HMAC is stripped from the stored payload before writing.
3. **Split async Promise**: the POS payment is not request-response — JS stores a Promise in `paymentLineResolvers`, which is resolved only when the WebSocket event fires from the webhook; browser refresh recovery is handled by the `PaymentScreen` patch.
4. **Tip flow spans three layers**: config constraint (Python), `tenderOption=AskGratuity` in request (JS), `TipAmount` extraction and `pos.setTip()` call (JS response handler).
5. **`_is_write_forbidden` carve-out**: `adyen_latest_response` is explicitly excluded from write-forbidden fields so the webhook can buffer its notification even during a locked POS session.

---

## Fit-to-standard

| Capability | Coverage |
|---|---|
| Cloud async Adyen Terminal API (Nexo 3.0) | Standard |
| Payment cancel (MerchantAbort) | Standard |
| Customer tip on terminal | Standard (requires tip product config) |
| Test/live environment switching | Standard |
| Local terminal API (LOCALHOST) | Gap — not supported |
| Offline/fallback on Adyen cloud outage | Gap — none |
| Refund via terminal | Gap — out of scope |
| Webhook URL auto-registration in Adyen portal | Gap — informational only (copy-paste) |

---

## Open questions

1. Does `pos_adyen` support a local terminal communication mode (Adyen LOCALHOST), or is it cloud-only?
2. What happens if `adyen_latest_response` holds a stale response from a previous POS session when a new session starts — is it cleared on session open?
3. Is there a refund path through the terminal, or are refunds entirely handled outside Odoo (Adyen dashboard / manual)?
