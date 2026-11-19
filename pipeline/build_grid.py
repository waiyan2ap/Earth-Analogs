"""Turn raw global rasters into the website's grid files.

  python pipeline/build_grid.py                      # raw files in pipeline/raw, output to docs/data
  python pipeline/build_grid.py --check 27.99,86.93  # also print every feature at a place you know
  python pipeline/build_grid.py --derive-only        # only add derived features (ts_day) to the existing grid

Files missing from the raw folder are skipped, so add datasets one at a time.
Edit FEATURES below as datasets arrive. The `scale` values are STARTING GUESSES (the gap that counts as
"completely different"); tune them and write the reasoning down in the methodology panel.
"""
import argparse, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finder_pipeline as fp
from raster_io import open_global_raster

# Sources below are filled in for the first real run (ETOPO 2022 + WorldClim 2.1). Add the ACCESS DATE in `date` when you download.
# DEM valid range starts at 0 m, not -500 m: shallow sea floor (e.g. the North Sea) must not be scored as land.
# WorldClim has no Antarctica, so thermal features are empty there; see pipeline/FIRST_RUN.md.
FEATURES = [
    dict(key="slope_p90", file="dem.tif", transform="slope", reduce="p90", label="Steep terrain (90th percentile slope)",
         unit="deg", dimension="terrain", scale=15, source="NOAA NCEI ETOPO 2022 Global Relief Model, ice surface, 60 arc-second", url="https://www.ncei.noaa.gov/products/etopo-global-relief-model",
         resolution="60 arc-second (about 1.85 km)", date="", open=dict(valid=(0, 9000))),
    dict(key="slope_median", file="dem.tif", transform="slope", reduce="median", label="Typical terrain (median slope)",
         unit="deg", dimension="terrain", scale=10, source="NOAA NCEI ETOPO 2022 Global Relief Model, ice surface, 60 arc-second", url="https://www.ncei.noaa.gov/products/etopo-global-relief-model",
         resolution="60 arc-second (about 1.85 km)", date="", open=dict(valid=(0, 9000))),
    # Landform: measured on the same ETOPO pixels as slope, and the same way on the Moon/Mars by build_targets.py.
    # scale: 2000 m relief gap and 0.5 hypsometric gap count as "completely different" (starting guesses, like the others).
    dict(key="relief", file="dem.tif", transform=None, reduce="relief", label="Local relief (95th minus 5th percentile elevation)",
         unit="m", dimension="landform", scale=2000, source="NOAA NCEI ETOPO 2022 Global Relief Model, ice surface, 60 arc-second", url="https://www.ncei.noaa.gov/products/etopo-global-relief-model",
         resolution="60 arc-second (about 1.85 km)", date="", open=dict(valid=(0, 9000))),
    dict(key="hypso", file="dem.tif", transform=None, reduce="hypso", label="Landform shape (hypsometric integral: low = lowland with a few peaks, high = upland cut by valleys or craters)",
         unit="", dimension="landform", scale=0.5, source="NOAA NCEI ETOPO 2022 Global Relief Model, ice surface, 60 arc-second", url="https://www.ncei.noaa.gov/products/etopo-global-relief-model",
         resolution="60 arc-second (about 1.85 km)", date="", open=dict(valid=(0, 9000))),
    # Surface (skin) temperature: the like-for-like thermal measure, because the Moon has no air. Made by prep_lst.py from
    # NASA NEO / MODIS Terra monthly maps (about 10:30 and 22:30 local solar time). build_targets.py --ts-day/--ts-night
    # measures the Moon/Mars sites the same way. scale: starting guesses, like the others.
    dict(key="ts_mean", file="ts_mean.tif", transform=None, reduce="mean", label="Mean surface temperature (average of day and night)",
         unit="degC", dimension="thermal", scale=120, source="NASA MODIS Terra MOD11C3 v6.1 land surface temperature, day and night, monthly, 12 months of 2025 averaged (LP DAAC direct download; pipeline/prep_lst.py)",
         url="https://doi.org/10.5067/MODIS/MOD11C3.061", resolution="0.05 degree (about 5.6 km)", date="", open=dict(valid=(-100, 80))),
    dict(key="ts_range", file="ts_range.tif", transform=None, reduce="mean", label="Day-night surface temperature swing",
         unit="degC", dimension="thermal", scale=60, source="NASA MODIS Terra MOD11C3 v6.1 land surface temperature, day and night, monthly, 12 months of 2025 averaged (LP DAAC direct download; pipeline/prep_lst.py)",
         url="https://doi.org/10.5067/MODIS/MOD11C3.061", resolution="0.05 degree (about 5.6 km)", date="", open=dict(valid=(-30, 80))),
    # Air temperature: Earth-only context (the Moon has no air), so it gets its own dimension and is never scored.
    dict(key="t_mean", file="t_mean.tif", transform=None, reduce="mean", label="Mean air temperature (2 m)",
         unit="degC", dimension="air", scale=120, source="WorldClim 2.1 (1970-2000), BIO1 annual mean temperature", url="https://www.worldclim.org/data/worldclim21.html",
         resolution="10 arc-minute (about 18 km)", date="", open=dict(valid=(-100, 80))),
    dict(key="t_range", file="t_range.tif", transform=None, reduce="mean", label="Annual air temperature range (warmest-month max minus coldest-month min)",
         unit="degC", dimension="air", scale=60, source="WorldClim 2.1 (1970-2000), BIO7 temperature annual range", url="https://www.worldclim.org/data/worldclim21.html",
         resolution="10 arc-minute (about 18 km)", date="", open=dict(valid=(0, 120))),
]
# Derived features: computed from features above, no new download. ts_day = ts_mean + ts_range / 2 is exactly the mean
# DAYTIME (about 10:30 local) surface temperature, because prep_lst.py makes ts_mean = mean((day + night) / 2) and
# ts_range = mean(day - night) over the same months and pixels. It has its own dimension so it is only used for targets
# that have a daytime value and nothing else (Mars, from MGS TES), and it does not change Moon scores.
DERIVED = [
    dict(key="ts_day", needs=("ts_mean", "ts_range"), calc=lambda f: f["ts_mean"] + f["ts_range"] / 2,
         label="Daytime surface temperature (about 10:30 local time on Earth)", unit="degC", dimension="day thermal", scale=120,
         source="Derived from NASA MODIS Terra MOD11C3 v6.1 land surface temperature, 12 months of 2025: daytime mean = "
                "ts_mean + ts_range / 2 (pipeline/build_grid.py)",
         url="https://doi.org/10.5067/MODIS/MOD11C3.061", resolution="0.05 degree (about 5.6 km)", date=""),
]


