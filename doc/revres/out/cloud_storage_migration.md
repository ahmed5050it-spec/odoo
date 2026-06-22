# cloud_storage_migration — Architecture Brief

> Module: `cloud_storage_migration` · Category: Technical Settings · Depends: `cloud_storage` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/cloud_storage_migration.facts.json` · Frontend: `doc/revres/frontend/cloud_storage_migration.frontend.json`

## 1. Summary

`cloud_storage_migration` is an **IT operations tool** for migrating existing
local binary attachments (`ir.attachment` type `'binary'`) to a cloud object
storage provider, transitioning them to type `'cloud_storage'`. It is a companion
to the `cloud_storage` parent module (which provides the provider abstraction and
URL/upload-info generation); this module supplies the **batch migration engine**:
a cron-driven loop, a progress watermark system, configurable scoping by model
and file-size window, and a read-only SQL-view report for admin monitoring.

The module owns **1 new model** (`cloud.storage.migration.report`, an `_auto=False`
SQL view), **2 inherits** (`ir.attachment`, `res.config.settings`), **0 routes**,
~380 py LOC. `application: false`, category *Technical Settings*, `auto_install:
false` — it is installed deliberately by an administrator preparing for cloud
storage adoption.

## 2. Structure (evidence)

- **Models (1 own + 2 inherit):**
  - `cloud.storage.migration.report` (`_auto=False`) — read-only SQL view joining
    `ir_attachment` (grouped by `res_model`, SUM/MAX/COUNT of `file_size` split into
    message-linked vs. all-attachment aggregates) with `ir_model`. Exposes 11 fields
    including `message_count`, `message_sum_size`, `all_count`, `all_sum_size`,
    `message_to_migrate`, `all_to_migrate`, `has_attachment_rel`.
  - `ir.attachment` (inherit) — adds `_migrate_local_to_cloud_storage(session)`
    (per-attachment upload) and `_cron_migrate_local_to_cloud_storage()` (cron entry
    point with the full batch loop).
  - `res.config.settings` (inherit) — adds progress display (`cloud_storage_migration_progress`
    Integer), two One2many model-scope selectors (`cloud_storage_migration_message_model_ids`,
    `cloud_storage_migration_all_model_ids`), their backing Char config_parameter fields,
    and `action_open_cloud_storage_migration_configurations`.
- **Routes:** 0 — no HTTP/RPC surface; the cron and settings are driven by the
  backend cron system and Settings UI.
- **Security:** 1 access rule (for the report model); 0 record rules; 0 groups.
- **Views:** 1 list view (`cloud.storage.migration.report`); Settings form extension
  (XPath inside `cloud_storage.cloud_storage_config_settings_view_form`).
- **Cron:** `ir_cron_manual_migrate_local_to_cloud_storage` — interval set to 9999
  months (effectively disabled until triggered manually or via `cron._trigger()`).

## 3. Frontend (gap #3)

No frontend. `js_files: 0`, `xml_templates: 0`, no OWL components, no registry
adds. All interaction is through the Odoo Settings form and the list-view report.

## 4. Behavior (beyond metadata)

- **Per-attachment upload — `_migrate_local_to_cloud_storage(session)` (code-read):**
  Validates `type == 'binary'` and `store_fname` is set (raises `ValidationError`
  otherwise). Gets the filesystem path via `self._full_path(self.store_fname)`, the
  target URL via `self._generate_cloud_storage_url()` (cloud_storage module), and
  `upload_info = self._generate_cloud_storage_upload_info()` for `{method, url,
  headers, response_status}`. Opens the local file as binary and calls
  `session.request(upload_info['method'], upload_info['url'], data=f, headers=headers,
  timeout=(10, 30))` — the `requests.Session` is passed in by the caller to reuse
  HTTP connections across the batch. On a non-matching response status, raises
  `ValidationError`. On success, writes `{type: 'cloud_storage', raw: False,
  mimetype: self.mimetype}` — mimetype is explicitly preserved because setting
  `raw=False` would otherwise trigger Odoo's mimetype recomputation from absent
  binary data.

- **Cron entry point and HTTP vs. cron-worker split (code-read):**
  `_cron_migrate_local_to_cloud_storage` (decorated `@assert_log_admin_access`) reads
  all migration parameters from `ir.config_parameter`: `cloud_storage_provider` (must
  be set), `cloud_storage_min_file_size`, `cloud_storage_migration_max_file_size`
  (default 1 GB), `cloud_storage_migration_max_batch_file_size` (default 10 GB), and
  comma-separated model lists validated against the ORM registry. **Key branch:** if
  `odoo.http.request` is truthy (the call originates from an HTTP worker via the
  Settings 'Manually Run' button), the method immediately calls `cron._trigger()` and
  returns — **no I/O is performed on the HTTP worker**. Only a cron-server worker
  (where `request` is `None`) executes actual uploads. This design prevents
  file-upload blocking from stalling the HTTP request pool.

- **SQL query loop and cursor-level progress tracking (code-read):**
  The main loop executes a raw SQL query on `ir_attachment` (LEFT JOIN
  `message_attachment_rel` for mail-linked detection; conditional LEFT anti-JOIN to
  `documents_document` if that module is installed). Filters: `type='binary'`,
  `url IS NULL`, `res_id IS NOT NULL`, `res_field IS NULL`, `store_fname IS NOT NULL`,
  `file_size BETWEEN min_file_size AND max_file_size`, `create_date < now() - 7 days`
  (recent uploads excluded to protect business operations), `id` between 0 and
  `max_attachment_id` (a stable ceiling established on first run). Progress is
  tracked by `commit_min_attachment_id(attachment_id)`, which runs a direct
  `UPDATE ir_config_parameter SET value=%s WHERE key='cloud_storage_migration_min_attachment_id'`
  (bypassing ORM cache to avoid `ormcache` invalidation) and then calls
  `env['ir.cron']._commit_progress(1)` to commit the transaction. On upload failure,
  `env.cr.rollback()` rolls back only the `ir.attachment.write` — the watermark
  committed earlier is preserved, so the failed attachment is skipped in subsequent
  runs.

- **SQL view and computed migration flags — `cloud.storage.migration.report`
  (code-read):** `init()` drops and recreates a PostgreSQL VIEW: it groups
  `ir_attachment` by `res_model` (only `type='binary'`, `res_id IS NOT NULL`,
  `res_field IS NULL`, non-null `file_size` and `res_model`), JOINs
  `message_attachment_rel` for the message-linked sub-aggregate, then INNER JOINs
  `ir_model` to get the ORM record id. `_compute_message_to_migrate` and
  `_compute_all_to_migrate` read `ir.config_parameter` model lists and flag the
  report rows. `get_progress()` computes migration percent as
  `min_attachment_id * 100 // max(max_attachment_id, min_attachment_id)` by reading
  `max` from `ir.config_parameter` and `min` via direct `cr.execute` to bypass ORM
  cache.

