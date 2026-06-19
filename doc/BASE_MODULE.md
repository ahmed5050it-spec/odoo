# Odoo `base` Module — Deep Dive

> **The `base` module** (`odoo/addons/base/`) is the foundational module of Odoo.
> It is `auto_install=True`, has **no dependencies** (`depends = []`), and is **always
> loaded first** (phase 0). Every other module — all 624 of them — depends on it,
> directly or transitively. This document maps its models, data, and responsibilities.

---

## 1. Why `base` is Special

| Property | Value | Meaning |
|----------|-------|---------|
| `depends` | `[]` (empty) | The **only** module with no dependencies. The "drain" of the dependency graph. |
| `auto_install` | `True` | Installed automatically on every new database. |
| `category` | `Hidden` | Not shown as a user-facing app. |
| `version` | `1.3` → normalized to `19.0.1.3` | Core version. |
| Load phase | **0** | Loaded before all other modules. |
| Data files | **65** | Bootstraps currencies, countries, languages, base security, cron jobs. |

The `base` module provides:
1. **The ORM's "system tables"** — the `ir.*` (Information Repository) models that
   describe models, fields, views, actions, security, cron, etc.
2. **The core business entities** — the `res.*` (Resource) models: partners, users,
   companies, countries, currencies, languages.
3. **Foundational mixins** — reusable behaviors (`image.mixin`, `avatar.mixin`, …).
4. **Bootstrap data** — world currencies, all countries & states, languages, base
   security groups, system cron jobs.

---

## 2. Module Layout

```
odoo/addons/base/
├── __init__.py
├── __manifest__.py          # name=Base, depends=[], auto_install=True, 65 data files
│
├── models/                  # ~45 model files (see §3, §4)
│   ├── ir_*.py              # technical framework models (ir.model, ir.ui.view, …)
│   ├── res_*.py             # business resource models (res.partner, res.users, …)
│   └── *_mixin.py           # reusable mixins (image, avatar, address, vat)
│
├── data/                    # 65 data files (bootstrap)
│   ├── res_currency_data.xml    # world currencies
│   ├── res_country_data.xml     # all countries
│   ├── res.country.state.csv    # states/provinces
│   ├── res.lang.csv             # languages
│   ├── ir_cron_data.xml         # system scheduled jobs
│   ├── res_users_data.xml       # admin / public users
│   ├── base_data.sql            # raw SQL bootstrap
│   └── …                        # + demo data files
│
├── security/                # ir.model.access.csv, base_groups.xml, base_security.xml
├── views/                   # backend views for all base models
├── wizard/                  # 8 transient wizards (module upgrade, lang install, …)
├── report/                  # base report definitions
├── rng/                     # RelaxNG schemas for XML validation
├── i18n/                    # translations
└── tests/                   # framework-level tests
```

---

## 3. The `ir.*` Models — Technical Framework ("Information Repository")

These models *are* the ORM's metadata and runtime infrastructure. They describe and
control how Odoo itself works. ~80 models total.

### 3.1 Meta-models (the ORM describing itself)

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.model` | `ir_model.py` | One record per Odoo model. The registry, persisted. |
| `ir.model.fields` | `ir_model.py` | One record per field of every model. |
| `ir.model.fields.selection` | `ir_model.py` | Selection field options. |
| `ir.model.constraint` | `ir_model.py` | SQL constraints declared by models. |
| `ir.model.relation` | `ir_model.py` | M2M relation tables. |
| `ir.model.access` | `ir_model.py` | **ACLs** — per-model CRUD rights per group. |
| `ir.model.data` | `ir_model.py` | **XML-IDs** — maps `module.xml_id` → (model, db id). Powers external references, upgrades, uninstall. |
| `ir.model.inherit` | `ir_model.py` | Tracks model inheritance relationships. |
| `base`, `_unknown` | `ir_model.py` | Abstract sentinel models. |

> **`ir.model.data` is critical:** Every record created from an XML/CSV data file gets
> an entry here. This is how Odoo knows which records belong to which module (for
> upgrade/uninstall), and how `ref="module.xml_id"` resolves.

### 3.2 UI & views

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.ui.view` | `ir_ui_view.py` | View definitions (form, list, kanban, search, …) as QWeb/XML arch. |
| `ir.ui.view.custom` | `ir_ui_view.py` | Per-user view customizations. |
| `ir.ui.menu` | `ir_ui_menu.py` | Menu tree (app menus, submenus). |
| `ir.qweb` | `ir_qweb.py` | The **QWeb template engine** — renders XML templates to HTML. |
| `ir.qweb.field.*` | `ir_qweb_fields.py` | ~25 field renderers (date, monetary, image, contact, …) for QWeb `t-field`. |
| `ir.asset` | `ir_asset.py` | Asset bundle declarations (JS/CSS). |

