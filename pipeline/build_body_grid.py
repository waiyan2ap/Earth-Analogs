"""Moon or Mars grid for "pick any point": the same terrain/landform features as targets.json, measured around EVERY
1-degree point of the body, so the website can compare any clicked point with Earth.
Writes docs/data/<body>_grid.json + <body>_<key>.bin (body = moon or mars).

  python pipeline/build_body_grid.py --body moon --dem pipeline/raw/moon_dem/ldem_16.lbl --dem-src "NAME (PAGE URL)"
  python pipeline/build_body_grid.py --body mars --dem pipeline/raw/mars_dem/FILE.tif --dem-src "NAME (PAGE URL)"
  (--dem may also be an https URL of a Cloud Optimized GeoTIFF that has overviews: only the overview level is read.)
  Mars has no global surface temperature map in this project yet, so the Mars grid is terrain and landform only.
  with Moon surface temperature where Diviner maps exist (made by prep_diviner.py; empty outside the bands you downloaded):
  python pipeline/build_body_grid.py --dem ... --dem-src "..." --ts-day pipeline/raw/moon_ts_day.tif --ts-night pipeline/raw/moon_ts_night.tif

Input: one GLOBAL simple-cylindrical elevation file that GDAL can open (GeoTIFF, or PDS .lbl/.img), ideally about
1.9 km per pixel (for example the LOLA gridded DEM at 16 pixels per degree). Bigger files are averaged down while reading.
Values may be heights (m) or radii (m, about 1,737,400 Moon / 3,396,190 Mars); radii are converted to heights.

Method, matching build_targets.py as closely as a global file allows:
  for each grid point (cell centres 89.5N..89.5S, 179.5W..179.5E, the Earth grid layout), take a 111.2 km x 111.2 km patch
  of 60 x 60 points 1853 m apart on a local equidistant grid centred on the point (correct at the poles too), sample the
  elevation file bilinearly, then compute slope (central differences), its 90th percentile and median, local relief
  (95th minus 5th percentile) and the hypsometric integral, with the same formulas as finder_pipeline.py.
  Difference from build_targets.py: targets are averaged from a 118 m (or 20 m) model; here the global model is sampled at
  about its own resolution. The script measures the named targets of the body both ways and prints the differences.
Surface temperature (optional): nearest-pixel mean of the two Diviner maps over the same 60 x 60 points, (day + night) / 2
  and day - night in degC, exactly like build_targets.py --ts-day/--ts-night. Left empty where less than half the patch has data.
"""
import argparse, datetime, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_site_terrain import MOON_R, MARS_R, PLAUSIBLE, GDAL_ENV, src_path

PATCH_KM, PIX_M = 111.2, 1853.0   # must match build_targets.py
N = int(round(PATCH_KM * 1000 / PIX_M))  # 60
CELL = 1.0
NY, NX = int(180 / CELL), int(360 / CELL)
TS_SRC = ("LRO Diviner Level 4 Global Cumulative Product, bolometric temperature, 10:15-10:45 and 22:15-22:45 local time "
          "(https://pds-geosciences.wustl.edu/lro/lro-l-dlre-4-rdr-v1/lrodlr_1001/data/gcp/)")
FEATS = [("slope_p90", "deg"), ("slope_median", "deg"), ("relief", "m"), ("hypso", "")]
BODY = {  # radius (m) and the targets.json sites used for the check (lat, lon as in build_targets.py)
    "moon": dict(R=MOON_R, name="Moon", check={"tranquility": (0.67, 23.47), "shackleton": (-89.9, 0.0)}),
    "mars": dict(R=MARS_R, name="Mars", check={"jezero": (18.4, 77.5), "olympus": (18.6, -133.8), "valles": (-14.0, -59.0)}),
}
R_BODY = MOON_R  # set in main() from --body


