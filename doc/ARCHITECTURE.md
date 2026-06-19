# Odoo Architecture (Reverse-Engineered Reference)

> **Scope:** This document is a reverse-engineering map of the Odoo **19.0** codebase
> in this repository. It describes the core framework (`odoo/`), the addon/module
> system (`addons/`), and how a request flows through the system end to end.
> It is meant as an onboarding and architecture-review reference — not official docs.
>
> **Source of truth:** version is declared in `odoo/release.py`
> (`version_info = (19, 0, 0, FINAL, 0, '')`, requires Python 3.10–3.14, PostgreSQL ≥ 13).

---

## 1. The Big Picture

Odoo is a modular, web-based ERP framework. Three ideas define its architecture:

1. **Everything is a module (addon).** Even the kernel (`base`) is an addon. Features
   are packaged as self-contained modules under `addons/` that declare dependencies
   and are loaded in dependency order into a per-database **Registry**.
2. **Everything is a model.** Business logic lives on ORM **Models** backed by
   PostgreSQL tables. The ORM (`odoo/orm/`) provides records, fields, computed values,
   constraints, and access control.
3. **Everything runs inside an Environment.** Every operation carries an `Environment`
   (database cursor + user + context), which is the gateway to models, the cache, and
   the transaction.

```
                         ┌──────────────────────────────────────┐
        HTTP / RPC  ───▶ │  odoo/http.py  (WSGI Application)     │
        clients          │  routing · sessions · auth · dispatch │
                         └───────────────┬──────────────────────┘
                                         │
                         ┌───────────────▼──────────────────────┐
        CLI / shell ───▶ │  odoo/service/  (server, model, db)   │
                         │  workers · cron · RPC · retry logic   │
                         └───────────────┬──────────────────────┘
                                         │  Environment(cr, uid, ctx)
                         ┌───────────────▼──────────────────────┐
                         │  odoo/orm/  (ORM kernel)              │
                         │  Registry · BaseModel · Field · Domain│
                         └───────────────┬──────────────────────┘
                                         │
                         ┌───────────────▼──────────────────────┐
                         │  odoo/sql_db.py  (psycopg pool/cursor)│
                         │           PostgreSQL                  │
                         └──────────────────────────────────────┘

   odoo/modules/  builds the Registry by loading addons in dependency order.
```

---

## 2. Repository Layout

| Path | Responsibility |
|------|----------------|
| `odoo-bin` | Executable entry point — runs `odoo/__main__.py`. |
| `odoo/__main__.py` | Three lines: `from .cli.command import main; main()`. |
| `odoo/cli/` | Command-line subcommands (`server`, `shell`, `db`, `scaffold`, …). |
| `odoo/service/` | Server bootstrap, worker models, DB management, RPC dispatch, cron. |
| `odoo/http.py` | WSGI `Application`, `Request`/`Response`, `Controller`, `route()`. |
| `odoo/orm/` | The ORM kernel: models, fields, registry, environment, domains. |
| `odoo/api/` | Public API surface / decorators re-exported as `odoo.api`. |
| `odoo/modules/` | Module discovery, manifest parsing, dependency graph, loading. |
| `odoo/sql_db.py` | PostgreSQL connection pooling and cursor abstraction. |
| `odoo/tools/` | Utilities (config, convert, translation, misc helpers). |
| `odoo/tests/` | Test framework base classes (`TransactionCase`, `HttpCase`, …). |
| `odoo/release.py` | Version, supported Python/PostgreSQL ranges, product metadata. |
| `addons/` | ~625 feature modules (the full Odoo app suite, including `base`). |
| `setup/`, `debian/`, `doc/` | Packaging, OS integration, documentation. |

---

## 3. Bootstrap & Startup Flow

