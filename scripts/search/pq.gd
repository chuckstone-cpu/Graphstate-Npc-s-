## Min-priority queue (binary heap) used by A* and D* Lite.
## Each entry is [key1, key2, item]; entries are ordered by key1, then key2
## (lexicographic order, exactly how D* Lite compares its two-part keys).
extends RefCounted

var _data: Array = []

func size() -> int:
	return _data.size()

func is_empty() -> bool:
	return _data.is_empty()

func push(k1: float, k2: float, item) -> void:
	_data.append([k1, k2, item])
	_sift_up(_data.size() - 1)

## Look at the smallest entry without removing it.
func top() -> Array:
	return _data[0]

## Remove and return the smallest entry.
func pop() -> Array:
	var first: Array = _data[0]
	var last: Array = _data.pop_back()
	if not _data.is_empty():
		_data[0] = last
		_sift_down(0)
	return first

static func less(a: Array, b: Array) -> bool:
	return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1])

func _sift_up(i: int) -> void:
	while i > 0:
		var parent := (i - 1) / 2
		if less(_data[i], _data[parent]):
			var tmp = _data[i]; _data[i] = _data[parent]; _data[parent] = tmp
			i = parent
		else:
			return

func _sift_down(i: int) -> void:
	var n := _data.size()
	while true:
		var smallest := i
		var l := 2 * i + 1
		var r := 2 * i + 2
		if l < n and less(_data[l], _data[smallest]): smallest = l
		if r < n and less(_data[r], _data[smallest]): smallest = r
		if smallest == i:
			return
		var tmp = _data[i]; _data[i] = _data[smallest]; _data[smallest] = tmp
		i = smallest
