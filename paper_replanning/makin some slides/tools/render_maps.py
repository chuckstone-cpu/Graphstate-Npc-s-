"""Render one benchmark map per set (dao, street, room) as a PNG for the slides.

Each picture shows the real map (walls dark, floor light) plus the longest selected
start->goal problem on that map and its 4-connected shortest path, found with our
own ported BFS (src/search/bfs.py). Nothing here is used by the experiments.

Run from paper_replanning/:  .venv/Scripts/python.exe "makin some slides/tools/render_maps.py"
"""
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]          # paper_replanning/
sys.path.insert(0, str(ROOT))
from src.maps import load_map                       # noqa: E402
from src.search import bfs                          # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "assets"
MAPS = {"dao": "lak304d", "street": "Boston_1_256", "room": "16room_005"}
CROP = {"room": 160}   # 512x512 is too big to read: show a square window around the path

# Dungeon palette (matches the deck's CSS variables)
WALL = (20, 16, 13)
FLOOR = (196, 178, 145)
PATH = (232, 163, 61)
START = (111, 154, 91)
GOAL = (200, 73, 44)


def longest_problem(map_set, map_name):
    """Return the selected problem on this map with the largest BFS length."""
    with open(ROOT / "data" / "selected_problems.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["map_set"] == map_set and r["map_name"] == map_name]
    return max(rows, key=lambda r: int(r["bfs_len"]))


def render(map_set, map_name, size=540):
    grid = load_map(ROOT / "data" / "raw" / map_set / f"{map_name}.map")
    p = longest_problem(map_set, map_name)
    start, goal = (int(p["sx"]), int(p["sy"])), (int(p["gx"]), int(p["gy"]))
    res = bfs.search(grid.width, grid.height, lambda c: grid.is_blocked(c[0], c[1]), start, goal)
    assert len(res["path"]) - 1 == int(p["bfs_len"]), "BFS length differs from selected_problems.csv"

    # Optional crop window (x0, y0, side) centred on the path, so large maps stay readable
    x0, y0, side_w, side_h = 0, 0, grid.width, grid.height
    if map_set in CROP:
        side = CROP[map_set]
        xs, ys = [c[0] for c in res["path"]], [c[1] for c in res["path"]]
        cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
        x0 = min(max(0, cx - side // 2), grid.width - side)
        y0 = min(max(0, cy - side // 2), grid.height - side)
        side_w = side_h = side

    img = Image.new("RGB", (side_w, side_h), FLOOR)
    px = img.load()
    for (x, y) in grid.blocked:
        if x0 <= x < x0 + side_w and y0 <= y < y0 + side_h:
            px[x - x0, y - y0] = WALL
    scale = max(1, size // max(side_w, side_h))
    img = img.resize((side_w * scale, side_h * scale), Image.NEAREST)

    d = ImageDraw.Draw(img)
    pts = [((x - x0) * scale + scale / 2, (y - y0) * scale + scale / 2) for (x, y) in res["path"]]
    d.line(pts, fill=PATH, width=max(3, scale + 1), joint="curve")
    r = max(5, scale * 2)
    for (cx, cy), col in ((pts[0], START), (pts[-1], GOAL)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col, outline=WALL, width=2)

    OUT.mkdir(exist_ok=True)
    img.save(OUT / f"map_{map_set}.png")
    print(f"{map_set}: {map_name} {grid.width}x{grid.height}, problem {p['problem_id']}, "
          f"BFS length {p['bfs_len']}, BFS expanded {res['expanded']}")


if __name__ == "__main__":
    for s, m in MAPS.items():
        render(s, m)
