# Odoo Profiling Subsystem — Deep Dive

> Odoo ships a built-in **performance profiler** that records SQL queries, Python stack
> traces, and QWeb template rendering during real request execution. Results are stored
> in the database (`ir.profile`) and visualized as flame graphs via **Speedscope**.
>
> Core code:
> - `odoo/tools/profiler.py` — the `Profiler` context manager + collectors (engine)
> - `odoo/addons/base/models/ir_profile.py` — `ir.profile` storage model + activation
> - `addons/web/controllers/profiling.py` — HTTP endpoints
> - `odoo/tools/speedscope.py` — converts traces to Speedscope JSON
> - `odoo/http.py` / `odoo/sql_db.py` — integration hooks

---

## 1. Big Picture

```
                         ┌──────────────────────────────────────────┐
   User enables          │           HTTP REQUEST                   │
   profiling   ─────────▶│  ir.http dispatch wraps handler in       │
   (session flag)        │  Profiler() context manager              │
                         └────────────────┬─────────────────────────┘
                                          │
              ┌───────────────────────────┼────────────────────────────┐
              │                           │                            │
       ┌──────▼──────┐          ┌─────────▼────────┐         ┌─────────▼────────┐
       │ SQLCollector│          │ PeriodicCollector│         │  QwebCollector   │
       │ query_hooks │          │ samples stack    │         │  qweb_hooks      │
       │ on cursor   │          │ every ~1ms in a  │         │  on template     │
       │             │          │ background thread│         │  directives      │
       └──────┬──────┘          └─────────┬────────┘         └─────────┬────────┘
              │                           │                            │
              └───────────────────────────┼────────────────────────────┘
                                          │  on __exit__ / end()
                                ┌─────────▼──────────┐
                                │  INSERT INTO       │
                                │  ir_profile (...)  │  ← one row per request
                                └─────────┬──────────┘
                                          │
                                ┌─────────▼──────────┐
                                │  Speedscope        │  ← /web/speedscope/<id>
                                │  flame graph (JS)  │     renders interactive view
                                └────────────────────┘
```

Three things are measured during a single execution:
1. **SQL** — every query, its text, params, start time, and duration.
2. **Python frames** — periodic samples of the call stack (statistical profiler).
3. **QWeb** — per-directive timing and query counts during template rendering.

---

## 2. The `Profiler` Context Manager (`odoo/tools/profiler.py`)

The entry point is a context manager:

```python
from odoo.tools.profiler import Profiler

with Profiler(description="my slow code", collectors=['sql', 'traces_async']) as p:
    do_expensive_work()

# results are auto-saved into ir_profile, and p.profile_id is set
```

### 2.1 Constructor parameters

| Param | Default | Meaning |
|-------|---------|---------|
| `collectors` | `['sql', 'traces_async']` | Which collectors to run (strings or instances). |
| `db` | `...` (auto) | DB to save results in. `...` = autodetect from thread; `None` = don't save. |
| `profile_session` | auto | Groups multiple profiles under one session label. |
| `description` | auto | Human label (route name, test method…). Defaults to caller frame. |
| `disable_gc` | `False` | Disable Python GC during profiling (cleaner SQL timing). |
| `params` | `{}` | Collector tuning (e.g. `traces_async_interval`, `entry_count_limit`, `time_limit`, `memory_profile`). |
| `log` | `False` | Log a text summary on exit. |

### 2.2 Lifecycle

| Phase | What happens |
|-------|--------------|
| `__enter__` | Captures `init_thread`, `init_frame`, `init_stack_trace` (the baseline). Sets `profiler_params` on the thread. Optionally disables GC. Records `start_time` / `start_cpu_time`. **Starts every collector.** |
| *(running)* | Collectors accumulate `_entries` via hooks or a sampling thread. |
| `__exit__` → `end()` | **Stops every collector.** Computes `duration` & `cpu_duration`. Resolves source-code lines for each frame. **Inserts one row into `ir_profile`.** Closes the GC/exit stack. |

The `end()` method is idempotent (`self.done` guard) — it can be triggered early by
limits (see §6) without double-saving.

### 2.3 Important detail: non-patched time

```python
real_time = time.time.__call__
real_cpu_time = time.thread_time.__call__
real_datetime_now = datetime.now
```

The profiler caches *unpatched* references to time functions so that test tools like
**freezegun** (which monkey-patch `datetime.now`/`time.time`) don't corrupt timing
measurements.

---

## 3. Collectors

All collectors subclass `Collector`, which provides a name-based registry
(`Collector.make('sql')`), an `_entries` list, and `add()` / `progress()` helpers.
Each entry is a dict containing at least a `stack` (call trace) and a `start` time.

