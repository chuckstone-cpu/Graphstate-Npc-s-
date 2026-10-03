## The goblin's BELIEF about the map (partially observable environment, Unit 1).
##
## Default reasoning (Unit 4): any cell the goblin has never seen is ASSUMED
## FREE (the "freespace assumption" from the D* Lite paper). When the goblin
## sees something that contradicts a belief, the belief is revised and the
## changed cells are reported so the planner can repair its path.
extends RefCounted

var width: int
var height: int
var known_blocked := {}   # cells the goblin believes are walls
var seen := {}            # cells the goblin has ever seen
var visible := {}         # cells visible right now

func _init(w: int, h: int) -> void:
	width = w
	height = h

func is_blocked(p: Vector2i) -> bool:
	if p.x < 0 or p.y < 0 or p.x >= width or p.y >= height:
		return true
	return known_blocked.has(p)

## Look around: every cell within `radius` with clear line of sight is observed.
## Returns the list of cells whose blocked/free status CHANGED in the belief.
func sense(world, from: Vector2i, radius: int) -> Array[Vector2i]:
	var changed: Array[Vector2i] = []
	visible.clear()
	for y in range(from.y - radius, from.y + radius + 1):
		for x in range(from.x - radius, from.x + radius + 1):
			var p := Vector2i(x, y)
			if not world.in_bounds(p):
				continue
			if (p - from).length_squared() > radius * radius:
				continue
			if not world.line_of_sight(from, p):
				continue
			visible[p] = true
			seen[p] = true
			var truth: bool = world.is_blocked(p)
			if truth != known_blocked.has(p):
				if truth:
					known_blocked[p] = true
				else:
					known_blocked.erase(p)
				changed.append(p)
	return changed
