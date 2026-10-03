## Screen-space HUD: health / mana bars, messages and the minimap.
## M toggles the big full-map view.
extends Control

const C_WALL := Color("2a1d26")
const C_FLOOR := Color("e2a76f")
const C_PROP := Color("8a7f8e")
const C_BARREL := Color("9a5b34")
const C_DOOR := Color("b0703c")
const C_LOCKED := Color("f2c14e")
const C_CRACKED := Color("6f7a8c")
const C_CHEST := Color("ffd84a")
const C_KNIGHT := Color("4ea8de")
const C_MANA := Color("4ea8de")
const C_HEALTH := Color("e05252")
const C_WEAPON := Color("e8e8f0")
const C_EXIT := Color("7bd389")

var knight
var world
var thief = null
var main = null
var debug := false
var font: Font
var big_map := false
var t := 0.0

func _ready() -> void:
	font = ThemeDB.fallback_font
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _process(delta: float) -> void:
	t += delta
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_M:
		big_map = not big_map

func _bar(pos: Vector2, w: float, frac: float, col: Color, label: String) -> void:
	draw_rect(Rect2(pos, Vector2(w, 18)), Color(0, 0, 0, 0.55))
	draw_rect(Rect2(pos + Vector2(2, 2), Vector2((w - 4) * clamp(frac, 0.0, 1.0), 14)), col)
	draw_string(font, pos + Vector2(8, 14), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color.WHITE)

func _draw() -> void:
	if knight == null or world == null:
		return
	var size := get_viewport_rect().size
	_bar(Vector2(16, 16), 220, knight.hp / knight.MAX_HP, Color("d64545"), "HP  %d / %d" % [knight.hp, knight.MAX_HP])
	_bar(Vector2(16, 40), 220, knight.mana / knight.MAX_MANA, Color("4ea8de"), "Mana  %.0f / %d" % [floor(knight.mana), knight.MAX_MANA])
	_bar(Vector2(16, 64), 220, knight.shield_hp / knight.MAX_SHIELD, Color("9aa4b8") if not knight.shielding else Color("dfe6f2"), "Shield  %d / %d" % [knight.shield_hp, knight.MAX_SHIELD] if knight.shield_hp > 0 else "Shield  BROKEN")
	if thief != null:
		_bar(Vector2(16, 92), 220, thief.hp / thief.MAX_HP, Color("8a3fb0"), "Thief  %d / %d" % [thief.hp, thief.MAX_HP])
	if debug and thief != null:
		_thief_panel(Vector2(16, size.y - 52 - 18 * (8 + thief.events.size())))
	var help := "WASD move   Space sword   Shift shield   E lock door (2 mana)   Q barricade (1)   M map   Tab thief's mind   R restart"
	draw_string(font, Vector2(16, size.y - 16), help, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 1, 0.75))
	if knight.message_t > 0.0:
		var a: float = min(1.0, knight.message_t)
		draw_string(font, Vector2(size.x / 2 - 120, size.y - 48), knight.message, HORIZONTAL_ALIGNMENT_CENTER, 240, 16, Color(1, 0.95, 0.7, a))
	if main != null and main.game_over != "":
		draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 0.55))
		draw_string(font, Vector2(0, size.y / 2 - 10), main.game_over, HORIZONTAL_ALIGNMENT_CENTER, size.x, 36, Color(1, 0.9, 0.6))
		draw_string(font, Vector2(0, size.y / 2 + 30), "Press R to play again", HORIZONTAL_ALIGNMENT_CENTER, size.x, 16, Color.WHITE)
		return
	if big_map:
		draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 0.6))
		var s: float = floor(min((size.x - 80) / world.width, (size.y - 80) / world.height))
		var origin := (size - Vector2(world.width, world.height) * s) / 2.0
		_minimap(origin, s)
		draw_string(font, origin + Vector2(0, -10), "CASTLE MAP  (M to close)", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color.WHITE)
	else:
		var s2 := 4.0
		var origin2 := Vector2(size.x - world.width * s2 - 16, 16)
		draw_rect(Rect2(origin2 - Vector2(4, 4), Vector2(world.width, world.height) * s2 + Vector2(8, 8)), Color(0, 0, 0, 0.6))
		_minimap(origin2, s2)

