"""Cut a small elevation patch (and sunlight map where one exists) around each Moon/Mars target for the Base plan tab.

  python pipeline/build_site_terrain.py                  # all sites, writes docs/data/siting/<site>.json
  python pipeline/build_site_terrain.py --site jezero    # one site
  python pipeline/build_site_terrain.py --site jezero --dem C:/path/local.tif   # use a file you downloaded instead

It reads ONLY the small window it needs straight from NASA/USGS servers (GDAL /vsicurl/), so nothing big is downloaded:
a 16-20 km patch is a few MB at most. Needs internet + `pip install rasterio numpy` (the same as build_grid.py).
Generated files in docs/data are never hand-edited: change this script and run it again.

Sources (pages checked 2026-11-10):
  Shackleton  elevation  NASA PGDA product 90, LOLA 20 m/px south pole DEM (COG, heights in metres)
              sunlight   NASA PGDA product 69, average solar illumination 60 m/px, 18.6-year average (COG)
  Tranquility elevation  USGS Moon LRO LOLA DEM 118 m (global, int16, scale 0.5 m per DN)
  Jezero      elevation  USGS Mars MGS MOLA - MEX HRSC Blended DEM Global 200 m v2 (interim, 11 GB file)
  Olympus     elevation  same Mars DEM (summit caldera area)
  Valles      elevation  same Mars DEM
Site centres: Tranquility = Apollo 11 landing site 0.67 N, 23.47 E (NASA NSSDC Apollo 11 page). Shackleton, Jezero,
Olympus and Valles use the index.html marker coordinates, not yet checked against the USGS planetary names gazetteer.
"""
import argparse, base64, datetime, json, math, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MOON_R, MARS_R = 1737400.0, 3396190.0

SITES = {
    "shackleton": dict(
        body="moon", lat=-89.9, lon=0.0, size_km=16, N=400, radius=MOON_R,
        dem="https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF",
        dem_name="NASA PGDA product 90: LOLA south pole DEM, 20 m/px (Barker et al. 2023)",
        dem_page="https://pgda.gsfc.nasa.gov/products/90", dem_res_m=20,
        sun=["https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF",
             "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_COG.TIF"],
        sun_name="NASA PGDA product 69: average solar illumination, 60 m/px, 18.6-year average (Mazarico et al. 2011)",
        sun_page="https://pgda.gsfc.nasa.gov/products/69",
        earth=["https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF"],
        earth_name="NASA PGDA product 69: average Earth visibility, 60 m/px, 18.6-year average (Mazarico et al. 2011)"),
    "tranquility": dict(
        body="moon", lat=0.67, lon=23.47, size_km=16, N=128, radius=MOON_R,  # Apollo 11 site, NASA NSSDC Apollo 11 page
        dem="https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif",
        dem_name="USGS Moon LRO LOLA DEM 118 m (global)",
        dem_page="https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m", dem_res_m=118),
    "jezero": dict(
        body="mars", lat=18.4, lon=77.5, size_km=20, N=100, radius=MARS_R,
        dem="https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif",
        dem_name="USGS Mars MOLA-HRSC Blended DEM 200 m v2 (interim, Fergason et al. 2018)",
        dem_page="https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m", dem_res_m=200),
    "olympus": dict(
        body="mars", lat=18.6, lon=-133.8, size_km=20, N=100, radius=MARS_R,
        dem="https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif",
        dem_name="USGS Mars MOLA-HRSC Blended DEM 200 m v2 (interim, Fergason et al. 2018)",
        dem_page="https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m", dem_res_m=200),
    "valles": dict(
        body="mars", lat=-14.0, lon=-59.0, size_km=20, N=100, radius=MARS_R,
        dem="https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif",
        dem_name="USGS Mars MOLA-HRSC Blended DEM 200 m v2 (interim, Fergason et al. 2018)",
        dem_page="https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m", dem_res_m=200),
}
PLAUSIBLE = {"moon": (-10000, 11000), "mars": (-9000, 22500)}  # metres; outside this means wrong units or scale


def src_path(p):
    return p if os.path.exists(p) else "/vsicurl/" + p


GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
                GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3", GDAL_HTTP_TIMEOUT="120",
                GDAL_HTTP_VERSION="1.1",          # HTTP/2 streams get reset by some servers ("Read failed"); 1.1 is steadier
                GDAL_HTTP_MULTIRANGE="SINGLE",    # some servers refuse several byte ranges in one request
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", CPL_VSIL_CURL_CHUNK_SIZE="1048576",
                CPL_VSIL_CURL_NON_CACHED="/vsicurl/")  # do not remember a failed download: retry really asks the server again


