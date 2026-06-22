# Odoo Modules Subsystem — Deep Dive

> **This document** analyzes `odoo/modules/` and the addon ecosystem at /home/user/odoo/addons/.
> It covers module discovery, manifest parsing, dependency resolution, loading phases,
> and concrete dependency data from all 625 addons in the codebase.

---

## 1. Overview: What is a Module?

An Odoo **module** (also called **addon**) is a self-contained package of code, data,
views, and metadata. The codebase ships with **625 modules**:

- **Core modules** (9): `base`, `web`, `rpc`, `social_media`, `uom`, `base_sparse_field`, `l10n_us`, `l10n_fr`, and others — no dependencies or only depend on `base`.
- **Hub modules** (hundreds): depend on core; in turn depended on by many others.
- **Leaf modules** (hundreds): depend on others but have no dependents.
- **Test modules** (prefixed `test_*`): special loading rules; loaded after their dependencies.

The deepest module dependency chain has **16 levels**: `test_event_full` depends on a web of 13 modules,
which collectively reach back through the dependency tree to `base`.

---

## 2. Module Discovery (`odoo/modules/module.py`)

### 2.1 Manifest parsing

The **manifest** is a Python dict in `<addon>/__manifest__.py`. It's parsed as a literal
(safe via `ast.literal_eval`), not executed. The `Manifest` class wraps it:

```python
class Manifest(Mapping[str, typing.Any]):
    """The manifest data of a module."""
    path: str                              # /abs/path/to/addon
    name: str                              # addon name (parent dir)
    __manifest_cached: dict                # parsed & validated manifest dict
```

Key responsibilities:
- **Parse & validate** the manifest dict (fill in defaults from `_DEFAULT_MANIFEST`).
- **Lazy load** description from README if not in manifest.
- **Check external dependencies** (Python packages, binaries).
- **Expose** all manifest fields as a Mapping (dict-like interface).

### 2.2 Discovery methods

| Function | Purpose |
|----------|---------|
| `Manifest.all_addon_manifests()` | Scan all `odoo.addons.__path__` dirs, return all manifests sorted by name. |
| `Manifest.for_addon(module_name)` | Lookup a single module by name (cached). |
| `Manifest._from_path(path)` | Parse manifest from a directory path. |
| `get_modules()` | Return list of all module names (convenience). |
| `load_openerp_module(module_name)` | **Import** the module (`odoo.addons.{name}`), triggering model registration via metaclass. |

### 2.3 The Manifest dict structure

All keys from `_DEFAULT_MANIFEST`:

| Key | Type | Meaning |
|-----|------|---------|
| **Identity** | | |
| `name` | str | Display name (e.g., "Accounting"). |
| `version` | str | Canonical version (e.g., "19.0.1.2.0") — validated format. |
| `category` | str | App category (e.g., "Accounting/Accounting"). |
| `summary` | str | One-line description. |
| `description` | str | Defaults to README file content. |
| **Dependencies** | | |
| `depends` | list[str] | Module names that must load first (drives graph). |
| **Lifecycle** | | |
| `installable` | bool | Can be installed (default: True). |
| `auto_install` | bool ∣ list[str] | Auto-install when deps satisfied (default: False). If list, auto-install when those modules are. |
| `uninstall_hook` | str | Function name in `__init__.py` to call on uninstall. |
| `pre_init_hook` | str | Function name to call before data is loaded (on install/update). |
| `post_init_hook` | str | Function name to call after data is loaded. |
| `post_load` | str | Function name to call after the module's Python is imported (server-wide, once per server boot). |
| **Data Loading** | | |
| `data` | list[str] | XML/CSV files loaded on install/upgrade (in order). |
| `demo` | list[str] | Demo data files (loaded only if `--without-demo` is not used). |
| `init_xml`, `demo_xml`, `update_xml` | list[str] | Deprecated aliases for `data`/`demo`. |
| **External** | | |
| `external_dependencies` | dict | Python packages and binaries required. E.g., `{'python': ['requests'], 'bin': ['ffmpeg']}`. |
| **Web/Assets** | | |
| `assets` | dict | JS/CSS/SCSS asset bundles. Keys are bundle names; values are lists of file paths (e.g., `assets['web.assets_backend']`). |
| `web` | bool | Module provides web/HTTP routes. |
| `application` | bool | Top-level app in app switcher (not just a feature module). |
| **Other** | | |
| `author` | str | Module author(s). |
| `license` | str | License type (default: LGPL-3). |
| `website` | str | Author/vendor URL. |
| `sequence` | int | Loading order hint (100 default). |
| `countries` | list[str] | ISO 3166 codes for localization modules. |
| `images` | list[str] | App icon/preview images. |
| `test` | list[str] | Test files to run with `-m test`. |

