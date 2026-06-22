#!/usr/bin/env python3
"""
Merge frontend (gap #3/#7) and runtime (gap #5/#6) extracts into the
metamodel records, making each record complete across all three layers
(metadata + code-read + live). Also appends synthesized behavioral_notes
and enriches it_architecture.

Usage:  python3 doc/revres/merge_layers.py [module ...]   (default: all records)
"""
import glob, json, os, sys

ROOT = os.path.dirname(__file__)


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def merge(module):
    mm_path = os.path.join(ROOT, "metamodel", f"{module}.metamodel.json")
    rec = load(mm_path)
    if not rec:
        return f"{module}: no metamodel record, skipped"
    fe = load(os.path.join(ROOT, "frontend", f"{module}.frontend.json"))
    rt = load(os.path.join(ROOT, "runtime", f"{module}.runtime.json"))
    ev = rec.setdefault("evidence", {})
    notes = ev.setdefault("behavioral_notes", [])
    existing = {n.get("element") for n in notes}
    it = rec.setdefault("it_architecture", {})

    if fe:
        f3, i7 = fe.get("frontend_gap3", {}), fe.get("integrations_gap7", {})
        ev["frontend"] = f3
        ev["integrations"] = i7
        # enrich IT architecture
        if f3.get("owl_components"):
            it["frontend_components"] = f3["owl_components"][:15]
        if i7.get("http_call_sites") or i7.get("sdk_imports"):
            it["external_integrations"] = {
                "http_call_sites": i7.get("http_call_sites", 0),
                "sdk_imports": i7.get("sdk_imports", []),
                "endpoints": i7.get("endpoints", [])[:5],
            }
        # synthesized notes (gap #3 / #7)
        if f3.get("js_files") and "frontend (OWL/JS)" not in existing:
            notes.append({"element": "frontend (OWL/JS)",
                          "observation": f"{f3['js_files']} JS files, {len(f3.get('owl_components',[]))} OWL components, "
                                         f"{len(f3.get('registry_adds',[]))} registry registrations, "
                                         f"{len(f3.get('patches',[]))} patches; asset bundles {list(f3.get('asset_bundles',{}).keys())[:3]}.",
                          "source": "static"})
        if (i7.get("http_call_sites") or i7.get("sdk_imports")) and "external integrations" not in existing:
            notes.append({"element": "external integrations",
                          "observation": f"{i7.get('http_call_sites',0)} outbound HTTP call sites; SDKs {i7.get('sdk_imports',[])}; "
                                         f"uses_api_keys={i7.get('uses_api_keys',False)}; endpoints {i7.get('endpoints',[])[:2]}.",
                          "source": "static"})

    if rt:
        real = [m for m in rt.get("models_runtime", []) if "rows" in m]
        ev["runtime"] = {"models_with_data": len(real),
                         "top": sorted(real, key=lambda x: -x["rows"])[:8]}
        if real and "runtime data/state" not in existing:
            top = ", ".join(f"{m['model']}={m['rows']}" for m in sorted(real, key=lambda x: -x["rows"])[:4])
            notes.append({"element": "runtime data/state",
                          "observation": f"live DB: {len(real)} models hold data ({top}); query-per-count captured.",
                          "source": "runtime"})

    # provenance
    prov = rec.setdefault("provenance", {})
    tools = set(prov.get("tools", []))
    if fe:
        tools.add("extract_frontend.py")
    if rt:
        tools.add("extract_runtime.sh")
    prov["tools"] = sorted(tools)

    json.dump(rec, open(mm_path, "w"), indent=2, ensure_ascii=False)
    layers = ["metadata", "code-read"]
    if fe:
        layers.append("frontend")
    if rt:
        layers.append("runtime")
    return f"{module}: merged layers={layers} notes={len(notes)}"


def main(argv):
    mods = argv[1:] or [os.path.basename(p).split(".")[0]
                        for p in glob.glob(os.path.join(ROOT, "metamodel", "*.metamodel.json"))]
    for m in sorted(set(mods)):
        print(merge(m))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
