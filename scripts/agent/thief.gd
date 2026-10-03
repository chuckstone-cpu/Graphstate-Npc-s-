## The thief: the AI opponent. Pure logic (no drawing) so it can be tested headless.
##
## Every time it reaches the centre of a tile it runs one decision cycle:
##   1. SENSE    look around (7 tiles, line of sight); revise beliefs; spot the knight
##   2. DECIDE   utility scores choose a mode: steal, fight or flee
##   3. PLAN     steal: pick a METHOD (go straight in, or fetch a weapon first)
##               by comparing A* costs, then follow it with D* Lite
##               fight: minimax + alpha-beta picks the next move or attack
##               flee: breadth-first search for the safest reachable tile
##   4. ACT      walk to the next tile, or smash / grab / attack
extends RefCounted

const Items = preload("res://scripts/items.gd")
const Belief = preload("res://scripts/agent/castle_belief.gd")
const DStarLite = preload("res://scripts/search/dstar_lite.gd")
const AStar = preload("res://scripts/search/astar.gd")
const Minimax = preload("res://scripts/search/minimax.gd")
const GU = preload("res://scripts/search/grid_utils.gd")

const TILE := 16
const MAX_HP := 50.0
const SPEED := 84.0            # px/s (knight walks at 62)
const CARRY_SPEED := 72.0      # still faster than the knight while carrying the chest
const VIEW := 7                # tiles
const STEP_TIME := 16.0 / SPEED  # seconds per tile step = one minimax "turn"
const SMASH_COST := {"barrel": 2.0, "door": 6.0, "cracked": 8.0}   # planning cost (in tiles)
const GRAB_TIME := 1.0
const ATTACK_WINDUP := 0.15
const KNIGHT_SWORD := 25.0
const KNIGHT_SWING_CD := 0.45

var world
var belief
var minimax
var pos := Vector2.ZERO
var cell := Vector2i.ZERO
var target = null              # Vector2i tile being walked into
var hp := MAX_HP
var weapon := ""
var carrying := false
var attack_cd := 0.0
var mode := "steal"            # steal | fight | flee | dead | won
var action := ""               # "" | smash | grab | attack
var action_t := 0.0
var action_total := 0.0
var action_cell := Vector2i.ZERO
var idle_t := 0.0
var time := 0.0
var facing_x := 1.0

# planning
var planner = null             # DStarLite for the current subgoal
var plan_goal := Vector2i(-1, -1)
var plan_weapon := "?"
var method := ""
var replan := true
var replan_t := 0.0
var flee_goal := Vector2i(-1, -1)
var flee_t := 0.0

# knowledge about the knight (Unit 3: facts in the knowledge base)
var knight_visible := false
var knight_last := Vector2i(-1, -1)
var knight_last_t := -100.0
var avoid_until := -1.0        # while time < avoid_until: steer clear of the knight
var fight_stall := 0.0         # seconds of fighting with no hits either way
var last_mm_value := 0.0

# for the HUD / report
var u_fight := 0.0
var u_flee := 0.0
var dstar_expanded := 0
var mm_nodes_ab := 0
var mm_nodes_plain := 0
var mm_total_ab := 0
var mm_total_plain := 0
var last_move := ""
var bubble := ""
var bubble_t := 0.0
var events: Array[String] = []

func _init(w, start: Vector2i) -> void:
	world = w
	cell = start
	pos = _center(start)
	belief = Belief.new(world)
	minimax = Minimax.new(func(p): return belief.kind(p) != "")
	_say("Slipped into the castle.")

# ---------------- helpers ----------------
func _center(p: Vector2i) -> Vector2:
	return Vector2(p) * TILE + Vector2(8, 8)

func _say(msg: String) -> void:
	events.push_front(msg)
	if events.size() > 7:
		events.pop_back()

func _bubble(b: String) -> void:
	bubble = b
	bubble_t = 1.2

func goal_cell() -> Vector2i:
	return world.thief_spawn if carrying else world.chest

## Navigation rule (uses BELIEFS + ontology): a cell blocks the thief unless it
## is walkable, or it is an obstacle the given weapon can smash.
func _nav_blocked(p: Vector2i, w: String) -> bool:
	if p == world.chest and not world.chest_taken:
		return false                     # the chest is the goal: walking "into" it = grab
	var k: String = belief.kind(p)
	if k == "":
		return false
	if k == "wall":
		return true
	return not Items.can_smash(w, k)

