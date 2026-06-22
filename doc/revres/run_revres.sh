#!/usr/bin/env bash
# revres workflow runner — generate reverse-engineering facts for Odoo modules.
#
# For each module it runs extract_module.py to produce a JSON "facts" file under
# OUT/. Those facts are the deterministic input a model turns into a narrative
# doc via PROMPT.md. Also writes an index.tsv (one row per module) for triage.
#
# Usage (from repo root /home/user/odoo):
#   doc/revres/run_revres.sh                      # all modules in addons/ + odoo/addons/
#   doc/revres/run_revres.sh mail account sale    # specific modules
#   OUT=/tmp/revres doc/revres/run_revres.sh base # custom output dir
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo /home/user/odoo)"

OUT="${OUT:-doc/revres/facts}"
EXTRACT="doc/revres/extract_module.py"
mkdir -p "$OUT"
INDEX="$OUT/index.tsv"
printf "module\tcategory\tdepends\tmodels\troutes\tpy_loc\tauto_install\n" > "$INDEX"

# build the module list
mods=()
if [ "$#" -gt 0 ]; then
  for name in "$@"; do
    for base in addons odoo/addons; do
      [ -f "$base/$name/__manifest__.py" ] && mods+=("$base/$name")
    done
  done
else
  for base in addons odoo/addons; do
    for d in "$base"/*/; do
      [ -f "${d}__manifest__.py" ] && mods+=("${d%/}")
    done
  done
fi

echo ">> ${#mods[@]} modules -> $OUT"
n=0
for mp in "${mods[@]}"; do
  name="$(basename "$mp")"
  facts="$OUT/$name.facts.json"
  python3 "$EXTRACT" "$mp" > "$facts" 2>/dev/null || { echo "  !! $name failed"; continue; }
  python3 - "$facts" "$INDEX" <<'PY'
import json, sys
f, idx = sys.argv[1], sys.argv[2]
d = json.load(open(f))
m, s = d["manifest"], d["stats"]
row = [d["module"], str(m.get("category") or ""),
       ",".join(m.get("depends") or [])[:60],
       str(s["model_count"]), str(s["route_count"]),
       str(s["python_loc"]), str(bool(m.get("auto_install")))]
open(idx, "a").write("\t".join(row) + "\n")
PY
  n=$((n+1))
done
echo ">> wrote $n facts files + $INDEX"
