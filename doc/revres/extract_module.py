#!/usr/bin/env python3
"""
revres engine — reverse-engineering fact extractor for an Odoo module.

Given a module directory, statically extracts structured facts (manifest,
models, fields, relationships, security, views, controllers, LOC) as JSON.
This is the deterministic "engine" half of the revres workflow: it produces
the ground-truth facts that a prompt (see PROMPT.md) turns into a narrative
reverse-engineering document.

Pure stdlib, no Odoo import, no DB — safe to run on any module path.

Usage:
    python3 doc/revres/extract_module.py <module_path> [--pretty]
    python3 doc/revres/extract_module.py odoo/addons/base
    python3 doc/revres/extract_module.py addons/mail --pretty > mail.facts.json
"""
from __future__ import annotations
import ast
import csv
import json
import os
import re
import sys
from collections import Counter

FIELD_RE = re.compile(r"fields\.(?P<ftype>[A-Z]\w+)\s*\(")
ROUTE_RE = re.compile(r"@(?:http\.)?route\(\s*(?P<args>.*?)\)", re.S)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def parse_manifest(mod_path):
    for name in ("__manifest__.py", "__openerp__.py"):
        p = os.path.join(mod_path, name)
        if os.path.exists(p):
            try:
                return ast.literal_eval(_read(p))
            except Exception:  # noqa: BLE001
                return {}
    return {}


def _assigned_name(node):
    """Return the string value of a `_name`/`_inherit`/`_description` assignment."""
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return node.value.value
    if isinstance(node.value, (ast.List, ast.Tuple)):
        return [e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return None


def extract_models(mod_path):
    """Walk python files, find model classes and their fields via AST."""
    models = []
    for root, _dirs, files in os.walk(mod_path):
        if os.sep + "tests" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fpath = os.path.join(root, fn)
            src = _read(fpath)
            if "_name" not in src and "_inherit" not in src:
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                info = {"_name": None, "_inherit": None, "_description": None,
                        "file": os.path.relpath(fpath, mod_path),
                        "fields": {}, "field_types": {}, "methods": 0}
                fcount = Counter()
                fields = {}
                for stmt in cls.body:
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                            and isinstance(stmt.targets[0], ast.Name):
                        tname = stmt.targets[0].id
                        if tname in ("_name", "_inherit", "_description"):
                            info[tname] = _assigned_name(stmt)
                        elif isinstance(stmt.value, ast.Call):
                            fn_src = ast.get_source_segment(src, stmt.value) or ""
                            m = FIELD_RE.search("fields." + fn_src.split("fields.", 1)[1]) \
                                if "fields." in fn_src else None
                            if m:
                                ftype = m.group("ftype")
                                fcount[ftype] += 1
                                relation = None
                                if ftype in ("Many2one", "One2many", "Many2many"):
                                    rm = re.search(r"['\"]([a-z0-9_.]+)['\"]", fn_src)
                                    relation = rm.group(1) if rm else None
                                fields[tname] = {"type": ftype, "relation": relation}
                    elif isinstance(stmt, ast.FunctionDef):
                        info["methods"] += 1
                # only keep classes that are actually Odoo models
                if info["_name"] or info["_inherit"]:
                    info["fields"] = fields
                    info["field_types"] = dict(fcount)
                    models.append(info)
    return models


def extract_security(mod_path):
    sec = {"access_rules": 0, "record_rules": 0, "groups": 0}
    acc = os.path.join(mod_path, "security", "ir.model.access.csv")
    if os.path.exists(acc):
        try:
            with open(acc, newline="", encoding="utf-8") as f:
                sec["access_rules"] = max(0, sum(1 for _ in csv.reader(f)) - 1)
        except OSError:
            pass
    for root, _d, files in os.walk(os.path.join(mod_path, "security")):
        for fn in files:
            if fn.endswith(".xml"):
                src = _read(os.path.join(root, fn))
                sec["record_rules"] += src.count('model="ir.rule"')
                sec["groups"] += src.count('model="res.groups"')
    return sec


def extract_routes(mod_path):
    routes = []
    cdir = os.path.join(mod_path, "controllers")
    for root, _d, files in os.walk(cdir):
        for fn in files:
            if fn.endswith(".py"):
                src = _read(os.path.join(root, fn))
                for m in ROUTE_RE.finditer(src):
                    args = m.group("args")
                    paths = re.findall(r"['\"](/[^'\"]+)['\"]", args)
                    auth = re.search(r"auth\s*=\s*['\"](\w+)['\"]", args)
                    typ = re.search(r"type\s*=\s*['\"](\w+)['\"]", args)
                    routes.append({"paths": paths,
                                   "auth": auth.group(1) if auth else None,
                                   "type": typ.group(1) if typ else None})
    return routes


def count_views(mod_path):
    counts = Counter()
    for root, _d, files in os.walk(os.path.join(mod_path, "views")):
        for fn in files:
            if fn.endswith(".xml"):
                src = _read(os.path.join(root, fn))
                for tag in ("form", "list", "tree", "kanban", "search",
                            "pivot", "graph", "calendar", "activity"):
                    counts[tag] += len(re.findall(r"<%s\b" % tag, src))
    return dict(counts)


def count_loc(mod_path):
    py = xml = 0
    for root, _d, files in os.walk(mod_path):
        for fn in files:
            p = os.path.join(root, fn)
            if fn.endswith(".py"):
                py += _read(p).count("\n")
            elif fn.endswith(".xml"):
                xml += _read(p).count("\n")
    return {"python_loc": py, "xml_loc": xml}


def extract(mod_path):
    mod_path = os.path.abspath(mod_path.rstrip("/"))
    manifest = parse_manifest(mod_path)
    models = extract_models(mod_path)
    field_totals = Counter()
    for m in models:
        field_totals.update(m["field_types"])
    return {
        "module": os.path.basename(mod_path),
        "path": mod_path,
        "manifest": {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "category": manifest.get("category"),
            "summary": manifest.get("summary"),
            "author": manifest.get("author"),
            "license": manifest.get("license"),
            "depends": manifest.get("depends", []),
            "auto_install": manifest.get("auto_install", False),
            "application": manifest.get("application", False),
            "data_files": len(manifest.get("data", [])),
            "demo_files": len(manifest.get("demo", [])),
            "external_dependencies": manifest.get("external_dependencies", {}),
        },
        "stats": {
            "model_count": len([m for m in models if m["_name"]]),
            "inherit_only_count": len([m for m in models if not m["_name"] and m["_inherit"]]),
            "field_type_totals": dict(field_totals.most_common()),
            "route_count": 0,  # filled below
            **count_loc(mod_path),
        },
        "models": sorted(models, key=lambda m: (m["_name"] or "~" + str(m["_inherit"]))),
        "security": extract_security(mod_path),
        "routes": extract_routes(mod_path),
        "views": count_views(mod_path),
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    pretty = "--pretty" in argv
    path = [a for a in argv[1:] if not a.startswith("--")][0]
    data = extract(path)
    data["stats"]["route_count"] = len(data["routes"])
    print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
