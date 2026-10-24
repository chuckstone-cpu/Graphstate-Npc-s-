"""Small helpers shared by every search algorithm.

Literal port of scripts/search/grid_utils.gd.
A grid cell is a tuple (x, y). Movement is 4-directional, each step costs 1.
"""

# Right, left, down, up - in exactly the game's order (it decides tie-breaking).
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def manhattan(a, b):
    """Manhattan distance: admissible for 4-way movement with unit cost
    (it never overestimates the true number of steps)."""
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def in_bounds(p, w, h):
    return p[0] >= 0 and p[1] >= 0 and p[0] < w and p[1] < h


def neighbors(p, w, h):
    out = []
    for d in DIRS:
        n = (p[0] + d[0], p[1] + d[1])
        if in_bounds(n, w, h):
            out.append(n)
    return out


def rebuild_path(came_from, goal):
    path = [goal]
    cur = goal
    while cur in came_from:
        cur = came_from[cur]
        path.insert(0, cur)            # GDScript push_front
    return path
