# hr_homeworking_calendar — Architecture Brief

> Module: `hr_homeworking_calendar` · Category: Human Resources/Remote Work · Depends: `hr_homeworking`, `calendar` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **7.0 Develop and Manage Human Capital**
> Odoo 19.0 · Facts: `doc/revres/facts/hr_homeworking_calendar.facts.json` · Frontend: `doc/revres/frontend/hr_homeworking_calendar.frontend.json`

## 1. Summary

`hr_homeworking_calendar` (UI name *Remote Work with calendar*) is the
**calendar visualisation + edit layer** on top of `hr_homeworking`. It lets users
**see** each employee's remote-work schedule on the standard attendee calendar and
**edit** it through a single dialog, `homework.location.wizard`. The wizard either
sets the **recurring weekday default** (writing `res.users.<weekday>_location_id`)
or a **one-day exception** (creating/updating/deleting a `hr.employee.location`
row). It owns **no persistent business object** — its only declared model is a
`TransientModel` (the wizard, 8 fields) plus two `_inherit`-only models adding the
calendar-feed methods (**0 routes, 1 ACL + 2 ir.rule, ~336 py LOC**,
`auto_install: true`). Crucially, **despite `depends=['calendar']` it creates no
`calendar.event` records** — the schedule is a *view overlay*, not calendar data.

## 2. Structure (evidence)

- **Models (1 transient + 2 inherit):** `homework.location.wizard` (`TransientModel`:
  `date`, `weekly` Boolean, `work_location_id`, `employee_id`, …);
  `hr.employee` (+`_get_worklocation(start,end)` building the calendar payload);
  `res.partner` (+`get_worklocation(start,end)`, the RPC entry point).
