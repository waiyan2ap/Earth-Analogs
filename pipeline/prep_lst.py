"""Average monthly MODIS land surface temperature maps into the two Earth files build_grid.py reads.

  python pipeline/prep_lst.py --hdf "pipeline/raw/lst/MOD11C3*.hdf"      # MOD11C3 files downloaded directly (recommended)
  python pipeline/prep_lst.py --day "pipeline/raw/lst/day/*.tif" --night "pipeline/raw/lst/night/*.tif"   # GeoTIFFs

MOD11C3 .hdf files (NASA LP DAAC, one per month, each holding the day and the night layer) are read with pyhdf
(pip install pyhdf), so GDAL's HDF4 driver is not needed. Values: integer x 0.02 = kelvin, 0 = no data (MOD11 user guide).

Input: global GeoTIFFs in plain latitude/longitude, one per month, for daytime and night-time surface temperature.
Works with MODIS MOD11C3 (monthly, 0.05 degree) layers LST_Day_CMG / LST_Night_CMG exported as GeoTIFF from AppEEARS
(add --scale 0.02 --nodata 0), and with the NASA Earth Observations (NEO) downloads "Land Surface Temperature [Day]" and "[Night]" (Terra/MODIS,
1 month), saved as "GeoTIFF (floating point)" at 0.1 degree. Values in degC or kelvin (detected); 99999 = no data.

Output (pipeline/raw, never committed to git):
  ts_mean.tif   mean surface temperature  = (day + night) / 2, averaged over all months given
  ts_range.tif  day-night surface swing   = day - night,       averaged over all months given
Both in degC. A pixel needs a value in at least half of the months, otherwise it is left empty.
Terra crosses the equator at about 10:30 and 22:30 local solar time, so these are temperatures at those two times.
"""
import argparse, glob, os, sys, warnings
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
warnings.simplefilter("ignore", RuntimeWarning)  # all-empty pixels (oceans) are expected


def load(paths, scale=None, nodata=None):
    import rasterio
    stack, prof = [], None
    for p in sorted(paths):
        with rasterio.open(p) as ds:
            if ds.dtypes[0] in ("uint8", "int8"):
                sys.exit(f"{os.path.basename(p)} is 8-bit: that is the coloured picture, not temperatures. "
                         "Download the 'GeoTIFF (floating point)' version.")
            a = ds.read(1).astype("float32")
            nd = ds.nodata if nodata is None else nodata
            if nd is not None and np.isfinite(nd):
                a[a == nd] = np.nan
            if scale:
                a *= scale  # e.g. MODIS MOD11C3 from AppEEARS: stored as integers, value x 0.02 = kelvin
            else:
                a[np.abs(a) >= 9999] = np.nan  # NEO fill value 99999
            if prof is None:
                prof = ds.profile
                b = ds.bounds
                if not (ds.crs and ds.crs.is_geographic and abs(b.left + 180) < .01 and abs(b.right - 180) < .01
                        and abs(b.top - 90) < .01 and abs(b.bottom + 90) < .01):
                    sys.exit(f"{os.path.basename(p)} is not a global latitude/longitude map (bounds {tuple(b)}).")
            elif (ds.width, ds.height) != (prof["width"], prof["height"]):
                sys.exit(f"{os.path.basename(p)} has a different size from the first file.")
        med = np.nanmedian(a)
        if med > 150:  # kelvin
            a -= 273.15
        stack.append(a)
        print(f"  {os.path.basename(p)}: {np.isfinite(a).mean():.0%} pixels with data, median {np.nanmedian(a):.1f} degC")
    return np.stack(stack), prof


