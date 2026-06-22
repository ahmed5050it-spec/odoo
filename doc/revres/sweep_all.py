#!/usr/bin/env python3
"""Mass sweep: give EVERY remaining Odoo module a baseline metamodel record.

For each module without a metamodel/<m>.metamodel.json:
  1. ensure facts/<m>.facts.json + frontend/<m>.frontend.json (run extractors)
  2. auto-classify (auto_classify.classify) -> (value_model, activity, apqc)
  3. gen_thin.gen() writes a schema-valid baseline record (tier: auto)

Records written here are BASELINE (category-inferred classification, no
code-read behavior). The assignments ledger marks them 'auto' vs agent 'deep'.

Usage: python3 doc/revres/sweep_all.py [--limit N]
"""
import json, os, subprocess, sys, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(ROOT))
sys.path.insert(0, ROOT)
import auto_classify  # noqa: E402
import gen_thin  # noqa: E402

ADDON_DIRS = [os.path.join(REPO, "addons"), os.path.join(REPO, "odoo", "addons")]


def all_modules():
    mods = {}
    for base in ADDON_DIRS:
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name)
            if name not in mods and os.path.isfile(os.path.join(p, "__manifest__.py")):
                mods[name] = p
    return mods


def have_record(m):
    return os.path.exists(os.path.join(ROOT, "metamodel", f"{m}.metamodel.json"))


def ensure_facts(m, path):
    f = os.path.join(ROOT, "facts", f"{m}.facts.json")
    fe = os.path.join(ROOT, "frontend", f"{m}.frontend.json")
    if not os.path.exists(f):
        with open(f, "w") as out:
            subprocess.run([sys.executable, os.path.join(ROOT, "extract_module.py"), path],
                           stdout=out, stderr=subprocess.DEVNULL, timeout=120)
    if not os.path.exists(fe):
        with open(fe, "w") as out:
            subprocess.run([sys.executable, os.path.join(ROOT, "extract_frontend.py"), path],
                           stdout=out, stderr=subprocess.DEVNULL, timeout=120)
    return f


def main(argv):
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 10**9
    mods = all_modules()
    todo = [(m, p) for m, p in mods.items() if not have_record(m)]
    print(f"total modules: {len(mods)} | already have record: {len(mods)-len(todo)} | sweeping: {min(len(todo),limit)}")
    done = 0
    from collections import Counter
    vmc = Counter()
    for m, p in todo[:limit]:
        try:
            fpath = ensure_facts(m, p)
            facts = json.load(open(fpath))
            vm, ac, apqc = auto_classify.classify(facts)
            gen_thin.gen(m, vm, ac, apqc)
            vmc[vm] += 1
            done += 1
        except Exception as e:  # noqa: BLE001
            print(f"  !! {m}: {e}")
    print(f"swept {done} baseline records | value models: {dict(vmc)}")
    print(f"catalog total now: {len(glob.glob(os.path.join(ROOT,'metamodel','*.metamodel.json')))}")


if __name__ == "__main__":
    main(sys.argv)
