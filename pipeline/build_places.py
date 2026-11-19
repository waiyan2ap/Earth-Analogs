"""Place names for the Earth grid: which country and province/state each 1-degree cell is in, so the website can say
"Iceland: Norðurland eystra" instead of only "64.5N, 17.5W". Writes docs/data/places.json.

  python pipeline/build_places.py
  (reads the two Natural Earth files from GitHub; or pass local copies with --admin1 FILE --admin0 FILE)

Source: Natural Earth 1:10m Cultural Vectors, Admin 1 (states, provinces) and Admin 0 (countries), public domain,
https://www.naturalearthdata.com/ (GeoJSON copies: https://github.com/nvkelso/natural-earth-vector/tree/master/geojson).
Method: rasterize the polygons on a 0.1 degree grid; each 1-degree cell takes the province (else country) that covers most of
its land. A cell with no land in Natural Earth gets no name. Boundaries are as Natural Earth draws them (de facto lines).
"""
import argparse, json, os, sys, urllib.request
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
SUB = 10  # 0.1 degree sub-pixels per 1-degree cell


def load(path_or_url):
    if os.path.exists(path_or_url):
        with open(path_or_url, encoding="utf-8") as f:
            return json.load(f)
    print(f"  downloading {path_or_url}")
    with urllib.request.urlopen(path_or_url, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def burn(features, label):
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    names, shapes = [], []
    for f in features:
        if not f.get("geometry"):
            continue
        n = label(f["properties"])
        if not n:
            continue
        names.append(n)
        shapes.append((f["geometry"], len(names)))  # 0 = nothing
    a = rasterize(shapes, out_shape=(180 * SUB, 360 * SUB), transform=from_origin(-180, 90, 1 / SUB, 1 / SUB),
                  fill=0, dtype="int32", all_touched=False)
    return a, names


def majority(a):
    """Per 1-degree cell: most common non-zero sub-pixel id (0 if the cell has no land)."""
    b = a.reshape(180, SUB, 360, SUB).transpose(0, 2, 1, 3).reshape(180, 360, SUB * SUB)
    out = np.zeros((180, 360), "int32")
    for i in range(180):
        for j in range(360):
            v = b[i, j][b[i, j] > 0]
            if v.size:
                u, c = np.unique(v, return_counts=True)
                out[i, j] = u[np.argmax(c)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin1", default=RAW + "ne_10m_admin_1_states_provinces.geojson")
    ap.add_argument("--admin0", default=RAW + "ne_10m_admin_0_countries.geojson")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data", "places.json"))
    a = ap.parse_args()
    A1, A0 = load(a.admin1), load(a.admin0)
    r1, n1 = burn(A1["features"], lambda p: (p.get("name_en") or p.get("name") or "").strip() + "|" + (p.get("admin") or "").strip())
    r0, n0 = burn(A0["features"], lambda p: "|" + (p.get("NAME_EN") or p.get("ADMIN") or p.get("NAME") or "").strip())
    m1, m0 = majority(r1), majority(r0)
    names, idx = [], {}
    cell = np.full((180, 360), -1, "int32")
    for i in range(180):
        for j in range(360):
            n = n1[m1[i, j] - 1] if m1[i, j] else (n0[m0[i, j] - 1] if m0[i, j] else None)
            if n is None or n.strip("|") == "":
                continue
            reg, cty = n.split("|", 1)
            n = f"{cty}: {reg}" if reg and cty and reg != cty else (cty or reg)
            if n not in idx:
                idx[n] = len(names); names.append(n)
            cell[i, j] = idx[n]
    out = {"schema": "earth-analogs-places/v1", "cell_deg": 1.0, "ny": 180, "nx": 360,
           "layout": "cells: row-major, row 0 = 90N, col 0 = 180W; value = index into names, -1 = no land in Natural Earth",
           "source": "Natural Earth 1:10m Admin 1 (states, provinces) and Admin 0 (countries), public domain "
                     "(https://www.naturalearthdata.com/); majority of land in each 1-degree cell (pipeline/build_places.py)",
           "names": names, "cells": cell.ravel().tolist()}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {a.out}: {len(names)} names, {(cell >= 0).sum()} named cells")
    for la, lo in ((64.5, -17.5), (-24.5, -69.5), (75.5, -89.5), (-77.5, 162.5), (36.5, 82.5)):
        k = cell[int(90 - la), int(lo + 180)]
        print(f"  {la:+.1f}, {lo:+.1f}: {names[k] if k >= 0 else '(none)'}")


if __name__ == "__main__":
    main()
