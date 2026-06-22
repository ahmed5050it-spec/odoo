# account_update_tax_tags — Architecture Brief

> Module: `account_update_tax_tags` · Category: Accounting/Accounting · Depends: `account` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **9.0 Manage Financial Resources**
> Odoo 19.0 · Facts: `doc/revres/facts/account_update_tax_tags.facts.json` · Frontend: `doc/revres/frontend/account_update_tax_tags.frontend.json`

## 1. Summary

`account_update_tax_tags` provides a one-shot **retroactive tax-grid-tag repair wizard** for
accountants and system administrators. When a company changes the tax repartition lines or
grid tags on an `account.tax` (e.g. after a localisation upgrade), existing posted journal
entries keep their old tag assignments. This wizard re-executes the tagging logic — in a
single multi-CTE SQL statement — against all `account.move.line` records from a specified
date, replacing the `account_account_tag_account_move_line_rel` junction rows to match the
current tax configuration.

The module is a **data-integrity maintenance tool**: it owns one TransientModel
(`account.update.tax.tags.wizard`, 3 fields), 0 persistent tables, 0 routes,
646 py LOC, 54 xml LOC, 1 access rule. The entry point is hidden behind
`groups="base.group_no_one"` in Accounting Settings — visible only in developer mode.

## 2. Structure (evidence)

- **Models:**
  - `account.update.tax.tags.wizard` (`wizard/account_update_tax_tags_wizard.py`,
    TransientModel): fields `company_id` (M2O `res.company`, readonly, default
    `env.company`), `date_from` (Date, computed/stored from `company.tax_lock_date + 1d`,
    readonly=False), `display_lock_date_warning` (Boolean, computed, non-stored);
    methods `_compute_date_from`, `_compute_display_lock_date_warning`,
    `_modify_tag_to_aml_relation`, `update_amls_tax_tags`.
- **Routes:** 0.
- **Security:** 1 `ir.model.access` row for `account.update.tax.tags.wizard`.
- **Views:** 1 wizard form (`account.update.tax.tags.wizard.form`) with an irreversibility
  warning banner, a conditional lock-date warning banner, `date_from` field, and
  Update / Discard footer buttons; 1 inherit on `res.config.settings` inserting the
  wizard action button inside `default_taxes_setting_container` gated to `base.group_no_one`.

## 3. Frontend (gap #3)

**None.** `frontend.present = false` — 0 JS files, 0 OWL components, 0 registry additions.
The wizard is a standard server-rendered Odoo dialog form. All logic is Python + SQL.

## 4. Behavior (beyond metadata)

- **Multi-CTE single-shot SQL in `_modify_tag_to_aml_relation` (code-read):** The method
  calls `env.flush_all()` then executes a single parameterised `env.cr.execute(...)`.
  The CTE has four stages:
  1. `base_aml_id_rep_tag_to_insert` — finds tags for **base lines** by traversing
     `account_move_line_account_tax_rel` → `account_tax_filiation_rel` (for group/child
     taxes) → `account_tax` → `account_tax_repartition_line` (matching `repartition_type='base'`
     and `document_type` derived from `move.move_type`) →
     `account_account_tag_account_tax_repartition_line_rel`.
  2. `tax_aml_id_rep_tag_to_insert` — finds tags for **tax lines** directly via
     `aml.tax_repartition_line_id` → `account_account_tag_account_tax_repartition_line_rel`.
  3. DELETE step — removes all rows in `account_account_tag_account_move_line_rel` for
     every aml appearing in the union of steps 1–2.
  4. INSERT step — re-inserts the new `(aml_id, tag_id)` pairs where `tag_id IS NOT NULL`.
  Finally gathers the union of deleted + inserted aml ids and returns them as an array.
  `env.invalidate_all()` is called after to flush the ORM cache.

- **`entry`-type move sign heuristic (code-read):** General journal entries have no
  inherent invoice/refund direction. The SQL resolves this from `aml.balance` and
  `parent_tax.type_tax_use`: sale tax + balance ≤ 0 → 'invoice'; sale tax + balance > 0
  → 'refund'; purchase tax + balance ≥ 0 → 'invoice'; purchase tax + balance < 0 →
  'refund'. A balance of 0 with a sale tax defaults to 'invoice'. This mirrors the original
  tagging algorithm but is expressed purely in SQL conditional logic inside the CTE.

- **Group/child tax guard in `update_amls_tax_tags` (code-read):** Searches for
  `account.tax` records with `children_tax_ids != False`, collects child ids, and raises
  `UserError('Update with children taxes that are child of multiple parents is not supported.')`
  if `len(children_taxes) > len(parent_taxes.children_tax_ids.ids)` — i.e. any child tax
  appears under more than one parent. This prevents the `account_tax_filiation_rel` JOIN
  from producing duplicate aml-tag pairs.