func _nav_extra(p: Vector2i, _w: String) -> float:
	var k: String = belief.kind(p)
	var extra: float = SMASH_COST.get(k, 0.0)
	# danger: avoid tiles near where the knight was last seen
	if (carrying or time < avoid_until) and knight_last.x >= 0 and time - knight_last_t < 12.0:
		var d := GU.manhattan(p, knight_last)
		if d < 6.0:
			extra += (6.0 - d) * 2.0
	return extra

func _blocked_fn(w: String) -> Callable:
	return func(p): return _nav_blocked(p, w)

func _extra_fn(w: String) -> Callable:
	return func(p): return _nav_extra(p, w)

func _power(w: String) -> float:
	return 0.0 if w == "" else Items.WEAPON_STATS[w]["power"]

# ---------------- main update (called every frame) ----------------
## knight = {"pos": Vector2, "hp": float, "cooldown": float, "shield": bool, "facing": Vector2i}
## Returns a list of events for main.gd, e.g. {"type": "hit", "damage": 9.0}
func update(delta: float, knight: Dictionary) -> Array:
	var out: Array = []
	if mode == "dead" or mode == "won":
		return out
	time += delta
	attack_cd = max(0.0, attack_cd - delta)
	bubble_t = max(0.0, bubble_t - delta)
	replan_t += delta
	flee_t += delta
	if mode == "fight":
		fight_stall += delta

	# watch the knight continuously (cheap): visible = in range + line of sight
	var kcell := Vector2i(floor(knight.pos.x / TILE), floor(knight.pos.y / TILE))
	knight_visible = pos.distance_to(knight.pos) <= VIEW * TILE and world.line_of_sight(cell, kcell)
	if knight_visible:
		if time - knight_last_t > 3.0:
			_say("Spotted the knight!")
			_bubble("!")
		knight_last = kcell
		knight_last_t = time
	elif mode != "fight" and time - knight_last_t > 3.0 and hp < MAX_HP:
		hp = min(MAX_HP, hp + 1.5 * delta)     # catches its breath while hidden

	# an action in progress (smashing, grabbing, attacking)
	if action != "":
		action_t -= delta
		if action_t <= 0.0:
			_finish_action(knight, out)
			action = ""
			_decide(knight, kcell)
		return out

	if target != null:
		# the tile ahead became solid mid-step (a barricade): step back
		if world.is_blocked(target) and target != world.chest:
			target = cell
		var dest := _center(target)
		var speed := CARRY_SPEED if carrying else SPEED
		if abs(dest.x - pos.x) > 0.5:
			facing_x = sign(dest.x - pos.x)
		pos = pos.move_toward(dest, speed * delta)
		if pos.distance_to(dest) < 0.01:
			cell = target
			target = null
			world.occupied.clear()
			world.occupied[cell] = true
			_on_arrive(out)
			if mode == "won":
				return out
			_decide(knight, kcell)
	else:
		idle_t += delta
		if idle_t >= 0.2:
			idle_t = 0.0
			_decide(knight, kcell)
	return out

func _on_arrive(out: Array) -> void:
	# pick up a better weapon lying here
	if world.items.has(cell):
		var item: String = world.items[cell]
		if Items.can_use("Rogue", item) and _power(item) > _power(weapon):
			world.items.erase(cell)
			if weapon != "":
				world.items[cell] = weapon       # drop the old one
			weapon = item
			replan = true
			_say("Picked up the %s." % item)
			_bubble("+")
	if carrying and cell == world.thief_spawn:
		mode = "won"
		_say("Escaped with the treasure!")
		out.append({"type": "thief_won"})

func _finish_action(knight: Dictionary, out: Array) -> void:
	match action:
		"smash":
			if world.smash(action_cell):
				belief.observe(world, action_cell)
				_say("Smashed through!")
				replan = true
		"grab":
			if not world.chest_taken:
				world.take_chest()
				carrying = true
				replan = true
				planner = null
				_say("Got the treasure! Running for the exit.")
				_bubble("$")
		"attack":
			var stats: Dictionary = Items.WEAPON_STATS[weapon]
			attack_cd = stats.cooldown
			if pos.distance_to(knight.pos) <= 25.0:      # reaches diagonal tiles too
				out.append({"type": "hit", "damage": stats.damage})
				fight_stall = 0.0

func take_hit(damage: float) -> void:
	if mode == "dead" or mode == "won":
		return
	hp -= damage
	fight_stall = 0.0
	_bubble("!!")
	if hp <= 0.0:
		hp = 0.0
		mode = "dead"
		action = ""
		_say("Defeated...")

