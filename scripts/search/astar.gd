## A* search (INFORMED search, Unit 2).
## f(n) = g(n) + h(n): cost so far + Manhattan-distance estimate to the goal.
## Because Manhattan distance is admissible, the first time the goal is popped
## the path is optimal. Used here as the "replan from scratch" baseline that
## D* Lite is compared against.
extends RefCounted

const GU = preload("res://scripts/search/grid_utils.gd")
const PQ = preload("res://scripts/search/pq.gd")

## Returns { "path": Array[Vector2i] (empty if no path), "expanded": int }
static func search(w: int, h: int, is_blocked: Callable, start: Vector2i, goal: Vector2i, extra_cost := Callable()) -> Dictionary:
	var open = PQ.new()
	var g := {start: 0.0}
	var came_from := {}
	var closed := {}
	var expanded := 0
	# key1 = f, key2 = h  (ties broken toward cells closer to the goal)
	open.push(GU.manhattan(start, goal), GU.manhattan(start, goal), start)
	while not open.is_empty():
		var cur: Vector2i = open.pop()[2]
		if closed.has(cur):
			continue                     # stale duplicate entry
		closed[cur] = true
		expanded += 1
		if cur == goal:
			return {"path": GU.rebuild_path(came_from, goal), "expanded": expanded, "cost": g[cur]}
		for n in GU.neighbors(cur, w, h):
			if is_blocked.call(n) or closed.has(n):
				continue
			var step := 1.0
			if extra_cost.is_valid():
				step += extra_cost.call(n)
			var new_g: float = g[cur] + step
			if new_g < g.get(n, INF):
				g[n] = new_g
				came_from[n] = cur
				var hn := GU.manhattan(n, goal)
				open.push(new_g + hn, hn, n)
	return {"path": [], "expanded": expanded, "cost": INF}
