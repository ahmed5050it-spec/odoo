#!/usr/bin/env bash
# revres runtime extractor — closes metadata gap #5 (actual data/state) and a
# slice of #6 (query cost) using a LIVE Odoo DB via the run-odoo skill.
#
# For each model of a module it pulls real row counts + a tiny sample from the
# running database (state the static schema can't show), and the per-call query
# count from the cursor. Uses `odoo shell` (self-contained; no HTTP server).
#
# Prereq: DB initialised (see .claude/skills/run-odoo). Defaults match that skill.
# Usage (repo root):
#   doc/revres/extract_runtime.sh sale            # one module -> JSON on stdout
#   doc/revres/extract_runtime.sh base > base.runtime.json
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo /home/user/odoo)"

MOD="${1:?usage: extract_runtime.sh <module>}"
DB="${DB:-odoo_run}"; DBHOST="${DBHOST:-localhost}"
DBUSER="${DBUSER:-odoo}"; DBPW="${DBPW:-odoo}"; DATADIR="${DATADIR:-/tmp/odoo-data}"

pg_lsclusters 2>/dev/null | grep -q online || pg_ctlcluster 16 main start 2>/dev/null

python_in=$(cat <<PY
import json
mod = "${MOD}"
# models that belong to this module (declared in its python files)
target = env['ir.model.data'].search([('module','=',mod),('model','=','ir.model')])
model_names = sorted(set(env['ir.model'].browse([d.res_id for d in target]).mapped('model')))
out = {"module": mod, "models_runtime": []}
for mn in model_names:
    M = env.get(mn)
    if M is None or M._abstract or M._transient:
        continue
    try:
        q0 = env.cr.sql_log_count if hasattr(env.cr,'sql_log_count') else 0
        n = M.search_count([])
        sample = M.search([], limit=2)
        names = sample.mapped('display_name') if 'display_name' in M._fields else sample.ids
        q1 = env.cr.sql_log_count if hasattr(env.cr,'sql_log_count') else 0
        out["models_runtime"].append({"model": mn, "rows": n,
                                       "sample": names[:2], "queries_for_count": max(0,q1-q0)})
    except Exception as e:
        out["models_runtime"].append({"model": mn, "error": str(e)[:80]})
print("REVRES_RUNTIME_JSON " + json.dumps(out, ensure_ascii=False))
PY
)

echo "$python_in" | ./odoo-bin shell -d "$DB" --db_host "$DBHOST" -r "$DBUSER" -w "$DBPW" \
    --data-dir "$DATADIR" --no-http 2>/dev/null \
  | sed -n 's/^REVRES_RUNTIME_JSON //p'
