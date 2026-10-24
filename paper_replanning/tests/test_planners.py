"""Tests for src/planners.py: every planner must always follow an OPTIMAL route.

"Optimal" is checked against a fresh BFS on the current grid (BFS is the simplest
correct shortest-path method for unit step costs).
"""

import csv
import json
import random
from pathlib import Path

import pytest

from src.maps import load_game_level, load_map
from src.planners import PLANNERS, make_planner
from src.search import bfs

ROOT = Path(__file__).resolve().parents[1]
LEVEL1 = ROOT.parent / "levels" / "level1.txt"


def bfs_moves(grid, a, b):
    """Shortest number of moves from a to b on the current grid (None if unreachable)."""
    path = bfs.search(grid.width, grid.height, lambda p: grid.is_blocked(*p), a, b)["path"]
    return len(path) - 1 if path else None


def level1():
    grid, markers = load_game_level(LEVEL1)
    return grid, markers["G"], markers["T"]


def walk_to_goal(planner, agent, goal, limit=10_000):
    """Follow the planner with no changes; return the number of moves taken."""
    steps = 0
    while agent != goal and steps < limit:
        agent = planner.next_step()
        assert agent is not None
        steps += 1
        planner.on_move(agent)
    return steps


@pytest.mark.parametrize("name", list(PLANNERS))
def test_static_map_all_planners_take_optimal_route(name):
    grid, s, t = level1()
    p = make_planner(name)
    p.init(grid, s, t)
    assert len(p.current_path()) - 1 == 27            # same optimum as test_port_matches_game
    assert walk_to_goal(p, s, t) == 27
    assert p.replans == 0


@pytest.mark.parametrize("name", list(PLANNERS))
def test_after_blocking_change_route_is_still_optimal(name):
    """Port of game test [2] for every planner: walk 4 steps, block current_path()[3]."""
    grid, s, t = level1()
    p = make_planner(name)
    p.init(grid, s, t)
    agent = s
    for _ in range(4):
        agent = p.next_step()
        p.on_move(agent)
    wall = p.current_path()[3]
    grid.blocked.add(wall)
    p.on_change(agent, [wall])
    route = p.current_path()
    assert wall not in route
    assert route[0] == agent and route[-1] == t
    assert len(route) - 1 == bfs_moves(grid, agent, t)
    assert p.replans == 1 and p.last_event_expansions > 0
    # ...and it really gets there in that many moves.
    assert walk_to_goal(p, agent, t) == bfs_moves(grid, agent, t)


def test_lazy_astar_replans_only_when_its_path_is_hit():
    grid, s, t = level1()
    p = make_planner("astar_lazy")
    p.init(grid, s, t)
    agent = p.next_step()
    p.on_move(agent)
    route = set(p.current_path())
    off_path = next(c for c in [(x, y) for y in range(grid.height) for x in range(grid.width)]
                    if not grid.is_blocked(*c) and c not in route and bfs_moves(grid, agent, t) is not None)
    grid.blocked.add(off_path)
    p.on_change(agent, [off_path])
    assert p.replans == 0 and p.last_event_expansions == 0
    on_path = p.current_path()[3]
    grid.blocked.add(on_path)
    p.on_change(agent, [on_path])
    assert p.replans == 1 and p.last_event_expansions > 0


def mini_sim_is_always_optimal(name, grid, s, t, seed, every=5, max_blocks=30):
    """Block a random cell on the planner's own path every `every` steps (never the
    agent, the goal, or a cut that disconnects them) and check optimality after each change.
    Returns the number of change events checked."""
    rng = random.Random(seed)
    p = make_planner(name)
    p.init(grid, s, t)
    agent, steps, blocks = s, 0, 0
    while agent != t and steps < 4000:
        agent = p.next_step()
        assert agent is not None
        steps += 1
        if steps % every == 0 and blocks < max_blocks:
            candidates = p.current_path()[2:-1]
            rng.shuffle(candidates)
            for c in candidates[:20]:
                grid.blocked.add(c)
                if bfs_moves(grid, agent, t) is not None:
                    break
                grid.blocked.discard(c)            # would disconnect: undo, try another
            else:
                p.on_move(agent)
                continue
            blocks += 1
            p.on_change(agent, [c])
            assert len(p.current_path()) - 1 == bfs_moves(grid, agent, t), f"{name} not optimal"
        else:
            p.on_move(agent)
    assert agent == t
    return blocks


@pytest.mark.parametrize("name", list(PLANNERS))
def test_repeated_blocking_on_level1_stays_optimal(name):
    grid, s, t = level1()
    assert mini_sim_is_always_optimal(name, grid, s, t, seed=1, every=3) > 0


def real_problems(n_per_set=1):
    """A few selected Moving AI problems (skipped if the data is not downloaded)."""
    maps = {(m["map_set"], m["map_name"]): m for m in
            json.loads((ROOT / "data" / "selected_maps.json").read_text())["maps"]}
    rows, seen = [], {}
    with open(ROOT / "data" / "selected_problems.csv") as f:
        for r in csv.DictReader(f):
            if seen.get(r["map_set"], 0) < n_per_set:
                seen[r["map_set"]] = seen.get(r["map_set"], 0) + 1
                rows.append((maps[(r["map_set"], r["map_name"])]["map_file"], r))
    return rows


@pytest.mark.parametrize("name", list(PLANNERS))
def test_repeated_blocking_on_real_maps_stays_optimal(name):
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        pytest.skip("Moving AI data not downloaded")
    for map_file, r in real_problems():
        grid = load_map(raw / map_file)
        s, t = (int(r["sx"]), int(r["sy"])), (int(r["gx"]), int(r["gy"]))
        assert mini_sim_is_always_optimal(name, grid, s, t, seed=7) > 0
