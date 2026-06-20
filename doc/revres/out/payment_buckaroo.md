# payment_buckaroo — Architecture Brief

> Payment Provider: Buckaroo — an acquirer adapter that links an Odoo merchant to
> Buckaroo, the Dutch PSP covering several European countries (card, iDEAL,
> Bancontact, SOFORT, Klarna, SEPA Direct Debit…). `_inherit`-only over the
> `payment` engine: no own models, no own ACL, 2 added provider fields.
> **Hosted-redirect only** — no server-to-server API, no tokenization. Odoo 19.0,
> `version 2.0`, LGPL-3.

## 1. Summary
payment_buckaroo is a concrete realization of the generic `payment` engine for
Buckaroo. It adds the `buckaroo` provider code plus two credential fields (website
key, secret key) and overrides the transaction/controller hooks to drive a single
flow: a **hosted-redirect BPE gateway** — Odoo builds a signed hidden-field form
that the browser auto-POSTs to Buckaroo's HTML gateway; the buyer pays on
Buckaroo; Buckaroo returns the signed feedback to two routes. There is **no
outbound REST/API-key channel** (the `uses_api_keys=true` flag refers to the
**signing secret**, not a transport credential) and **no card data in Odoo**. It
is a finance/infrastructure support component, not an end-user app
(`application=false`).

## 2. Structure
- **Application:** Buckaroo acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (no `payment.token` — no tokenization).
- **Models:** `payment.provider` (+`buckaroo_website_key`, `buckaroo_secret_key`;
  4 methods), `payment.transaction` (no new fields; 4 override methods).
- **Routes:** `/payment/buckaroo/return` (http POST, csrf=False,
  save_session=False), `/payment/buckaroo/webhook` (http POST, csrf=False).
- **Views:** 1 form inheritance (website + secret key, shown only when
  `code=='buckaroo'`, secret password-masked) + the `redirect_form` QWeb template
  + `payment_provider_data.xml`. `xml_loc=47`.
- **Security:** 0/0/0; `buckaroo_secret_key` gated by `base.group_system` (website
  key ungrouped).

## 3. Frontend (gap #3)
**None.** 0 JS files, 0 OWL components, 0 registry adds, 0 patches. The entire
buyer interaction is the server-rendered `redirect_form` QWeb template
(`payment_buckaroo_templates.xml`) whose hidden inputs auto-POST to the Buckaroo
HTML gateway. No browser SDK, no inline card form — card/iDEAL/wallet data are
collected on Buckaroo's hosted page, never in Odoo.

## 4. Behavior beyond metadata (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` builds the BPE payload
  (`Brq_websitekey`, `Brq_amount`, `Brq_currency`, `Brq_invoicenumber`=reference,
  and **all four** result URLs `Brq_return/returncancel/returnerror/returnreject`
  set to the same return URL — each participates in the signature; plus
  `Brq_culture`), signs it into `Brq_signature`, and adds `api_url` (live
  `checkout.buckaroo.nl/html/` vs sandbox `testcheckout.buckaroo.nl/html/` by
  `provider.state`). **No S2S API call.**
- **Signature (`_buckaroo_generate_digital_sign`):** keeps only keys prefixed
  `add_`/`brq_`/`cust_` (case-insensitive); on **incoming** it URL-decodes values
  (`url_unquote_plus`) and **excludes** `brq_signature`; sorts pairs by lowercase
  key (lower-case required because `ord('A') < ord('_') < ord('a')`); concatenates
  `key=value` with no separator; appends `buckaroo_secret_key`; returns
  `sha1(...).hexdigest()`. **Fixed SHA-1, not an HMAC.**
- **Inbound (`return` POST + `webhook` POST):** both `_normalize_data_keys`
  (lower-case all keys) → `_search_by_reference` (`_extract_reference`→
  `brq_invoicenumber`) → `_verify_signature` **before** `_process`.
  `_verify_signature` recomputes over the **raw** data and rejects (HTTP 403
  Forbidden) on missing `brq_signature` or a failed `hmac.compare_digest`. Both
  routes are authenticated and authoritative — no separate verification GET.
- **Status mapping (`_apply_updates`):** `provider_reference` = first of the
  comma-separated `brq_transactions`; `int(brq_statuscode)` →
  `790/791/792/793`=pending, `190`=done, `890/891`=canceled, `690`=error
  (refused), `490/491/492`=error, else error. Distinct refused/error/cancel
  buckets.
- **Currency allow-list (`_get_supported_currencies`):** filtered to
  `const.SUPPORTED_CURRENCIES` = EUR/GBP/PLN/DKK/NOK/SEK/CHF/USD (8).

## 5. IT architecture
- **Services:** `/payment/buckaroo/return` (signed POST, processes,
  →`/payment/status`), `/payment/buckaroo/webhook` (signed push POST, processes,
  returns `''`).
- **Data objects:** `payment.provider` (+2 fields), `payment.transaction`.
- **Key relations:** tx → provider (`provider_code=='buckaroo'` gates every
  override); external keys `reference==brq_invoicenumber`,
  `provider_reference==first brq_transactions key`.
- **External integration (gap #7):** `uses_api_keys=true` but **misleading** — the
  key is a signing secret, not a transport credential; there is no authenticated
  S2S endpoint. Endpoints are the two BPE HTML gateways; reached purely by the
  browser POSTing the signed form. None of this is derivable from metadata.

## 6. Business architecture
- **Capabilities (inferred):** accept card/iDEAL/European-method payments via
  Buckaroo hosted redirect (Bancontact, Belfius, KBC, SOFORT, Przelewy24, EPS,
  Trustly, Klarna, in3, SEPA Direct Debit, PayPal…); signed-redirect settlement
  with no card data in Odoo; multi-currency (8 currencies).
- **Value streams (inferred):** Collect-Payment (redirect → signed return/push →
  `_process`), Settle (`190`→`_set_done`→downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; secret key gated by `base.group_system`.
- **Policies (inferred):** inbound signature authenticity (403 on mismatch);
  outbound `Brq_signature`; signature scoped to `add_`/`brq_`/`cust_` keys (excl.
  `brq_signature`, URL-decoded incoming); currency allow-list; all four result
  URLs signed.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. Links the
  payer and merchant by connecting the merchant to Buckaroo's European payment
  network (network promotion/contract mgmt = website key + signing secret +
  method/currency enablement; service provisioning = build/sign/confirm the BPE
  redirect; infrastructure operation = HTML-gateway handoff + signed return/push
  loop). Inherits the parent `payment` engine's model exactly. Mirrors siblings
  payment_stripe / payment_xendit (network/support) — like APS and AsiaPay, a
  redirect-only acquirer (no S2S API, no tokenization), here with a fuller
  pending/done/cancel/refused/error status model and a SHA-1 prefix-filtered
  signature.
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-redirect BPE gateway; European method routing;
  SHA-1 prefix-filtered signed-redirect integrity + verified settlement; push
  webhook + (signed POST) return; multi-currency (8 currencies).
- **Common gaps:** no S2S API (redirect-only; secret is a signing secret); no
  tokenization/saved cards; no manual capture / void / in-module refund; SHA-1
  pinned; webhook needs a public URL + a set secret key; currency bounded to 8;
  downstream reconciliation lives elsewhere.
- **Open questions:** full BPE field sets; runtime state/method-mix distribution;
  how refunds/chargebacks are handled operationally; whether instances rely on the
  push webhook vs the (also signed) POST return route.
