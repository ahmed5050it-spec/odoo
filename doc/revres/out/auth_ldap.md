# auth_ldap — Architecture Brief

> Module: `auth_ldap` · Category: Hidden/Tools · Depends: `base` · `base_setup` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> External dep: **python-ldap** (apt `python3-ldap`)
> Odoo 19.0 · Facts: `doc/revres/facts/auth_ldap.facts.json` · Frontend: `doc/revres/frontend/auth_ldap.frontend.json`

## 1. Summary

`auth_ldap` is **IT identity & access infrastructure** — it lets Odoo users sign in
with their **corporate LDAP / Active Directory** credentials, transparently. There is
no login-page widget: the user types their normal login/password into the standard web
login form, Odoo's native check runs first, and on failure `auth_ldap` falls back to a
**server-to-server LDAP simple-bind** against the directory. A successful bind *is* the
proof of identity (the directory, not Odoo, verifies the password). On first login a
local `res.users` "shadow" account is **just-in-time provisioned**. It owns **no
business object of its own**: 1 real model (`res.company.ldap`, pure connection config)
plus thin extensions of `res.company` / `res.config.settings` / `res.users`, **0
routes**, ~534 Python LOC. Not `auto_install`, but once installed it sits beneath the
login every other module relies on.

## 2. Structure (evidence)

- **Models:** `res.company.ldap` (11 fields: `ldap_server`/`ldap_server_port`,
  `ldap_tls`, `ldap_binddn`/`ldap_password` service account, `ldap_base` search-scope DN,
  `ldap_filter` login matcher, `create_user`, `user` Template User, `sequence`,
  `company`) — the only real model; plus extensions of `res.company` (`ldaps` One2many,
  `groups=base.group_system`), `res.config.settings` (`ldaps` related → `company_id.ldaps`,
  Settings-page editing), and `res.users` (credential-pipeline hooks, **no new stored fields**).
- **Routes:** none — `auth_ldap` exposes no controllers; it hooks `res.users._login` /
  `_check_credentials` / `change_password`.
- **Security:** 1 access rule, 0 record rules, 0 groups. Config + stored service
  credentials are gated to `base.group_system` (ACL + `groups=` on the One2many).
- **Views:** 1 form + 1 list (directory admin) surfaced through the `res.config.settings`
  General Settings page; per-record **Test Connection** button.

## 3. Frontend (gap #3) & Integrations (gap #7)