### 3.1 SQLCollector (`name='sql'`)

Records **every SQL query** executed on the thread, with its call stack.

**Mechanism — `query_hooks`:**
- On `start()`, it appends `self.hook` to `init_thread.query_hooks`.
- `odoo/sql_db.py:Cursor.execute()` iterates `current_thread.query_hooks` for every
  query (see `sql_db.py:434`):
  ```python
  for hook in getattr(current_thread, 'query_hooks', ()):
      func = hook(self, query, params, start, 10)
      if func and callable(func):
          update_query_endtime_functions.append(func)
  ```
- The hook records `{query, full_query, start, time}` and returns an `update_sample`
  callback so the cursor can fill in the **actual** elapsed time after execution.

**Output entry:**
```python
{
  'query': 'SELECT ... FROM res_partner WHERE ...',
  'full_query': 'SELECT ... (with params substituted)',
  'start': 1718800000.123,
  'time': 0.0042,           # seconds
  'stack': [...],           # python call stack at query time
  'exec_context': (...),    # ExecutionContext annotations
}
```

### 3.2 PeriodicCollector (`name='traces_async'`) — the statistical profiler

Samples the **Python call stack** of the profiled thread at a fixed interval (default
**1ms**, clamped 1ms–5s) from a **separate background thread**.

**Mechanism:**
- Runs `run()` in its own `threading.Thread`, calling `progress()` every
  `frame_interval` seconds.
- Each sample grabs the profiled thread's current frame via
  `sys._current_frames()[thread.ident]` and walks it up to `init_frame`.
- **Deduplication:** if the stack is identical to the previous sample, it's skipped.
- **GIL-freeze detection:** if more than 10 intervals elapsed between samples (e.g. a C
  call held the GIL), it injects a `⚠ Profiler freezed for N s` marker frame so the time
  isn't silently misattributed.
- **Memory mode:** if `memory_profile` is set, each sample also records RSS
  (`process.memory_info().rss`).

This is a **sampling** (statistical) profiler — low overhead, approximate. The longer a
function runs, the more samples land in it.

### 3.3 SyncCollector (`name='traces_sync'`) — the deterministic profiler

Records the **complete** execution trace synchronously using `sys.settrace()`.

**Mechanism:**
- Installs a trace hook via `sys.settrace(self.hook)`.
- On every `call` / `return` event, records the frame and event (ignores `line` events).
- `post_process()` reconstructs full stack traces from the evented call/return stream.

**Tradeoff:** exact but **slow and memory-heavy** (the docstring warns
`--limit-memory-hard` may need raising). Not multithread-safe. Use for short, precise
captures; use `traces_async` for general profiling.

### 3.4 QwebCollector (`name='qweb'`) — template profiler

Records **QWeb template rendering**, attributing time and SQL query counts to individual
template directives (`t-if`, `t-foreach`, `t-field`, `t-call`, …).

**Mechanism — `QwebTracker` + `qweb_hooks`:**
- The QWeb engine wraps each render in a `QwebTracker`, which calls registered
  `qweb_hooks` on `render` / `enter` / `leave` directive events.
- `QwebCollector.hook` records each event with the current `sql_log_count` and time.
- `post_process()` walks the enter/leave event stream as a stack, computing per-directive
  `delay` (time) and `query` (SQL count) deltas, plus the template `archs` (source XML).

The result lets the UI show *which template directive* caused N queries or M ms.

### 3.5 ExecutionContext — stack annotations

```python
with ExecutionContext(model='res.partner', method='search'):
    ...
```

Pushes a `(stack_size, context_dict)` tuple onto `thread.exec_context`. Collectors
attach the current `exec_context` to each entry, and Speedscope renders it as an extra
synthetic stack level. This is how Odoo annotates traces with model/method/QWeb-directive
info beyond raw Python frames.

---

## 4. Storage: the `ir.profile` Model (`base/models/ir_profile.py`)

Each completed profiler run becomes **one row** in `ir_profile`.

### 4.1 Schema

| Field | Type | Content |
|-------|------|---------|
| `session` | Char (indexed) | Session label grouping related profiles. |
| `name` | Char | Description (route, method…). |
| `duration` | Float | Real elapsed time (s). |
| `cpu_duration` | Float | CPU clock time (excludes SQL/IO wait). |
| `init_stack_trace` | Text | Baseline stack where profiling started. |
| `sql` | Text (JSON) | SQLCollector entries. |
| `sql_count` | Integer | Number of queries. |
| `traces_async` | Text (JSON) | PeriodicCollector samples. |
| `traces_sync` | Text (JSON) | SyncCollector entries. |
| `qweb` | Text (JSON) | QwebCollector data. |
| `others` | Text (JSON) | Any non-standard collectors. |
| `entry_count` | Integer | Total entries collected. |
| `speedscope` | Binary (computed) | Generated Speedscope JSON. |
| `speedscope_url` | Text (computed) | `/web/speedscope/<id>`. |

