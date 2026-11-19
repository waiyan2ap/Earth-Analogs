# First real run: Earth grid from public data

Goal: replace the fake Earth grid with real numbers, one dataset at a time. Everything here also works with the 13 Nov NASA files:
put a file in `pipeline/raw/` under the name `build_grid.py` expects and edit its entry in `FEATURES`.

## 1. Environment (do this first, it is the slowest step)
Easiest for a team: **Google Colab** (free). In a notebook: `!pip install rasterio numpy`, upload/clone the repo, and for
reprojection `!apt-get install -y gdal-bin`. Locally: `pip install -r pipeline/requirements.txt` (rasterio ships its own GDAL;
the `gdalwarp` command needs GDAL installed separately, e.g. conda: `conda install -c conda-forge gdal`).

## 2. Download three files into `pipeline/raw/` (never commit them)
| Save as | What | Where |
|---|---|---|
| `dem.tif` | ETOPO 2022, **60 arc-second, ice surface** elevation, GeoTIFF | NOAA NCEI: https://www.ncei.noaa.gov/products/etopo-global-relief-model (GeoTiff > 60 Arc-Second) |
| `t_mean.tif` | WorldClim 2.1 historical climate, **10 minutes, bioclimatic (bio)**, variable BIO1 | https://www.worldclim.org/data/worldclim21.html |
| `t_range.tif` | same zip, variable BIO7 | same page |

Write the **access date** into `date=""` of each entry in `FEATURES` (`build_grid.py`). Check the challenge rules allow non-NASA open data.

## 3. Check every file before building
    python pipeline/inspect_raster.py pipeline/raw/dem.tif
    python pipeline/inspect_raster.py pipeline/raw/t_mean.tif
It says in plain words if the file is not global, has an unflagged fill value (-9999), looks like Kelvin, or does not divide into 1-degree cells.
Look at the spot checks: Everest about 8,000+ m, Dead Sea about -430 m, Pacific empty for temperature.

## 4. Build into a TEMP folder first (the default output overwrites docs/data)
    python pipeline/build_grid.py --out /tmp/grid_test --check 27.99,86.93
    python pipeline/build_grid.py --out /tmp/grid_test --check 25,3
Everest (steep, cold) and Sahara (flat, hot) must look different. If yes, copy the files from `/tmp/grid_test` to `docs/data/`.
`targets.json` stays `"demo": true` until Moon/Mars values have sources, so the app keeps its DEMO banner.

## Known limits (write these in the methodology panel)
- WorldClim has **no Antarctica**: thermal features are empty there (McMurdo Dry Valleys is one of our analog sites).
- WorldClim is **2 m air temperature**; Moon/Mars values are usually **surface** temperature. Not the same thing.
- A 60 arc-second DEM has ~1.85 km pixels, which smooths slopes. Compute Moon/Mars slopes at a similar pixel size or the comparison is unfair.
- ETOPO "ice surface" is the top of the ice (Greenland, Antarctica); the "bedrock" version is the ground under it.
