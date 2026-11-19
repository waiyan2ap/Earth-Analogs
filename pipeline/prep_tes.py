"""Mars surface temperature for the Mars targets, from MGS TES Data Tool exports, written into docs/data/targets.json.

  Summary of one file (writes nothing):
    python pipeline/prep_tes.py --site jezero --day pipeline/raw/tes/jezero_day.van.gz
  Daytime only (writes ts_day for that site into docs/data/targets.json):
    python pipeline/prep_tes.py --site jezero --day pipeline/raw/tes/jezero_day.van.gz --day-only
  Day and night together (writes ts_mean and ts_range for that site into docs/data/targets.json):
    python pipeline/prep_tes.py --site jezero --day pipeline/raw/tes/jezero_day.van.gz --night pipeline/raw/tes/jezero_night.van.gz

Input: tab-separated exports (.van or .van.gz) from the TES Data Tool at the ASU TES Data Node (MGS TES Standard Data
  Products, archived by the PDS Geosciences Node). Query used: the site's 111.2 km box, Observation Type = Surface,
  Time of Day = Day or Night, Clear Atmosphere and Highest Spectral Quality on. Columns needed (header line):
  LONGITUDE_IAU2000 (deg E), LATITUDE, LOCAL_TIME (Mars hours), TARGET_TEMPERATURE (K); SOLAR_LONGITUDE (Ls) recommended.

Method, same formulas as build_targets.py so the app treats it like the Moon and Earth values:
  only spots inside the site's 111.2 km patch are used;
  if SOLAR_LONGITUDE is exported, each pass over the patch (rows sharing one Ls value) is averaged first, then the passes,
  so one long pass cannot outweigh many short ones; without it every spot counts equally (the source text says which);
  day and night means are converted to degC; ts_mean = (day + night) / 2, ts_range = day - night.
Difference from Earth and Moon, written into the source text: TES crossed at about 14:00 and 02:00 local time, not 10:30 and
  22:30, and the Clear Atmosphere filter drops the dustiest season. The script prints the actual local times and Ls covered.

Raw exports stay in pipeline/raw/tes/ (never committed; their file names contain the requester's email address).
"""
import argparse, datetime, gzip, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARS_R = 3396190.0  # same as build_site_terrain.py
PATCH_KM = 111.2  # must match build_targets.py
SITES = {  # centres must match build_targets.py
    "jezero": (18.4, 77.5),
    "olympus": (18.6, -133.8),
    "valles": (-14.0, -59.0),
}
COLS = ("LONGITUDE_IAU2000", "LATITUDE", "LOCAL_TIME", "TARGET_TEMPERATURE")  # required
LS = "SOLAR_LONGITUDE"  # optional: without it every spot is weighted equally instead of every pass
SRC = ("MGS TES Standard Data Products, TARGET_TEMPERATURE of surface observations with Clear Atmosphere and Highest "
       "Spectral Quality, queried with the TES Data Tool (ASU TES Data Node; archive: PDS Geosciences Node)")


def read(path):
    op = gzip.open if path.lower().endswith(".gz") else open
    with op(path, "rt", encoding="ascii", errors="replace") as f:
        head = f.readline().strip().split("\t")
        miss = [c for c in COLS if c not in head]
        if miss:
            sys.exit(f"{os.path.basename(path)}: missing column(s) {', '.join(miss)}. Tick them in the TES Data Tool and export again.")
        ix = [head.index(c) for c in COLS]
        il = head.index(LS) if LS in head else None
        rows = []
        for n, line in enumerate(f):
            p = line.rstrip("\n").split("\t")
            try:
                lon, lat, lt, t = (float(p[i]) for i in ix)
                rows.append((lon, lat, float(p[il]) if il is not None else float(n), lt, t))  # no Ls: each spot is its own "pass"
            except (ValueError, IndexError):
                continue
    if not rows:
        sys.exit(f"{os.path.basename(path)}: no data rows.")
    return rows, il is not None


def in_patch(lat0, lon0, lat, lon):
    half = PATCH_KM * 500.0
    dlat = math.degrees(half / MARS_R)
    dlon = math.degrees(half / (MARS_R * max(math.cos(math.radians(lat0)), 0.01)))
    dl = (lon - lon0 + 180) % 360 - 180
    return abs(lat - lat0) <= dlat and abs(dl) <= dlon