```
odoo-bin
  └─ odoo/__main__.py
      └─ cli.command.main()
          ├─ parse --addons-path, pick command (default: "server")
          ├─ find_command(name)        # internal + addon-provided commands
          └─ command.run(args)
              └─ cli/server.py
                  ├─ tools.config.parse_config(args)   # CLI + file + env
                  ├─ (optionally create empty database)
                  └─ service.server.start(preload=dbs, stop=stop_after_init)
                      ├─ instantiate WSGI app (http.Application)
                      ├─ choose worker model (threaded / gevent / prefork)
                      ├─ for each DB: Registry.new(db, update_module=True)
                      │     └─ modules.loading.load_module_graph()
                      │           └─ per module (in dependency order):
                      │                load_openerp_module()  # import Python
                      │                registry.load()        # register models
                      │                init schema, run hooks, load data files
                      ├─ bind Werkzeug HTTP server
                      └─ event loop: serve requests + run cron
```

**Key startup files:** `odoo/cli/command.py`, `odoo/cli/server.py`,
`odoo/service/server.py`, `odoo/modules/loading.py`, `odoo/orm/registry.py`.

The CLI auto-discovers subcommands from `odoo/cli/*.py` **and** from any addon that
ships an `addons/<module>/cli/` package, so modules can extend the command set.

---

## 4. The ORM Kernel (`odoo/orm/`)

The ORM is the heart of the framework. Business code subclasses `models.Model` and
manipulates **recordsets** rather than rows.

### 4.1 Core classes

| Class | File | Role |
|-------|------|------|
| `BaseModel` | `orm/models.py` | Base for all models: CRUD, search, read_group, validation, recordset semantics. |
| `Model` | `orm/models.py` | Standard persistent model (has a DB table). |
| `AbstractModel` | `orm/models.py` | Non-persistent base for mixins/shared behavior. |
| `TransientModel` | `orm/models.py` | "Wizard" models — short-lived rows, auto-vacuumed. |
| `MetaModel` | `orm/models.py` | Metaclass that assembles the final model class from all module contributions. |
| `Field` | `orm/fields*.py` | Descriptor base; one subclass per field type. |
| `Environment` | `orm/environments.py` | `(cr, uid, context)` execution context; gateway to models/cache. |
| `Transaction` | `orm/environments.py` | Per-database transaction state shared by environments. |
| `Registry` | `orm/registry.py` | Per-database map of model name → assembled model class; owns the cache and schema. |
| `Domain` | `orm/domains.py` | Search-filter DSL (`[('field', 'op', value)]`). |
| `Command` | `orm/commands.py` | Factory for relational writes (create/link/unlink/set/clear). |

### 4.2 Records, recordsets & the Environment

- A recordset is an *ordered collection of records of one model* bound to an
  `Environment`. `len`, iteration, slicing, and set operations all work on it.
- `self.env` exposes the environment from any model method: `self.env[model_name]`,
  `self.env.cr` (cursor), `self.env.user`, `self.env.context`, `self.env.company`.
- The **cache** lives on the environment/transaction; field reads are batched via
  **prefetching** so iterating a recordset doesn't issue N queries.

### 4.3 Fields

Fields are Python descriptors; each type lives in a focused module:

| Module | Field types |
|--------|-------------|
| `orm/fields_misc.py` | `Id`, `Boolean`, `Json` |
| `orm/fields_numeric.py` | `Integer`, `Float`, `Monetary` |
| `orm/fields_textual.py` | `Char`, `Text`, `Html` |
| `orm/fields_temporal.py` | `Date`, `Datetime` |
| `orm/fields_selection.py` | `Selection` |
| `orm/fields_relational.py` | `Many2one`, `One2many`, `Many2many` |
| `orm/fields_reference.py` | `Reference`, `Many2oneReference` |
| `orm/fields_binary.py` | `Binary`, `Image` |
| `orm/fields_properties.py` | `Properties`, `PropertiesDefinition` |

Fields can be **stored** (a real column) or **computed** (`compute=`), and computed
fields may be made stored + searchable. Recomputation is driven by `@api.depends`.

### 4.4 Decorators (`odoo/orm/decorators.py`, exposed via `odoo.api`)

