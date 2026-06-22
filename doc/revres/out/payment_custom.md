# payment_custom — Reverse-Engineering Brief

**Module:** `payment_custom`
**Full name:** Payment Provider: Custom Payment Modes
**Odoo version:** 19.0
**Category:** Accounting/Payment Providers
**LOC (Python):** 328
**Tier:** deep (≥3 code-read behavioral notes)

---

## 1. Purpose and Scope

`payment_custom` is Odoo's built-in adapter for **offline / manual payment flows** — primarily **wire transfers** (bank transfers). Unlike real online acquirers, it makes zero API calls to any external payment network. Its role is to:

1. Show the customer bank-account wire-transfer instructions (dynamically assembled from `account.journal` bank records)
2. Record a **payment intent** in Odoo as a `payment.transaction` in `pending` state
3. Give the accountant a reconciliation communication reference (invoice payment reference or sale order reference)

The module is deliberately minimal: the actual settlement happens outside Odoo when the bank transfer arrives, and the accountant reconciles it manually via the accounting module.

---

## 2. IT Architecture

### Models inherited

| Model | New fields |
|---|---|
| `payment.provider` | `code` selection_add `'custom'`; `custom_mode` (Selection: `wire_transfer`); `qr_code` (Boolean); DB constraint enforces `custom_mode` not null iff `code='custom'` |
| `payment.transaction` | none (6 method overrides) |

### Routes

| Path | Auth | Type | Purpose |
|---|---|---|---|
| `/payment/custom/process` | public | http POST, csrf=False | Receives the submitted payment form; calls `_process('custom', post)` → `_set_pending`; redirects to `/payment/status` |

### External integration

None. `uses_api_keys=False`, zero endpoints, zero outbound HTTP calls. The only cross-module dependency at runtime is an **optional check** for the `account_payment` module (to look up `account.journal` bank accounts for the pending message) — but `account_payment` is not a declared `depends`.

---

## 3. Behavioral Notes (code-read)

### 3.1 Always-pending flow: _get_specific_rendering_values + _apply_updates + _extract_amount_data

`payment_custom` implements a deliberate no-op payment flow. `_get_specific_rendering_values` returns only `{api_url: '/payment/custom/process', reference: self.reference}` — no redirect to any payment gateway. `CustomController.custom_process_transaction` (csrf=False, public, POST) does nothing except call `payment.transaction.sudo()._process('custom', post)` then redirect to `/payment/status`. `_apply_updates` unconditionally calls `self._set_pending()` regardless of the POST data — the transaction always lands in `pending`, never `done`. `_extract_amount_data` returns `None` for `provider_code=='custom'`, instructing the payment engine to skip amount validation entirely (there is no API response to validate an amount against). This means no funds movement is tracked in Odoo, no API call is ever made, and the transaction remains `pending` indefinitely from this module's perspective.

### 3.2 PaymentPostProcessing JS patch: 'pending' treated as terminal for custom providers

The standard payment post-processing page polls the transaction state until a terminal state (`done`/`error`/`canceled`) is reached. For `custom` providers, transactions stay in `pending` forever. Without the JS patch, the polling would never stop. `static/src/interactions/post_processing.js` patches `PaymentPostProcessing.getFinalStates`: when `providerCode === 'custom'`, `'pending'` is added to the `finalStates` set, so the post-processing widget immediately redirects to the landing route rather than polling. This client-side patch is the single thing that makes the offline payment UX coherent, and it is entirely invisible from Python metadata.

### 3.3 action_recompute_pending_msg: dynamic bank-account HTML from account.journal

The wire-transfer pending message (shown to the customer after they submit) is dynamically built from the company's bank accounts. `action_recompute_pending_msg` checks whether the `account_payment` module is installed (`ir.module.module._get('account_payment').state == 'installed'`); if yes, it queries `account.journal` records of `type='bank'` scoped to the provider's company, collects `bank_account_id.display_name` values, and renders an HTML block listing them under a "Please use the following transfer details" header. `_transfer_ensure_pending_msg_is_set` auto-triggers this when `pending_msg` is empty. The `create()` override nullifies `pending_msg` immediately after creation for `wire_transfer` providers so it is freshly computed on first use. The dependency on `account_payment` and the dynamic bank-account lookup are invisible from field/model metadata.

### 3.4 _get_communication: invoice/sale reference for bank reconciliation

`_get_communication` builds the reference string the customer should include in their bank transfer. Priority: (1) `invoice_ids[0].payment_reference` if the transaction has linked invoices; (2) `sale_order_ids[0].reference` if linked to sale orders; (3) `self.reference` as fallback. This communication reference is shown in the pending message so the accountant can match the incoming bank transfer to the correct Odoo document. `_get_sent_message` returns a custom "The customer has selected {provider_name} to make the payment." message. `_log_received_message` excludes custom transactions (filtered before calling `super`) because custom providers never actually receive an external notification — logging a "received" chatter message would be misleading for an offline flow.

