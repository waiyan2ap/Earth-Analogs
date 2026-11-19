"""Check a downloaded raster BEFORE running build_grid.py.

  python pipeline/inspect_raster.py pipeline/raw/dem.tif
  python pipeline/inspect_raster.py pipeline/raw/t_mean.tif --cell 1

Prints what the file really is (size, pixel size, bounds, units hints, fill value), reads a quick overview,
samples a few places you can sanity-check, and tells you in plain words what to fix. Needs only rasterio + numpy.
"""
import argparse, sys
import numpy as np

PLACES = [  # (name, lat, lon, what to expect)
    ("Mount Everest", 27.99, 86.93, "elevation: roughly 8,000-8,850 m (a ~1 km pixel smooths the summit); air temp: very cold"),
    ("Dead Sea shore", 31.50, 35.50, "elevation: about -430 m"),
    ("Sahara (Algeria)", 25.00, 3.00, "elevation: a few hundred m; air temp: hot, about 20-28 C"),
    ("Atacama (Chile)", -24.50, -69.25, "elevation: 2,000+ m; air temp: mild, about 10-18 C"),
    ("McMurdo Dry Valleys", -77.50, 162.50, "air temp: about -20 C. Empty here means the dataset skips Antarctica"),
    ("Pacific Ocean", 0.00, -150.00, "elevation: deep negative; air temp: empty (land-only data)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--cell", type=float, default=1.0, help="grid cell size in degrees (default 1)")
    ap.add_argument("--band", type=int, default=1)
    a = ap.parse_args()
    import rasterio
    from rasterio.enums import Resampling
    ds = rasterio.open(a.path)
    b, ok, fix = ds.bounds, True, []
    pix = abs(ds.res[1])
    print(f"file        {a.path}")
    print(f"size        {ds.width} x {ds.height} pixels, {ds.count} band(s), dtype {ds.dtypes[a.band - 1]}")
    print(f"pixel size  {pix:.6f} deg (about {pix * 111:.1f} km at the equator)")
    print(f"crs         {ds.crs}")
    print(f"bounds      west {b.left:.3f}  east {b.right:.3f}  south {b.bottom:.3f}  north {b.top:.3f}")
    print(f"fill value  {ds.nodatavals[a.band - 1]}   scale {ds.scales[a.band - 1]}   offset {ds.offsets[a.band - 1]}")

    glob = ds.crs is not None and ds.crs.is_geographic and abs(b.left + 180) < 1e-3 and abs(b.right - 180) < 1e-3 \
        and abs(b.top - 90) < 1e-3 and abs(b.bottom + 90) < 1e-3
    if not glob:
        ok = False
        ppd = max(1, round(1 / pix))
        fix.append("Not a global lat/lon raster (build_grid refuses it). Pad or reproject it to the whole globe, keeping the pixel count per degree:\n"
                   f"      gdalwarp -t_srs EPSG:4326 -te -180 -90 180 90 -ts {360 * ppd} {180 * ppd} -r average {a.path} fixed.tif\n"
                   "      (add -dstnodata <fill value> if the file has one)")
    by, bx = a.cell and (ds.height * a.cell / 180), (ds.width * a.cell / 360)
    if abs(by - round(by)) > 1e-6 or abs(bx - round(bx)) > 1e-6:
        ok = False
        fix.append(f"{ds.width}x{ds.height} pixels do not divide into {a.cell}-degree cells. Resample to a whole number of pixels per cell.")
    else:
        print(f"cells       OK: {int(round(bx))}x{int(round(by))} pixels per {a.cell}-degree cell")

    sc, off, nd = ds.scales[a.band - 1], ds.offsets[a.band - 1], ds.nodatavals[a.band - 1]
    oh, ow = min(ds.height, 1080), min(ds.width, 2160)
    ov = ds.read(a.band, out_shape=(oh, ow), resampling=Resampling.nearest).astype("float64")
    raw_big = float(np.nanmax(np.abs(ov)))
    if nd is not None and not np.isnan(nd):
        ov[ov == nd] = np.nan
    ov = ov * sc + off
    fin = np.isfinite(ov)
    print(f"overview    {fin.mean() * 100:.1f}% of pixels have data")
    if fin.any():
        v = ov[fin]
        print(f"values      min {v.min():.2f}   median {np.median(v):.2f}   max {v.max():.2f}")
        sentinels = (-9999, -999, -32768, -32767, 32767, 65535, 9999)
        hit = [x for x in sentinels if (ov == x).any()]
        if hit and (nd is None or np.isnan(nd) or nd not in hit):
            ok = False
            fix.append(f"Value(s) {hit} look like a fill value but the file does not flag them as missing. "
                       f"Set open=dict(nodata={hit[0]}) for this feature in build_grid.py, or they will be treated as real data.")
        if v.max() > 1e10 or v.min() < -1e10:
            ok = False
            fix.append("Huge values: the fill value is not flagged in the file. Set open=dict(nodata=<that value>) for this feature in build_grid.py.")
        if v.min() < -500 and v.max() > 1000:
            fix.append("Elevation below -500 m is mostly ocean. build_grid.py keeps only 0 to 9000 m for the DEM so the sea floor is not scored as land.")
        if np.median(v) > 150 and v.max() < 400:
            fix.append("Median above 150 with max below 400: this looks like Kelvin. Convert (K - 273.15) or set scale/offset in build_grid.py.")
    print("\nspot checks (compare with what you know):")
    for name, lat, lon, note in PLACES:
        try:
            r, c = ds.index(lon, lat)
            if not (0 <= r < ds.height and 0 <= c < ds.width):
                print(f"  {name:22s} outside the file")
                continue
            raw = ds.read(a.band, window=((r, r + 1), (c, c + 1)))[0, 0]
            miss = (nd is not None and not np.isnan(nd) and raw == nd) or not np.isfinite(raw)
            val = "no data" if miss else f"{float(raw) * sc + off:.2f}"
            print(f"  {name:22s} {val:>10}   {note}")
        except Exception as e:
            print(f"  {name:22s} could not sample ({e})")
    print()
    if ok and not fix:
        print("RESULT: looks ready for build_grid.py.")
    elif ok:
        print("RESULT: readable, but check these notes:")
    else:
        print("RESULT: fix these before running build_grid.py:")
    for f in fix:
        print("  - " + f)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