def why(e):
    """The real reason behind rasterio's generic 'Read failed' (it hides it in the exception chain)."""
    parts, seen = [], set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        t = str(e).strip()
        if t and t not in parts:
            parts.append(t)
        e = e.__cause__ or e.__context__
    return " <- ".join(parts)


class NotPlain(Exception):
    """The file is tiled or compressed, so the direct byte-range reader cannot be used."""


def fetch(url, off, n, tries=6):
    """Bytes off..off+n-1 of a web file, retried until exactly n bytes arrive (servers sometimes cut a reply short)."""
    import urllib.request
    last = None
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={off}-{off + n - 1}", "User-Agent": "earth-analogs-pipeline"})
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status != 206:
                    raise NotPlain(f"server ignored the byte range (HTTP {r.status})")
                b = r.read()
            if len(b) == n:
                return b
            last = IOError(f"got {len(b)} of {n} bytes")
        except NotPlain:
            raise
        except Exception as e:
            last = e
        time.sleep(1.5 * (t + 1))
    raise IOError(f"bytes {off}-{off + n - 1}: {last}")


def read_window_ranges(url, win):
    """Read a window of an uncompressed, strip-organised GeoTIFF by asking the server for only the bytes of each row
    inside the window (a few hundred bytes per row). GDAL instead downloads every whole row strip it touches
    (213 KB per row for the 11 GB Mars DEM), and those long replies are what the server keeps cutting short.
    Raises NotPlain for tiled or compressed files, which GDAL reads fine."""
    import struct
    from concurrent.futures import ThreadPoolExecutor
    h = fetch(url, 0, 16)
    bo = {b"II": "<", b"MM": ">"}.get(h[:2])
    if bo is None:
        raise NotPlain("not a TIFF")
    ver = struct.unpack(bo + "H", h[2:4])[0]
    big = ver == 43
    if ver not in (42, 43):
        raise NotPlain("not a TIFF")
    ifd = struct.unpack(bo + ("Q" if big else "I"), h[8:16] if big else h[4:8])[0]
    csz, esz = (8, 20) if big else (2, 12)
    cnt = struct.unpack(bo + ("Q" if big else "H"), fetch(url, ifd, csz))[0]
    raw = fetch(url, ifd + csz, cnt * esz)
    TS = {1: "B", 3: "H", 4: "I", 16: "Q"}  # TIFF type -> struct code
    tags = {}
    for k in range(cnt):
        e = raw[k * esz:(k + 1) * esz]
        tag, typ = struct.unpack(bo + "HH", e[:4])
        n = struct.unpack(bo + ("Q" if big else "I"), e[4:12] if big else e[4:8])[0]
        vb = e[12:20] if big else e[8:12]
        if typ in TS:
            sz = struct.calcsize(TS[typ])
            if n * sz <= len(vb):
                v = struct.unpack(bo + TS[typ] * n, vb[:n * sz])
                tags[tag] = (typ, n, None, v)
            else:  # value list stored elsewhere: keep where it is, read only what we need
                tags[tag] = (typ, n, struct.unpack(bo + ("Q" if big else "I"), vb)[0], None)
    get1 = lambda t, d=None: tags[t][3][0] if t in tags and tags[t][3] else d
    if 322 in tags or get1(259, 1) != 1 or get1(277, 1) != 1 or 273 not in tags:
        raise NotPlain("tiled, compressed or multi-band")
    W, H, bits, fmt = get1(256), get1(257), get1(258), get1(339, 1)
    rps = min(get1(278, H), H)
    dt = np.dtype(bo + {(1, 8): "u1", (1, 16): "u2", (1, 32): "u4", (2, 8): "i1", (2, 16): "i2", (2, 32): "i4",
                        (3, 32): "f4", (3, 64): "f8"}[(fmt, bits)])
    c0, r0, nc, nr = int(win.col_off), int(win.row_off), int(win.width), int(win.height)
    if c0 < 0 or r0 < 0 or c0 + nc > W or r0 + nr > H:
        raise NotPlain("window runs off the edge of the map")
    typ, n, at, v = tags[273]
    s0, s1 = r0 // rps, (r0 + nr - 1) // rps
    if v is None:  # read just the strip offsets this window needs
        sz = struct.calcsize(TS[typ])
        v = dict(zip(range(s0, s1 + 1), struct.unpack(bo + TS[typ] * (s1 - s0 + 1), fetch(url, at + s0 * sz, (s1 - s0 + 1) * sz))))
    else:
        v = dict(enumerate(v))
    def row(r):
        s = r // rps
        return np.frombuffer(fetch(url, v[s] + ((r - s * rps) * W + c0) * dt.itemsize, nc * dt.itemsize), dt)
    with ThreadPoolExecutor(6) as ex:
        a = np.stack(list(ex.map(row, range(r0, r0 + nr))))
    return a


