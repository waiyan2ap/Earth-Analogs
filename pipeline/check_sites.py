"""Check named sites and find new candidate leads, before and after adding them to pipeline/named_sites.json.

  python pipeline/check_sites.py                  # check every site in named_sites.json and list leads
  python pipeline/check_sites.py --leads 10       # how many new leads per target (default 8)
  python pipeline/check_sites.py --out site_check.md   # also write the report to a file (do not commit it to docs/data)

Reads only files that are already built: pipeline/named_sites.json, docs/data/grid.json + *.bin, docs/data/targets.json
and docs/data/places.json. Writes nothing to docs/data. Nothing here is typed by hand: every number comes from those files.

Three checks, in the order a new site should pass them:

1. Record check (every site). Is the coordinate inside the valid range? Does coord_src name a source and not say
   "not checked"? Earth only: which country/province does Natural Earth put in the site's 1-degree cell (places.json),
   and does it contain the "expect_place" text if the site has one? Does the cell have a value in every scored dimension?
   Does another named Earth site share the same cell (then both get identical values and the second adds nothing)?
   Moon/Mars only: does targets.json have values for it (build_targets.py has measured it)?

2. Evidence check (Earth analogs). For every target on a body the site is an analog for, where does the site's cell rank
   among all scored Earth cells? Same score and same rank as the website (Find on Earth, rankAt in docs/index.html).
   top 25%      = the measurements support the pairing
   25 to 50%    = partly
   below 50%    = the pairing rests only on its cited reason (geology, chemistry, ice...), which the grid does not measure.
   A low rank does not reject a site: it tells you to say the reason is not measured. A site with no cited reason
   (tags_src or a pair "why") and a low rank has nothing behind it.

3. Leads (Moon/Mars targets). The best distinct Earth cells (at least 800 km apart) that are more than 500 km from every
   named Earth site. These are where to look in the literature for a published analog. A lead becomes a site only after a
   paper or agency page names a place there as an analog; the grid score alone is never the reason.
"""
import argparse, json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from finder_pipeline import cell_of

UNCHECKED = ("not checked", "not yet checked", "general knowledge")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def km(a, b, c, d):
    r = math.pi / 180
    x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def score_grid(grid, feats, T):
    """Same rule as efScore in docs/index.html: per feature 1 - min(1, |gap|/scale); features share their dimension's
    weight; dimensions count equally; a cell is scored only if it has a value in every dimension used."""
    use = [f for f in grid["features"] if f["key"] in T and T[f["key"]].get("value") is not None]
    per = {}
    for f in use:
        per[f["dimension"]] = per.get(f["dimension"], 0) + 1
    n = grid["ny"] * grid["nx"]
    num, den, hit = np.zeros(n), np.zeros(n), np.zeros(n, int)
    for d in per:
        seen = np.zeros(n, bool)
        for f in (f for f in use if f["dimension"] == d):
            a = feats[f["key"]]
            ok = np.isfinite(a)
            s = 1 - np.minimum(1, np.abs(a - T[f["key"]]["value"]) / (f.get("scale") or 1))
            num[ok] += s[ok] / per[d]
            den[ok] += 1 / per[d]
            seen |= ok
        hit += seen
    sc = np.full(n, np.nan)
    m = (den > 0) & (hit == len(per))
    sc[m] = num[m] / den[m]
    return sc.astype(np.float32), use