Notes:
- `_log_access = False` — no `create_uid`/`write_uid` FKs (avoids coupling to `res.users`
  and reduces overhead). `create_date` is kept manually.
- `_allow_sudo_commands = False` — security hardening.
- Text trace fields use `prefetch=False` (they're large; don't load unless needed).

### 4.2 The INSERT (in `Profiler.end()`)

`Profiler.end()` builds the values dict and inserts directly via raw SQL (not the ORM —
to avoid profiling the save itself and to work even without a full environment):

```python
query = SQL("INSERT INTO ir_profile(%s) VALUES %s RETURNING id",
            SQL(",").join(map(SQL.identifier, values)),
            tuple(values.values()))
cr.execute(query)
self.profile_id = cr.fetchone()[0]
```

Collectors whose `_store == "others"` go into the `others` JSON blob; the rest map to
their own named column.

### 4.3 Garbage collection

```python
@api.autovacuum
def _gc_profile(self):
    # remove profiles older than 30 days
    domain = [('create_date', '<', now - timedelta(days=30))]
    records = self.sudo().search(domain, limit=GC_UNLINK_LIMIT)
    records.unlink()
```

Registered with `@api.autovacuum`, so the daily vacuum cron auto-purges profiles older
than 30 days (batched by `GC_UNLINK_LIMIT`).

---

## 5. Activation & Security

Profiling is **off by default** and gated by two layers.

### 5.1 Database-level gate

```python
def _enabled_until(self):
    limit = self.env['ir.config_parameter'].sudo().get_param('base.profiling_enabled_until', '')
    return limit if str(fields.Datetime.now()) < limit else None
```

A system parameter `base.profiling_enabled_until` holds an expiration datetime.
Profiling only works while *now < that limit*. A system user enabling profiling is shown
the **`base.enable.profiling.wizard`**, which offers durations (5 min / 1 hour / 1 day /
1 month) and writes the expiration parameter on submit. This prevents leaving profiling
permanently on in production.

### 5.2 Session-level activation

`ir.profile.set_profiling(profile=True, collectors=..., params=...)`:
- Verifies the DB gate (`_enabled_until`). If not enabled and the caller is a system
  user → returns the wizard action; otherwise raises a `UserError`.
- Stores in the **HTTP session**:
  - `profile_session` — the session label
  - `profile_expiration` — copied from the DB limit
  - `profile_collectors` — list of collectors
  - `profile_params` — collector params

### 5.3 HTTP endpoints (`addons/web/controllers/profiling.py`)

| Route | Auth | Purpose |
|-------|------|---------|
| `/web/set_profiling?profile=1&collectors=sql,traces_async` | public | Enable/disable profiling for the session. Returns JSON state. |
| `/web/speedscope/<ids>` | user | Render the interactive Speedscope flame graph (or memory chart). Supports `speedscope_download_json` / `_html`. |
| `/web/profile_config/<ids>` | user | Render the config page to choose visualization options. |

The `/web/set_profiling` route is auth=`public` (so it works even before login), but the
DB gate still applies — a public user can only activate it if the admin opened the window.

---

## 6. Request Integration (`odoo/http.py`)

The profiler is wired into request dispatch so that **a whole HTTP request** is profiled
when the session flag is set.

```python
# odoo/http.py
def _get_profiler_context_manager(self):
    if self.session.get('profile_session') and self.db:
        if self.session['profile_expiration'] < str(datetime.now()):
            # auto-disable if the user forgot
            self.session['profile_session'] = None
        elif 'set_profiling' in self.httprequest.path:
            pass  # don't profile the toggle route itself
        else:
            return profiler.Profiler(
                db=self.db,
                description=self.httprequest.full_path,
                profile_session=self.session['profile_session'],
                collectors=self.session['profile_collectors'],
                params=self.session['profile_params'],
            )
    return contextlib.nullcontext()
```

And the dispatch wraps the handler (`http.py:2855`):

```python
with request._get_profiler_context_manager():
    result = self.dispatcher.dispatch(...)
```

So every profiled request produces one `ir_profile` row, labeled with the request path
and grouped under the session. When the flag is off, the `nullcontext()` adds essentially
zero overhead.

### 6.1 Safety limits

`params` may include limits checked in `Collector.progress()` on each entry:

