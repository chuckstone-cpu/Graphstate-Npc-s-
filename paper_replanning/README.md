# Replanning Against a Saboteur

Research code for the Outwit project, phase 2 (Fundamentals of AI).

**Question.** When an opponent deliberately blocks an NPC's route (a *saboteur*), does incremental
replanning (D* Lite) still save search effort compared with replanning from scratch (A*, BFS), and
compared with a *lazy* A* that replans only when its path is actually broken? We test this on real
game maps from the Moving AI benchmarks and report whatever happens.

The search code is a line-by-line Python port of the Godot game's GDScript (`../scripts/search/`).

## Setup (Windows, Python 3.10+)

```
cd paper_replanning
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Running (stage 1: data)

```
python scripts/download_maps.py      # downloads + extracts maps/scenarios into data/raw/
python scripts/survey_maps.py        # writes results/tables/map_survey.csv
python scripts/select_problems.py    # writes data/selected_maps.json, data/selected_problems.csv
python -m pytest                     # unit tests
```

All parameters (map sets, filters, seed) live in `config/mvp.json`.

## Data

Maps and scenarios come from the Moving AI Lab 2D pathfinding benchmarks
(<https://www.movingai.com/benchmarks/>), released under the **Open Data Commons Attribution
License (ODC-By)**. Please cite:

> N. Sturtevant, "Benchmarks for Grid-Based Pathfinding," *IEEE Transactions on Computational
> Intelligence and AI in Games*, 4(2):144–148, 2012.

The raw downloads (`data/raw/`) are not committed; run `scripts/download_maps.py` to fetch them.

### Modelling choices you should know about

- **Passable cells are only `.`, `G` and `S`.** Every other character (`@`, `O`, `T`, `W`) is blocked.
  This means **water (`W`) is treated as blocked**, a simplification. Moving AI lets some units
  cross water.
- Our NPC moves **4-connected** (right, left, down, up), each step costs 1, and the heuristic is
  Manhattan distance, just like in the game. The scenario files' "optimal length" column is an
  **octile** (8-connected) length, so we never use it. We only take start/goal pairs from the
  scenario files and compute our own 4-connected shortest length with BFS.

### Map selection

Per set we pick 8 maps with max side ≤ 256 and ≥ 30% passable cells, except the `room` set,
where every map is 512×512, so its size limit is raised to 512 (`max_side_overrides` in
`config/mvp.json`). Per map we pick 15 scenario problems whose 4-connected BFS length is 60–250
moves. Maps that cannot supply 15 such problems are skipped (they are listed in
`data/selected_maps.json`).

### Step limit per trip (caps actually used)

A run stops after `max_steps = factor × opt_len + 100` agent steps (`config/mvp.json`, "sim").
Every change event happens by step 150 (30 blocks, one every 5 steps), long before any cap, so
the cap can only cut off the final walk to the goal. It never changes the blocks, the replans or
the expansion counts.

- **Main run (all 5760 runs): `10 × opt_len + 100`.** The first version used `4 × opt_len + 100`,
  but in the smoke run the saboteur's detours on room maps reached 6–7× the optimum: by closing
  doorways it forced the NPC around whole rooms.
- **52 runs still hit the 10× cap** (all saboteur, all on room maps; trips of 10.6–23.6× the
  optimum). They were re-run with **`30 × opt_len + 100`** (`scripts/rerun_capped.py`) and all
  reached the goal. Runs are deterministic (same seeds, same blocks), and the re-runs matched the
  originals **exactly** in every count column and every event; only `steps`, `success` and the
  re-measured timings differed. They were then merged into `runs.csv`/`events.csv`
  (`scripts/merge_capped_reruns.py`; the pre-merge files are in `results/backup/`). After the
  merge all 5760 runs have `success = True`.

### Planned-path length limit

The game's D* Lite `current_path()` stops after `max_len = 2000` cells. The port keeps that
default, but `src/sim.py` asks for up to 10000 (`PATH_MAX_LEN`), because saboteur detours on the
room map `64room_009` produced planned paths of up to **1999 cells**, measured by
`scripts/verify_long_paths.py`. The change does not alter any result: the simulator asserts that
every path it uses is complete, that assert never fired, and re-running the 67 runs with the
longest paths under the new limit reproduced every count column and every event exactly.

### Paper

`paper/` holds the IEEE-format LaTeX paper (`main.tex`, `refs.bib`, `figures/`, `tables/`).
The tables are generated from the analysis output, never typed by hand:

```
python analysis/analyze.py          # results/tables, results/figures, results/SUMMARY.md
python paper/make_tables.py         # paper/tables/*.tex
```

Then copy `results/figures/*.pdf` to `paper/figures/` and upload `paper/overleaf_upload.zip` to
Overleaf (New Project -> Upload Project; compiler pdfLaTeX). `paper/main.pdf` is a preview built
locally with Tectonic (XeTeX engine); Overleaf's pdfLaTeX output may differ by a line or two.

### Timing

Expansions (cells taken out of the open list) are the main metric because they do not depend on the
machine. Wall-clock times use `time.perf_counter_ns` and are secondary: Python timing is noisy.
