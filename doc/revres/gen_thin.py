#!/usr/bin/env python3
"""Generate a baseline metamodel record for a THIN module from its facts +
frontend extracts (the architect step automated for small modules). Classification
is supplied on the CLI. Produces a schema-valid record; meant for modules too small
to warrant a full agent pass.

Usage: gen_thin.py <module> <value_model> <activity_class> <apqc_category>
"""
import json, os, sys

ROOT = os.path.dirname(__file__)


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def gen(module, vm, ac, apqc):
    facts = load(f"{ROOT}/facts/{module}.facts.json")
    fe = load(f"{ROOT}/frontend/{module}.frontend.json")
    if not facts:
        return f"{module}: no facts"
    f3 = (fe or {}).get("frontend_gap3", {})
    i7 = (fe or {}).get("integrations_gap7", {})
    models = [m for m in facts["models"] if m.get("_name")]
    data_objects = [m["_name"] for m in models][:20]
    erm = []
    for m in models:
        for r in m.get("fields", {}).values() if isinstance(m.get("fields"), dict) else []:
            pass
    # relations come as "a->b" strings only in metamodel; facts store fields dict -> derive
    for m in models:
        flds = m.get("fields", {})
        if isinstance(flds, dict):
            for fn, fv in flds.items():
                if isinstance(fv, dict) and fv.get("relation"):
                    erm.append(f"{m['_name']} -> {fv['relation']}")
    notes = []
    if f3.get("js_files"):
        notes.append({"element": "frontend (OWL/JS)",
                      "observation": f"{f3['js_files']} JS files, {len(f3.get('owl_components',[]))} OWL components, "
                                     f"{len(f3.get('registry_adds',[]))} registry adds; bundles {list(f3.get('asset_bundles',{}).keys())[:3]}.",
                      "source": "static"})
    if i7.get("http_call_sites") or i7.get("sdk_imports"):
        notes.append({"element": "external integrations",
                      "observation": f"{i7.get('http_call_sites',0)} HTTP call sites; SDKs {i7.get('sdk_imports',[])}; api_keys={i7.get('uses_api_keys',False)}.",
                      "source": "static"})
    notes.append({"element": "thin module",
                  "observation": f"{len(models)} models, {facts['stats']['route_count']} routes, {facts['stats']['python_loc']} py LOC — "
                                 "baseline record (auto-architect); deep method semantics not code-read.",
                  "source": "ast"})
    rec = {
        "subsystem": module,
        "evidence": {
            "manifest": {k: facts["manifest"].get(k) for k in ("name", "category", "depends", "auto_install", "application")},
            "models": [{"_name": m["_name"], "_description": m.get("_description"),
                        "fields": len(m.get("fields", {})) if isinstance(m.get("fields"), dict) else m.get("fields", 0)} for m in models],
            "routes": facts["routes"], "security": facts["security"], "views": facts["views"],
            "frontend": f3, "integrations": i7, "runtime": {"models_with_data": 0, "top": []},
            "behavioral_notes": notes,
        },
        "it_architecture": {
            "application": f"{module} ({facts['manifest'].get('name')})",
            "software_services": sorted({p for r in facts["routes"] for p in r.get("paths", [])})[:10],
            "data_objects": data_objects,
            "logical_data_erm": sorted(set(erm))[:12],
            "information_flows": [f"depends: {', '.join(facts['manifest'].get('depends', []))}"],
            "frontend_components": f3.get("owl_components", [])[:15],
        },
        "business_architecture": {
            "capabilities": [facts["manifest"].get("name", module)],
            "value_streams": [], "information_concepts": data_objects[:6],
            "organization": [], "products": [],
            "policies": [f"{facts['security']['record_rules']} record rules"] if facts["security"]["record_rules"] else [],
            "stakeholders": [], "strategy": None, "metrics": [],
        },
        "classification": {"value_model": vm, "activity_class": ac, "apqc_category": apqc,
                           "rationale": f"{module}: thin {vm}/{ac} module (auto-architect baseline)."},
        "fit_to_standard": {"standard_capabilities": [facts["manifest"].get("name", module)],
                            "typical_fits": [], "common_gaps": [],
                            "drive_hints": [f"odoo shell: env['{data_objects[0]}'].search([],limit=3)" if data_objects else "n/a"]},
        "reverse_eng_confidence": {"information_concepts": "auto", "organization": "auto", "products": "auto",
                                   "capabilities": "inferred", "value_streams": "inferred", "policies": "inferred",
                                   "metrics": "inferred", "strategy": "human"},
        "open_questions": ["Baseline auto-architect record; method semantics + value-stream not deeply code-read."],
        "provenance": {"explorer_facts": f"doc/revres/facts/{module}.facts.json",
                       "tools": ["extract_module.py", "extract_frontend.py", "gen_thin.py"], "odoo_version": "19.0"},
    }
    json.dump(rec, open(f"{ROOT}/metamodel/{module}.metamodel.json", "w"), indent=2, ensure_ascii=False)
    return f"{module}: {vm}/{ac}/{apqc} ({len(models)} models)"


if __name__ == "__main__":
    print(gen(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