| Decorator | Meaning |
|-----------|---------|
| `@api.depends(*fields)` | Declares dependencies of a computed field → auto-recompute. |
| `@api.constrains(*fields)` | Python validation run on create/write; raise `ValidationError`. |
| `@api.onchange(*fields)` | Form-side reaction when a field changes (UI only). |
| `@api.model` | Method bound to the model, not to records (no recordset). |
| `@api.model_create_multi` | `create()` receives a list of dicts → batch creation. |
| `@api.depends_context(*keys)` | Computed value also depends on context keys. |
| `@api.ondelete(at_uninstall=…)` | Guard logic run before `unlink`. |
| `@api.private` | Method is not callable over RPC. |
| `@api.autovacuum` | Hook invoked periodically by the autovacuum cron. |

### 4.5 Inheritance models (a defining Odoo trait)

- **Classical inheritance** (`_inherit = 'model'`, same `_name`): extend an existing
  model in place — add fields, override methods. The `MetaModel` merges every module's
  contributions for a given `_name` into one class.
- **Prototype/delegation** (`_inherits = {'other.model': 'field_id'}`): compose by
  embedding another model via a `Many2one`.
- **Mixins** (`AbstractModel`): reusable behavior pulled in via `_inherit`.

This is why a model's final behavior is the *sum of all installed modules* that touch
it — you must think in terms of the assembled class, not a single file.

---

## 5. Module / Addon System (`odoo/modules/`)

Addons are the unit of packaging, dependency, and deployment.

| File | Role |
|------|------|
| `modules/module.py` | Locate modules, parse `__manifest__.py` (`Manifest`), import code. |
| `modules/module_graph.py` | `ModuleGraph` — topological sort of dependencies from `base`. |
| `modules/loading.py` | `load_module_graph()` orchestrates the whole load: code → models → schema → data → hooks. |
| `modules/db.py` | Track module install state in the database. |
| `modules/migration.py` | `MigrationManager` runs pre-/post- migration scripts on upgrade. |

### 5.1 Loading sequence (per module, in dependency order)

1. `load_openerp_module()` imports the module's Python (model classes get registered).
2. `registry.load()` assembles/updates model classes and `init_models()` creates or
   alters tables, columns, constraints, and indexes.
3. `pre_init_hook` (if declared) runs before data.
4. Data files from the manifest `data` (and `demo` if enabled) are loaded via the
   XML/CSV converter.
5. `post_init_hook` (if declared) runs after data.
6. Migration scripts run when the installed version differs from the manifest version.

### 5.2 Anatomy of an addon

```
addons/<module>/
├── __init__.py            # imports models/, controllers/, wizard/, hooks
├── __manifest__.py        # REQUIRED metadata (see below)
├── models/                # ORM models (business logic)
├── views/                 # XML: form/list/kanban/search views, menus, actions
├── controllers/           # http.Controller subclasses (web/HTTP/JSON routes)
├── security/              # ir.model.access.csv + record rules (XML)
├── data/                  # XML/CSV data loaded on install
├── demo/                  # demo data (only with --without-demo off)
├── static/                # JS/CSS/SCSS/owl assets + frontend tests
├── wizard/                # TransientModel + their views
├── report/                # QWeb report definitions and templates
├── tests/                 # Python tests (TransactionCase, HttpCase, …)
└── i18n/                  # <lang>.po translation catalogs
```

### 5.3 The manifest (`__manifest__.py`)

A single dict describing the module. The most important keys:

| Key | Meaning |
|-----|---------|
| `name`, `version`, `category`, `summary` | Identity & catalog metadata. |
| `depends` | Modules that must load first (drives the dependency graph). |
| `data` | XML/CSV files loaded on install/update (order matters). |
| `demo` | Demo-only data files. |
| `assets` | Frontend bundles (JS/CSS/SCSS) wired into asset bundles. |
| `installable`, `auto_install`, `application` | Visibility & install behavior. |
| `external_dependencies` | Required `python`/`bin` packages. |
| `pre_init_hook`, `post_init_hook`, `uninstall_hook` | Lifecycle callbacks. |
| `license`, `author` | Legal/attribution (`base` is LGPL-3). |