### 3.3 Actions (what buttons/menus do)

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.actions.actions` | `ir_actions.py` | Base action model. |
| `ir.actions.act_window` | `ir_actions.py` | Open a view/window action (most common). |
| `ir.actions.act_url` | `ir_actions.py` | Open a URL. |
| `ir.actions.server` | `ir_actions.py` | Server-side Python/automation action. |
| `ir.actions.client` | `ir_actions.py` | Client-side (JS) action. |
| `ir.actions.report` | `ir_actions_report.py` | Report generation (PDF/HTML via QWeb). |
| `ir.actions.todo` | `ir_actions.py` | Configuration wizard sequencing. |
| `ir.embedded.actions` | `ir_embedded_actions.py` | Embedded sub-actions in views. |

### 3.4 Runtime services

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.cron` | `ir_cron.py` | **Scheduled actions** (the cron scheduler). |
| `ir.cron.trigger` | `ir_cron.py` | One-shot cron triggers. |
| `ir.cron.progress` | `ir_cron.py` | Cron execution progress tracking. |
| `ir.http` | `ir_http.py` | HTTP routing, authentication, request dispatch hooks. |
| `ir.mail_server` | `ir_mail_server.py` | Outgoing SMTP server config & sending. |
| `ir.sequence` | `ir_sequence.py` | Auto-numbering sequences (e.g., invoice numbers). |
| `ir.sequence.date_range` | `ir_sequence.py` | Per-period sequence ranges. |
| `ir.attachment` | `ir_attachment.py` | **File storage** — binary attachments, filestore management. |
| `ir.binary` | `ir_binary.py` | Binary field serving (images, downloads). |
| `ir.config_parameter` | `ir_config_parameter.py` | System-wide key/value settings. |
| `ir.default` | `ir_default.py` | Default field values (per company/user/condition). |
| `ir.logging` | `ir_logging.py` | Persisted log entries. |
| `ir.profile` | `ir_profile.py` | Performance profiling records. |

### 3.5 Security & rules

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.rule` | `ir_rule.py` | **Record rules** — row-level access (domain-based filters per group). |
| `ir.model.access` | `ir_model.py` | Model-level ACLs (read/write/create/unlink per group). |

### 3.6 Module management

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.module.module` | `ir_module.py` | One record per available module; tracks install state. |
| `ir.module.module.dependency` | `ir_module.py` | Module dependency records. |
| `ir.module.category` | `ir_module.py` | App categories. |
| `ir.module.module.exclusion` | `ir_module.py` | Mutually-exclusive modules. |

### 3.7 Import/Export & misc

| Model | File | Responsibility |
|-------|------|----------------|
| `ir.exports` / `ir.exports.line` | `ir_exports.py` | Saved export field lists. |
| `ir.fields.converter` | `ir_fields.py` | Import data type conversion. |
| `ir.filters` | `ir_filters.py` | Saved search filters. |
| `ir.autovacuum` | `ir_autovacuum.py` | Periodic cleanup orchestration (`@api.autovacuum`). |
| `ir.demo` / `ir.demo_failure` | `ir_demo*.py` | Demo data install tracking. |
| `decimal.precision` | `decimal_precision.py` | Configurable decimal rounding per domain. |
| `report.layout`, `report.paperformat` | `report_*.py` | Report page formats. |

---

## 4. The `res.*` Models — Business Resources

These are the foundational **business** entities every ERP needs. ~30 models.

### 4.1 Parties & organization

