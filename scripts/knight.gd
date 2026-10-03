## The player: a knight. WASD to move, Space to swing the sword,
## hold Shift (or right mouse) to raise the shield,
## E to lock/unlock a nearby door, Q to drop a barrel barricade.
## Movement is smooth (not tile-by-tile) with a hand-written box-vs-tile
## collision check against the SAME world grid the AI uses.
extends Node2D

const TILE := 16
const SPEED := 84.0              # pixels per second (same as the thief)
const HALF := Vector2(5, 5)      # collision box half-size (smaller than a tile)
const MAX_HP := 100.0
const MAX_MANA := 6.0
const SWING_TIME := 0.25
const SWING_COOLDOWN := 0.45
const SWORD_DAMAGE := 25.0
const LOCK_COST := 2.0
const BARREL_COST := 1.0
const MAX_SHIELD := 60.0
const SHIELD_SPEED := 0.5        # move at half speed behind the shield

var world
var sheet: Texture2D
var hp := MAX_HP
var mana := 3.0
var shield_hp := MAX_SHIELD
var shielding := false
var facing := Vector2i(0, 1)
var moving := false
var walk_time := 0.0
var swing_t := -1.0              # >= 0 while swinging
var cooldown := 0.0
var hurt_flash := 0.0
var message := ""
var message_t := 0.0

signal swung(center: Vector2, radius: float, damage: float)

func setup(w, tex: Texture2D) -> void:
	world = w
	sheet = tex
	position = Vector2(world.knight_spawn) * TILE + Vector2(8, 8)

func cell() -> Vector2i:
	return Vector2i(floor(position.x / TILE), floor(position.y / TILE))

func _process(delta: float) -> void:
	var dir := Vector2(
		Input.get_axis("ui_left", "ui_right") + (float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))),
		Input.get_axis("ui_up", "ui_down") + (float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W))))
	dir = dir.limit_length(1.0)
	shielding = shield_hp > 0.0 and (Input.is_key_pressed(KEY_SHIFT) or Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT))
	if shielding:
		dir *= SHIELD_SPEED
	moving = dir.length() > 0.05
	if moving:
		if abs(dir.x) > abs(dir.y):
			facing = Vector2i(sign(dir.x), 0)
		else:
			facing = Vector2i(0, sign(dir.y))
		walk_time += delta
		_move(dir * SPEED * delta)
	cooldown = max(0.0, cooldown - delta)
	hurt_flash = max(0.0, hurt_flash - delta)
	message_t = max(0.0, message_t - delta)
	if swing_t >= 0.0:
		swing_t += delta
		if swing_t > SWING_TIME:
			swing_t = -1.0
	_pickup()
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_SPACE: _swing()
		KEY_E: _toggle_door()
		KEY_Q: _barricade()

# ---------- movement with collision ----------
## Move along x, then along y, so the knight slides along walls.
func _move(v: Vector2) -> void:
	var nx := position + Vector2(v.x, 0)
	if not _box_hits(nx): position = nx
	var ny := position + Vector2(0, v.y)
	if not _box_hits(ny): position = ny

func _box_hits(center: Vector2) -> bool:
	var lo := Vector2i(floor((center.x - HALF.x) / TILE), floor((center.y - HALF.y) / TILE))
	var hi := Vector2i(floor((center.x + HALF.x - 0.01) / TILE), floor((center.y + HALF.y - 0.01) / TILE))
	for y in range(lo.y, hi.y + 1):
		for x in range(lo.x, hi.x + 1):
			if world.is_blocked(Vector2i(x, y)):
				return true
	return false

# ---------- actions ----------
func _swing() -> void:
	if cooldown > 0.0 or shielding:
		return
	swing_t = 0.0
	cooldown = SWING_COOLDOWN
	# the blade sweeps the tile in front and its two diagonals
	var hit_center := position + Vector2(facing) * 12.0
	var hit_radius := 12.0
	# smash any barrel the blade touches
	var c := cell()
	var broke := 0
	for dy in range(-2, 3):
		for dx in range(-2, 3):
			var p := c + Vector2i(dx, dy)
			var r := Rect2(Vector2(p) * TILE, Vector2(TILE, TILE))
			var closest := Vector2(clamp(hit_center.x, r.position.x, r.end.x), clamp(hit_center.y, r.position.y, r.end.y))
			if closest.distance_to(hit_center) <= hit_radius and world.break_barrel(p):
				broke += 1
	if broke > 0:
		_say("Smashed!")
	swung.emit(hit_center, hit_radius, SWORD_DAMAGE)

