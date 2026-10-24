"""The four NPC planners we compare, behind one common interface.

Every planner reads the SAME live Grid object as the simulator: when the
prankster blocks a cell, the simulator adds it to grid.blocked and then calls
planner.on_change(...). So the NPC always knows the true map (full knowledge).

Interface (used by src/sim.py):
    init(grid, start, goal)      plan the first route (counted as initial_expansions)
    next_step()                  the next cell to move to (None = no route)
    current_path()               planned cells from the agent to the goal (agent first)
    on_move(agent)               the agent moved and nothing changed
    on_change(agent, changed)    the agent moved AND these cells just became blocked

Counters (expansions are counted only inside the search code):
    initial_expansions, initial_time_ns     the first plan
    replans                                 searches run because of a change event
    replan_expansions_total, replan_time_ns_total
    max_single_replan_expansions, max_single_replan_ns
    move_expansions_total, move_time_ns_total   work done in on_move (only D* Lite does any)
    last_event_expansions, last_event_ns        work of the most recent on_change (for events.csv)

The four planners:
    bfs_restart    re-run BFS from the agent after every change event
    astar_restart  re-run A* from the agent after every change event
    astar_lazy     keep the path; re-run A* only if a newly blocked cell is on the
                   rest of the path (blocking can never create a shorter route, so an
                   untouched path is still optimal)
    dstar_lite     one D* Lite object for the whole run; move_start + compute every step
                   (exactly like the game's goblin), notify_changed on change events
"""

import time

from src.search import astar, bfs
from src.search.dstar_lite import DStarLite


class Planner:
    """Shared bookkeeping: counters and timing. Subclasses do the actual planning."""
    name = "base"

    def __init__(self):
        self.initial_expansions = 0
        self.initial_time_ns = 0
        self.replans = 0
        self.replan_expansions_total = 0
        self.replan_time_ns_total = 0
        self.max_single_replan_expansions = 0
        self.max_single_replan_ns = 0
        self.move_expansions_total = 0
        self.move_time_ns_total = 0
        self.last_event_expansions = 0
        self.last_event_ns = 0

    def _is_blocked(self, p):
        """The is_blocked callable the search code expects: (x, y) -> bool."""
        return self.grid.is_blocked(p[0], p[1])

    def _record_replan(self, expansions, ns):
        """Add one replan (a search triggered by a change event) to the counters."""
        self.replans += 1
        self.replan_expansions_total += expansions
        self.replan_time_ns_total += ns
        self.max_single_replan_expansions = max(self.max_single_replan_expansions, expansions)
        self.max_single_replan_ns = max(self.max_single_replan_ns, ns)


class PathPlanner(Planner):
    """A planner that searches for a whole path and then walks along it.

    Used by bfs_restart, astar_restart and astar_lazy. `self.path[self.idx]` is
    always the agent's cell.
    """
    search_fn = None          # bfs.search or astar.search, set by the subclass

    def init(self, grid, start, goal):
        self.grid, self.goal = grid, goal
        self.path, self.idx = [start], 0
        expansions, ns = self._plan_from(start)
        self.initial_expansions, self.initial_time_ns = expansions, ns

    def _plan_from(self, agent):
        """Search from the agent to the goal on the current grid; return (expansions, ns)."""
        t0 = time.perf_counter_ns()
        result = type(self).search_fn(self.grid.width, self.grid.height, self._is_blocked, agent, self.goal)
        ns = time.perf_counter_ns() - t0
        self.path = result["path"] if result["path"] else [agent]    # [agent] alone = no route
        self.idx = 0
        return result["expanded"], ns

    def next_step(self):
        if self.idx + 1 >= len(self.path):
            return None
        self.idx += 1
        return self.path[self.idx]

    def current_path(self):
        return self.path[self.idx:]

    def on_move(self, agent):
        assert agent == self.path[self.idx], "agent left the planned path"
        # Nothing to do: the path is still valid because nothing changed.

    def on_change(self, agent, changed):
        assert agent == self.path[self.idx], "agent left the planned path"
        if self._needs_replan(changed):
            expansions, ns = self._plan_from(agent)
            self._record_replan(expansions, ns)
            self.last_event_expansions, self.last_event_ns = expansions, ns
        else:
            self.last_event_expansions, self.last_event_ns = 0, 0

    def _needs_replan(self, changed):
        return True               # the "restart" planners always replan


class BFSRestart(PathPlanner):
    name = "bfs_restart"
    search_fn = staticmethod(bfs.search)


class AStarRestart(PathPlanner):
    name = "astar_restart"
    search_fn = staticmethod(astar.search)


class AStarLazy(PathPlanner):
    name = "astar_lazy"
    search_fn = staticmethod(astar.search)

    def _needs_replan(self, changed):
        """Replan only if a newly blocked cell lies on the rest of the path."""
        remaining = set(self.path[self.idx + 1:])
        return any(c in remaining for c in changed)


class DStarLitePlanner(Planner):
    name = "dstar_lite"

    def init(self, grid, start, goal):
        self.grid, self.goal = grid, goal
        self.ds = DStarLite(grid.width, grid.height, self._is_blocked, start, goal)
        t0 = time.perf_counter_ns()
        self.ds.compute_shortest_path()
        self.initial_time_ns = time.perf_counter_ns() - t0
        self.initial_expansions = self.ds.expanded_last

    def next_step(self):
        return self.ds.next_step()

    def current_path(self):
        return self.ds.current_path()

    def on_move(self, agent):
        # Like the game's goblin: move_start + compute every step. With no changes
        # this usually expands nothing, but any work it does is counted (separately).
        t0 = time.perf_counter_ns()
        self.ds.move_start(agent)
        self.ds.compute_shortest_path()
        self.move_time_ns_total += time.perf_counter_ns() - t0
        self.move_expansions_total += self.ds.expanded_last

    def on_change(self, agent, changed):
        t0 = time.perf_counter_ns()
        self.ds.move_start(agent)
        self.ds.notify_changed(changed)
        self.ds.compute_shortest_path()
        ns = time.perf_counter_ns() - t0
        self._record_replan(self.ds.expanded_last, ns)
        self.last_event_expansions, self.last_event_ns = self.ds.expanded_last, ns


PLANNERS = {cls.name: cls for cls in (BFSRestart, AStarRestart, AStarLazy, DStarLitePlanner)}


def make_planner(name):
    return PLANNERS[name]()
