"""Speed check: how long do single searches take, and how long would the full MVP run take?

The simulator and pranksters do not exist yet, so we cannot time real runs.
Instead we time the building blocks on the selected problems and add them up:

  t_bfs, t_astar, t_dstar   mean time of ONE full search (start -> goal) per map set
  E = min(B, trip_length / K)   change events per run (K = act every K steps, B = max blocks)

  per run, NPC work:
    bfs_restart    (1 + E * f) * t_bfs
    astar_restart  (1 + E * f) * t_astar
    astar_lazy     <= astar_restart (it replans only when its path is hit)
    dstar_lite     t_dstar + E * f * t_astar   (crude upper bound for repairs; usually far less)
  per run, prankster work (real time, but not counted as NPC work):
    none           0
    random_*       E * t_bfs                    (one reachability check per act)
    saboteur       E * (C * t_astar + t_bfs)    (C candidate A* searches + one check per act)

f is the average cost of a replan relative to a full search. The agent walks
toward the goal, so replans get cheaper; we report f = 0.5 (typical) and
f = 1.0 (pessimistic). The parallel speed-up is measured, not assumed.

Usage:  python scripts/speed_check.py [--per-map 3] [--workers N]
"""

import argparse
import csv
import json
import os
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.maps import load_map                    # noqa: E402
from src.search import astar, bfs                # noqa: E402
from src.search.dstar_lite import DStarLite      # noqa: E402

PLANNERS = ["bfs_restart", "astar_restart", "astar_lazy", "dstar_lite"]
PRANKSTERS = ["none", "random_global", "random_local", "saboteur"]


def time_problem(task):
    """Time one BFS, one A* and one D* Lite initial search for one problem."""
    map_path, s, t = task
    grid = load_map(map_path)
    blocked = lambda p: grid.is_blocked(p[0], p[1])     # noqa: E731
    out = {}
    t0 = time.perf_counter_ns()
    out["bfs_exp"] = bfs.search(grid.width, grid.height, blocked, s, t)["expanded"]
    t1 = time.perf_counter_ns()
    out["astar_exp"] = astar.search(grid.width, grid.height, blocked, s, t)["expanded"]
    t2 = time.perf_counter_ns()
    ds = DStarLite(grid.width, grid.height, blocked, s, t)
    ds.compute_shortest_path()
    t3 = time.perf_counter_ns()
    out["dstar_exp"] = ds.expanded_last
    out["t_bfs"], out["t_astar"], out["t_dstar"] = (t1 - t0) / 1e9, (t2 - t1) / 1e9, (t3 - t2) / 1e9
    return out


def load_tasks(per_map):
    maps = {(m["map_set"], m["map_name"]): m for m in
            json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]}
    tasks, rows, taken = [], [], {}
    with open(ROOT / "data" / "selected_problems.csv") as f:
        all_rows = list(csv.DictReader(f))
    for r in all_rows:
        key = (r["map_set"], r["map_name"])
        if taken.get(key, 0) < per_map:
            taken[key] = taken.get(key, 0) + 1
            path = ROOT / "data" / "raw" / maps[key]["map_file"]
            tasks.append((path, (int(r["sx"]), int(r["sy"])), (int(r["gx"]), int(r["gy"]))))
            rows.append(r)
    return tasks, rows, all_rows, maps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-map", type=int, default=3)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    config = json.loads((ROOT / "config" / "mvp.json").read_text())
    K = config["prankster"]["act_every_k_steps"]
    B = config["prankster"]["max_blocks_per_run"]
    C = config["prankster"]["saboteur_candidates"]

    tasks, rows, all_rows, maps = load_tasks(args.per_map)
    print(f"timing {len(tasks)} problems ({args.per_map} per map), single process...")
    t0 = time.perf_counter()
    results = [time_problem(task) for task in tasks]
    serial_s = time.perf_counter() - t0

    # 1) single-search timings, per set, and on the largest map
    by_set = {}
    for r, res in zip(rows, results):
        by_set.setdefault(r["map_set"], []).append((r, res))
    print(f"\n{'set':7} {'n':>3} {'BFS ms':>8} {'A* ms':>8} {'D* ms':>8}   {'BFS exp':>8} {'A* exp':>8} {'D* exp':>8}")
    means = {}
    for map_set, items in by_set.items():
        m = {k: statistics.mean(res[k] for _, res in items)
             for k in ("t_bfs", "t_astar", "t_dstar", "bfs_exp", "astar_exp", "dstar_exp")}
        means[map_set] = m
        print(f"{map_set:7} {len(items):3} {1e3 * m['t_bfs']:8.1f} {1e3 * m['t_astar']:8.1f} "
              f"{1e3 * m['t_dstar']:8.1f}   {m['bfs_exp']:8.0f} {m['astar_exp']:8.0f} {m['dstar_exp']:8.0f}")

    largest = max(maps.values(), key=lambda m: (m["width"] * m["height"], m["passable_pct"]))
    print(f"\nlargest selected map: {largest['map_set']}/{largest['map_name']} "
          f"({largest['width']}x{largest['height']}, {largest['passable_pct']}% passable)")
    for r, res in zip(rows, results):
        if r["map_name"] == largest["map_name"]:
            print(f"  problem {r['problem_id']} (BFS len {r['bfs_len']}): "
                  f"A* {1e3 * res['t_astar']:.1f} ms / {res['astar_exp']} exp, "
                  f"D* Lite {1e3 * res['t_dstar']:.1f} ms / {res['dstar_exp']} exp, "
                  f"BFS {1e3 * res['t_bfs']:.1f} ms / {res['bfs_exp']} exp")

    # 2) measured parallel speed-up on the same work
    print(f"\nsame work with {args.workers} worker processes...")
    t0 = time.perf_counter()
    with Pool(args.workers) as pool:
        pool.map(time_problem, tasks, chunksize=1)
    parallel_s = time.perf_counter() - t0
    speedup = serial_s / parallel_s
    print(f"  serial {serial_s:.1f} s, parallel {parallel_s:.1f} s -> speed-up {speedup:.1f}x")

    # 3) estimate of the full MVP run, problem by problem (uses every selected problem's length)
    print(f"\nestimate for the full run: {len(all_rows)} problems x {len(PLANNERS)} planners "
          f"x {len(PRANKSTERS)} pranksters = {len(all_rows) * 16} runs")
    for f_label, f in (("typical f=0.5", 0.5), ("pessimistic f=1.0", 1.0)):
        total = {p: 0.0 for p in PRANKSTERS}
        for r in all_rows:
            m = means[r["map_set"]]
            E = min(B, int(r["bfs_len"]) // K)
            for prank in PRANKSTERS:
                e = 0 if prank == "none" else E
                npc = ((1 + e * f) * m["t_bfs"] + 2 * (1 + e * f) * m["t_astar"]
                       + m["t_dstar"] + e * f * m["t_astar"])
                prank_cost = {"none": 0, "random_global": e * m["t_bfs"], "random_local": e * m["t_bfs"],
                              "saboteur": e * (C * m["t_astar"] + m["t_bfs"])}[prank]
                total[prank] += npc + 4 * prank_cost       # the prankster acts in all 4 planners' runs
        serial_h = sum(total.values()) / 3600
        print(f"  {f_label:18}: serial {serial_h:5.1f} h -> with {args.workers} workers "
              f"~{serial_h / speedup:4.1f} h   (by prankster, serial h: "
              + ", ".join(f"{p} {v / 3600:.1f}" for p, v in total.items()) + ")")


if __name__ == "__main__":
    main()
