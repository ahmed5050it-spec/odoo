# payment_asiapay — Architecture Brief

> Payment Provider: AsiaPay — an acquirer adapter that links an Odoo merchant to
> AsiaPay, the Hong-Kong PSP operating the PayDollar / PesoPay / SiamPay / BimoPay
> brands across most of Asia. `_inherit`-only over the `payment` engine: no own
> models, no own ACL, 4 added provider fields. **Hosted-redirect only** — no
> server-to-server API, no tokenization, webhook-only settlement. Odoo 19.0,
> `version 1.0`, LGPL-3.

## 1. Summary
payment_asiapay is a concrete realization of the generic `payment` engine for
AsiaPay. It adds the `asiapay` provider code plus four credential fields (brand,
merchant id, secure-hash secret, secure-hash **function**) and overrides the
transaction/controller hooks to drive a single flow: a **hosted-redirect payForm**
— Odoo builds a signed hidden-field form that the browser auto-POSTs to one of
four AsiaPay brand hosts; the buyer pays on AsiaPay; AsiaPay notifies Odoo's
webhook (the `/return` route is a deliberate no-op). There is **no outbound
REST/API-key channel** and **no card data in Odoo**. A distinctive trait: the
signature **hash algorithm is account-configurable** (SHA1 / SHA256 / SHA512). It
is a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. Structure
- **Application:** AsiaPay/PayDollar acquirer adapter; inherits `payment.provider`
  / `payment.transaction` (no `payment.token` — no tokenization).
- **Models:** `payment.provider` (+`asiapay_brand` [paydollar/pesopay/siampay/
  bimopay], `asiapay_merchant_id`, `asiapay_secure_hash_secret`,
  `asiapay_secure_hash_function` [sha1/sha256/sha512]; 4 methods),
  `payment.transaction` (no new fields; 5 override methods).
- **Routes:** `/payment/asiapay/return` (http GET, **no-op**),
  `/payment/asiapay/webhook` (http POST, csrf=False).
- **Views:** 1 form inheritance (AsiaPay credentials) + the `redirect_form` QWeb
  template + `payment_provider_data.xml`. `xml_loc=67`.
- **Security:** 0/0/0; `asiapay_secure_hash_secret` gated by `base.group_system`
  (brand / merchant id / hash function ungrouped).

## 3. Frontend (gap #3)
**None.** 0 JS files, 0 OWL components, 0 registry adds, 0 patches. The entire
buyer interaction is the server-rendered `redirect_form` QWeb template
(`payment_asiapay_templates.xml`) whose hidden inputs (merchantId / orderRef /
currCode / payType / lang / payMethod / secureHash + successUrl/failUrl/cancelUrl)
auto-POST to the AsiaPay/PayDollar payForm. No browser SDK, no inline card form —
card/wallet data are collected on AsiaPay's hosted page, never in Odoo.

## 4. Behavior beyond metadata (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` builds the payForm payload —
  `merchant_id`, `amount`, `reference`, `currency_code` = the ISO code translated
  to AsiaPay's **numeric** code via `const.CURRENCY_MAPPING` (HKD→344, USD→840…),
  `mps_mode='SCP'`, `payment_type='N'`, `language` via
  `get_language_code(...)`→single-letter code (E/C/J…), `payment_method` via
  `const.PAYMENT_METHODS_MAPPING` (default `'ALL'`) — signs it and adds `api_url`
  (per-brand host, live vs sandbox by `provider.state`). **No S2S API call.**
- **Signature (`_asiapay_calculate_signature`):** a fixed **ordered** key list
  (`const.SIGNATURE_KEYS`: outgoing `[merchant_id, reference, currency_code,
  amount, payment_type]`; incoming `[src, prc, successcode, Ref, PayRef, Cur, Amt,
  payerAuth]`) + the secret, joined with `|`, hashed with
  `hashlib.new(asiapay_secure_hash_function)` — **SHA1/256/512 per account**
  (default sha1). Not an HMAC.