def derive(feats, meta):
    for d in DERIVED:
        if all(k in feats for k in d["needs"]):
            feats[d["key"]] = d["calc"](feats).astype("float32")
            meta[d["key"]] = {k: d[k] for k in ("label", "unit", "dimension", "scale", "source", "url", "resolution", "date")}
            a = feats[d["key"]]
            print(f"ok     {d['key']} (derived): {int(np.isfinite(a).sum())} cells with data, range {np.nanmin(a):.2f} to {np.nanmax(a):.2f} {d['unit']}")


def derive_only(out):
    """Add the derived features to an existing grid (docs/data) without the raw files."""
    import json
    with open(os.path.join(out, "grid.json"), encoding="utf-8") as f:
        man = json.load(f)
    feats, meta = {}, {}
    for f in man["features"]:
        if f["key"] in {d["key"] for d in DERIVED}:
            continue
        feats[f["key"]] = np.fromfile(os.path.join(out, f["key"] + ".bin"), "<f4").reshape(man["ny"], man["nx"])
        meta[f["key"]] = {k: f.get(k, "") for k in ("label", "unit", "dimension", "scale", "source", "url", "resolution", "date")}
    derive(feats, meta)
    extra = {k: v for k, v in man.items() if k not in ("schema", "cell_deg", "ny", "nx", "layout", "features")}
    fp.export(feats, meta, man["cell_deg"], out, extra or None)
    print(f"wrote {len(feats)} features to {out}")


REDUCE = {"p90": fp.p90, "median": fp.median, "mean": fp.mean, "relief": fp.relief, "hypso": fp.hypso}


def build(raw, out, cell, check=None):
    feats, meta = {}, {}
    for f in FEATURES:
        path = os.path.join(raw, f["file"])
        if not os.path.exists(path):
            print(f"skip   {f['key']}: missing {path}")
            continue
        rows, ny, nx, pix = open_global_raster(path, **f.get("open", {}))
        if abs(ny * cell / 180 - round(ny * cell / 180)) > 1e-6 or abs(nx * cell / 360 - round(nx * cell / 360)) > 1e-6:
            raise SystemExit(f"{f['file']}: {ny}x{nx} pixels do not divide into {cell}-degree cells. "
                             "Resample to a whole number of pixels per cell (e.g. 0.01 degree).")
        read = rows if f.get("transform") != "slope" else (
            lambda a, b, rows=rows, pix=pix: fp.slope_deg(rows(a, b), 90 - a * pix, pix))
        a = fp.to_cells(read, ny, nx, cell, REDUCE[f["reduce"]])
        feats[f["key"]] = a
        meta[f["key"]] = {k: f[k] for k in ("label", "unit", "dimension", "scale", "source", "url", "resolution", "date")}
        print(f"ok     {f['key']}: {int(np.isfinite(a).sum())} cells with data, range {np.nanmin(a):.2f} to {np.nanmax(a):.2f} {f['unit']}")
    if not feats:
        raise SystemExit(f"No input files found in {raw}. Put your downloaded rasters there (see FEATURES for the names).")
    derive(feats, meta)
    fp.export(feats, meta, cell, out)
    print(f"wrote {len(feats)} features to {out}")
    if check:
        lat, lon = check
        i, j = fp.cell_of(lat, lon, cell)
        print(f"check at lat {lat}, lon {lon} (cell row {i}, col {j}):")
        for k, a in feats.items():
            print(f"  {k}: {a[i, j]:.2f} {next(x['unit'] for x in FEATURES if x['key'] == k)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(HERE, "raw"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data"))
    ap.add_argument("--cell", type=float, default=1.0)
    ap.add_argument("--check", help="lat,lon of a place you know, to sanity-check values")
    ap.add_argument("--derive-only", action="store_true", help="only add derived features (ts_day) to the existing docs/data grid")
    a = ap.parse_args()
    if a.derive_only:
        derive_only(a.out)
        sys.exit()
    build(a.raw, a.out, a.cell, tuple(float(x) for x in a.check.split(",")) if a.check else None)
