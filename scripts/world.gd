## The castle: the single source of truth for the map.
## The knight's collisions, the thief's AI and the renderer all ask THIS object
## what is solid, so what you see is always what the AI believes is solid.
##
## Level legend (levels/castle.txt):
##   #  wall           .  floor          b  barrel (solid decor)
##   D  door (open by default, the knight can lock it)
##   C  cracked wall (solid; a hammer can smash it - part 2)
##   T  treasure chest  S  thief entrance / exit   K  knight spawn
##   d  dagger   a  axe   H  hammer      m  mana potion   h  health potion
##   props (solid, unbreakable): k shelf  s statue  f fountain  t table  x bars
extends "res://scripts/grid.gd"

const PROP_CHARS := {"k": "shelf", "s": "statue", "f": "fountain", "t": "table", "x": "bars"}
const ITEM_CHARS := {"d": "dagger", "a": "axe", "H": "hammer", "m": "mana_potion", "h": "health_potion"}

var walls := {}          # Vector2i -> true
var doors := {}          # Vector2i -> "open" | "locked" | "broken"
var cracked := {}        # Vector2i -> true while intact
var barrels := {}        # Vector2i -> true (breakable: decor + knight barricades)
var props := {}          # Vector2i -> prop name (solid, unbreakable)
var recent_breaks: Array[Vector2i] = []   # barrels smashed since the renderer last looked
var rubble := {}         # cracked walls that have been smashed open
var occupied := {}       # cells the thief stands on / is stepping into (no barricades there)
var items := {}          # Vector2i -> item name lying on the floor
var chest := Vector2i(-1, -1)
var chest_taken := false
var knight_spawn := Vector2i.ZERO
var thief_spawn := Vector2i.ZERO

func load_text(text: String) -> void:
	var rows := text.strip_edges().split("\n")
	height = rows.size()
	width = 0
	for y in height:
		var row: String = rows[y].strip_edges(false, true)
		width = max(width, row.length())
		for x in row.length():
			var p := Vector2i(x, y)
			var ch := row[x]
			match ch:
				"#": walls[p] = true
				"D": doors[p] = "open"
				"C": cracked[p] = true
				"b": barrels[p] = true
				"T": chest = p
				"K": knight_spawn = p
				"S": thief_spawn = p
				_:
					if PROP_CHARS.has(ch):
						props[p] = PROP_CHARS[ch]
					elif ITEM_CHARS.has(ch):
						items[p] = ITEM_CHARS[ch]
	_rebuild_blocked()

## Rebuild the `blocked` set used by every search algorithm.
func _rebuild_blocked() -> void:
	blocked.clear()
	for p in walls: blocked[p] = true
	for p in cracked: blocked[p] = true
	for p in barrels: blocked[p] = true
	for p in props: blocked[p] = true
	for p in doors:
		if doors[p] == "locked":
			blocked[p] = true
	if not chest_taken:
		blocked[chest] = true

func is_wall_like(p: Vector2i) -> bool:
	return not in_bounds(p) or walls.has(p) or cracked.has(p)

func is_floor(p: Vector2i) -> bool:
	return in_bounds(p) and not is_wall_like(p)

func set_door(p: Vector2i, state: String) -> void:
	doors[p] = state
	_rebuild_blocked()

func add_barrel(p: Vector2i) -> void:
	barrels[p] = true
	_rebuild_blocked()

func remove_barrel(p: Vector2i) -> void:
	barrels.erase(p)
	_rebuild_blocked()

func break_barrel(p: Vector2i) -> bool:
	if not barrels.has(p):
		return false
	barrels.erase(p)
	recent_breaks.append(p)
	_rebuild_blocked()
	return true

## What kind of obstacle is at p? ("" = walkable)
func obstacle_kind(p: Vector2i) -> String:
	if not in_bounds(p) or walls.has(p) or props.has(p):
		return "wall"
	if cracked.has(p): return "cracked"
	if barrels.has(p): return "barrel"
	if doors.get(p, "") == "locked": return "door"
	if p == chest and not chest_taken: return "chest"
	return ""

## Smash whatever breakable obstacle is at p. Returns true if something broke.
func smash(p: Vector2i) -> bool:
	match obstacle_kind(p):
		"barrel":
			return break_barrel(p)
		"door":
			doors[p] = "broken"
			recent_breaks.append(p)
			_rebuild_blocked()
			return true
		"cracked":
			cracked.erase(p)
			rubble[p] = true
			recent_breaks.append(p)
			_rebuild_blocked()
			return true
	return false

func take_chest() -> void:
	chest_taken = true
	_rebuild_blocked()
