## Headless tests for the search code. Run from the outwit folder:
##   godot --headless -s tests/run_tests.gd
## Checks that BFS, A* and D* Lite all find optimal paths, and that D* Lite's
## REPAIRED path after walls change is exactly as short as a fresh A* search.
extends SceneTree

const Grid = preload("res://scripts/grid.gd")
const BFS = preload("res://scripts/search/bfs.gd")
const AStar = preload("res://scripts/search/astar.gd")
const DStarLite = preload("res://scripts/search/dstar_lite.gd")
const Goblin = preload("res://scripts/agent/goblin.gd")

var failures := 0

func check(cond: bool, msg: String) -> void:
	if cond:
		print("  PASS  ", msg)
	else:
		print("  FAIL  ", msg)
		failures += 1

func _init() -> void:
	print("== Outwit search tests ==")
	test_static_level()
	test_wall_drop_repair()
	test_random_dynamic()
	test_goblin_full_run()
	print("== %s (%d failures) ==" % ["ALL PASSED" if failures == 0 else "FAILED", failures])
	quit(1 if failures > 0 else 0)

func test_static_level() -> void:
	print("[1] Same optimal length from BFS, A*, D* Lite on level1")
	var w = Grid.new(); w.load_file("res://levels/level1.txt")
	var s: Vector2i = w.markers["G"]; var t: Vector2i = w.markers["T"]
	var bfs := BFS.search(w.width, w.height, w.is_blocked, s, t)
	var ast := AStar.search(w.width, w.height, w.is_blocked, s, t)
	var ds = DStarLite.new(w.width, w.height, w.is_blocked, s, t)
	ds.compute_shortest_path()
	var dpath: Array[Vector2i] = ds.current_path()
	check(bfs["path"].size() > 0, "a path exists")
	check(bfs["path"].size() == ast["path"].size(), "BFS len %d == A* len %d" % [bfs["path"].size(), ast["path"].size()])
	check(dpath.size() == ast["path"].size(), "D* len %d == A* len %d" % [dpath.size(), ast["path"].size()])
	check(ds.gv(s) == ast["path"].size() - 1, "D* g(start) %.0f == steps %d" % [ds.gv(s), ast["path"].size() - 1])
	print("      expansions: BFS %d, A* %d, D* Lite %d" % [bfs["expanded"], ast["expanded"], ds.expanded_last])

func test_wall_drop_repair() -> void:
	print("[2] Wall dropped on the route mid-walk -> D* repairs, matches A*")
	var w = Grid.new(); w.load_file("res://levels/level1.txt")
	var s: Vector2i = w.markers["G"]; var t: Vector2i = w.markers["T"]
	var ds = DStarLite.new(w.width, w.height, w.is_blocked, s, t)
	ds.compute_shortest_path()
	# walk 4 steps
	var pos := s
	for i in 4:
		pos = ds.next_step(); ds.move_start(pos); ds.compute_shortest_path()
	var path: Array[Vector2i] = ds.current_path()
	var wall_cell: Vector2i = path[3]
	w.set_blocked(wall_cell, true)
	ds.notify_changed([wall_cell])
	ds.compute_shortest_path()
	var repaired: Array[Vector2i] = ds.current_path()
	var fresh := AStar.search(w.width, w.height, w.is_blocked, pos, t)
	check(not repaired.has(wall_cell), "repaired path avoids the new wall at %s" % [wall_cell])
	check(repaired.size() == fresh["path"].size(), "repaired len %d == fresh A* len %d" % [repaired.size(), fresh["path"].size()])
	print("      repair cost: D* %d expansions vs A* from scratch %d" % [ds.expanded_last, fresh["expanded"]])

func test_random_dynamic() -> void:
	print("[3] 40 random maps, walls toggled while walking: D* always optimal")
	var rng := RandomNumberGenerator.new(); rng.seed = 42
	var ok := true
	var d_total := 0; var a_total := 0
	for trial in 40:
		var w = Grid.new(); w.width = 20; w.height = 15
		for y in w.height:
			for x in w.width:
				if rng.randf() < 0.22: w.blocked[Vector2i(x, y)] = true
		var s := Vector2i(0, 0); var t := Vector2i(19, 14)
		w.set_blocked(s, false); w.set_blocked(t, false)
		var ds = DStarLite.new(w.width, w.height, w.is_blocked, s, t)
		ds.compute_shortest_path()
		var pos := s
		for step in 60:
			if pos == t: break
			# randomly flip 3 cells (never the agent or goal)
			var changed := []
			for k in 3:
				var c := Vector2i(rng.randi_range(0, 19), rng.randi_range(0, 14))
				if c == pos or c == t: continue
				w.set_blocked(c, not w.is_blocked(c)); changed.append(c)
			ds.notify_changed(changed)
			ds.compute_shortest_path()
			var fresh := AStar.search(w.width, w.height, w.is_blocked, pos, t)
			d_total += ds.expanded_last; a_total += fresh["expanded"]
			var d_cost: float = ds.gv(pos)
			var a_cost: float = INF if fresh["path"].is_empty() else float(fresh["path"].size() - 1)
			if d_cost != a_cost:
				ok = false
				print("      mismatch trial %d step %d: D* %s A* %s" % [trial, step, d_cost, a_cost])
				break
			var nxt = ds.next_step()
			if nxt == null: break
			pos = nxt; ds.move_start(pos)
		if not ok: break
	check(ok, "D* Lite cost == A* cost after every change")
	print("      total expansions: D* Lite %d vs repeated A* %d" % [d_total, a_total])

func test_goblin_full_run() -> void:
	print("[4] Goblin agent with fog of war reaches treasure and exit")
	var w = Grid.new(); w.load_file("res://levels/level1.txt")
	var gob = Goblin.new(w, w.markers["G"], w.markers["T"], w.markers["E"])
	var steps := 0
	while gob.state != "escaped" and steps < 500:
		var nxt = gob.decide(w)
		if nxt == null and gob.state != "escaped":
			break
		if nxt != null:
			check_walkable(w, nxt)
			gob.pos = nxt
		steps += 1
	check(gob.state == "escaped", "escaped in %d steps (%d replans, D* %d vs A* %d expansions)" % [steps, gob.replans, gob.dstar_total, gob.astar_total])

func check_walkable(w, p: Vector2i) -> void:
	if w.is_blocked(p):
		check(false, "goblin stepped into a wall at %s" % [p])
