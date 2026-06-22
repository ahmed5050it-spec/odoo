---
name: run-odoo
description: Build, launch, and drive the Odoo 19 ERP server in this container. Use when asked to run, start, boot, serve, smoke-test, or interact with Odoo, or to query/poke its ORM or web/JSON-RPC API. Covers Postgres setup, Python deps, DB init, background launch, and the smoke.sh driver.
---

# Run Odoo (19.0)

Odoo is a Python web/ERP **server** backed by PostgreSQL. There is no native
screenshot path in this container (see Gotchas — Chromium is unavailable), so
the agent drives it through three verified surfaces:

1. **HTTP + JSON-RPC** via `curl` (web API / login).
2. **`odoo shell`** — programmatic ORM access (the layer most PRs touch). **Most
   reliable** here; works every call.
3. The **driver `smoke.sh`** that wraps all of the above.

Paths below are relative to the repo root (`/home/user/odoo`). The driver lives
at `.claude/skills/run-odoo/smoke.sh`.

> Heads-up: the foreground command watchdog kills long-lived listeners with
> **exit 144**. Always launch the server with your runner's **background mode**
> (plain `nohup … & disown`), then run `smoke.sh smoke` from a *separate* call.

## Prerequisites (exact, ran this session)

System has Python 3.11 and PostgreSQL 16 preinstalled. Start PG and create the
role Odoo connects as:

```bash
pg_ctlcluster 16 main start            # or: service postgresql start
sudo -u postgres psql -c "CREATE ROLE odoo WITH LOGIN SUPERUSER PASSWORD 'odoo';"
```

Install the Python deps (these exact lines worked; the split-out / `--no-deps`
ones work around broken system setuptools and an immovable Debian
`cryptography`):

```bash
pip install --no-cache-dir psycopg2-binary lxml passlib werkzeug babel decorator \
  pytz reportlab psutil docutils rjsmin polib qrcode vobject xlsxwriter \
  python-stdnum freezegun geoip2
pip install --no-cache-dir chardet openpyxl xlrd asn1crypto cbor2 zeep
pip install --no-cache-dir docopt-ng            # drop-in for docopt (wheel build fails)
pip install --no-cache-dir --no-deps num2words   # its docopt dep is satisfied above
pip install --no-cache-dir lxml_html_clean       # lxml 6 split this out
pip install --no-cache-dir --no-deps pyopenssl   # --no-deps: don't touch Debian cryptography
```

Verify: `python3 -c "import odoo.release; print(odoo.release.version)"` → `19.0`.

## Build / init the database (one-time)

```bash
mkdir -p /tmp/odoo-data
./odoo-bin -d odoo_run --db_host localhost -r odoo -w odoo --data-dir /tmp/odoo-data \
  -i base,web --stop-after-init --without-demo=all
```

Last lines show `Modules loaded.` / `Registry loaded`. Default login is
`admin` / `admin`. Or use the driver: `.claude/skills/run-odoo/smoke.sh init`.

## Run — agent path (PRIMARY)

