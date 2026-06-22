# resource — Reverse-Engineering Brief

The **resource** module is the working-time and capacity backbone of Odoo: it
defines *when* and *how much* a resource (a person or a machine) is available to
work. It owns the working-schedule master data — `resource.calendar` (a weekly
grid of `resource.calendar.attendance` periods plus `resource.calendar.leaves`
time off) and `resource.resource` (the schedulable resource) — and, crucially,
an **interval engine** that turns that data into concrete working-time and
availability for any datetime range. It is a `Hidden`, non-application module
depending only on `base` and `web`, deliberately thin in data but heavy in
computation (2,576 Python LOC over 5 models, 0 routes). It is firm
infrastructure: HR, manufacturing and project scheduling all consume it — the
working-time analogue of what `analytic` is for costs.

## Role & Dependencies

- **base** — core ORM, `res.company`, `res.users`, `res.partner` (timezones via
  `_tz_get`); calendars and resources are company-scoped master data.
- **web** — backend assets for the calendar grid form/list editor (the only UI).

What it adds on top: a reusable **working-schedule + time-off model** and the
**capacity-calculation engine** (`_work_intervals_batch` and friends) that every
scheduling app builds on, plus `resource.mixin` to make any record schedulable.

## Data Model (the ERM)

| Model | _description | #fields | Key relations |
|-------|--------------|--------:|---------------|
| `resource.calendar` | Resource Working Time | 21 | `attendance_ids`, `leave_ids`/`global_leave_ids`, `company_id` |
| `resource.calendar.attendance` | Work Detail | 13 | `calendar_id` |
| `resource.calendar.leaves` | Resource Time Off Detail | 7 | `calendar_id`, `resource_id`, `company_id` |
| `resource.resource` | Resources | 12 | `calendar_id`, `user_id`, `company_id` |
| `resource.mixin` | Resource Mixin | 4 | `resource_id`, `resource_calendar_id` (related) |

The **central model is `resource.calendar`** (the schedule + the engine);
`resource.resource` is the schedulable unit hung off it. `resource.mixin` is the
polymorphic/abstract model (`_inherit` without `_name`) inherited by downstream
records (`hr.employee`, `mrp.workcenter`) to attach a `resource_id` and calendar,
auto-creating the `resource.resource` on `create`. Field distribution is
relation-light and attribute/Selection-heavy (Many2one 13, Selection 10, Float 9,
Boolean 9) — typical of configuration/master data rather than a transactional
document.

## Behavior & Surfaces

- **Routes:** none — there is no web/RPC surface; this is pure backend
  infrastructure invoked by other Python code.
- **Views:** 4 form / 4 list / 3 search / 1 calendar — a plain admin editor for
  the working-time grid; no kanban/pivot/graph, underlining its master-data role.
- **Security:** 8 access rules, 5 record rules, **0 module groups** — reads via
  `base.group_user`, full CRUD via `base.group_system`; record rules
  (`resource_security.xml`) scope calendars/attendances/leaves/resources by
  company. Constraints: `_check_overlap` (no overlapping attendances),
  `CHECK(time_efficiency>0)`, leave `date_from <= date_to`.

Behavior metadata can't show (code-read):
- **`_attendance_intervals_batch`** expands the weekly attendance grid into
  `(start, end, attendance)` tuples via `rrule`, handling two-week alternating
  calendars, per-resource timezones, and flexible/duration-based schedules.
- **`_work_intervals_batch` = attendances − leaves** (Intervals set difference);
  this is the join point behind `get_work_hours_count`, `get_work_duration_data`,
  `plan_hours`/`plan_days`, `_adjust_to_calendar` and `_unavailable_intervals`.
- **`resource.calendar.leaves`** with `resource_id = False` is a *global* company
  closure (subtracts for all); set, it is resource-specific; `time_type`
  distinguishes absence from work-equivalent time.
- **Timezone correctness** is pervasive: inputs localized to UTC, computed in the
  resource/calendar tz, reverted to the caller's tz on output.

## Value-Configuration Classification

Against Stabell & Fjeldstad, resource is **support** (firm infrastructure), not a
primary chain/shop/network flow. It does not transform, solve, or mediate a
customer transaction; it supplies the working-time substrate that *other*
modules' value configurations stand on. `activity_class = support`. It is exactly
analogous to `analytic`: analytic is the shared vessel for cost/revenue, resource
is the shared vessel for working-time and availability. Evidence: a grep shows
`hr`, `hr_attendance`, `hr_calendar`, `hr_holidays`, `hr_timesheet`,
`hr_work_entry` and `mrp` all call its interval engine.

## APQC PCF Hint

**7.0 Develop and Manage Human Capital** — the same category as `hr`. The
dominant use is workforce scheduling and time/absence management (employee work
schedules and time off via `resource.calendar` / `resource.calendar.leaves`), and
`resource.resource` models the workforce/work-center whose capacity is planned.
Not 8.0 Manage IT (this is business scheduling data, not IT services) and not the
over-generic 13.0 Develop and Manage Business Capabilities; its material-resource
reuse in `mrp` extends it into manufacturing capacity planning, but human-capital
working-time is the defining purpose, so 7.0 is the primary home.

## How to Drive It

Use the **run-odoo** skill (`odoo shell`); there are no routes to curl. Real
queries:

```python
# the company default working schedule + its computed capacity
env['resource.calendar'].search([], limit=5).mapped(('name','hours_per_day','hours_per_week','tz'))

# the engine: working hours in a period, and "8 working hours from Monday 08:00"
from datetime import datetime
cal = env.company.resource_calendar_id
cal.get_work_hours_count(datetime(2026,6,1), datetime(2026,6,30))
cal.plan_hours(8, datetime(2026,6,22,8,0))

# resources and global (company-wide) time off
env['resource.resource'].search([], limit=5).mapped(('name','resource_type','calendar_id.name'))
env['resource.calendar.leaves'].search([('resource_id','=',False)], limit=5).mapped(('name','date_from','date_to'))
```

## Open Questions

- How `hr`/contract modules override `_get_calendars_validity_within_period` so
  the correct calendar applies per date range (base treats validity as the whole
  period).
- How `mrp` work-order scheduling consumes `plan_hours`/`_adjust_to_calendar` and
  applies `resource.resource.time_efficiency` to operation durations.
- Performance of the `rrule` + `Intervals` math over long horizons and many
  resources, including per-timezone localization.
- Flexible / duration-based interval synthesis edge cases (centring on 12:00,
  capping at `hours_per_week`) and how downstream overtime/time-off math reads
  them.

*Provenance: structural facts from `extract_module.py` / `extract_frontend.py`
(`facts/resource.facts.json`); behavioral notes code-read from
`addons/resource/models/` (resource_calendar.py, resource_resource.py,
resource_calendar_attendance.py, resource_calendar_leaves.py, resource_mixin.py).
Odoo 19.0.*
