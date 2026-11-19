"""Download every raw file the pipeline needs into pipeline/raw/, straight from NASA / NOAA / WorldClim, and check it.

  python pipeline/fetch_data.py                 # everything (about 2.3 GB)
  python pipeline/fetch_data.py --only earth    # Earth grid inputs: ETOPO, WorldClim, MODIS (about 1.4 GB)
  python pipeline/fetch_data.py --only moon     # Diviner tables for the Moon temperature (about 470 MB)
  python pipeline/fetch_data.py --list          # show what would be downloaded, download nothing
  python pipeline/fetch_data.py --record        # (lead only) write checksums of your files into data_manifest.json

Files already present with the right size (and checksum, once recorded) are skipped, so it is safe to run again.
Broken downloads resume where they stopped. Nothing here is committed to git (pipeline/raw/ is ignored).

MODIS files need a free NASA Earthdata login (https://urs.earthdata.nasa.gov/users/new). The script asks for it, or reads
EARTHDATA_USER / EARTHDATA_PASS, or a ~/.netrc (Windows: %USERPROFILE%\\_netrc) line for urs.earthdata.nasa.gov.
Moon/Mars elevation is NOT downloaded: build_targets.py and build_site_terrain.py read small windows from the web directly.
"""
import argparse, getpass, hashlib, json, os, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
MANIFEST = os.path.join(HERE, "data_manifest.json")
URS = "urs.earthdata.nasa.gov"

MODIS = [("2025.01.01", "MOD11C3.A2025001.061.2025035172114.hdf", 70964636),
         ("2025.02.01", "MOD11C3.A2025032.061.2025063170308.hdf", 72219922),
         ("2025.03.01", "MOD11C3.A2025060.061.2025093043031.hdf", 73863959),
         ("2025.04.01", "MOD11C3.A2025091.061.2025125142315.hdf", 74037314),
         ("2025.05.01", "MOD11C3.A2025121.061.2025153164905.hdf", 73691014),
         ("2025.06.01", "MOD11C3.A2025152.061.2025182145012.hdf", 72164923),
         ("2025.07.01", "MOD11C3.A2025182.061.2025213154157.hdf", 71413359),
         ("2025.08.01", "MOD11C3.A2025213.061.2025246014643.hdf", 72758381),
         ("2025.09.01", "MOD11C3.A2025244.061.2025275150152.hdf", 73253020),
         ("2025.10.01", "MOD11C3.A2025274.061.2025306143832.hdf", 75951178),
         ("2025.11.01", "MOD11C3.A2025305.061.2025335114103.hdf", 74445464),
         ("2025.12.01", "MOD11C3.A2025335.061.2026006185449.hdf", 72808827)]
DIV = "https://pds-geosciences.wustl.edu/lro/lro-l-dlre-4-rdr-v1/lrodlr_1001/data/gcp/"

# group, file under pipeline/raw, url, expected bytes (from the lead's working copy), what it is
FILES = [("earth", "dem.tif",
          "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/60s/60s_surface_elev_gtif/ETOPO_2022_v1_60s_N90W180_surface.tif",
          465969062, "NOAA ETOPO 2022, 60 arc-second, ice surface elevation"),
         ("earth", "worldclim/wc2.1_10m_bio.zip", "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_bio.zip",
          None, "WorldClim 2.1 bioclimatic variables, 10 minutes (t_mean.tif = BIO1, t_range.tif = BIO7 are taken out of it)")]
FILES += [("earth", "lst/" + f, f"https://e4ftl01.cr.usgs.gov/MOLT/MOD11C3.061/{d}/{f}", n, "NASA MODIS MOD11C3 v6.1, " + d[:7])
          for d, f, n in MODIS]
FILES += [("moon", "diviner/" + f + ext, DIV + f + ext, n if ext == ".tab" else None, "LRO Diviner Global Cumulative Product")
          for f in ("global_cumul_avg_cyl_00n10n_002", "global_cumul_avg_cyl_10s00s_002", "global_cumul_avg_cyl_90s80s_002")
          for ext, n in ((".tab", 156211313), (".xml", None))]
EXTRACT = {"worldclim/wc2.1_10m_bio.zip": [("wc2.1_10m_bio_1.tif", "t_mean.tif", 3790814), ("wc2.1_10m_bio_7.tif", "t_range.tif", 3488376)]}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def session():
    try:
        import requests
    except ImportError:
        sys.exit("needs requests: run  pip install -r pipeline/requirements.txt  and try again")

    class S(requests.Session):
        def rebuild_auth(self, prep, resp):  # send the Earthdata password only to the Earthdata login server
            if "Authorization" in prep.headers and requests.utils.urlparse(prep.url).hostname != URS:
                del prep.headers["Authorization"]
    s = S()
    s.headers["User-Agent"] = "earth-analogs-pipeline"
    return s


