# Odoo Messaging Subsystem (Mail / Discuss) — Deep Dive

> The `mail` module (display name **"Discuss"**, `odoo/addons/mail/`) is Odoo's
> messaging backbone. It powers three things:
> 1. **Chatter** — the message/log/activity thread on (almost) every business record.
> 2. **Email** — outgoing/incoming email, templates, mail gateway, bounce handling.
> 3. **Discuss** — real-time chat channels, DMs, reactions, calls.
>
> It is one of the most depended-on modules (**42 direct dependents**). `depends = [base,
> base_setup, bus, web_tour, html_editor]`.

---

## 1. The Two Central Models

Everything revolves around two models with very different roles:

```
┌─────────────────────────────────────────────────────────────────┐
│  mail.message   (models.Model)      — the DATA: a stored message │
│  ───────────────────────────────────────────────────────────────│
│  A single message: body, author, recipients, attachments, type,  │
│  subtype, and a polymorphic link to ANY record (model + res_id). │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  mail.thread    (models.AbstractModel)  — the BEHAVIOR: a mixin  │
│  ───────────────────────────────────────────────────────────────│
│  Inherited by any model that wants a chatter. Provides           │
│  message_post(), followers, tracking, email gateway, notify.     │
└─────────────────────────────────────────────────────────────────┘
```

A `crm.lead`, `sale.order`, `project.task`, etc. becomes "discussable" simply by
inheriting `mail.thread`:

```python
class CrmLead(models.Model):
    _name = 'crm.lead'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

That single line adds the chatter widget, follower management, field-change tracking,
and email integration.

---

## 2. `mail.message` — The Message Record (`models/mail_message.py`, ~1470 lines)

One row per message — whether a user comment, a system notification, an incoming email,
or a tracking entry.

### 2.1 Key fields

| Group | Field | Meaning |
|-------|-------|---------|
| **Content** | `subject` | Optional subject. |
| | `body` | HTML content (sanitized). |
| | `preview` | Computed text-only excerpt (email preview). |
| | `attachment_ids` | M2M to `ir.attachment`. |
| **Threading** | `parent_id` / `child_ids` | Reply threading. |
| | `model` + `res_id` | **Polymorphic link** to the related record (`res_id` is a `Many2oneReference`). |
| | `record_name` | Display name of the linked record. |
| **Classification** | `message_type` | `comment`, `email`, `email_outgoing`, `notification`, `auto_comment`, `user_notification`, `out_of_office`. |
| | `subtype_id` | → `mail.message.subtype` (semantic category; drives follower filtering). |
| | `is_internal` | Hide from portal/public users. |
| **Origin** | `author_id` | → `res.partner` (sender). |
| | `email_from` | Raw sender email if no partner matched. |
| | `author_guest_id` | → `mail.guest` (anonymous Discuss users). |
| **Recipients** | `partner_ids` | M2M direct recipients. |
| | `notification_ids` | → `mail.notification` (per-recipient delivery state). |
| **Reactions** | `reaction_ids` | Emoji reactions. |
| | `message_link_preview_ids` | URL previews. |

### 2.2 Polymorphic design

`mail.message` is **not** a child of any one model. The `(model, res_id)` pair lets a
single table hold messages for every model in the system. The chatter on a record queries
`mail.message WHERE model=%s AND res_id=%s`.

### 2.3 The message type / state map

The model docstring documents the full state machine across delivery channels
(`mail.notification`, `mail.mail`, `sms.sms`, `snailmail.letter`) — notification status
(`ready/sent/bounce/exception/canceled`) and failure types (`mail_email_invalid`,
`mail_smtp`, `sms_credit`, …). This unified model lets the chatter show delivery
success/failure icons regardless of channel.

---

## 3. `mail.thread` — The Chatter Mixin (`models/mail_thread.py`, ~5100 lines)

An `AbstractModel` meant to be inherited. Public methods are prefixed `message_` to avoid
collisions on the host model. It's the largest single model in `mail` and the heart of
the subsystem.

### 3.1 Configuration hooks (class attributes)

| Attribute | Default | Effect |
|-----------|---------|--------|
| `_mail_flat_thread` | — | If True, parentless messages attach to the first message (flat conversation). |
| `_mail_post_access` | `'write'` | Document access required to post (can be relaxed to `'read'`). |
| `_mail_thread_customer` | False | Auto-subscribe the detected customer on post. |

### 3.2 The core API — posting

| Method | Purpose |
|--------|---------|
| **`message_post(...)`** | **The main entry point.** Creates a `mail.message` on the record and triggers notification. Used by chatter, automation, code. |
| `message_post_with_source(...)` | Post rendering a QWeb view/template as the body. |
| `message_notify(...)` | Send a notification **without** logging it on the record's chatter (transient ping). |
| `_message_log(...)` / `_message_log_batch(...)` | Log an internal note (no notification, `message_type='notification'`). |
| `_message_create(values_list)` | Low-level batch message creation. |

`message_post` orchestrates: compute author → resolve parent → create the `mail.message`
→ attach files → call `_notify_thread()` → run `_message_post_after_hook()`.

### 3.3 The notification pipeline

`_notify_thread()` fans a posted message out to recipients across channels:

```
message_post()
   └─ _notify_thread(message, msg_vals)
        ├─ _notify_get_recipients()          ← gather followers + explicit recipients
        ├─ _notify_get_recipients_classify() ← split by channel & group
        │
        ├─ _notify_thread_by_inbox()         ← in-app (bus push to Discuss inbox)
        ├─ _notify_thread_by_email()         ← create mail.mail records
        └─ _notify_thread_by_web_push()      ← browser/mobile push notifications
