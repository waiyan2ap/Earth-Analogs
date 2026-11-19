"""Measure the Moon/Mars target values for "Find on Earth" from real elevation data, and write docs/data/targets.json.

  python pipeline/build_targets.py                 # all sites
  python pipeline/build_targets.py --site jezero   # one site (the others in targets.json are kept)
  python pipeline/build_targets.py --site jezero --dem C:/path/local.tif   # use a file you downloaded
  python pipeline/build_targets.py --site tranquility --ts-day D.tif --ts-night N.tif --ts-unit K --ts-src "NAME, HOURS (URL)"
                                                   # surface temperature (ts_mean, ts_range) from two maps you downloaded

Why this script exists: the Earth grid (build_grid.py) measures slope on ETOPO 2022 at 60 arc-seconds (about 1.85 km
pixels) and summarises it per 1-degree cell (about 111 km). Slope depends strongly on pixel size, so the Moon and Mars
must be measured the SAME way or the comparison is meaningless. For each site this script:
  1. reads a 111 km x 111 km patch of the planetary elevation model around the site, at full resolution;
  2. averages it down to 1853 m pixels (60 x 60);
  3. computes slope with the same central-difference rule as finder_pipeline.slope_deg;
  4. takes the 90th percentile and the median, like the Earth grid's slope_p90 and slope_median;
  5. measures local relief and the hypsometric integral of the same 60 x 60 elevation pixels, with the same
     functions (finder_pipeline.relief / hypso) the Earth grid uses for its relief and hypso features.

Only terrain and landform are written. Thermal targets (t_mean, t_range) are NOT written: the Earth grid uses 2 m air temperature from
WorldClim, and there is no like-for-like sourced value for the Moon or Mars sites yet. Features with no target are
simply not used by the app.

Needs: pip install rasterio numpy. Reads only the patch it needs over the internet (no big downloads), except the
lunar south pole file, which is 20 m per pixel: that patch is about 125 MB and can take a few minutes.
"""
import argparse, datetime, json, math, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finder_pipeline as fp
from build_site_terrain import MOON_R, MARS_R, PLAUSIBLE, GDAL_ENV, block_mean, read_window, src_path, why

PATCH_KM = 111.2   # one degree of latitude on Earth: the size of one Earth grid cell
PIX_M = 1853.0     # 60 arc-seconds on Earth: the pixel size of the Earth elevation model (ETOPO 2022)
N = int(round(PATCH_KM * 1000 / PIX_M))  # 60

LOLA_POLE = dict(url="https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF",
                 name="NASA PGDA product 90: LOLA south pole DEM, 20 m/px (Barker et al. 2023)",
                 page="https://pgda.gsfc.nasa.gov/products/90")
LOLA_GLOBAL = dict(url="https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif",
                   name="USGS Moon LRO LOLA DEM 118 m (global)",
                   page="https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m")
MARS_BLEND = dict(url="https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif",
                  name="USGS Mars MOLA-HRSC Blended DEM 200 m v2 (Fergason et al. 2018)",
                  page="https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m")

# Site centres are the site markers in docs/index.html (same as the dataset), except Tranquility (NASA NSSDC Apollo 11 page).
SITES = {
    "shackleton": dict(body="moon", lat=-89.9, lon=0.0, radius=MOON_R, dem=LOLA_POLE),
    "tranquility": dict(body="moon", lat=0.67, lon=23.47, radius=MOON_R, dem=LOLA_GLOBAL),
    "jezero": dict(body="mars", lat=18.4, lon=77.5, radius=MARS_R, dem=MARS_BLEND),
    "olympus": dict(body="mars", lat=18.6, lon=-133.8, radius=MARS_R, dem=MARS_BLEND),
    "valles": dict(body="mars", lat=-14.0, lon=-59.0, radius=MARS_R, dem=MARS_BLEND),
}