- **Lock-date advisory (code-read):** `_compute_date_from` initialises `date_from` to
  `company.tax_lock_date + timedelta(days=1)` (falling back to today if no lock date exists).
  `_compute_display_lock_date_warning` sets a Boolean if the user overrides `date_from`
  to a date before `tax_lock_date`. The wizard form shows a warning banner in this case
  but does NOT prevent execution — the operation is non-enforced, i.e. the admin can
  deliberately update locked periods.

- **Developer-mode-only entry point (code-read):** The `res.config.settings` inherit
  places the wizard action button inside the tax settings block with
  `groups="base.group_no_one"`. This group is only assigned in Odoo's developer/technical
  mode, so the feature is intentionally hidden from regular accounting users who might run
  it without understanding the irreversibility. The wizard form itself also displays a
  prominent warning: "irreversible action … highly recommended to backup your database."

## 5. IT architecture

- **Application:** retroactive tax-grid-tag repair tool, no new persistent tables.
- **Data objects (mutated):** `account_account_tag_account_move_line_rel` junction table
  (DELETE + INSERT in-place); `account.move.line` rows (tag relationships replaced).
- **Data objects (read):** `account.tax.repartition.line`, `account.account.tag`,
  `account_account_tag_account_tax_repartition_line_rel`, `account_tax_filiation_rel`,
  `account_move_line_account_tax_rel`, `account.move` (move_type, company_id,
  tax_cash_basis_origin_move_id), `res.company` (tax_lock_date).
- **Key relations:**
  - `account.update.tax.tags.wizard -> res.company` (scope)
  - `account.move.line ->M2M account.account.tag` (via junction table, mutated)
  - `account.tax.repartition.line ->M2M account.account.tag` (source of truth)
  - `account.tax ->M2M account.tax` (children, via `account_tax_filiation_rel`)
- **Flows:** admin opens wizard in Settings (developer mode) → selects date_from → clicks
  Update → `update_amls_tax_tags` checks group-tax guard → calls
  `_modify_tag_to_aml_relation(company_id, date_from)` → single SQL CTE mutates
  `account_account_tag_account_move_line_rel` → returns array of impacted aml ids →
  `env.invalidate_all()`. No routes, no outbound calls, no scheduled actions.

## 6. Business architecture

- **Capabilities (inferred from code-read):** retroactively re-assign tax grid tags
  on historical journal items after a tax configuration change; handle group/child tax
  structures and CABA (cash-basis) moves; scope repair by company and date; advise
  on tax lock date boundary.
- **Value streams (inferred):**
  - *Tax-Config-Correction:* admin reconfigures tax repartition lines (e.g. during
    localisation upgrade) → runs wizard with date_from → historical amls re-tagged →
    tax grid reports (e.g. VAT declaration) now consistent with current tax definitions.
- **Information concepts (code-read):** `account.move.line` (target of mutation),
  `account.account.tag` (tax grid tag), `account.tax.repartition.line` (tag source of truth),
  `res.company`, `company.tax_lock_date`.
- **Organization (code-read):** `base.group_no_one` (developer/technical mode — gating
  group for the Settings entry point).
- **Policies (code-read):** company-scoped; date_from cutoff (amls before date excluded);
  child-of-multiple-parents guard (UserError); irreversible (no undo); lock-date non-enforced;
  state-agnostic (posted, draft, cancelled amls all updated).
- **Stakeholders:** System Administrator / Technical Accountant; Auditor (relies on
  consistent tax grid data for fiscal declarations).
- **Metrics:** none tracked.
- **Strategy:** `null`.

## 7. Classification

- **Value model: support** — a data-integrity maintenance tool for the accounting subsystem.
  It creates no business object, performs no transaction, generates no revenue. It is pure
  firm infrastructure (Stabell & Fjeldstad support), enabling accurate fiscal reporting
  after a tax configuration change.
- **Activity class: support.**
- **APQC: 9.0 Manage Financial Resources** — the work is tax-grid data-quality maintenance
  to support accurate VAT/tax reporting within the financial management function.

## 8. Fit-to-Standard

- **Standard capabilities:** one-shot retroactive aml re-tagging from a configurable date;
  company-scoped; group/child tax (account_tax_filiation_rel) support; CABA move handling
  via `tax_cash_basis_origin_move_id`; advisory lock-date warning; developer-mode-only
  exposure in Accounting Settings.
- **Typical fits:** post-localisation-upgrade tag repair; correcting tags after a mid-year
  tax reconfiguration; one-time data cleanup after import/migration with missing tax tags.
- **Common gaps:** no preview / dry-run mode (directly mutates DB); no rollback (backup
  advised but not automated); child tax belonging to multiple parents is hard-blocked; no
  granularity below date_from (cannot target specific taxes or journals); lock-date is
  advisory only (can overwrite locked periods).
- **Drive:** `env['account.update.tax.tags.wizard'].create({'date_from': '2024-01-01'}).update_amls_tax_tags()`;
  Settings → Technical (developer mode) → Accounting → Tax section → "Update tax tags
  on existing Journal Entries".
