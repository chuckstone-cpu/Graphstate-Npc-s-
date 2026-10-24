"""Min-priority queue (binary heap) used by A* and D* Lite.

Literal port of scripts/search/pq.gd.
Each entry is [key1, key2, item]; entries are ordered by key1, then key2
(lexicographic order, exactly how D* Lite compares its two-part keys).

We do NOT use Python's heapq: heapq would break ties by comparing the items
(the (x, y) cells) too, which changes the order cells come out of the queue,
and so changes the expansion counts compared with the game.
"""


class PQ:
    def __init__(self):
        self._data = []

    def size(self):
        return len(self._data)

    def is_empty(self):
        return len(self._data) == 0

    def push(self, k1, k2, item):
        self._data.append([k1, k2, item])
        self._sift_up(len(self._data) - 1)

    def top(self):
        """Look at the smallest entry without removing it."""
        return self._data[0]

    def pop(self):
        """Remove and return the smallest entry."""
        first = self._data[0]
        last = self._data.pop()
        if self._data:
            self._data[0] = last
            self._sift_down(0)
        return first

    @staticmethod
    def less(a, b):
        return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1])

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2          # GDScript int division
            if PQ.less(self._data[i], self._data[parent]):
                self._data[i], self._data[parent] = self._data[parent], self._data[i]
                i = parent
            else:
                return

    def _sift_down(self, i):
        n = len(self._data)
        while True:
            smallest = i
            l = 2 * i + 1
            r = 2 * i + 2
            if l < n and PQ.less(self._data[l], self._data[smallest]):
                smallest = l
            if r < n and PQ.less(self._data[r], self._data[smallest]):
                smallest = r
            if smallest == i:
                return
            self._data[i], self._data[smallest] = self._data[smallest], self._data[i]
            i = smallest