- **Settings wiring (code-read):** `get_values()` calls `report.get_progress()` and
  reads both model-list config params, validates names against `env`, and issues
  `Command.set` to hydrate the One2many fields from `ir.model.search`. The inverses
  `_inverse_cloud_storage_migration_message_model_ids` and
  `_inverse_cloud_storage_migration_all_model_ids` write comma-joined model names
  back into the Char `config_parameter` fields. `action_open_cloud_storage_migration_configurations`
  returns an act_window on `ir.config_parameter` filtered to the 7 migration-related
  parameter keys, exposing a power-user escape hatch to raw parameters.

- **External integrations (gap #7):** `sdk_imports: ['requests']` (used directly in
  `ir_attachment.py` via `requests.Session`). `http_call_sites: 0` (the extractor
  counts outbound call-site patterns; the actual call is `session.request(...)` inside
  `_migrate_local_to_cloud_storage`). `uses_api_keys: false` — auth is handled by
  the cloud storage provider URL/header mechanism in the `cloud_storage` parent
  module. No fixed external endpoints (provider-specific URLs come from
  `_generate_cloud_storage_upload_info`).

## 5. IT architecture

- **Application:** batch IT-operations migration tool: local binary `ir.attachment`
  → cloud object storage, with cron scheduling, watermark-based progress, admin
  reporting, and Settings UI.
- **Data objects:** `ir.attachment` (inherit: migration methods), `cloud.storage.migration.report`
  (`_auto=False` SQL view), `res.config.settings` (inherit: progress + model selectors).
- **ERM:**
  - `ir.attachment` (type binary) → cloud storage URL (via `_generate_cloud_storage_url`).
  - `ir.attachment.res_model` → `ir.model.model` (report view JOIN).
  - `ir.attachment` LEFT JOIN `message_attachment_rel` (mail-linked detection).
  - `ir.attachment` LEFT anti-JOIN `documents_document` (exclusion when module present).
  - `ir.config_parameter` keys: `cloud_storage_migration_min_attachment_id`,
    `cloud_storage_migration_max_attachment_id`, `cloud_storage_migration_message_models`,
    `cloud_storage_migration_all_models`, `cloud_storage_migration_max_file_size`,
    `cloud_storage_migration_max_batch_file_size`.
