## Main scene: builds the castle, the knight (you) and the thief (the AI),
## passes events between them and decides who wins.
extends Node2D

const World = preload("res://scripts/world.gd")
const MapView = preload("res://scripts/map_view.gd")
const Knight = preload("res://scripts/knight.gd")
const Thief = preload("res://scripts/agent/thief.gd")
const ThiefView = preload("res://scripts/thief_view.gd")
const Hud = preload("res://scripts/hud.gd")
const SHEET := preload("res://assets/kenney/tilemap_packed.png")

const THIEF_DELAY := 3.0          # seconds before the thief sneaks in

var world
var knight
var thief = null
var thief_view
var hud
var camera: Camera2D
var clock := 0.0
var game_over := ""

func _ready() -> void:
	RenderingServer.set_default_clear_color(Color("1b1420"))
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST   # crisp pixel art
	restart()

func restart() -> void:
	for c in get_children():
		c.queue_free()
	clock = 0.0
	game_over = ""
	thief = null
	world = World.new()
	world.load_file("res://levels/castle.txt")

	var map = MapView.new()
	map.setup(world, SHEET)
	add_child(map)

	thief_view = ThiefView.new()
	add_child(thief_view)

	knight = Knight.new()
	knight.setup(world, SHEET)
	knight.swung.connect(_on_knight_swing)
	add_child(knight)

	camera = Camera2D.new()
	camera.zoom = Vector2(3, 3)
	camera.position_smoothing_enabled = true
	camera.position_smoothing_speed = 8.0
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = world.width * 16
	camera.limit_bottom = world.height * 16
	knight.add_child(camera)

	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Hud.new()
	hud.knight = knight
	hud.world = world
	hud.main = self
	layer.add_child(hud)

func _process(delta: float) -> void:
	if game_over != "":
		knight.set_process(false)
		return
	clock += delta
	if thief == null and clock >= THIEF_DELAY:
		thief = Thief.new(world, world.thief_spawn)
		thief_view.setup(thief, SHEET)
		hud.thief = thief
		knight._say("The thief has entered the castle!")
	if thief != null:
		var info := {"pos": knight.position, "hp": knight.hp, "cooldown": knight.cooldown, "shield": knight.shielding, "facing": knight.facing}
		for e in thief.update(delta, info):
			match e.type:
				"hit": knight.take_damage(e.damage)
				"thief_won": game_over = "The thief escaped with the treasure!"
		if thief.mode == "dead":
			game_over = "You defeated the thief!"
	if knight.hp <= 0.0:
		game_over = "The thief has slain you..."

func _on_knight_swing(center: Vector2, radius: float, damage: float) -> void:
	if thief != null and thief.mode != "dead" and thief.pos.distance_to(center) <= radius + 7.0:
		thief.take_hit(damage)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_R: restart()
			KEY_TAB:
				thief_view.debug = not thief_view.debug
				hud.debug = thief_view.debug
