"""Tests for src/sim.py."""

import csv
import json
from pathlib import Path

import pytest

from src.maps import Grid, load_game_level, load_map
from src.planners import PLANNERS
from src.sim import PATH_MAX_LEN, checked_path, run_one

ROOT = Path(__file__).resolve().parents[1]
LEVEL1 = ROOT.parent / "levels" / "level1.txt"
CONFIG = json.loads((ROOT / "config" / "mvp.json").read_text())


def level1_problem():
    grid, m = load_game_level(LEVEL1)
    (sx, sy), (gx, gy) = m["G"], m["T"]
    return grid, {"problem_id": "level1/0", "map_set": "game", "map_name": "level1",
                  "sx": sx, "sy": sy, "gx": gx, "gy": gy, "bfs_len": 27}


def first_real_problem_per_set(sets=("dao", "street")):
    """The first selected problem of each set (skipped if the data is not downloaded)."""
    if not (ROOT / "data" / "raw").exists():
        pytest.skip("Moving AI data not downloaded")
    maps = {(m["map_set"], m["map_name"]): m for m in
            json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]}
    out, seen = [], set()
    with open(ROOT / "data" / "selected_problems.csv") as f:
        for r in csv.DictReader(f):
            if r["map_set"] in sets and r["map_set"] not in seen:
                seen.add(r["map_set"])
                out.append((load_map(ROOT / "data" / "raw" / maps[(r["map_set"], r["map_name"])]["map_file"]), r))
    return out


@pytest.mark.parametrize("planner", list(PLANNERS))
def test_no_prankster_means_optimal_walk_and_zero_replans(planner):
    cases = [level1_problem()] + first_real_problem_per_set()
    for grid, prob in cases:
        row, events = run_one(grid, prob, planner, "none", CONFIG)
        assert row["success"]
        assert row["steps"] == int(prob["bfs_len"]) == row["opt_len_initial"]
        assert row["replans"] == 0 and row["replan_expansions_total"] == 0
        assert row["blocks_placed"] == 0 and events == []
        assert row["move_expansions_total"] == 0


def test_run_does_not_change_the_loaded_map():
    grid, prob = level1_problem()
    before = set(grid.blocked)
    row, _ = run_one(grid, prob, "dstar_lite", "saboteur", CONFIG)
    assert row["blocks_placed"] > 0 and grid.blocked == before


@pytest.mark.parametrize("planner", list(PLANNERS))
def test_with_saboteur_every_planner_still_succeeds(planner):
    grid, prob = level1_problem()
    row, events = run_one(grid, prob, planner, "saboteur", CONFIG)
    assert row["success"] and row["blocks_placed"] == len(events) > 0
    assert row["steps"] >= row["opt_len_initial"]       # blocks can only make the trip longer


def test_skipped_turns_still_tell_dstar_about_the_move():
    """In a corridor every cell AHEAD of the agent is a cut (blocking it disconnects
    the goal), so the saboteur, which only looks along the path ahead, skips every turn.
    D* Lite must still get move_start (via on_move), or it would plan from a stale cell.
    (A random prankster could still legally block the dead end BEHIND the agent.)"""
    corridor = Grid(30, 1, set())
    prob = {"problem_id": "corridor/0", "map_set": "test", "map_name": "corridor",
            "sx": 0, "sy": 0, "gx": 29, "gy": 0, "bfs_len": 29}
    row, events = run_one(corridor, prob, "dstar_lite", "saboteur", CONFIG)
    assert row["success"] and row["steps"] == 29 and events == []
    assert row["prankster_skipped_turns"] == 29 // CONFIG["prankster"]["act_every_k_steps"]


def test_checked_path_catches_the_max_len_limit():
    class FakePlanner:
        def current_path(self, max_len):
            return [(i, 0) for i in range(max_len)]        # exactly max_len cells = cut off
    with pytest.raises(AssertionError, match="max_len"):
        checked_path(FakePlanner(), (PATH_MAX_LEN + 5, 0))


def test_simulator_asks_dstar_for_long_paths_but_port_default_is_unchanged():
    """A corridor path of 2500 cells: the port's default stops at 2000, the simulator's call does not."""
    from src.planners import make_planner
    corridor = Grid(2600, 1, set())
    p = make_planner("dstar_lite")
    p.init(corridor, (0, 0), (2499, 0))
    assert len(p.ds.current_path()) == 2000                 # port default, untouched
    assert len(checked_path(p, (2499, 0))) == 2500          # what the simulator sees
