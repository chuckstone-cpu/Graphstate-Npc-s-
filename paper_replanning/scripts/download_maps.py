"""Download the Moving AI benchmark maps and scenarios listed in config/mvp.json.

For every map set (e.g. "dao") we fetch two zip files:
    <base_url>/<set>/<set>-map.zip    (the .map files)
    <base_url>/<set>/<set>-scen.zip   (the .scen files = start/goal problems)
and unpack them into data/raw/<set>/. Anything already on disk is skipped, so the
script is safe to re-run.

Usage:  python scripts/download_maps.py
"""

import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # the paper_replanning/ folder
CONFIG = ROOT / "config" / "mvp.json"
RAW = ROOT / "data" / "raw"


def download(url, dest):
    """Download one file to `dest`, unless it is already there."""
    if dest.exists():
        print(f"  already have {dest.name}")
        return
    print(f"  downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "paper-replanning-research"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    # Write to a temporary name first, so a half-finished download never looks complete.
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.rename(dest)
    print(f"  saved {dest.name} ({len(data) / 1e6:.1f} MB)")


def extract(zip_path, out_dir):
    """Unpack a zip into out_dir, skipping files that already exist.

    Safety check: a zip entry may not point outside out_dir (e.g. "../../evil.py").
    """
    out_dir = out_dir.resolve()
    new_files = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (out_dir / member.filename).resolve()
            if out_dir not in target.parents:
                raise ValueError(f"unsafe path in {zip_path.name}: {member.filename}")
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))
            new_files += 1
    print(f"  extracted {new_files} new files from {zip_path.name}")


def main():
    config = json.loads(CONFIG.read_text())
    base_url = config["data"]["base_url"]
    failed = []
    for map_set in config["data"]["map_sets"]:
        print(f"[{map_set}]")
        set_dir = RAW / map_set
        zip_dir = set_dir / "_zips"
        zip_dir.mkdir(parents=True, exist_ok=True)
        for kind in ("map", "scen"):
            name = f"{map_set}-{kind}.zip"
            zip_path = zip_dir / name
            url = f"{base_url}/{map_set}/{name}"
            try:
                download(url, zip_path)
            except OSError as err:          # URLError, connection reset, timeout...
                print(f"  FAILED: {err}")
                failed.append((url, zip_path))
                continue
            extract(zip_path, set_dir)
        n_maps = len(list(set_dir.rglob("*.map")))
        n_scens = len(list(set_dir.rglob("*.scen")))
        print(f"  {map_set}: {n_maps} .map files, {n_scens} .scen files")

    if failed:
        # Manual fallback: download the zips in a browser (maybe on another network)
        # and drop them in the folder shown; re-running this script then just extracts them.
        print("\nSome downloads failed. Download these by hand and save them as shown,")
        print("then run this script again:")
        for url, zip_path in failed:
            print(f"  {url}\n    -> {zip_path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
