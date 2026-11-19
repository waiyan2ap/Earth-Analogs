"""Surface albedo: a new comparison dimension for Earth and Mars (the Moon has no like-for-like global albedo file yet).

  python pipeline/prep_albedo.py --modis "pipeline/raw/albedo/MCD43C3*.hdf"
  python pipeline/prep_albedo.py --mars pipeline/raw/albedo/Mars_MGS_TES_Albedo_mosaic_global_7410m.tif
  (both at once is fine)

Adds one feature, key "albedo", dimension "albedo", to the files the website already reads. Nothing else is changed:
  --modis  docs/data/albedo.bin + an "albedo" entry in docs/data/grid.json (Earth grid)
  --mars   docs/data/mars_albedo.bin + an entry in docs/data/mars_grid.json (pick any point on Mars)
           and an "albedo" value for every Mars site in docs/data/targets.json (Jezero, Olympus, Valles)

Earth: NASA MODIS MCD43C3 v6.1 (Terra+Aqua BRDF/Albedo, 0.05 degree CMG), layer Albedo_WSA_shortwave = white-sky
  (bihemispherical) albedo, 0.3-5.0 um, value x 0.001, 32767 = no data. Each file is a 16-day retrieval centred on its
  date; give one file per month. Per 0.05 degree pixel the months with a value are averaged, then each 1-degree cell is the
  mean of its pixels. Snow and ice are included (that is the point: an ice sheet is not dark regolith).
Mars: MGS TES bolometric albedo global mosaic (USGS Astrogeology, 7410 m, 0.3-2.9 um reduced to Lambert albedo,
  Christensen et al. 2001). Values are clipped to 0.06-0.32 in that file (about 3% of pixels at each end), so the
  darkest and brightest regions read slightly less extreme than they are. Averaged over the same 111.2 km patch as the
  rest of the Mars grid (60 x 60 points around each 1-degree point, nearest pixel).
Why white-sky against Lambert: both describe reflection of diffuse, all-direction light over a broad solar band, so
  they are the closest like-for-like pair available. They are not identical (band edges, and TES is afternoon data).

Needs: numpy, rasterio, and pyhdf for the .hdf files (pip install pyhdf).
"""
import argparse, datetime, glob, json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "docs", "data")
SCALE = 0.3  # albedo gap that counts as "completely different": starting guess, like the other scales (see README)
EARTH_SRC = ("NASA MODIS MCD43C3 v6.1 BRDF/Albedo, white-sky shortwave albedo (0.3-5.0 um), 0.05 degree CMG, one 16-day "
             "retrieval per month of 2025 averaged (LP DAAC; pipeline/prep_albedo.py)")
EARTH_URL = "https://doi.org/10.5067/MODIS/MCD43C3.061"
MARS_SRC = ("MGS TES global bolometric albedo mosaic, 7410 m (USGS Astrogeology, "
            "https://astrogeology.usgs.gov/search/map/mars_mgs_tes_global_bolometric_albedo_map_7410m; Christensen et al. 2001)")
LABEL = "Surface albedo (share of sunlight reflected)"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)


def put_feature(man, feat):
    man["features"] = [f for f in man["features"] if f["key"] != feat["key"]] + [feat]


def earth(pattern):
    try:
        from pyhdf.SD import SD, SDC
    except ImportError:
        sys.exit("reading .hdf files needs pyhdf: run  pip install pyhdf  and try again")
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"no files match {pattern}")
    s = c = None
    months = []
    for p in files:
        f = SD(p, SDC.READ)
        d = f.select("Albedo_WSA_shortwave")
        at = d.attributes()
        a = d.get().astype("float32")
        f.end()
        if a.shape != (3600, 7200):
            sys.exit(f"{os.path.basename(p)}: {a.shape} is not the 0.05 degree global grid (3600 x 7200)")
        ok = (a != at.get("_FillValue", 32767)) & (a >= 0) & (a <= 32766)
        a = a * at.get("scale_factor", 0.001) + at.get("add_offset", 0.0)
        s = np.where(ok, a, 0) if s is None else s + np.where(ok, a, 0)
        c = ok.astype("uint8") if c is None else c + ok
        months.append(os.path.basename(p).split(".")[1])
        print(f"  {os.path.basename(p)}: {ok.mean():.0%} of pixels have a value, median {np.median(a[ok]):.3f}")
    with np.errstate(invalid="ignore"):
        px = np.where(c > 0, s / np.maximum(c, 1), np.nan)
    cells = px.reshape(180, 20, 360, 20)
    with np.errstate(invalid="ignore"):
        n = np.isfinite(cells).sum(axis=(1, 3))
        out = np.where(n > 0, np.nansum(cells, axis=(1, 3)) / np.maximum(n, 1), np.nan).astype("float32")
    out.astype("<f4").tofile(os.path.join(DATA, "albedo.bin"))
    gpath = os.path.join(DATA, "grid.json")
    man = load(gpath)
    put_feature(man, dict(key="albedo", label=LABEL, unit="", dimension="albedo", scale=SCALE,
                          source=EARTH_SRC + f"; files {', '.join(months)}", url=EARTH_URL,
                          resolution="0.05 degree (about 5.6 km)", date=datetime.date.today().isoformat()))
    save(gpath, man)
    print(f"earth: {int(np.isfinite(out).sum())} cells with an albedo, range {np.nanmin(out):.3f} to {np.nanmax(out):.3f}, "
          f"from {len(files)} files; wrote albedo.bin and grid.json")
    return out


