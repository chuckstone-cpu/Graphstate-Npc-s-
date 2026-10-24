"""Choose the maps and start/goal problems used in the experiments.

Rules (all numbers come from config/mvp.json, "selection"):
  1. A map is ELIGIBLE if max(width, height) <= max_side (or the set's entry in
     max_side_overrides, e.g. room: 512), its passable fraction is >= min_passable_frac,
     and it has a .scen file.
  2. Per map set, shuffle the eligible maps with a seeded random generator and walk
     down the list.
  3. For each map, shuffle its .scen problems (seeded per map) and keep the first
     `problems_per_map` whose 4-connected BFS length (number of moves) is in
     [min_bfs_len, max_bfs_len]. Problems are skipped if the start or goal is on a
     cell we treat as blocked (e.g. water), if the goal is unreachable, or if the
     same start/goal pair was already taken.
  4. A map that cannot supply enough problems is REJECTED (recorded in the JSON) and
     the next map in the shuffled list is tried, until `maps_per_set` maps are chosen.
     If a set runs out of maps, we print a warning and record the shortfall:
     the filters are never loosened automatically.

The .scen "optimal length" column is octile (8-direction) and is NOT used to select
problems. We only use it for one sanity check: a 4-direction path can never be
shorter than the octile optimum, so bfs_len < octile length would mean a bug.

Writes data/selected_maps.json and data/selected_problems.csv.

Usage:  python scripts/select_problems.py [--raw data/raw] [--out-dir data] [--config config/mvp.json]
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))                 # so "import src..." works when run as a script

from src.benchmark_files import find_map_files   # noqa: E402
from src.maps import load_map, load_scen, max_side_for   # noqa: E402
from src.seeding import derive_seed              # noqa: E402

from src.search import bfs                       # noqa: E402  (the port of the game's bfs.gd)

PROBLEM_COLUMNS = ["problem_id", "map_set", "map_name", "scen_index", "bucket",
                   "sx", "sy", "gx", "gy", "bfs_len", "octile_length_unused"]


def bfs_length(grid, start, goal):
    """Number of 4-connected moves on the shortest path, or None if unreachable."""
    result = bfs.search(grid.width, grid.height, lambda c: c in grid.blocked, start, goal)
    return len(result["path"]) - 1 if result["path"] else None


def pick_problems(grid, problems, sel, rng):
    """Shuffle the problems and keep the first ones that pass the filters.

    Returns (chosen, stats). Each chosen item is (problem, bfs_len).
    """
    order = list(problems)
    rng.shuffle(order)
    chosen, seen_pairs = [], set()
    stats = {"tried": 0, "blocked_endpoint": 0, "unreachable": 0, "too_short": 0,
             "too_long": 0, "duplicate": 0}
    for p in order:
        if len(chosen) == sel["problems_per_map"]:
            break
        stats["tried"] += 1
        if (p.map_width, p.map_height) != (grid.width, grid.height):
            raise ValueError(f"{grid.name}: scen problem {p.index} says map is "
                             f"{p.map_width}x{p.map_height}, file is {grid.width}x{grid.height}")
        if (p.start, p.goal) in seen_pairs:
            stats["duplicate"] += 1
            continue
        if grid.is_blocked(*p.start) or grid.is_blocked(*p.goal):
            stats["blocked_endpoint"] += 1       # e.g. start on water, which we treat as blocked
            continue
        length = bfs_length(grid, p.start, p.goal)
        if length is None:
            stats["unreachable"] += 1
        elif length < sel["min_bfs_len"]:
            stats["too_short"] += 1
        elif length > sel["max_bfs_len"]:
            stats["too_long"] += 1
        else:
            chosen.append((p, length))
            seen_pairs.add((p.start, p.goal))
    return chosen, stats


def eligible_maps(set_dir, map_set, sel):
    """Return (all map names, list of (name, map_path, scen_path, grid)) that pass the filters."""
    files = find_map_files(set_dir)
    max_side = max_side_for(sel, map_set)
    good = []
    for name, (map_path, scen_path) in files.items():
        if scen_path is None:
            continue
        grid = load_map(map_path)
        frac = grid.passable_count() / (grid.width * grid.height)
        if max(grid.width, grid.height) <= max_side and frac >= sel["min_passable_frac"]:
            good.append((name, map_path, scen_path, grid))
    return list(files), good


def print_histogram(lengths, lo, hi, width=20):
    """Text histogram of path lengths in bins of `width` moves."""
    edges = list(range(lo, hi + 1, width))
    for start in edges:
        end = min(start + width - 1, hi)
        count = sum(start <= x <= end for x in lengths)
        print(f"  {start:3d}-{end:3d} | {'#' * count} {count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "mvp.json")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    seed = config["master_seed"]
    sel = config["selection"]

    chosen_maps, problem_rows, per_set = [], [], {}
    sanity_violations = 0

    for map_set in config["data"]["map_sets"]:
        all_names, good = eligible_maps(args.raw / map_set, map_set, sel)
        rng_maps = random.Random(derive_seed(seed, "select_maps", map_set))
        rng_maps.shuffle(good)

        accepted, rejected = [], []
        for name, map_path, scen_path, grid in good:
            if len(accepted) == sel["maps_per_set"]:
                break
            rng_probs = random.Random(derive_seed(seed, "select_problems", map_set, name))
            picks, stats = pick_problems(grid, load_scen(scen_path), sel, rng_probs)
            if len(picks) < sel["problems_per_map"]:
                rejected.append({"map_name": name, "qualifying_problems": len(picks), **stats})
                print(f"[{map_set}] reject {name}: only {len(picks)} qualifying problems")
                continue
            accepted.append(name)
            chosen_maps.append({
                "map_set": map_set,
                "map_name": name,
                "width": grid.width,
                "height": grid.height,
                "passable_pct": round(100 * grid.passable_count() / (grid.width * grid.height), 2),
                "map_file": map_path.relative_to(args.raw).as_posix(),
                "scen_file": scen_path.relative_to(args.raw).as_posix(),
                "problem_stats": stats,
            })
            for p, length in picks:
                if length < p.octile_length_unused - 1e-6:
                    sanity_violations += 1
                problem_rows.append({
                    "problem_id": f"{map_set}/{name}/{p.index}",
                    "map_set": map_set, "map_name": name, "scen_index": p.index,
                    "bucket": p.bucket, "sx": p.start[0], "sy": p.start[1],
                    "gx": p.goal[0], "gy": p.goal[1], "bfs_len": length,
                    "octile_length_unused": p.octile_length_unused,
                })
            print(f"[{map_set}] chose {name} ({grid.width}x{grid.height}), "
                  f"tried {stats['tried']} problems to get {len(picks)}")

        shortfall = sel["maps_per_set"] - len(accepted)
        per_set[map_set] = {"maps_in_set": len(all_names), "eligible": len(good),
                            "chosen": accepted, "rejected_for_problems": rejected,
                            "shortfall": shortfall}
        if shortfall > 0:
            print(f"WARNING [{map_set}]: only {len(accepted)} of {sel['maps_per_set']} maps "
                  f"could be chosen ({len(all_names)} maps in set, {len(good)} pass the "
                  f"size/passable filters). Filters were NOT changed.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"master_seed": seed, "selection": sel, "per_set": per_set, "maps": chosen_maps}
    (args.out_dir / "selected_maps.json").write_text(json.dumps(summary, indent=2))
    with open(args.out_dir / "selected_problems.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROBLEM_COLUMNS)
        writer.writeheader()
        writer.writerows(problem_rows)

    # Report.
    print(f"\n{len(chosen_maps)} maps, {len(problem_rows)} problems chosen")
    for map_set, info in per_set.items():
        lengths = sorted(r["bfs_len"] for r in problem_rows if r["map_set"] == map_set)
        if lengths:
            print(f"{map_set}: {len(info['chosen'])} maps, {len(lengths)} problems, BFS length "
                  f"min {lengths[0]} / median {lengths[len(lengths) // 2]} / max {lengths[-1]}")
    print("BFS length histogram (all chosen problems):")
    print_histogram([r["bfs_len"] for r in problem_rows], sel["min_bfs_len"], sel["max_bfs_len"])
    print(f"sanity check (bfs_len >= octile length): {sanity_violations} violations")
    print(f"wrote {args.out_dir / 'selected_maps.json'} and {args.out_dir / 'selected_problems.csv'}")


if __name__ == "__main__":
    main()
