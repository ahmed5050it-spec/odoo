# calendar (Calendar) — Architecture Brief

> Module `calendar`, display name **"Calendar"** (`odoo/addons/calendar/`). Odoo's
> meeting/event scheduling subsystem: events, attendees, RSVP invitations, recurring
> series, and reminders. `depends = [base, mail]`. 9 own models + extensions of
> res.partner/res.users/mail.activity/discuss.channel, 10 routes, ~7.9k Python LOC.
> `application = true`, `auto_install = false`. Cross-cutting scheduling used by crm,
> hr, project, and appointment, and the calendar target for `mail.activity` due dates.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). calendar is cross-cutting scheduling
  infrastructure, not a primary value chain — it produces no sellable output and depends
  only on `base` + `mail`. It is *consumed* by other subsystems (crm meetings, hr
  appointments, project deadlines; `mail.activity.calendar_event_id` links activities to
  meetings), the definition of a shared support function.
- **activity_class: support.**
- **apqc_category: 13.0 Develop and Manage Business Capabilities** — the
  management/enabling band for collaboration/time-coordination infrastructure. No
  operating category (1.0-9.0) fits; **9.0 Acquire/Manage Assets** was rejected because
  calendar coordinates people's *time*, not physical/IT assets.
- **Why:** events flow into `mail` (invitations, chatter, reminders) and the bus
  (in-app alerts), but nothing flows into a stock/account document chain — it enables
  other processes rather than transforming a customer order.

## 2. IT Architecture

- **Application:** calendar — meeting/event scheduling component on top of mail.
- **Software services (routes):** 10 routes. RSVP via custom `auth=calendar` token
  (`/calendar/meeting/accept|decline|view`, `/calendar/recurrence/accept|decline`);
  `auth=user` JSON-RPC (`/calendar/notify`, `/calendar/notify_ack`,
  `/calendar/check_credentials`); public videocall join
  (`/calendar/join_videocall/<access_token>`).
- **Core data objects:** `calendar.event` (central, 65 fields, `mail.thread`),
  `calendar.attendee` (invitee + RSVP state), `calendar.recurrence` (RRULE),
  `calendar.alarm` (reminder), `calendar.alarm_manager` (AbstractModel, cron/bus logic).
- **Key ERM:** `calendar.event → res.users (organizer)` / `→ res.partner (partner_ids)`;
  `calendar.attendee → calendar.event` + `→ res.partner`; `calendar.recurrence →
  calendar.event (base_event_id + calendar_event_ids)` + `→ ir.cron.trigger`;
  `calendar.event → calendar.alarm (alarm_ids m2m)`; `→ discuss.channel (videocall)`.

## 3. Behavioral Notes (code-read, the metadata gap)

1. **Recurrence expansion** (`calendar.recurrence._apply_recurrence`): serializes the UI
   fields into an iCalendar RRULE (`_get_rrule`, dateutil), then **materializes concrete
   `calendar.event` rows** per occurrence by copying the base event; reconciles existing
   events, creates only missing ranges, detaches off-pattern ones. Capped at
   `MAX_RECURRENT_EVENT=720`, with DST-aware timezone localization. Invisible to metadata.
2. **Attendee RSVP + invitation emails** (`calendar.attendee.do_accept/do_decline/
   do_tentative` + `_notify_attendees`): RSVP sets `state` AND posts a chatter message on
   the event (subtype `calendar.subtype_invitation`). Invite/reschedule renders a
   `mail.template`, **attaches an ICS file** (`_get_ics_file`, `text/calendar`), and mails
   each attendee via `message_notify`. Gated by `calendar.block_mail` / `no_mail_to_attendees`.
3. **Alarm/reminder cron + bus** (`calendar.event._setup_alarms` + `calendar.alarm_manager`):
   email alarms schedule `ir.cron.trigger` against cron `calendar.ir_cron_scheduler_alarm`
   at `start - duration_minutes`; the cron runs `_send_reminder` to email due attendees.
   Notification alarms push the next 24h via the bus — `user._bus_send('calendar.alarm', notif)`.
