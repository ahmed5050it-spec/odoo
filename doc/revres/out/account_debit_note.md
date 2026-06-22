# account_debit_note — Architecture Brief

> Module: `account_debit_note` · Category: Accounting/Accounting · Depends: `account` · `auto_install: false`
> Value model: **chain** · Activity class: **support** · APQC: **9.0 Manage Financial Resources**
> Odoo 19.0 · Facts: `doc/revres/facts/account_debit_note.facts.json` · Frontend: `doc/revres/frontend/account_debit_note.frontend.json`

## 1. Summary

`account_debit_note` adds a legally recognised **Debit Note** document type to Odoo Accounting.
A debit note is the positive-correction counterpart to a credit note: it increases the amount
owed on a posted invoice, or converts a posted credit note back into a payable.
The module delivers a **wizard** (`account.debit.note`, TransientModel), **extensions** to
`account.move` (3 fields: `debit_origin_id`, `debit_note_ids`, `debit_note_count`) and
`account.journal` (1 field: `debit_sequence`), a form-action button on posted invoices, PDF
template overrides, and search filters.
It owns **no new persistent business table**: everything it writes goes into the existing
`account.move` rows.
Stats: **1 wizard model + 2 inherits, 0 routes, 258 py LOC, 172 xml LOC, 1 access rule**.

## 2. Structure (evidence)

- **Models:**
  - `account.debit.note` (`wizard/account_debit_note.py`, TransientModel): fields
    `move_ids` (M2M `account.move`), `date`, `reason`, `journal_id`, `copy_lines`,
    computed `move_type`, `journal_type`, related `country_code`; methods
    `default_get`, `_compute_from_moves`, `_compute_journal_type`,
    `_prepare_default_values`, `create_debit`.
  - `account.move` (`models/account_move.py`): adds `debit_origin_id` (M2O `account.move`,
    `btree_not_null` index, `copy=False`), `debit_note_ids` (O2M inverse),
    `debit_note_count` (Integer, computed); adds methods `action_view_debit_notes`,
    `action_debit_note`, `_get_last_sequence_domain`, `_get_starting_sequence`,
    `_get_copy_message_content`.
  - `account.journal` (`models/account_journal.py`): adds stored Boolean `debit_sequence`
    (defaults True for sale/purchase journals).
- **Routes:** 0 — all interaction is ORM wizard / backend form actions.
- **Security:** 1 `ir.model.access` row for `account.debit.note` (group `account.group_account_invoice`).
- **Views:** wizard form `account.debit.note.form`; inherits on `account.move` form (smart
  button + `debit_origin_id` field + Debit Note action button); filter inherits on invoice
  search, move search, move-line search; journal form inherit (debit_sequence field);
  QWeb PDF template inherit (`account.report_invoice_document`).

## 3. Frontend (gap #3)

**None.** `frontend.present = false` — 0 JS files, 0 OWL components, 0 registry additions.
The Debit Note wizard is a standard server-rendered Odoo form dialog (`target: new`).
The smart button on the invoice form is plain XML with `oe_stat_button`.
No OWL components, no asset bundles, no client-side code.

## 4. Behavior (beyond metadata)

- **Strict entry-guard in `default_get` (code-read):** The wizard raises `UserError` before
  the user even sees the form if any selected `account.move` is not in state `'posted'`, if
  any move already has `debit_origin_id` set (preventing double-debiting the same invoice),
  or if move_type is not one of the four eligible types. These rules are enforcement
  logic, not ORM constraints — metadata shows fields but not the guard.

- **Refund-to-invoice type conversion in `create_debit` (code-read):** When the source move
  is `in_refund` or `out_refund`, `_prepare_default_values` maps the type to `in_invoice` or
  `out_invoice` respectively before calling `move.copy()`. This makes a debit note from a
  credit note a *positive payable*, not another refund. The call uses
  `move.with_context(include_business_fields=True)` so that `sale.order` / `purchase.order`
  backlinks are carried into the new move.

- **Separate numbering sequence (code-read):** `_get_last_sequence_domain` appends
  `AND debit_origin_id IS [NOT] NULL` when `journal.debit_sequence` is `True`, splitting
  the journal's sequence into two independent series. `_get_starting_sequence` prefixes the
  first debit-invoice sequence with `'D'` (e.g. `DINV/2024/00001`) to make them visually
  distinct. `debit_sequence` defaults `True` for sale/purchase journals via
  `_compute_debit_sequence` (`@api.depends('type')`).

