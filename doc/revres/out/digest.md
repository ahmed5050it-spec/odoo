# digest (KPI Digests) — Architecture Brief

> Module `digest`, display name **"KPI Digests"** (`odoo/addons/digest/`). Odoo's
> periodic performance-summary engine: the *"Odoo: your daily/weekly summary"*
> email that broadcasts company KPIs (connected users, messages, and — via
> consumer modules — revenue, leads, invoiced, etc.) with period-over-period
> margins. `depends = [mail, portal, resource]`. 2 own models, 3 HTTP routes,
> ~1.1k Python LOC, 0 JS. `application=False`.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). digest has **no value stream of
  its own** — it produces no product, order, or document. It is internal
  performance-reporting / communication infrastructure that *reads* primary
  activities' metrics and *broadcasts* them on a schedule.
- **activity_class: support.**
- **apqc_category: 13.0 Develop and Manage Business Capabilities** (manage business
  performance / KPI reporting). Chosen over **9.4** (internal controls) because the
  digest is forward-looking performance *monitoring*, not compliance/control
  enforcement; and over a pure internal-comms reading (which would lean on `mail`
  at ~13.x Information & Knowledge Mgmt) because email is only the delivery
  *channel* — the reason-for-being is the KPI content and its extensible metric
  catalog. No 13.0 row exists yet in `apqc_odoo_map.tsv`; architect classification.

## 2. IT Architecture

- **Application:** digest — periodic KPI summary-email component; a thin **host**
  other apps extend with their own `kpi_*` fields.
- **Software services (routes):** `/digest/<id>/unsubscribe_oneclik` (public, POST,
  csrf-exempt, RFC-8058), `/digest/<id>/unsubscribe` (public), `/digest/<id>/set_periodicity`
  (user, manager-gated). All `http`.
- **Core data objects:** `digest.digest` (13 fields, 33 methods), `digest.tip`
  (5 fields); plus inherits on `res.config.settings` (default-digest setting) and
  `res.users` (auto-subscribe).
- **Key ERM:** `digest.digest → res.users (user_ids, share=False)`;
  `→ res.company → res.currency (currency_id related)`; `digest.tip → res.users`
  (already-received) `+ res.groups` (audience); `res.config.settings → digest.digest`;
  `kpi_*_value → (any model)._read_group` over a date window (computed, not a stored FK).

## 3. Behavioral Notes (code-read, the metadata gap)

1. **Cron + per-subscriber batching** (`_cron_send_digest_email` → `_action_send`):
   daily cron picks digests with `next_run_date <= today` and `state='activated'`,
   then iterates `user_ids` and renders **one `mail.mail` per recipient** in their
   lang/company. `_check_daily_logs` reads `res.users.log`; recipients with no login
   in the window trigger a one-step periodicity slow-down
   (`daily→weekly→monthly→quarterly`) to throttle spam. `next_run_date` advances by
   the periodicity delta.
2. **KPI compute over date windows** (`_compute_kpis` / `_calculate_company_based_kpi`):
   KPIs are opt-in `kpi_*` Booleans with paired `<f>_value` computes. `_compute_kpis`
   renders **3 columns** (Last 24h / 7 Days / 30 Days) by re-running each value under
   different context timeframes (+ prior period for the margin %), invalidating cache
   between runs. `_calculate_company_based_kpi` `_read_group`s the target model on
   `(date_field >= start, < end)` scoped to the digest company;
   `kpi_mail_message_total_value` `search_count`s `mail.message` (subtype `mail.mt_comment`).
   `AccessError` silently drops that KPI from the user's email.
3. **Unsubscribe + per-recipient hmac** (`controllers/portal.py`): `_action_send_to_user`
   mints a per-(digest,user) token (`_get_unsubscribe_token`), embedded both as a body
   link and as RFC-8058 `List-Unsubscribe` / `One-Click` headers. The public controller
   `consteq`-validates the token before `_action_unsubscribe_users`; the one-click route
   is POST-only + `csrf=False` so an MUA can act without a session.
4. **Tip rotation** (`_compute_tips`): pulls `digest.tip` rows **not yet sent** to the
   user (`user_ids != user.id`) and matching their groups (or group-less), `limit=tips_count`;
   renders/sanitizes the Html; appends the user to `tip.user_ids` so each tip shows **once
   per recipient** and rotates over successive digests.
5. **Auto-subscribe** (`res.users.create`): new non-share users are added to the default
   digest (`ir.config_parameter digest.default_digest_id`) so employees receive it without
   manual opt-in.

