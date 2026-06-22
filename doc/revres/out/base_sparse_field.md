# base_sparse_field — Architecture Brief

> Module: `base_sparse_field` · Category: Hidden · Depends: `base` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/base_sparse_field.facts.json` · Frontend: `doc/revres/frontend/base_sparse_field.frontend.json`

## 1. Summary

`base_sparse_field` is a **pure ORM framework extension** that adds two things to
Odoo's field system: a new `fields.Serialized` field type (a PostgreSQL TEXT column
storing a JSON dict) and a `sparse` parameter that any field can declare to have its
value stored inside a named Serialized column instead of in its own database column.

The design solves a concrete PostgreSQL limit: a single table can have at most 1 600
columns. Models with many optional attributes would breach this ceiling; sparse fields
pack multiple logical fields into one TEXT column, each key appearing in the JSON only
when non-null. The module is **entirely infrastructure**: **1 own TransientModel**
(`sparse_fields.test`, a test fixture), **2 inherits** (`base`, `ir.model.fields`),
**0 routes**, **0 business views**, ~268 py LOC. Category is *Hidden*; `auto_install`
is False.

## 2. Structure (evidence)

- **Models (1 own + 2 inherit):**
  - `sparse_fields.test` (TransientModel) — demo/test fixture; declares `data`
    (Serialized) plus `boolean`, `integer`, `float`, `char`, `selection`
    (sparse='data'), and `partner` (Many2one → `res.partner`, sparse='data').
  - `base` (inherit) — overrides `_valid_field_parameter` to whitelist `'sparse'`
    as a valid field parameter so Odoo's field-definition checker does not reject it.
  - `ir.model.fields` (inherit) — adds the `serialized` option to the `ttype`
    Selection field (`ondelete cascade`) and `serialization_field_id` Many2one
    (self-referential, points to the Serialized host field).
- **Routes:** 0 — this module has no HTTP surface.
- **Security:** 1 access rule (for `sparse_fields.test`); 0 record rules; 0 groups.
- **Views:** 0 declared business views. `views/views.xml` is referenced in the
  manifest but contains no UI view records (only the `ir.model.access.csv`
  counterpart in security/).

## 3. Frontend (gap #3)

No frontend. `js_files: 0`, `xml_templates: 0`, no OWL components, no registry
adds, no asset bundles. This module has no web-client surface.

## 4. Behavior (beyond metadata)

- **Sparse-field wiring at import time (code-read):** `models/fields.py` uses a
  `monkey_patch(cls)` decorator that saves the original method as `func.super` and
  replaces it on the class. Three methods are patched onto `fields.Field`:
  `_get_attrs`, `_compute_sparse`, and `_inverse_sparse`. When `_get_attrs` sees
  `attrs.get('sparse')`, it forces `store=False`, `copy=False` (unless overridden),
  `compute=self._compute_sparse`, and — if not `readonly` — `inverse=self._inverse_sparse`.
  The `sparse` attribute itself is a plain string (`fields.Field.sparse = None`
  registered at module level). No DB column is created for the sparse field.

- **JSON read/write via compute/inverse (code-read):** `_compute_sparse` reads
  `record[self.sparse]` (the Serialized dict returned by `convert_to_record` as a
  Python `dict`) and assigns `values.get(self.name)` to `record[self.name]`. For
  relational fields (`self.relational`) it additionally calls `.exists()` to discard
  stale ids from deleted records. `_inverse_sparse` calls
  `self.convert_to_read(record[self.name], record, use_display_name=False)` to obtain
  a serialisable value. If truthy and different from the stored entry, it updates
  the dict and writes `record[self.sparse] = values`. If falsy, it `pop`s the key
  from the dict — so absent/null sparse values are never stored in the JSON, keeping
  it compact. Both methods work entirely through the ORM cache with no direct SQL.

- **`class Serialized(fields.Field)` — the column type (code-read):** `type =
  'serialized'`, `column_type = ('text', 'text')` — a PostgreSQL TEXT column.
  `prefetch = False` prevents batch-loading in normal ORM prefetch cycles (avoids
  pulling large JSON blobs when other fields are fetched). `convert_to_cache` stores
  `json.dumps(value, default=json_default)` if value is a `dict`, else `None`.
  `convert_to_record` calls `json.loads(value or '{}')` — callers always receive a
  `dict`, never `None`. `convert_to_column_insert` delegates to `convert_to_cache`
  so INSERT and UPDATE see the same serialised form. The class is registered at
  module level as `fields.Serialized = Serialized`.

- **ORM reflection and immutability guards (code-read):** `ir.model.fields._reflect_fields`
  overrides the base method, calls `super()` first, then raw-SQL-reads
  `ir_model_fields` for `(model, name, id, serialization_field_id)` across the
  affected models. For each `field.sparse` found, it resolves the serialisation
  field's id from the same result set (raises `UserError` if the Serialized host is
  missing). Changed mappings are batched by target value and emitted as a single
  `UPDATE ir_model_fields SET serialization_field_id=%s WHERE id IN %s` per distinct
  value. `pool.post_init(records.modified, ['serialization_field_id'])` marks the
  ORM cache dirty after install. `write()` enforces two immutability rules: changing
  `serialization_field_id` on an existing sparse field raises `UserError('Changing
  the storing system for field … is not allowed')`; renaming a sparse field raises
  `UserError('Renaming sparse field … is not allowed')`. `_instanciate_attrs`
  reconstructs dynamically-created sparse fields (e.g. via Studio) by browsing
  `serialization_field_id` and setting `attrs['sparse'] = serialization_record.name`.

- **External integrations (gap #7):** 0 HTTP call sites, 0 SDK imports, no API
  keys, no external endpoints. Purely in-process ORM engineering.

## 5. IT architecture

- **Application:** ORM field-type extension enabling compact multi-field JSON
  storage in a single TEXT column.
- **Data objects:** `fields.Field` (monkey-patched), `fields.Serialized` (new
  class), `ir.model.fields` (inherit with `serialization_field_id`), `base`
  (inherit with `_valid_field_parameter`), `sparse_fields.test` (TransientModel
  test fixture).
- **ERM:** `sparse_field.serialization_field_id` → `ir.model.fields` (the Serialized
  host; immutable after create); sparse field values stored inside the Serialized
  TEXT/JSON dict (no own column); `sparse_fields.test.partner` → `res.partner`
  (demonstrates relational sparse field).
- **Information flows:**
  - `depends: base` only.
  - Import-time monkey-patch of `fields.Field` — runs before any ORM registry build.
  - Read path: ORM reads sparse_field → `_compute_sparse` → JSON dict `.get(name)`.
  - Write path: ORM writes sparse_field → `_inverse_sparse` → update/pop JSON dict
    → write Serialized column.
  - Reflection path: module install → `_reflect_fields` → raw SQL → UPDATE
    `serialization_field_id` → `pool.post_init`.
  - Dynamic-field path: `_instanciate_attrs` → browse `serialization_field_id` →
    `attrs['sparse']` set.

## 6. Business architecture

- **Capabilities:** zero-extra-column sparse field declarations; automatic
  compute/inverse wiring; null-omitting JSON compaction; `.exists()` guard for
  deleted relational targets; ORM reflection into `ir.model.fields`; dynamic
  reconstruction from `ir.model.fields` data.
- **Value streams:**
  - *Define*: developer declares `fields.Serialized()` + `fields.X(sparse='data')`
    → `_get_attrs` wires compute/inverse at class load → no extra DB columns.
  - *Read*: ORM/UI reads sparse field → `_compute_sparse` → typed Python value.
  - *Write*: ORM/UI writes sparse field → `_inverse_sparse` → JSON dict updated
    in TEXT column.
  - *Reflect*: module install → `_reflect_fields` → `serialization_field_id` links
    visible in Settings > Technical > Fields.
- **Policies:**
  - Sparse field is always `store=False` — JSON column is sole persistence.
  - Sparse field is `copy=False` by default (avoids JSON bloat on duplicate).
  - `serialization_field_id` is immutable after creation.
  - Sparse field names cannot be renamed after creation.
  - Falsy values are popped from the JSON dict — absent keys save space.
- **Stakeholders:** Odoo module developers needing many optional fields near the
  PostgreSQL 1600-column ceiling; Studio/low-code users; DBA/ops team.

## 7. Classification

**Value model: support** (Stabell & Fjeldstad infrastructure). **APQC 8.0 Manage
Information Technology** — this is database schema engineering (DB engine
augmentation), not a business capability. Porter support activity. Category *Hidden*,
`application: false` confirm invisible plumbing.

## 8. Fit-to-Standard

**Standard capabilities:** `fields.Serialized()` JSON TEXT host column; `sparse=`
parameter on any field type; automatic compute/inverse; `.exists()` guard for
Many2one; `ir.model.fields` reflection; rename/reparent immutability.

**Typical fits:** models with many optional attributes near PostgreSQL column limit;
product-variant or configuration-specific attributes in one column; Studio ad-hoc
fields without DBA involvement.

**Common gaps:**
- Sparse fields are not searchable via ORM domain — `store=False` excludes them from
  SQL WHERE clauses; filtering requires a custom query or a stored computed field.
- No GROUP BY or aggregate support on individual JSON keys.
- Renaming or reparenting a sparse field after creation requires a data migration.
- Converting an existing stored field to sparse is not supported by the module.
- No automatic GIN/btree index on individual JSON keys.

**Drive hints:**
```python
# odoo shell
r = env['sparse_fields.test'].create({})
r.write({'boolean': True, 'integer': 42, 'char': 'hello'})
r.data   # -> {'boolean': True, 'integer': 42, 'char': 'hello'}
r.write({'integer': False})
r.data   # -> {'boolean': True, 'char': 'hello'}   # falsy value popped

env['ir.model.fields'].search([
    ('model', '=', 'sparse_fields.test'),
    ('serialization_field_id.name', '=', 'data')
])  # all sparse fields on the model
```
```sql
-- psql
SELECT data FROM sparse_fields_test LIMIT 5;
```