**1. Launch in the background** (use your runner's background mode):

```bash
nohup ./odoo-bin -d odoo_run --db_host localhost -r odoo -w odoo \
  --data-dir /tmp/odoo-data --http-port 8069 --http-interface 127.0.0.1 \
  </dev/null >/tmp/odoo-server.log 2>&1 & disown; echo "launched $!"
```

Wait ~10s for `HTTP service (werkzeug) running on localhost:8069` in
`/tmp/odoo-server.log`.

**2. Drive it** (from a separate call) with the smoke driver:

```bash
.claude/skills/run-odoo/smoke.sh smoke
```

Verified output:

```
>> [HTTP] GET /web/login
   HTTP 200
>> [JSON-RPC] version_info
   OK
>> [JSON-RPC] authenticate (admin/admin)
   uid=2
>> SMOKE PASS
```

Raw equivalents (also verified):

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8069/web/login   # -> HTTP 200
curl -s http://127.0.0.1:8069/jsonrpc -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{"service":"common","method":"login","args":["odoo_run","admin","admin"]}}'
# -> {"jsonrpc":"2.0","id":null,"result":2}
```

Authenticated ORM read over JSON-RPC (`execute_kw`):

```bash
curl -s http://127.0.0.1:8069/jsonrpc -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{"service":"object","method":"execute_kw","args":["odoo_run",2,"admin","res.users","search_read",[[],["login"]],{"limit":3}]}}'
# -> {"jsonrpc":"2.0","id":null,"result":[{"id":2,"login":"admin"}]}
```

## Direct invocation — `odoo shell` (most reliable; no server needed)

Best for poking the ORM / testing internal functions. Pipe Python to stdin:

```bash
printf '%s\n' \
  "print('MODULES', env['ir.module.module'].search_count([('state','=','installed')]))" \
  "print('MODELS', env['ir.model'].search_count([]))" \
  "print('ADMIN', env['res.users'].browse(2).name)" \
| ./odoo-bin shell -d odoo_run --db_host localhost -r odoo -w odoo \
    --data-dir /tmp/odoo-data --no-http
```

Verified output: `MODULES 5`, `MODELS 129`, `ADMIN Administrator`.
Or: `.claude/skills/run-odoo/smoke.sh shell`.

## Stop

```bash
.claude/skills/run-odoo/smoke.sh stop      # or: pkill -f "odoo-bin.*http-port"
```

## Run — human path

`./odoo-bin -d odoo_run …` in a foreground terminal serves on
http://localhost:8069 until Ctrl-C. Useless headless (no browser here) and the
container watchdog kills foreground listeners — use the background path above.

## Gotchas (battle scars from this container)

- **exit 144 on launch.** The foreground watchdog reaps long-lived listeners.
  Launch the server via background mode (`nohup … & disown`); never foreground.
  `setsid` did **not** help — plain `nohup`+`disown` is what stays up.
- **No Chromium / no screenshot.** apt only ships a *snap stub*
  (`chromium-browser` → "requires the chromium snap"), there's no snap daemon,
  the Playwright CDN (`cdn.playwright.dev`) is egress-blocked (403), and pulling
  a Chromium binary from googleapis is policy-denied. So GUI screenshots are not
  possible; drive via JSON-RPC + `odoo shell` instead.
- **`docopt` wheel build fails** (old system setuptools, `install_layout`
  AttributeError). Install **`docopt-ng`** + `num2words --no-deps`.
- **`lxml.html.clean` ImportError** — lxml 6 split it out; `pip install lxml_html_clean`.
- **`ModuleNotFoundError: OpenSSL`** — needs `pyopenssl`, but a plain install
  tries to uninstall the Debian `cryptography` and fails. Use `--no-deps`.
- **`pip --upgrade wheel` fails** ("RECORD file not found", Debian-managed) —
  harmless; ignore it.
- **Runs as root with a warning** ("Running as user 'root' is a security
  risk") — it still runs; no fix needed in-container.
- **`ofxparse` wheel fails to build** — only used by an OFX bank-import addon we
  don't install; skip it.
- **egress is allowlist-gated** — `storage.googleapis.com`/`github.com` reachable,
  most others 403 with "Host not in allowlist".

## Troubleshooting

| Symptom | Fix |
|---|---|
| `smoke smoke` shows `HTTP 000` | Server isn't up. Re-launch via background mode; wait for `werkzeug running` in `/tmp/odoo-server.log`. |
| Launch returns exit 144 | Expected for foreground; use the runner's background mode. |
| `psycopg2.OperationalError: role "odoo"` | Run the `CREATE ROLE odoo …` line in Prerequisites. |
| `could not connect to server` | `pg_ctlcluster 16 main start`. |
| `ModuleNotFoundError: <x>` at boot | `pip install <x>`; for `num2words`/`pyopenssl` use the `--no-deps` forms above. |
