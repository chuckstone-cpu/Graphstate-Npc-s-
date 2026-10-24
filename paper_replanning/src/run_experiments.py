"""Run every (problem, planner, prankster) combination and write the CSV logs.

    python -m src.run_experiments --config config/mvp.json
    python -m src.run_experiments --limit 2 --problems-per-map 3 --out-dir results/smoke

  --limit N             use only the first N selected maps of EACH map set
  --problems-per-map M  use only the first M selected problems of each map
  --workers W           worker processes (default: CPU cores - 1)

Output (in --out-dir, default results/):
  runs.csv    one row per run      (columns: src.sim.RUN_COLUMNS)
  events.csv  one row per block    (columns: src.sim.EVENT_COLUMNS)

  errors.csv  runs that raised an error (e.g. a sanity assert); the experiment carries on

The process asks Windows to stay awake (screen on) while it runs; see keep_windows_awake().
Results are appended as soon as each run finishes, so a crash loses only the runs
in progress. Re-running the same command RESUMES: run_ids already in runs.csv are
skipped. (Events of a run whose row never got written are removed first, so
nothing is counted twice.)
"""

import argparse
import csv
import json
import os
import random
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.maps import load_map                                       # noqa: E402
from src.planners import PLANNERS                                   # noqa: E402
from src.pranksters import PRANKSTER_NAMES                          # noqa: E402
from src.seeding import derive_seed                                 # noqa: E402
from src.sim import EVENT_COLUMNS, RUN_COLUMNS, make_run_id, run_one  # noqa: E402

# ---------- worker side ----------
_CONFIG = None
_MAP_CACHE = {}


def _init_worker(config):
    global _CONFIG
    _CONFIG = config


def _run_job(job):
    """Run one simulation in a worker process. job = (map_file, problem dict, planner, prankster).

    Returns ("ok", run_row, event_rows), or ("error", run_id, message) if the run raised
    (e.g. a sanity assert in sim.py fired). One bad run must not crash a 3-hour experiment:
    the error is written to errors.csv, and the run has no row in runs.csv, so it is retried
    on resume.
    """
    map_file, problem, planner_name, prankster_name = job
    try:
        if map_file not in _MAP_CACHE:
            _MAP_CACHE[map_file] = load_map(ROOT / "data" / "raw" / map_file)
        row, events = run_one(_MAP_CACHE[map_file], problem, planner_name, prankster_name, _CONFIG)
        return "ok", row, events
    except Exception as err:                                     # noqa: BLE001
        run_id = make_run_id(problem["problem_id"], planner_name, prankster_name)
        return "error", run_id, f"{type(err).__name__}: {err}\n{traceback.format_exc()}"


