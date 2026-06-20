# hr_homeworking — Architecture Brief

> Module: `hr_homeworking` · Category: Human Resources/Remote Work · Depends: `hr` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **7.0 Develop and Manage Human Capital**
> Odoo 19.0 · Facts: `doc/revres/facts/hr_homeworking.facts.json` · Frontend: `doc/revres/frontend/hr_homeworking.frontend.json`

## 1. Summary

`hr_homeworking` (UI name *Remote Work*) models **where each employee works**.
A schedule has two layers: a **recurring weekly default** (7 day-of-week
`Many2one` fields `monday_location_id`..`sunday_location_id` on `hr.employee`)
and **dated exceptions** stored as `hr.employee.location` rows (one per employee
per day, enforced by a `unique(employee_id, date)` constraint). The effective
"today's location" is always `exceptional_location_id or employee[dayfield]` —
the dated exception wins. That resolved location is then published as a **presence
icon** and a **Discuss IM-status badge**. It owns exactly **one small model**
(`hr.employee.location`, 7 fields) and otherwise decorates `hr.employee`,
`hr.employee.public`, `hr.work.location`, `res.users`, `res.partner`
(**0 routes, 2 ACL + 2 ir.rule, ~326 py LOC**, `auto_install: true`). Its
substance is the **two-layer resolution + the cross-model presence side-effects**.

## 2. Structure (evidence)

- **Models (1 own + 5 inherit):** `hr.employee.location` (the dated exception);
  `hr.employee` (+7 weekday default m2o, `exceptional_location_id` compute,
  `hr_icon_display` `selection_add` presence_home/office/other); `hr.employee.public`
  (read-only mirror of the 7 day fields); `hr.work.location` (delete guard);
  `res.users` (7 day fields `related readonly=False` to the employee + self
  read/write sync); `res.partner` (IM-status decoration).