| Model | File | Responsibility |
|-------|------|----------------|
| `res.partner` | `res_partner.py` | **The central contact model.** Customers, vendors, companies, individuals, addresses. Referenced by nearly every business document. |
| `res.partner.category` | `res_partner.py` | Partner tags. |
| `res.partner.industry` | `res_partner.py` | Industry classification. |
| `res.partner.bank` | `res_bank.py` | Partner bank accounts. |
| `res.bank` | `res_bank.py` | Bank master records. |
| `res.company` | `res_company.py` | **Companies** — multi-company support. Every record can be company-scoped. |

### 4.2 Users & access

| Model | File | Responsibility |
|-------|------|----------------|
| `res.users` | `res_users.py` | **Users** — login, password, groups. Inherits from `res.partner` (a user *is* a partner). |
| `res.groups` | `res_groups.py` | **Security groups** — the unit of access control. |
| `res.groups.privilege` | `res_groups_privilege.py` | Group privilege categorization. |
| `res.users.log` | `res_users.py` | Login history. |
| `res.users.settings` | `res_users_settings.py` | Per-user UI/app settings. |
| `res.users.apikeys` | `res_users.py` | API key authentication. |
| `res.users.deletion` | `res_users_deletion.py` | GDPR user deletion tracking. |
| `res.device` / `res.device.log` | `res_device.py` | Logged-in device/session tracking. |

### 4.3 Localization reference data

| Model | File | Responsibility |
|-------|------|----------------|
| `res.country` | `res_country.py` | Countries (ISO codes, formats). |
| `res.country.state` | `res_country.py` | States/provinces. |
| `res.country.group` | `res_country.py` | Country groupings (e.g., EU). |
| `res.currency` | `res_currency.py` | Currencies. |
| `res.currency.rate` | `res_currency.py` | Exchange rates over time. |
| `res.lang` | `res_lang.py` | Languages (locale, date/number formats, direction). |

### 4.4 Configuration

| Model | File | Responsibility |
|-------|------|----------------|
| `res.config` | `res_config.py` | Base config wizard. |
| `res.config.settings` | `res_config.py` | **Settings framework** — the base class for every module's Settings panel (transient model). |

---

## 5. Foundational Mixins

`base` defines reusable `AbstractModel` mixins that other models inherit via `_inherit`:

| Mixin | File | Adds |
|-------|------|------|
| `image.mixin` | `image_mixin.py` | `image_1920` + auto-resized variants (`image_128`, `image_512`, …). |
| `avatar.mixin` | `avatar_mixin.py` | Avatar image (extends image.mixin) with default colored avatar. |
| `format.address.mixin` | `res_partner.py` | Country-specific address formatting. |
| `format.vat.label.mixin` | `res_partner.py` | Country-specific VAT label. |
| `properties.base.definition.mixin` | `properties_base_definition_mixin.py` | Dynamic "properties" fields support. |

**Example usage in another module:**
```python
class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['image.mixin']   # ← inherits image_1920, image_128, etc.
```

---

## 6. Bootstrap Data (the 65 data files)

When `base` installs, it loads foundational reference data that the entire system needs:

| Data file | Loads |
|-----------|-------|
| `base_data.sql` | Raw SQL bootstrap (initial rows before ORM is fully up). |
| `res_currency_data.xml` | All world currencies (USD, EUR, …). |
| `res_country_data.xml` | All ~250 countries with ISO codes. |
| `res.country.state.csv` | States/provinces (US states, etc.). |
| `res.lang.csv` | Available languages with locale formats. |
| `res_lang_data.xml` | Default language (en_US) setup. |
| `res_company_data.xml` | The default "My Company". |
| `res_users_data.xml` | **admin** user + **public** user + **__system__** (superuser). |
| `res_partner_data.xml` | Default partners (company, admin contact). |
| `ir_cron_data.xml` | System scheduled jobs (autovacuum, mail queue, …). |
| `ir_config_parameter_data.xml` | Default system parameters (db uuid, etc.). |
| `ir_module_category_data.xml` | App category tree. |
| `report_paperformat_data.xml` | Standard paper formats (A4, Letter). |

Plus demo variants (`*_demo.xml`) loaded only when demo data is enabled.

> **The three system users** created here are foundational:
> - `base.user_admin` — the Administrator.
> - `base.public_user` — anonymous/website visitors.
> - `base.user_root` (`__system__`, id=1) — the superuser (`SUPERUSER_ID`), bypasses all access checks.