```

Recipients are **classified** into groups (`_notify_get_recipients_groups`) — e.g.
internal users, portal customers, followers — each group getting a tailored email layout
and action buttons (`_notify_get_action_link`).

### 3.4 Field-change tracking

When a tracked field changes, `mail.thread` auto-posts a notification message:

- `_message_track(fields_iter, initial_values)` — detects changes on fields declared with
  `tracking=True`.
- Produces `mail.tracking.value` rows (old → new value) shown inline in the chatter.
- `_message_track_post_template()` — can post a full template on certain transitions
  (e.g. stage changes).

```python
stage_id = fields.Many2one('crm.stage', tracking=True)  # ← changes logged to chatter
```

### 3.5 The mail gateway (incoming email)

`mail.thread` is also a **full inbound email router**:

| Method | Purpose |
|--------|---------|
| `message_process(model, message, ...)` | Entry point for an incoming raw email (called by `fetchmail` / mail server). |
| `message_route(...)` | Decide which record(s) an email belongs to (reply? new thread? alias?). |
| `message_parse(...)` | Parse MIME → dict (subject, body, attachments, headers). |
| `message_new(msg_dict, ...)` | **Override hook**: create a new record from an email (e.g. email → new lead). |
| `message_update(msg_dict, ...)` | **Override hook**: update an existing record from a reply. |
| `_message_route_process(...)` | Apply routing + post the message. |
| `_message_receive_bounce()` / `_message_reset_bounce()` | Bounce tracking per recipient. |

Routing uses **References/In-Reply-To** headers, **mail aliases** (`mail.alias`), and a
signed reply token (`hmac`) to attach replies to the correct record.

### 3.6 Follower management

| Method | Purpose |
|--------|---------|
| `message_subscribe(partner_ids, subtype_ids)` | Add followers (optionally on specific subtypes). |
| `message_unsubscribe(partner_ids)` | Remove followers. |

---

## 4. Supporting Models

### 4.1 Followers — `mail.followers` (`models/mail_followers.py`)

Who gets notified about a record. A junction of `(res_model, res_id, partner_id,
subtype_ids)`.

| Field | Meaning |
|-------|---------|
| `res_model` + `res_id` | The followed record (polymorphic). |
| `partner_id` | The follower. |
| `subtype_ids` | Which subtypes this follower wants (granular subscription). |

A follower only receives a message if the message's `subtype_id` is in their
`subtype_ids` — this is how you can follow "stage changes" but not "every comment".

### 4.2 Subtypes — `mail.message.subtype` (`models/mail_message_subtype.py`)

The **semantic category** of a message, enabling per-topic subscription.

| Field | Meaning |
|-------|---------|
| `name` | e.g. "Discussions", "Note", "Stage Changed". |
| `res_model` | Model it applies to (False = all). |
| `internal` | Only internal users see it. |
| `default` | Auto-selected when subscribing. |
| `parent_id` + `relation_field` | Subtype propagation across related records (e.g. task subtype → project followers). |
| `hidden` | Hide from the follower options UI. |

Example: posting a comment uses `mail.mt_comment`; a record-creation note uses
`mail.mt_note`. Followers subscribe to subtypes, not to message types.

### 4.3 Notifications — `mail.notification` (`models/mail_notification.py`)

**Per-recipient, per-channel** delivery record. One `mail.message` → many
`mail.notification` (one per recipient per channel).

| Field | Meaning |
|-------|---------|
| `mail_message_id` | The message. |
| `res_partner_id` | The recipient. |
| `notification_type` | `inbox`, `email`, `sms`, `snail`. |
| `notification_status` | `ready`, `sent`, `bounce`, `exception`, `canceled`. |
| `failure_type` / `failure_reason` | Why delivery failed. |
| `is_read` / `read_date` | Inbox read state. |

This is what drives the red "failed delivery" envelope and the Discuss inbox counter.

### 4.4 Outgoing queue — `mail.mail` (`models/mail_mail.py`, ~1000 lines)

The **email send queue**. A `mail.mail` wraps a `mail.message` with SMTP-specific data
and a send state.

| Field | Meaning |
|-------|---------|
| `state` | `outgoing`, `sent`, `received`, `exception`, `cancel`. |
| `mail_message_id` | The underlying message. |
| `failure_reason` | SMTP error text. |

A cron (`ir.cron`) processes `outgoing` mails in batches, sending via `ir.mail_server`
(SMTP), and updates state + the linked `mail.notification` records.

### 4.5 Other message-related models

| Model | File | Purpose |
|-------|------|---------|
| `mail.message.reaction` | `mail_message_reaction.py` | Emoji reactions (partner or guest). |
| `mail.message.translation` | `mail_message_translation.py` | On-demand body translation. |
| `mail.message.link.preview` | `mail_message_link_preview.py` | Link → rich preview join. |
| `mail.link.preview` | `mail_link_preview.py` | Cached URL preview (OpenGraph). |
| `mail.message.schedule` | `mail_message_schedule.py` | Delayed/scheduled message sending. |
| `mail.tracking.value` | `mail_tracking_value.py` | Stored field-change old/new pairs. |
| `mail.tracking.duration.mixin` | `mail_tracking_duration_mixin.py` | Time-in-stage analytics. |

### 4.6 Email composition & rendering

| Model / Mixin | Purpose |
|---------------|---------|
| `mail.template` | Reusable QWeb/Jinja email templates with dynamic placeholders. |
| `mail.render.mixin` | Renders template expressions (`{{ object.name }}`) against records. |
| `mail.composer.mixin` | Shared logic for the "Send message" / mass-mail composer. |
| `mail.alias` / `mail.alias.domain` | Email aliases that route inbound mail to models. |
| `mail.alias.mixin` | Lets a model own an alias (e.g. a project's email address). |
| `mail.blacklist` / `mail.thread.blacklist` | Email opt-out / blacklist enforcement. |

---

## 5. Discuss — Real-Time Chat (`models/discuss/`)

Beyond record chatter, `mail` provides full chat via **`discuss.channel`**.

| Model | Purpose |
|-------|---------|
| `discuss.channel` | A conversation: `channel_type` ∈ `chat` (DM), `group`, `channel` (public/private), `livechat`. Itself inherits `mail.thread` — messages are still `mail.message` rows. |
| `discuss.channel.member` | Membership + per-member state (seen message, fold state, custom name). |
| `discuss.channel.rtc.session` | WebRTC session for voice/video calls. |
| `discuss.call.history` | Call logs. |
| `mail.guest` | Anonymous chat participants (livechat visitors). |
| `discuss.voice.metadata` | Voice message metadata. |
| `bus.listener.mixin` | Ties models to the **bus** (websocket) for live updates. |

Real-time delivery rides on the `bus` module (long-polling/websocket). When a message is
posted to a channel, `_notify_thread_by_inbox` pushes it over the bus to connected
clients.

### 5.1 The `Store` serializer

`odoo/addons/mail/tools/discuss/Store` is a structured serializer that batches related
records (messages, authors, attachments, reactions, channel members…) into a single
payload for the JS client — avoiding N+1 RPC round-trips when rendering a thread.

---

## 6. Activities — `mail.activity` (the "to-do" layer)

A sibling mixin, `mail.activity.mixin`, adds **scheduled activities** (calls, meetings,
to-dos) to records — the yellow clock icon and "Activities" view.

| Model | Purpose |
|-------|---------|
| `mail.activity` | A planned action (type, deadline, assignee, note) on a record. |
| `mail.activity.type` | Configurable activity categories (Call, Email, To-Do…). |
| `mail.activity.plan` / `mail.activity.plan.template` | Predefined sets of activities (e.g. onboarding plan). |
| `mail.activity.mixin` | Inherited alongside `mail.thread` to add the activity widget. |

---

## 7. End-to-End: Posting a Comment on a Sale Order

```
User types a message in the chatter of a sale.order and hits Send
  │
  └─ RPC → sale_order.message_post(body="...", message_type='comment',
                                   subtype_xmlid='mail.mt_comment')
       │
       ├─ _message_compute_author()         → resolve author_id from env.user
       ├─ _message_compute_parent_id()      → threading
       ├─ _message_create([values])         → INSERT mail.message
       │     (model='sale.order', res_id=42, body, subtype_id=mt_comment)
       │
       ├─ attach attachment_ids → ir.attachment
       │
       └─ _notify_thread(message)
            ├─ _notify_get_recipients()
            │     └─ read mail.followers WHERE res_model='sale.order' AND res_id=42
            │        keep those whose subtype_ids include mt_comment
            ├─ _notify_get_recipients_classify() → internal vs portal groups
            │
            ├─ _notify_thread_by_inbox()
            │     ├─ create mail.notification (type='inbox') per recipient
            │     └─ bus push → Discuss inbox updates live
            │
            └─ _notify_thread_by_email()
                  ├─ render email (mail.render.mixin / layout)
                  ├─ create mail.mail (state='outgoing') + mail.notification(type='email')
                  └─ cron sends via ir.mail_server → state='sent'
