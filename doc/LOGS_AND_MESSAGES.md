# Understanding Odoo by Its Logs & Messages

> **Two complementary audit trails** let you see what Odoo actually *does* at runtime
> without reading all the source:
>
> 1. **Logs** — the technical, developer-facing stream (`odoo/netsvc.py`, Python
>    `logging`, `ir.logging`, SQL traces, the profiler). *What the server executed.*
> 2. **Messages** — the business-facing chatter (`mail.message`, `mail.tracking.value`).
>    *What changed on a record and why.*
>
> This doc has two halves:
> - **Part A — Internals:** how each subsystem works.
> - **Part B — Reverse-engineering:** how to use them to figure out what a feature does.

---

# PART A — How Logging & Messaging Work Internally

## 1. The Logging Subsystem (`odoo/netsvc.py`, `odoo/loglevels.py`)

Odoo builds on Python's standard `logging` but adds Odoo-specific record fields, colored
output, performance metrics, and a database handler.

### 1.1 Initialization — `init_logger()`

Called once at startup (from `cli/server.py`). It:
1. Installs a custom **`LogRecord` factory** that adds `perf_info`, `pid`, and `dbname` to
   every record (`netsvc.py:169`).
2. Attaches handlers: a **stream/file handler** (colored if a TTY), and optionally a
   **`PostgreSQLHandler`** if `--log-db` is set.
3. Sets per-logger levels from `DEFAULT_LOG_CONFIGURATION` + the `--log-level` preset +
   any `--log-handler` overrides.

### 1.2 The custom `LogRecord`

```python
class LogRecord(logging.LogRecord):
    def __init__(self, ...):
        self.perf_info = ""                                      # query count/time
        self.pid = os.getpid()                                  # worker PID
        self.dbname = getattr(threading.current_thread(), 'dbname', '?')  # which DB
```

This is why every Odoo log line can show **PID + database + perf** — fields the standard
library doesn't provide. They come from **thread-locals** set per request (see how the
profiler and `sql_db` also read `threading.current_thread()`).

### 1.3 The default log format

```
%(asctime)s %(pid)s %(levelname)s %(dbname)s %(name)s: %(message)s %(perf_info)s
```

Reading a line:
```
2026-06-19 10:00:01,123 12345 INFO mydb odoo.addons.sale.models.sale_order: Confirmed SO 42  3 0.012 0.004
                        │     │    │    │                                    │                 │ │     │
                        │     │    │    │                                    │                 │ │     └ remaining (non-SQL) time
                        │     │    │    │                                    │                 │ └ SQL time (s)
                        │     │    │    │                                    │                 └ query count
                        │     │    │    │                                    └ the message
                        │     │    │    └ logger name = module path (tells you WHERE)
                        │     │    └ database name
                        │     └ log level
                        └ worker PID
```

The trailing `perf_info` (`query_count query_time remaining_time`) is injected by
**`PerfFilter`** (`netsvc.py:113`) from thread-local counters — a free per-request
profiler in every werkzeug log line. `ColoredPerfFilter` colors slow timings red/yellow.

### 1.4 Log levels & presets

Standard levels plus Odoo's **`RUNBOT` (25)** level (between INFO and WARNING, used by CI).
`loglevels.py` defines the string aliases (`LOG_DEBUG`, `LOG_WARNING='warn'`, …).

`--log-level` maps to a **preset** (`PSEUDOCONFIG_MAPPER`) that sets several loggers at
once:

| `--log-level` | Sets |
|---------------|------|
| `info` (default) | everything INFO |
| `debug` | `odoo:DEBUG`, `odoo.sql_db:INFO` |
| `debug_sql` | `odoo.sql_db:DEBUG` (**logs every SQL query**) |
| `debug_rpc` | `odoo:DEBUG` + `odoo.http.rpc.request:DEBUG` (**logs RPC calls**) |
| `debug_rpc_answer` | + `odoo.http.rpc.response:DEBUG` (**logs RPC responses**) |
| `warn` / `error` / `critical` | raise the floor |

### 1.5 Targeted logger control — `--log-handler`

The most powerful flag for reverse-engineering. Set any logger to any level:

```bash
# Log every SQL query the sale module triggers, nothing else noisy
odoo-bin --log-handler=odoo.sql_db:DEBUG --log-handler=odoo.addons.sale:DEBUG

# Quiet a chatty module
odoo-bin --log-handler=odoo.addons.mail:WARNING
```

Logger names **are module paths** (`odoo.addons.<module>.<file>`), so you can target
exactly the code you're investigating.

### 1.6 The database handler — `ir.logging` + `PostgreSQLHandler`

With `--log-db=DBNAME`, the `PostgreSQLHandler` (`netsvc.py:46`) writes every qualifying
log record into the **`ir.logging`** table — so logs are queryable via SQL/ORM, even from
a remote database.

