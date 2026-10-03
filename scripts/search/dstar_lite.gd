## D* Lite (Koenig & Likhachev, AAAI 2002) - INCREMENTAL heuristic search.
##
## Big idea: search BACKWARDS from the goal to the agent. g(s) is the cost from
## s to the goal. When the agent moves, the goal stays the same, so all those
## g-values stay valid. When a few cells change (the player drops a wall), only
## the cells whose cost-to-goal actually changed get fixed. A* would throw
## everything away and search again from scratch.
##
## Terms:
##   g(s)   - current best known cost from s to the goal
##   rhs(s) - one-step lookahead: min over neighbours s' of c(s, s') + g(s')
##   s is "consistent" when g(s) == rhs(s); inconsistent cells go in the queue
##   key(s) = [min(g, rhs) + h(start, s) + km, min(g, rhs)]
##   km     - grows each time the agent moves, so old queue keys stay valid
##            without re-sorting the whole queue
extends RefCounted

const GU = preload("res://scripts/search/grid_utils.gd")
const PQ = preload("res://scripts/search/pq.gd")

var width: int
var height: int
var is_blocked: Callable          # what the AGENT BELIEVES is blocked
var extra_cost: Callable          # optional: extra cost to ENTER a cell (e.g. a door to smash)
var start: Vector2i               # agent position
var goal: Vector2i
var last: Vector2i                # agent position at the last replan (for km)
var km := 0.0

var g := {}                       # Vector2i -> float (missing = INF)
var rhs := {}                     # Vector2i -> float (missing = INF)
var open := {}                    # Vector2i -> [k1, k2] : cells currently in the queue
var heap = PQ.new()               # may hold stale entries; `open` says which are live

# Stats for the HUD / report
var expanded_last := 0            # vertex expansions in the most recent compute
var expanded_total := 0
var touched := {}                 # cells expanded in the most recent compute (for drawing)

func _init(w: int, h: int, blocked_fn: Callable, s_start: Vector2i, s_goal: Vector2i, extra_fn := Callable()) -> void:
	width = w
	height = h
	is_blocked = blocked_fn
	extra_cost = extra_fn
	start = s_start
	last = s_start
	goal = s_goal
	rhs[goal] = 0.0
	_insert(goal)

# ---------- small helpers ----------
func gv(s: Vector2i) -> float: return g.get(s, INF)
func rhsv(s: Vector2i) -> float: return rhs.get(s, INF)

## Edge cost: 1 between two free cells (+ any extra cost for entering b),
## INF if either end is blocked. Costs are >= 1, so Manhattan stays admissible.
func cost(a: Vector2i, b: Vector2i) -> float:
	if is_blocked.call(a) or is_blocked.call(b):
		return INF
	if extra_cost.is_valid():
		return 1.0 + extra_cost.call(b)
	return 1.0

func calc_key(s: Vector2i) -> Array:
	var m: float = min(gv(s), rhsv(s))
	return [m + GU.manhattan(start, s) + km, m]

func _insert(s: Vector2i) -> void:
	var k := calc_key(s)
	open[s] = k
	heap.push(k[0], k[1], s)

## Returns the smallest live key, throwing away stale heap entries.
func _top_key() -> Array:
	while not heap.is_empty():
		var e: Array = heap.top()
		var live = open.get(e[2])
		if live != null and live[0] == e[0] and live[1] == e[1]:
			return [e[0], e[1]]
		heap.pop()
	return [INF, INF]

# ---------- the algorithm (numbers match the paper's optimised version) ----------

## Recompute rhs(u) and put u in the queue only if it is inconsistent.
func update_vertex(u: Vector2i) -> void:
	if u != goal:
		var best := INF
		for s in GU.neighbors(u, width, height):
			best = min(best, cost(u, s) + gv(s))
		rhs[u] = best
	open.erase(u)
	if gv(u) != rhsv(u):
		_insert(u)

## Process inconsistent cells until the agent's own cell is consistent and
## nothing in the queue could still improve it.
func compute_shortest_path() -> void:
	expanded_last = 0
	touched.clear()
	while PQ.less(_top_key(), calc_key(start)) or rhsv(start) != gv(start):
		if open.is_empty():
			break
		var k_old := _top_key()
		var u: Vector2i = heap.pop()[2]
		var k_new := calc_key(u)
		expanded_last += 1
		touched[u] = true
		if PQ.less(k_old, k_new):
			# key is out of date (km changed since it was queued) - re-queue
			open[u] = k_new
			heap.push(k_new[0], k_new[1], u)
		elif gv(u) > rhsv(u):
			# OVERCONSISTENT: a cheaper route was found - lock it in
			g[u] = rhsv(u)
			open.erase(u)
			for p in GU.neighbors(u, width, height):
				update_vertex(p)
		else:
			# UNDERCONSISTENT: u got more expensive (e.g. a wall appeared) -
			# reset it and let it and its neighbours find new values
			g[u] = INF
			update_vertex(u)
			for p in GU.neighbors(u, width, height):
				update_vertex(p)
	expanded_total += expanded_last

## Call when the agent has moved to a new cell (before the next compute).
func move_start(new_start: Vector2i) -> void:
	km += GU.manhattan(last, new_start)
	last = new_start
	start = new_start

## Call with every cell whose blocked/free status changed in the agent's belief.
## Every edge touching a changed cell changed cost, so the cell and all its
## neighbours need their rhs recomputed.
func notify_changed(cells: Array) -> void:
	for c in cells:
		update_vertex(c)
		for n in GU.neighbors(c, width, height):
			update_vertex(n)

func has_path() -> bool:
	return gv(start) < INF

## Greedy step: the neighbour that minimises c(start, s') + g(s').
func next_step():
	if not has_path():
		return null
	var best = null
	var best_val := INF
	for s in GU.neighbors(start, width, height):
		var v := cost(start, s) + gv(s)
		if v < best_val:
			best_val = v
			best = s
	return best

## The full planned route (for drawing the path line).
func current_path(max_len := 2000) -> Array[Vector2i]:
	var path: Array[Vector2i] = [start]
	if not has_path():
		return path
	var cur := start
	var seen := {start: true}
	while cur != goal and path.size() < max_len:
		var best = null
		var best_val := INF
		for s in GU.neighbors(cur, width, height):
			var v := cost(cur, s) + gv(s)
			if v < best_val:
				best_val = v
				best = s
		if best == null or seen.has(best):
			break
		seen[best] = true
		path.append(best)
		cur = best
	return path
