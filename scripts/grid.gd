## The TRUE world map. One source of truth: the AI and the renderer both read
## this, so the goblin can never walk through a wall that is drawn on screen.
##
## Level files are plain text, one character per tile:
##   #  wall        .  floor
##   G  goblin start
##   T  treasure    E  exit
extends RefCounted

var width := 0
var height := 0
var blocked := {}        # Vector2i -> true for every wall cell
var markers := {}        # character -> Vector2i (G, T, E ...)

func load_text(text: String) -> void:
	var rows := text.strip_edges().split("\n")
	height = rows.size()
	width = 0
	blocked.clear()
	markers.clear()
	for y in height:
		var row: String = rows[y].strip_edges(false, true)
		width = max(width, row.length())
		for x in row.length():
			var ch := row[x]
			var p := Vector2i(x, y)
			if ch == "#":
				blocked[p] = true
			elif ch != ".":
				markers[ch] = p

func load_file(path: String) -> void:
	load_text(FileAccess.get_file_as_string(path))

func in_bounds(p: Vector2i) -> bool:
	return p.x >= 0 and p.y >= 0 and p.x < width and p.y < height

func is_blocked(p: Vector2i) -> bool:
	return not in_bounds(p) or blocked.has(p)

func set_blocked(p: Vector2i, value: bool) -> void:
	if value:
		blocked[p] = true
	else:
		blocked.erase(p)

## Line of sight with Bresenham's line algorithm: can you see `to` from `from`
## without a wall in between? (The target cell itself may be a wall.)
func line_of_sight(from: Vector2i, to: Vector2i) -> bool:
	var x0 := from.x; var y0 := from.y
	var dx: int = abs(to.x - x0); var dy: int = -abs(to.y - y0)
	var sx := 1 if x0 < to.x else -1
	var sy := 1 if y0 < to.y else -1
	var err := dx + dy
	while true:
		if x0 == to.x and y0 == to.y:
			return true
		if not (x0 == from.x and y0 == from.y) and is_blocked(Vector2i(x0, y0)):
			return false
		var e2 := 2 * err
		if e2 >= dy:
			err += dy; x0 += sx
		if e2 <= dx:
			err += dx; y0 += sy
	return true