- **Routes:** **0** — no web/RPC surface; no external calls (gap #7 empty).
- **Security:** 2 ACL (full CRUD for `base.group_user` and `hr.group_hr_user`) +
  2 `ir.rule` — `homeworking_own_rule` scopes a regular user to their own
  `hr.employee.location` rows; `homeworking_admin_rule` gives HR the `(1=1)` domain.
  No own `res.groups`.
- **Views:** **0** own model views (xml_loc=167 is form/list inheritance adding
  the day fields onto existing `hr.employee`/`res.users` views).

## 3. Frontend (gap #3)

**1 JS / 2 XML**, bundle `web.assets_backend` (+`web.assets_unit_tests`).
**No OWL components, no registry adds** — **4 prototype patches**.
`static/src/components/hr_presence_status/hr_presence_status.js` patches the `hr`
module's `HrPresenceStatus`, `HrPresenceStatusPill`, `HrPresenceStatusPrivate`,
`HrPresenceStatusPrivatePill` so that when a record carries a `work_location_type`
the badge swaps its icon (`home`→`fa-home`, `office`→`fa-building`,
`other`→`fa-map-marker`), recolors by `hr_presence_state`, and labels with
`work_location_name` (else *Unspecified*); it also appends
`work_location_type`/`work_location_name`/`hr_presence_state` to each widget's
`fieldDependencies`. `im_status_patch.xml` and the avatar-card popover XML extend
the avatar card.

## 4. Behavior (beyond metadata)

- **Two-layer resolution (code-read):** `_get_current_day_location_field()` returns
  `DAYS[fields.Date.today().weekday()]`; `_compute_exceptional_location_id` searches
  `hr.employee.location` for `date == today`. Every read of the effective location
  is `exceptional_location_id or employee[dayfield]` — the dated exception always
  overrides the weekly default. The fields look like 8 unrelated m2o; the
  precedence is invisible to metadata.
- **`get_views` day-field hack (code-read):** because "today's location" lives in a
  different column each weekday, `hr.employee.get_views` string-replaces the
  placeholder `today_location_name` (search arch) and `work_location_name`
  (list arch) with the live day field and injects its definition via
  `fields_get` — a view-time arch rewrite so users can group/sort by where people
  work today.
- **Presence + IM side-effects (code-read):** `_compute_presence_icon` sets
  `hr_icon_display = f'presence_{location_type}'` and forces
  `show_hr_icon_display`; `res.users`/`res.partner._compute_im_status` rewrite the
  Discuss status to `'<location_type>_<state>'` (e.g. `home_online`). One location
  row changes both the kanban icon **and** the chat badge.
- **Referential guard + user write-through (code-read):**
  `hr.work.location._unlink_except_used_by_employee` (`@api.ondelete`) blocks
  deleting a location referenced by any weekly default (`UserError`) but
  cascade-unlinks `hr.employee.location` exceptions; `res.users` exposes the 7 day
  fields as `related readonly=False` and adds `DAYS` to
  `_get_employee_fields_to_sync`/`SELF_READABLE_FIELDS`/`SELF_WRITEABLE_FIELDS`, so
  a user editing their own schedule writes straight through to `hr.employee`.
- **External integration (static, gap #7):** none — `http_call_sites=0`, no SDKs,
  no endpoints.

## 5. IT architecture

- **Application:** per-employee work-location schedule (weekly defaults + dated
  exceptions) surfaced as a presence/IM signal.
- **Data objects:** `hr.employee.location` + inherits on `hr.employee`,
  `hr.employee.public`, `hr.work.location`, `res.users`, `res.partner`.
- **Key relations:** `hr.employee.location → hr.employee` (cascade) + `hr.work.location`,
  `unique(employee_id, date)`; `hr.employee → hr.work.location ×7` +
  `exceptional_location_id`; `res.users → hr.employee` (7 related fields).
- **Flows:** resolve-today (`DAYS[weekday]`, exception-or-default) → presence icon
  + IM status; `get_views` arch rewrite for groupby; ondelete guard; user→employee
  write-through.

## 6. Business architecture

- **Capabilities (inferred):** recurring weekly schedule; dated exceptions;
  today's-location resolution; presence + IM decoration; employee self-service;
  master-data delete guard.
- **Value streams (inferred):** *Set-Schedule-to-Presence* (set day field / dated
  exception → computes → colleagues see today's location) and
  *Group-by-Today's-Location* (list/search swaps in the live day field).
- **Information concepts (auto):** `hr.employee.location`; the 7 weekday default
  fields; `hr.work.location` (type home/office/other); location-decorated presence.
- **Policies (inferred):** one location per employee per day; exception overrides
  default; own-rows-only for users; can't delete an in-use location; HR-only
  visibility of `exceptional_location_id`.
- **Strategy:** `null` (human). **Organization/Products:** none own.

## 7. Classification

- **Value model: support** — workforce administration, shared HR/firm
  infrastructure (Stabell & Fjeldstad *support*; Porter support activity). It owns
  no chain/shop/network business object; it records and publishes where people work.
- **Activity class: support.**
- **APQC: 7.0 Develop and Manage Human Capital** — specifically the 7.x
  employee-information / workforce-management nuance: capturing each employee's
  remote/office/other schedule and turning it into a presence/availability signal.
  It does not recruit (7.1), train (7.3) or run payroll (7.4). `8.0 Manage IT` was
  rejected (no routes/external calls/IT plumbing); `9.x`/`13.x` rejected (manages
  people, not assets or generic capabilities).

## 8. Fit-to-Standard

- **Standard:** weekly per-employee schedule; dated exceptions; today's-location
  resolution; presence + IM decoration; self-service editing; group/filter by
  today's location; deletion guard on `hr.work.location`.
- **Typical fits:** hybrid/remote teams publishing who is in-office vs at home;
  inline colleague location in Discuss/HR kanban; employee self-managed remote days.
- **Common gaps:** single location per day (no part-day/multi-location); 7 fixed
  fields (no date-ranged recurring rule); no approval workflow on remote days;
  calendar view needs the separate `hr_homeworking_calendar` add-on; no occupancy
  analytics beyond a today's-location groupby.
- **Drive:** `e._get_current_day_location_field()`; create a `hr.employee.location`
  for today then read `e.hr_icon_display`; `hr.work.location.unlink()` to see the
  `UserError`; inspect the `get_views` search arch rewrite.
