# base_import_module — Architecture Brief

> Module: `base_import_module` · Category: Hidden/Tools · Depends: `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/base_import_module.facts.json` · Frontend: `doc/revres/frontend/base_import_module.frontend.json`

## 1. Summary

`base_import_module` lets an administrator **import a custom Odoo module from a
zip/folder at runtime** — installing or upgrading a packaged module uploaded
through the UI (or an HTTP endpoint) without touching the addons-path or
restarting the server. It is structurally framework plumbing: **1 own transient
model** (`base.import.module`, the upload wizard) plus **4 extensions** of core
models (`ir.module.module`, `ir.http`, `ir.ui.view`, `base.module.uninstall`),
**1 HTTP route**, ~1740 Python LOC, ~123 XML LOC. It owns no business object — it
acts **on the platform itself**, registering uploaded code/data modules into the
live database and governing their lifecycle (state `imported=True`).

## 2. Structure (evidence)

- **Models (1 own + 4 extensions):** `base.import.module` (TransientModel,
  `models/base_import_module.py`; fields `module_file`/`state`/`import_message`/
  `force`/`with_demo`/`modules_dependencies`, 3 methods). Extensions:
  `ir.module.module` (`models/ir_module.py`, ~21 methods — the import engine, adds
  `imported` + `module_type`), `ir.http` (webclient translations from DB
  attachments), `ir.ui.view` (imported-module view handling),
  `base.module.uninstall` (delete imported modules on uninstall).
- **Routes (1):** `/base_import_module/login_upload` (HTTP POST, `auth='none'`,
  `csrf=False`) — inline-authenticated admin module upload for CI/scripts.
- **Security:** 1 access rule (`base.group_system`, no unlink), 0 record rules.
- **Views:** `base.import.module` upload form + an `ir.module.module` list override
  for the Industries Apps browse. The Import Module menu/`force` are debug-only
  (`base.group_no_one`).

## 3. Frontend (gap #3)

Lightweight — extract_frontend reports **present, 2 JS / 0 XML**, no OWL component
or QWeb template of its own. `base_import_list_view.js` spreads `@web/views/list/
list_view`, swaps in `ImportModuleListRenderer` (`base_import_list_renderer.js`),
and `registry.category("views").add("ir_module_module_tree_view", …)` so the Apps/
Industries module list renders with a custom renderer, driving the `more_info`
service/action that opens a module form. The actual upload UI is a plain Python
QWeb wizard form, not OWL — behaviour beyond that lives in `models/ir_module.py`.

## 4. Behavior (beyond metadata)

- **`import_module` + `_import_zipfile`:** the wizard base64-decodes the `.zip` into
  a `BytesIO` and calls `ir.module.module._import_zipfile`, which gates on
  `is_admin()` (else `AccessError`), rejects non-zips and entries over
  `MAX_FILE_SIZE=100MB`, unpacks into a temp dir, parses each manifest, **topo-sorts
  the modules by `depends`**, and imports each in order (failures wrapped in a
  `UserError` carrying the traceback). (code-read)
- **`_import_module` (runtime registration):** registers a module into the live DB
  **without it being on the addons-path**. Either writes an existing
  `ir.module.module` to `state='installed'` (mode `update`, or `init` if `force`) or
  **creates** a new record with `imported=True, state='installed'` (mode `init`).
  Unmet `depends` are `button_immediate_install`'d first; Studio-authored modules
  are refused unless `web_studio` is installed (`_is_studio_custom`). (code-read)
- **Loading data + assets:** for each manifest `data`/`init_xml` (`+demo`) file
  ending `.xml/.csv/.sql` it calls `odoo.tools.convert_file(...)` to load records;
  it walks `<module>/static` and stores **every static file as a base64
  `ir.attachment`** (`url='/<module>/…'`, served from the DB not disk), stores `.po`
  files for webclient translation, and turns manifest `assets` into `ir.asset` rows
  (glob wildcards rejected). Each gets an `ir.model.data` row for clean uninstall.
  (code-read)
- **`/base_import_module/login_upload` + force:** `auth='none'`, POST, `csrf=False`,
  `save_session=False`. Authenticates inline from posted `login`/`password`, and
  only if `request.env.uid` is set (None under MFA) **and** the user `_is_admin()`
  does it call `_import_zipfile(mod_file, force=force=='1')`; otherwise `AccessError`
  → HTTP 500. The scriptable/CI counterpart to the wizard; `force='1'` ⇒ mode
  `init` (re-init `noupdate` records), else mode `update`. (code-read)