`base` is the only `auto_install` kernel module and is always loaded first.

---

## 6. HTTP / Web Layer (`odoo/http.py`)

The WSGI front door. One `Application` object is the WSGI callable for all traffic.

### 6.1 Request routing

`Application.__call__` classifies each request and serves it through one of three paths:

- **`_serve_static`** — `/<module>/static/...` files, served without a DB.
- **`_serve_nodb`** — routes that don't need a database (e.g. DB manager).
- **`_serve_db`** — opens the registry + cursor, builds an `Environment`, runs
  authentication, then dispatches to the matched controller. The transaction is
  committed or rolled back around the handler.

### 6.2 Controllers & routes

```python
class MyController(http.Controller):
    @http.route('/my/endpoint', auth='user', type='http', methods=['GET'])
    def handler(self, **kw):
        return request.render('module.template', {...})
```

`@route(...)` parameters:

| Param | Values / meaning |
|-------|------------------|
| `auth` | `user` (logged in), `public` (anonymous allowed), `none` (no env). |
| `type` | `http` (HTML/forms/files) or `json` (JSON-RPC body). |
| `methods` | Allowed HTTP verbs. |
| `csrf` | CSRF protection for state-changing HTTP routes. |
| `website`, `sitemap` | Website integration flags. |

### 6.3 Dispatch lifecycle

```
Application.__call__
  → Request._serve_db
      → ir.http._match()          # find route across installed modules
      → ir.http._authenticate()   # apply auth= policy, set env user
      → Dispatcher.pre_dispatch()
      → Dispatcher.dispatch()  →  @route handler  →  Response
      → Dispatcher.post_dispatch()
```

Routing is itself extensible: `ir.http` is an ORM model, so addons can hook into
matching, authentication, and rendering.

---

## 7. Service Layer (`odoo/service/`)

Glue between the network/CLI and the ORM.

| File | Role |
|------|------|
| `service/server.py` | `start()` — worker models (threaded / gevent / **prefork** multiprocess), HTTP binding, the **cron** scheduler, graceful signal handling, file-watch auto-reload, memory/CPU limits. |
| `service/model.py` | RPC dispatch (`execute_kw`, `call_kw`) and **`retrying()`** — re-runs a transaction with backoff on serialization/concurrency failures. |
| `service/db.py` | Create/drop/duplicate/backup/restore databases; bootstrap a new DB (install `base`, create admin, load languages). |
| `service/common.py`, `service/security.py` | Version/auth helper services and password verification. |

**Concurrency model:** Odoo serves requests with one cursor/transaction per request.
Because PostgreSQL can raise serialization errors under concurrency, `retrying()`
catches them, rolls back, resets the environment, and retries with exponential backoff
(bounded). This is why handlers must be **idempotent within a transaction**.

---

## 8. Database Layer (`odoo/sql_db.py`)

| Class / function | Role |
|------------------|------|
| `db_connect()` | Returns a `Connection` for a database, backed by a per-DB pooled connection set. |
| `ConnectionPool` | Thread-safe pool: checkout/return, idle recycling, size limits. |
| `BaseCursor` / `Cursor` | psycopg cursor wrapper: parameterized queries (SQL-injection-safe), query logging/metrics, savepoint helpers. |
| `Savepoint` | Context manager for nested transactions (rollback on error, release on success). |

The ORM never talks to psycopg directly in business code — it goes through
`self.env.cr`, which is a `Cursor`. Savepoints back the `with self.env.cr.savepoint()`
pattern used for partial rollbacks (e.g. per-row import tolerance).

---

## 9. CLI (`odoo/cli/`)