```

Each recipient ends up with:
- A `mail.notification` row tracking delivery per channel.
- An inbox entry (live via bus) and/or an email.
- Delivery success/failure reflected back on the message's status icon.

---

## 8. Mental Model & Summary

```
   mail.thread (mixin)  ──posts──▶  mail.message (data)
        │                                │
        │ has followers                  │ fans out via
        ▼                                ▼
   mail.followers              mail.notification (per recipient/channel)
   (who + which subtypes)        │            │            │
                                inbox        email        web push
                                (bus)     (mail.mail →   (web_push)
                                          ir.mail_server)
```

| Concern | Model(s) |
|---------|----------|
| **A message** | `mail.message` (polymorphic via model+res_id) |
| **Add chatter to a model** | inherit `mail.thread` (+ `mail.activity.mixin`) |
| **Who is notified** | `mail.followers` filtered by `mail.message.subtype` |
| **Delivery state** | `mail.notification` (per recipient/channel) |
| **Email sending** | `mail.mail` queue → `ir.mail_server` |
| **Incoming email** | `mail.thread.message_process` + `mail.alias` routing |
| **Field-change logs** | `tracking=True` → `mail.tracking.value` |
| **Real-time chat** | `discuss.channel` + `discuss.channel.member` over `bus` |
| **Email templates** | `mail.template` + `mail.render.mixin` |
| **Scheduled to-dos** | `mail.activity` + `mail.activity.mixin` |

**Why it's designed this way:**
- **Polymorphism** (`model` + `res_id`) lets one message table serve every model.
- **The mixin pattern** (`mail.thread`) adds full messaging to any model with one
  inheritance line — no schema changes per model.
- **Subtypes + followers** give granular, per-topic subscriptions instead of all-or-nothing.
- **Notifications decoupled from messages** lets the same message reach inbox, email, SMS,
  and push, each with independent delivery tracking.
- **Discuss reuses `mail.message`** — chat and chatter share one storage model, so search,
  attachments, and reactions work identically everywhere.

---

*Source: inspection of `odoo/addons/mail/models/` — `mail_message.py` (~1470 lines),
`mail_thread.py` (~5100 lines), `mail_followers.py`, `mail_notification.py`,
`mail_message_subtype.py`, `mail_mail.py`, and `models/discuss/` (Odoo 19.0).*