# ---------------- decision cycle ----------------
func _decide(knight: Dictionary, kcell: Vector2i) -> void:
	# 1. SENSE
	var changed: Array[Vector2i] = belief.sense(world, cell, VIEW)
	if not changed.is_empty():
		replan = true
		for p in changed:
			if belief.kind(p) == "door":
				_say("A door is locked! Rethinking.")
				_bubble("?")
				break

	# 2. DECIDE (utility-based)
	var hp_ratio := hp / MAX_HP
	var armed := weapon != ""
	var near := knight_visible and GU.manhattan(cell, kcell) <= 6
	u_fight = (_power(weapon) * hp_ratio * 1.2 + (0.4 if knight.hp < 40.0 else 0.0)) if armed else -1.0
	u_flee = (1.0 - hp_ratio) * 1.3 + (0.0 if armed else 1.0) + (0.3 if knight.shield else 0.0)
	# minimax said fighting here is a losing trade -> fighting is less attractive
	if last_mm_value < -10.0:
		u_fight -= 0.8
	var new_mode := mode
	var cornered := knight_visible and GU.manhattan(cell, kcell) <= 2
	if fight_stall > 6.0:
		# standoff: neither side is landing hits. Back off and find another way in.
		avoid_until = time + 12.0
		fight_stall = 0.0
		_say("Standoff... trying another way around.")
		_bubble("?")
	var avoiding := time < avoid_until or carrying
	if near and (not avoiding or cornered):
		new_mode = "fight" if u_fight >= u_flee else "flee"
	elif near and avoiding:
		new_mode = "steal"
	elif (mode == "fight" or mode == "flee") and time - knight_last_t > 2.5:
		new_mode = "steal"
	if new_mode != mode:
		if new_mode == "flee": _say("Too dangerous - running!"); _bubble("!")
		elif new_mode == "fight": _say("Fighting the knight with the %s." % weapon)
		elif new_mode == "steal": _say("Lost him. Back to the plan.")
		mode = new_mode
		replan = true
		planner = null

	# 3 + 4. PLAN and ACT
	match mode:
		"fight": _act_fight(knight, kcell)
		"flee": _act_flee(kcell)
		_: _act_steal(changed)

# ---------- STEAL: hierarchical method choice + D* Lite ----------
## Method selection: compare the A* cost of going straight for the goal with
## the cost of detouring to fetch each better weapon first (a weapon may open a
## locked door / cracked wall, and being armed is worth a few steps).
func _choose_method() -> void:
	var goal := goal_cell()
	var best_cost := INF
	var best_goal := goal
	var best_desc := ""
	var direct: Dictionary = AStar.search(world.width, world.height, _blocked_fn(weapon), cell, goal, _extra_fn(weapon))
	if direct.cost < INF:
		best_cost = direct.cost
		best_desc = "go straight for the %s" % ("exit" if carrying else "chest")
	if not carrying:
		for p in world.items:
			var item: String = world.items[p]
			if not Items.can_use("Rogue", item) or _power(item) <= _power(weapon):
				continue
			var a: Dictionary = AStar.search(world.width, world.height, _blocked_fn(weapon), cell, p, _extra_fn(weapon))
			if a.cost == INF:
				continue
			var b: Dictionary = AStar.search(world.width, world.height, _blocked_fn(item), p, goal, _extra_fn(item))
			if b.cost == INF:
				continue
			var c: float = a.cost + b.cost - (8.0 if weapon == "" else 2.0)   # value of being armed
			if c < best_cost:
				best_cost = c
				best_goal = p
				best_desc = "fetch the %s, then the chest" % item
	if best_desc == "":
		method = "no known way in - waiting"
		plan_goal = Vector2i(-1, -1)
		planner = null
		return
	if best_desc != method:
		_say("Plan: " + best_desc + ".")
	method = best_desc
	if best_goal != plan_goal or plan_weapon != weapon or planner == null:
		plan_goal = best_goal
		plan_weapon = weapon
		planner = DStarLite.new(world.width, world.height, _blocked_fn(weapon), cell, plan_goal, _extra_fn(weapon))

