## Breadth-First Search (UNINFORMED search, Unit 2).
## Explores cells in rings of equal distance from the start using a FIFO queue.
## With unit step costs it finds a shortest path, but it has no idea where the
## goal is, so it usually expands many more cells than A*.
extends RefCounted

const GU = preload("res://scripts/search/grid_utils.gd")

## is_blocked: Callable(Vector2i) -> bool
## Returns { "path": Array[Vector2i] (empty if no path), "expanded": int }
static func search(w: int, h: int, is_blocked: Callable, start: Vector2i, goal: Vector2i) -> Dictionary:
	var frontier: Array[Vector2i] = [start]   # FIFO queue
	var head := 0                              # index of the queue front
	var came_from := {}
	var visited := {start: true}
	var expanded := 0
	while head < frontier.size():
		var cur: Vector2i = frontier[head]
		head += 1
		expanded += 1
		if cur == goal:
			return {"path": GU.rebuild_path(came_from, goal), "expanded": expanded}
		for n in GU.neighbors(cur, w, h):
			if not visited.has(n) and not is_blocked.call(n):
				visited[n] = true
				came_from[n] = cur
				frontier.append(n)
	return {"path": [], "expanded": expanded}