def keep_windows_awake():
    """Ask Windows not to sleep (or turn the screen off) while this process runs.

    This is a request from this process only, like a video player makes: it changes no
    settings, and Windows drops it automatically when the process exits. On "Modern
    Standby" laptops the machine sleeps when the screen goes off, so we keep the display on.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
    previous = ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
    return previous != 0                                         # 0 means the call failed


# ---------- main side ----------
def build_jobs(config, limit_maps, problems_per_map):
    """List every (map_file, problem, planner, prankster) job, in a seeded random order."""
    maps = json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]
    chosen, per_set = {}, {}
    for m in maps:                                  # keep the first N maps of each set
        if limit_maps is None or per_set.get(m["map_set"], 0) < limit_maps:
            per_set[m["map_set"]] = per_set.get(m["map_set"], 0) + 1
            chosen[(m["map_set"], m["map_name"])] = m["map_file"]
    jobs, per_map = [], {}
    with open(ROOT / "data" / "selected_problems.csv") as f:
        for r in csv.DictReader(f):
            key = (r["map_set"], r["map_name"])
            if key not in chosen:
                continue
            if problems_per_map is not None and per_map.get(key, 0) >= problems_per_map:
                continue
            per_map[key] = per_map.get(key, 0) + 1
            for planner in PLANNERS:
                for prankster in PRANKSTER_NAMES:
                    jobs.append((chosen[key], r, planner, prankster))
    # Shuffle so slow maps (room) are spread out and the progress-bar ETA is honest.
    random.Random(derive_seed(config["master_seed"], "job_order")).shuffle(jobs)
    return jobs


def done_run_ids(runs_path, events_path):
    """run_ids already finished, and drop orphan events (run row missing) from events.csv."""
    if not runs_path.exists():
        return set()
    with open(runs_path, newline="") as f:
        done = {r["run_id"] for r in csv.DictReader(f)}
    if events_path.exists():
        with open(events_path, newline="") as f:
            rows = list(csv.DictReader(f))
        kept = [r for r in rows if r["run_id"] in done]
        if len(kept) != len(rows):
            print(f"resume: removing {len(rows) - len(kept)} events of unfinished runs")
            with open(events_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=EVENT_COLUMNS)
                w.writeheader()
                w.writerows(kept)
    return done


def open_csv(path, columns):
    """Open a CSV for appending; write the header only if the file is new."""
    new = not path.exists() or path.stat().st_size == 0
    f = open(path, "a", newline="")
    w = csv.DictWriter(f, fieldnames=columns)
    if new:
        w.writeheader()
    return f, w


def print_sanity_tables(runs_path):
    """Pivot tables to eyeball after a run (needs pandas)."""
    import pandas as pd
    df = pd.read_csv(runs_path)
    order = list(PLANNERS)
    pd.set_option("display.width", 160)
    print(f"\n{len(df)} runs in {runs_path}")
    for col in ("replan_expansions_total", "replans", "max_single_replan_expansions"):
        print(f"\nmean {col}  (rows = planner, columns = prankster)")
        print(df.pivot_table(index="planner", columns="prankster", values=col, aggfunc="mean")
              .reindex(order)[PRANKSTER_NAMES].round(1).to_string())
    print("\nsuccess rate")
    print(df.pivot_table(index="planner", columns="prankster", values="success", aggfunc="mean")
          .reindex(order)[PRANKSTER_NAMES].to_string())
    print("\nruns per cell")
    print(df.pivot_table(index="planner", columns="prankster", values="run_id", aggfunc="count")
          .reindex(order)[PRANKSTER_NAMES].to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "mvp.json")
    parser.add_argument("--limit", type=int, default=None, help="first N maps of each set")
    parser.add_argument("--problems-per-map", type=int, default=None)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    runs_path, events_path = args.out_dir / "runs.csv", args.out_dir / "events.csv"

    jobs = build_jobs(config, args.limit, args.problems_per_map)
    done = done_run_ids(runs_path, events_path)
    todo = [j for j in jobs if make_run_id(j[1]["problem_id"], j[2], j[3]) not in done]
    print(f"{len(jobs)} runs in this config, {len(jobs) - len(todo)} already done, "
          f"{len(todo)} to run with {args.workers} workers")

    if todo:
        print("keep-awake request:", "on" if keep_windows_awake() else "not available")
        runs_f, runs_w = open_csv(runs_path, RUN_COLUMNS)
        events_f, events_w = open_csv(events_path, EVENT_COLUMNS)
        errors_f, errors_w = open_csv(args.out_dir / "errors.csv", ["run_id", "error"])
        n_errors = 0
        try:
            with Pool(args.workers, initializer=_init_worker, initargs=(config,)) as pool:
                bar = tqdm(pool.imap_unordered(_run_job, todo, chunksize=1),
                           total=len(todo), unit="run", smoothing=0.05)
                for status, *result in bar:
                    if status == "error":
                        n_errors += 1
                        errors_w.writerow({"run_id": result[0], "error": result[1]})
                        errors_f.flush()
                        bar.set_postfix(errors=n_errors)
                        continue
                    row, events = result
                    events_w.writerows(events)       # events first, then the run row:
                    events_f.flush()                 # a run counts as done only once its row exists
                    runs_w.writerow(row)
                    runs_f.flush()
        finally:
            runs_f.close()
            events_f.close()
            errors_f.close()
        if n_errors:
            print(f"\n{n_errors} runs FAILED with an error; see {args.out_dir / 'errors.csv'}")

    print_sanity_tables(runs_path)


if __name__ == "__main__":
    main()