**`ir.logging` schema** (`base/models/ir_logging.py`):

| Field | Meaning |
|-------|---------|
| `type` | `server` or `client` (browser JS logs post here too). |
| `dbname` | Source database. |
| `name` | Logger name (module path). |
| `level` | DEBUG/INFO/WARNING/… |
| `message` | The text (+ traceback if any). |
| `path` / `line` / `func` | **Exact source location** — file, line number, function. |

Notable design details (and why they matter):
- Rows are inserted via **raw SQL bypassing the ORM** (the handler can't recurse into ORM
  logging). `SET LOCAL statement_timeout = 1000` guards against deadlocks.
- `_log_access` FKs are **manually defined as plain Integers** — a real FK to `res_users`
  would deadlock during module install when the ORM holds a lock on `res_users` while the
  handler tries to insert. The long comment in the model documents this hard-won lesson.

> **Why this is gold for reverse-engineering:** `ir.logging.path/line/func` points you at
> the **exact line** of code that emitted a message. You can go from a symptom in the UI
> to the source line with one query.

### 1.7 Where logs come from in code

Every module file does:
```python
import logging
_logger = logging.getLogger(__name__)     # __name__ == 'odoo.addons.sale.models.sale_order'
...
_logger.info("Confirmed SO %s", order.name)
```

`tools.mute_logger('odoo.sql_db')` is a context manager/decorator used to silence a logger
in a block (common in tests). `_logger.runbot(...)` emits at the RUNBOT level.

### 1.8 SQL & profiling traces (cross-references)

Two adjacent mechanisms give deeper traces:
- **SQL logging:** `--log-handler=odoo.sql_db:DEBUG` logs every query with timing (see
  `sql_db.py:execute`). This is the cheapest way to see *what the ORM did to the DB*.
- **The profiler** (`PROFILING_SUBSYSTEM.md`): for a full flame graph of SQL + Python +
  QWeb on a real request, enable session profiling. Logs tell you *that* something ran;
  the profiler tells you *how long and via which call stack*.

---

## 2. The Messaging / Tracking Audit Trail (recap + the audit angle)

(Full internals in `MESSAGING_SUBSYSTEM.md`; here is the part relevant to *understanding
what happened to a record*.)

Where logs are **technical**, the chatter is the **business** audit trail stored per
record:

| Mechanism | Model | What it records |
|-----------|-------|-----------------|
| **Messages** | `mail.message` (`model`+`res_id`) | Comments, notes, system notifications posted to a record. |
| **Tracking** | `mail.tracking.value` | Every change to a `tracking=True` field: old value → new value, with the message that recorded it. |
| **Delivery** | `mail.notification` | Per-recipient/channel delivery status of each message. |
| **Followers** | `mail.followers` | Who was subscribed (and to which subtypes) at the time. |

### 2.1 Field tracking — the record-level changelog

```python
class SaleOrder(models.Model):
    _inherit = ['mail.thread']
    state    = fields.Selection([...], tracking=True)   # ← changes logged to chatter
    amount_total = fields.Monetary(tracking=True)
```

On `write()`, `mail.thread._message_track()` compares old vs new values for tracked
fields and posts a `mail.message` (type `notification`) with `mail.tracking.value` rows.
The chatter then shows: *"Status: Quotation → Sales Order"* with author and timestamp.

This is a **business-readable, per-record audit log** — no need to grep server logs to see
who moved an order to "confirmed" and when.

### 2.2 Logs vs Messages — the division of labor

```
        LOGS                              MESSAGES (chatter)
  ───────────────────             ─────────────────────────────
  Audience: developers            Audience: business users
  Scope:    the whole server      Scope:    one record
  Stored:   file / ir.logging     Stored:   mail.message / mail.tracking.value
  Answers:  "what code ran,       Answers:  "what changed on THIS record,
             what SQL, how long?"            by whom, and when?"
  Lifetime: rotated / GC'd        Lifetime: lives with the record
```

---

# PART B — Reverse-Engineering a Feature via Logs & Messages

