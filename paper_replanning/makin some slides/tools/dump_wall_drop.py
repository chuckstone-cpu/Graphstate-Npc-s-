"""Dump the level1 wall-drop scenario (same steps as tests/test_port_matches_game.py [2]) as JSON
so the slides can draw the REAL paths from our verified port instead of invented ones.

Run from paper_replanning/:  .venv/Scripts/python.exe "makin some slides/tools/dump_wall_drop.py"
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # paper_replanning/
sys.path.insert(0, str(ROOT))
from src.maps import load_game_level                # noqa: E402
from src.search import astar                        # noqa: E402
from src.search.dstar_lite import DStarLite         # noqa: E402

LEVEL1 = ROOT.parent / "levels" / "level1.txt"


def blocked_fn(grid):
    return lambda p: grid.is_blocked(p[0], p[1])


w, markers = load_game_level(LEVEL1)
s, t = markers["G"], markers["T"]
ds = DStarLite(w.width, w.height, blocked_fn(w), s, t)
ds.compute_shortest_path()
first_expanded = ds.expanded_last
initial = ds.current_path()

walked = [s]
pos = s
for _ in range(4):                                  # walk 4 steps, exactly as the test does
    pos = ds.next_step()
    ds.move_start(pos)
    ds.compute_shortest_path()
    walked.append(pos)
before = ds.current_path()
wall = before[3]
w.blocked.add(wall)
ds.notify_changed([wall])
ds.compute_shortest_path()
repaired = ds.current_path()
fresh = astar.search(w.width, w.height, blocked_fn(w), pos, t)

out = {
    "rows": LEVEL1.read_text().splitlines(),
    "start": s, "goal": t, "agent": pos, "wall": wall,
    "walked": walked, "path_before": before, "path_repaired": repaired,
    "dstar_first_expanded": first_expanded,
    "dstar_repair_expanded": ds.expanded_last, "fresh_astar_expanded": fresh["expanded"],
}
print(json.dumps(out))