### 3.5 DB constraint + _get_provider_domain + custom_mode extensibility design

A PostgreSQL CHECK constraint (`_custom_providers_setup`: `CHECK(custom_mode IS NULL OR (code = 'custom' AND custom_mode IS NOT NULL))`) enforces that only `code='custom'` providers may have a non-null `custom_mode`, and that every `custom` provider must have one. `_get_provider_domain` is overridden: when `provider_code=='custom'` and a `custom_mode` keyword is provided, it ANDs a `('custom_mode', '=', custom_mode)` domain so callers can locate a specific variant (e.g. wire_transfer only). `_get_removal_values` nullifies `custom_mode` when a provider is removed/reset. This design allows future `custom_mode` values to be added as Selection additions without schema changes. Currently only `'wire_transfer'` exists in `const.DEFAULT_PAYMENT_METHOD_CODES` and the Selection definition.

---

## 4. Business Architecture

### Capabilities
1. Accept wire-transfer/bank-transfer payments with customer-facing instructions listing company bank accounts
2. Generate a communication/reference string for bank reconciliation (invoice reference > sale order reference > tx reference)
3. Display QR codes on the wire-transfer instructions page (`qr_code` flag)
4. Support future custom payment modes via extensible `custom_mode` Selection
5. Offline-flow UX: treat `pending` as terminal in the post-processing page (no polling)

### Value streams
- **Collect-Payment (wire transfer):** customer selects Custom provider → bank account instructions shown (with optional QR) → customer submits form → POST `/payment/custom/process` → `_set_pending` → `/payment/status` (pending = final per JS patch) → accountant matches incoming bank transfer using communication reference → manual reconciliation in `account_payment`
- **Reconcile:** `_get_communication` returns invoice/sale reference → included in transfer → accountant matches in bank statement import

### Policies
- Transaction always lands in `pending`: `_apply_updates` unconditionally calls `_set_pending`; no `done`/`error`/`canceled` path
- Amount validation skipped: `_extract_amount_data` returns `None`
- DB constraint: `custom_mode` must be set iff `code='custom'`
- `pending_msg` auto-recomputed from `account.journal` bank accounts when empty; `create()` nullifies it to force fresh compute
- Chatter "received" message suppressed for custom transactions
- Post-processing JS patch adds `'pending'` to `finalStates` for custom provider

---

## 5. Classification

| Dimension | Value |
|---|---|
| Value model | **network** (Stabell & Fjeldstad mediating-technology: mediates between payer and merchant via offline bank transfer instructions; same structural role as online acquirers in the payment engine, but degenerate — no real-time external network) |
| Activity class | **support** (Accounting/Payment Providers; application=False) |
| APQC category | 9.0 Manage Financial Resources — 9.5 process payments / collect cash (offline wire-transfer collection) |

---

## 6. Fit-to-Standard Assessment

### What fits out of the box
- Wire-transfer / bank-transfer payment intent recording for B2B invoicing
- Dynamic bank-account instructions from `account.journal` (when `account_payment` is installed)
- Bank-reconciliation communication reference tied to invoice or sale order
- Extensible for additional offline payment modes (Selection addition, no schema change)

### Common gaps
- **No automatic settlement:** transaction stays `pending` indefinitely; accountant must manually mark it paid via bank statement reconciliation
- **No real-time confirmation:** no webhook, no callback; customer experience ends at the "pending" status page
- **`pending_msg` can become stale** if bank accounts change after provider configuration; requires re-running `action_recompute_pending_msg`
- **QR code rendering** depends on upstream `payment` QWeb templates and `account_payment` QR generation; this module only sets the flag
- **Only one `custom_mode`** currently (`wire_transfer`); other offline modes (check, cash) are not implemented

---

## 7. Open Questions

1. How does the accountant operationally close a pending wire-transfer transaction — is there a manual "mark as paid" action in `account_payment`, or does it happen via bank statement import and reconciliation?
2. Which QWeb template consumes the `qr_code` flag and what QR format is generated (SEPA QR, Swiss QR bill, generic URL)?
3. Are additional `custom_mode` values (e.g. `'check'`, `'cash_on_delivery'`) planned? The extensibility design is in place.
4. Is there a cron or server action to keep `pending_msg` in sync when bank accounts change?

---

## 8. Provenance

- Facts: `doc/revres/facts/payment_custom.facts.json`
- Frontend: `doc/revres/frontend/payment_custom.frontend.json`
- Source read: `models/payment_provider.py`, `models/payment_transaction.py`, `controllers/main.py`, `const.py`, `static/src/interactions/post_processing.js`
- Odoo version: 19.0
