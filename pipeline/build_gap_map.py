"""Where does Earth have no analog? For every 1-degree point on the Moon or Mars, find the best-matching place anywhere on Earth.

  python pipeline/build_gap_map.py               # Moon and Mars
  python pipeline/build_gap_map.py --body moon   # one body

Inputs (already built, nothing downloaded, nothing typed by hand):
  docs/data/grid.json + <feature>.bin            Earth grid (build_grid.py)
  docs/data/<body>_grid.json + <body>_*.bin      Moon / Mars grid (build_body_grid.py)

Outputs (generated: do not edit, rerun this script after either grid changes):
  docs/data/<body>_earthbest_<set>.bin       best Earth score at each Moon/Mars point, in % (float32, NaN = not scored)
  docs/data/<body>_earthbest_<set>_cell.bin  index of that best Earth cell (row * 360 + col, stored as float32)
  docs/data/<body>_earthbest.json            what each layer was scored on, sources, and area summaries

Feature sets ("<set>"):
  terrain  terrain + landform (slope_p90, slope_median, relief, hypso). Moon and Mars.
  all      terrain + landform + surface temperature (ts_mean, ts_range). Moon only, because Mars has no global
           temperature grid. Points where LRO Diviner has no value are left empty (not scored on fewer features).
  albedo   terrain + landform + surface albedo (MODIS on Earth, MGS TES on Mars). Mars only, because the Moon has no
           sourced albedo map. This is what clicking a Mars point compares on.

Score: exactly the website's Find on Earth rule. Per feature 1 - min(1, |gap| / scale), with the scales in grid.json;
features share their dimension's weight; dimensions count equally; an Earth cell is used only if it has a value in
every dimension. So clicking a point on the map and running "Find similar places on Earth" gives the same best score.

Needs: numpy. Takes about a minute per layer.
"""
import argparse, datetime, json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "docs", "data")
SETS = {"terrain": ["slope_p90", "slope_median", "relief", "hypso"],
        "all": ["slope_p90", "slope_median", "relief", "hypso", "ts_mean", "ts_range"],
        "albedo": ["slope_p90", "slope_median", "relief", "hypso", "albedo"]}
BODY_SETS = {"moon": ["terrain", "all"], "mars": ["terrain", "albedo"]}
CHUNK = 256


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def grid(prefix, meta):
    out = {}
    for f in meta["features"]:
        a = np.fromfile(os.path.join(DATA, prefix + f["key"] + ".bin"), "<f4")
        if a.size != meta["ny"] * meta["nx"]:
            sys.exit(f"{prefix}{f['key']}.bin does not match the size in its grid json; rebuild it")
        out[f["key"]] = a.astype(np.float32)
    return out


def best_match(E, B, feats, n_body):
    """For each body cell: max over Earth cells of the score, and which Earth cell gives it."""
    dims = {}
    for f in feats:
        dims.setdefault(f["dimension"], []).append(f)
    # Same rule as efScore in docs/index.html: an Earth cell is used if it has a value in every dimension; inside a
    # dimension the features it has share the weight (num / den), so a cell missing one feature is scored on the rest.
    has = {d: np.any([np.isfinite(E[f["key"]]) for f in fs], axis=0) for d, fs in dims.items()}
    idx_e = np.nonzero(np.all(list(has.values()), axis=0))[0]
    ok_b = np.all([np.isfinite(B[f["key"]]) for f in feats], axis=0)  # body point: every feature of the set
    best = np.full(n_body, np.nan, np.float32)
    cell = np.full(n_body, np.nan, np.float32)
    todo = np.nonzero(ok_b)[0]
    ev = {f["key"]: E[f["key"]][idx_e][None, :] for f in feats}
    fin = {k: np.isfinite(v) for k, v in ev.items()}
    den = np.zeros((1, len(idx_e)), np.float32)
    for d, fs in dims.items():
        for f in fs:
            den += fin[f["key"]] / np.float32(len(fs))
    for s in range(0, len(todo), CHUNK):
        rows = todo[s:s + CHUNK]
        tot = np.zeros((len(rows), len(idx_e)), np.float32)
        for d, fs in dims.items():
            for f in fs:
                b = B[f["key"]][rows][:, None]
                sim = 1 - np.minimum(1, np.abs(ev[f["key"]] - b) / np.float32(f.get("scale") or 1))
                tot += np.where(fin[f["key"]], sim, 0) / np.float32(len(fs))
        tot /= den
        k = tot.argmax(axis=1)
        best[rows] = tot[np.arange(len(rows)), k] * 100
        cell[rows] = idx_e[k]
        print(f"\r  {min(s + CHUNK, len(todo))}/{len(todo)} points", end="", flush=True)
    print()
    return best, cell, len(idx_e)


