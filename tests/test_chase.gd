## Thief vs a scripted chasing knight (3 trials).  godot --headless -s tests/test_chase.gd
extends SceneTree
const World = preload("res://scripts/world.gd")
const Thief = preload("res://scripts/agent/thief.gd")
const AStar = preload("res://scripts/search/astar.gd")
func _init():
	for trial in 3:
		var w = World.new(); w.load_file("res://levels/castle.txt")
		var th = Thief.new(w, w.thief_spawn)
		var kpos := Vector2(55, 23) * 16 + Vector2(8, 8)
		var khp := 100.0; var kcd := 0.0; var t := 0.0; var dt := 1.0/30.0
		var hits_on_knight := 0; var hits_on_thief := 0
		var waypoint = null
		var kf := Vector2i(0, 1)
		var react := 0.0
		while t < 180.0:
			t += dt; kcd = max(0.0, kcd - dt)
			for e in th.update(dt, {"pos": kpos, "hp": khp, "cooldown": kcd, "shield": false, "facing": kf}):
				if e.type == "hit": khp -= e.damage; hits_on_knight += 1
			# knight: after 20+trial*10 s starts hunting the thief along A*
			if t > 20.0 + trial * 10.0:
				var kc := Vector2i(floor(kpos.x / 16), floor(kpos.y / 16))
				if waypoint == null or kpos.distance_to(Vector2(waypoint) * 16 + Vector2(8, 8)) < 1.0:
					var a = AStar.search(w.width, w.height, w.is_blocked, kc, th.cell)
					waypoint = a.path[1] if a.path.size() >= 2 else null
				if waypoint != null:
					var dv: Vector2 = (Vector2(waypoint) * 16 + Vector2(8, 8)) - kpos
					if dv.length() > 0.5:
						kf = Vector2i(sign(dv.x), 0) if abs(dv.x) > abs(dv.y) else Vector2i(0, sign(dv.y))
					kpos = kpos.move_toward(Vector2(waypoint) * 16 + Vector2(8, 8), 62.0 * dt)
			if th.pos.distance_to(kpos) <= 22.0: react += dt
			else: react = 0.0
			if kcd <= 0.0 and react >= 0.3:
				# a human needs ~0.3 s to react: then turn towards the thief and swing
				var dv2: Vector2 = th.pos - kpos
				kf = Vector2i(sign(dv2.x), 0) if abs(dv2.x) >= abs(dv2.y) else Vector2i(0, sign(dv2.y))
			if kcd <= 0.0 and react >= 0.3 and th.pos.distance_to(kpos + Vector2(kf) * 12.0) <= 19.0:
				kcd = 0.45; th.take_hit(25.0); hits_on_thief += 1
			if th.mode in ["won", "dead"] or khp <= 0: break
		print("trial %d: %s at %.1fs | thief hp %.0f, knight hp %.0f | thief hits %d, knight hits %d | weapon %s | minimax ab %d vs plain %d" % [trial, "thief escaped" if th.mode == "won" else ("thief dead" if th.mode == "dead" else ("knight dead" if khp <= 0 else "timeout")), t, th.hp, khp, hits_on_knight, hits_on_thief, th.weapon, th.mm_total_ab, th.mm_total_plain])
		for e in th.events: print("     ", e)
	quit()
