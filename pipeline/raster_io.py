"""Read a real global Earth raster (GeoTIFF) in the shape finder_pipeline.to_cells expects.

Handles the two classic traps: fill values (no-data) and scale/offset (e.g. temperature stored as
integers x0.02). Reads a band of rows at a time, so big files do not need big RAM.
"""
import numpy as np


def open_global_raster(path, band=1, nodata=None, valid=None, scale=None, offset=None):
    """Returns (read_rows, ny, nx, pix_deg).
    nodata: fill value to treat as missing (default: the file's own flag; many files flag it wrongly, so check!)
    valid:  (low, high) in final units; anything outside becomes missing (cuts leftover fill values)
    scale/offset: override the file's own (value = raw * scale + offset)"""
    import rasterio
    from rasterio.windows import Window
    ds = rasterio.open(path)
    b = ds.bounds
    ok = (ds.crs is not None and ds.crs.is_geographic and abs(b.left + 180) < 1e-3 and abs(b.right - 180) < 1e-3
          and abs(b.top - 90) < 1e-3 and abs(b.bottom + 90) < 1e-3)
    if not ok:
        raise ValueError(f"{path} is not a global lat/lon raster (bounds {tuple(b)}, crs {ds.crs}). Fix it first, e.g.:\n"
                         "  gdalwarp -t_srs EPSG:4326 -te -180 -90 180 90 -tr 0.01 0.01 -r average in.tif out.tif")
    nd = nodata if nodata is not None else ds.nodatavals[band - 1]
    sc = scale if scale is not None else ds.scales[band - 1]
    off = offset if offset is not None else ds.offsets[band - 1]

    def read_rows(i0, i1):
        a = ds.read(band, window=Window(0, i0, ds.width, i1 - i0)).astype("float32")
        if nd is not None and not np.isnan(nd):
            a[a == nd] = np.nan
        a = a * sc + off
        if valid is not None:
            a[(a < valid[0]) | (a > valid[1])] = np.nan
        return a

    return read_rows, ds.height, ds.width, abs(ds.res[1])