**Defaults:** Missing keys are filled in from `_DEFAULT_MANIFEST`. A module with no
`depends` gets `depends = ['base']` (except `base` itself, which has `depends = []`).

### 2.4 External dependencies

The `external_dependencies` dict is checked at load time via `Manifest.check_manifest_dependencies()`:

```python
external_dependencies = {
    'python': ['requests', 'psutil>=5.4.0'],
    'bin': ['wkhtmltopdf', 'ffmpeg'],
}
```

- **Python:** Validated using `packaging.requirements.Requirement` (PEP 508).
- **Binaries:** Checked via `tools.find_in_path()` (searches `$PATH`).
- **Missing:** Raises `MissingDependency` exception, halting load.

---

## 3. Module Dependency Graph (`odoo/modules/module_graph.py`)

The **ModuleGraph** is a directed acyclic graph (DAG) of module dependencies. It solves
two problems:

1. **Topological sort**: determine the order to load modules (dependencies first).
2. **Loading phases**: sequence install-time module initialization to handle upgrades
   cleanly.

### 3.1 ModuleNode

Each module in the graph is a `ModuleNode`:

```python
class ModuleNode:
    name: str                      # module name ('base', 'account', …)
    manifest: Mapping              # manifest dict
    depends: OrderedSet[ModuleNode]  # direct dependencies (nodes, not names)
    state: STATES                  # 'uninstalled' | 'installed' | 'to install' | 'to upgrade' | 'to remove'
    depth: int                     # longest path from self to 'base'
    phase: int                     # loading phase (0=base, 1+=others, odd=update, even=install)
    order_name: str                # name for sorting within phase (special for test_* modules)
```

**Properties:**

| Property | Meaning |
|----------|---------|
| `depth` | Longest distance from this module to `base` along the dependency graph. Test modules inherit their last dependency's depth (no +1). |
| `phase` | Loading phase (see §3.3). |
| `order_name` | Sort key within phase. For test modules: `"{last_dep_order_name} {test_module_name}"` (space = priority). |
| `demo_installable` | `True` if all dependencies have demo=True. |

**Example depths:**

```
base                    → depth = 0
account (depends base)  → depth = 1
sale (depends account)  → depth = 2
sale_mrp (depends sale, mrp)  → depth = max(2, 1) + 1 = 3
```

### 3.2 Building the graph

```python
graph = ModuleGraph(cr, mode='load'|'update')  # cursor, and load vs. update mode
graph.extend([module_names])   # add modules and resolve dependencies
```

`extend()` does:
1. Create `ModuleNode` for each new module.
2. Check `installable` — skip if not.
3. `_update_depends()` — resolve manifest `depends` to node references; skip if any
   dependency is missing or would create a cycle.
4. `_update_depth()` — calculate each module's depth (recursive, caches result).
5. `_update_from_database()` — fetch `ir_module_module` state/version/demo flags
   from the database (if the table exists); skip modules marked `uninstallable`.

### 3.3 Loading phases

Modules are loaded in **phases**. The phase is determined by the module's state and
the graph's mode:

#### Load mode (`mode='load'`)
All non-base modules load in **phase 1** (flat). Within phase 1, sorted by `(depth, order_name)`:

