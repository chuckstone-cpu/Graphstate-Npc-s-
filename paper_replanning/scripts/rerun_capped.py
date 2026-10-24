"""Re-run the runs that were cut off by the step cap, with a larger cap, and check
that nothing else changes.

Why this is valid: a run is deterministic (same map, problem, planner and prankster
seed -> same blocks, same searches). All B blocks are placed by step K * B (= 150),
long before any cap, so a larger cap only lets the NPC finish its walk. Every count
(expansions, replans, blocks, events) must therefore come out IDENTICAL; only
`steps` and `success` may differ. Timing columns are re-measured, so they differ by noise.

Reads   results/runs.csv, results/events.csv
Writes  results/capped_reruns_runs.csv, results/capped_reruns_events.csv
It does NOT change runs.csv / events.csv.

Usage:  python scripts/rerun_capped.py [--factor 30] [--workers N]
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
from src.sim import EVENT_COLUMNS, RUN_COLUMNS, run_one            # noqa: E402

TIMING_RUN_COLUMNS = ["replan_time_ms_total", "max_single_replan_ms", "initial_time_ms",
                      "prankster_time_ms"]
ALLOWED_TO_DIFFER = ["steps", "success"]


def _job(args):
    map_file, problem, planner, prankster, config = args
    return run_one(load_map(ROOT / "data" / "raw" / map_file), problem, planner, prankster, config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor", type=int, default=30, help="new max_steps_factor")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--old-factor", type=int, default=None,
                        help="cap factor the runs were made with (default: the one in the config)")
    args = parser.parse_args()

    config = json.loads((ROOT / "config" / "mvp.json").read_text())
    old_f = args.old_factor or config["sim"]["max_steps_factor"]
    extra = config["sim"]["max_steps_extra"]
    out = args.results_dir
    runs = pd.read_csv(out / "runs.csv")
    events = pd.read_csv(out / "events.csv")

    capped = runs[(~runs.success) & (runs.steps == old_f * runs.opt_len_initial + extra)]
    other_failures = runs[(~runs.success) & ~runs.run_id.isin(capped.run_id)]
    print(f"{len(runs)} runs, {len(capped)} cut off by the cap ({old_f} x opt + {extra}), "
          f"{len(other_failures)} failed for another reason")
    if len(other_failures):
        print(other_failures[["run_id", "steps", "opt_len_initial"]].to_string(index=False))
    if capped.empty:
        return

    # Same config except the cap.
    new_config = copy.deepcopy(config)
    new_config["sim"]["max_steps_factor"] = args.factor
    probs = pd.read_csv(ROOT / "data" / "selected_problems.csv").set_index("problem_id")
    maps = {(m["map_set"], m["map_name"]): m["map_file"]
            for m in json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]}
    jobs = []
    for r in capped.itertuples():
        problem = probs.loc[r.problem_id].to_dict()
        problem["problem_id"] = r.problem_id
        jobs.append((maps[(r.map_set, r.map_name)], problem, r.planner, r.prankster, new_config))

    keep_windows_awake()                     # these are the slowest runs; don't let the laptop sleep
    print(f"re-running them with max_steps = {args.factor} x opt + {extra} on {args.workers} workers...")
    with Pool(args.workers) as pool:
        results = pool.map(_job, jobs, chunksize=1)

    new_runs = pd.DataFrame([row for row, _ in results], columns=RUN_COLUMNS)
    new_events = pd.DataFrame([e for _, evs in results for e in evs], columns=EVENT_COLUMNS)
    new_runs.to_csv(out / "capped_reruns_runs.csv", index=False)
    new_events.to_csv(out / "capped_reruns_events.csv", index=False)
    # Read them back so both sides have exactly the same CSV types.
    new_runs = pd.read_csv(out / "capped_reruns_runs.csv").set_index("run_id")
    new_events = pd.read_csv(out / "capped_reruns_events.csv")
    old_runs = capped.set_index("run_id").loc[new_runs.index]

    # 1) run rows: every column except steps/success/timings must be identical.
    must_match = [c for c in RUN_COLUMNS
                  if c not in ALLOWED_TO_DIFFER + TIMING_RUN_COLUMNS + ["run_id"]]
    diff_cols = [c for c in must_match if not old_runs[c].equals(new_runs[c])]

    # 2) events: same blocks at the same steps with the same expansions (time_ms is re-measured).
    ev_cols = [c for c in EVENT_COLUMNS if c != "time_ms"]
    key = ["run_id", "step", "block_x", "block_y"]
    old_ev = events[events.run_id.isin(new_runs.index)][ev_cols].sort_values(key).reset_index(drop=True)
    new_ev = new_events[ev_cols].sort_values(key).reset_index(drop=True)
    events_identical = old_ev.equals(new_ev)

    print("\nper run:")
    cap_new = args.factor * old_runs.opt_len_initial + extra
    table = pd.DataFrame({
        "opt": old_runs.opt_len_initial, "old_steps (cap)": old_runs.steps,
        "new_steps": new_runs.steps, "new_cap": cap_new,
        "new/opt": (new_runs.steps / old_runs.opt_len_initial).round(2),
        "success": new_runs.success,
        "counts identical": (old_runs[must_match] == new_runs[must_match]).all(axis=1),
    })
    print(table.to_string())

    print(f"\nrun columns that must match ({len(must_match)}): "
          + ("ALL IDENTICAL" if not diff_cols else f"DIFFERENT in {diff_cols}"))
    print(f"events ({len(old_ev)} old vs {len(new_ev)} new, compared on {ev_cols}): "
          + ("ALL IDENTICAL" if events_identical else "DIFFERENT"))
    print(f"all re-runs reach the goal: {bool(new_runs.success.all())}")
    print("timing columns (re-measured, expected to differ): median |old - new| / old =",
          {c: round(float(((old_runs[c] - new_runs[c]).abs() / old_runs[c].clip(lower=1e-9)).median()), 3)
           for c in TIMING_RUN_COLUMNS})


if __name__ == "__main__":
    main()
