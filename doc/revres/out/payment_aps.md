# payment_aps — Architecture Brief

> Payment Provider: Amazon Payment Services — an acquirer adapter that links an
> Odoo merchant to Amazon Payment Services (PayFort), the MENA-region PSP.
> `_inherit`-only over the `payment` engine: no own models, no own ACL, 4 added
> provider fields. **Hosted-redirect only** — no server-to-server API, no
> tokenization. Odoo 19.0, `version 1.0`, LGPL-3.

## 1. Summary
payment_aps is a concrete realization of the generic `payment` engine for Amazon
Payment Services (PayFort). It adds the `aps` provider code plus four credential
fields (merchant identifier, access code, SHA **request** phrase, SHA **response**
phrase) and overrides the transaction/controller hooks to drive a single flow: a
**hosted-redirect PURCHASE** — Odoo builds a signed hidden-field form that the
browser auto-POSTs to the PayFort payment page; the buyer pays on PayFort; APS
returns the signed feedback to two routes. There is **no outbound REST/API-key
channel** and **no card data in Odoo**. It is a finance/infrastructure support
component, not an end-user app (`application=false`).

## 2. Structure
- **Application:** APS/PayFort acquirer adapter; inherits `payment.provider` /
  `payment.transaction` (no `payment.token` — no tokenization).
- **Models:** `payment.provider` (+`aps_merchant_identifier`, `aps_access_code`,
  `aps_sha_request`, `aps_sha_response`; 3 methods), `payment.transaction`
  (no new fields; 5 override methods).
- **Routes:** `/payment/aps/return` (http POST, csrf=False, save_session=False),
  `/payment/aps/webhook` (http POST, csrf=False).
- **Views:** 1 form inheritance (APS credentials) + the `redirect_form` QWeb
  template + `payment_provider_data.xml`. `xml_loc=60`.
- **Security:** 0/0/0; `aps_access_code` / `aps_sha_request` / `aps_sha_response`
  gated by `base.group_system` (the merchant identifier is ungrouped).

## 3. Frontend (gap #3)
**None.** 0 JS files, 0 OWL components, 0 registry adds, 0 patches. The entire
buyer interaction is the server-rendered `redirect_form` QWeb template
(`payment_aps_templates.xml`) whose hidden inputs auto-POST to the PayFort
payment page. No browser SDK, no inline card form — card data is collected on
PayFort's hosted page, never in Odoo. The only browser artifact is the auto-POST
form, which is plain server-rendered HTML.

## 4. Behavior beyond metadata (code-read — the metadata gap)
- **Redirect flow:** `_get_specific_rendering_values` builds a `command='PURCHASE'`
  payload (access_code, merchant_identifier, merchant_reference=reference, amount
  in minor units, currency, language=`partner_lang[:2]`, customer_email,
  return_url) plus, for non-`card` methods, a `payment_option` = the brand
  upper-cased (`utils.get_payment_option`; `card` is omitted so the buyer picks
  the brand on PayFort). It signs the dict and adds `api_url` (live
  `checkout.payfort.com` vs sandbox `sbcheckout.payfort.com` by `provider.state`).
  **No server-to-server API call.**
- **Signature (`_aps_calculate_signature`):** SHA-256 of `phrase + sorted
  "k=value" pairs (excluding `signature`) + phrase` — a *sandwich*, not an HMAC.
  Direction-specific phrase: `aps_sha_request` outgoing, `aps_sha_response`
  incoming.
- **Inbound (`return` POST + `webhook` POST):** both `_search_by_reference`
  (`_extract_reference` → `merchant_reference`) then `_verify_signature` **before**
  `_process`. `_verify_signature` rejects (HTTP 403 Forbidden) on missing
  signature or a failed `hmac.compare_digest` against the SHA-256 recomputed with
  the response phrase. Unlike most acquirers the return route is itself a signed
  POST and authoritative — no separate verification GET.
- **Status mapping (`_apply_updates`):** `provider_reference=fort_id`; status
  `'19'`→pending, `'14'`→done; missing→error; anything else→error (carrying
  `response_message`). **No cancel branch.**

## 5. IT architecture
- **Services:** `/payment/aps/return` (signed POST, processes, →`/payment/status`),
  `/payment/aps/webhook` (signed POST, processes, returns `''`).
- **Data objects:** `payment.provider` (+4 fields), `payment.transaction`.
- **Key relations:** tx → provider (`provider_code=='aps'` gates every override);
  external keys `reference==merchant_reference`, `provider_reference==fort_id`.
- **External integration (gap #7):** `uses_api_keys=false`. The only endpoints
  are the two PayFort hosted pages; reached purely by the browser POSTing the
  signed form. Authenticity rests on the SHA-256 request/response phrases +
  access code, not a transport key. None of this is derivable from metadata.

## 6. Business architecture
- **Capabilities (inferred):** accept MENA-region card payments via APS/PayFort
  hosted redirect; per-brand routing (Visa/Mastercard/Amex/Discover);
  signed-redirect settlement with no card data in Odoo; multi-currency.
- **Value streams (inferred):** Collect-Payment (redirect → signed return/webhook
  → `_process`), Settle (`'14'`→`_set_done`→downstream).
- **Information concepts (auto):** payment.provider, payment.transaction.
- **Organization (auto):** no own groups; secret credentials gated by
  `base.group_system`.
- **Policies (inferred):** inbound signature authenticity (403 on mismatch);
  outbound form signed with the request phrase; references forced to a
  `tx`-prefixed token; minor-unit amounts.
- **Strategy:** null (human). **Products:** none.

## 7. Classification
- **value_model: network** — Stabell & Fjeldstad mediating-technology. Links the
  payer and merchant by connecting the merchant to APS/PayFort's MENA card
  network (network promotion/contract mgmt = merchant id + access code + SHA
  phrases; service provisioning = build/sign/confirm the PURCHASE redirect;
  infrastructure operation = hosted-page handoff + signed return/webhook loop).
  Inherits the parent `payment` engine's model exactly. Mirrors siblings
  payment_stripe / payment_xendit (network/support) — APS is the thinnest variant
  (redirect-only, no S2S API, no tokenization).
- **activity_class: support** — payment acceptance is an infrastructure/finance
  support function (Accounting/Payment Providers, `application=false`).
- **apqc_category: 9.0 Manage Financial Resources** (9.5 process payments /
  collect cash; manage an external payment provider).

## 8. Fit-to-Standard & Open Questions
- **Standard:** hosted-redirect PURCHASE via PayFort; per-brand routing;
  signed-redirect integrity + signature-verified settlement; webhook + (signed
  POST) return; multi-currency.
- **Common gaps:** no S2S API (redirect-only); no tokenization/saved cards; no
  manual capture / void / in-module refund; no cancel-state mapping (non-19/14
  →error); webhook needs a public URL + a set SHA response phrase; downstream
  reconciliation lives elsewhere.
- **Open questions:** full PayFort field sets; runtime state/brand-mix
  distribution; how refunds/cancellations are handled operationally; whether
  instances rely on the webhook vs the (also signed) POST return route.
