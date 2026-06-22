# mail (Discuss) — Architecture Brief

> Module `mail`, display name **"Discuss"** (`odoo/addons/mail/`). Odoo's messaging
> and collaboration backbone: chatter, email, activities, and real-time chat.
> `depends = [base, base_setup, bus, web_tour, html_editor]`. 58 models, 64 routes,
> ~41.7k Python LOC. One of the most-depended-on modules (~42 dependents).

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). mail is cross-cutting infrastructure,
  not a primary value chain. It also carries **network** logic (the bus + channels +
  notifications broker person-to-person and system-to-person exchange).
- **activity_class: support.**
- **apqc_category:** best fit *13.0 Information & Knowledge Management* / *9.4 internal
  controls*; concrete anchor in `apqc_odoo_map.tsv` is **3.5.4.8 Handle sales order
  inquiries (post-order)** = `mail.message` `message_post` on a `sale.order` (support).
- **Why:** the `mail.thread` mixin is inherited by ~42 modules to add chatter, activity,
  and field tracking — shared collaboration infrastructure, the definition of a support
  subsystem.

## 2. IT Architecture

- **Application:** mail — messaging/collaboration component and foundational mixin layer.
- **Software services (routes):** `/mail/message/post`, `/mail/thread/*`, `/mail/inbox/messages`,
  `/mail/message/reaction`, `/discuss/channel/*`, `/mail/rtc/channel/*`,
  `/websocket/update_bus_presence`, `/mail/attachment/upload`. 64 routes, mostly `jsonrpc`,
  many `auth=public` (Discuss + livechat guests).
- **Core data objects:** `mail.thread` (mixin), `mail.message` (data), `mail.followers`,
  `mail.notification`, `mail.mail`, `mail.message.subtype`, `mail.tracking.value`,
  `mail.activity`(+mixin), `mail.template`, `mail.alias`, `discuss.channel`(+member),
  `mail.guest`.
- **Key ERM:** `mail.message → res.partner (author)`, `→ mail.message.subtype`,
  `→ (model,res_id)` polymorphic host; `mail.followers → partner + subtype`;
  `mail.message → mail.notification (1:N per recipient/channel)`; `→ mail.mail → ir.mail_server`;
  `discuss.channel → discuss.channel.member → res.partner / mail.guest`.

## 3. Behavioral Notes (code-read, the metadata gap)

1. **`message_post`** (`mail_thread.py:2182`) resolves author → creates a `mail.message`
   (polymorphic `model`+`res_id`) → attaches files → calls `_notify_thread()`. One
   `_inherit` line gives any model full chatter, no per-model schema change.
2. **`_notify_thread`** (`:3262`) fans out to recipients (followers filtered by subtype +
   explicit partners) across three channels: `_notify_thread_by_inbox` (mail.notification
   type=inbox + bus push), `_notify_thread_by_email` (mail.mail queue → cron → ir.mail_server),
   `_notify_thread_by_web_push`. Scheduled sends deferred via `mail.message.schedule`.
3. **Tracking** (`_message_track`, `:644`): writing a `tracking=True` field creates
   `mail.tracking.value` (typed old/new) on an auto-posted message — the "Stage changed"
   audit log. Lives in Python, invisible to metadata.
4. **Inbound gateway** (`message_process`/`message_route`, `:1424`/`:1121`) routes raw
   email to a record via References/In-Reply-To headers, `mail.alias`, and a signed hmac
   reply token; `message_new`/`message_update` hooks turn email into a record or a reply.
5. **`mail.notification`** is per-recipient/per-channel — one message → many rows tracking
   `notification_status` (sent/bounce/exception/canceled). Drives the failed-delivery
   envelope and inbox counters; decouples a message from multi-channel delivery state.
6. **`discuss.channel`** itself inherits `mail.thread`, so chat messages are still
   `mail.message` rows; real-time delivery rides the **bus** (websocket) via
   `bus.listener.mixin`; RTC calls use `discuss.channel.rtc.session`.

## 4. Business Architecture

- **Capabilities (inferred):** Record Collaboration (chatter), Field-Change Tracking/Audit,
  Email Communication (templates, queue, inbound gateway), Multi-channel Notification,
  Real-time Team Messaging (Discuss + calls), Activity/To-Do Scheduling, Deliverability
  controls (blacklist/bounce).
- **Value streams (inferred):** Collaborate-on-a-Record; Inbound-Email-to-Record;
  Notify-and-Track-Change.
- **Information concepts (auto):** mail.message, mail.followers, mail.notification,
  mail.activity, mail.template, mail.alias, discuss.channel, mail.guest.
- **Organization (auto):** mail defines **no own groups** (facts: `groups: 0`); 26 record
  rules reuse `base.group_user / group_portal / group_public / group_system`.
- **Policies (inferred):** channel visibility scoped by `group_public_id`/membership;
  follower-subtype filtering for per-topic subscription; `_mail_post_access` gate;
  blacklist/bounce opt-out.
- **Metrics (inferred):** notification delivery status; `mail.tracking.duration.mixin`
  (time-in-stage); inbox/needaction counters; `discuss.call.history`.
- **Strategy:** human (none derivable).

## 5. Fit-to-Standard

- **Out-of-box:** chatter on any model; field tracking; email templates + outgoing queue;
  inbound alias routing; multi-channel notification w/ delivery tracking; activities + plans;
  Discuss channels/DMs/reactions/calls; blacklist/bounce.
- **Typical fits:** inherit `['mail.thread','mail.activity.mixin']` for chatter+activities;
  template-driven notification emails; alias → record creation (support@ → ticket); audit
  via `tracking=True`.
- **Common gaps:** custom notification routing/digests; channel access beyond
  `group_public_id` rules; SFU/Twilio RTC scaling; advanced deliverability (DKIM/SPF/ESP);
  Tenor/Translate/web-push need external API keys.

## 6. Drive Hints (run-odoo)

```
odoo shell: r=env['res.partner'].browse(1); r.message_post(body='hi'); \
            r.message_ids[:1].mapped(('subtype_id.name','message_type'))
odoo shell: env['mail.message'].search_count([('model','=','sale.order')])
odoo shell: env['mail.notification'].read_group([],['id'],['notification_status'])
curl jsonrpc /mail/message/post (auth=public); /discuss/channel/messages
```

## 7. Open Questions

- Recipient classification (`_notify_get_recipients_groups`) splitting internal/portal/
  follower email layouts.
- Clean single APQC leaf for a cross-cutting infra module (13.x vs 9.x) — none is exact.
- Full `discuss.channel` access matrix (group_public_id vs membership vs invitation token)
  across the 26 record rules.
- `tools/discuss/Store` serializer batching contract (performance, not in metadata).

## 8. Provenance

- Facts: `doc/revres/facts/mail.facts.json`.
- Tools: `extract_module.py`; code-read of `mail_thread.py`, `mail_message.py`,
  `mail_security.xml`; `doc/MESSAGING_SUBSYSTEM.md`.
- Odoo 19.0. Record: `doc/revres/metamodel/mail.metamodel.json` (schema-valid).
