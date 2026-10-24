"""A* search (INFORMED search, Unit 2).

Literal port of scripts/search/astar.gd.
f(n) = g(n) + h(n): cost so far + Manhattan-distance estimate to the goal.
Because Manhattan distance is admissible, the first time the goal is popped
the path is optimal. Used here as the "replan from scratch" baseline that
D* Lite is compared against.
"""

from src.search import grid_utils as GU
from src.search.pq import PQ

INF = float("inf")


def search(w, h, is_blocked, start, goal, extra_cost=None):
    """Returns {"path": list of cells (empty if no path), "expanded": int, "cost": float}."""
    open = PQ()
    g = {start: 0.0}
    came_from = {}
    closed = {}
    expanded = 0
    # key1 = f, key2 = h  (ties broken toward cells closer to the goal)
    open.push(GU.manhattan(start, goal), GU.manhattan(start, goal), start)
    while not open.is_empty():
        cur = open.pop()[2]
        if cur in closed:
            continue                     # stale duplicate entry
        closed[cur] = True
        expanded += 1
        if cur == goal:
            return {"path": GU.rebuild_path(came_from, goal), "expanded": expanded, "cost": g[cur]}
        for n in GU.neighbors(cur, w, h):
            if is_blocked(n) or n in closed:
                continue
            step = 1.0
            if extra_cost is not None:
                step += extra_cost(n)
            new_g = g[cur] + step
            if new_g < g.get(n, INF):
                g[n] = new_g
                came_from[n] = cur
                hn = GU.manhattan(n, goal)
                open.push(new_g + hn, hn, n)
    return {"path": [], "expanded": expanded, "cost": INF}
