"""Change models ("pranksters"): opponents that block cells while the NPC walks.

All of them only BLOCK cells, never unblock. The simulator (src/sim.py) decides
WHEN a prankster may act (every K agent steps, at most B blocks per run); the
prankster only decides WHICH cell to block.

Interface:
    act(grid, agent, goal, path) -> list of cells to block ([] = skip this turn)
        `path` is the NPC's current planned path (agent first, goal last).
        act() never changes the grid itself: any tentative block is undone before
        returning, and the simulator applies the returned cells.

Common rules (every prankster):
    - never block the agent's cell or the goal,
    - never block a cell that would disconnect the agent from the goal,
    - if a drawn cell breaks a rule, try another one; after `max_tries` tries, skip the turn.
    - each prankster has its own random.Random(seed), so a run is reproducible.

The four models:
    none           never blocks anything (control)
    random_global  a uniformly random free cell anywhere on the map
    random_local   a uniformly random free cell within Chebyshev radius R of the agent
    saboteur       greedy interdiction: of up to C cells evenly spaced along the NPC's
                   path, block the one that makes the agent's trip longest
                   (ties -> the one closest to the agent along the path)

The prankster's own searches are NOT counted as NPC work.
"""

import random

from src.search import astar, bfs


def _blocked_fn(grid):
    return lambda p: grid.is_blocked(p[0], p[1])


def still_connected(grid, agent, goal):
    """True if the goal can still be reached from the agent (BFS reachability check)."""
    return bool(bfs.search(grid.width, grid.height, _blocked_fn(grid), agent, goal)["path"])


class Prankster:
    name = "base"

    def __init__(self, seed, config):
        self.rng = random.Random(seed)
        self.max_tries = config["max_tries"]
        self.skipped_turns = 0          # turns where no legal cell was found

    def act(self, grid, agent, goal, path):
        raise NotImplementedError

    def _legal(self, grid, cell, agent, goal):
        """Common rules: not the agent, not the goal, and blocking it keeps the goal reachable."""
        if cell == agent or cell == goal or grid.is_blocked(*cell):
            return False
        grid.blocked.add(cell)                      # tentative block...
        ok = still_connected(grid, agent, goal)
        grid.blocked.discard(cell)                  # ...always undone
        return ok

    def _first_legal_draw(self, grid, agent, goal, draw):
        """Call draw() up to max_tries times; return [cell] for the first legal one, else []."""
        for _ in range(self.max_tries):
            cell = draw()
            if cell is not None and self._legal(grid, cell, agent, goal):
                return [cell]
        self.skipped_turns += 1
        return []


class NoPrankster(Prankster):
    name = "none"

    def act(self, grid, agent, goal, path):
        return []


class RandomGlobal(Prankster):
    """A uniformly random free cell anywhere on the map."""
    name = "random_global"

    def __init__(self, seed, config, grid):
        super().__init__(seed, config)
        # All cells that are free at the start, in a fixed order (so the seed decides everything).
        self.initially_free = [(x, y) for y in range(grid.height) for x in range(grid.width)
                               if not grid.is_blocked(x, y)]

    def act(self, grid, agent, goal, path):
        def draw():
            # Redraw (without using up a try) until we hit a cell that is STILL free.
            # Drawing uniformly from the initially free cells and rejecting the ones
            # blocked since gives a uniform draw over the currently free cells.
            for _ in range(100_000):
                cell = self.rng.choice(self.initially_free)
                if not grid.is_blocked(*cell):
                    return cell
            return None
        return self._first_legal_draw(grid, agent, goal, draw)


class RandomLocal(Prankster):
    """A uniformly random free cell within Chebyshev radius R of the agent."""
    name = "random_local"

    def __init__(self, seed, config):
        super().__init__(seed, config)
        self.radius = config["local_radius"]

    def act(self, grid, agent, goal, path):
        ax, ay = agent
        r = self.radius
        # Every free cell in the (2R+1) x (2R+1) square around the agent, in a fixed order.
        nearby = [(x, y) for y in range(ay - r, ay + r + 1) for x in range(ax - r, ax + r + 1)
                  if not grid.is_blocked(x, y)]
        if not nearby:
            self.skipped_turns += 1
            return []
        return self._first_legal_draw(grid, agent, goal, lambda: self.rng.choice(nearby))


class Saboteur(Prankster):
    """Greedy interdiction: block the path cell that lengthens the agent's trip the most."""
    name = "saboteur"

    def __init__(self, seed, config):
        super().__init__(seed, config)
        self.n_candidates = config["saboteur_candidates"]
        self.last_candidates = []       # (cell, new A* cost or None) of the last act, for tests

    def candidate_indices(self, path_len):
        """Up to C indices evenly spaced from 2 to the cell before the goal (path_len - 2)."""
        lo, hi = 2, path_len - 2
        if hi < lo:
            return []
        if hi - lo + 1 <= self.n_candidates:
            return list(range(lo, hi + 1))
        c = self.n_candidates
        # Rounded integer spacing: lo + round(i * (hi - lo) / (c - 1)).
        return [lo + (i * (hi - lo) + (c - 1) // 2) // (c - 1) for i in range(c)]

    def act(self, grid, agent, goal, path):
        self.last_candidates = []
        best_cell, best_cost = None, -1.0
        for i in self.candidate_indices(len(path)):
            cell = path[i]
            if cell == agent or cell == goal or grid.is_blocked(*cell):
                continue
            # Tentatively block it and ask: how long is the agent's trip now?
            grid.blocked.add(cell)
            result = astar.search(grid.width, grid.height, _blocked_fn(grid), agent, goal)
            grid.blocked.discard(cell)
            # No path means this block would disconnect agent and goal: not allowed.
            # (A* finds a path whenever one exists, so this is the same test as BFS.)
            cost = result["cost"] if result["path"] else None
            self.last_candidates.append((cell, cost))
            # Strictly greater: on a tie, the earlier candidate (closer to the agent) wins.
            if cost is not None and cost > best_cost:
                best_cell, best_cost = cell, cost
        if best_cell is None:
            self.skipped_turns += 1
            return []
        return [best_cell]


PRANKSTER_NAMES = ["none", "random_global", "random_local", "saboteur"]


def make_prankster(name, seed, config, grid):
    """config = the "prankster" block of config/mvp.json."""
    if name == "none":
        return NoPrankster(seed, config)
    if name == "random_global":
        return RandomGlobal(seed, config, grid)
    if name == "random_local":
        return RandomLocal(seed, config)
    if name == "saboteur":
        return Saboteur(seed, config)
    raise ValueError(f"unknown prankster {name!r}")
