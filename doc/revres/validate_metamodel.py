#!/usr/bin/env python3
"""Validate metamodel records against the schema + print a coverage table.

Usage: python3 doc/revres/validate_metamodel.py
Pure stdlib (no jsonschema dep): checks required keys + confidence tags.
"""
import json, glob, os, sys

ROOT = os.path.dirname(__file__)
SCHEMA = json.load(open(os.path.join(ROOT, "metamodel.schema.json")))
REQ = SCHEMA["required"]

rows, ok = [], True
for f in sorted(glob.glob(os.path.join(ROOT, "metamodel", "*.metamodel.json"))):
    try:
        r = json.load(open(f))
    except Exception as e:  # noqa: BLE001
        print(f"INVALID JSON: {f}: {e}"); ok = False; continue
    missing = [k for k in REQ if k not in r]
    cls = r.get("classification", {})
    conf = r.get("reverse_eng_confidence", {})
    rows.append((r.get("subsystem", "?"),
                 cls.get("value_model", "?"),
                 cls.get("apqc_category", "?")[:24],
                 len(r.get("it_architecture", {}).get("data_objects", [])),
                 len(conf),
                 "OK" if not missing else "MISSING:" + ",".join(missing)))
    if missing:
        ok = False

print(f"{'module':<12}{'value_model':<10}{'apqc':<26}{'objs':<6}{'conf':<6}status")
print("-" * 70)
for m, vm, ap, no, nc, st in rows:
    print(f"{m:<12}{vm:<10}{ap:<26}{no:<6}{nc:<6}{st}")
print(f"\n{len(rows)} records | {'ALL VALID' if ok else 'ERRORS PRESENT'}")
sys.exit(0 if ok else 1)