- **PDF title branch (code-read):** The QWeb template `account.report_invoice_document` is
  inherited to replace every title variant (`invoice_title`, `draft_invoice_title`,
  `cancelled_invoice_title`, `proforma_invoice_title`, `draft_proforma_invoice_title`,
  `cancelled_proforma_invoice_title`) with a `t-if="o.debit_origin_id"` branch that renders
  "Debit Note" instead of "Invoice". The date label on `out_invoice` documents also switches
  to "Debit Note Date". This is a print-time template branch, not a stored model field.

- **Chatter message (code-read):** `_get_copy_message_content` is overridden so that when
  a move is copied with `default.get('debit_origin_id')` set, the chatter thread on the
  new debit note records "This debit note was created from: <link to original>", providing
  a traceable audit trail.

## 5. IT architecture

- **Application:** debit-note extension to the `account` module; no new database tables.
- **Data objects:** `account.move` (extended with debit-note fields), `account.journal`
  (extended with `debit_sequence`), `account.debit.note` (transient wizard).
- **Key relations:**
  - `account.move.debit_origin_id -> account.move` (indexed with `btree_not_null`; the
    debit note points at its source invoice)
  - `account.move.debit_note_ids` (One2many inverse: original invoice sees all its debit notes)
  - `account.debit.note ->M2M account.move` (wizard input, via `account_move_debit_move` m2m table)
- **Flows:** User selects posted invoices in list/form → triggers `action_debit_note` →
  opens wizard dialog → `default_get` validates → user fills date/reason/copy_lines/journal →
  `create_debit` calls `move.copy(default=_prepare_default_values(move))` → new `account.move`
  records created in draft with `debit_origin_id` set → wizard returns act_window to the
  new move(s).
- **No routes, no outbound calls, no scheduled actions.**

## 6. Business architecture

- **Capabilities (inferred from code-read):** issue formal upward invoice corrections;
  cancel vendor credit notes; maintain debit-note traceability; enforce per-journal debit
  sequences; render debit notes correctly on printed PDFs.
- **Value streams (inferred):**
  - *Invoice-Correction (upward):* posted invoice → Debit Note wizard → draft debit note
    → accountant reviews/posts → customer owes more.
  - *Credit-Note Cancellation:* posted credit note → Debit Note wizard → draft debit note
    (converted to invoice type) → accountant posts → offsets the credit note.
- **Information concepts (auto):** `account.move`, `account.journal`, `account.debit.note`.
- **Organization:** `account.group_account_invoice` controls wizard access; `account.group_account_user`
  (inherited from `account`) for reading.
- **Policies (code-read):** only `posted` moves are eligible; no double-debiting;
  only invoice/refund move types; refunds converted to invoice type; lines not copied by
  default for refund-source debit notes.
- **Stakeholders:** Accountant / Billing Clerk; Customer / Vendor.
- **Metrics:** `debit_note_count` (computed per invoice via `_read_group`).
- **Strategy:** `null`.

## 7. Classification

- **Value model: chain** — debit notes are a direct element of the Order-to-Cash and
  Procure-to-Pay financial settlement processes: they formally adjust amounts payable/receivable.
  The module is a legal-compliance extension to a primary chain activity.
- **Activity class: support** — within the chain, debit notes are a correction/adjustment
  mechanism, not a revenue-generating primary activity.
- **APQC: 9.0 Manage Financial Resources** — the work is formal financial document issuance
  and correction within Accounts Receivable / Accounts Payable processes.

## 8. Fit-to-Standard

- **Standard capabilities:** debit note wizard from posted invoice/bill/credit note; optional
  line copy; per-journal separate sequence with 'D' prefix; PDF title switching; smart button
  count on original; search filter on invoice and journal item views.
- **Typical fits:** correcting undercharged invoices; cancelling a credit note by converting
  it to a positive invoice; multi-company deployments with compliance-mandated separate
  debit note numbering.
- **Common gaps:** no automatic reconciliation between original and debit note; no approval
  workflow before posting; no country-specific legal format beyond 'D' prefix (l10n modules
  extend this); `copy_lines` is silently ignored for refund-source debit notes.
- **Drive:** `env['account.debit.note'].with_context(active_model='account.move',
  active_ids=[move_id]).create({'date': fields.Date.today(), 'reason': 'correction',
  'copy_lines': True}).create_debit()`; `env['account.move'].browse(move_id).debit_note_ids`.