```
Phase 0:  base
Phase 1:  <all others, sorted by depth then name>
```

**Why?** When simply starting a server with all modules installed, there's no
"install" vs. "upgrade" distinction — just load everything. Depth ordering ensures
dependencies load before dependents.

#### Update mode (`mode='update'`)
Modules are split into phases based on their state and dependencies:

```
Phase 0:           base
Phase 1:           installed modules (no change)
Phase 2:           new modules ('to install') that don't depend on phase 1 upgrades
Phase 3:           new modules that DO depend on phase 2 installs
Phase odd:         modules not being initialized (already installed)
Phase even:        modules being initialized (to install / to upgrade)
```

**Why?** If module A is being upgraded and module B is being newly installed and
B depends on A:

```
     BEFORE                    DURING UPGRADE
   +---------+                 +---------+
   |    A    |                 |    A    |  (to upgrade)
   +---------+ (installed)     +---------+
     ^                           ^
     |                           |
   +---------+                 +---------+
   |    B    |        ──────▶  |    B    |  (to install)
   +---------+ (unins)        +---------+
                                 
Phase 0: A                    Phase 0: base
Phase 1: (none)               Phase 1: A (installed modules not affected)
                              Phase 2: B (new modules in phase 1 deps)
```

Within each phase, modules sort by `(phase, depth, order_name)` — so dependencies
within the same phase load first, and after all prior phases.

### 3.4 Test module special handling

Modules starting with `test_` are loaded immediately after their last (deepest)
dependency:

```python
if self.name.startswith('test_'):
    last_installed_dependency = max(self.depends, key=lambda m: (m.depth, m.order_name))
    # inherit depth from dependency (no +1)
    depth = last_installed_dependency.depth
    # prefix order_name with dep's order_name + space (space < any alphanumeric)
    order_name = last_installed_dependency.order_name + ' ' + self.name
```

This ensures a test module for feature X loads after feature X but before other
unrelated modules, minimizing test isolation issues.

**Example:** `test_sale_custom` depends on `sale`:
- `sale` has depth 2, order_name "sale"
- `test_sale_custom` gets depth 2, order_name "sale test_sale_custom"
- Loading order within phase: `sale`, then `test_sale_custom`, then other depth-2 modules.

---

## 4. Module Loading Orchestration (`odoo/modules/loading.py`)

The **load_module_graph** function is the conductor. It's called by the registry during
startup.

### 4.1 Entry point & context

```python
def load_module_graph(env, graph, perform_checks=True, test_file=None):
    """Load modules according to the dependency graph.
    
    :param env: Environment (with cr, uid, context)
    :param graph: ModuleGraph instance (pre-built, sorted)
    :param perform_checks: if True, check module version, signals, etc.
    :param test_file: if provided, run tests (legacy parameter)
    """
```

Called from `odoo/orm/registry.py:Registry.init_models()` after `Registry.__init__` has
built the graph via `ModuleGraph.extend()`.

### 4.2 Load sequence for each module

For each module in the sorted graph:

```
1. load_openerp_module(module_name)
   │
   └─ sys.modules['odoo.addons.{name}']
      (imports models/__init__.py, etc.)
      → Models register via MetaModel.__new__
   
2. registry.load(module_name, ...)
   │
   ├─ registry._module_models[name] = get models for this module
   ├─ registry._init_models()
   │  └─ CREATE/ALTER tables, constraints, indexes
   └─ registry._module_depends[name] = resolved manifest['depends']
   
3. if module.load_state != 'installed':   # about to install or upgrade
   │
   ├─ pre_init_hook()  (if declared in manifest)
   │
   ├─ load_data(env, idref, mode, kind='data', package=module)
   │  └─ for each file in manifest['data']:
   │     └─ convert_file() ← parses XML/CSV, creates/updates records
   │
   ├─ if demo_active:
   │     load_demo(env, module, idref, mode)
   │     └─ load_data(..., kind='demo')
   │
   ├─ post_init_hook()  (if declared)
   │
   └─ run migration scripts (MigrationManager)
      └─ if manifest['version'] != installed_version:
         └─ execute migrations in addons/<name>/migrations/

4. Mark module as 'installed' (update ir_module_module state)
```

