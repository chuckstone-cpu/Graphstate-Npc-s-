## The goblin: a goal-based, model-based agent (Unit 1).
## Each time it reaches the centre of a tile it runs one SENSE -> BELIEVE -> PLAN
## -> ACT cycle:
##   1. sense:   look around (field of view), revise beliefs
##   2. believe: changed cells are passed to D* Lite
##   3. plan:    D* Lite repairs the path incrementally
##   4. act:     return the next tile to walk to
## Plain logic: no Node, no drawing. main.gd handles visuals.
extends RefCounted

const Belief = preload("res://scripts/agent/belief.gd")
const DStarLite = preload("res://scripts/search/dstar_lite.gd")
const AStar = preload("res://scripts/search/astar.gd")

const VIEW_RADIUS := 5

var pos: Vector2i
var belief
var planner                        # DStarLite for the current goal
var goals: Array[Vector2i] = []    # treasure first, then the exit
var has_treasure := false
var state := "planning"            # planning | moving | stuck | escaped
var bubble := ""                   # "!" saw a change, "?" no route
var events: Array[String] = []

# Benchmark numbers for the HUD and the report
var replans := 0
var dstar_total := 0               # D* Lite expansions summed over all replans
var astar_total := 0               # what repeated A* from scratch would have cost
var last_dstar := 0
var last_astar := 0

func _init(world, start: Vector2i, treasure: Vector2i, exit_cell: Vector2i) -> void:
	pos = start
	goals = [treasure, exit_cell]
	belief = Belief.new(world.width, world.height)
	_new_planner(world)

func current_goal() -> Vector2i:
	return goals[0]

func _new_planner(world) -> void:
	planner = DStarLite.new(world.width, world.height, belief.is_blocked, pos, current_goal())

func _say(msg: String) -> void:
	events.push_front(msg)
	if events.size() > 8:
		events.pop_back()

## One decision. Returns the next cell to move to, or null to wait.
func decide(world):
	bubble = ""
	# --- reached the current goal? ---
	if pos == current_goal():
		if not has_treasure:
			has_treasure = true
			goals.pop_front()
			_say("Got the treasure! Heading for the exit.")
			_new_planner(world)
		else:
			state = "escaped"
			_say("Escaped with the treasure.")
			return null

	# --- 1. SENSE + 2. BELIEVE ---
	planner.move_start(pos)
	var changed: Array[Vector2i] = belief.sense(world, pos, VIEW_RADIUS)
	if not changed.is_empty():
		planner.notify_changed(changed)

	# --- 3. PLAN (incremental repair) ---
	var had_path_before: bool = planner.has_path()
	planner.compute_shortest_path()
	if planner.expanded_last > 0:
		replans += 1
		last_dstar = planner.expanded_last
		last_astar = AStar.search(world.width, world.height, belief.is_blocked, pos, current_goal())["expanded"]
		dstar_total += last_dstar
		astar_total += last_astar
		if not changed.is_empty() and replans > 1:
			bubble = "!"
			_say("Map changed (%d cells). Repaired path: D* %d vs A* %d expansions." % [changed.size(), last_dstar, last_astar])

	# --- 4. ACT ---
	var nxt = planner.next_step()
	if nxt == null:
		state = "stuck"
		bubble = "?"
		if had_path_before:
			_say("No route left that I know of. Waiting...")
		return null
	state = "moving"
	return nxt
