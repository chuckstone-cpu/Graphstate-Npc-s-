## Minimax with alpha-beta pruning (ADVERSARIAL search, Unit 2).
##
## When the armed thief is close to the knight, the fight is modelled as a
## small two-player, zero-sum, turn-based game on the grid:
##   - MAX player = thief, MIN player = knight, they alternate moves
##   - each move: step up/down/left/right, stay, or attack (only if adjacent
##     and the attack is off cooldown)
##   - the knight's sword sweeps a 3-tile ARC in front of him (front tile + its
##     two diagonals) and he can spend a turn turning to face the thief. So the
##     thief can win fights by circling round and stabbing from the side or behind.
##   - the thief's short weapon also reaches DIAGONAL tiles (where the sword
##     can't), so hit-and-run from the corners is a real tactic.
##   - the evaluation scores a position from the THIEF's point of view
## Real time is handled by treating each tile step as one turn. The thief runs
## this search every time it reaches a tile centre and plays the best first move.
extends RefCounted

const DIRS: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
const WIN := 1000.0

var is_blocked: Callable     # cell -> bool (walls etc.)
var thief_dmg := 9.0
var thief_cd_max := 2        # turns between thief attacks
var knight_dmg := 25.0
var knight_cd_max := 2
var nodes := 0               # nodes visited in the last search

func _init(blocked_fn: Callable) -> void:
	is_blocked = blocked_fn

## state = {"t": Vector2i, "k": Vector2i, "kf": Vector2i (knight facing),
##          "thp": float, "khp": float, "tcd": int, "kcd": int}
## Returns {"move": "attack" | "stay" | Vector2i(step direction), "value": float, "nodes": int}
func best_move(state: Dictionary, depth: int, use_pruning := true) -> Dictionary:
	nodes = 0
	var best_val := -INF
	var best = "stay"
	var alpha := -INF
	var beta := INF
	for m in _moves(state, true):
		var child := _apply(state, m, true)
		var v := _search(child, depth - 1, alpha, beta, false, use_pruning)
		if v > best_val:
			best_val = v
			best = m
		if use_pruning:
			alpha = max(alpha, best_val)
	return {"move": best, "value": best_val, "nodes": nodes}

func _search(s: Dictionary, depth: int, alpha: float, beta: float, thief_turn: bool, prune: bool) -> float:
	nodes += 1
	if s.thp <= 0.0: return -WIN - depth      # lose sooner = worse
	if s.khp <= 0.0: return WIN + depth       # win sooner = better
	if depth == 0:
		return evaluate(s)
	if thief_turn:
		var v := -INF
		for m in _moves(s, true):
			v = max(v, _search(_apply(s, m, true), depth - 1, alpha, beta, false, prune))
			if prune:
				alpha = max(alpha, v)
				if alpha >= beta:
					break                  # beta cut-off: the knight would never allow this
		return v
	else:
		var v := INF
		for m in _moves(s, false):
			v = min(v, _search(_apply(s, m, false), depth - 1, alpha, beta, true, prune))
			if prune:
				beta = min(beta, v)
				if alpha >= beta:
					break                  # alpha cut-off: the thief already has better
		return v

## Score from the thief's view: damage dealt is good, damage taken is twice as
## bad (it has less HP), being adjacent with a ready weapon is good, being
## adjacent to a knight whose sword is ready is bad.
func evaluate(s: Dictionary) -> float:
	var score: float = (100.0 - s.khp) - 2.0 * (50.0 - s.thp)
	var adjacent: bool = _cheb(s.t, s.k) == 1
	var exposed: bool = in_arc(s.k, s.kf, s.t)
	if adjacent and s.tcd == 0: score += 4.0
	if exposed and s.kcd == 0: score -= 8.0          # inside the arc of a ready sword
	if adjacent and not exposed: score += 2.0        # flanking position
	score -= 0.3 * _dist(s.t, s.k)          # stay engaged
	return score

func _dist(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)

## Is cell c inside the sword arc of a knight at k facing f?
static func in_arc(k: Vector2i, f: Vector2i, c: Vector2i) -> bool:
	var perp := Vector2i(f.y, f.x)
	var front := k + f
	return c == front or c == front + perp or c == front - perp

## Direction the knight should face to bring c into his arc.
static func face_towards(k: Vector2i, c: Vector2i) -> Vector2i:
	var d := c - k
	if abs(d.x) >= abs(d.y):
		return Vector2i(sign(d.x), 0)
	return Vector2i(0, sign(d.y))

## Chebyshev distance: 1 for the 8 surrounding tiles (diagonals included).
func _cheb(a: Vector2i, b: Vector2i) -> int:
	return max(abs(a.x - b.x), abs(a.y - b.y))

func _moves(s: Dictionary, thief: bool) -> Array:
	var me: Vector2i = s.t if thief else s.k
	var other: Vector2i = s.k if thief else s.t
	var cd: int = s.tcd if thief else s.kcd
	var out: Array = []
	if thief:
		if cd == 0 and _cheb(me, other) == 1:
			out.append("attack")             # try attacks first: better pruning
	else:
		var hit := in_arc(me, s.kf, other)
		if cd == 0 and hit:
			out.append("attack")             # the sword only reaches the arc in front
		if _cheb(me, other) == 1 and not hit:
			out.append("turn")               # turn to face the thief
	for d in DIRS:
		var n := me + d
		if n != other and not is_blocked.call(n):
			out.append(d)
	out.append("stay")
	return out

func _apply(s: Dictionary, m, thief: bool) -> Dictionary:
	var n := s.duplicate()
	if thief:
		n.tcd = max(0, s.tcd - 1)
		if m is String and m == "attack":
			n.khp = s.khp - thief_dmg
			n.tcd = thief_cd_max
		elif m is Vector2i:
			n.t = s.t + m
	else:
		n.kcd = max(0, s.kcd - 1)
		if m is String and m == "attack":
			n.thp = s.thp - knight_dmg
			n.kcd = knight_cd_max
		elif m is String and m == "turn":
			n.kf = face_towards(s.k, s.t)
		elif m is Vector2i:
			n.k = s.k + m
			n.kf = m
	return n