def mars(path):
    import build_body_grid as bb
    from build_site_terrain import MARS_R
    bb.R_BODY = MARS_R
    G = bb.open_global(path, 1.0)  # want_px_m=1: never average while reading
    a = G[0]
    a[(a < 0) | (a > 1)] = np.nan
    lo, hi = np.nanmin(a), np.nanmax(a)
    if not (0 < lo < hi < 1):
        sys.exit(f"values {lo} to {hi} are not albedos (0 to 1): wrong file?")
    print(f"  TES albedo map: {a.shape[1]} x {a.shape[0]} px, values {lo:.3f} to {hi:.3f}")

    def patch(lat, lons):
        dla, dlo = bb.patch_offsets(lat)
        lons = np.atleast_1d(lons)
        v = bb.sample(G, np.broadcast_to(dla, (len(lons), bb.N, bb.N)), lons[:, None, None] + dlo[None], True)
        v = v.reshape(len(lons), -1)
        ok = np.isfinite(v)
        with np.errstate(invalid="ignore"):
            return np.where(ok.mean(axis=1) >= 0.5, np.nansum(v, axis=1) / np.maximum(ok.sum(axis=1), 1), np.nan)

    lons = -180 + (np.arange(bb.NX) + 0.5) * bb.CELL
    out = np.full((bb.NY, bb.NX), np.nan, "float32")
    for i in range(bb.NY):
        out[i] = patch(90 - (i + 0.5) * bb.CELL, lons)
    out.astype("<f4").tofile(os.path.join(DATA, "mars_albedo.bin"))
    today = datetime.date.today().isoformat()
    src = (f"Measured by pipeline/prep_albedo.py from {MARS_SRC}: mean over the {bb.PATCH_KM} km patch of {bb.N} x {bb.N} "
           f"points around each 1-degree point (nearest pixel). Accessed {today}.")
    gpath = os.path.join(DATA, "mars_grid.json")
    man = load(gpath)
    put_feature(man, dict(key="albedo", unit="", source=src))
    save(gpath, man)
    print(f"mars grid: {np.isfinite(out).mean():.0%} of points have an albedo; wrote mars_albedo.bin and mars_grid.json")
    # the named Mars targets, at their exact centres (same coordinates as build_targets.py)
    import build_targets as bt
    tpath = os.path.join(DATA, "targets.json")
    tj = load(tpath)
    for sid, cfg in bt.SITES.items():
        if cfg["body"] != "mars":
            continue
        v = float(patch(cfg["lat"], cfg["lon"])[0])
        if not math.isfinite(v):
            print(f"  {sid}: no albedo value around the site")
            continue
        text = (f"Measured by pipeline/prep_albedo.py from {MARS_SRC}: mean over a {bb.PATCH_KM} km patch centred "
                f"{abs(cfg['lat'])}°{'N' if cfg['lat'] >= 0 else 'S'}, {abs(cfg['lon'])}°{'E' if cfg['lon'] >= 0 else 'W'}. "
                f"Accessed {today}.")
        tj["targets"].setdefault(sid, {})["albedo"] = {"value": round(v, 3), "source": text}
        print(f"  {sid}: albedo {v:.3f}")
    save(tpath, tj)
    print("wrote targets.json (albedo for the Mars targets; all other values unchanged)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modis", help='MCD43C3 .hdf files, one per month, e.g. "pipeline/raw/albedo/MCD43C3*.hdf" (quotes needed)')
    ap.add_argument("--mars", help="MGS TES global bolometric albedo GeoTIFF")
    a = ap.parse_args()
    if not (a.modis or a.mars):
        ap.error("give --modis and/or --mars")
    sys.path.insert(0, HERE)
    if a.modis:
        earth(a.modis)
    if a.mars:
        mars(a.mars)


if __name__ == "__main__":
    main()
