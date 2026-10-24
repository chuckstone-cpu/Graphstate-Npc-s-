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

### Timing

Expansions (cells taken out of the open list) are the main metric because they do not depend on the
machine. Wall-clock times use `time.perf_counter_ns` and are secondary: Python timing is noisy.
