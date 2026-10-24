"""Load Moving AI benchmark files: maps (.map) and scenarios (.scen).

Map format (Sturtevant 2012):
    type octile
    height H
    width W
    map
    <H rows of exactly W characters>
Row 0 is the top of the map and column 0 is the left, so the character at
row y, column x is cell (x, y).

Passable characters: '.', 'G', 'S'. Everything else ('@', 'O', 'T', 'W', ...)
is blocked. Note that this treats water 'W' as blocked (a simplification).

Scenario format:
    version 1
    then one problem per line with 9 tab-separated columns:
    bucket, map path, map width, map height, start x, start y, goal x, goal y, optimal length
The optimal length there is for OCTILE (8-direction) movement. Our NPC moves in
4 directions, so that number is NOT our shortest path length. We keep it only
for reference, under the name `octile_length_unused`.
"""

from dataclasses import dataclass
from pathlib import Path

PASSABLE_CHARS = {".", "G", "S"}


@dataclass
class Grid:
    """A grid map: its size plus the set of blocked cells (x, y)."""
    width: int
    height: int
    blocked: set
    name: str = ""

    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, x, y):
        """True for walls and for any cell outside the map (like the game)."""
        return not self.in_bounds(x, y) or (x, y) in self.blocked

    def passable_count(self):
        return self.width * self.height - len(self.blocked)


@dataclass
class Problem:
    """One start/goal pair from a .scen file."""
    index: int                     # 0-based position of the problem in its .scen file
    bucket: int
    map_path: str
    map_width: int
    map_height: int
    start: tuple                   # (x, y)
    goal: tuple                    # (x, y)
    octile_length_unused: float    # octile optimum from the file; NOT valid for 4-connected moves


def max_side_for(selection, map_set):
    """The size limit for one map set: the per-set override if there is one, else max_side."""
    return selection.get("max_side_overrides", {}).get(map_set, selection["max_side"])


def load_map(path):
    """Read a .map file and return a Grid. Raises ValueError if the file is malformed."""
    path = Path(path)
    lines = path.read_text().splitlines()

    # Header: four lines, "type ...", "height H", "width W", "map".
    if len(lines) < 4:
        raise ValueError(f"{path.name}: too short to be a .map file")
    if not lines[0].startswith("type"):
        raise ValueError(f"{path.name}: first line should be 'type ...'")
    height = _read_header_number(lines[1], "height", path)
    width = _read_header_number(lines[2], "width", path)
    if lines[3].strip() != "map":
        raise ValueError(f"{path.name}: fourth line should be 'map'")

    rows = lines[4:4 + height]
    if len(rows) != height:
        raise ValueError(f"{path.name}: expected {height} rows, found {len(rows)}")

    blocked = set()
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"{path.name}: row {y} has {len(row)} chars, expected {width}")
        for x, ch in enumerate(row):
            if ch not in PASSABLE_CHARS:
                blocked.add((x, y))
    return Grid(width=width, height=height, blocked=blocked, name=path.stem)


def load_game_level(path):
    """Read one of the Godot game's level files (e.g. levels/level1.txt).

    Port of Grid.load_text in scripts/grid.gd. Legend: '#' wall, '.' floor,
    any other character is a marker on a floor cell (G = start, T = treasure, E = exit).
    Returns (Grid, markers) where markers maps a character to its (x, y).
    """
    path = Path(path)
    rows = path.read_text().strip().split("\n")
    width = 0
    blocked, markers = set(), {}
    for y, row in enumerate(rows):
        row = row.rstrip()                     # drops the '\r' of Windows line endings
        width = max(width, len(row))
        for x, ch in enumerate(row):
            if ch == "#":
                blocked.add((x, y))
            elif ch != ".":
                markers[ch] = (x, y)
    return Grid(width=width, height=len(rows), blocked=blocked, name=path.stem), markers


def _read_header_number(line, key, path):
    """Parse a header line like 'height 128' and return the number."""
    parts = line.split()
    if len(parts) != 2 or parts[0] != key:
        raise ValueError(f"{path.name}: expected '{key} <number>', got {line!r}")
    return int(parts[1])


def load_scen(path):
    """Read a .scen file and return a list of Problem objects (in file order)."""
    path = Path(path)
    lines = path.read_text().splitlines()
    if not lines or not lines[0].startswith("version"):
        raise ValueError(f"{path.name}: first line should be 'version ...'")

    problems = []
    for line in lines[1:]:
        if not line.strip():
            continue                                  # ignore blank lines
        # Columns are tab-separated. Splitting on tabs also allows a map path with spaces.
        cols = line.split("\t") if "\t" in line else line.split()
        if len(cols) != 9:
            raise ValueError(f"{path.name}: expected 9 columns, got {len(cols)}: {line!r}")
        bucket, map_path, mw, mh, sx, sy, gx, gy, opt = cols
        problems.append(Problem(
            index=len(problems),
            bucket=int(bucket),
            map_path=map_path,
            map_width=int(mw),
            map_height=int(mh),
            start=(int(sx), int(sy)),
            goal=(int(gx), int(gy)),
            octile_length_unused=float(opt),
        ))
    return problems