- **Information flows:**
  - `depends: cloud_storage` (provides URL/upload-info generation and provider abstraction).
  - HTTP trigger: Settings 'Manually Run' → `_cron_migrate_local_to_cloud_storage` →
    detects `request` truthy → `cron._trigger()` → returns (no upload).
  - Cron trigger: cron worker → `_cron_migrate_local_to_cloud_storage` → raw SQL
    SELECT loop → `_migrate_local_to_cloud_storage` → `requests.Session.request` →
    `ir.attachment.write(type='cloud_storage')` → watermark committed → loop/break.
  - Timeout path: `time.monotonic() > end_time` → break → `cron._trigger()`.
  - Batch-size path: `total_file_size + file_size >= max_batch_file_size` → break →
    `cron._trigger()`.
  - Report path: SQL view → Settings 'Attachments Report' list view.
  - Settings-read: `get_values` → `report.get_progress()` + model lists → form.
  - Settings-write: `_inverse_*_model_ids` → comma-joined model names → `ir.config_parameter`.

## 6. Business architecture

- **Capabilities:** batch local-to-cloud binary migration with model-scoped targeting;
  time-budget-aware cron with automatic rescheduling; resumable watermark-based
  progress; HTTP-worker safety (no I/O on HTTP workers); configurable file-size
  filtering; exclusion of recent/documents/res_field attachments; per-model
  attachment size/count report; Settings progressbar.
- **Value streams:**
  - *Configure stream:* admin selects model scope in Settings → ir.config_parameter
    updated → cron trigger enabled.
  - *Migrate stream:* cron worker → raw SQL loop → per-attachment upload to cloud →
    type transition binary→cloud_storage → watermark committed → loop until timeout
    or batch ceiling → reschedule.
  - *Monitor stream:* admin opens Settings → `get_progress()` → progressbar;
    'Attachments Report' → SQL view list showing per-model counts/sizes and migration
    flags.
- **Policies:**
  - Uploads only on cron-server workers (`request`-truthy guard).
  - Attachments < 7 days old excluded to protect ongoing business operations.
  - `documents.document`-linked attachments excluded when that module is installed.
  - `res_field`-set and `res_id`-absent attachments excluded.
  - Only `store_fname`-present attachments within the configured size window are eligible.
  - Watermark committed before each upload (upload idempotency across restarts).
  - Failed uploads → `env.cr.rollback()` + warning log; attachment is skipped in
    subsequent runs (watermark already committed).
  - Cron default interval 9999 months (disabled until triggered).
- **Stakeholders:** system administrator (configures and monitors), cron-server worker
  (performs I/O), cloud storage provider (receives uploads), `cloud_storage` module
  (provides provider abstraction).

## 7. Classification

**Value model: support** (Stabell & Fjeldstad IT infrastructure). **APQC 8.0 Manage
Information Technology** — this is an IT operations/storage management tool: moving
binary blobs from local disk to cloud object storage. Porter support activity.
`application: false`, category *Technical Settings*, no customer-facing model. 13.0
was rejected: this is IT infrastructure migration, not a business-process capability.

## 8. Fit-to-Standard

**Standard capabilities:** cron-driven batch migration of local binary `ir.attachment`
records to cloud storage; two scoping modes (message-linked attachments vs. all
attachments per model); configurable per-file and per-run size limits; time-budget
cron with auto-rescheduling; resumable watermark; HTTP-worker safety; attachment
report SQL view; 7-day recency exclusion; `documents.document` exclusion.

**Typical fits:** post-deployment migration of on-premises Odoo attachment binaries
to a configured cloud provider; incremental zero-downtime migration during live
production; admin-controlled scoping (migrate mail-heavy models first, then expand).

**Common gaps:**
- No reverse migration (cloud → local): one-directional only.
- Single-threaded cron loop — no parallel upload workers.
- Failed attachments are silently skipped after rollback with no retry queue or
  failed-attachment report.
- The 7-day recency exclusion is hard-coded; no config parameter to adjust it.
- No completion notification or alert when migration finishes or when an attachment
  fails repeatedly.
- `documents.document` exclusion is opportunistic (module presence check) with no UI
  override.

**Drive hints:**
```python
# odoo shell
env['cloud.storage.migration.report'].search_read([], limit=10)
# per-model attachment counts, sizes, and migration scheduling flags

env['cloud.storage.migration.report'].get_progress()
# current migration percentage (0-100)

env['ir.config_parameter'].sudo().get_param('cloud_storage_migration_min_attachment_id')
# current watermark (last attachment id processed)

env['ir.config_parameter'].sudo().get_param('cloud_storage_migration_max_attachment_id')
# stable ceiling (set once on first cron run)

# Trigger migration directly from shell (shell context = cron context, request=None)
env['ir.attachment'].sudo()._cron_migrate_local_to_cloud_storage()
```