def area_share(v, ny, nx, cd, test):
    lat = 90 - (np.arange(ny) + .5) * cd
    w = np.repeat(np.cos(np.radians(lat)), nx)
    ok = np.isfinite(v)
    return float((w * (ok & test(np.nan_to_num(v)))).sum() / (w * ok).sum() * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", choices=sorted(BODY_SETS))
    a = ap.parse_args()
    eg = load(os.path.join(DATA, "grid.json"))
    if eg.get("demo"):
        sys.exit("grid.json is marked demo: build the real Earth grid first (build_grid.py)")
    E = grid("", eg)
    efeat = {f["key"]: f for f in eg["features"]}
    for body in ([a.body] if a.body else BODY_SETS):
        bg = load(os.path.join(DATA, f"{body}_grid.json"))
        if bg.get("demo"):
            print(f"{body}_grid.json is marked demo: skipped")
            continue
        B = grid(f"{body}_", bg)
        n = bg["ny"] * bg["nx"]
        meta = {"schema": "earth-analogs-earthbest/v0", "body": body, "ny": bg["ny"], "nx": bg["nx"], "cell_deg": bg["cell_deg"],
                "layout": "row-major float32 LE, row 0 = 90N, col 0 = 180W, NaN = not scored. *_cell.bin: Earth grid cell "
                          "index (row * nx + col of docs/data/grid.json)",
                "note": "Generated by pipeline/build_gap_map.py on " + datetime.date.today().isoformat() + ". Do not edit by hand.",
                "layers": {}}
        for st in BODY_SETS[body]:
            keys = [k for k in SETS[st] if k in B and k in efeat]
            if keys != SETS[st]:
                print(f"{body} {st}: missing {sorted(set(SETS[st]) - set(keys))} in one of the grids, skipped")
                continue
            feats = [efeat[k] for k in keys]
            print(f"== {body}, {st}: {', '.join(keys)}")
            best, cell, n_earth = best_match(E, B, feats, n)
            best.astype("<f4").tofile(os.path.join(DATA, f"{body}_earthbest_{st}.bin"))
            cell.astype("<f4").tofile(os.path.join(DATA, f"{body}_earthbest_{st}_cell.bin"))
            cd = bg["cell_deg"]
            summ = {"points": int(np.isfinite(best).sum()), "earth_cells": n_earth,
                    "median": round(float(np.nanmedian(best)), 1), "max": round(float(np.nanmax(best)), 1),
                    "min": round(float(np.nanmin(best)), 1),
                    "area_ge_80": round(area_share(best, bg["ny"], bg["nx"], cd, lambda x: x >= 80), 1),
                    "area_lt_50": round(area_share(best, bg["ny"], bg["nx"], cd, lambda x: x < 50), 1)}
            meta["layers"][st] = {"features": keys, "summary": summ,
                                  "body_sources": sorted({f["source"] for f in bg["features"] if f["key"] in keys}),
                                  "earth_sources": sorted({efeat[k]["source"] for k in keys})}
            print(f"  scored {summ['points']} points against {n_earth} Earth cells; best Earth score median {summ['median']}%, "
                  f"range {summ['min']} to {summ['max']}%; area >= 80%: {summ['area_ge_80']}%, area < 50%: {summ['area_lt_50']}%")
        with open(os.path.join(DATA, f"{body}_earthbest.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, ensure_ascii=False)
        print(f"wrote docs/data/{body}_earthbest*.bin and {body}_earthbest.json")


if __name__ == "__main__":
    main()