def read_strips(path, win, sc, off, strips=16):
    """Read a window in horizontal strips, each retried on a fresh connection, so one dropped request does not lose everything."""
    from rasterio.windows import Window
    h, w = int(win.height), int(win.width)
    out = np.full((h, w), np.nan, "float32")
    edges = np.linspace(0, h, min(strips, h) + 1).astype(int)
    for s in range(len(edges) - 1):
        r0, r1 = edges[s], edges[s + 1]
        a = read_window(path, Window(win.col_off, win.row_off + r0, w, r1 - r0))
        out[r0:r1] = a.astype("float32").filled(np.nan) * sc + off
        print(f"    strip {s + 1} of {len(edges) - 1} read")
    return out


def read_patch(path, lat, lon, radius):
    """N x N elevation array (metres) with PIX_M pixels, centred on lat/lon."""
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import from_bounds
    ll = f"+proj=longlat +R={radius} +no_defs"
    half = PATCH_KM * 500.0
    with rasterio.open(path) as ds:
        p4 = ds.crs.to_proj4() if ds.crs else ""
        print(f"    file: {ds.width} x {ds.height} px, crs: {p4 or 'none'}, dtype {ds.dtypes[0]}, nodata {ds.nodata}")
        if "+proj=stere" in p4:  # polar stereographic: metres, true scale at the pole
            (x,), (y,) = transform(ll, ds.crs, [lon], [lat])
            hx = hy = half
        else:  # cylindrical or geographic: measure the box along the ground; try both longitude conventions
            dlat = math.degrees(half / radius)
            dlon = math.degrees(half / (radius * math.cos(math.radians(lat))))
            for lo in (lon, lon + 360, lon - 360):
                xs, ys = transform(ll, ds.crs, [lo - dlon, lo + dlon, lo, lo], [lat, lat, lat - dlat, lat + dlat])
                x, y, hx, hy = (xs[0] + xs[1]) / 2, (ys[2] + ys[3]) / 2, abs(xs[1] - xs[0]) / 2, abs(ys[3] - ys[2]) / 2
                if ds.bounds.left <= x - hx and x + hx <= ds.bounds.right:
                    break
            else:
                raise SystemExit("    the patch crosses the edge of the file (longitude wrap). Use a site away from the map edge.")
        if not (ds.bounds.bottom <= y - hy and y + hy <= ds.bounds.top):
            raise SystemExit("    the patch is outside the file. Wrong coordinates, or the file does not cover this site.")
        win = from_bounds(x - hx, y - hy, x + hx, y + hy, ds.transform).round_offsets().round_lengths()
        print(f"    reading a {int(win.width)} x {int(win.height)} px window "
              f"(about {win.width * win.height * np.dtype(ds.dtypes[0]).itemsize / 1e6:.0f} MB)")
        sc, off = ds.scales[0] or 1, ds.offsets[0] or 0
    a = read_strips(path, win, sc, off)
    return block_mean(a.astype("float64"), N)


