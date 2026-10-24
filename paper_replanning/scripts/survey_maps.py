"""Survey every downloaded map: size, passable %, number of scenario problems.

Prints one line per map and writes results/tables/map_survey.csv.
It also marks whether each map passes the selection filters in config/mvp.json
(max side length and minimum passable fraction), so we can see how many maps
are usable before select_problems.py runs.

Usage:  python scripts/survey_maps.py [--raw data/raw] [--out results/tables/map_survey.csv]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))                 # so "import src..." works when run as a script

from src.benchmark_files import find_map_files   # noqa: E402
from src.maps import load_map, load_scen, max_side_for   # noqa: E402

COLUMNS = ["map_set", "map_name", "width", "height", "passable_cells", "passable_pct",
           "scen_problems", "passes_size", "passes_passable"]


def survey(raw_dir, map_sets, sel):
    """Return one dict per map (see COLUMNS). `sel` is the config's "selection" block."""
    rows = []
    for map_set in map_sets:
        max_side = max_side_for(sel, map_set)
        for name, (map_path, scen_path) in find_map_files(raw_dir / map_set).items():
            grid = load_map(map_path)
            frac = grid.passable_count() / (grid.width * grid.height)
            rows.append({
                "map_set": map_set,
                "map_name": name,
                "width": grid.width,
                "height": grid.height,
                "passable_cells": grid.passable_count(),
                "passable_pct": round(100 * frac, 2),
                "scen_problems": len(load_scen(scen_path)) if scen_path else 0,
                "passes_size": max(grid.width, grid.height) <= max_side,
                "passes_passable": frac >= sel["min_passable_frac"],
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "tables" / "map_survey.csv")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "mvp.json")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    sel = config["selection"]
    rows = survey(args.raw, config["data"]["map_sets"], sel)

    print(f"{'set':8} {'map':28} {'size':>9} {'pass%':>6} {'problems':>8}  filters")
    for r in rows:
        ok = "OK" if r["passes_size"] and r["passes_passable"] else (
            ("too big " if not r["passes_size"] else "") +
            ("too few passable" if not r["passes_passable"] else ""))
        print(f"{r['map_set']:8} {r['map_name']:28} {r['width']:>4}x{r['height']:<4} "
              f"{r['passable_pct']:6.1f} {r['scen_problems']:8}  {ok}")

    # Per-set totals, so the shortage (if any) is obvious.
    print()
    for map_set in config["data"]["map_sets"]:
        in_set = [r for r in rows if r["map_set"] == map_set]
        good = [r for r in in_set if r["passes_size"] and r["passes_passable"]]
        print(f"{map_set}: {len(in_set)} maps, {len(good)} pass both filters "
              f"(max side <= {max_side_for(sel, map_set)}, passable >= {100 * sel['min_passable_frac']:.0f}%)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
