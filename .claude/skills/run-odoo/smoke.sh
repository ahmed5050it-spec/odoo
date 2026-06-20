#!/usr/bin/env bash
# Odoo run/smoke driver — launches Odoo (if needed) and drives the running
# server through HTTP + JSON-RPC, then runs a programmatic ORM check via
# `odoo shell`. This is the agent-facing harness for the run-odoo skill.
#
# Usage (from the repo root /home/user/odoo):
#   .claude/skills/run-odoo/smoke.sh init     # create/upgrade the DB (base,web)
#   .claude/skills/run-odoo/smoke.sh start    # launch server in background
#   .claude/skills/run-odoo/smoke.sh smoke    # HTTP + JSON-RPC checks (server must be up)
#   .claude/skills/run-odoo/smoke.sh shell    # programmatic ORM check via odoo shell
#   .claude/skills/run-odoo/smoke.sh stop     # stop the background server
#   .claude/skills/run-odoo/smoke.sh all      # init + start + smoke + shell
#
# Env overrides: DB, PORT, DBHOST, DBUSER, DBPW, DATADIR, ADDONS
set -uo pipefail

DB="${DB:-odoo_run}"
PORT="${PORT:-8069}"
DBHOST="${DBHOST:-localhost}"
DBUSER="${DBUSER:-odoo}"
DBPW="${DBPW:-odoo}"
DATADIR="${DATADIR:-/tmp/odoo-data}"
LOG="${LOG:-/tmp/odoo-server.log}"
PIDFILE="${PIDFILE:-/tmp/odoo-run.pid}"
BASE="http://127.0.0.1:${PORT}"

cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || echo /home/user/odoo)"

common=(--db_host "$DBHOST" -r "$DBUSER" -w "$DBPW" --data-dir "$DATADIR")

pg_up() { pg_lsclusters 2>/dev/null | grep -q online || (pg_ctlcluster 16 main start 2>/dev/null || service postgresql start 2>/dev/null); }

init() {
  pg_up
  echo ">> init DB '$DB' with base,web (no demo)"
  ./odoo-bin -d "$DB" "${common[@]}" -i base,web --stop-after-init --without-demo=all 2>&1 | tail -3
}

start() {
  pg_up
  echo ">> launching Odoo on $BASE"
  # NOTE: invoke this via your runner's BACKGROUND mode (the foreground watchdog
  # reaps long-lived listeners with exit 144). Plain nohup + disown is the
  # pattern proven to keep the server up in this container.
  nohup ./odoo-bin -d "$DB" "${common[@]}" --http-port "$PORT" --http-interface 127.0.0.1 \
        < /dev/null > "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  disown 2>/dev/null || true
  for i in $(seq 1 30); do
    sleep 1
    curl -s -o /dev/null -m 3 "$BASE/web/login" && { echo ">> up (pid $(cat "$PIDFILE"))"; return 0; }
  done
  echo "!! server did not come up; tail $LOG"; tail -15 "$LOG"; return 1
}

stop() {
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null && echo ">> stopped $(cat "$PIDFILE")" && rm -f "$PIDFILE" || echo ">> no pidfile"
}

smoke() {
  local rc=0
  echo ">> [HTTP] GET /web/login"
  code=$(curl -s -o /dev/null -m 10 -w "%{http_code}" "$BASE/web/login")
  echo "   HTTP $code"; [ "$code" = 200 ] || rc=1

  echo ">> [JSON-RPC] version_info"
  curl -s -m 10 "$BASE/web/webclient/version_info" -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","method":"call","params":{}}' | grep -q '"server_version"' \
    && echo "   OK" || { echo "   FAIL"; rc=1; }

  echo ">> [JSON-RPC] authenticate (admin/admin)"
  uid=$(curl -s -m 10 "$BASE/jsonrpc" -X POST -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{\"service\":\"common\",\"method\":\"login\",\"args\":[\"$DB\",\"admin\",\"admin\"]}}" \
    | grep -oE '"result": *[0-9]+' | grep -oE '[0-9]+')
  echo "   uid=$uid"; [ -n "$uid" ] && [ "$uid" -ge 1 ] 2>/dev/null || rc=1

  [ $rc -eq 0 ] && echo ">> SMOKE PASS" || echo ">> SMOKE FAIL"
  return $rc
}

shell_check() {
  pg_up
  echo ">> [shell] programmatic ORM check"
  printf '%s\n' \
    "print('MODULES', env['ir.module.module'].search_count([('state','=','installed')]))" \
    "print('MODELS', env['ir.model'].search_count([]))" \
    "print('ADMIN', env['res.users'].browse(2).name)" \
  | ./odoo-bin shell -d "$DB" "${common[@]}" --no-http 2>/dev/null \
  | grep -E "MODULES|MODELS|ADMIN"
}

case "${1:-all}" in
  init) init ;;
  start) start ;;
  smoke) smoke ;;
  shell) shell_check ;;
  stop) stop ;;
  all) init && start && smoke && shell_check; stop ;;
  *) echo "usage: $0 {init|start|smoke|shell|stop|all}"; exit 2 ;;
esac
