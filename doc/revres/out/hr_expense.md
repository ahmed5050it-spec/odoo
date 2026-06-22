# hr_expense — Reverse-Engineering Brief

The **Expenses** module (`Human Resources/Expenses`, v2.1, `application: true`,
`auto_install: false`) lets employees capture, submit, and get reimbursed for
business expenses, and is the **bridge that turns an HR event into an accounting
document**. An expense moves through an approval workflow and, once approved, is
*posted* — creating an `account.move` (employee receipt) or an `account.move` +
`account.payment` (company-paid). It depends on `account`, `hr`, and `web_tour`.
It is a **support** module: it sits beside the primary value chain, feeding
9.0 Finance with every posting and — through the auto-installed `sale_expense`
bridge — re-invoicing costs into 3.0 Sales (`sale.order`). Note: in Odoo 19 there
is no `hr.expense.sheet`; expenses post directly (a `former_sheet_id` legacy
integer is retained for grouping).

## Role & Dependencies

- **account** — the whole point of posting: expenses become `account.move` /
  `account.move.line` / `account.payment`; uses journals, taxes, analytic.
- **hr** — the subject of an expense is an `hr.employee`; approval routing uses
  department managers and `expense_manager_id`.
- **web_tour** — ships the `hr_expense_tour` onboarding tour (frontend asset).

Capability added on top: an **employee-expense lifecycle** (capture → approve →
reimburse) plus the accounting bridge and analytic cost tagging that the base HR
and accounting modules do not provide on their own.

## Data Model (the ERM)

| _name | _description | #fields | key relations |
|-------|--------------|---------|---------------|
| `hr.expense` | Expense | 46 | employee_id→hr.employee, product_id→product.product, account_id→account.account, account_move_id→account.move, payment_method_line_id→account.payment.method.line, tax_ids→account.tax |
| `hr.expense.split.wizard` | Expense Split Wizard | 7 | expense_id→hr.expense, expense_split_line_ids→hr.expense.split |
| `hr.expense.split` | Expense Split | 15 | expense_id→hr.expense, product_id→product.product |
| `hr.expense.post.wizard` | Expense Posting Wizard | 3 | employee_journal_id→account.journal |
| `hr.expense.refuse.wizard` | Expense Refuse Reason Wizard | 2 | expense_ids→hr.expense |

The **central model is `hr.expense`** (the rest are transient wizards). The
module also carries **16 inherit-only extensions** (`_inherit` without `_name`):
notably `account.move`/`account.move.line` (add `expense_ids`/`expense_id`),
`account.payment`, `product.template` (`can_be_expensed`), `hr.employee`
(`expense_manager_id`), and `res.company`/`res.config.settings`. Field mix is
**relational-heavy** (31 Many2one, 9 Many2many) with a strong **monetary** core
(12 Monetary fields for amounts/taxes/currency) — characteristic of a financial
document model with multi-currency support.

## Behavior & Surfaces

- **Routes:** none (`route_count: 0`). No public HTTP/RPC controller surface;
  all interaction is through the backend ORM/UI and the mail alias.
- **Views:** backend-form-centric — 2 form, 4 list, 1 kanban, plus 1 pivot +
  1 graph (the analytics/dashboard) and 1 activity. UX is an internal back-office
  approval queue, not a customer-facing portal.
- **Security:** 14 access rules, **12 record rules**, **3 groups** —
  `group_hr_expense_team_approver` (Team Approver), `group_hr_expense_user`
  (All Approver), `group_hr_expense_manager` (Administrator). Record rules scope
  employees to their own expenses and approvers to their team/department.
- **Lifecycle (code-read):** `state` is computed (`draft → submitted → approved
  → posted → in_payment → paid`; `refused` terminal) from `approval_state` and
  the linked move's `payment_state`. `action_submit` schedules a review
  activity (auto-validates if no approver); `action_approve` runs duplicate
  detection; `action_post` creates the accounting document; `action_reset`
  reverses/unlinks it.
- **Intake (code-read):** `message_new` creates a draft expense from an email,
  parsing product code / price / currency from the subject.

## Value-Configuration Classification

**Value model: `support`** (Stabell & Fjeldstad). `hr_expense` is a cross-cutting
HR-administration function, not a transform/solve/mediate primary activity. It
**bridges into two primary domains**: it feeds **accounting** (`account.move` /
`account.payment` on every post — the AP/reimbursement leg) and, via the
auto-installed `sale_expense` bridge (`product.template.expense_policy` defined in
`sale` + `sale_order_id` on `hr.expense`), it **re-invoices into sales**
(`sale.order.line`). The connective tissue is **analytic accounting**:
`hr.expense` inherits `analytic.mixin`, so each posted move line carries an
`analytic_distribution` that lands as an `account.analytic.line` cost on the value
unit (project/order) — exactly `PRIMARY_SUPPORT_INTEGRATION_AR.md` link #4
(المصاريف → الخدمة عبر `expense_policy`). **Activity class: support.**

## APQC PCF Hint

Most likely **7.0 Develop and Manage Human Capital** — the module's home,
ownership (HR approver groups), and subject (`hr.employee`) are HR; the
submit/approve/reimburse cycle is HR administration (employee reimbursement).
It *feeds* **9.0 Finance** (posting) and **3.0 Market and Sell** (re-invoice) as
downstream consumers, but those are not its owning activity. (inferred)

## How to Drive It

Use the **run-odoo** skill (`odoo shell`). No routes to curl. Real-model examples:

```python
# Inspect the expense lifecycle states
env['hr.expense'].fields_get(['state','approval_state'])['state']['selection']
# List recent expenses with their workflow + payer
env['hr.expense'].search([], limit=5).mapped(('name','state','payment_mode','total_amount'))
# Post an approved expense and watch account_move_id get set (the HR->accounting bridge)
e = env['hr.expense'].search([('state','=','approved')], limit=1); e.action_post()
# Confirm the sale re-invoice policy (requires sale_expense + a configured product)
env['product.template'].fields_get(['expense_policy'])
```

## Open Questions

- The exact recompute order of the ~15 monetary/tax compute methods when a
  **custom currency rate** is set (`_compute_total_amount` vs `_compute_tax_amount`
  vs `_compute_currency_rate`).
- Batching semantics of `action_post` when employee-paid and company-paid
  expenses span multiple journals / payment methods.
- Whether **re-invoicing** is in scope for a given deployment (needs the
  auto-installed `sale_expense` bridge and products with `expense_policy` set).

---
*Provenance: static facts from `extract_module.py` (`facts/hr_expense.facts.json`)
+ `extract_frontend.py`; behavioral notes from reading
`addons/hr_expense/models/hr_expense.py` and `addons/sale_expense/models/`. Odoo 19.0.*