def summarise(path, site, label):
    lat0, lon0 = SITES[site]
    rows, has_ls = read(path)
    keep = [r for r in rows if in_patch(lat0, lon0, r[1], r[0]) and 100 < r[4] < 400]
    if not keep:
        sys.exit(f"{label}: no rows inside the {PATCH_KM} km patch around {site}. Is this the right file?")
    passes = {}
    for r in keep:
        passes.setdefault(r[2], []).append(r[4])
    means = [sum(v) / len(v) for v in passes.values()]
    t = sum(means) / len(means) - 273.15
    lts = sorted(r[3] for r in keep)
    ls = sorted(passes)
    hh = lambda h: f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}"
    lt_lo, lt_hi = lts[int(0.05 * (len(lts) - 1))], lts[int(0.95 * (len(lts) - 1))]
    bins = [0] * 12
    for x in ls:
        bins[int(x // 30) % 12] += 1
    gaps = [f"{30 * i}-{30 * i + 30}" for i, n in enumerate(bins) if n == 0]
    if not has_ls:
        gaps = None
    lons = [r[0] for r in keep]
    print(f"  {label}: {len(keep)} of {len(rows)} spots inside the patch" + (f", {len(passes)} passes" if has_ls else ", no SOLAR_LONGITUDE column (spots weighted equally)"))
    print(f"    longitude covered {min(lons):.2f} to {max(lons):.2f} E")
    print(f"    local time {hh(lt_lo)} to {hh(lt_hi)} (5th to 95th percentile), median {hh(lts[len(lts) // 2])}")
    if has_ls:
        print(f"    Ls without any pass: {', '.join(gaps) or 'none'}")
    print(f"    mean: {t:.1f} degC ({t + 273.15:.1f} K)" + (f"; pass means range {min(means) - 273.15:.1f} to {max(means) - 273.15:.1f} degC" if has_ls else ""))
    return dict(t=t, lt=(hh(lt_lo), hh(lt_hi)), n=len(keep), passes=len(passes) if has_ls else None, gaps=gaps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=sorted(SITES))
    ap.add_argument("--day", required=True, help="TES Data Tool export for Time of Day = Day")
    ap.add_argument("--night", help="TES Data Tool export for Time of Day = Night (writes ts_mean and ts_range)")
    ap.add_argument("--day-only", action="store_true", help="no night file: write the daytime mean as ts_day")
    ap.add_argument("--url", help="page of the TES Data Tool you used, added to the source text")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "data", "targets.json"))
    a = ap.parse_args()
    print(f"== {a.site}: TES surface temperature over a {PATCH_KM} km patch")
    d = summarise(a.day, a.site, "day")
    lat0, lon0 = SITES[a.site]
    src = SRC[:-1] + f", {a.url})" if a.url else SRC
    where = f"{abs(lat0)}°{'N' if lat0 >= 0 else 'S'}, {abs(lon0)}°{'E' if lon0 >= 0 else 'W'}"
    pw = lambda x: f"{x['n']} spots, {x['passes']} passes averaged first" if x["passes"] else f"{x['n']} spots, weighted equally"
    if not a.night:
        if not a.day_only:
            print("\nno --night file: summary only, targets.json not changed. Add --day-only to write ts_day.")
            return
        text = (f"Measured by pipeline/prep_tes.py from {src}: daytime mean over a {PATCH_KM} km patch centred {where}, "
                f"{d['lt'][0]}-{d['lt'][1]} local time ({pw(d)}). Compared with Earth's daytime value at about 10:30 local "
                f"time (MODIS Terra), so Mars is measured about 3.5 hours later in its day."
                + (f" No clear-sky passes at Ls {', '.join(d['gaps'])} (dusty season)." if d["gaps"] else "")
                + f" Accessed {datetime.date.today().isoformat()}.")
        write(a.out, a.site, {"ts_day": {"value": round(d["t"], 1), "source": text}})
        return
    n = summarise(a.night, a.site, "night")
    if d["t"] < n["t"]:
        sys.exit("day is colder than night: check that --day and --night are not swapped. Nothing written.")
    gaps = sorted(set(d["gaps"] or []) | set(n["gaps"] or []))
    pw = lambda x: f"{x['n']} spots, {x['passes']} passes" if x["passes"] else f"{x['n']} spots, weighted equally"
    text = (f"Measured by pipeline/prep_tes.py from {src}: mean over a {PATCH_KM} km patch centred "
            f"{abs(lat0)}°{'N' if lat0 >= 0 else 'S'}, {abs(lon0)}°{'E' if lon0 >= 0 else 'W'}. "
            f"Day {d['lt'][0]}-{d['lt'][1]} local time ({pw(d)}), night {n['lt'][0]}-{n['lt'][1]} ({pw(n)}). mean = (day + night) / 2, swing = day - night. NOT the same local hours as "
            f"Earth and Moon (10:30 and 22:30), so the swing is not like for like."
            + (f" No clear-sky passes at Ls {', '.join(gaps)} (dusty season)." if gaps else "")
            + f" Accessed {datetime.date.today().isoformat()}.")
    write(a.out, a.site, {"ts_mean": {"value": round((d["t"] + n["t"]) / 2, 1), "source": text},
                          "ts_range": {"value": round(d["t"] - n["t"], 1), "source": text}})


def write(out, site, vals):
    with open(out, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("demo"):
        sys.exit("targets.json is marked demo; run build_targets.py for real terrain first. Nothing written.")
    doc.setdefault("targets", {}).setdefault(site, {}).update(vals)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {out}: {site} " + ", ".join(f"{k} {v['value']} degC" for k, v in vals.items()))


if __name__ == "__main__":
    main()