func _nearest_door():
	var best = null
	var best_d := 1e9
	for p in world.doors:
		var d := (Vector2(p) * TILE + Vector2(8, 8)).distance_to(position)
		if d < TILE * 1.6 and d < best_d:
			best_d = d
			best = p
	return best

func _toggle_door() -> void:
	var door = _nearest_door()
	if door == null:
		_say("No door nearby")
		return
	match world.doors[door]:
		"open":
			if mana < LOCK_COST:
				_say("Need %d mana to lock" % int(LOCK_COST)); return
			if _box_overlaps_cell(door):
				_say("Step out of the doorway first"); return
			mana -= LOCK_COST
			world.set_door(door, "locked")
			_say("Door locked")
		"locked":
			world.set_door(door, "open")
			_say("Door unlocked")
		"broken":
			_say("This door is smashed")

func _barricade() -> void:
	var target := cell() + facing
	if not world.is_floor(target) or world.is_blocked(target) or world.doors.has(target) \
			or world.items.has(target) or target == world.thief_spawn or world.occupied.has(target):
		_say("Can't barricade there"); return
	if mana < BARREL_COST:
		_say("Need mana for a barricade"); return
	mana -= BARREL_COST
	world.add_barrel(target)
	_say("Barricade placed")

func _box_overlaps_cell(p: Vector2i) -> bool:
	var r := Rect2(position - HALF, HALF * 2)
	return r.intersects(Rect2(Vector2(p) * TILE, Vector2(TILE, TILE)))

## Potions are knight-only ("the ways of a warrior").
func _pickup() -> void:
	var c := cell()
	if not world.items.has(c):
		return
	match world.items[c]:
		"mana_potion":
			if mana < MAX_MANA:
				mana = min(MAX_MANA, mana + 3.0)
				world.items.erase(c)
				_say("+3 mana")
		"health_potion":
			if hp < MAX_HP:
				hp = min(MAX_HP, hp + 35.0)
				world.items.erase(c)
				_say("+35 health")
		_:
			pass  # the knight fights only with his sword - weapons stay on the floor

## The shield soaks up damage while raised and wears out; whatever it
## can't absorb goes through to the knight.
func take_damage(amount: float) -> void:
	if shielding and shield_hp > 0.0:
		var absorbed: float = min(amount, shield_hp)
		shield_hp -= absorbed
		amount -= absorbed
		if shield_hp <= 0.0:
			_say("Your shield broke!")
		else:
			_say("Blocked!")
	if amount > 0.0:
		hp = max(0.0, hp - amount)
		hurt_flash = 0.25

func _say(msg: String) -> void:
	message = msg
	message_t = 2.0

# ---------- drawing ----------
func _tile_rect(id: int) -> Rect2:
	return Rect2((id % 12) * 16, (id / 12) * 16, 16, 16)

func _draw() -> void:
	var bob: float = -abs(sin(walk_time * 14.0)) * 1.5 if moving else 0.0
	# shadow
	draw_circle(Vector2(0, 7), 5, Color(0, 0, 0, 0.3))
	var tint := Color(1, 0.4, 0.4) if hurt_flash > 0.0 else Color.WHITE
	# mirror the sprite when facing left
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(-1, 1) if facing.x < 0 else Vector2.ONE)
	draw_texture_rect_region(sheet, Rect2(Vector2(-8, -9 + bob), Vector2(16, 16)), _tile_rect(96), tint)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	if shielding:
		var sp := Vector2(facing) * 7.0 + Vector2(0, -1)
		draw_texture_rect_region(sheet, Rect2(sp - Vector2(7, 7), Vector2(14, 14)), _tile_rect(102))
	# sword swing: the sword sprite sweeps a 120 degree arc in the facing direction
	if swing_t >= 0.0:
		var base := Vector2(facing).angle()
		var a := base - 1.0 + 2.0 * (swing_t / SWING_TIME)
		draw_set_transform(Vector2.ZERO, a + PI / 2, Vector2.ONE)
		draw_texture_rect_region(sheet, Rect2(Vector2(-8, -20), Vector2(16, 16)), _tile_rect(104))
		draw_set_transform(Vector2.ZERO, 0, Vector2.ONE)
		draw_arc(Vector2.ZERO, 13, base - 1.0, a, 10, Color(1, 1, 1, 0.5), 1.5)
