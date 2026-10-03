## Headless simulations of the thief AI.  godot --headless -s tests/test_thief.gd
extends SceneTree

const World = preload("res://scripts/world.gd")
const Thief = preload("res://scripts/agent/thief.gd")

var failures := 0
func check(c: bool, m: String) -> void:
	print(("  PASS  " if c else "  FAIL  ") + m)
	if not c: failures += 1

func _init() -> void:
	print("== Thief simulations ==")
	scenario("[A] nobody guarding, doors open", [], Vector2i(5, 5), false, "won")
	scenario("[B] both vault doors locked", [Vector2i(50, 6), Vector2i(55, 13)], Vector2i(5, 5), false, "won")
	scenario("[C] knight guards the chest and swings", [], Vector2i(56, 9), true, "")
	scenario("[D] knight guards, doors locked", [Vector2i(50, 6), Vector2i(55, 13)], Vector2i(56, 9), true, "")
	print("== %s ==" % ("ALL PASSED" if failures == 0 else "%d FAILED" % failures))
	quit(failures)

## A crude scripted knight: stands still and swings when the thief is close.
func scenario(name: String, locked: Array, knight_cell: Vector2i, knight_swings: bool, expect: String) -> void:
	print(name)
	var w = World.new(); w.load_file("res://levels/castle.txt")
	for d in locked: w.set_door(d, "locked")
	var th = Thief.new(w, w.thief_spawn)
	var kpos := Vector2(knight_cell) * 16 + Vector2(8, 8)
	var khp := 100.0
	var kcd := 0.0
	var dt := 1.0 / 30.0
	var t := 0.0
	var last_method := ""
	var log_lines := []
	while t < 240.0:
		t += dt
		kcd = max(0.0, kcd - dt)
		var ev: Array = th.update(dt, {"pos": kpos, "hp": khp, "cooldown": kcd, "shield": false, "facing": Vector2i(0, -1)})
		for e in ev:
			if e.type == "hit": khp -= e.damage
		# an eager human: swings whenever the thief is within ~2.5 tiles,
		# but only hits if the thief is actually in sword reach
		if knight_swings and kcd <= 0.0 and th.pos.distance_to(kpos) <= 40.0:
			kcd = 0.45
			if th.pos.distance_to(kpos) <= 22.0:
				th.take_hit(25.0)
		if th.method != last_method:
			last_method = th.method
			log_lines.append("t=%5.1fs  plan: %s" % [t, th.method])
		if th.mode in ["won", "dead"] or khp <= 0.0:
			break
	for l in log_lines: print("      " + l)
	for e in th.events: print("      thought: " + e)
	var result: String = th.mode if th.mode in ["won", "dead"] else ("knight_dead" if khp <= 0 else "timeout")
	print("      result: %s at t=%.1fs  thief hp %.0f  knight hp %.0f  weapon '%s'  D* exp %d  minimax ab %d vs plain %d" % [result, t, th.hp, khp, th.weapon, th.dstar_expanded, th.mm_total_ab, th.mm_total_plain])
	if expect != "":
		check(result == expect, "%s -> %s" % [name, expect])
	else:
		check(result != "timeout", "%s ends in a decision (%s)" % [name, result])
