"""Tests for src/pranksters.py: the rules every prankster must obey."""

import json
import random
from pathlib import Path

import pytest

from src.maps import Grid, load_game_level
from src.pranksters import make_prankster, still_connected
from src.search import astar, bfs
from src.sim import run_one

ROOT = Path(__file__).resolve().parents[1]
LEVEL1 = ROOT.parent / "levels" / "level1.txt"
CONFIG = json.loads((ROOT / "config" / "mvp.json").read_text())
PCFG = CONFIG["prankster"]
BLOCKING = ["random_global", "random_local", "saboteur"]


def shortest_path(grid, a, b):
    return bfs.search(grid.width, grid.height, lambda p: grid.is_blocked(*p), a, b)["path"]


def astar_cost(grid, a, b):
    return astar.search(grid.width, grid.height, lambda p: grid.is_blocked(*p), a, b)["cost"]


def maps_for_testing():
    """level1 plus three random 20x15 maps (22% walls) with a reachable goal."""
    grid, m = load_game_level(LEVEL1)
    out = [(grid, m["G"], m["T"])]
    rng = random.Random(3)
    while len(out) < 4:
        g = Grid(20, 15, {(x, y) for y in range(15) for x in range(20) if rng.random() < 0.22})
        g.blocked -= {(0, 0), (19, 14)}
        if still_connected(g, (0, 0), (19, 14)):
            out.append((g, (0, 0), (19, 14)))
    return out


def walk_with_prankster(name, grid, start, goal, seed=0, max_acts=40):
    """The agent follows a shortest path; the prankster acts every step.
    Yields (agent, path_before, cells_blocked, prankster) after each act."""
    p = make_prankster(name, seed, PCFG, grid)
    agent, acts = start, 0
    while agent != goal and acts < max_acts:
        path = shortest_path(grid, agent, goal)
        agent = path[1]
        path = shortest_path(grid, agent, goal)
        changed = p.act(grid, agent, goal, path)
        acts += 1
        yield agent, path, changed, p
        grid.blocked.update(changed)


def test_none_never_blocks():
    grid, m = load_game_level(LEVEL1)
    for _, _, changed, _ in walk_with_prankster("none", grid, m["G"], m["T"]):
        assert changed == []


@pytest.mark.parametrize("name", BLOCKING)
def test_never_blocks_agent_or_goal_and_never_disconnects(name):
    total = 0
    for grid, s, t in maps_for_testing():
        for agent, _, changed, _ in walk_with_prankster(name, grid, s, t):
            assert len(changed) <= 1
            for c in changed:
                assert c != agent and c != t
                assert not grid.is_blocked(*c)              # it was a free cell
                grid.blocked.add(c)
                assert still_connected(grid, agent, t), f"{name} disconnected agent from goal"
                grid.blocked.discard(c)
                total += 1
    assert total > 20                                       # the pranksters really did act


def test_act_never_changes_the_grid_itself():
    for name in BLOCKING:
        grid, m = load_game_level(LEVEL1)
        before = set(grid.blocked)
        p = make_prankster(name, 1, PCFG, grid)
        path = shortest_path(grid, m["G"], m["T"])
        p.act(grid, m["G"], m["T"], path)
        assert grid.blocked == before


def test_random_local_stays_within_radius():
    grid, m = load_game_level(LEVEL1)
    for agent, _, changed, _ in walk_with_prankster("random_local", grid, m["G"], m["T"]):
        for c in changed:
            assert max(abs(c[0] - agent[0]), abs(c[1] - agent[1])) <= PCFG["local_radius"]


def test_saboteur_picks_the_worst_candidate_and_never_shortens_the_trip():
    checked = 0
    for grid, s, t in maps_for_testing():
        for agent, path, changed, p in walk_with_prankster("saboteur", grid, s, t):
            if not changed:
                continue
            before = astar_cost(grid, agent, t)
            grid.blocked.add(changed[0])
            after = astar_cost(grid, agent, t)
            grid.blocked.discard(changed[0])
            assert after >= before                          # blocking never shortens a trip
            costs = [c for _, c in p.last_candidates if c is not None]
            assert after == max(costs)                      # it chose the worst candidate
            # Tie rule: the chosen cell is the FIRST (closest to the agent) of the best ones.
            first_best = next(cell for cell, c in p.last_candidates if c == max(costs))
            assert changed[0] == first_best
            assert changed[0] in path[2:-1]                 # from index 2 to the cell before the goal
            checked += 1
    assert checked > 20


def test_saboteur_candidate_indices():
    sab = make_prankster("saboteur", 0, PCFG, None)
    idx = sab.candidate_indices(30)                         # path indices 0..29, goal at 29
    assert len(idx) == 12 and idx[0] == 2 and idx[-1] == 28
    assert idx == sorted(set(idx))                          # evenly spaced, no duplicates
    assert sab.candidate_indices(6) == [2, 3, 4]            # short path: every cell from 2 to 4
    assert sab.candidate_indices(3) == []                   # agent, one cell, goal: nothing to block


@pytest.mark.parametrize("name", BLOCKING)
def test_corridor_every_block_would_disconnect_so_turn_is_skipped(name):
    corridor = Grid(8, 1, set())                            # a 1-cell-wide corridor
    p = make_prankster(name, 0, PCFG, corridor)
    path = [(x, 0) for x in range(8)]
    assert p.act(corridor, (0, 0), (7, 0), path) == []
    assert p.skipped_turns == 1


def level1_problem():
    grid, m = load_game_level(LEVEL1)
    (sx, sy), (gx, gy) = m["G"], m["T"]
    return grid, {"problem_id": "level1/0", "map_set": "game", "map_name": "level1",
                  "sx": sx, "sy": sy, "gx": gx, "gy": gy, "bfs_len": 27}


@pytest.mark.parametrize("name", BLOCKING)
def test_simulator_respects_K_and_B(name):
    grid, prob = level1_problem()
    cfg = json.loads(json.dumps(CONFIG))
    cfg["prankster"]["act_every_k_steps"] = 3
    cfg["prankster"]["max_blocks_per_run"] = 4
    row, events = run_one(grid, prob, "astar_restart", name, cfg)
    assert row["blocks_placed"] <= 4 and len(events) == row["blocks_placed"]
    assert all(e["step"] % 3 == 0 for e in events)
    assert row["blocks_placed"] > 0


@pytest.mark.parametrize("name", BLOCKING)
def test_same_seed_gives_same_blocks(name):
    grid, prob = level1_problem()
    cfg = json.loads(json.dumps(CONFIG))
    cfg["prankster"]["act_every_k_steps"] = 2
    a = run_one(grid, prob, "astar_lazy", name, cfg)
    b = run_one(grid, prob, "astar_lazy", name, cfg)
    cells = lambda ev: [(e["step"], e["block_x"], e["block_y"]) for e in ev]   # noqa: E731
    assert cells(a[1]) == cells(b[1]) and len(a[1]) > 0
    assert a[0]["seed"] == b[0]["seed"]
    # Fairness: every planner gets the same prankster seed for the same problem.
    assert run_one(grid, prob, "dstar_lite", name, cfg)[0]["seed"] == a[0]["seed"]