**Frontend (gap #3):** none shipped — 0 JS/OWL/registry/patches/bundles. The whole
user surface is **server-rendered QWeb email**: `digest_mail_layout` (HTML/CSS shell)
+ `digest_mail_main` (3-col KPI grid `digest_tool_kpi` with ⬆/⬇ margin badges, tips
loop, manager preferences, mobile banner, unsubscribe footer) + `portal_digest_unsubscribed`.
Backend config is plain form/list/search.
**Integrations (gap #7):** no outbound HTTP/SDK, no API keys, no endpoints.

## 4. Business Architecture

- **Capabilities (inferred):** Periodic KPI Digest Email; Company Performance Metric
  Computation (period-over-period margin); Extensible KPI Catalog; Subscriber &
  Auto-Subscription mgmt; Engagement-Based Send Throttling; Per-Recipient Unsubscribe/
  Preference self-service; Tip/Onboarding rotation.
- **Value streams (inferred):** Compute-and-Broadcast-KPIs; Throttle-Inactive-Recipients;
  Unsubscribe-and-Tune.
- **Information concepts (auto):** `digest.digest`, `digest.tip`.
- **Organization (auto):** **no own groups** (facts `groups: 0`); 4 access rules split
  `base.group_erp_manager` (CRUD) vs `base.group_user` (read-only); recipients restricted
  to `share=False` internal users.
- **Policies (inferred):** internal-only recipients; engagement throttle via `res.users.log`;
  hmac-token (not ACL) unsubscribe, one-click POST-only; `set_periodicity` manager-gated;
  unreadable KPIs dropped per user; default-digest auto-subscription via config params.
- **Metrics (inferred):** `kpi_res_users_connected`, `kpi_mail_message_total`, per-KPI
  margin %; downstream revenue/leads/invoiced/POS/website/project/livechat/recruitment
  KPIs injected by **9 consumer modules** (crm, account, project, point_of_sale,
  website_sale, sale_management, im_livechat, hr_recruitment + digest).
- **Strategy:** null (human — none derivable).

## 5. Fit-to-Standard

- **Out-of-box:** daily/weekly/monthly/quarterly KPI digest per company; 2 base KPIs
  with 3-timeframe margins; opt-in KPI toggles; per-recipient send + token/one-click
  unsubscribe; inactive-recipient slow-down; new-user auto-subscribe; rotating tips.
- **Typical fits:** enable the default digest; toggle KPIs + set periodicity in Settings;
  add a custom KPI via `kpi_<x>` Boolean + `kpi_<x>_value` compute calling
  `_calculate_company_based_kpi`; switch periodicity from the email.
- **Common gaps:** no charts/trends/drill-down (counts over a fixed window, only an
  optional "Open Report" link); custom KPIs need Python/Studio; audience is a flat internal
  user list (no segments/A-B/portal); single channel (email — no in-app dashboard / Slack /
  PDF); throttle is presence-based, not open/click tracking.

## 6. Drive Hints (run-odoo)

```
odoo shell: env['digest.digest'].search([]).mapped(('name','periodicity','state','next_run_date'))
odoo shell: d=env.ref('digest.digest_digest_default'); [f for f in d._fields if f.startswith('kpi_') and d[f]]
odoo shell: d._action_send_to_user(env.user); env['mail.mail'].search([],order='id desc',limit=1)
odoo shell: d._compute_kpis(env.company, env.user)   # 3-column KPI payload + margins
curl -X POST '/digest/<id>/unsubscribe_oneclik' -d 'token=<hmac>&user_id=<uid>'
```

## 7. Open Questions

- The `Marketing` manifest category looks legacy — behavior is management/performance
  reporting (13.0), not marketing.
- Full KPI set + compute cost once all 9 consumer modules are installed (base ships only 2).
- Clean single APQC leaf under 13.0 for a periodic management-KPI instrument vs 9.x controls.
- Multi-company: per-digest `company_id` scoping vs a recipient in several companies when
  computing `res.users` KPIs.

## 8. Provenance

- Facts: `doc/revres/facts/digest.facts.json`; frontend/integrations `doc/revres/frontend/digest.frontend.json`.
- Tools: `extract_module.py`, `extract_frontend.py`; code-read of `models/digest.py`,
  `models/digest_tip.py`, `models/res_users.py`, `controllers/portal.py`,
  `data/ir_cron_data.xml`, `data/digest_data.xml`, `security/ir.model.access.csv`; grep of
  `kpi_*` injection across addons.
- Odoo 19.0. Record: `doc/revres/metamodel/digest.metamodel.json` (schema-valid).