**Zero client footprint** — `extract_frontend` reports `present: false`: 0 JS files, 0
XML templates, 0 OWL components, 0 registry adds, 0 services, 0 patches, 0 asset
bundles. The entire UI is the server-rendered Settings page and the `res.company.ldap`
list/form views. Integrations (gap #7): the HTTP-oriented scan reports
**`http_call_sites: 0`, `sdk_imports: []`, `endpoints: []`** because the integration is
**not over HTTP** — it is the **LDAP protocol** via the `python-ldap` library
(`import ldap`, declared in manifest `external_dependencies.python=['python-ldap']`).
Every authentication makes server-to-server binds/searches
(`ldap.initialize` → `start_tls_s` → `simple_bind_s` → `search_st` → `passwd_s`) against
a corporate directory (OpenLDAP, Microsoft Active Directory / Entra on-prem, FreeIPA,
389-DS). `uses_api_keys: true` reflects the stored service-account bind credentials
(`ldap_binddn`/`ldap_password`); targets are admin-configured per `res.company.ldap`
record, not hardcoded.

## 4. Behavior (beyond metadata)

- **Directory config** (`res.company.ldap`): one server's wiring — `ldap_server:port`
  (default `127.0.0.1:389`), `ldap_tls` (STARTTLS), `ldap_binddn`/`ldap_password`
  (service account; empty = anonymous bind), `ldap_base` (subtree search scope),
  `ldap_filter` (each `%s` ← the login; **must resolve to exactly one entry**, e.g.
  `(&(objectCategory=person)(objectClass=user)(sAMAccountName=%s))` for AD). `ldaps` is a
  One2many per company, tried in `sequence` order. (code-read)
- **Bind fallback auth** (`res.users._login` / `_check_credentials` →
  `res.company.ldap._authenticate`): `super()._login` (local password) runs first; only on
  `AccessDenied` **and** no existing local row does it iterate `_get_ldap_dicts()` and call
  `_authenticate`, which **rejects empty passwords up front** (RFC 4513 — no
  "unauthenticated authentication"), resolves the DN, then `simple_bind_s(dn, password)`.
  First matching server wins → `auth_method='ldap'`, `mfa='default'`. (code-read)
- **JIT provisioning + attribute mapping** (`_get_or_create_user` / `_map_ldap_attributes`):
  matches a local account by raw SQL `lower(login)`; if absent and `create_user` is set,
  provisions a new `res.users` — `name` ← LDAP `cn`, `login` ← login, `email` ← login (only
  if email-shaped), `company_id` ← config company — via `sudo()`+`no_reset_password`, either
  `create()` or `copy()` of the Template User. Absent + `create_user` False → `AccessDenied`.
  (code-read)
- **Password write-through** (`res.users.change_password` → `_change_password` +
  `_set_empty_password`): binds the directory with the OLD password and issues
  `ldap.passwd_s(dn, old, new)`; on success it **NULLs the local password column** (raw
  `UPDATE res_users SET password=NULL`) so the directory stays the sole credential, then
  returns without falling through to super. (code-read)
- **Connection handling** (`_connect` / `_query` / `test_ldap_connection`): builds
  `ldap://server:port`, honours the `auth_ldap.disable_chase_ref` ICP (default → referrals
  OFF, stops AD referral chasing), calls `start_tls_s()` when `ldap_tls`; `_query` service-binds
  and `search_st` over `ldap_base` (SCOPE_SUBTREE, 60s timeout); `test_ldap_connection` is an
  admin action returning a `display_notification` (success / server-down / bad-creds / timeout).
  (code-read)

## 5. IT architecture

- **Application:** LDAP/AD authentication delegated to the directory via `python-ldap`
  simple-bind, with JIT provisioning and password write-through.
- **Software services:** no HTTP routes — hooks `res.users._login` / `_check_credentials`
  / `change_password`; admin action `res.company.ldap.test_ldap_connection`.
- **Data objects:** `res.company.ldap`; `res.company` (`ldaps`); `res.config.settings`
  (`ldaps` related); `res.users` (bind fallback + JIT hooks).
- **Information flows:** login → `super` (local) → on AccessDenied + no local row →
  `_get_ldap_dicts()` → `_authenticate` per server → `simple_bind_s` at the directory;
  provision → `_get_or_create_user` → `_map_ldap_attributes` → `create()`/`copy(Template)`;
  password change → `_change_password` (`passwd_s`) → `_set_empty_password` (NULL local).

## 6. Business architecture

- **Capabilities (inferred):** directory-based authentication (LDAP/AD simple-bind);
  directory connection configuration; external-to-local identity mapping & JIT user
  provisioning; password write-through / directory-synchronised credentials; service-account
  query & connection validation.
- **Value streams (inferred):** Configure-Directory (admin enters server/TLS/bind/base/filter
  → Test Connection → directory becomes an auth source); Login-to-Session (login fails locally
  → LDAP service-query resolves DN → simple-bind → match/provision `res.users` → session).
- **Information concepts (auto):** `res.company.ldap`, `ldap_binddn`/`ldap_password`,
  `ldap_base`, `ldap_filter`, `res.users` (local shadow account).
- **Organization/Products (auto):** none (no own groups, no `product.*`).
- **Policies (inferred):** config to `base.group_system` only; bind-is-truth (empty passwords
  rejected, RFC 4513); local-first / LDAP-fallback (existing local user not overridden); JIT
  only when `create_user`; `ldap_filter` must resolve to exactly one entry; credential
  neutralisation (local password NULLed on directory change).
- **Metrics (inferred):** count of configured directories; count of LDAP-provisioned users;
  Test Connection success/failure outcomes.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** IT identity & access infrastructure (Porter support activity;
  Stabell & Fjeldstad "support"). It owns no business object — its one real model
  (`res.company.ldap`) is pure connection config, everything else extends
  `res.users`/`res.company`/config. It creates no document chain and holds no
  customer/order/product/ledger data; its sole job is to authenticate users against an
  **external** corporate directory beneath the login every module sits behind. Hence not
  chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** This is the "identity & access management /
  external system integration" capability — a concrete running access-control runtime (LDAP
  bind fallback, service-account directory query, identity mapping, JIT provisioning, password
  write-through). **11.0 "Manage Enterprise Risk, Compliance, …"** was considered (directory
  auth touches account-security governance) but rejected: 11.0 is the governance layer
  (control frameworks, audits, policy), whereas `auth_ldap` is the technical *implementation*
  IT builds and operates — squarely 8.0. Mirrors the sibling `auth_oauth` / `auth_totp` / `web`
  records.

## 8. Fit-to-Standard

- **Standard:** transparent LDAP/AD auth delegated via `python-ldap` simple-bind (standard
  login form kept); per-company, sequence-ordered directory list configured from Settings
  (server/port, STARTTLS, bind DN+password, base DN, login filter); service-account
  subtree-scoped query with a login-to-entry filter (must resolve to exactly one); JIT local
  user provisioning (name ← `cn`, email ← login, optional Template User copy); local-first /
  LDAP-fallback ordering; password write-through (`passwd_s`) NULLing the local credential;
  admin Test Connection + AD-referral-chasing toggle.
- **Typical fits:** employees log in with existing AD / corporate LDAP credentials out of the
  box; centralise password policy and account lifecycle in the directory while Odoo holds thin
  shadow accounts; multi-company pointing each company at its own directory; STARTTLS + a
  dedicated read-only service bind DN.
- **Common gaps:** simple-bind / STARTTLS only (no out-of-box `ldaps://` 636, Kerberos/SASL,
  cert bind); no LDAP-group → Odoo-group mapping and no de-provisioning (directory disable does
  not deactivate the shadow account); attribute mapping hardcoded (`cn`/email) — richer sync
  needs `_map_ldap_attributes` override; ambiguous filter entries silently fail; service-account
  password is plain config (no vault); no connection pooling/caching, failover only by trying the
  next configured server.
- **Drive hints:**
  `env['res.company.ldap'].search_read([], ['ldap_server','ldap_server_port','ldap_tls','ldap_base','ldap_filter','create_user'])`;
  `env['res.company.ldap'].create({'company': env.company.id,'ldap_server':'127.0.0.1','ldap_server_port':389,'ldap_base':'dc=example,dc=com','ldap_filter':'(uid=%s)'})`;
  `env['res.company.ldap'].browse(1).test_ldap_connection()`;
  `env['res.users'].search_read([('login','!=','admin')], ['login','company_id'])`;
  `python3 -c 'import ldap; print(ldap.__version__)'` (confirm the python-ldap dependency).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/res_company_ldap.py`, `models/res_users.py`, `models/res_company.py`,
`models/res_config_settings.py`. Odoo 19.0.*