```python
exceeded_entry_count = entry_count_limit and counter >= entry_count_limit
exceeded_time_limit   = time_limit and time_limit < (now - start_time)
if exceeded_entry_count or exceeded_time_limit:
    self.profiler.end()   # auto-stop & save early
```

This prevents a runaway profiling session from exhausting memory.

### 6.2 Thread-pool / gevent guard

If the thread isn't in `sys._current_frames()` (e.g. a gevent longpolling worker),
`__enter__` catches the `KeyError`, disables all collectors, and logs a warning rather
than crashing the request.

---

## 7. Visualization: Speedscope (`odoo/tools/speedscope.py`)

`Speedscope` converts collected entries into the **Speedscope** JSON format
(`https://www.speedscope.app`), an interactive flame-graph viewer (loaded from a CDN,
configurable via the `speedscope_cdn` system parameter).

The `ir.profile` model offers several derived "views" via `_parse_params` /
`_add_outputs`:

| View | Built from | Shows |
|------|-----------|-------|
| **Combined** | sql + frames | Python frames and SQL queries merged on one timeline. |
| **Frames** | traces_async | Pure Python call-stack flame graph. |
| **Sql (no gap)** | sql | Queries packed together (ignores idle gaps). |
| **Sql (density)** | sql | Query density over time. |
| **Memory** | traces_async (RSS) | RSS memory over time (baselined), via a custom chart template. |

Aggregation mode is either `tabs` (one tab per profile) or `temporal` (all profiles on
one timeline). Multiple `ir.profile` rows can be opened together **only if they share the
same `init_stack_trace`** (enforced in `_generate_speedscope`).

`profile.json()` also lets you dump a profile to a standalone JSON file (useful with
`Profiler(db=None)` outside a request).

---

## 8. Putting It Together — End-to-End Flow

```
1. Admin enables profiling
   └─ base.enable.profiling.wizard → set ir.config_parameter
        base.profiling_enabled_until = now + 1h

2. User clicks "Enable profiling" in UI
   └─ POST /web/set_profiling?profile=1&collectors=sql,traces_async
        └─ ir.profile.set_profiling()
             └─ session['profile_session'] = "2026-06-19 10:00 Mitchell Admin"
                session['profile_collectors'] = ['sql', 'traces_async']

3. User performs an action → HTTP request
   └─ ir.http dispatch:
        with request._get_profiler_context_manager():   # Profiler(...)
            ├─ Profiler.__enter__():
            │    ├─ SQLCollector.start()      → thread.query_hooks += hook
            │    └─ PeriodicCollector.start() → background sampling thread @1ms
            │
            ├─ handler runs business logic:
            │    ├─ each cr.execute() → query_hook records SQL + stack + time
            │    └─ sampling thread snapshots Python stack every 1ms
            │
            └─ Profiler.__exit__() → end():
                 ├─ stop collectors
                 ├─ resolve source lines for stacks
                 └─ INSERT INTO ir_profile(name, session, sql, traces_async, ...)

4. User opens the result
   └─ GET /web/speedscope/<id>
        └─ ir.profile._generate_speedscope()
             └─ Speedscope.make() → JSON → interactive flame graph in browser
```

---

## 9. Summary

| Aspect | Design |
|--------|--------|
| **Activation** | Two-gate: DB parameter (`profiling_enabled_until`) + per-session flag. Off by default; time-boxed. |
| **What's measured** | SQL queries (hook-based), Python stack (1ms sampling thread), QWeb directives (template hooks), optional RSS memory. |
| **How it hooks in** | Thread-local hook lists (`query_hooks`, `profile_hooks`, `qweb_hooks`) + a wrapping context manager in request dispatch. |
| **Overhead when off** | `nullcontext()` — negligible. |
| **Storage** | One `ir_profile` row per run; large traces as JSON text; auto-GC after 30 days. |
| **Visualization** | Speedscope flame graphs (combined/frames/SQL/memory) served from `/web/speedscope`. |
| **Safety** | Entry/time limits, GIL-freeze detection, gevent thread guard, unpatched time refs (freezegun-safe), raw-SQL save (doesn't profile itself). |

The design lets developers profile **real production requests** with low overhead, a
statistical-by-default sampler (with an optional deterministic mode), and rich SQL+Python
correlation — all visualized as interactive flame graphs.

---

*Source: inspection of `odoo/tools/profiler.py`, `odoo/tools/speedscope.py`,
`odoo/addons/base/models/ir_profile.py`, `addons/web/controllers/profiling.py`, and the
profiler hooks in `odoo/http.py` and `odoo/sql_db.py` (Odoo 19.0).*
