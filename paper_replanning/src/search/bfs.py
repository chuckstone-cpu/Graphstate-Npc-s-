"""Breadth-First Search (UNINFORMED search, Unit 2).

Literal port of scripts/search/bfs.gd.
Explores cells in rings of equal distance from the start using a FIFO queue.
With unit step costs it finds a shortest path, but it has no idea where the
goal is, so it usually expands many more cells than A*.
"""

from src.search import grid_utils as GU


def search(w, h, is_blocked, start, goal):
    """is_blocked: function (x, y) tuple -> bool.

    Returns {"path": list of cells (empty if no path), "expanded": int}.
    """
    frontier = [start]   # FIFO queue
    head = 0             # index of the queue front
    came_from = {}
    visited = {start: True}
    expanded = 0
    while head < len(frontier):
        cur = frontier[head]
        head += 1
        expanded += 1
        if cur == goal:
            return {"path": GU.rebuild_path(came_from, goal), "expanded": expanded}
        for n in GU.neighbors(cur, w, h):
            if n not in visited and not is_blocked(n):
                visited[n] = True
                came_from[n] = cur
                frontier.append(n)
    return {"path": [], "expanded": expanded}