def slope_deg(z, pix_m):
    """Same rule as finder_pipeline.slope_deg (central differences, one-sided at the edges), on square metric pixels."""
    gy, gx = np.gradient(z, pix_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def measure(site_id, cfg, dem_override=None):
    print(f"\n== {site_id}: {PATCH_KM} km patch at {PIX_M:.0f} m pixels ({N} x {N})")
    print("  elevation:", dem_override or cfg["dem"]["url"])
    z = read_patch(src_path(dem_override or cfg["dem"]["url"]), cfg["lat"], cfg["lon"], cfg["radius"])
    ok = np.isfinite(z)
    if ok.mean() < 0.9:
        raise SystemExit(f"  only {ok.mean():.0%} of the patch has data: not enough to measure slope fairly.")
    lo, hi = np.nanmin(z), np.nanmax(z)
    pl = PLAUSIBLE[cfg["body"]]
    if lo < pl[0] or hi > pl[1]:
        raise SystemExit(f"  elevations {lo:.0f} to {hi:.0f} m are outside {pl} m: units or scale factor are wrong.")
    s = slope_deg(z, PIX_M)
    p90, med = float(np.nanpercentile(s, 90)), float(np.nanmedian(s))
    print(f"  elevation {lo:.0f} to {hi:.0f} m, {ok.mean():.0%} cells with data")
    rel, hyp = fp.relief(z), fp.hypso(z)
    print(f"  slope at {PIX_M:.0f} m pixels: 90th percentile {p90:.2f} deg, median {med:.2f} deg")
    print(f"  local relief {rel:.0f} m, hypsometric integral {hyp:.3f}")
    src = (f"Measured by pipeline/build_targets.py from {cfg['dem']['name']} ({cfg['dem']['page']}): "
           f"{PATCH_KM} km patch centred {abs(cfg['lat'])}°{'N' if cfg['lat'] >= 0 else 'S'}, "
           f"{abs(cfg['lon'])}°{'E' if cfg['lon'] >= 0 else 'W'}, averaged to {PIX_M:.0f} m pixels to match the Earth "
           f"grid (ETOPO 2022, 60 arc-seconds). Accessed {datetime.date.today().isoformat()}."
           + (" Local file used: " + os.path.basename(dem_override) + "." if dem_override else ""))
    out = {"slope_p90": {"value": round(p90, 2), "source": src}, "slope_median": {"value": round(med, 2), "source": src},
           "relief": {"value": round(rel, 0), "source": src}}
    if math.isfinite(hyp):  # a perfectly flat patch has no shape value; leave it out rather than invent one
        out["hypso"] = {"value": round(hyp, 3), "source": src}
    return out


def patch_mean(path, lat, lon, radius, label, unit):
    """Mean of a (usually coarse) temperature map over the PATCH_KM box around lat/lon, in degC.
    Works with geographic or simple cylindrical maps in -180..180 or 0..360 longitude, and polar stereographic maps.
    If the box is smaller than one pixel, the pixel under the site is used."""
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import from_bounds, Window
    ll = f"+proj=longlat +R={radius} +no_defs"
    half = PATCH_KM * 500.0
    with rasterio.open(path) as ds:
        print(f"    {label}: {os.path.basename(path)}, {ds.width} x {ds.height} px, crs {ds.crs.to_proj4() if ds.crs else 'none'}")
        if ds.crs is None:
            raise SystemExit(f"    {label}: the file has no map projection. Convert it to GeoTIFF with gdal_translate first.")
        p4 = ds.crs.to_proj4()
        if "+proj=stere" in p4:
            (x,), (y,) = transform(ll, ds.crs, [lon], [lat]); hx = hy = half
        else:
            dlat = math.degrees(half / radius); dlon = math.degrees(half / (radius * max(math.cos(math.radians(lat)), 0.01)))
            for lo in (lon, lon + 360, lon - 360):
                xs, ys = transform(ll, ds.crs, [lo - dlon, lo + dlon, lo, lo], [lat, lat, max(lat - dlat, -90), min(lat + dlat, 90)])
                x, y, hx, hy = (xs[0] + xs[1]) / 2, (ys[2] + ys[3]) / 2, abs(xs[1] - xs[0]) / 2, abs(ys[3] - ys[2]) / 2
                if ds.bounds.left <= x <= ds.bounds.right:
                    break
            else:
                raise SystemExit(f"    {label}: the site is outside the map.")
        win = from_bounds(x - hx, y - hy, x + hx, y + hy, ds.transform).round_offsets().round_lengths()
        win = win.intersection(Window(0, 0, ds.width, ds.height))
        if win.width < 1 or win.height < 1:
            r, c = ds.index(x, y); win = Window(c, r, 1, 1)
        a = ds.read(1, window=win, masked=True).astype("float64").filled(np.nan) * (ds.scales[0] or 1) + (ds.offsets[0] or 0)
    a[np.abs(a) >= 9999] = np.nan
    if not np.isfinite(a).any():
        raise SystemExit(f"    {label}: no valid values around the site.")
    v = float(np.nanmean(a))
    if unit == "K":  # stated by the user: lunar nights (about 100 K) look like degC to any automatic guess
        v -= 273.15
    if not -273 < v < 200:
        raise SystemExit(f"    {label}: {v:.1f} degC is not a plausible surface temperature; check units and scale factor.")
    print(f"    {label}: mean of {int(np.isfinite(a).sum())} pixels = {v:.1f} degC")
    return v


def measure_thermal(site_id, cfg, day, night, src, unit):
    """Like-for-like with the Earth grid's ts_mean / ts_range: (day + night) / 2 and day - night, from two maps of the
    surface temperature at a daytime and a night-time local hour. Say which hours in --ts-src."""
    print(f"\n== {site_id}: surface temperature over a {PATCH_KM} km patch")
    d = patch_mean(src_path(day), cfg["lat"], cfg["lon"], cfg["radius"], "day", unit)
    n = patch_mean(src_path(night), cfg["lat"], cfg["lon"], cfg["radius"], "night", unit)
    if d < n:
        print("  warning: day is colder than night here. Check that --ts-day and --ts-night are not swapped.")
    text = (f"Measured by pipeline/build_targets.py from {src}: mean over a {PATCH_KM} km patch centred "
            f"{abs(cfg['lat'])}°{'N' if cfg['lat'] >= 0 else 'S'}, {abs(cfg['lon'])}°{'E' if cfg['lon'] >= 0 else 'W'}; "
            f"mean = (day + night) / 2, swing = day - night. Files: {os.path.basename(day)}, {os.path.basename(night)}. "
            f"Accessed {datetime.date.today().isoformat()}.")
    print(f"  surface temperature: day {d:.1f}, night {n:.1f}, mean {(d + n) / 2:.1f}, swing {d - n:.1f} degC")
    return {"ts_mean": {"value": round((d + n) / 2, 1), "source": text}, "ts_range": {"value": round(d - n, 1), "source": text}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=sorted(SITES), help="one site only (default: all)")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data", "targets.json"))
    ap.add_argument("--dem", help="local elevation file to use instead of the online one (needs --site)")
    ap.add_argument("--debug", action="store_true", help="print GDAL's network messages (for troubleshooting)")
    ap.add_argument("--ts-day", help="surface temperature map at a daytime local hour (needs --site, --ts-night, --ts-src)")
    ap.add_argument("--ts-night", help="surface temperature map at a night-time local hour")
    ap.add_argument("--ts-unit", choices=["K", "C"], help="unit of the values in the two maps: K (kelvin) or C (degC)")
    ap.add_argument("--ts-src", help='dataset name, local hours and page, e.g. "LRO Diviner ..., 10:30 and 22:30 local time (https://...)"')
    a = ap.parse_args()
    if a.dem and not a.site:
        sys.exit("--dem needs --site")
    thermal = bool(a.ts_day or a.ts_night)
    if thermal and not (a.site and a.ts_day and a.ts_night and a.ts_src and a.ts_unit):
        sys.exit("surface temperature needs --site, --ts-day, --ts-night, --ts-unit and --ts-src together")
    old = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            prev = json.load(f)
        if not prev.get("demo"):  # keep real values measured earlier; never keep demo placeholders
            old = prev.get("targets", {})
        else:
            print("existing targets.json is marked demo: its placeholder values are dropped")
    import rasterio
    env = dict(GDAL_ENV)
    if a.debug:
        env.update(CPL_DEBUG="ON", CPL_CURL_VERBOSE="YES")
    done, failed = [], []
    with rasterio.Env(**env):
        for sid in ([a.site] if a.site else SITES):
            try:
                new = measure_thermal(sid, SITES[sid], a.ts_day, a.ts_night, a.ts_src, a.ts_unit) if thermal else measure(sid, SITES[sid], a.dem)
                old[sid] = {**old.get(sid, {}), **new}  # keep the other features measured earlier
                done.append(sid)
            except SystemExit as e:
                print(f"  FAILED {sid}: {e}")
                failed.append(sid)
            except Exception as e:  # network or file errors: report and go on with the next site
                print(f"  FAILED {sid}: {type(e).__name__}: {why(e)}")
                failed.append(sid)
    if not old:
        sys.exit("\nnothing measured, targets.json not changed")
    out = {"schema": "earth-analogs-targets/v0", "demo": False, "patch_km": PATCH_KM, "pixel_m": PIX_M,
           "note": "Generated by pipeline/build_targets.py. Do not edit by hand. Terrain (slope), landform (relief, "
                   "hypsometric integral) and, where measured with --ts-day/--ts-night, surface temperature.",
           "targets": old}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {a.out}: measured {', '.join(done) or 'none'}"
          + (f"; FAILED {', '.join(failed)} (run again later with --site NAME)" if failed else "")
          + f"; sites in file: {', '.join(old)}")


if __name__ == "__main__":
    main()
