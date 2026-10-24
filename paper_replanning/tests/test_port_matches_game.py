"""Proof that the Python search code is a faithful port of the Godot game.

These are ports of tests [1]-[3] in the game's tests/run_tests.gd. The expected
numbers for [1] and [2] were printed by the GODOT version on levels/level1.txt
(start = G, goal = T). If the port drifts by even one expansion, these fail.
Never edit the expected numbers to make a test pass: fix the port instead.
"""

import random
from pathlib import Path

from src.maps import Grid, load_game_level
from src.search import astar, bfs
from src.search.dstar_lite import DStarLite

INF = float("inf")
REPO = Path(__file__).resolve().parents[2]        # the game repo (one level above paper_replanning/)
LEVEL1 = REPO / "levels" / "level1.txt"


def blocked_fn(grid):
    """The is_blocked callable the search code expects: (x, y) -> bool."""
    return lambda p: grid.is_blocked(p[0], p[1])


def test_static_level_matches_game_numbers():
    """[1] Same optimal length from BFS, A*, D* Lite on level1, with the game's expansion counts."""
    w, markers = load_game_level(LEVEL1)
    s, t = markers["G"], markers["T"]
    b = bfs.search(w.width, w.height, blocked_fn(w), s, t)
    a = astar.search(w.width, w.height, blocked_fn(w), s, t)
    ds = DStarLite(w.width, w.height, blocked_fn(w), s, t)
    ds.compute_shortest_path()
    dpath = ds.current_path()

    assert len(b["path"]) == 28 and b["expanded"] == 190      # game: BFS 28 cells, 190 expansions
    assert len(a["path"]) == 28 and a["expanded"] == 67       # game: A* 28 cells, 67 expansions
    assert ds.expanded_last == 75                             # game: D* Lite 75 expansions
    assert ds.gv(s) == 27                                     # game: g(start) = 27
    assert len(dpath) == len(a["path"])


def test_wall_drop_repair_matches_game_numbers():
    """[2] Wall dropped on the route mid-walk -> D* repairs, matches A*."""
    w, markers = load_game_level(LEVEL1)
    s, t = markers["G"], markers["T"]
    ds = DStarLite(w.width, w.height, blocked_fn(w), s, t)
    ds.compute_shortest_path()
    # walk 4 steps
    pos = s
    for _ in range(4):
        pos = ds.next_step()
        ds.move_start(pos)
        ds.compute_shortest_path()
    wall_cell = ds.current_path()[3]
    w.blocked.add(wall_cell)
    ds.notify_changed([wall_cell])
    ds.compute_shortest_path()
    repaired = ds.current_path()
    fresh = astar.search(w.width, w.height, blocked_fn(w), pos, t)

    assert wall_cell == (6, 3)                                # game: the wall lands on (6, 3)
    assert wall_cell not in repaired
    assert len(repaired) == len(fresh["path"]) == 24          # game: repaired path = 24 cells = fresh A*
    assert ds.expanded_last == 3                              # game: D* Lite repair = 3 expansions
    assert fresh["expanded"] == 58                            # game: fresh A* = 58 expansions


def test_random_dynamic_maps_dstar_always_optimal():
    """[3] 40 random 20x15 maps (22% walls), 3 random cell flips per step:
    D* Lite's g(agent) always equals a fresh A* cost.

    Note: Godot's RandomNumberGenerator (PCG32) and Python's random (Mersenne
    Twister) give different numbers for seed 42, so these are NOT the same 40
    maps as in the game. The game test prints no expected numbers here, only
    the property "D* cost == A* cost", which is what we check. Flips go both
    ways (walls appear AND disappear), a harder case than our blocking-only experiments.
    """
    rng = random.Random(42)
    checks = 0
    for trial in range(40):
        w = Grid(20, 15, set())
        for y in range(w.height):
            for x in range(w.width):
                if rng.random() < 0.22:
                    w.blocked.add((x, y))
        s, t = (0, 0), (19, 14)
        w.blocked.discard(s)
        w.blocked.discard(t)
        ds = DStarLite(w.width, w.height, blocked_fn(w), s, t)
        ds.compute_shortest_path()
        pos = s
        for step in range(60):
            if pos == t:
                break
            # randomly flip 3 cells (never the agent or goal)
            changed = []
            for _ in range(3):
                c = (rng.randint(0, 19), rng.randint(0, 14))
                if c == pos or c == t:
                    continue
                if c in w.blocked:
                    w.blocked.discard(c)
                else:
                    w.blocked.add(c)
                changed.append(c)
            ds.notify_changed(changed)
            ds.compute_shortest_path()
            fresh = astar.search(w.width, w.height, blocked_fn(w), pos, t)
            a_cost = INF if not fresh["path"] else float(len(fresh["path"]) - 1)
            assert ds.gv(pos) == a_cost, f"mismatch trial {trial} step {step}"
            checks += 1
            nxt = ds.next_step()
            if nxt is None:
                break
            pos = nxt
            ds.move_start(pos)
    assert checks > 40          # make sure the loop really ran (not 40 instantly-blocked maps)