func _act_steal(changed: Array[Vector2i]) -> void:
	if replan or replan_t > 4.0 or planner == null:
		_choose_method()
		replan = false
		replan_t = 0.0
	if planner == null:
		_bubble("?")
		return
	planner.move_start(cell)
	if not changed.is_empty():
		planner.notify_changed(changed)
	planner.compute_shortest_path()
	dstar_expanded = planner.expanded_total
	if cell == plan_goal:
		replan = true
		return
	var nxt = planner.next_step()
	if nxt == null:
		replan = true
		_bubble("?")
		return
	_step_or_act(nxt)

## Walk into the next cell, or smash / grab if something is in the way.
func _step_or_act(nxt: Vector2i) -> void:
	if nxt == world.chest and not world.chest_taken:
		_start_action("grab", nxt, GRAB_TIME)
		return
	var k: String = world.obstacle_kind(nxt)
	if k == "":
		target = nxt
		world.occupied[nxt] = true
	elif Items.can_smash(weapon, k):
		_start_action("smash", nxt, Items.SMASH_TIME[k])
		_bubble("*")
	else:
		belief.observe(world, nxt)       # it was wrong about this cell
		replan = true

func _start_action(a: String, c: Vector2i, t: float) -> void:
	action = a
	action_cell = c
	action_t = t
	action_total = t
	if c.x != cell.x:
		facing_x = sign(c.x - cell.x)

# ---------- FIGHT: minimax with alpha-beta ----------
func _act_fight(knight: Dictionary, kcell: Vector2i) -> void:
	var d := int(GU.manhattan(cell, kcell))
	if d > 3:
		# too far for the game tree: close in along an A* path
		var a: Dictionary = AStar.search(world.width, world.height, _blocked_fn(weapon), cell, kcell)
		if a.path.size() >= 2:
			_step_or_act(a.path[1])
		return
	var stats: Dictionary = Items.WEAPON_STATS[weapon]
	minimax.thief_dmg = stats.damage * (0.3 if knight.shield else 1.0)
	minimax.thief_cd_max = int(ceil(stats.cooldown / STEP_TIME))
	minimax.knight_dmg = KNIGHT_SWORD
	minimax.knight_cd_max = int(ceil(KNIGHT_SWING_CD / STEP_TIME))
	var state := {"t": cell, "k": kcell, "kf": knight.get("facing", Vector2i(0, 1)), "thp": hp, "khp": float(knight.hp),
		"tcd": int(ceil(attack_cd / STEP_TIME)), "kcd": int(ceil(knight.cooldown / STEP_TIME))}
	var best: Dictionary = minimax.best_move(state, 4, true)
	last_mm_value = best.value
	mm_nodes_ab = best.nodes
	mm_nodes_plain = minimax.best_move(state, 4, false).nodes     # same search without pruning, for comparison
	mm_total_ab += mm_nodes_ab
	mm_total_plain += mm_nodes_plain
	var m = best.move
	if m is String and m == "attack":
		last_move = "attack"
		_start_action("attack", kcell, ATTACK_WINDUP)
	elif m is Vector2i:
		last_move = "step"
		_step_or_act(cell + m)
	else:
		last_move = "wait"

# ---------- FLEE: breadth-first search for the safest tile ----------
func _act_flee(kcell: Vector2i) -> void:
	if flee_goal == Vector2i(-1, -1) or cell == flee_goal or flee_t > 1.5:
		flee_t = 0.0
		flee_goal = _safest_cell(kcell, 14)
		planner = DStarLite.new(world.width, world.height, _blocked_fn(weapon), cell, flee_goal, _extra_fn(weapon))
	planner.move_start(cell)
	planner.compute_shortest_path()
	var nxt = planner.next_step()
	if nxt != null:
		_step_or_act(nxt)

## BFS outwards up to `depth` steps; score each reachable tile by how far it is
## from the knight (and whether the knight could see it).
func _safest_cell(kcell: Vector2i, depth: int) -> Vector2i:
	var best := cell
	var best_score := -INF
	var dist := {cell: 0}
	var queue: Array[Vector2i] = [cell]
	var head := 0
	while head < queue.size():
		var c: Vector2i = queue[head]
		head += 1
		var score: float = GU.manhattan(c, kcell) - 0.3 * dist[c]
		if not world.line_of_sight(kcell, c):
			score += 4.0
		if score > best_score:
			best_score = score
			best = c
		if dist[c] >= depth:
			continue
		for n in GU.neighbors(c, world.width, world.height):
			if not dist.has(n) and belief.kind(n) == "" and n != kcell:
				dist[n] = dist[c] + 1
				queue.append(n)
	return best
