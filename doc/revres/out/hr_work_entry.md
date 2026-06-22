# hr_work_entry — Reverse-Engineering Brief

The **hr_work_entry** module is the **payroll/attendance time bridge** of Odoo:
it converts an employee's working schedule into a typed, dated, conflict-checked
ledger of *payable time*. Work entries are not keyed in by hand — they are
**generated** per `hr.version` (the contract snapshot) by subtracting time off
(`resource.calendar.leaves`) from the working-time grid (`resource.calendar`),
tagging each resulting interval with an `hr.work.entry.type` that carries a
payroll code and pay rate. It is a non-application module depending only on `hr`
(and transitively `resource`): 4 own models, 0 routes, 2,293 Python LOC. Its
place in the graph is squarely between **resource** (the schedule engine it
builds on) and **payroll** (the consumer of its validated entries).

## Role & Dependencies

- **hr** — `hr.employee`, `hr.department` and `hr.version` (the contract snapshot
  every work entry belongs to and whose dates gate generation).
- **resource** (transitive) — it inherits `resource.calendar`,
  `resource.calendar.attendance` and `resource.calendar.leaves` to attach a
  `work_entry_type_id`, and calls `_attendance_intervals_batch` as its substrate.

What it adds: the **work-entry ledger + generation/validation engine** that turns
"working schedule minus time off" into payable, payroll-codeable time.

## Data Model (the ERM)

| Model | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `hr.work.entry` | HR Work Entry | 18 | `employee_id`, `version_id`, `work_entry_type_id`, `department_id`, `company_id` |
| `hr.work.entry.type` | HR Work Entry Type | 13 | `country_id` |
| `hr.work.entry.regeneration.wizard` | Regenerate Employee Work Entries | 10 | `employee_ids`, `validated_work_entry_employee_ids` |
| `hr.user.work.entry.employee` | Work Entries Employees | 4 | `user_id`, `employee_id` |

The **central model is `hr.work.entry`** (one row = one employee/day/type with a
float `duration` and a `state`); `hr.work.entry.type` is its classifier (payroll
`code`, `amount_rate`, `is_leave`/`is_work`/`is_extra_hours`). The module also
extends four models via `_inherit` without `_name` (mixins/extensions):
`hr.version` (generation watermark + `work_entry_source`), `hr.employee`,
`resource.calendar`, `resource.calendar.attendance`/`.leaves` (each gains
`work_entry_type_id`). Field distribution is relational/attribute-mixed
(Many2one 11, Boolean 13, Char 11) — a transactional record plus configuration.

## Behavior & Surfaces

- **Routes:** none — no web/RPC surface; entries are produced by backend
  generation and surfaced through views.
- **Views:** 3 form / 2 list / 1 kanban / 1 calendar / 1 pivot — the colored
  **calendar** (and pivot for hours) is the primary UX over generated entries.
- **Security:** 6 access rules, 3 record rules, **0 module groups** — officer
  (`hr.group_hr_user`) reads/writes/creates but cannot delete; `base.group_system`
  full CRUD; work-entry types and the regeneration wizard are manager-only
  (`hr.group_hr_manager`); record rules scope entries by company.

Behavior metadata can't show (code-read):
- **Generation engine** (`hr.version._get_version_work_entries_values`): pulls
  `_attendance_intervals_batch`, subtracts `resource.calendar.leaves`
  (`real_attendances = attendances − leaves − worked_leaves`), tags each interval
  with a type, then splits across local-midnight and merges same-day/same-type
  rows; bounded by `date_generated_from`/`date_generated_to` per version.
- **Conflict detection** (`_check_if_error` on every create/write/unlink): raw-SQL
  flags `state='conflict'` for any (employee, day) summing ≤0 or >24h, plus leaves
  outside the schedule and collisions with already-validated days.
- **Validation gate**: `action_validate` moves entries to `validated` ("In
  Payslip") only if no conflict; validated entries are **immutable** (cannot be
  deleted) — protecting downstream payroll.
- **Regeneration on change**: editing contract dates `_remove_work_entries`;
  changing `resource_calendar_id`/`work_entry_source` `_recompute_work_entries`
  (force-regenerates via the wizard, skipping validated periods); a monthly cron
  `_cron_generate_missing_work_entries` batch-fills the current period.

## Value-Configuration Classification

Against Stabell & Fjeldstad, hr_work_entry is **support** (firm infrastructure),
not a primary chain/shop/network flow. It does not transform, solve or mediate a
customer transaction; it is the payroll-prep time-tracking backbone that sits
**on top of `resource`** (same `support` value model) and feeds **payroll**. It
takes the resource working schedule and time off and turns them into typed,
rate-bearing, validatable payable time — a bridge, not a producer.
`activity_class = support`.

## APQC PCF Hint

**7.0 Develop and Manage Human Capital** — the same category as its `hr` parent
and the `resource` module it extends. It is the "manage employee time, attendance
and compensation inputs" slice of 7.0: it prepares the payable-time inputs to
payroll. Not 9.0 Manage Financial Resources (it computes no accounting), and not
a primary value flow.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`); there are no routes to curl. Real
queries:

```python
# generate a month of entries for one employee, then count them
emp = env['hr.employee'].search([], limit=1)
emp.generate_work_entries('2026-06-01', '2026-06-30')
env['hr.work.entry'].search_count([('employee_id', '=', emp.id)])

# the type catalog: payroll code, pay rate, leave/overtime flags
env['hr.work.entry.type'].search([], limit=10).mapped(('name','code','amount_rate','is_leave','is_extra_hours'))

# generated entries and conflicts; try to push drafts "In Payslip"
env['hr.work.entry'].search([], limit=5).mapped(('display_name','date','duration','state','work_entry_type_id.code'))
env['hr.work.entry'].search([('state','=','conflict')], limit=5).mapped(('employee_id.name','date','duration'))
env['hr.work.entry'].search([('state','=','draft')]).action_validate()
```

## Open Questions

- The `work_entry_source` overrides (`attendances`/`planning`) contributed by
  `hr_attendance` / planning bridges, and how they replace
  `_get_attendance_intervals`.
- How `hr_work_entry_holidays` changes leave-type precedence
  (`_get_interval_leave_work_entry_type`) so global time off wins over home
  working.
- The downstream `hr_payroll` contract: which codes/rates map to which salary
  rules, and how worked-leave (`is_work` leave) and `is_extra_hours` are paid.
- Flexible / fully-flexible calendar behaviour on leave-interval synthesis versus
  statically-generated entries.

*Provenance: structural facts from `extract_module.py` / `extract_frontend.py`
(`facts/hr_work_entry.facts.json`, `frontend/hr_work_entry.frontend.json`);
behavioral notes code-read from `addons/hr_work_entry/models/` (hr_work_entry.py,
hr_work_entry_type.py, hr_employee.py, hr_version.py, resource_calendar.py) and
`wizard/hr_work_entry_regeneration_wizard.py`. Odoo 19.0.*
