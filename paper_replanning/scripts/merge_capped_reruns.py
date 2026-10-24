"""Merge the re-runs of step-capped runs (results/capped_reruns_*.csv) into runs.csv / events.csv.

Only run this after scripts/rerun_capped.py (and scripts/verify_long_paths.py) showed the
re-runs are identical to the originals apart from steps, success and timings.

What it does:
  1. backs up runs.csv and events.csv to results/backup/ (refuses to overwrite a backup),
  2. replaces each capped run's row with its re-run row (only rows that really hit the
     main run's cap: success False and steps == factor * opt + extra),
  3. removes those runs' old events and adds the re-run events (no duplicates),
  4. checks: 5760 unique run_ids, all success, no duplicate events, every other row
     byte-for-byte unchanged, errors.csv empty.

It works on the CSV text (csv module), so untouched rows are written back exactly as they were.

Usage:  python scripts/merge_capped_reruns.py
"""

import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
EVENT_KEY = ("run_id", "step", "block_x", "block_y")


def read_csv(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def main():
    config = json.loads((ROOT / "config" / "mvp.json").read_text())
    factor, extra = config["sim"]["max_steps_factor"], config["sim"]["max_steps_extra"]

    run_cols, runs = read_csv(RESULTS / "runs.csv")
    ev_cols, events = read_csv(RESULTS / "events.csv")
    rr_cols, reruns = read_csv(RESULTS / "capped_reruns_runs.csv")
    rre_cols, rerun_events = read_csv(RESULTS / "capped_reruns_events.csv")
    assert rr_cols == run_cols and rre_cols == ev_cols, "column mismatch"
    rerun_by_id = {r["run_id"]: r for r in reruns}

    # Check every re-run replaces a row that really hit the main run's cap.
    by_id = {r["run_id"]: r for r in runs}
    for run_id in rerun_by_id:
        old = by_id[run_id]
        cap = factor * int(old["opt_len_initial"]) + extra
        if old["success"] != "False" or int(old["steps"]) != cap:
            sys.exit(f"STOP: {run_id} is not a capped run (already merged?). Nothing changed.")

    backup = RESULTS / "backup"
    backup.mkdir(exist_ok=True)
    for name in ("runs.csv", "events.csv"):
        target = backup / name.replace(".csv", "_before_merge.csv")
        if target.exists():
            sys.exit(f"STOP: backup {target} already exists. Nothing changed.")
        shutil.copy2(RESULTS / name, target)
    print(f"backed up runs.csv and events.csv to {backup}")

    merged_runs = [rerun_by_id.get(r["run_id"], r) for r in runs]        # same order as before
    kept_events = [e for e in events if e["run_id"] not in rerun_by_id]
    merged_events = kept_events + rerun_events
    write_csv(RESULTS / "runs.csv", run_cols, merged_runs)
    write_csv(RESULTS / "events.csv", ev_cols, merged_events)

    # ---- checks ----
    ids = [r["run_id"] for r in merged_runs]
    ev_keys = [tuple(e[k] for k in EVENT_KEY) for e in merged_events]
    _, before = read_csv(backup / "runs_before_merge.csv")
    unchanged = all(a == b for a, b in zip(before, merged_runs) if a["run_id"] not in rerun_by_id)
    _, errors = read_csv(RESULTS / "errors.csv")
    print(f"replaced {len(rerun_by_id)} run rows; events: removed "
          f"{len(events) - len(kept_events)}, added {len(rerun_events)}")
    print(f"runs.csv rows: {len(merged_runs)}  unique run_ids: {len(set(ids))}")
    print(f"all success=True: {all(r['success'] == 'True' for r in merged_runs)}")
    print(f"events.csv rows: {len(merged_events)} (before: {len(events)})  "
          f"duplicate events: {len(ev_keys) - len(set(ev_keys))}")
    print(f"all other {len(merged_runs) - len(rerun_by_id)} run rows unchanged: {unchanged}")
    print(f"errors.csv rows: {len(errors)}")


if __name__ == "__main__":
    main()
