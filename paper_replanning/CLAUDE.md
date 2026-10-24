# Replanning Against a Saboteur — research code (Outwit phase 2)

You are helping a 2nd-year AI student (Amrita, Fundamentals of AI course) build the experiments for a
research paper. The student will read and defend every line in a viva, so code must be simple,
heavily commented in plain English, and honest. A separate reviewer (another Claude) critiques your
results, so never fabricate or "smooth" numbers.

## Research question (do not change it)
When the map is changed by an opponent who **deliberately blocks the NPC's route** (a saboteur),
does incremental replanning (D* Lite) still save search effort compared with replanning from scratch
(A*, BFS) — and compared with a *lazy* A* that only replans when its path is actually broken?
We test on **real game maps** (Moving AI benchmarks). No expected outcome: report whatever happens.

## Where things live
- Repo: this git repository. Work ONLY inside `paper_replanning/`. Never edit the Godot game
  (`project.godot`, `scripts/`, `levels/`, `assets/`, `tests/` at repo root, or an `outwit/` folder).
- The Godot game's search code (the source of truth to port) is in `scripts/search/*.gd`
  (`pq.gd`, `grid_utils.gd`, `bfs.gd`, `astar.gd`, `dstar_lite.gd`) and `tests/run_tests.gd`,
  plus `levels/level1.txt`. If they are not at the repo root, search the repo for `dstar_lite.gd`.
- Layout to create:
```
paper_replanning/
  CLAUDE.md               (this file)
  README.md               (how to run everything; data licence + citation)
  requirements.txt        (pandas, scipy, matplotlib, pytest, tqdm)
  config/mvp.json         (all experiment parameters + seed)
  scripts/download_maps.py, scripts/survey_maps.py, scripts/select_problems.py
  src/maps.py             (load .map/.scen)
  src/search/pq.py, grid_utils.py, bfs.py, astar.py, dstar_lite.py   (literal ports)
  src/planners.py         (common wrapper: BFS-restart, A*-restart, A*-lazy, D* Lite)
  src/pranksters.py       (change models)
  src/sim.py              (one run = one NPC trip)
  src/run_experiments.py  (all runs, multiprocessing, writes CSVs)
  analysis/analyze.py     (stats, figures, tables, SUMMARY.md)
  tests/                  (pytest)
  data/raw/               (downloads — gitignored)
  data/selected_maps.json, data/selected_problems.csv   (small, committed)
  results/                (runs.csv, events.csv, figures/, tables/, SUMMARY.md)
  paper/                  (LaTeX, later)
```
- Add `paper_replanning/.gitignore` with `data/raw/`, `__pycache__/`, `.venv/`, `.pytest_cache/`,
  and `results/events.csv` if it is larger than 50 MB.

## Environment
Windows laptop, Python 3.10+. Use a venv in `paper_replanning/.venv`. Only stdlib for the search
code; pandas/scipy/matplotlib only in analysis. Any multiprocessing entry point must be under
`if __name__ == "__main__":` (Windows spawn). Use `pathlib` for paths.

## Data: Moving AI 2D grid benchmarks (Sturtevant 2012, Open Data Commons Attribution License)
- Download URLs (maps + scenarios), MVP sets = `dao`, `street`, `room`:
  `https://www.movingai.com/benchmarks/<set>/<set>-map.zip` and `.../<set>/<set>-scen.zip`
  (other sets available later: da2, sc1, wc3maps512, bgmaps, maze, random).
- `.map` format: lines `type octile`, `height H`, `width W`, `map`, then H rows of W chars,
  (0,0) top-left. **Passable: `.` `G` `S`. Blocked: everything else (`@ O T W`).** (We treat water
  as blocked for simplicity — document this in README.)
- `.scen` format: first line `version 1`, then 9 columns: bucket, map path, map width, map height,
  start x, start y, goal x, goal y, optimal length. **The given optimal length is OCTILE (diagonal
  moves). Our NPC moves 4-connected, so NEVER use that column as ground truth** — use scen files
  only as a source of start/goal pairs, and compute our own 4-connected shortest length with BFS.
- Citation: N. Sturtevant, "Benchmarks for Grid-Based Pathfinding," IEEE TCIAIG 4(2):144–148, 2012.

## The grid model (identical to the game)
4-connected moves (right, left, down, up — in exactly that order, as in `grid_utils.gd`), every step
costs 1, coordinates are (x, y), heuristic = Manhattan distance. A cell outside the map is blocked.

## Algorithms — LITERAL ports of the GDScript
- Port `pq.gd` as-is (custom binary heap comparing only (k1, k2); lazy deletion via the `open`
  dict in D* Lite). **Do not use `heapq` or tuples that compare coordinates** — tie-breaking must
  match the game so expansion counts match exactly.
- Port `bfs.gd`, `astar.gd` (key = (f, h)), `dstar_lite.gd` (g/rhs/km, `move_start`,
  `notify_changed`, `compute_shortest_path`, `next_step`, `current_path`) line by line, keeping
  the comments. Count an "expansion" exactly where the GDScript does.
