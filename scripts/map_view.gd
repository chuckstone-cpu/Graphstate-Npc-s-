## Draws the castle with the Kenney Tiny Dungeon sheet (16x16 tiles, CC0).
## Pure visuals: reads the world, never changes it.
extends Node2D

const TILE := 16
# Kenney tile ids (tilemap_packed.png is 12 tiles wide)
const T_WALL_TOP := 0
const T_WALL_FACE := 40
const T_FLOORS := [48, 48, 48, 48, 48, 48, 49, 50]
const RIM := Color("b8c2d6")
const RIM_DARK := Color("3a2733")
const T_DOOR_OPEN := 33
const T_DOOR_LOCKED := 45
const T_RUBBLE := 24
const T_CRACKED := 28
const T_BARREL := 82
const T_CHEST := 89
const T_EXIT := 9
const PROP_TILES := {"shelf": 63, "statue": 19, "fountain": 20, "table": 72, "bars": 77}
const ITEM_TILES := {"dagger": 103, "axe": 118, "hammer": 117, "mana_potion": 116, "health_potion": 115}

var world
var sheet: Texture2D
var time := 0.0
var debris := []          # [position, velocity, life]

func setup(w, tex: Texture2D) -> void:
	world = w
	sheet = tex

func _process(delta: float) -> void:
	time += delta
	# spawn wood chips for smashed barrels
	for p in world.recent_breaks:
		for i in 10:
			var ang := randf() * TAU
			debris.append([Vector2(p) * TILE + Vector2(8, 8), Vector2(cos(ang), sin(ang)) * randf_range(20, 60), 0.5])
	world.recent_breaks.clear()
	for d in debris:
		d[0] += d[1] * delta
		d[1] *= 0.9
		d[2] -= delta
	debris = debris.filter(func(d): return d[2] > 0.0)
	queue_redraw()

func _rect(id: int) -> Rect2:
	return Rect2((id % 12) * 16, (id / 12) * 16, 16, 16)

func _tile(id: int, p: Vector2i, offset := Vector2.ZERO, tint := Color.WHITE) -> void:
	draw_texture_rect_region(sheet, Rect2(Vector2(p) * TILE + offset, Vector2(TILE, TILE)), _rect(id), tint)

## Stone rim on the edges of the dark wall tops that touch a floor,
## in the style of Kenney's sample map.
func _rims(p: Vector2i) -> void:
	var o := Vector2(p) * TILE
	if world.is_floor(p + Vector2i(-1, 0)):
		draw_rect(Rect2(o, Vector2(3, TILE)), RIM)
		draw_rect(Rect2(o + Vector2(3, 0), Vector2(1, TILE)), RIM_DARK)
	if world.is_floor(p + Vector2i(1, 0)):
		draw_rect(Rect2(o + Vector2(TILE - 3, 0), Vector2(3, TILE)), RIM)
		draw_rect(Rect2(o + Vector2(TILE - 4, 0), Vector2(1, TILE)), RIM_DARK)
	if world.is_floor(p + Vector2i(0, -1)):
		draw_rect(Rect2(o, Vector2(TILE, 3)), RIM)
		draw_rect(Rect2(o + Vector2(0, 3), Vector2(TILE, 1)), RIM_DARK)

func _draw() -> void:
	for y in world.height:
		for x in world.width:
			var p := Vector2i(x, y)
			if world.walls.has(p):
				# wall with floor below shows its brick face, otherwise the dark top
				var face: bool = world.is_floor(p + Vector2i(0, 1))
				_tile(T_WALL_FACE if face else T_WALL_TOP, p)
				if not face:
					_rims(p)
				continue
			if world.cracked.has(p):
				_tile(T_CRACKED, p)
				continue
			# floor variety, deterministic per cell
			var h := int(abs(x * 73856093 ^ y * 19349663)) % T_FLOORS.size()
			_tile(T_FLOORS[h], p)
			if world.doors.has(p):
				match world.doors[p]:
					"open": _tile(T_DOOR_OPEN, p)
					"locked":
						_tile(T_DOOR_LOCKED, p)
						# padlock marker
						var c := Vector2(p) * TILE + Vector2(8, 10)
						draw_rect(Rect2(c - Vector2(2.5, 1), Vector2(5, 4)), Color("f2c14e"))
						draw_arc(c + Vector2(0, -1), 2, PI, TAU, 6, Color("f2c14e"), 1.0)
					"broken": _tile(T_RUBBLE, p)
	# thief entrance marker
	_tile(T_EXIT, world.thief_spawn, Vector2.ZERO, Color(1, 1, 1, 0.9))
	# items float gently
	for p in world.items:
		var bob: float = sin(time * 3.0 + p.x) * 1.0
		draw_circle(Vector2(p) * TILE + Vector2(8, 14), 3.5, Color(0, 0, 0, 0.25))
		_tile(ITEM_TILES[world.items[p]], p, Vector2(0, bob - 1))
	for p in world.props:
		_tile(PROP_TILES[world.props[p]], p)
	for p in world.barrels:
		_tile(T_BARREL, p)
	for d in debris:
		draw_rect(Rect2(d[0], Vector2(2, 2)), Color(0.75, 0.5, 0.3, clamp(d[2] * 2.0, 0.0, 1.0)))
	if not world.chest_taken:
		var glow := 0.5 + 0.5 * sin(time * 2.0)
		draw_circle(Vector2(world.chest) * TILE + Vector2(8, 8), 10 + glow * 2, Color(1, 0.85, 0.3, 0.12))
		_tile(T_CHEST, world.chest)
