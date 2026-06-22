# iap — Architecture Brief

> Module: `iap` · Category: Hidden/Tools · Depends: `web` · `base_setup` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/iap.facts.json` · Frontend: `doc/revres/frontend/iap.frontend.json`

## 1. Summary

`iap` is the **In-App Purchase framework** — the credit/account plumbing that brokers
paid calls to Odoo's external IAP services (SMS, lead enrichment, snailmail,
partner autocomplete, OCR, lead mining…). It owns no business object of its own:
just **3 models, 0 routes, ~723 py LOC**. Its substance is the **single outbound
JSON-RPC broker** (`iap_tools.iap_jsonrpc`) plus the **per-service prepaid wallet**
(`iap.account`). `auto_install: true` and category *Hidden/Tools* mark it as
ubiquitous, invisible plumbing — the **egress chokepoint** through which every
dependent module's metered call to `iap.odoo.com` flows (gap #7).

## 2. Structure (evidence)

- **Models (3):** `iap.account` (11 fields — the local credit wallet),
  `iap.service` (5 fields — the service catalogue, e.g. `reveal`), and
  `iap.enrich.api` (AbstractModel, 0 fields — a facade over one paid endpoint).
- **Routes:** **0** — `iap` exposes no web/RPC surface; all traffic is *outbound*.
- **Security:** 4 access rules, 1 record rule, 0 groups. `base.group_system`
  CRUDs accounts; `base.group_user` may read/create only; `account_token` is
  restricted to `group_system`.
- **Views:** form 1 + list 1 (the IAP Accounts admin screen) — no analytical views.

## 3. Frontend (gap #3)

Minimal: **1 JS / 1 XML**, bundled in `web.assets_backend`. One OWL component,
`IAPActionButtonsWidget`, registered as the `iap_buy_more_credits` view widget.
`onManageServiceLinkClicked` does `orm.silent.call('iap.account','get_account_id')`
then opens the account form; `onViewServicesClicked` does
`doAction('iap.iap_account_action')`. Host modules drop this widget on their
settings/config views to surface "Manage Service & Buy Credits" / "View My Services".

## 4. Behavior (beyond metadata)

- **`iap.account` wallet (code-read):** one row per service; identity is
  `account_token` (uuid4, size 43, `group_system`). `balance`/`state` are NOT
  stored — `web_read()` → `_get_account_information_from_iap()` POSTs each
  token+`dbuuid` to `/iap/1/get-accounts-information` and writes back the synced
  balance/state on every form read. On a neutralized/duplicated DB the token is
  suffixed `+disabled` so credits can never be spent.
- **`iap_tools.iap_jsonrpc` (code-read):** the ONE internet egress point —
  `requests.post(url, json=jsonrpc_envelope)`, unwraps `result`, and maps server
  errors to typed exceptions: `InsufficientCreditError` (carries credit/service/
  base_url so callers can prompt top-up), `IAPServerError`, or `AccessError`
  (timeouts). Target host = `iap.endpoint` param (default `https://iap.odoo.com`);
  under `module.current_test` it hard-fails — never bills or hits the network.
- **Credit check & top-up (code-read):** `get_credits()` POSTs `/iap/1/balance`
  (the "do I have enough?" probe, returns count or −1); `get_credits_url()` builds
  the buy-more deep-link to `/iap/1/credit` with a **SHA1-hashed** token (the raw
  secret never leaves in a URL). `iap.account.get(service)` lazily provisions the
  account on a separate cursor (the first paid call typically rolls back the main one).
- **`iap.enrich.api` (code-read):** the broker pattern other modules copy —
  `_contact_iap()` injects token+`dbuuid` and calls
  `https://iap-services.odoo.com/iap/clearbit/1/lead_enrichment_email`.

## 5. IT architecture

- **Application:** the IAP framework — credit-account plumbing + outbound JSON-RPC
  broker to Odoo IAP services.
- **Data objects:** `iap.account`, `iap.service`, `iap.enrich.api`.
- **ERM:** `iap.account → iap.service` (service_id), `→ res.company` (company_ids
  scope), `→ res.users` (low-credit alert recipients).
- **Information flows:** outbound `iap_jsonrpc → requests.post → iap.endpoint`;
  balance sync via `web_read`; errors (`InsufficientCreditError`…) propagated up to
  gate paid features; consumed by sms / snailmail / partner_autocomplete / crm
  mining / ocr (each calls `iap.account.get` + `iap_jsonrpc`).

## 6. Business architecture

- **Capabilities (inferred):** Broker paid calls to external IAP services; provision
  & hold per-service credit accounts; check balance & gate features; provide a
  buy-more top-up link; sync balance/state; low-credit email alerts; per-company
  scoping; disable spending on neutralized DBs.
- **Value streams (inferred):** *Provision-to-Spend* (`get(service)` → token →
  `iap_jsonrpc` → result or `InsufficientCreditError`); *Low-credit-to-Top-up*
  (balance sync → `get_credits_url` → Odoo IAP portal → recharged).
- **Information concepts (auto):** `iap.account`, `iap.service`, `iap.enrich.api`,
  `account_token`, remote credit balance/state.
- **Organization / Products (auto):** none (0 groups, no `product.*`).
- **Policies (inferred):** record rule scopes accounts to own companies; token is
  `group_system`-only; neutralized DB → `+disabled`; tests never bill.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `iap` is shared firm IT infrastructure (Porter support;
  Stabell & Fjeldstad "support"). It creates no primary value in any single
  chain/shop/network — it is the credit plumbing and outbound broker **many** modules
  reach external paid services through. `auto_install: true` + Hidden/Tools confirm
  ubiquitous plumbing; with 3 models / 0 routes its substance is the external HTTP
  integration (gap #7) and the credit wallet.
- **APQC: 8.0 Manage Information Technology.** The work is managing external IT
  services / vendor connectivity — provision accounts, broker calls, meter credits,
  manage the IAP endpoint config. 9.0 (Acquire/Manage Assets) was considered for the
  credit-purchase flavour but rejected: there is no purchase.order/account.move/asset
  here — `iap` only mints a top-up URL and meters a remote prepaid balance; the
  capability is technical vendor-connectivity, squarely 8.0.

## 8. Fit-to-Standard

- **Standard:** per-service prepaid account with secret token; single outbound
  JSON-RPC broker with typed errors; configurable `iap.endpoint`; on-demand
  balance/state sync; buy-more deep-link + `iap_buy_more_credits` widget; low-credit
  alerting; multi-company scoping; auto spend-disable on neutralized DBs; lazy
  provisioning (`iap.account.get`).
- **Typical fits:** any metered paid call (declare an `iap.service`, call
  `iap.account.get` then `iap_jsonrpc`); embedding the buy-credits widget; pointing
  the DB at a private IAP proxy via the `iap.endpoint` parameter.
- **Common gaps:** no local consumption/spend ledger (billing lives server-side,
  gap #7); no authorize/capture two-phase charge in this version (a paid call is a
  single `iap_jsonrpc` answered with `InsufficientCreditError`); requires outbound
  HTTPS (air-gapped needs a self-hosted endpoint); no in-app checkout (top-up is a
  portal redirect); tests cannot exercise real calls.
- **Drive hints:** `env['iap.service'].search([]).mapped('technical_name')`;
  `env['iap.account'].get('reveal').sudo().account_token`;
  `env['iap.account'].get_credits_url('reveal')`;
  `env['ir.config_parameter'].sudo().get_param('iap.endpoint','https://iap.odoo.com')`.