---

## 7. Wizards (Transient Models)

`base/wizard/` holds 8 transient (in-memory) wizards for administration:

| Wizard | Purpose |
|--------|---------|
| `base.module.upgrade` | Apply pending module upgrades. |
| `base.module.uninstall` | Uninstall a module (+ show impact). |
| `base.module.update` | Refresh the module list from disk. |
| `base.language.install` | Install a new language. |
| `base.language.export` | Export translations (.po). |
| `base.language.import` | Import translations. |
| `base.partner.merge` | Merge duplicate partners. |
| `wizard.ir.model.menu.create` | Auto-generate menu for a model. |

---

## 8. How `base` Bootstraps a Database

```
New database creation (service/db.py)
  │
  ├─ _create_empty_database()      ← CREATE DATABASE
  │
  └─ Registry.new(db, update_module=True)
      │
      ├─ load 'base' first (phase 0)
      │   │
      │   ├─ load_openerp_module('base')
      │   │   └─ import all base/models/*.py
      │   │       └─ ir.model, ir.model.fields, res.partner, res.users, … registered
      │   │
      │   ├─ create core tables (ir_model, ir_model_fields, res_partner, res_users, …)
      │   │
      │   ├─ load base/data/*.xml (65 files):
      │   │   ├─ currencies, countries, states, languages
      │   │   ├─ admin / public / __system__ users
      │   │   ├─ default company
      │   │   ├─ base security groups
      │   │   └─ system cron jobs
      │   │
      │   └─ mark base as 'installed'
      │
      └─ load remaining modules (phase 1+)
          (web, then account, sale, … — all depending on base)
```

Once `base` is installed, the database has:
- A working ORM metadata layer (`ir.model`, `ir.model.fields`).
- The XML-ID registry (`ir.model.data`) for cross-references.
- Security primitives (`res.groups`, `ir.model.access`, `ir.rule`).
- Core business entities (partners, users, companies).
- World reference data (currencies, countries, languages).
- The QWeb engine, action system, cron scheduler, and attachment store.

---

## 9. Mental Model: `ir.*` vs `res.*`

```
┌─────────────────────────────────────────────────────────────┐
│  ir.*  =  "Information Repository"  =  THE FRAMEWORK ITSELF   │
│                                                               │
│  How Odoo works: models, fields, views, actions, menus,       │
│  security, cron, modules, QWeb, attachments, sequences.       │
│  → Mostly invisible to end users. Used BY the framework.      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  res.*  =  "Resource"  =  CORE BUSINESS ENTITIES             │
│                                                               │
│  What every business needs: partners, users, companies,       │
│  countries, currencies, languages, banks.                     │
│  → Visible & extended by every business module.               │
└─────────────────────────────────────────────────────────────┘
```

**Rule of thumb:**
- A field like `model_id` → `ir.model` (a reference to framework metadata).
- A field like `partner_id` → `res.partner` (a reference to a business entity).

Every other module builds on these two families: `account` adds `account.move`
referencing `res.partner` and `res.currency`; `sale` adds `sale.order` referencing
`res.partner` and `res.users`; and so on.

---

## 10. Summary

The `base` module is the **kernel** of Odoo:

1. **No dependencies, always first** — it's the root of the dependency graph.
2. **Defines the ORM's self-description** — `ir.model` & `ir.model.fields` make the
   framework introspectable and extensible.
3. **Provides the XML-ID system** — `ir.model.data` enables external references,
   modular upgrades, and clean uninstalls.
4. **Implements security primitives** — `res.groups`, `ir.model.access`, `ir.rule`.
5. **Ships core business entities** — `res.partner`, `res.users`, `res.company`.
6. **Bundles world reference data** — currencies, countries, languages.
7. **Hosts runtime services** — cron, mail server, attachments, sequences, QWeb,
   HTTP routing hooks.

Without `base`, there is no Odoo. Every one of the other 624 modules extends models
defined here, references its data, or relies on its services.

---

*Source: inspection of `odoo/addons/base/` in Odoo 19.0 (~45 model files, ~110 models,
65 data files, 8 wizards).*
