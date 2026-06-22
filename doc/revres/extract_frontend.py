#!/usr/bin/env python3
"""
revres frontend + integrations extractor — closes metadata gaps #3 and #7.

Statically mines a module's `static/src/` (JS/OWL) and Python for things the
Python ORM metadata never captures:
  - #3 Frontend: OWL components, registry registrations, patches, .xml templates,
    asset-bundle targets from the manifest.
  - #7 External integrations: outbound HTTP/API calls, SDK imports, api-key params.

Pure stdlib, no Odoo import, no DB. Complements extract_module.py.

Usage:
    python3 doc/revres/extract_frontend.py addons/mail [--pretty]
"""
from __future__ import annotations
import ast
import json
import os
import re
import sys
from collections import Counter

# --- #3 frontend signals ---------------------------------------------------
OWL_COMPONENT_RE = re.compile(r"class\s+(\w+)\s+extends\s+Component\b")
REGISTRY_RE = re.compile(r"registry\s*\.\s*category\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.\s*add\(\s*['\"]([^'\"]+)['\"]")
PATCH_RE = re.compile(r"\bpatch\(\s*([\w.]+)\s*,")
TEMPLATE_RE = re.compile(r"static_template\s*=\s*['\"]([^'\"]+)['\"]|\.xml\b")
SERVICE_RE = re.compile(r"name:\s*['\"]([\w.]+)['\"]")

# --- #7 external integration signals ---------------------------------------
HTTP_CALL_RE = re.compile(r"\b(requests\.(get|post|put|patch|delete)|urlopen|http\.client|Session\(\)|aiohttp|httpx)\b")
SDK_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+(stripe|paypalrestsdk|boto3|googleapiclient|twilio|sendgrid|zeep|xmlrpc|ovh|requests)\b", re.M)
APIKEY_RE = re.compile(r"(api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?secret|bearer)", re.I)
ENDPOINT_RE = re.compile(r"['\"](https?://[^'\"]{8,80})['\"]")


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def extract_frontend(mod_path):
    static = os.path.join(mod_path, "static", "src")
    fe = {"present": os.path.isdir(static), "js_files": 0, "xml_templates": 0,
          "owl_components": [], "registry_adds": [], "patches": [], "services": []}
    if not fe["present"]:
        return fe
    for root, _d, files in os.walk(static):
        for fn in files:
            p = os.path.join(root, fn)
            if fn.endswith(".js"):
                fe["js_files"] += 1
                src = _read(p)
                fe["owl_components"] += OWL_COMPONENT_RE.findall(src)
                fe["registry_adds"] += [f"{cat}:{key}" for cat, key in REGISTRY_RE.findall(src)]
                fe["patches"] += PATCH_RE.findall(src)
                fe["services"] += [m for m in SERVICE_RE.findall(src)]
            elif fn.endswith(".xml"):
                fe["xml_templates"] += 1
    # de-dup + cap
    for k in ("owl_components", "registry_adds", "patches", "services"):
        fe[k] = sorted(set(fe[k]))[:40]
    return fe


def extract_integrations(mod_path):
    integ = {"http_call_sites": 0, "sdk_imports": [], "uses_api_keys": False,
             "endpoints": [], "files": []}
    for root, _d, files in os.walk(mod_path):
        if os.sep + "static" in root or os.sep + "tests" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            src = _read(p)
            calls = len(HTTP_CALL_RE.findall(src))
            sdks = SDK_IMPORT_RE.findall(src)
            ep = ENDPOINT_RE.findall(src)
            if calls or sdks or ep or APIKEY_RE.search(src):
                rel = os.path.relpath(p, mod_path)
                integ["http_call_sites"] += calls
                integ["sdk_imports"] += sdks
                integ["endpoints"] += ep
                integ["uses_api_keys"] = integ["uses_api_keys"] or bool(APIKEY_RE.search(src))
                if calls or sdks or ep:
                    integ["files"].append(rel)
    integ["sdk_imports"] = sorted(set(integ["sdk_imports"]))
    integ["endpoints"] = sorted(set(integ["endpoints"]))[:20]
    integ["files"] = sorted(set(integ["files"]))[:20]
    return integ


def extract(mod_path):
    mod_path = os.path.abspath(mod_path.rstrip("/"))
    # asset bundles declared in the manifest
    assets = {}
    man = os.path.join(mod_path, "__manifest__.py")
    if os.path.exists(man):
        try:
            m = ast.literal_eval(_read(man))
            assets = {b: len(v) for b, v in (m.get("assets") or {}).items()}
        except Exception:  # noqa: BLE001
            pass
    fe = extract_frontend(mod_path)
    fe["asset_bundles"] = assets
    return {
        "module": os.path.basename(mod_path),
        "frontend_gap3": fe,
        "integrations_gap7": extract_integrations(mod_path),
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    pretty = "--pretty" in argv
    path = [a for a in argv[1:] if not a.startswith("--")][0]
    print(json.dumps(extract(path), indent=2 if pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
