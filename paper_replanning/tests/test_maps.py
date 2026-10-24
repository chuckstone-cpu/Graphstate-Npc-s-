"""Tests for src/maps.py on a tiny hand-written map, plus BFS lengths and seeding.

tests/fixtures/tiny.map (6 wide, 4 high; (0,0) is top-left):
    y=0   ..@...
    y=1   .T.W..
    y=2   G.S.O.
    y=3   ......
Blocked: @ at (2,0), T at (1,1), W at (3,1), O at (4,2). G and S are passable.
"""

from pathlib import Path

import pytest

from scripts.select_problems import bfs_length
from src.maps import Grid, load_map, load_scen, max_side_for
from src.search import bfs
from src.seeding import derive_seed

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_map_size_and_blocked_cells():
    grid = load_map(FIXTURES / "tiny.map")
    assert (grid.width, grid.height) == (6, 4)
    assert grid.blocked == {(2, 0), (1, 1), (3, 1), (4, 2)}
    assert grid.passable_count() == 20
    assert grid.name == "tiny"


def test_passable_and_blocked_characters():
    grid = load_map(FIXTURES / "tiny.map")
    assert not grid.is_blocked(0, 2)   # 'G' is passable
    assert not grid.is_blocked(2, 2)   # 'S' is passable
    assert grid.is_blocked(3, 1)       # 'W' (water) is treated as blocked
    assert grid.is_blocked(1, 1)       # 'T' (tree) is blocked


def test_outside_the_map_is_blocked():
    grid = load_map(FIXTURES / "tiny.map")
    for cell in [(-1, 0), (0, -1), (6, 0), (0, 4)]:
        assert grid.is_blocked(*cell)


def test_load_scen():
    problems = load_scen(FIXTURES / "tiny.map.scen")
    assert len(problems) == 2
    p = problems[1]
    assert p.index == 1 and p.bucket == 1
    assert p.map_path == "tiny.map"
    assert (p.map_width, p.map_height) == (6, 4)
    assert p.start == (0, 2) and p.goal == (5, 0)
    assert p.octile_length_unused == pytest.approx(5.82842712)


def test_malformed_map_is_rejected(tmp_path):
    bad = tmp_path / "bad.map"
    bad.write_text("type octile\nheight 2\nwidth 3\nmap\n...\n..\n")   # second row too short
    with pytest.raises(ValueError):
        load_map(bad)


def test_map_with_missing_rows_is_rejected(tmp_path):
    bad = tmp_path / "short.map"
    bad.write_text("type octile\nheight 3\nwidth 2\nmap\n..\n..\n")    # only 2 of 3 rows
    with pytest.raises(ValueError):
        load_map(bad)


def test_bfs_lengths_on_tiny_map():
    grid = load_map(FIXTURES / "tiny.map")
    # (0,0) -> (5,3): straight down then right, 3 + 5 = 8 moves (= Manhattan distance).
    assert bfs_length(grid, (0, 0), (5, 3)) == 8
    # (0,2) -> (5,0): the water at (3,1) and the O at (4,2) force a detour along the
    # bottom row and up the right edge: 9 moves, not the Manhattan 7.
    assert bfs_length(grid, (0, 2), (5, 0)) == 9


def test_water_really_changes_the_answer():
    # Same map but with the water cell made passable: the short route through (3,1) opens.
    grid = load_map(FIXTURES / "tiny.map")
    no_water = Grid(grid.width, grid.height, grid.blocked - {(3, 1)})
    assert bfs_length(no_water, (0, 2), (5, 0)) == 7


def test_bfs_path_includes_both_ends_and_unreachable_is_empty():
    grid = load_map(FIXTURES / "tiny.map")
    result = bfs.search(6, 4, lambda c: c in grid.blocked, (0, 0), (5, 3))
    assert result["path"][0] == (0, 0) and result["path"][-1] == (5, 3)
    assert len(result["path"]) == 9                     # 8 moves = 9 cells, like the game
    walled = Grid(3, 1, {(1, 0)})                        # "." "@" "." : no way across
    assert bfs_length(walled, (0, 0), (2, 0)) is None


def test_max_side_override_applies_only_to_its_set():
    sel = {"max_side": 256, "max_side_overrides": {"room": 512}}
    assert max_side_for(sel, "room") == 512
    assert max_side_for(sel, "dao") == 256
    assert max_side_for({"max_side": 256}, "room") == 256     # no overrides key at all


def test_derive_seed_is_reproducible_and_label_dependent():
    assert derive_seed(42, "select_maps", "dao") == derive_seed(42, "select_maps", "dao")
    assert derive_seed(42, "select_maps", "dao") != derive_seed(42, "select_maps", "room")
    assert derive_seed(42, "x") != derive_seed(43, "x")
