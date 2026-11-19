"""Global analog finder: offline pipeline core (first version).

Runs on free Colab/Kaggle. Needs only numpy. Reading real rasters (GeoTIFF/NetCDF) is up to
you: pass a function that returns rows of a global equirectangular array
(row 0 = 90N, col 0 = 180W, NaN = no data). Everything here is tested on synthetic data only.

Output (static files the website loads, no server):
  grid.json     manifest: cell size, shape, and per-feature label/unit/dimension/scale/source
  <key>.bin     one little-endian float32 array per feature, row-major, north-up, NaN = no data

Similarity rule is the SAME as the app's methodology panel:
  per feature: 1 - min(1, |a - b| / scale); overall: weighted mean over features that have values.
"""
import json, os
import numpy as np

R_EARTH = 6371000.0


def to_cells(read_rows, ny, nx, cell_deg, reduce):
    """Aggregate a global raster to cell_deg cells, one band of rows at a time (keeps RAM low).
    read_rows(i0, i1) -> (i1-i0, nx) array. reduce(block) -> one number per cell."""
    by, bx = round(ny * cell_deg / 180), round(nx * cell_deg / 360)
    cy, cx = ny // by, nx // bx
    out = np.full((cy, cx), np.nan, np.float32)
    for i in range(cy):
        band = read_rows(i * by, (i + 1) * by)
        for j in range(cx):
            blk = band[:, j * bx:(j + 1) * bx]
            if np.isfinite(blk).any():
                out[i, j] = reduce(blk)
    return out


def slope_deg(dem, lat_top, pix_deg):
    """Slope in degrees for a DEM band. lat_top = latitude of the band's first row, pix_deg = pixel size.
    Pixel width shrinks with latitude, so it is computed per row. Edge rows use one-sided gradients."""
    ny = dem.shape[0]
    lat = lat_top - (np.arange(ny) + 0.5) * pix_deg
    dy = R_EARTH * np.radians(pix_deg)
    dx = np.maximum(R_EARTH * np.cos(np.radians(lat)) * np.radians(pix_deg), 1.0)[:, None]
    gy, gx = np.gradient(dem.astype(np.float64), dy, axis=0), np.gradient(dem.astype(np.float64), axis=1) / dx
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def p90(b): return float(np.nanpercentile(b, 90))
def median(b): return float(np.nanmedian(b))
def mean(b): return float(np.nanmean(b))


# Landform shape of one cell (Earth) or one 111 km patch (Moon/Mars), measured on elevation pixels of the same size.
# p5 and p95 are used instead of min and max so one bad pixel cannot set the value.
def relief(b):
    """Local relief in metres: 95th minus 5th percentile of elevation in the block."""
    lo, hi = np.nanpercentile(b, [5, 95])
    return float(hi - lo)


def hypso(b):
    """Hypsometric integral (Strahler 1952; Pike & Wilson 1971 elevation-relief ratio), 0 to 1:
    (mean - low) / (high - low), with low/high = 5th/95th percentile. Low = mostly low ground with a few peaks
    (e.g. a lone cone on a plain is about 0.33), high = mostly high ground cut by valleys or craters, about 0.5 =
    evenly spread. NaN where the block is completely flat."""
    lo, hi = np.nanpercentile(b, [5, 95])
    if not hi > lo:
        return float("nan")
    return float(np.clip((np.nanmean(b) - lo) / (hi - lo), 0.0, 1.0))


def similarity(feats, target, scales, weights):
    """feats: {key: (cy,cx) array}. target/scales/weights: {key: number}. Returns (score grid, per-feature grids)."""
    num = 0.0
    den = 0.0
    per = {}
    for k, w in weights.items():
        s = 1 - np.minimum(1, np.abs(feats[k] - target[k]) / scales[k])
        per[k] = s
        ok = np.isfinite(s) & (w > 0)
        num = num + np.where(ok, w * np.nan_to_num(s), 0)
        den = den + np.where(ok, w, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan), per


def cell_of(lat, lon, cell_deg):
    return int((90 - lat) // cell_deg), int((lon + 180) // cell_deg)


def backtest(score, known, cell_deg):
    """known: [(name, lat, lon)] of sites the literature calls analogs for this target.
    Returns each site's percentile among all scored cells (100 = best cell on Earth)."""
    land = score[np.isfinite(score)]
    out = {}
    for name, lat, lon in known:
        i, j = cell_of(lat, lon, cell_deg)
        v = score[i, j]
        out[name] = None if not np.isfinite(v) else round(100 * float((land < v).mean()), 1)
    return out


def export(feats, meta, cell_deg, outdir, extra=None):
    """meta[key] = {label, unit, dimension, scale, source, url, resolution, date}."""
    os.makedirs(outdir, exist_ok=True)
    ny, nx = next(iter(feats.values())).shape
    man = {"schema": "earth-analogs-grid/v0", "cell_deg": cell_deg, "ny": ny, "nx": nx,
           "layout": "row-major float32 LE, row 0 = 90N, col 0 = 180W, NaN = no data", "features": []}
    if extra:
        man.update(extra)
    for k, a in feats.items():
        a.astype("<f4").tofile(os.path.join(outdir, k + ".bin"))
        man["features"].append({"key": k, **meta[k]})
    with open(os.path.join(outdir, "grid.json"), "w") as f:
        json.dump(man, f, indent=1)
    return man
