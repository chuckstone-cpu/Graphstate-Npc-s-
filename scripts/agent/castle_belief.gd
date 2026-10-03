## What the thief BELIEVES about the castle (partially observable world).
##
## Prior knowledge: the thief studied the castle's blueprints, so it knows the
## walls, furniture and cracked walls from the start. What it CANNOT know
## without seeing it: which doors the knight has locked, where new barricades
## are, what got smashed. Default reasoning: doors are assumed open until it
## sees them locked. Every time it looks around, contradicted beliefs are
## revised and the changed cells go to D* Lite.
extends RefCounted

var width: int
var height: int
var static_solid := {}   # walls + furniture (never change)
var doors := {}          # believed door states
var barrels := {}        # believed barrels
var cracked := {}        # believed intact cracked walls
var visible := {}
var seen := {}

func _init(world) -> void:
	width = world.width
	height = world.height
	for p in world.walls: static_solid[p] = true
	for p in world.props: static_solid[p] = true
	for p in world.doors: doors[p] = "open"        # default: doors are open
	barrels = world.barrels.duplicate()
	cracked = world.cracked.duplicate()

## Kind of obstacle the thief believes is at p ("" = believed walkable).
func kind(p: Vector2i) -> String:
	if p.x < 0 or p.y < 0 or p.x >= width or p.y >= height or static_solid.has(p):
		return "wall"
	if cracked.has(p): return "cracked"
	if barrels.has(p): return "barrel"
	if doors.get(p, "") == "locked": return "door"
	return ""

## Look around. Returns cells whose believed state changed.
func sense(world, from: Vector2i, radius: int) -> Array[Vector2i]:
	var changed: Array[Vector2i] = []
	visible.clear()
	for y in range(from.y - radius, from.y + radius + 1):
		for x in range(from.x - radius, from.x + radius + 1):
			var p := Vector2i(x, y)
			if not world.in_bounds(p) or (p - from).length_squared() > radius * radius:
				continue
			if not world.line_of_sight(from, p):
				continue
			visible[p] = true
			seen[p] = true
			if observe(world, p):
				changed.append(p)
	return changed

## Copy the true state of one cell into the belief. Returns true if it changed.
func observe(world, p: Vector2i) -> bool:
	var before := kind(p)
	if world.barrels.has(p): barrels[p] = true
	else: barrels.erase(p)
	if world.cracked.has(p): cracked[p] = true
	else: cracked.erase(p)
	if world.doors.has(p): doors[p] = world.doors[p]
	return kind(p) != before