def load_hdf(paths):
    """MOD11C3 Climate Modeling Grid: 3600 x 7200 at 0.05 degree, row 0 at 90N, column 0 at 180W."""
    try:
        from pyhdf.SD import SD, SDC
    except ImportError:
        sys.exit("reading .hdf files needs pyhdf: run  pip install pyhdf  and try again")
    from rasterio.transform import from_origin
    out = {"LST_Day_CMG": [], "LST_Night_CMG": []}
    for p in sorted(paths):
        f = SD(p, SDC.READ)
        for k in out:
            ds = f.select(k)
            at = ds.attributes()
            a = ds.get().astype("float32")
            if a.shape != (3600, 7200):
                sys.exit(f"{os.path.basename(p)}: {k} is {a.shape}, expected (3600, 7200). Is this MOD11C3?")
            fill, sc, off = at.get("_FillValue", 0), at.get("scale_factor", 0.02), at.get("add_offset", 0.0)
            a[a == fill] = np.nan
            a = a * sc + off - 273.15
            out[k].append(a)
            ds.endaccess()
        f.end()
        print(f"  {os.path.basename(p)}: day median {np.nanmedian(out['LST_Day_CMG'][-1]):.1f}, "
              f"night median {np.nanmedian(out['LST_Night_CMG'][-1]):.1f} degC")
    prof = dict(driver="GTiff", width=7200, height=3600, count=1, crs="EPSG:4326",
                transform=from_origin(-180, 90, 0.05, 0.05))
    return np.stack(out["LST_Day_CMG"]), np.stack(out["LST_Night_CMG"]), prof


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdf", help='MOD11C3 .hdf files, e.g. "pipeline/raw/lst/MOD11C3*.hdf" (quotes needed)')
    ap.add_argument("--day", help='daytime files, e.g. "pipeline/raw/lst/day/*.tif" (quotes needed)')
    ap.add_argument("--night", help="night-time files, same months as --day")
    ap.add_argument("--out", default=os.path.join(HERE, "raw"))
    ap.add_argument("--scale", type=float, help="multiply raw values by this, e.g. 0.02 for MOD11C3 files from AppEEARS")
    ap.add_argument("--nodata", type=float, help="raw value meaning no data, e.g. 0 for MOD11C3 files from AppEEARS")
    a = ap.parse_args()
    import rasterio
    if a.hdf:
        hp = glob.glob(a.hdf)
        if not hp:
            sys.exit(f"no files match {a.hdf}")
        print(f"MOD11C3 ({len(hp)} files):")
        D, N, prof = load_hdf(hp)
        n = len(hp)
    else:
        if not (a.day and a.night):
            sys.exit("give --hdf, or both --day and --night")
        dp, np_ = glob.glob(a.day), glob.glob(a.night)
        if not dp or not np_:
            sys.exit(f"no files found: {len(dp)} day, {len(np_)} night. Check the paths.")
        if len(dp) != len(np_):
            sys.exit(f"{len(dp)} day files but {len(np_)} night files: use the same months for both.")
        print(f"day ({len(dp)} files):")
        D, prof = load(dp, a.scale, a.nodata)
        print(f"night ({len(np_)} files):")
        N, _ = load(np_, a.scale, a.nodata)
        n = len(dp)
    need = max(1, n // 2)
    both = np.isfinite(D) & np.isfinite(N)
    with np.errstate(invalid="ignore"):
        mean = np.where(both, (D + N) / 2, np.nan)
        rng = np.where(both, D - N, np.nan)
        cnt = both.sum(0)
        out = {"ts_mean": np.where(cnt >= need, np.nanmean(mean, 0), np.nan),
               "ts_range": np.where(cnt >= need, np.nanmean(rng, 0), np.nan)}
    prof.update(dtype="float32", count=1, nodata=np.nan, compress="deflate")
    os.makedirs(a.out, exist_ok=True)
    for k, v in out.items():
        path = os.path.join(a.out, k + ".tif")
        with rasterio.open(path, "w", **prof) as ds:
            ds.write(v.astype("float32"), 1)
        print(f"wrote {path}: {np.isfinite(v).mean():.0%} pixels with data, {np.nanmin(v):.1f} to {np.nanmax(v):.1f} degC")


if __name__ == "__main__":
    main()