- **Lifecycle overrides:** `module_uninstall` captures imported modules **before**
  super() and `unlink()`s them (they can't be reinstalled — data files are gone);
  `button_upgrade` reverts imported modules pushed to `to upgrade` back to
  `installed`; `_get_modules_to_load_domain` excludes imported modules from boot
  load. (code-read)

## 5. IT architecture

- **Application:** runtime module-deployment tool — unpack + dependency-order +
  register an uploaded module into the live DB, load its data/static/i18n, and
  govern its uninstall/upgrade lifecycle.
- **Software services:** `/base_import_module/login_upload` (HTTP admin upload);
  RPC `base.import.module.import_module`; `ir.module.module._import_zipfile` /
  `_import_module`; `button_immediate_install_app` / `_get_modules_from_apps`
  (industries data modules).
- **Data objects:** `base.import.module`, `ir.module.module` (extended).
- **Information flows:** UI wizard → `import_module` → `_import_zipfile` →
  per-module `_import_module` → `convert_file` + `ir.attachment`/`ir.asset`/
  `ir.model.data`; HTTP/CI path via `login_upload`; outbound `requests` to
  `https://apps.odoo.com` to list/download industries data modules. Depends on `web`.

## 6. Business architecture

- **Capabilities (inferred):** import a module from a zip/folder at runtime;
  validate/size-cap/dependency-order an archive; register it as `imported`;
  load its data/static/i18n/assets into the DB; browse + install industries data
  modules; govern the imported-module lifecycle; HTTP upload for CI deployment.
- **Value streams (inferred):** Zip-to-Installed-Module (upload → validate →
  topo-sort → register + load → `installed` → redirect `/odoo`); Industry-App
  (browse apps.odoo.com → download → import); CI-Deploy (POST `login_upload`).
- **Information concepts (auto):** import wizard session, `ir.module.module.imported`,
  `module_type`, imported-module attachments, import result / missing-deps message.
- **Organization (auto):** `base.group_system` (admin) — the only access; all paths
  also require `is_admin()`. **Products (auto):** none.
- **Policies (inferred):** admin-only gating; `.zip`-only, 100MB/entry cap; Studio
  modules need `web_studio`; imported modules excluded from boot load, not
  upgradable, deleted on uninstall; no glob wildcards in asset paths; MFA users
  blocked from the upload endpoint.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Runtime module-deployment tooling — firm IT
  infrastructure (Porter support activity; Stabell & Fjeldstad "support"). It
  creates no primary value in any chain/shop/network and owns no business object;
  its only persistent footprint is bookkeeping on `ir.module.module`. It acts on
  the platform itself, provisioning uploaded modules into the running database;
  `auto_install=true`, depends only on `web`.
- **APQC: 8.0 Manage Information Technology.** The work is application deployment /
  change management — taking a packaged module and provisioning it into the running
  platform. 13.0 "Develop and Manage Business Capabilities" was considered (runtime
  import underpins onboarding industry capabilities) but rejected: this is a
  concrete running deployment utility, not a governance/portfolio capability —
  squarely 8.0. Mirrors the `base_import` and `web` classifications.

## 8. Fit-to-Standard

- **Standard:** upload a `.zip` module and install it into the running DB (no
  restart); multi-module dependency-ordered import with auto-install of known deps;
  force-init re-load of `noupdate` records; store static/i18n/assets in the DB;
  browse + install industries data modules from apps.odoo.com; authenticated HTTP
  upload for CI; auto-delete imported modules on uninstall.
- **Typical fits:** deploying Studio/industry/data modules without filesystem access
  (SaaS/Odoo.sh); CI pushing a built `.zip` via `login_upload`; loading an industry
  configuration pack (optionally with demo data).
- **Common gaps:** imported modules can't be upgraded via the standard flow; only
  `.xml/.csv/.sql` + static/i18n loaded (no executable Python from the DB); no
  state/version reconciliation if the module later appears on the addons-path;
  100MB/entry cap and admin-only gating; Studio modules need `web_studio`.
- **Drive hints:** `odoo shell`
  `env['ir.module.module']._import_zipfile(open('/path/mod.zip','rb'), force=False)`;
  `…search([('imported','=',True)]).mapped('name')`; `curl -F login=admin -F
  password=admin -F mod_file=@mod.zip .../base_import_module/login_upload`; UI
  (debug): Settings → Technical → Import Module → upload `.zip` → Install.