def read_window(path, win, tries=5, nodata=None):
    """Read one window, reopening the file on every retry (a failed connection is not reused). Returns a masked array.
    Web files that are plain (uncompressed, in row strips) are read row by row with byte ranges instead (see above)."""
    import rasterio
    if path.startswith("/vsicurl/"):
        try:
            a = read_window_ranges(path[len("/vsicurl/"):], win)
            print(f"    read {a.shape[1]} x {a.shape[0]} px directly by byte range")
            return np.ma.masked_equal(a, nodata) if nodata is not None and np.isfinite(nodata) else np.ma.masked_invalid(a.astype("float64"))
        except NotPlain as e:
            print(f"    byte-range reader not usable ({e}); reading with GDAL")
    last = None
    for attempt in range(tries):
        try:
            with rasterio.open(path) as ds:
                return ds.read(1, window=win, masked=True)
        except Exception as e:
            last = e
            print(f"    read attempt {attempt + 1} of {tries} failed: {why(e)}")
            time.sleep(4 * (attempt + 1))
    raise last


def read_patch(path, lat, lon, half_m, N, radius):
    """Return (N x N float array, up_label, metres per output pixel) centred on lat/lon, half_m metres each way."""
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import from_bounds
    ll = f"+proj=longlat +R={radius} +no_defs"
    with rasterio.open(path) as ds:
        p4 = ds.crs.to_proj4() if ds.crs else ""
        print(f"    file: {ds.width} x {ds.height} px, crs: {p4 or 'none'}, dtype {ds.dtypes[0]}, "
              f"nodata {ds.nodata}, scale {ds.scales[0]}, offset {ds.offsets[0]}")
        (x,), (y,) = transform(ll, ds.crs, [lon], [lat])
        if "+proj=stere" in p4:  # polar stereographic: metres, true scale at the pole
            hx = hy = half_m
            (_,), (ulat,) = transform(ds.crs, ll, [x], [y + 1000])
            (ulon,), _ = transform(ds.crs, ll, [x], [y + 1000])
            up = f"toward {ulon % 360:.0f}°E longitude (polar map)"
        else:  # cylindrical or geographic: measure the box by moving along the ground
            dlat = math.degrees(half_m / radius)
            dlon = math.degrees(half_m / (radius * max(math.cos(math.radians(lat)), 0.05)))
            xs, ys = transform(ll, ds.crs, [lon - dlon, lon + dlon, lon, lon], [lat, lat, lat - dlat, lat + dlat])
            hx, hy = abs(xs[1] - xs[0]) / 2, abs(ys[3] - ys[2]) / 2
            up = "north"
        win = from_bounds(x - hx, y - hy, x + hx, y + hy, ds.transform).round_offsets().round_lengths()
        print(f"    reading a {int(win.width)} x {int(win.height)} px window (about {win.width * win.height * np.dtype(ds.dtypes[0]).itemsize / 1e6:.1f} MB)")
        sc, off, nd = ds.scales[0] or 1, ds.offsets[0] or 0, ds.nodata
    a = read_window(path, win, nodata=nd).astype("float64").filled(np.nan) * sc + off  # servers sometimes drop a request: retried inside
    return block_mean(a, N), up, 2 * half_m / N


def block_mean(a, N):
    """Shrink a full-resolution window to N x N cells by averaging the pixels inside each cell (ignores no-data)."""
    ri, ci = np.linspace(0, a.shape[0], N + 1).astype(int), np.linspace(0, a.shape[1], N + 1).astype(int)
    out = np.full((N, N), np.nan)
    for i in range(N):
        for j in range(N):
            b = a[ri[i]:max(ri[i + 1], ri[i] + 1), ci[j]:max(ci[j + 1], ci[j] + 1)]
            if np.isfinite(b).any():
                out[i, j] = np.nanmean(b)
    return out


def b64(arr, dtype):
    return base64.b64encode(np.ascontiguousarray(arr, dtype=dtype).astype(np.dtype(dtype).newbyteorder("<")).tobytes()).decode()


