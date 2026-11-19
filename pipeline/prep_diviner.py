"""Turn LRO Diviner Global Cumulative Product tables into two Moon surface temperature maps for build_targets.py.

  python pipeline/prep_diviner.py --tab "pipeline/raw/diviner/global_cumul_avg_cyl_*_002.tab"

Input: Diviner Level 4 Global Cumulative Product (GCP), PDS data set LRO-L-DLRE-5-PRP / urn:nasa:pds:lro_diviner_derived1,
  https://pds-geosciences.wustl.edu/lro/lro-l-dlre-4-rdr-v1/lrodlr_1001/data/gcp/
  Each .tab file is one 10-degree latitude band: one row per 0.5 x 0.5 degree bin and 0.25 hour of local time, nadir
  observations 2009-07-05 to 2015-04-01. Columns (from the .xml label): Center_Longitude, Center_Latitude, Local_Time (hr),
  t3..t9 (channel brightness temperatures, K), tbol (bolometric brightness temperature, K). -9999 = no observations.
  Download only the bands your sites need (Tranquility: 10s00s and 00n10n; Shackleton: 90s80s).

Output (pipeline/raw, never committed): moon_ts_day.tif and moon_ts_night.tif, bolometric temperature in KELVIN on a
global 0.5 degree lunar latitude/longitude grid (Moon radius 1737.4 km). Empty outside the bands you downloaded.
  day   = mean of the two 15-minute bins either side of 10:30 local time (10:15-10:45)
  night = mean of the two bins either side of 22:30 local time (22:15-22:45)
These are the same local hours as the Earth map (MODIS Terra crosses at about 10:30 and 22:30), so the comparison is like for like.
Then: python pipeline/build_targets.py --site tranquility --ts-day pipeline/raw/moon_ts_day.tif --ts-night pipeline/raw/moon_ts_night.tif --ts-unit K --ts-src "..."
"""
import argparse, glob, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MOON_R = 1737400.0
SLOTS = {"day": (10.25, 10.75), "night": (22.25, 22.75)}  # local-time window in hours, centred on the MODIS overpass times


def read_tab(path):
    """Return lon, lat, local time, tbol columns. Fixed-width ASCII with an optional header line; commas are tolerated."""
    rows = []
    with open(path, encoding="ascii", errors="replace") as f:
        for line in f:
            p = line.replace(",", " ").split()
            if len(p) != 11:
                continue
            try:
                rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[10])))
            except ValueError:
                continue  # the header line
    if not rows:
        sys.exit(f"{os.path.basename(path)}: no data rows found. Is this a Diviner GCP .tab file?")
    return np.array(rows, dtype="float64").T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tab", required=True, help='Diviner GCP tables, e.g. "pipeline/raw/diviner/global_cumul_avg_cyl_*_002.tab" (quotes needed)')
    ap.add_argument("--out", default=os.path.join(HERE, "raw"))
    a = ap.parse_args()
    paths = sorted(glob.glob(a.tab))
    if not paths:
        sys.exit(f"no files match {a.tab}")
    import rasterio
    from rasterio.transform import from_origin
    ny, nx = 360, 720
    acc = {k: (np.zeros((ny, nx)), np.zeros((ny, nx))) for k in SLOTS}
    for p in paths:
        lon, lat, lt, tb = read_tab(p)
        if np.nanmax(np.abs(lat)) > 90 or np.nanmax(np.abs(lon)) > 360 or np.nanmax(lt) > 24:
            sys.exit(f"{os.path.basename(p)}: columns are not longitude, latitude, local time as expected.")
        lon = np.where(lon > 180, lon - 360, lon)
        i = np.clip(((90 - lat) / 0.5).astype(int), 0, ny - 1)
        j = np.clip(((lon + 180) / 0.5).astype(int), 0, nx - 1)
        ok = tb > 0  # -9999 = no observations; brightness temperatures below 0 K are noise
        msg = []
        for k, (t0, t1) in SLOTS.items():
            m = ok & (lt > t0) & (lt < t1)
            s, c = acc[k]
            np.add.at(s, (i[m], j[m]), tb[m])
            np.add.at(c, (i[m], j[m]), 1)
            msg.append(f"{k} {m.sum()} bins, median {np.median(tb[m]) if m.any() else float('nan'):.0f} K")
        print(f"  {os.path.basename(p)}: lat {lat.min():.2f} to {lat.max():.2f}, {len(tb)} rows; " + "; ".join(msg))
    prof = dict(driver="GTiff", width=nx, height=ny, count=1, dtype="float32", nodata=np.nan, compress="deflate",
                crs=f"+proj=longlat +R={MOON_R} +no_defs", transform=from_origin(-180, 90, 0.5, 0.5))
    os.makedirs(a.out, exist_ok=True)
    for k, (s, c) in acc.items():
        with np.errstate(invalid="ignore", divide="ignore"):
            v = np.where(c > 0, s / c, np.nan).astype("float32")
        path = os.path.join(a.out, f"moon_ts_{k}.tif")
        with rasterio.open(path, "w", **prof) as ds:
            ds.write(v, 1)
        print(f"wrote {path}: {int(np.isfinite(v).sum())} cells with data, {np.nanmin(v):.0f} to {np.nanmax(v):.0f} K")


if __name__ == "__main__":
    main()
