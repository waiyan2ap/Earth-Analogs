"""Download and prepare high-resolution planetary textures for Earth Analogs Explorer.

Sourced from Solar System Scope (NASA elevation and spacecraft imaging data, CC-BY 4.0).
Places optimized textures into docs/assets/textures/.
"""
import os
import ssl
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "docs", "assets", "textures")
os.makedirs(OUT_DIR, exist_ok=True)

BASE_URL = "https://www.solarsystemscope.com/textures/download/"

# Core targets: download 8k and downsample to 4k (4096x2048) for high crispness and modest file size.
# Context planets: 2k (2048x1024).
TARGETS = [
    # (output_name, remote_file, target_width, target_height)
    ("earth.jpg", "8k_earth_daymap.jpg", 4096, 2048),
    ("clouds.jpg", "8k_earth_clouds.jpg", 4096, 2048),
    ("moon.jpg", "8k_moon.jpg", 4096, 2048),
    ("mars.jpg", "8k_mars.jpg", 4096, 2048),
    ("sky.jpg", "2k_stars_milky_way.jpg", 2048, 1024),
    ("sun.jpg", "2k_sun.jpg", 2048, 1024),
    ("mercury.jpg", "2k_mercury.jpg", 2048, 1024),
    ("venus.jpg", "2k_venus_atmosphere.jpg", 2048, 1024),
    ("jupiter.jpg", "2k_jupiter.jpg", 2048, 1024),
    ("saturn.jpg", "2k_saturn.jpg", 2048, 1024),
    ("rings.png", "2k_saturn_ring_alpha.png", None, None),
    ("uranus.jpg", "2k_uranus.jpg", 2048, 1024),
    ("neptune.jpg", "2k_neptune.jpg", 2048, 1024),
]


def download_and_process():
    ctx = ssl._create_unverified_context()
    total_size = 0

    for out_name, remote_name, w, h in TARGETS:
        dest_path = os.path.join(OUT_DIR, out_name)
        temp_path = os.path.join(OUT_DIR, "tmp_" + remote_name)
        url = BASE_URL + remote_name

        print(f"Fetching {remote_name} -> {out_name}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            data = resp.read()

        if w and h and (w != 2048 or "8k" in remote_name):
            # Write temp file and resize using macOS sips
            with open(temp_path, "wb") as f:
                f.write(data)
            cmd = ["sips", "-z", str(h), str(w), "-s", "formatOptions", "85", temp_path, "--out", dest_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            with open(dest_path, "wb") as f:
                f.write(data)

        size = os.path.getsize(dest_path)
        total_size += size
        print(f"  OK: {out_name} ({size:,} bytes, {size / 1024 / 1024:.2f} MB)")

    print(f"\nAll textures ready! Total folder size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    download_and_process()
