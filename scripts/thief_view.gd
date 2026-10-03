## Draws the thief (Kenney sprite #112) and, with Tab, its "mind":
## field of view, planned path, mode and current plan.
extends Node2D

const TILE := 16
const WEAPON_TILES := {"dagger": 103, "axe": 118, "hammer": 117}

var agent
var sheet: Texture2D
var debug := false
var font: Font
var t := 0.0

func setup(a, tex: Texture2D) -> void:
	agent = a
	sheet = tex
	font = ThemeDB.fallback_font

func _process(delta: float) -> void:
	t += delta
	queue_redraw()

func _rect(id: int) -> Rect2:
	return Rect2((id % 12) * 16, (id / 12) * 16, 16, 16)

func _draw() -> void:
	if agent == null:
		return
	var p: Vector2 = agent.pos
	if debug and agent.mode != "dead":
		draw_arc(p, agent.VIEW * TILE, 0, TAU, 48, Color(1, 0.3, 0.3, 0.35), 1.0)
		if agent.planner != null and agent.mode != "fight":
			var path: Array[Vector2i] = agent.planner.current_path()
			var pts := PackedVector2Array([p])
			for i in range(1, path.size()):
				pts.append(Vector2(path[i]) * TILE + Vector2(8, 8))
			if pts.size() >= 2:
				draw_polyline(pts, Color(1, 0.35, 0.35, 0.8), 1.0)
	if agent.mode == "dead":
		draw_set_transform(p, PI / 2, Vector2.ONE)
		draw_texture_rect_region(sheet, Rect2(Vector2(-8, -8), Vector2(16, 16)), _rect(112), Color(0.6, 0.6, 0.6))
		draw_set_transform(Vector2.ZERO, 0, Vector2.ONE)
		return
	var moving: bool = agent.target != null
	var bob: float = -abs(sin(t * 16.0)) * 1.5 if moving else 0.0
	if agent.action == "smash":
		bob = -2.0 * abs(sin(t * 20.0))
	draw_circle(p + Vector2(0, 7), 5, Color(0, 0, 0, 0.3))
	draw_set_transform(p, 0.0, Vector2(agent.facing_x, 1))
	draw_texture_rect_region(sheet, Rect2(Vector2(-8, -9 + bob), Vector2(16, 16)), _rect(112))
	if agent.weapon != "":
		var swing: float = 0.0
		if agent.action == "attack" or agent.action == "smash":
			swing = sin(t * 25.0) * 0.8
		draw_set_transform(p + Vector2(6 * agent.facing_x, -2 + bob), (0.6 + swing) * agent.facing_x, Vector2(agent.facing_x, 1) * 0.75)
		draw_texture_rect_region(sheet, Rect2(Vector2(-8, -12), Vector2(16, 16)), _rect(WEAPON_TILES[agent.weapon]))
	draw_set_transform(Vector2.ZERO, 0, Vector2.ONE)
	if agent.carrying:
		draw_texture_rect_region(sheet, Rect2(p + Vector2(-6, -21 + bob), Vector2(12, 12)), _rect(89))
	# health bar
	var w := 14.0
	draw_rect(Rect2(p + Vector2(-w / 2, -14), Vector2(w, 2.5)), Color(0, 0, 0, 0.6))
	draw_rect(Rect2(p + Vector2(-w / 2, -14), Vector2(w * agent.hp / agent.MAX_HP, 2.5)), Color("e05252"))
	# smash / grab progress
	if agent.action == "smash" or agent.action == "grab":
		var frac: float = 1.0 - agent.action_t / max(0.01, agent.action_total)
		draw_rect(Rect2(p + Vector2(-8, 10), Vector2(16, 2)), Color(0, 0, 0, 0.6))
		draw_rect(Rect2(p + Vector2(-8, 10), Vector2(16 * frac, 2)), Color("f2c14e"))
	# thought bubble
	if agent.bubble_t > 0.0:
		draw_circle(p + Vector2(9, -20), 5.5, Color(1, 1, 1, 0.95))
		draw_string(font, p + Vector2(5.5, -16.5), agent.bubble, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color.BLACK)
	if debug:
		draw_string(font, p + Vector2(-30, 20), agent.mode.to_upper(), HORIZONTAL_ALIGNMENT_CENTER, 60, 6, Color(1, 0.8, 0.8))