| Command | Purpose |
|---------|---------|
| `server` | Start the server (default command). |
| `shell` | Interactive Python REPL with a live `env`. |
| `db` | Database create/drop/list operations. |
| `scaffold` | Generate a skeleton addon. |
| `populate` | Generate volume/demo data for performance testing. |
| `i18n` | Import/export translations. |
| `cloc` | Count lines of code (for app/customization sizing). |
| `neutralize` | Sanitize a DB copy (disable mail, crons, external calls). |
| `deploy`, `obfuscate`, `upgrade_code`, `help` | Deployment, code protection, code migration, help. |

`cli/command.py` discovers both internal commands and addon-contributed ones.

---

## 10. Data & Security Model

- **Data files** (`data/*.xml|csv`) declare records loaded at install/update.
  XML records carry XML-IDs (`module.identifier`) tracked in `ir.model.data`, enabling
  idempotent upgrades and cross-module references (`ref="base.USD"`).
- **Access control** has two layers:
  - `security/ir.model.access.csv` — coarse per-model CRUD rights per group.
  - **Record rules** (`ir.rule`) — row-level domains (e.g. "only own records",
    multi-company isolation), applied automatically to every search/read.
- **Groups** (`res.groups`) gate menus, fields, and access rights.
- `SUPERUSER_ID` / `sudo()` bypass these checks — used deliberately in trusted code.

---

## 11. Frontend (where it lives)

The Python backend renders server-side via **QWeb** templates (`*.xml`) for reports and
website pages, while the web client is an **OWL** (Odoo Web Library) JS application whose
sources live under each addon's `static/` and are wired into **asset bundles** declared
in the manifest's `assets` key. The backend exposes data to the client through the
`json`/`call_kw` RPC path described in §6–§7.

---

## 12. Cross-Cutting: How a Click Becomes a Database Write

1. Browser calls a `json` route (`call_kw`) targeting `model.method`.
2. `http.Application._serve_db` opens a registry + cursor, builds the `Environment`,
   authenticates the user.
3. `service.model.call_kw` resolves the model from the **Registry** and invokes the
   method on a recordset, all wrapped by `retrying()`.
4. The method uses fields/recordsets; the ORM batches reads via the cache/prefetch and
   queues writes; `@api.depends` triggers recomputation; `@api.constrains` validates.
5. Access rights and record rules are enforced on every read/write.
6. On success the cursor commits; on a serialization error the transaction is retried;
   on a business error it rolls back and the exception is returned to the client.

---

## 13. Subsystem Dependency Summary

| Layer | Depends on | Consumed by |
|-------|-----------|-------------|
| `sql_db` | psycopg / PostgreSQL | ORM, Environment, everything DB-bound |
| `orm` (models/fields) | `sql_db`, decorators | All business code |
| `orm.Registry` | `modules`, model classes | `Environment`, services |
| `modules` | module graph, converters | Registry construction |
| `http` | `Environment`, `service.model` | External web/RPC clients |
| `service` | Registry, Environment, http | CLI, network server |
| `cli` | service, `tools.config` | Operator / shell entry point |

---

## 14. Where to Look First (cheat sheet)

| You want to understand… | Start here |
|--------------------------|-----------|
| How a model behaves | `addons/<m>/models/*.py` + every `_inherit` of that `_name` |
| What a module installs | `addons/<m>/__manifest__.py` (`depends`, `data`) |
| Recordset / field semantics | `odoo/orm/models.py`, `odoo/orm/fields*.py` |
| Search filters | `odoo/orm/domains.py` |
| Request routing | `odoo/http.py` + `ir.http` model |
| Server/worker/cron behavior | `odoo/service/server.py` |
| RPC + retry semantics | `odoo/service/model.py` |
| Startup sequence | `odoo/cli/server.py` → `odoo/modules/loading.py` |
| Access/security | `security/ir.model.access.csv`, `ir.rule` records |

---

*Generated as a reverse-engineering reference for the Odoo 19.0 source tree in this
repository. Verify specifics against the cited files, which remain the source of truth.*
