"""Re-run the runs with the longest planned paths and MEASURE their path lengths.

Why: D* Lite's current_path() used to stop at 2000 cells; the simulator now asks for
up to 10000 (see PATH_MAX_LEN in src/sim.py). This script checks that the change does
not alter any result, and measures how long the planned paths really get.

Which runs: after a run's last block the NPC walks an optimal route straight to the
goal, so the path right after the last block is exactly (steps - step of last block + 1)
cells long. That is a lower bound for the run's longest path; we re-run every run whose
lower bound is >= --min-len (default 1000).

Reference results = results/runs.csv and events.csv, with the runs that were cut off by
the step cap replaced by their re-runs in results/capped_reruns_*.csv (if not merged yet).
The re-runs use max_steps = --factor x opt + extra (default 30). Every column except the
timing columns must match exactly, including steps and success; events must match
exactly except time_ms.

Usage:  python scripts/verify_long_paths.py [--min-len 1000] [--factor 30]
"""

import argparse
import copy
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.maps import load_map                                      # noqa: E402
from src.run_experiments import keep_windows_awake                 # noqa: E402
from src.sim import EVENT_COLUMNS, PATH_MAX_LEN, RUN_COLUMNS       # noqa: E402

TIMING = ["replan_time_ms_total", "max_single_replan_ms", "initial_time_ms", "prankster_time_ms"]


def _job(args):
    """Run one simulation while recording the longest current_path() after every planner call."""
    import src.sim as sim
    map_file, problem, planner, prankster, config = args
    longest = [0]
    real_make = sim.make_planner

    def make_tracked(name):
        p = real_make(name)
        for method in ("init", "on_move", "on_change"):
            orig = getattr(p, method)

            def wrapped(*a, _orig=orig):
                _orig(*a)
                longest[0] = max(longest[0], len(p.current_path(max_len=PATH_MAX_LEN)))
            setattr(p, method, wrapped)
        return p

    sim.make_planner = make_tracked
    row, events = sim.run_one(load_map(ROOT / "data" / "raw" / map_file), problem, planner, prankster, config)
    return row, events, longest[0]


def reference_results(results):
    """runs/events with the capped runs replaced by their re-runs (no-op once merged)."""
    runs = pd.read_csv(results / "runs.csv").set_index("run_id")
    events = pd.read_csv(results / "events.csv")
    rerun_path = results / "capped_reruns_runs.csv"
    if rerun_path.exists():
        rr = pd.read_csv(rerun_path).set_index("run_id")
        rr_ev = pd.read_csv(results / "capped_reruns_events.csv")
        if not runs.loc[rr.index, "success"].all():               # not merged yet
            runs.loc[rr.index] = rr[runs.columns]
            events = pd.concat([events[~events.run_id.isin(rr.index)], rr_ev], ignore_index=True)
    return runs, events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-len", type=int, default=1000)
    parser.add_argument("--factor", type=int, default=30)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    results = ROOT / "results"

    config = json.loads((ROOT / "config" / "mvp.json").read_text())
    new_config = copy.deepcopy(config)
    new_config["sim"]["max_steps_factor"] = args.factor
    runs, events = reference_results(results)

    last_block = events.groupby("run_id").step.max()
    lower_bound = (runs.loc[last_block.index, "steps"] - last_block + 1).sort_values(ascending=False)
    chosen = lower_bound[lower_bound >= args.min_len]
    print(f"{len(chosen)} runs with a path lower bound >= {args.min_len} cells "
          f"(re-running with max_steps = {args.factor} x opt + {config['sim']['max_steps_extra']}, "
          f"current_path max_len = {PATH_MAX_LEN})")

    probs = pd.read_csv(ROOT / "data" / "selected_problems.csv").set_index("problem_id")
    maps = {(m["map_set"], m["map_name"]): m["map_file"]
            for m in json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]}
    jobs = []
    for run_id in chosen.index:
        r = runs.loc[run_id]
        problem = probs.loc[r.problem_id].to_dict()
        problem["problem_id"] = r.problem_id
        jobs.append((maps[(r.map_set, r.map_name)], problem, r.planner, r.prankster, new_config))

    keep_windows_awake()
    with Pool(args.workers) as pool:
        out = pool.map(_job, jobs, chunksize=1)

    # Same CSV round-trip as the real results, so types match exactly.
    tmp_runs, tmp_events = results / "_verify_runs.csv", results / "_verify_events.csv"
    pd.DataFrame([o[0] for o in out], columns=RUN_COLUMNS).to_csv(tmp_runs, index=False)
    pd.DataFrame([e for o in out for e in o[1]], columns=EVENT_COLUMNS).to_csv(tmp_events, index=False)
    new_runs = pd.read_csv(tmp_runs).set_index("run_id")
    new_events = pd.read_csv(tmp_events)
    tmp_runs.unlink()
    tmp_events.unlink()

    old_runs = runs.loc[new_runs.index]
    must_match = [c for c in RUN_COLUMNS if c not in TIMING + ["run_id"]]
    bad_cols = [c for c in must_match if not old_runs[c].equals(new_runs[c])]
    ev_cols = [c for c in EVENT_COLUMNS if c != "time_ms"]
    key = ["run_id", "step", "block_x", "block_y"]
    old_ev = events[events.run_id.isin(new_runs.index)][ev_cols].sort_values(key).reset_index(drop=True)
    new_ev = new_events[ev_cols].sort_values(key).reset_index(drop=True)

    measured = pd.Series({o[0]["run_id"]: o[2] for o in out}).loc[new_runs.index]
    table = pd.DataFrame({"lower_bound": chosen.loc[new_runs.index], "measured_longest": measured,
                          "steps": new_runs.steps, "success": new_runs.success})
    print(table.sort_values("measured_longest", ascending=False).head(10).to_string())
    print(f"\nrun columns that must match ({len(must_match)}, incl. steps and success): "
          + ("ALL IDENTICAL" if not bad_cols else f"DIFFERENT in {bad_cols}"))
    print(f"events ({len(old_ev)} old vs {len(new_ev)} new, without time_ms): "
          + ("ALL IDENTICAL" if old_ev.equals(new_ev) else "DIFFERENT"))
    print(f"measured >= lower bound in every run: {bool((measured >= table.lower_bound).all())}")
    print(f"LONGEST current_path() MEASURED: {measured.max()} cells "
          f"(old limit 2000, new limit {PATH_MAX_LEN}); runs >= 2000: {(measured >= 2000).sum()}, "
          f">= 1800: {(measured >= 1800).sum()}")


if __name__ == "__main__":
    main()