- **Routes:** **0** — no web/RPC surface of its own; no external calls (gap #7 empty).
- **Security:** 1 ACL (`homework.location.wizard` CRUD for `base.group_user`) +
  2 `ir.rule` — `homeworking_location_wizard_own_rule` lets a user run the wizard
  only for themselves; `..._admin_rule` gives HR the `(1=1)` domain. No own
  `res.groups`.
- **Views:** **0** model views (xml_loc=187 is the wizard form +
  `set_location_wizard_action`, `target='new'`, bound). The schedule itself is
  rendered by **patching the calendar module in JS**, not by XML.

## 3. Frontend (gap #3)

**5 JS / 2 XML**, bundle `web.assets_backend` (+`web.assets_unit_tests`).
**No OWL components, no registry adds** — **6 prototype patches** over the
`calendar` app: `AttendeeCalendarModel`, `AttendeeCalendarController`,
`AttendeeCalendarCommonRenderer`, `AttendeeCalendarYearRenderer`,
`AttendeeCalendarCommonPopover`. `calendar_model.js` (`updateData`/
`loadWorkLocations`) RPC-calls `res.partner.get_worklocation` and synthesises
virtual day-cells via `createHomeworkingRecordAt` (records carry
`resModel:'hr.employee.location'`, `homeworking:true`, and a `ghostRecord` flag for
weekly-default cells with no `hr_employee_location_id`). The controller routes a
click to the wizard action and deletes by clearing the weekly default (ghost) or
`orm.unlink('hr.employee.location')` (real exception). The reported "services"
`date`/`weekday`/`weekly` are template/prop hooks, not Odoo registry services.

## 4. Behavior (beyond metadata)

- **The write engine (code-read):** `homework.location.wizard.set_employee_location`
  is where every calendar edit lands. `weekday = date.weekday()`,
  `default = DAYS[weekday]`. **Branch A (`weekly=True`):** delete any same-date
  exception, then `employee.sudo().user_id.write({DAYS[weekday]: work_location_id})`
  — so "recurring" means setting the **day-of-week default through the user record**
  (related-synced to `hr.employee`), *not* a `calendar.event`. **Branch B (one-off):**
  if the chosen location equals the weekday default it **unlinks** the exception
  (no redundant row); elif an exception exists it **writes** it; else it **creates**
  a new `hr.employee.location`.
- **The calendar feed (code-read):** `hr.employee._get_worklocation(start,end)` seeds
  per-employee `user_id`/`partner_id`/`employee_name`, emits the 7 weekday defaults,
  then `search_read`s `hr.employee.location` in the window and folds each dated row
  into `exceptions[date]` carrying `hr_employee_location_id` (so the front end can
  tell a real, editable exception from a synthesised default). `res.partner.get_worklocation`
  resolves employees by `work_contact_id` (scoped to `env.company`) and delegates here.
- **Calendar = overlay, not events (code-read):** grep confirms `calendar.event`
  appears only in a test mock. The JS `createHomeworkingRecordAt` builds ghost/real
  cells; `deleteRecord` clears `res.users.<weekday>_location_id` for a ghost else
  unlinks the exception; `editRecord` opens the wizard. No event rows are written.
- **Wizard UX coupling (code-read):** `_compute_day_week_string`
  (`@depends('date')`) renders the date's weekday name (`format_date 'EEEE'`) into
  the form's *"Repeat every &lt;weekday&gt;"* label next to the `weekly` checkbox; the
  action passes `default_date`/`default_work_location_id` into context, which the
  wizard fields default from.
- **External integration (static, gap #7):** none.

## 5. IT architecture

- **Application:** calendar visualisation + edit dialog for the `hr_homeworking`
  schedule (writes weekly defaults or dated exceptions; surfaced by patching the
  attendee calendar).
- **Data objects:** `homework.location.wizard` + inherits on `hr.employee`,
  `res.partner`.
- **Key relations:** wizard → `hr.work.location` + `hr.employee` (transient);
  `set_employee_location` → `hr.employee.location` (create/write/unlink) **or**
  `res.users.<weekday>_location_id`; `get_worklocation` → `hr.employee` via
  `work_contact_id`.
- **Flows:** OWL `loadWorkLocations` → RPC `get_worklocation` →
  `_get_worklocation` payload; click cell → wizard action →
  `set_employee_location`; delete ghost → clear default, delete real → unlink.

## 6. Business architecture

- **Capabilities (inferred):** visualise the schedule on the attendee calendar;
  edit via one dialog; set a recurring weekday default or a one-day exception;
  auto-prune redundant exceptions; delete a day's location.
- **Value streams (inferred):** *Calendar-Edit-to-Schedule* (click day → wizard →
  exception or weekday default written → reload) and *Schedule-to-Calendar-View*
  (merge defaults + exceptions → paint cells).
- **Information concepts (auto):** the wizard (transient edit intent);
  `hr.employee.location` and the weekday defaults (owned by `hr_homeworking`); the
  virtual calendar cell (ghost vs real).
- **Policies (inferred):** wizard self-only for users (HR for all); `weekly` sets
  the default + clears conflicting exceptions; an exception equal to the default is
  not stored; ghost delete clears the default, real delete unlinks only that row;
  **no `calendar.event` is ever created**.
- **Strategy:** `null` (human). **Organization/Products:** none own.

## 7. Classification

- **Value model: support** — a thin UX/integration tier on workforce-administration
  data; it inherits `hr_homeworking`'s classification (Stabell & Fjeldstad *support*;
  Porter support activity). It owns no chain/shop/network business object.
- **Activity class: support.**
- **APQC: 7.0 Develop and Manage Human Capital** — same employee-information /
  workforce-management nuance as its parent, here adding a calendar view + edit
  dialog. The `calendar` dependency is **purely the attendee-calendar UI being
  patched** (no `calendar.event`), so this is not a scheduling/event-management
  capability in its own right. `8.0 Manage IT` rejected (no routes/external
  calls/IT plumbing) — it is the presentation/editing tier of an HR people-data
  feature.

## 8. Fit-to-Standard

- **Standard:** attendee-calendar rendering of the schedule; the
  `homework.location.wizard` dialog (weekly default or dated exception);
  auto-pruning of exceptions matching the default; delete affordances;
  server-side merge of defaults + exceptions (`get_worklocation`).
- **Typical fits:** seeing/editing hybrid days on the same calendar used for
  meetings; employee self-scheduling by clicking the calendar; HR adjusting many
  employees visually.
- **Common gaps:** **no `calendar.event`**, so the schedule does NOT appear in
  synced external calendars (Google/Outlook) or block meeting availability;
  inherits the one-location-per-day limit; dialog-per-day editing (no drag-to-recur);
  all UX is JS patches over the calendar module (tight coupling, gap #3); no
  approval/notification.
- **Drive:** `env['res.partner'].get_worklocation(start, end)` for the feed; create
  a wizard and call `set_employee_location()` for both `weekly=False`/`True`;
  `rg 'calendar.event' addons/hr_homeworking_calendar` to confirm no event rows.