def earthdata_login(s):
    u, p = os.environ.get("EARTHDATA_USER"), os.environ.get("EARTHDATA_PASS")
    if not (u and p):
        import netrc
        try:
            a = netrc.netrc().authenticators(URS)
            if a:
                u, p = a[0], a[2]
        except (OSError, netrc.NetrcParseError):
            pass
    if not (u and p):
        print("MODIS files need a free NASA Earthdata login (make one at https://urs.earthdata.nasa.gov/users/new).")
        u = input("  Earthdata username: ").strip()
        p = getpass.getpass("  Earthdata password (not shown): ")
    s.auth = (u, p)


def download(s, url, path, size, tries=6):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    for t in range(tries):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        try:
            h = {"Range": f"bytes={have}-"} if have else {}
            with s.get(url, headers=h, stream=True, timeout=120) as r:
                if r.status_code == 401:
                    sys.exit(f"  login refused for {url}. Check the Earthdata username/password, and that you have "
                             "approved 'LP DAAC Data Pool' under Applications in your Earthdata profile.")
                if r.status_code == 416 and size and have == size:
                    break
                r.raise_for_status()
                if have and r.status_code != 206:
                    have = 0  # server ignored the resume request: start again
                if "text/html" in r.headers.get("Content-Type", ""):
                    raise IOError("got a web page instead of the file (login page or error page)")
                total = (have + int(r.headers.get("Content-Length", 0))) or size
                with open(part, "ab" if have else "wb") as f:
                    done, last = have, 0
                    for b in r.iter_content(1 << 20):
                        f.write(b)
                        done += len(b)
                        if time.time() - last > 2:
                            last = time.time()
                            print(f"\r    {done / 1e6:7.1f} / {total / 1e6:.1f} MB" if total else f"\r    {done / 1e6:7.1f} MB", end="", flush=True)
            print()
            if size and os.path.getsize(part) < size:
                raise IOError(f"stopped at {os.path.getsize(part)} of {size} bytes")
            break
        except SystemExit:
            raise
        except Exception as e:
            print(f"\n    attempt {t + 1} of {tries} failed: {e}")
            time.sleep(3 * (t + 1))
    else:
        sys.exit(f"  could not download {url}. Run the script again later; it continues where it stopped.")
    os.replace(part, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["earth", "moon"])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--record", action="store_true", help="write checksums of the files you have into pipeline/data_manifest.json")
    a = ap.parse_args()
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    todo = [f for f in FILES if not a.only or f[0] == a.only]

    if a.record:
        for _, name, *_ in FILES:
            p = os.path.join(RAW, name)
            if os.path.exists(p):
                man[name] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
                print(f"  recorded {name}")
        for outs in EXTRACT.values():
            for _, out, _ in outs:
                p = os.path.join(RAW, out)
                if os.path.exists(p):
                    man[out] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
                    print(f"  recorded {out}")
        with open(MANIFEST, "w") as f:
            json.dump(man, f, indent=1, sort_keys=True)
        print(f"wrote {MANIFEST}: commit it so everyone checks against the same files")
        return

    s, logged_in, bad = None, False, []
    for grp, name, url, size, what in todo:
        p = os.path.join(RAW, name)
        size = man.get(name, {}).get("bytes", size)
        ok = os.path.exists(p) and (size is None or os.path.getsize(p) == size)
        if name in EXTRACT and all(os.path.exists(os.path.join(RAW, o)) and os.path.getsize(os.path.join(RAW, o)) == n
                                   for _, o, n in EXTRACT[name]):
            ok = True  # what we need from the zip is already taken out of it
        print(f"{'have' if ok else 'get '}  {name}  ({what})")
        if a.list or ok:
            continue
        if s is None:
            s = session()
        if "e4ftl01" in url and not logged_in:
            earthdata_login(s)
            logged_in = True
        download(s, url, p, size)
    if a.list:
        return
    for z, outs in EXTRACT.items():
        zp = os.path.join(RAW, z)
        if not os.path.exists(zp) or (a.only and a.only != "earth"):
            continue
        for member, out, size in outs:
            op = os.path.join(RAW, out)
            if os.path.exists(op) and os.path.getsize(op) == size:
                continue
            with zipfile.ZipFile(zp) as zf, zf.open(member) as src, open(op, "wb") as dst:
                dst.write(src.read())
            print(f"made  {out}  (from {member})")
    print("checking ...")
    for name in [f[1] for f in todo if f[1] not in EXTRACT] + ([o[1] for outs in EXTRACT.values() for o in outs] if a.only != "moon" else []):
        p = os.path.join(RAW, name)
        if not os.path.exists(p):
            bad.append(f"{name}: missing")
        elif name in man and man[name].get("sha256") and sha256(p) != man[name]["sha256"]:
            bad.append(f"{name}: different from the lead's copy (checksum). Delete it and run again.")
    if bad:
        print("PROBLEMS:\n  " + "\n  ".join(bad))
        sys.exit(1)
    print("all files present" + (" and identical to the lead's copies" if man else "") + ". Next: see README section 4.")


if __name__ == "__main__":
    main()