4. **Frontend `calendarNotificationService`** (`static/.../calendar_notification_service.js`,
   source: static): subscribes to the `calendar.alarm` bus channel (same channel the backend
   pushes to), shows a sticky reminder, OK acks via `rpc('/calendar/notify_ack')`, Details
   opens the event form. Not in Python metadata.

## 4. Business Architecture

- **Capabilities (inferred):** Schedule Meetings & Events; Manage Attendees & RSVP
  Invitations; Configure Recurring Events; Send Reminders & Notifications (email + in-app).
- **Value streams (inferred):** Schedule-to-Attend — create meeting → invite attendees
  (email + ICS) → RSVP → reminder → join videocall.
- **Information concepts (auto):** calendar.event, calendar.attendee, calendar.recurrence,
  calendar.alarm, res.partner.
- **Organization (auto):** calendar defines **no own groups** (facts: `groups: 0`); 4 record
  rules reuse base user/portal groups for privacy + own-meeting scoping.
- **Policies (inferred):** privacy scoping (public/private/confidential) via record rules;
  `calendar.block_mail` and `calendar.max_recurrence_years` config params gate mailing and
  recurrence horizon; cron `calendar.ir_cron_scheduler_alarm` drives reminders.
- **Metrics (inferred):** RSVP rollups on calendar.event — attendees_count, accepted_count,
  declined_count, tentative_count, awaiting_count.
- **Strategy:** human (none derivable).

## 5. Fit-to-Standard

- **Out-of-box:** event creation with attendees/locations; RSVP invitations with ICS +
  chatter; recurring events (daily/weekly/monthly/yearly, end by count/date/forever);
  email + in-app bus reminders; videocall link + public join page; attendee calendar view
  (day/week/month/year) with free/busy filters.
- **Typical fits:** internal team meeting scheduling; activity due-dates on a calendar;
  privacy-scoped event visibility.
- **Common gaps:** external sync (Google/Microsoft) lives in `calendar_google` /
  `microsoft_calendar` (base only ships the provider config wizard); self-service booking
  (the `appointment` module); room/resource double-booking beyond free/busy; bespoke
  reminder escalation.

## 6. Drive Hints (run-odoo)

```
odoo shell: env['calendar.event'].search([], limit=5).mapped(('name','start','recurrency'))
odoo shell: e=env['calendar.event'].create({'name':'Test','start':'2026-07-01 09:00:00',
            'stop':'2026-07-01 10:00:00','recurrency':True,'rrule_type':'weekly','mon':True,
            'count':3,'end_type':'count'}); e.recurrence_id.calendar_event_ids.mapped('start')
odoo shell: env['calendar.alarm_manager']._notify_next_alarm(env.user.partner_id.ids)  # bus push
curl http /calendar/meeting/accept (auth=calendar token, RSVP accept)
```

## 7. Open Questions

- Precedence between `privacy` and `effective_privacy` when organizer default vs
  event-level privacy differ.
- How `recurrence_update` (self_only/future_events/all_events) routes `calendar.event.write`
  to recurrence split vs bulk update.
- Whether `videocall_source='discuss'` always creates a `discuss.channel` or only on demand.

## 8. Provenance

- Facts: `doc/revres/facts/calendar.facts.json`; frontend: `doc/revres/frontend/calendar.frontend.json`.
- Tools: `extract_module.py`, `extract_frontend.py`; code-read of `calendar_event.py`,
  `calendar_attendee.py`, `calendar_recurrence.py`, `calendar_alarm.py`,
  `calendar_alarm_manager.py`, `calendar_notification_service.js`.
- Odoo 19.0. Record: `doc/revres/metamodel/calendar.metamodel.json` (schema-valid).
