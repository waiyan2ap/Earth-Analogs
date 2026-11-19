"""Build the named-site dataset the website loads (docs/data/sites.json) from real, sourced data only.

  python pipeline/build_named_sites.py

Inputs (nothing is typed by hand except names, coordinates, descriptions and tags):
  pipeline/named_sites.json   hand-edited team file: sites, coordinates (+ where they come from), tags (+ citation),
                              which body each Earth site is an analog for, and body facts with their source
  docs/data/grid.json + *.bin the Earth grid from build_grid.py: each Earth site takes the values of the 1-degree cell
                              that contains it, so a named site scores exactly like the same cell in "Find on Earth"
  docs/data/targets.json      Moon/Mars values from build_targets.py

Output: docs/data/sites.json (schema earth-analogs/v1). Generated: do not edit it, edit the inputs and rerun.
Rerun after build_grid.py or build_targets.py.

Scoring defaults match "Find on Earth": each dimension (terrain, landform, thermal) counts equally and its features
share that weight; a feature with no value on one side is skipped. Tags are shown but have
weight 0 (not scored) because they are curated labels, not measurements.
"""
import argparse, datetime, json, math, os, re, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from finder_pipeline import cell_of

GROUP = {"terrain": "Terrain", "landform": "Landform", "thermal": "Climate", "day thermal": "Climate", "air": "Air (Earth only)"}  # "Climate" keeps the app's Climate preset working
SHORT = {"slope_p90": "Steep slope (90th pct)", "slope_median": "Median slope", "relief": "Local relief",
         "hypso": "Landform shape", "ts_mean": "Mean surface temperature", "ts_range": "Day-night surface swing", "ts_day": "Daytime surface temperature",
         "t_mean": "Mean air temperature", "t_range": "Air temperature range"}
UNIT = {"deg": "°", "degC": "°C"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=os.path.join(HERE, "named_sites.json"))
    ap.add_argument("--data", default=os.path.join(HERE, "..", "docs", "data"))
    a = ap.parse_args()

    inp = load(a.sites)
    grid = load(os.path.join(a.data, "grid.json"))
    tj = load(os.path.join(a.data, "targets.json"))
    if grid.get("demo") or tj.get("demo"):
        sys.exit("grid.json or targets.json is marked demo. Build the real ones first (build_grid.py, build_targets.py).")
    T = tj.get("targets", {})
    ny, nx, cell = grid["ny"], grid["nx"], grid["cell_deg"]
    feats = {}
    for f in grid["features"]:
        arr = np.fromfile(os.path.join(a.data, f["key"] + ".bin"), "<f4")
        if arr.size != ny * nx:
            sys.exit(f"{f['key']}.bin does not match the size in grid.json; rerun build_grid.py")
        feats[f["key"]] = arr.reshape(ny, nx)

    per_dim = {}
    for f in grid["features"]:
        per_dim[f["dimension"]] = per_dim.get(f["dimension"], 0) + 1
    metrics = [{"key": f["key"], "label": SHORT.get(f["key"], f["label"]), "desc": f["label"], "type": "num",
                "unit": UNIT.get(f["unit"], f["unit"]), "group": GROUP.get(f["dimension"], f["dimension"].title()),
                "dimension": f["dimension"], "scale": f["scale"], "weight": round(1 / per_dim[f["dimension"]], 4)}
               for f in grid["features"]]
    metrics.append({"key": "tags", "label": "Geology tags (curated)", "type": "tags", "group": "Terrain", "weight": 0})

    sources, gsrc = {}, {}  # one source entry per Earth dataset, shared by its features
    for f in grid["features"]:
        sid = gsrc.setdefault(f["source"], "grid:%d" % len(gsrc))
        sources[sid] = {"name": f"{f['source']}: value of the {cell:g}° grid cell that contains the site "
                                f"(pipeline/build_grid.py)", "url": f.get("url", "")}
    sources["tags:curated"] = {"name": "Geology tags curated by the team. No citation yet; shown but not scored by default.",
                               "url": "", "uncited": True}

    out_sites, report, tsrc = [], [], {}
    for s in inp["sites"]:
        o = {k: s[k] for k in ("id", "body", "type", "name", "lat", "lon", "summary") if k in s}
        o["coord_src"] = s.get("coord_src", "") + (" Check against: " + s["coord_check"] + "." if s.get("coord_check") else "")
        if s.get("analogs"):
            o["analogs"] = s["analogs"]
        if s.get("analog_for"):
            o["analog_for"] = s["analog_for"]
        m = {}
        if s["body"] == "earth":
            i, j = cell_of(s["lat"], s["lon"], cell)
            for f in grid["features"]:
                v = float(feats[f["key"]][i, j])
                if math.isfinite(v):
                    m[f["key"]] = {"value": round(v, 3 if f["key"] == "hypso" else 2), "source": gsrc[f["source"]]}
            report.append(f"  {s['id']:12s} cell row {i}, col {j}: " + ", ".join(f"{k} {v['value']}" for k, v in m.items()))
        else:
            t = T.get(s["id"], {})
            for f in grid["features"]:
                if f["key"] in t and t[f["key"]].get("value") is not None:
                    src = t[f["key"]].get("source", "")
                    sid = tsrc.setdefault(src, "targets:%s:%d" % (s["id"], len(tsrc)))  # one entry per distinct source text
                    if sid not in sources:
                        mm = re.match(r"Measured by (\S+) from (.+?) \((https?://[^)]+)\)", src)
                        sources[sid] = {"name": (f"{mm.group(2)}, measured by {mm.group(1)} over a {tj.get('patch_km', '')} km "
                                                 f"patch around {s['name']}") if mm else src,
                                        "url": mm.group(3) if mm else ""}
                    m[f["key"]] = {"value": t[f["key"]]["value"], "source": sid}
            report.append(f"  {s['id']:12s} from targets.json: " + (", ".join(f"{k} {v['value']}" for k, v in m.items()) or "NO VALUES"))
        if s.get("tags"):
            if s.get("tags_src"):
                sid = "tags:" + s["id"]
                sources[sid] = {"name": f"Geology tags for {s['name']}: {s['tags_src']}", "url": s.get("tags_url", "")}
            else:
                sid = "tags:curated"
            m["tags"] = {"value": s["tags"], "source": sid}
        o["metrics"] = m
        out_sites.append(o)

    bodies = {}
    for bid, b in inp["bodies"].items():
        facts = []
        for f in b.get("facts", []):
            if not f.get("src"):
                print(f"  skipped body fact without a source: {bid} / {f.get('label')}")
                continue
            facts.append({"label": f["label"], "value": f"{f['value']} ({f['src']})"})
            sources.setdefault("fact:" + f["src"], {"name": f["src"], "url": f.get("url", "")})
        bodies[bid] = {"name": b["name"], "summary": b.get("summary", ""), "facts": facts}

    data = {"schema": "earth-analogs/v1",
            "meta": {"title": "Named sites: values from the Earth grid and Moon/Mars targets", "status": "real",
                     "updated": datetime.date.today().isoformat(),
                     "howto": "Generated by pipeline/build_named_sites.py from pipeline/named_sites.json, docs/data/grid.json "
                              "and docs/data/targets.json. Do not edit by hand."},
            "sources": sources,
            "metrics": metrics, "bodies": bodies, "sites": out_sites}
    path = os.path.join(a.data, "sites.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print("values per site:")
    print("\n".join(report))
    print(f"wrote {path}: {len(out_sites)} sites, {len(metrics)} metrics, {len(sources)} sources")


if __name__ == "__main__":
    main()