- **Inbound (asymmetric trust):** `/return` (GET) is a **no-op** (returns no
  authoritative data, AsiaPay has no fetch API) → just redirects to
  `/payment/status`. **All** settlement is the `/webhook` (POST):
  `_search_by_reference` (`_extract_reference`→`'Ref'`) then `_verify_signature`
  **before** `_process`; rejects (HTTP 403) on missing `secureHash` or failed
  `hmac.compare_digest`.
- **Status mapping (`_apply_updates`):** `provider_reference='PayRef'`;
  `successcode` `'0'`→done, `'1'`/other→error (with `prc`); missing→ValidationError.
  **No pending, no cancel** — binary success/failure.
- **Currency constraint (`_limit_available_currency_ids`):** `@api.constrains`
  enforces **at most one** available currency per non-disabled account and rejects
  currencies outside `const.CURRENCY_MAPPING`.

## 5. IT architecture
- **Services:** `/payment/asiapay/return` (GET, no-op → `/payment/status`),
  `/payment/asiapay/webhook` (POST, secureHash-verified, processes, returns
  `'OK'` — sole settlement path).
- **Data objects:** `payment.provider` (+4 fields), `payment.transaction`.
- **Key relations:** tx → provider (`provider_code=='asiapay'` gates every
  override); `asiapay_brand` → API host; `available_currency_ids` constrained to
  one; external keys `reference==orderRef/'Ref'`, `provider_reference=='PayRef'`.
- **External integration (gap #7):** `uses_api_keys=false`. Endpoints are the four
  per-brand payForm hosts (live + sandbox); reached purely by the browser POSTing
  the signed form. Authenticity rests on the secure-hash secret + the configured
  hash function, not a transport key. None of this is derivable from metadata.

## 6. Business architecture
- **Capabilities (inferred):** accept card/local-wallet payments via AsiaPay
  hosted redirect; multi-brand acquiring (PayDollar/PesoPay/SiamPay/BimoPay); wide
  Asian method coverage (Alipay, WeChat Pay, FPS, Octopus, GCash, Maya, DANA, OVO,
  QRIS, UnionPay…); configurable-hash signed-redirect settlement;
  single-currency-per-account.
- **Value streams (inferred):** Collect-Payment (redirect → signed webhook →
  `_process`), Settle (`'0'`→`_set_done`→downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; hash secret gated by `base.group_system`.
- **Policies (inferred):** webhook signature authenticity (403 on mismatch);
  non-authoritative return route; single-currency + allow-list constraint;
  35-char singularized references.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. Links the
  payer and merchant by connecting the merchant to AsiaPay's Asian payment network
  (network promotion/contract mgmt = brand + merchant id + hash secret/algorithm +
  single-currency enablement; service provisioning = build/sign/confirm the
  payForm redirect; infrastructure operation = per-brand host handoff + webhook
  loop, the return route a deliberate no-op). Inherits the parent `payment`
  engine's model exactly. Mirrors siblings payment_stripe / payment_xendit
  (network/support) — like APS, a redirect-only acquirer (no S2S API, no
  tokenization), distinguished by multi-brand hosts, account-configurable hash,
  and webhook-only settlement.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-redirect payForm (per-brand host); wide Asian method
  routing; configurable-hash signed-redirect integrity + verified settlement;
  webhook-only settlement; single-currency-per-account (~22 currencies).
- **Common gaps:** no S2S API (redirect-only); no tokenization/saved cards; no
  manual capture / void / in-module refund; no pending/cancel state (binary
  success/error); `/return` is a no-op so a reachable webhook URL is mandatory;
  one currency per account; downstream reconciliation lives elsewhere.
- **Open questions:** full payForm/datafeed field sets; runtime state/brand/hash
  distribution; how refunds/cancellations are handled operationally; whether
  instances reliably register the webhook datafeed (the only authoritative path).