- The ports are correct only if `tests/test_port_matches_game.py` reproduces the game's numbers on
  `levels/level1.txt` (start = `G`, goal = `T`):
  - BFS: path 28 cells, 190 expansions. A*: path 28 cells, 67 expansions. D* Lite: 75 expansions,
    g(start) = 27.
  - Wall-drop test from `run_tests.gd` (walk 4 D* steps, block `current_path()[3]`, notify,
    recompute): blocked cell is (6, 3); repaired path = 24 cells = fresh A* path; D* Lite repair = 3
    expansions vs fresh A* = 58.
  - Plus: on 40 random 20×15 maps (22% walls, seed 42) with 3 random cell flips per step,
    D* Lite's g(agent) always equals a fresh A* cost (port of test [3]).
  If numbers differ, fix the port; never edit the expected numbers.

## Planners compared (src/planners.py, common interface)
All planners plan on the CURRENT true grid (changes are announced to the NPC the moment they
happen — full knowledge; partial sensing is a later scenario).
1. `bfs_restart`: re-run BFS from the agent after every change event.
2. `astar_restart`: re-run A* from the agent after every change event.
3. `astar_lazy`: keep the current path; re-run A* only if a newly blocked cell lies on the
   remaining path. (Strong baseline: blocking-only changes cannot create a shorter route, so an
   untouched path stays optimal.)
4. `dstar_lite`: one D* Lite instance per run; `move_start` every step; `notify_changed` +
   `compute_shortest_path` on change events.
Count expansions inside the search code only (prankster computations never count).

## Change models ("pranksters", src/pranksters.py) — blocking only, never unblocking
- `none`: no changes (control; replans should be ~0).
- `random_global`: uniform random free cell anywhere on the map (what older papers do).
- `random_local`: uniform random free cell within Chebyshev radius R=8 of the agent
  (separates "near the agent" from "on purpose").
- `saboteur` (greedy interdiction, the new one): take the NPC's current planned path, sample up to
  C=12 cells evenly spaced from index 2 to the cell before the goal; for each, tentatively block it
  and run the saboteur's OWN A* from agent to goal; choose the cell that increases the trip cost the
  most (ties → closer to the agent). Its searches are not counted as NPC work.
Common rules: act every K=5 agent steps, at most B=30 blocks per run, never block the agent's cell,
the goal, or a cell that disconnects agent from goal (check with BFS; if it would, try the next
candidate / redraw, max 20 tries, else skip this turn). Each prankster uses its own
`random.Random(seed)` seeded from (master seed, map, problem) so runs are reproducible.

## One run (src/sim.py) — exact order
```
grid = fresh copy of map; agent = start; planner.init(grid, start, goal); initial plan (count it
separately as 'initial_expansions')
steps = 0; max_steps = 4 * initial_optimal_length + 100
while agent != goal and steps < max_steps:
    nxt = planner.next_step()            # None => fail (should not happen: reachability kept)
    agent = nxt; steps += 1
    if steps % K == 0 and blocks < B:
        changed = prankster.act(grid, agent, goal, planner.current_path())  # list of cells
        if changed: apply to grid; planner.on_change(agent, changed)  -> timed, expansions logged
    else:
        planner.on_move(agent)           # D* Lite move_start; others nothing (count any work)
```
Fairness: identical maps, problems, seeds and rules for every planner. The saboteur reacts to each
planner's own path (realistic: the opponent watches the NPC), so trajectories may differ slightly —
report path length so this is visible.

## Logs
`results/runs.csv` (one row per run): run_id, map_set, map_name, width, height, problem_id, sx, sy,
gx, gy, opt_len_initial, planner, prankster, seed, success, steps, blocks_placed,
initial_expansions, replan_expansions_total, replans, max_single_replan_expansions,
replan_time_ms_total, max_single_replan_ms.
`results/events.csv` (one row per change event): run_id, step, planner, prankster, block_x, block_y,
dist_block_agent (Manhattan), dist_block_goal, on_planner_path (bool), expansions, time_ms.
Expansions are the primary metric (machine-independent); time is secondary (Python is noisy —
use `time.perf_counter_ns`, and say so in README).

## Analysis (analysis/analyze.py) — report, don't spin
- Table: mean ± 95% CI (bootstrap, 2000 resamples, seed) of replan_expansions_total and of
  max_single_replan_expansions, per planner × prankster, overall and per map set.
- Paired comparison per (problem, prankster): D* Lite vs astar_lazy and vs astar_restart —
  Wilcoxon signed-rank (scipy), win/tie/loss counts, median ratio, rank-biserial effect size.
- Figure 1: mean expansions per change event vs dist_block_goal (binned), one line per planner,
  one panel per prankster. Figure 2: box plot (log y) of replan_expansions_total by planner,
  grouped by prankster. Figure 3: worst single replan ("hitch") per planner × prankster.
  Figure 4: path length overhead (steps / opt_len_initial).
- `results/SUMMARY.md`: the numbers, plain-English bullet findings, and anything surprising or
  suspicious. Include sample sizes everywhere.

## Working rules
- Small steps. After each stage STOP and print a checkpoint report: what you built, the exact test
  output, a few sample numbers, open questions, and a suggested commit message (one per meaningful
  unit). **Do not run `git commit` or `git push` — the student commits and pushes himself.**
- Never invent data or expected values; if something looks wrong, say so.
- Prefer clarity over cleverness: short functions, docstrings explaining the idea in plain words.
- Keep runtime visible: print progress (tqdm) and an ETA before long runs; if a full run would take
  more than ~3 hours, propose a smaller config instead of starting it.