def top_share(land, v):
    """Share of scored cells that score at least as high, in % (rankAt in index.html gives 100 minus this)."""
    if v is None or not math.isfinite(v):
        return None
    return 100 * (len(land) - np.searchsorted(land, v, side="left")) / len(land)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=os.path.join(HERE, "named_sites.json"))
    ap.add_argument("--data", default=os.path.join(HERE, "..", "docs", "data"))
    ap.add_argument("--leads", type=int, default=8)
    ap.add_argument("--out")
    a = ap.parse_args()

    S = load(a.sites)["sites"]
    grid = load(os.path.join(a.data, "grid.json"))
    T = load(os.path.join(a.data, "targets.json")).get("targets", {})
    P = load(os.path.join(a.data, "places.json"))
    ny, nx, cd = grid["ny"], grid["nx"], grid["cell_deg"]
    feats = {f["key"]: np.fromfile(os.path.join(a.data, f["key"] + ".bin"), "<f4").astype(np.float64) for f in grid["features"]}
    pcells, pnames = P["cells"], P["names"]
    place = lambda i, j: (pnames[pcells[i * nx + j]] if pcells[i * nx + j] >= 0 else "sea or no land in Natural Earth")
    lines, problems = [], 0

    def say(s=""):
        lines.append(s)

    say("# Site check")
    say(f"Grid: {grid.get('note', 'docs/data/grid.json')[:60]}... {ny}x{nx}, {cd} degree cells.")
    say("")
    say("## 1. Record check")
    cells = {}
    for s in S:
        flags = []
        lat, lon = s.get("lat"), s.get("lon")
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            flags.append("FAIL coordinate missing or out of range (lat -90..90, lon -180..180, west negative)")
        src = (s.get("coord_src") or "").lower()
        if not src:
            flags.append("FAIL no coord_src")
        elif any(u in src for u in UNCHECKED):
            flags.append("WARN coord_src says the coordinate is not checked" + (f" (check: {s['coord_check']})" if s.get("coord_check") else ""))
        if s["body"] == "earth" and lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            i, j = cell_of(lat, lon, cd)
            i, j = min(ny - 1, i), min(nx - 1, j)
            pl = place(i, j)
            exp = s.get("expect_place")
            if exp and exp.lower() not in pl.lower():
                flags.append(f"FAIL cell is in '{pl}', expected '{exp}': coordinate is probably wrong (or a coastal cell)")
            missing = sorted({f["dimension"] for f in grid["features"] if f["dimension"] != "air" and not math.isfinite(feats[f["key"]][i * nx + j])})
            if missing:
                flags.append("WARN no Earth value for: " + ", ".join(missing) + " (the site cannot be scored on a target that uses them)")
            if (i, j) in cells:
                flags.append(f"WARN same 1-degree cell as '{cells[(i, j)]}': identical values, adds no new measurement")
            cells.setdefault((i, j), s["id"])
            where = f"cell row {i}, col {j}: {pl}"
        elif s["body"] != "earth":
            where = "targets.json: " + (", ".join(T[s["id"]]) if s["id"] in T else "NOT MEASURED (run build_targets.py --site " + s["id"] + ")")
            if s["id"] not in T:
                flags.append("FAIL no values in targets.json")
        else:
            where = ""
        problems += sum(f.startswith("FAIL") for f in flags)
        say(f"- **{s['id']}** ({s['body']}) {lat}, {lon}; {where}" + ("".join("\n  - " + f for f in flags) if flags else " · OK"))

    targets = [s for s in S if s["type"] == "target" and s["id"] in T]
    earth = [s for s in S if s["body"] == "earth"]
    scored = {}
    for t in targets:
        sc, use = score_grid(grid, feats, T[t["id"]])
        land = np.sort(sc[np.isfinite(sc)])
        scored[t["id"]] = (sc, land, use)

    say("")
    say("## 2. Evidence check (Earth analogs)")
    say("Rank of each Earth site's cell among all scored Earth cells, for every target on the bodies it is an analog for.")
    curated = {(t["id"], p["id"]): p.get("why", "") for t in S if t["type"] == "target" for p in t.get("analogs", [])}
    for e in earth:
        bodies = e.get("analog_for") or ["moon", "mars"]
        i, j = cell_of(e["lat"], e["lon"], cd)
        cited = bool(e.get("tags_src"))
        rows = []
        for t in targets:
            if t["body"] not in bodies:
                continue
            sc, land, _ = scored[t["id"]]
            v = float(sc[min(ny - 1, i) * nx + min(nx - 1, j)])
            ts = top_share(land, v)
            why = curated.get((t["id"], e["id"]))
            if ts is None:
                verdict = "not scored (no value in a dimension this target uses)"
            elif ts <= 25:
                verdict = "supported by measurements"
            elif ts <= 50:
                verdict = "partly supported"
            elif why is None:
                verdict = "low rank (not a curated pair, so no claim is made)"
            else:
                verdict = "rests on the cited reason only" if (cited or why) else "NO SUPPORT: curated pair, low rank, no cited reason"
            rows.append(f"{t['id']} {'' if ts is None else f'{v*100:.0f}%, top {ts:.1f}%'}: {verdict}" + (" [curated pair]" if why is not None else ""))
        say(f"- **{e['id']}**{'' if cited else ' (no tags_src citation)'}: " + "; ".join(rows))

    say("")
    say("## 3. Leads: best Earth cells far from every named site")
    say("Look these places up in the literature. Add one only if a paper or agency page names it as an analog.")
    for t in targets:
        sc, land, use = scored[t["id"]]
        idx = np.argsort(-np.nan_to_num(sc, nan=-1))
        out = []
        for k in idx:
            if not math.isfinite(sc[k]):
                break
            la, lo = 90 - (k // nx + .5) * cd, -180 + (k % nx + .5) * cd
            if any(km(la, lo, e["lat"], e["lon"]) <= 500 for e in earth):
                continue
            if all(km(la, lo, q[0], q[1]) > 800 for q in out):
                out.append((la, lo, float(sc[k]), place(k // nx, k % nx), top_share(land, float(sc[k]))))
                if len(out) == a.leads:
                    break
        say(f"- **{t['id']}** (scored on {', '.join(f['key'] for f in use)}):")
        for la, lo, v, pl, ts in out:
            say(f"  - {abs(la):.1f}{'N' if la >= 0 else 'S'} {abs(lo):.1f}{'E' if lo >= 0 else 'W'} · {pl} · {v*100:.0f}%, top {ts:.2f}%")

    say("")
    say(f"{problems} FAIL line(s). Fix those before running build_named_sites.py.")
    txt = "\n".join(lines)
    print(txt)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
