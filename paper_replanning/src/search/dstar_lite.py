"""D* Lite (Koenig & Likhachev, AAAI 2002) - INCREMENTAL heuristic search.

Literal port of scripts/search/dstar_lite.gd.

Big idea: search BACKWARDS from the goal to the agent. g(s) is the cost from
s to the goal. When the agent moves, the goal stays the same, so all those
g-values stay valid. When a few cells change (the player drops a wall), only
the cells whose cost-to-goal actually changed get fixed. A* would throw
everything away and search again from scratch.

Terms:
  g(s)   - current best known cost from s to the goal
  rhs(s) - one-step lookahead: min over neighbours s' of c(s, s') + g(s')
  s is "consistent" when g(s) == rhs(s); inconsistent cells go in the queue
  key(s) = [min(g, rhs) + h(start, s) + km, min(g, rhs)]
  km     - grows each time the agent moves, so old queue keys stay valid
           without re-sorting the whole queue
"""

from src.search import grid_utils as GU
from src.search.pq import PQ

INF = float("inf")


class DStarLite:
    def __init__(self, w, h, blocked_fn, s_start, s_goal, extra_fn=None):
        self.width = w
        self.height = h
        self.is_blocked = blocked_fn      # what the AGENT BELIEVES is blocked
        self.extra_cost = extra_fn        # optional: extra cost to ENTER a cell (e.g. a door to smash)
        self.start = s_start              # agent position
        self.last = s_start               # agent position at the last replan (for km)
        self.goal = s_goal
        self.km = 0.0

        self.g = {}                       # cell -> float (missing = INF)
        self.rhs = {}                     # cell -> float (missing = INF)
        self.open = {}                    # cell -> [k1, k2] : cells currently in the queue
        self.heap = PQ()                  # may hold stale entries; `open` says which are live

        # Stats for the HUD / report
        self.expanded_last = 0            # vertex expansions in the most recent compute
        self.expanded_total = 0
        self.touched = {}                 # cells expanded in the most recent compute (for drawing)

        self.rhs[self.goal] = 0.0
        self._insert(self.goal)

    # ---------- small helpers ----------
    def gv(self, s):
        return self.g.get(s, INF)

    def rhsv(self, s):
        return self.rhs.get(s, INF)

    def cost(self, a, b):
        """Edge cost: 1 between two free cells (+ any extra cost for entering b),
        INF if either end is blocked. Costs are >= 1, so Manhattan stays admissible."""
        if self.is_blocked(a) or self.is_blocked(b):
            return INF
        if self.extra_cost is not None:
            return 1.0 + self.extra_cost(b)
        return 1.0

    def calc_key(self, s):
        m = min(self.gv(s), self.rhsv(s))
        return [m + GU.manhattan(self.start, s) + self.km, m]

    def _insert(self, s):
        k = self.calc_key(s)
        self.open[s] = k
        self.heap.push(k[0], k[1], s)

    def _top_key(self):
        """Returns the smallest live key, throwing away stale heap entries."""
        while not self.heap.is_empty():
            e = self.heap.top()
            live = self.open.get(e[2])
            if live is not None and live[0] == e[0] and live[1] == e[1]:
                return [e[0], e[1]]
            self.heap.pop()
        return [INF, INF]

    # ---------- the algorithm (numbers match the paper's optimised version) ----------

    def update_vertex(self, u):
        """Recompute rhs(u) and put u in the queue only if it is inconsistent."""
        if u != self.goal:
            best = INF
            for s in GU.neighbors(u, self.width, self.height):
                best = min(best, self.cost(u, s) + self.gv(s))
            self.rhs[u] = best
        self.open.pop(u, None)            # GDScript open.erase(u)
        if self.gv(u) != self.rhsv(u):
            self._insert(u)

    def compute_shortest_path(self):
        """Process inconsistent cells until the agent's own cell is consistent and
        nothing in the queue could still improve it."""
        self.expanded_last = 0
        self.touched.clear()
        while PQ.less(self._top_key(), self.calc_key(self.start)) or self.rhsv(self.start) != self.gv(self.start):
            if not self.open:
                break
            k_old = self._top_key()
            u = self.heap.pop()[2]
            k_new = self.calc_key(u)
            self.expanded_last += 1
            self.touched[u] = True
            if PQ.less(k_old, k_new):
                # key is out of date (km changed since it was queued) - re-queue
                self.open[u] = k_new
                self.heap.push(k_new[0], k_new[1], u)
            elif self.gv(u) > self.rhsv(u):
                # OVERCONSISTENT: a cheaper route was found - lock it in
                self.g[u] = self.rhsv(u)
                self.open.pop(u, None)
                for p in GU.neighbors(u, self.width, self.height):
                    self.update_vertex(p)
            else:
                # UNDERCONSISTENT: u got more expensive (e.g. a wall appeared) -
                # reset it and let it and its neighbours find new values
                self.g[u] = INF
                self.update_vertex(u)
                for p in GU.neighbors(u, self.width, self.height):
                    self.update_vertex(p)
        self.expanded_total += self.expanded_last

    def move_start(self, new_start):
        """Call when the agent has moved to a new cell (before the next compute)."""
        self.km += GU.manhattan(self.last, new_start)
        self.last = new_start
        self.start = new_start

    def notify_changed(self, cells):
        """Call with every cell whose blocked/free status changed in the agent's belief.
        Every edge touching a changed cell changed cost, so the cell and all its
        neighbours need their rhs recomputed."""
        for c in cells:
            self.update_vertex(c)
            for n in GU.neighbors(c, self.width, self.height):
                self.update_vertex(n)

    def has_path(self):
        return self.gv(self.start) < INF

    def next_step(self):
        """Greedy step: the neighbour that minimises c(start, s') + g(s')."""
        if not self.has_path():
            return None
        best = None
        best_val = INF
        for s in GU.neighbors(self.start, self.width, self.height):
            v = self.cost(self.start, s) + self.gv(s)
            if v < best_val:
                best_val = v
                best = s
        return best

    def current_path(self, max_len=2000):
        """The full planned route (for drawing the path line)."""
        path = [self.start]
        if not self.has_path():
            return path
        cur = self.start
        seen = {self.start: True}
        while cur != self.goal and len(path) < max_len:
            best = None
            best_val = INF
            for s in GU.neighbors(cur, self.width, self.height):
                v = self.cost(cur, s) + self.gv(s)
                if v < best_val:
                    best_val = v
                    best = s
            if best is None or best in seen:
                break
            seen[best] = True
            path.append(best)
            cur = best
        return path