def open_global(path, want_px_m):
    """Return (array, lon_of_col0_centre, dlon, lat_of_row0_centre, dlat) for a global simple-cylindrical file, in degrees."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform
    remote = path.startswith(("http://", "https://"))
    with rasterio.Env(**GDAL_ENV), rasterio.open(src_path(path)) as ds:
        if ds.crs is None:
            sys.exit(f"{os.path.basename(path)} has no map projection.")
        ll = f"+proj=longlat +R={R_BODY} +no_defs"
        b, px = ds.bounds, ds.transform.a
        xm, ym = (b.left + b.right) / 2, (b.bottom + b.top) / 2
        # centres of the first two columns: the file edges of a global map are the same meridian, so measure inwards
        xs, ys = transform(ds.crs, ll, [b.left + px / 2, b.left + 1.5 * px, xm, xm], [ym, ym, b.top, b.bottom])
        step = (xs[1] - xs[0]) % 360
        lon_w, lat_n, lat_s = xs[0] - step / 2, ys[2], ys[3]
        lon_e = lon_w + step * ds.width
        if abs((lon_e - lon_w) - 360) > 1 or abs((lat_n - lat_s) - 180) > 1:
            sys.exit(f"{os.path.basename(path)} covers {lon_e - lon_w:.1f} x {lat_n - lat_s:.1f} degrees; a global "
                     "(360 x 180) simple cylindrical file is needed.")
        native = 2 * math.pi * R_BODY / ds.width
        f = max(1, int(round(want_px_m / native)))
        if remote and f > 1 and not any(o <= f for o in ds.overviews(1)):
            sys.exit(f"  {path} has no overviews, so reading it would download the whole file "
                     f"({ds.width} x {ds.height} px). Download a smaller global file instead (README).")
        h, w = ds.height // f, ds.width // f
        print(f"  elevation file: {ds.width} x {ds.height} px ({native:.0f} m at the equator)"
              + (f", averaged {f}x{f} while reading to {w} x {h}" if f > 1 else ""))
        a = ds.read(1, out_shape=(h, w), resampling=Resampling.average, masked=True).astype("float64").filled(np.nan)
        a = a * (ds.scales[0] or 1) + (ds.offsets[0] or 0)
    a[np.abs(a) > 1e7] = np.nan
    med = np.nanmedian(a)
    if med > 1e6:  # radii, not heights
        a -= R_BODY
        print(f"  values are radii (median {med:.0f} m): converted to heights above {R_BODY:.0f} m")
    dlon, dlat = 360.0 / w, 180.0 / h
    return a, lon_w + dlon / 2, dlon, lat_n - dlat / 2, dlat


def patch_offsets(lat0):
    """Latitude and longitude offsets (deg) of the N x N local equidistant grid around a point at latitude lat0."""
    k = (np.arange(N) - (N - 1) / 2) * PIX_M
    x, y = np.meshgrid(k, -k)  # row 0 = north edge, like the Earth grid
    rho = np.hypot(x, y)
    c = rho / R_BODY
    p0 = math.radians(lat0)
    with np.errstate(invalid="ignore", divide="ignore"):
        lat = np.arcsin(np.cos(c) * math.sin(p0) + np.where(rho > 0, y * np.sin(c) * math.cos(p0) / rho, 0))
        dlon = np.arctan2(x * np.sin(c), rho * math.cos(p0) * np.cos(c) - y * math.sin(p0) * np.sin(c))
    return np.degrees(lat), np.degrees(dlon)


def sample(G, lat, lon, nearest=False):
    a, lon0, dlon, lat0, dlat = G
    h, w = a.shape
    c = ((lon - lon0) / dlon) % w
    r = np.clip((lat0 - lat) / dlat, 0, h - 1)
    if nearest:
        return a[np.clip(np.rint(r).astype(int), 0, h - 1), np.rint(c).astype(int) % w]
    r0 = np.minimum(np.floor(r).astype(int), h - 2); fr = r - r0
    c0 = np.floor(c).astype(int); fc = c - c0; c1 = (c0 + 1) % w; c0 %= w
    return (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0, c1] * (1 - fr) * fc
            + a[r0 + 1, c0] * fr * (1 - fc) + a[r0 + 1, c1] * fr * fc)


def terrain(z):
    """z: (..., N, N) heights. Same formulas as build_targets.measure / finder_pipeline.relief / hypso."""
    gy, gx = np.gradient(z, PIX_M, axis=(-2, -1))
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    flat = lambda v: v.reshape(v.shape[:-2] + (-1,))
    p90 = np.nanpercentile(flat(s), 90, axis=-1)
    med = np.nanmedian(flat(s), axis=-1)
    lo, hi = np.nanpercentile(flat(z), [5, 95], axis=-1)
    rel = hi - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        hyp = np.where(hi > lo, np.clip((np.nanmean(flat(z), axis=-1) - lo) / (hi - lo), 0, 1), np.nan)
    bad = np.isfinite(flat(z)).mean(axis=-1) < 0.9  # same rule as build_targets.py
    return [np.where(bad, np.nan, v) for v in (p90, med, rel, hyp)]


def main():
    global R_BODY
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", choices=sorted(BODY), default="moon")
    ap.add_argument("--dem", required=True, help="global simple-cylindrical elevation file (local path, or COG URL)")
    ap.add_argument("--dem-src", required=True, help='dataset name and page, e.g. "LRO LOLA gridded DEM, 16 px/deg (https://...)"')
    ap.add_argument("--ts-day", help="Moon surface temperature map at about 10:30 local time (prep_diviner.py output, K)")
    ap.add_argument("--ts-night", help="same at about 22:30 local time")
    ap.add_argument("--ts-src", default=TS_SRC)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data"))
    a = ap.parse_args()
    if bool(a.ts_day) != bool(a.ts_night):
        sys.exit("--ts-day and --ts-night go together")
    if a.ts_day and a.body != "moon":
        sys.exit("--ts-day/--ts-night are Diviner (Moon) maps; there is no global Mars temperature map yet")
    B = BODY[a.body]
    R_BODY = B["R"]
    print(f"== {B['name']} grid: {NY} x {NX} points, {PATCH_KM} km patch of {N} x {N} points at {PIX_M:.0f} m around each")
    G = open_global(a.dem, PIX_M)
    lo, hi = np.nanmin(G[0]), np.nanmax(G[0])
    pl = PLAUSIBLE[a.body]
    if lo < pl[0] or hi > pl[1]:
        sys.exit(f"  heights {lo:.0f} to {hi:.0f} m are outside {pl} m: units or scale factor are wrong.")
    print(f"  heights {lo:.0f} to {hi:.0f} m")
    TD = TN = None
    if a.ts_day:
        TD, TN = open_global(a.ts_day, 1.0), open_global(a.ts_night, 1.0)  # want_px_m=1: never average the 0.5 deg maps
    out = {k: np.full((NY, NX), np.nan, "float32") for k, _ in FEATS + [("ts_mean", ""), ("ts_range", "")]}
    lons = -180 + (np.arange(NX) + 0.5) * CELL
    for i in range(NY):
        lat0 = 90 - (i + 0.5) * CELL
        dla, dlo = patch_offsets(lat0)
        LAT = np.broadcast_to(dla, (NX, N, N))
        LON = lons[:, None, None] + dlo[None]
        z = sample(G, LAT, LON)
        for (k, _), v in zip(FEATS, terrain(z)):
            out[k][i] = v
        if TD:
            d, n = sample(TD, LAT, LON, True).reshape(NX, -1), sample(TN, LAT, LON, True).reshape(NX, -1)
            ok = np.isfinite(d) & np.isfinite(n) & (np.abs(d) < 9999) & (np.abs(n) < 9999)
            enough = ok.mean(axis=1) >= 0.5
            dm, nm = np.where(ok, d, 0.0), np.where(ok, n, 0.0)
            cnt = np.maximum(ok.sum(axis=1), 1)
            dmean, nmean = dm.sum(axis=1) / cnt - 273.15, nm.sum(axis=1) / cnt - 273.15
            out["ts_mean"][i] = np.where(enough, (dmean + nmean) / 2, np.nan)
            out["ts_range"][i] = np.where(enough, dmean - nmean, np.nan)
        if i % 20 == 0:
            print(f"  row {i + 1} of {NY} (latitude {lat0:+.1f})")
    # check against targets.json: each named target of this body measured the same way at its exact centre
    try:
        with open(os.path.join(a.out, "targets.json"), encoding="utf-8") as f:
            TT = json.load(f)["targets"]
        print("\n  check at the named targets (this file vs targets.json, which used a finer model averaged to 1853 m):")
        for sid, (la, lo_) in B["check"].items():
            T = TT.get(sid, {})
            dla, dlo = patch_offsets(la)
            v = terrain(sample(G, dla, lo_ + dlo))
            print(f"   {sid}: " + ", ".join(f"{k} {float(x):.3f} vs {T[k]['value']}{(' ' + u) if u else ''}"
                                          for (k, u), x in zip(FEATS, v) if k in T))
    except (OSError, KeyError, ValueError) as e:
        print(f"  (no check against targets.json: {e})")
    today = datetime.date.today().isoformat()
    terr_src = (f"Measured by pipeline/build_body_grid.py from {a.dem_src}: {PATCH_KM} km patch of {N} x {N} points "
                f"{PIX_M:.0f} m apart centred on each 1-degree point, sampled bilinearly. Accessed {today}.")
    ts_src = (f"Measured by pipeline/build_body_grid.py from {a.ts_src}: mean over the same patch; mean = (day + night) / 2, "
              f"swing = day - night. Empty where less than half the patch has data. Accessed {today}.")
    feats = [dict(key=k, unit=u, source=terr_src) for k, u in FEATS]
    if TD:
        feats += [dict(key="ts_mean", unit="degC", source=ts_src), dict(key="ts_range", unit="degC", source=ts_src)]
    os.makedirs(a.out, exist_ok=True)
    for f in feats:
        out[f["key"]].astype("<f4").tofile(os.path.join(a.out, f"{a.body}_{f['key']}.bin"))
        v = out[f["key"]]
        print(f"  {a.body}_{f['key']}.bin: {np.isfinite(v).mean():.0%} of points have a value")
    man = {"schema": "earth-analogs-bodygrid/v0", "body": a.body, "demo": False, "cell_deg": CELL, "ny": NY, "nx": NX,
           "patch_km": PATCH_KM, "pixel_m": PIX_M,
           "layout": "row-major float32 LE, row 0 = 90N, col 0 = 180W, NaN = no data; each value describes the patch "
                     "centred on the cell centre",
           "note": "Generated by pipeline/build_body_grid.py. Do not edit by hand.", "features": feats}
    with open(os.path.join(a.out, f"{a.body}_grid.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {os.path.join(a.out, a.body + '_grid.json')} and {len(feats)} .bin files")


if __name__ == "__main__":
    main()
