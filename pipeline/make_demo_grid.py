"""Write SYNTHETIC grid files so the website and the format can be developed before real data exists.
These numbers are made up. The manifest is marked "demo": true and the site must show a DEMO banner.

  python pipeline/make_demo_grid.py [--out docs/data]
"""
import argparse, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finder_pipeline as fp

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data"))
out = ap.parse_args().out
cell, ny, nx = 1.0, 180, 360
lat = 90 - (np.arange(ny) + .5) * cell
lon = -180 + (np.arange(nx) + .5) * cell
LAT, LON = np.meshgrid(lat, lon, indexing="ij")
rng = np.random.default_rng(7)
land = (np.sin(np.radians(LON * 2)) + np.cos(np.radians(LAT * 3)) + rng.normal(0, .3, (ny, nx))) > 0.1
t_mean = 30 - 0.6 * np.abs(LAT) + rng.normal(0, 2, (ny, nx))
relief = np.abs(np.sin(np.radians(LON * 3))) * np.abs(np.cos(np.radians(LAT * 2))) * 25 + rng.normal(0, 1.5, (ny, nx))
feats = {"slope_p90": np.where(land, np.clip(relief, 0, 45), np.nan).astype("f4"),
         "t_mean": np.where(land, t_mean, np.nan).astype("f4")}
src = "SYNTHETIC DEMO DATA, not real"
meta = {"slope_p90": dict(label="Steep terrain (90th percentile slope)", unit="deg", dimension="terrain", scale=15, source=src, url="", resolution="1 deg", date=""),
        "t_mean": dict(label="Mean surface temperature", unit="degC", dimension="thermal", scale=120, source=src, url="", resolution="1 deg", date="")}
fp.export(feats, meta, cell, out, extra={"demo": True})
# Demo target values (made up). Real ones come from the Moon/Mars patch around each site, with sources.
src_t = "DEMO placeholder, not measured"
vals = {"shackleton": (14, -20), "tranquility": (3, 8), "jezero": (8, -6), "olympus": (12, -12), "valles": (18, 2)}
targets = {"schema": "earth-analogs-targets/v0", "demo": True, "patch_km": 110,
           "targets": {k: {"slope_p90": {"value": a, "source": src_t}, "t_mean": {"value": b, "source": src_t}} for k, (a, b) in vals.items()}}
import json
with open(os.path.join(out, "targets.json"), "w") as f:
    json.dump(targets, f, indent=1)
print(f"wrote {len(feats)} features and targets.json to {out} (DEMO data)")
