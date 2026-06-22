# base_setup — Architecture Brief

> Module: `base_setup` · Category: Hidden · Depends: `base` · `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/base_setup.facts.json` · Frontend: `doc/revres/frontend/base_setup.frontend.json`

## 1. Summary

`base_setup` is the **foundation of Odoo's General Settings**: it owns the base
`res.config.settings` option registry plus apps/users onboarding and company
setup. It is a **behavioral, not data-bearing** module — `auto_install=true`
configuration plumbing every deployment relies on. Only one declared model exists
(the abstract `kpi.provider`, which holds no rows); its real substance is ~30
`res.config.settings` fields, including **~16 `module_*` installer toggles** that
trigger app install on save, `group_*` feature flags, `config_parameter` writes,
the invite-users flow, and the Settings dashboard counters (~934 Python LOC,
~258 XML LOC).

## 2. Structure (evidence)

- **Models:** 1 own abstract model (`kpi.provider`) + 3 inherit-only extensions
  (`res.config.settings`, `res.users`, `ir.http`).
- **Routes (3):** `/base_setup/data` (dashboard users tile, `erp_manager`-gated),
  `/base_setup/demo_active` (detect demo databases), `/kpi/summary` (KPI hook).
- **Security:** none of its own (0 access rules, 0 record rules, 0 groups) —
  gating is in controller code (`base.group_erp_manager`) and `execute()`
  (admin-only).
- **Views:** no own view records here (Settings form lives in data/XML); the
  module contributes one cog-menu OWL widget.

## 3. Frontend (gap #3)

extract_frontend reports **present, 1 JS / 1 XML**, one OWL component:
`ResetModuleStateCogMenu` (bundle `web.assets_backend`). `static/src/views/
module_views.js` registers it in the **`cogMenu` registry** for the
`ir.module.module` list view; it calls `ir.module.module.button_reset_state` and
reloads — a recovery tool for module installs left in a transient state. Thin
frontend, but not reverse-engineerable from Python metadata.

## 4. Behavior (beyond metadata)

- **`module_*` toggles → app install:** `res.config.settings.execute()` classifies
  `module_<name>` fields, computes to-install / to-uninstall, then runs
  `ir.module.module.button_immediate_install()` at the **end of the transaction**
  (MUST be last to avoid registry↔DB desync); uninstall opens
  `base.module.uninstall`. Env is reset and the client reloads. (code-read)
- **`group_*` + `config_*`:** `set_values()` calls `_apply_group`/`_remove_group`
  on `base.group_user` for `group_multi_currency`; `show_effect` /
  `profiling_enabled_until` persist to `ir.config_parameter`. (code-read)
- **`web_create_users(emails)`:** invite flow — normalizes emails, requires
  Discuss, **reactivates** matching deactivated users, then `create()`s the rest
  under `signup_valid` to issue signup tokens. (code-read)
- **Company setup + counters:** `open_company`/`open_new_user_default_groups`/
  `edit_external_header` actions; `company_count`/`active_user_count`/
  `language_count` are `@api.depends('company_id')` sudo `search_count` computes
  (depends on a field because it's a TransientModel). (code-read)
- **`/base_setup/data`:** raw SQL over `res_users`/`res_users_log` for active and
  "pending" (never-logged-in) user counts feeding the dashboard tile. (static)

## 5. IT architecture

- **Application:** `base_setup` — General Settings foundation over `base` + `web`.
- **Software services:** `/base_setup/data`, `/base_setup/demo_active`,
  `/kpi/summary`.
- **Data objects:** `res.config.settings` (ext), `res.users` (ext),
  `kpi.provider`, `ir.http` (ext).
- **Information flows:** save Settings → `execute()` → groups/`ir.default`/
  `ir.config_parameter` → `button_immediate_install()` → txn reset → reload;
  invite → `web_create_users` → reactivate/create + signup tokens.

## 6. Business architecture

- **Capabilities (inferred):** Configure the system via General Settings;
  Enable/disable features by installing apps (`module_*`); Toggle group feature
  flags (`group_*`); Onboard & invite users; Set up company profile/report
  layout/footer; Surface setup KPIs/counters.
- **Value streams (inferred):** Configure-to-Activate; Invite-to-Active-User.
- **Information concepts (auto):** `res.config.settings`, `kpi.provider`, company
  profile, module install state, system parameter.
- **Organization/Products (auto):** none (no groups, no `product.*`).
- **Policies (inferred):** `execute()` admin-only; `/base_setup/data`
  `erp_manager`-gated; `group_*` mutates firm-wide `base.group_user`; install must
  run last in the transaction.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** `base_setup` is cross-cutting firm IT infrastructure
  (Porter support; Stabell & Fjeldstad "support") — it creates no primary value in
  any chain/shop/network. `auto_install=true` makes it ubiquitous configuration
  plumbing.
- **Activity class: support. APQC: 8.0 Manage Information Technology** — the work
  is IT delivery/configuration management: provision application capabilities
  (install apps), manage IT configuration (parameters, feature flags), administer
  user/company setup. 13.0 (Develop & Manage Business Capabilities) was considered
  but rejected — this is a concrete installer/config mechanism, not governance.

## 8. Fit-to-standard

- **Out-of-box:** grouped General Settings toggles; install apps via `module_*`
  checkbox; `group_*` feature flags; `config_parameter` system settings; company
  profile + report layout/footer; invite-users with reactivation/signup tokens;
  dashboard counters + KPI hook; reset-module-state cog menu.
- **Common gaps:** new Settings options need dev (field + view); install
  side-effects not previewed; `group_*` flags are firm-wide (no per-user);
  `get_kpi_summary` returns `[]` until overridden; no external integrations here
  (gap #7: zero outbound HTTP/SDK call sites).
- **Drive:** `env['res.config.settings']._get_classified_fields()`;
  `create({'module_voip': True}).execute()`;
  `env['res.users'].web_create_users([...])`; `POST /base_setup/data`.