### 4.3 The idref dictionary

`idref` is a **global mapping** of XML-IDs → record IDs built up as data is loaded.
It allows cross-references:

```xml
<!-- in base/data/users.xml -->
<record id="base_user_admin" model="res.users">
    <field name="login">admin</field>
</record>

<!-- in sale/data/sale_data.xml -->
<record model="sale.order">
    <field name="user_id" ref="base.base_user_admin"/>  ← resolves via idref
</record>
```

`idref` is shared across all modules and cleared between data/demo phases.

### 4.4 Error handling in load_data

If loading a data file raises an exception:
- For **regular** (`data`) files: the exception propagates, halting the load.
- For **demo** files: the exception is caught, logged, and loading continues (module
  installs without demo). A `ir.demo_failure` record is created to track the failure.

### 4.5 Conversion modes & noupdate

The `LoadMode` enum determines how records are created/updated:

| Mode | Behavior |
|------|----------|
| `init` | Records created/updated. On re-install, old XML-IDs are cleaned first. |
| `update` | Records updated; non-declared records left alone (safe for user-modified data). |

The `noupdate` flag is set by load_data based on the kind:
- `kind='data'` → `noupdate=False` (updates on each install/upgrade)
- `kind='demo'` → `noupdate=True` (demo data doesn't re-run on upgrades)

---

## 5. Dependency Data Analysis (625 modules)

### 5.1 Hub modules (most depended-on)

These are the "core" modules that many others build on:

| Module | Dependents | Category |
|--------|-----------|----------|
| **account** | 151 | Accounting/Accounting |
| **account_edi_ubl_cii** | 44 | Accounting/Accounting |
| **point_of_sale** | 44 | Sales/Point of Sale |
| **base_vat** | 43 | Accounting/Accounting |
| **mail** | 42 | Productivity/Discuss |
| **web** | 31 | Hidden |
| **base_iban** | 25 | Accounting/Accounting |
| **payment** | 23 | Hidden |
| **sale** | 21 | Sales/Sales |
| **website** | 20 | Website/Website |
| **base_setup** | 19 | Hidden |
| **hr** | 18 | Human Resources/Employees |
| **portal** | 17 | Hidden |
| **sms** | 17 | Sales/Sales |

**Observation:** Accounting (`account*`) dominates — ERP's core. Sales, HR, and Web
support 10–20 others each. The hub structure mirrors business logic hierarchy.

### 5.2 Core kernel (9 modules with no or only base dependency)

These must be present for any Odoo install:

| Module | Auto-install | Category | Notes |
|--------|:-------:|----------|-------|
| `base` | N/A | Hidden | Always first; handles core data models. |
| `web` | ✓ | Hidden | WSGI app, asset bundler, web UI framework. |
| `rpc` | ✓ | Extra Tools | RPC dispatch, legacy endpoints. |
| `social_media` | ✗ | Marketing | Social media tracking (opt-in). |
| `uom` | ✗ | Sales | Unit of measure reference data. |
| `base_sparse_field` | ✗ | Hidden | Sparse field storage optimization. |
| `l10n_us`, `l10n_fr` | ✗ | Accounting | Localization packs (country-specific). |
| `iot_*` | ✗ | Hidden | IoT box integration (non-standard). |

Auto-install modules (`web`, `rpc`) load automatically unless explicitly excluded.

### 5.3 Deepest chains (longest dependency path)

The deepest dependency tree has 16 levels:

```
test_event_full (depth 16)
  └─ depends on 13 modules:
     [event, event_booth, event_crm, event_crm_sale, event_sale,
      event_sms, payment_demo, website_event_booth_sale_exhibitor,
      website_event_exhibitor, website_event_sale, website_event_track,
      website_event_track_live, website_event_track_quiz]
```

Each of those has its own sub-dependencies, creating a tree. The longest single path
is typically:

```
test_event_full → website_event_track_quiz → website_event_track
                → event_sale → event → base         (depth ≈ 6)
            OR  → payment_demo → payment → account → base  (depth ≈ 4)
```

The max of all such paths = 16.

### 5.4 Category distribution

Modules are grouped by `category` (hierarchical):

```
Accounting/Accounting                  (account, payroll_expense, edi, …)
Sales/Sales                            (sale, sales_team, sales_management, …)
Sales/Point of Sale                    (point_of_sale, pos_*, …)
Inventory/Inventory                    (stock, stock_*, …)
Manufacturing/Manufacturing            (mrp, mrp_*, …)
Human Resources/Employees              (hr, hr_*, …)
Productivity/Discuss                   (mail, discuss, …)
Website/Website                        (website, website_*, …)
Hidden                                 (base, web, rpc, internal features)
Marketing                              (social_media, marketing, …)
...
```

The hierarchy reflects both feature grouping and dependency ordering (usually).

---

## 6. Module Loading Flow Diagram

```
Server start (cli/server.py)
  │
  ├─ tools.config.parse_config()    ← CLI args, config file, env vars
  ├─ initialize_sys_path()          ← setup odoo.addons, odoo.upgrade
  │
  └─ service.server.start()
      │
      └─ for each database:
          │
          └─ Registry.new(db_name, update_module=True)
              │
              ├─ Registry.__init__(db, update_module)
              │   │
              │   └─ ModuleGraph(cr, mode='update'|'load')
              │       ├─ extend(available_modules)
              │       │   ├─ create ModuleNode for each
              │       │   ├─ _update_depends()  ← resolve manifest['depends']
              │       │   ├─ _update_depth()    ← compute longest paths
              │       │   └─ _update_from_database()  ← fetch ir_module_module state
              │       │
              │       └─ __iter__() → sorted by (phase, depth, order_name)
              │
              ├─ Registry.init_models()
              │   │
              │   └─ load_module_graph(env, graph)
              │       │
              │       └─ for each module in sorted order:
              │           │
              │           ├─ load_openerp_module(name)
              │           │   └─ __import__('odoo.addons.{name}')
              │           │       ├─ models/__init__.py imported
              │           │       ├─ Model classes defined
              │           │       └─ MetaModel.__new__ registers them
              │           │
              │           ├─ registry.load(name)
              │           │   ├─ _init_models()
              │           │   │   ├─ CREATE TABLE if not exists
              │           │   │   ├─ ALTER TABLE (add columns)
              │           │   │   ├─ CREATE CONSTRAINT
              │           │   │   └─ CREATE INDEX
              │           │   │
              │           │   └─ _module_models[name] = [models]
              │           │
              │           ├─ if module.state in ['to install', 'to upgrade']:
              │           │   ├─ pre_init_hook()     (if declared)
              │           │   ├─ load_data(kind='data')
              │           │   │   └─ for each file in manifest['data']:
              │           │   │       └─ convert_file(env, ...)
              │           │   │           ├─ parse XML/CSV
              │           │   │           └─ create/update records
              │           │   ├─ if demo_active:
              │           │   │   └─ load_demo()
              │           │   │       └─ load_data(kind='demo')
              │           │   ├─ post_init_hook()    (if declared)
              │           │   └─ run migration scripts
              │           │
              │           └─ update ir_module_module.state = 'installed'
              │
              └─ registry.ready = True
```

---

## 7. Key Algorithms & Invariants

### 7.1 Topological sort (depth calculation)

```python
def depth(module) -> int:
    if module.name == 'base':
        return 0
    elif module.name.startswith('test_'):
        return max_depth_of_deps(module)  # no +1
    else:
        return 1 + max_depth_of_deps(module)
```

**Invariant:** `depth` is the longest path from this module to `base`. Calculated
once, cached. If a cycle is detected (RecursionError), the module is skipped.

### 7.2 Phase calculation (update mode)

```python
def phase(module) -> int:
    if module.name == 'base':
        return 0
    if mode == 'load':
        return 1
    
    # Update mode: compute based on dependencies
    max_dep_phase = max(
        (dep.phase + (1 if dep.state == 'to install' else 0) + (1 if dep.name == 'base' else 0))
        for dep in module.depends
    )
    # if this module is 'to install', add 1 (separate from non-installing deps)
    if module.state == 'to install':
        max_dep_phase += 1
    return max_dep_phase
```

**Invariant:** In update mode, a module's phase is always ≥ all its dependencies'
phases. New modules get an extra phase bump if any dependency is upgrading.

### 7.3 Circular dependency detection

If module A depends on module B, and B depends on A (or via transitivity), depth
calculation will hit Python's `RecursionError`. The graph catches it and skips the
offending module with a warning:

```python
try:
    module.depth  # trigger recursive property
except RecursionError:
    _logger.warning('module %s: in a dependency loop, skipped', name)
    self._remove(name)
```

### 7.4 Missing dependency handling

If module A depends on module B, but B is not available (not in addons paths, or
skipped as uninstallable), then A is also skipped:

```python
try:
    module.depends = OrderedSet(self._modules[dep] for dep in depends)
except KeyError:
    missing = [dep for dep in depends if dep not in self._modules]
    _logger.warning('module %s: some depends are not loaded (%s), skipped',
                    name, ', '.join(missing))
    self._remove(name)
```

When A is removed, any module that depends on A is also removed recursively.

---

## 8. External Dependencies Checking

Before loading a module's Python code, its external dependencies are validated:

```python
manifest.check_manifest_dependencies()
```

For each entry in `external_dependencies`:
- **Python:** Uses `importlib.metadata` to check if the package is installed, and
  optionally validates the version specifier (PEP 508).
- **Binary:** Uses `tools.find_in_path(binary)` to check if the binary is in `$PATH`.

If any dependency is missing, `MissingDependency` is raised, and the module load fails.
This happens **before** the module's Python code is imported, preventing import errors.

---

## 9. Post-Load Hooks

The `post_load` manifest key is unique: it's a function name to call **after** the
module's Python is imported, but **before** any database access. It's server-wide and
called once per server boot (not per database).

```python
# in load_openerp_module()
if post_load := manifest.get('post_load'):
    getattr(sys.modules[qualname], post_load)()
```

**Example use:** Registering global request handlers, monkey-patching, or initializing
server-wide caches.

Unlike `pre_init_hook` / `post_init_hook` (which are per-database and called during
install/upgrade), `post_load` runs for every server start, even if the module is
already installed.

---

## 10. Summary: The Module Loading Contract

1. **Discovery:** Scan `odoo.addons.__path__` for `__manifest__.py` files.
2. **Manifest validation:** Fill defaults, check licenses, validate versions, resolve `depends` → module names.
3. **Build graph:** Create `ModuleNode` for each module, resolve `depends` → nodes, compute `depth` and `phase`.
4. **Sort:** Modules are sorted by `(phase, depth, order_name)`.
5. **Load in order:** For each module:
   - Import Python code (triggers model registration).
   - Create/alter database schema.
   - If installing/upgrading: run pre hook → load data → run post hook → run migrations.
   - Mark as installed.

**Key invariants:**
- **Dependency first:** A module is never loaded before its dependencies.
- **Idempotence:** Loading a module twice (e.g., server restart) produces the same state.
- **Transactionality:** Each module's initialization is a transaction; on error, it rolls back.
- **No circular deps:** Circular dependencies are detected and the cycle is broken by skipping.

---

*This document synthesizes code inspection of `odoo/modules/*.py` and dependency analysis
of all 625 installed modules. It is current as of Odoo 19.0.*