The goal: given a behavior you observe in the UI ("clicking *Confirm* on a sale order does
X"), figure out *what code implements it* — without reading the whole module.

## 3. The Workflow

### Step 1 — Capture the RPC call (what the UI invoked)

Turn on RPC logging to see exactly which model + method the button calls:

```bash
odoo-bin --log-level=debug_rpc
# or, targeted:
odoo-bin --log-handler=odoo.http.rpc.request:DEBUG
```

Click the button; the log shows the `call_kw` — e.g.
`sale.order.action_confirm(...)`. Now you know the **entry-point method**.

### Step 2 — Trace the SQL it produced (what hit the database)

```bash
odoo-bin --log-handler=odoo.sql_db:DEBUG
```

The query stream reveals which tables were written, in what order — exposing side effects
(e.g. confirming an SO inserts `stock.picking`, updates `sale.order.state`). Each line has
timing, so slow steps stand out.

### Step 3 — Pinpoint the emitting source line

If a module logs progress, run with that module at DEBUG and read `path:line:func` (or
query `ir.logging` if `--log-db` is on):

```python
# Find the exact code locations that logged during the action
env['ir.logging'].search([
    ('name', 'like', 'odoo.addons.sale%'),
    ('level', '=', 'INFO'),
    ('create_date', '>=', t0),
]).mapped(lambda r: f"{r.path}:{r.line} {r.func} — {r.message}")
```

`path:line:func` takes you straight to the implementing function.

### Step 4 — Read the record's chatter (what changed, business-side)

Open the record's chatter (or query it) to see the *outcome* as tracked changes:

```python
order = env['sale.order'].browse(42)

# All messages posted to this record (the human-readable history)
for m in order.message_ids.sorted('date'):
    print(m.date, m.author_id.name, m.message_type, m.subtype_id.name, m.preview)

# Every tracked field change (the field-level changelog)
tracked = env['mail.tracking.value'].search([
    ('mail_message_id.model', '=', 'sale.order'),
    ('mail_message_id.res_id', '=', 42),
])
for t in tracked:
    print(t.field_id.name, ':', t.old_value_char, '→', t.new_value_char)
```

Logs told you *which code ran*; the chatter tells you *what it changed on the record* in
business terms — together they reconstruct the feature's behavior.

### Step 5 — Confirm with a profile (optional, deep)

For the full call stack and cost, enable the profiler on the request
(`PROFILING_SUBSYSTEM.md`): the Speedscope flame graph shows the exact Python call tree
from `action_confirm` down to every SQL query — the definitive "what runs" picture.

## 4. A Worked Example — "What does *Confirm* do on a Sale Order?"

```
1. --log-handler=odoo.http.rpc.request:DEBUG
   → log: call_kw sale.order action_confirm
   ⇒ entry point = SaleOrder.action_confirm()

2. --log-handler=odoo.sql_db:DEBUG
   → log shows: UPDATE sale_order SET state='sale';
                INSERT INTO stock_picking ...;
                INSERT INTO account_move ... (if invoicing)
   ⇒ side effects = state change + delivery + (maybe) invoice

3. Record chatter (order.message_ids):
   → "Quotation → Sales Order" (tracking on state)
   → "Delivery <WH/OUT/0001> created" (system note)
   ⇒ business outcome confirmed, with author + timestamp

4. ir.logging query (if --log-db):
   → path=/addons/sale/models/sale_order.py line=312 func=action_confirm
   ⇒ jump straight to the implementing code
```

In four steps — no full source read — you've mapped the button to its entry method, its
DB side effects, its business outcome, and its source line.

## 5. Quick Reference — Flags & Queries

| I want to see… | Do this |
|----------------|---------|
| Which method the UI called | `--log-level=debug_rpc` |
| Every SQL query + timing | `--log-handler=odoo.sql_db:DEBUG` |
| One module's debug logs | `--log-handler=odoo.addons.<mod>:DEBUG` |
| Logs queryable in SQL | `--log-db=<db>` then read `ir.logging` |
| Exact source line of a log | `ir.logging.path / line / func` |
| Per-request query count/time | the `perf_info` tail on each log line |
| What changed on a record | `record.message_ids` + `mail.tracking.value` |
| Who was notified & if it sent | `mail.notification` (status per recipient) |
| Full call-stack + cost | enable session profiling → Speedscope |

## 6. Summary

- **Logs** (`netsvc.py` → file / `ir.logging`) are the **server-wide, developer** trail:
  logger name = module path, `path:line:func` = exact source, `perf_info` = per-request
  cost, `--log-handler` = surgical targeting, `odoo.sql_db:DEBUG` = every query.
- **Messages** (`mail.message` + `mail.tracking.value`) are the **per-record, business**
  trail: who changed what field to what, and when — stored with the record forever.
- **Reverse-engineering method:** RPC log → SQL log → `ir.logging` source line → record
  chatter → (optional) profiler. You go from an observed UI behavior to the exact code and
  its business effect without reading the whole module.

The two systems are intentionally complementary: logs answer *"what did the server do?"*,
messages answer *"what happened to this record?"* — and used together they let you
reconstruct any feature's implementation from the outside in.

---

*Source: `odoo/netsvc.py` (logging setup, handlers, filters, formats), `odoo/loglevels.py`,
`odoo/addons/base/models/ir_logging.py`, plus `MESSAGING_SUBSYSTEM.md` and
`PROFILING_SUBSYSTEM.md` (Odoo 19.0).*