func _minimap(o: Vector2, s: float) -> void:
	for y in world.height:
		for x in world.width:
			var p := Vector2i(x, y)
			var col := C_FLOOR
			if world.walls.has(p): col = C_WALL
			elif world.cracked.has(p): col = C_CRACKED
			elif world.props.has(p): col = C_PROP
			elif world.barrels.has(p): col = C_BARREL
			elif world.doors.has(p): col = C_LOCKED if world.doors[p] == "locked" else C_DOOR
			draw_rect(Rect2(o + Vector2(p) * s, Vector2(s, s)), col)
	# items
	for p in world.items:
		var n: String = world.items[p]
		var c := C_WEAPON
		if n == "mana_potion": c = C_MANA
		elif n == "health_potion": c = C_HEALTH
		draw_rect(Rect2(o + Vector2(p) * s + Vector2(s, s) * 0.2, Vector2(s, s) * 0.6), c)
	# exit and chest
	draw_rect(Rect2(o + Vector2(world.thief_spawn) * s, Vector2(s, s)), C_EXIT)
	if not world.chest_taken:
		draw_rect(Rect2(o + Vector2(world.chest) * s - Vector2(s, s) * 0.3, Vector2(s, s) * 1.6), C_CHEST)
	# camera view rectangle + knight
	var kp: Vector2 = knight.position / 16.0
	var view: Vector2 = get_viewport_rect().size / 3.0 / 16.0
	draw_rect(Rect2(o + (kp - view / 2.0) * s, view * s), Color(1, 1, 1, 0.5), false, 1.0)
	# the thief: always shown, big pulsing red marker with a dark outline and a ring
	if thief != null and thief.mode != "dead":
		var tp: Vector2 = o + thief.pos / 16.0 * s
		var r: float = max(4.0, s * 1.2)
		var ring: float = r + 3.0 + 4.0 * fmod(t * 1.5, 1.0)
		draw_arc(tp, ring, 0, TAU, 24, Color(1, 0.2, 0.2, 1.0 - fmod(t * 1.5, 1.0)), 1.5)
		draw_circle(tp, r + 1.5, Color.BLACK)
		draw_circle(tp, r, Color("ff3b3b"))
		if thief.carrying:
			draw_circle(tp, r * 0.45, C_CHEST)
	var pulse := 0.6 + 0.4 * sin(t * 6.0)
	draw_circle(o + kp * s, max(2.5, s * 0.8), Color(C_KNIGHT, pulse))

func _thief_panel(o: Vector2) -> void:
	var th = thief
	var lines := [
		"THIEF'S MIND  (Tab to hide)",
		"Mode: %s    Weapon: %s%s" % [th.mode, th.weapon if th.weapon != "" else "none", "   carrying chest" if th.carrying else ""],
		"Plan: %s" % th.method,
		"Utility  fight %.2f  vs  flee %.2f" % [th.u_fight, th.u_flee],
		"Knight: %s" % ("in sight" if th.knight_visible else ("last seen at %s" % [th.knight_last] if th.knight_last.x >= 0 else "not seen yet")),
		"D* Lite expansions so far: %d" % th.dstar_expanded,
		"Minimax nodes  alpha-beta %d  vs  plain %d" % [th.mm_total_ab, th.mm_total_plain],
		"",
	]
	for e in th.events:
		lines.append("- " + e)
	draw_rect(Rect2(o - Vector2(6, 16), Vector2(400, 18 * lines.size() + 12)), Color(0, 0, 0, 0.55))
	for i in lines.size():
		draw_string(font, o + Vector2(0, i * 18), lines[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 0.85, 0.85) if i == 0 else Color.WHITE)
