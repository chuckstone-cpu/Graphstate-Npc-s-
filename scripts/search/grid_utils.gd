## Small helpers shared by every search algorithm.
## A grid cell is a Vector2i(x, y). Movement is 4-directional, each step costs 1.
extends RefCounted

const DIRS: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]

## Manhattan distance: admissible for 4-way movement with unit cost
## (it never overestimates the true number of steps).
static func manhattan(a: Vector2i, b: Vector2i) -> float:
	return float(abs(a.x - b.x) + abs(a.y - b.y))

static func in_bounds(p: Vector2i, w: int, h: int) -> bool:
	return p.x >= 0 and p.y >= 0 and p.x < w and p.y < h

static func neighbors(p: Vector2i, w: int, h: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for d in DIRS:
		var n := p + d
		if in_bounds(n, w, h):
			out.append(n)
	return out

static func rebuild_path(came_from: Dictionary, goal: Vector2i) -> Array[Vector2i]:
	var path: Array[Vector2i] = [goal]
	var cur := goal
	while came_from.has(cur):
		cur = came_from[cur]
		path.push_front(cur)
	return path
