"""One run = one NPC trip from start to goal, with one planner and one prankster.

The loop follows CLAUDE.md exactly, with one fix: CLAUDE.md's pseudo-code calls
neither on_change nor on_move when the prankster acts but places nothing (a
skipped turn, or the `none` prankster). D* Lite must still hear about the move
(move_start), so in that case we call on_move.

    grid = fresh copy of the map; agent = start; planner.init(grid, start, goal)
    steps = 0; max_steps = 4 * opt_len + 100
    while agent != goal and steps < max_steps:
        agent = planner.next_step(); steps += 1          (None -> the run fails)
        if steps % K == 0 and blocks < B:
            changed = prankster.act(grid, agent, goal, planner.current_path())
            if changed: block them; planner.on_change(agent, changed); log an event
            else:       planner.on_move(agent)
        else:
            planner.on_move(agent)
"""

import time

from src.maps import Grid
from src.planners import make_planner
from src.pranksters import make_prankster
from src.seeding import derive_seed

# D* Lite's current_path() stops after max_len cells. The game's default (kept in the
# port, src/search/dstar_lite.py) is 2000, which is plenty for the game's small levels.
# On room maps the saboteur's doorway detours made planned paths of at least 1994 cells,
# within 0.3% of that limit, so the simulator asks for up to 10000. This changes no
# result: every path the simulator used in the main run was already shorter than 2000
# (checked_path asserted it), and a shorter path comes out the same for any max_len.
PATH_MAX_LEN = 10000

RUN_COLUMNS = [
    "run_id", "map_set", "map_name", "width", "height", "problem_id", "sx", "sy", "gx", "gy",
    "opt_len_initial", "planner", "prankster", "seed", "success", "steps", "blocks_placed",
    "initial_expansions", "replan_expansions_total", "replans", "max_single_replan_expansions",
    "replan_time_ms_total", "max_single_replan_ms",
    # extra columns (not in the CLAUDE.md list, useful for checking):
    "move_expansions_total", "initial_time_ms", "prankster_skipped_turns", "prankster_time_ms",
]
EVENT_COLUMNS = [
    "run_id", "step", "planner", "prankster", "block_x", "block_y", "dist_block_agent",
    "dist_block_goal", "on_planner_path", "expansions", "time_ms",
]


def make_run_id(problem_id, planner_name, prankster_name):
    return f"{problem_id}|{planner_name}|{prankster_name}"


def prankster_seed(master_seed, problem):
    """Seed from (master seed, map, problem): the same for every planner, so all
    planners face the same random draws (the saboteur needs none)."""
    return derive_seed(master_seed, "prankster", problem["map_set"], problem["map_name"],
                       problem["problem_id"])


def checked_path(planner, goal):
    """planner.current_path(), with two sanity checks: it must not have been cut off
    at the max_len limit, and it must end at the goal."""
    path = planner.current_path(max_len=PATH_MAX_LEN)
    assert len(path) < PATH_MAX_LEN, f"current_path() hit the max_len={PATH_MAX_LEN} limit"
    assert path[-1] == goal, "current_path() does not end at the goal"
    return path


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def run_one(map_grid, problem, planner_name, prankster_name, config):
    """Simulate one trip. Returns (run_row, event_rows).

    map_grid: the loaded map (Grid); it is copied, never changed.
    problem:  dict with problem_id, map_set, map_name, sx, sy, gx, gy, bfs_len.
    config:   the whole config/mvp.json dict.
    """
    K = config["prankster"]["act_every_k_steps"]
    B = config["prankster"]["max_blocks_per_run"]
    start = (int(problem["sx"]), int(problem["sy"]))
    goal = (int(problem["gx"]), int(problem["gy"]))
    opt_len = int(problem["bfs_len"])
    run_id = make_run_id(problem["problem_id"], planner_name, prankster_name)
    seed = prankster_seed(config["master_seed"], problem)

    grid = Grid(map_grid.width, map_grid.height, set(map_grid.blocked), map_grid.name)
    planner = make_planner(planner_name)
    prankster = make_prankster(prankster_name, seed, config["prankster"], grid)

    agent = start
    planner.init(grid, start, goal)
    assert len(checked_path(planner, goal)) - 1 == opt_len, "initial plan is not BFS-optimal"

    steps, blocks, events, prankster_ns = 0, 0, [], 0
    max_steps = config["sim"]["max_steps_factor"] * opt_len + config["sim"]["max_steps_extra"]
    while agent != goal and steps < max_steps:
        nxt = planner.next_step()
        if nxt is None:
            break                                     # no route: the run fails
        agent = nxt
        steps += 1
        if steps % K == 0 and blocks < B:
            path = checked_path(planner, goal)
            t0 = time.perf_counter_ns()
            changed = prankster.act(grid, agent, goal, path)
            prankster_ns += time.perf_counter_ns() - t0
            if changed:
                on_path = set(path[1:])
                for c in changed:
                    grid.blocked.add(c)
                blocks += len(changed)
                planner.on_change(agent, changed)
                for c in changed:
                    events.append({
                        "run_id": run_id, "step": steps, "planner": planner_name,
                        "prankster": prankster_name, "block_x": c[0], "block_y": c[1],
                        "dist_block_agent": manhattan(c, agent), "dist_block_goal": manhattan(c, goal),
                        "on_planner_path": c in on_path,
                        "expansions": planner.last_event_expansions,
                        "time_ms": planner.last_event_ns / 1e6,
                    })
            else:
                planner.on_move(agent)                # nothing changed (see module docstring)
        else:
            planner.on_move(agent)

    row = {
        "run_id": run_id, "map_set": problem["map_set"], "map_name": problem["map_name"],
        "width": grid.width, "height": grid.height, "problem_id": problem["problem_id"],
        "sx": start[0], "sy": start[1], "gx": goal[0], "gy": goal[1],
        "opt_len_initial": opt_len, "planner": planner_name, "prankster": prankster_name,
        "seed": seed, "success": agent == goal, "steps": steps, "blocks_placed": blocks,
        "initial_expansions": planner.initial_expansions,
        "replan_expansions_total": planner.replan_expansions_total,
        "replans": planner.replans,
        "max_single_replan_expansions": planner.max_single_replan_expansions,
        "replan_time_ms_total": planner.replan_time_ns_total / 1e6,
        "max_single_replan_ms": planner.max_single_replan_ns / 1e6,
        "move_expansions_total": planner.move_expansions_total,
        "initial_time_ms": planner.initial_time_ns / 1e6,
        "prankster_skipped_turns": prankster.skipped_turns,
        "prankster_time_ms": prankster_ns / 1e6,
    }
    return row, events