def build(site_id, cfg, out_dir, dem_override=None, sun_override=None):
    print(f"\n== {site_id}: {cfg['size_km']} km patch, {cfg['N']} x {cfg['N']} cells")
    half = cfg["size_km"] * 500.0
    print("  elevation:", dem_override or cfg["dem"])
    z, up, cell = read_patch(src_path(dem_override or cfg["dem"]), cfg["lat"], cfg["lon"], half, cfg["N"], cfg["radius"])
    ok = np.isfinite(z)
    if ok.mean() < 0.5:
        raise SystemExit(f"  only {ok.mean():.0%} of the patch has data. Wrong coordinates, or the file does not cover this site.")
    lo, hi = np.nanmin(z), np.nanmax(z)
    print(f"  elevation range {lo:.0f} to {hi:.0f} m, {ok.mean():.0%} cells with data")
    pl = PLAUSIBLE[cfg["body"]]
    if lo < pl[0] or hi > pl[1]:
        raise SystemExit(f"  elevations outside {pl} m: units or scale factor are wrong. Check the dataset page.")
    out = dict(schema="earth-analogs-siteterrain/v0", id=site_id, body=cfg["body"], N=cfg["N"], cell_m=round(cell, 2),
               km=cfg["size_km"], center=dict(lat=cfg["lat"], lon=cfg["lon"]), up=up,
               layout="row-major, row 0 = top of map, little-endian; h = int16 metres (-32768 = no data)",
               accessed=datetime.date.today().isoformat(),
               dem=dict(name=cfg["dem_name"], url=cfg["dem_page"], file=os.path.basename(cfg["dem"]), res_m=cfg["dem_res_m"]),
               h=b64(np.where(ok, np.round(z), -32768), "<i2"))
    # Optional percentage maps (sunlight, Earth visibility). If one fails, the elevation file is still written.
    for key, urls, name in (("sun", [sun_override] if sun_override else cfg.get("sun", []), cfg.get("sun_name")),
                            ("earth", cfg.get("earth", []), cfg.get("earth_name"))):
        for url in urls:
            print(f"  {key}:", url)
            try:
                s, _, _ = read_patch(src_path(url), cfg["lat"], cfg["lon"], half, cfg["N"], cfg["radius"])
            except Exception as e:
                print(f"    not read ({type(e).__name__}: {e})")
                continue
            mx = np.nanmax(s)
            if mx <= 1.0001:
                s = s * 100
            elif mx > 100.01:
                print(f"    values go up to {mx}: not a fraction or a percent. Check the PDS label scale factor "
                      "(product 69 page) before using this file. Skipped.")
                break
            print(f"  {key} range {np.nanmin(s):.1f} to {np.nanmax(s):.1f} % of time")
            out[key] = b64(np.where(np.isfinite(s), np.clip(np.round(s), 0, 100), 255), "u1")
            out[key + "_src"] = dict(name=name, url=cfg["sun_page"], file=os.path.basename(url), res_m=60)
            break
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{site_id}.json")
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"  wrote {path} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=sorted(SITES), help="one site only (default: all)")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data", "siting"))
    ap.add_argument("--dem", help="local elevation file to use instead of the online one (needs --site)")
    ap.add_argument("--sun", help="local sunlight file to use instead of the online one (needs --site)")
    ap.add_argument("--km", type=float, help="patch width in km (needs --site), e.g. 8 for a closer, sharper view")
    ap.add_argument("--cell", type=float, help="cell size in metres (needs --site). Below the dataset's own pixel size adds no detail")
    ap.add_argument("--debug", action="store_true", help="print GDAL's network messages (for troubleshooting)")
    a = ap.parse_args()
    if (a.dem or a.sun or a.km or a.cell) and not a.site:
        sys.exit("--dem/--sun/--km/--cell need --site")
    if a.site and (a.km or a.cell):
        c = SITES[a.site]
        c["size_km"] = a.km or c["size_km"]
        c["N"] = int(round(c["size_km"] * 1000 / (a.cell or c["size_km"] * 1000 / c["N"])))
        if c["N"] > 600:
            sys.exit(f"{c['N']} x {c['N']} cells is too many for the browser; use a smaller --km or a larger --cell")
        if c["size_km"] * 1000 / c["N"] < c["dem_res_m"]:
            print(f"note: cells smaller than the dataset's {c['dem_res_m']} m pixels add no real detail")
    import rasterio
    env = dict(GDAL_ENV)
    if a.debug:
        env.update(CPL_DEBUG="ON", CPL_CURL_VERBOSE="YES")
    with rasterio.Env(**env):
        for sid in ([a.site] if a.site else SITES):
            try:
                build(sid, SITES[sid], a.out, a.dem, a.sun)
            except SystemExit as e:
                print(f"  FAILED {sid}: {e}")
            except Exception as e:  # network or file errors: report and go on with the next site
                print(f"  FAILED {sid}: {type(e).__name__}: {why(e)}")
