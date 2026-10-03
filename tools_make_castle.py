# Generates levels/castle.txt (64x48). Run: python tools_make_castle.py
from collections import deque
W, H = 64, 48
g = [['#'] * W for _ in range(H)]
def room(x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1): g[y][x] = '.'
def put(x, y, c): g[y][x] = c
def hline(y, x0, x1, c='.'):
    for x in range(x0, x1 + 1): g[y][x] = c
def vline(x, y0, y1, c='.'):
    for y in range(y0, y1 + 1): g[y][x] = c

# ---- 12 rooms ----
room(2, 2, 12, 11)    # Library
room(18, 3, 29, 9)    # Prison
room(35, 3, 44, 10)   # Shrine
room(51, 3, 61, 12)   # Vault
room(2, 18, 13, 27)   # Armory
room(17, 16, 31, 31)  # Great Hall
room(34, 18, 46, 29)  # Courtyard
room(50, 19, 60, 28)  # Antechamber
room(2, 35, 12, 45)   # Entrance
room(17, 36, 28, 44)  # Kitchen
room(33, 34, 45, 45)  # Barracks
room(49, 35, 61, 45)  # Storage

# ---- corridors (D = lockable door) ----
hline(6, 13, 16); put(17, 6, 'D')            # Library - Prison
hline(6, 30, 33); put(34, 6, 'D')            # Prison - Shrine
hline(6, 45, 49); put(50, 6, 'D')            # Shrine - Vault        (vault entry 1)
hline(22, 14, 16)                            # Armory - Hall
hline(23, 32, 33); hline(24, 32, 33)         # Hall - Courtyard (wide arch)
hline(24, 47, 48); put(49, 24, 'D')          # Courtyard - Antechamber
hline(40, 13, 15); put(16, 40, 'D')          # Entrance - Kitchen
hline(40, 29, 32)                            # Kitchen - Barracks
hline(40, 46, 47); put(48, 40, 'D')          # Barracks - Storage
vline(7, 12, 16); put(7, 17, 'D')            # Library - Armory
vline(6, 28, 34); vline(7, 28, 34)           # Armory - Entrance (wide)
vline(23, 10, 14); put(23, 15, 'D')          # Prison - Hall
vline(22, 32, 34); put(22, 35, 'D')          # Hall - Kitchen
vline(40, 11, 16); put(40, 17, 'D')          # Shrine - Courtyard
vline(39, 30, 33)                            # Courtyard - Barracks
vline(55, 14, 18); put(55, 13, 'D')          # Antechamber - Vault   (vault entry 2)
vline(55, 29, 34)                            # Antechamber - Storage
# secret tunnel: prison cell -> along the top -> cracked vault wall (vault entry 3)
put(24, 2, '.'); hline(1, 24, 56); put(56, 2, 'C')
# side passage: Entrance -> behind the kitchen -> Barracks (long flank route)
vline(9, 46, 46); hline(46, 9, 33, '#')      # (border row stays wall)
vline(12, 33, 34); hline(33, 12, 31); vline(31, 32, 33)   # Entrance top -> Hall bottom-right flank
put(30, 32, '#')
# cracked wall shortcut: Storage -> Antechamber side wall
hline(31, 56, 61); vline(61, 31, 34); put(60, 30, '.')
put(60, 29, 'C')

# ---- props (solid, unbreakable): s statue, f fountain, t table, k shelf, x fence ----
for x in range(3, 12):
    if x not in (6, 9): put(x, 2, 'k')                 # library shelves
for x in (4, 5, 9, 10): put(x, 6, 'k'); put(x, 9, 'k')
for x in range(18, 30):
    if x not in (20, 27): put(x, 5, 'x')               # prison bars
put(23, 3, 'x'); put(23, 4, 'x')
for (x, y) in [(20, 19), (28, 19), (20, 28), (28, 28), (24, 19), (24, 28)]: put(x, y, 's')   # hall pillars
put(40, 23, 'f'); put(40, 24, 'f')                       # courtyard fountain
for (x, y) in [(36, 20), (44, 20), (36, 27), (44, 27)]: put(x, y, 's')
for (x, y) in [(20, 38), (21, 38), (24, 38), (25, 38), (20, 42), (21, 42), (24, 42), (25, 42)]: put(x, y, 't')
for (x, y) in [(35, 36), (36, 36), (42, 36), (43, 36), (35, 43), (36, 43), (42, 43), (43, 43)]: put(x, y, 't')
# ---- barrels (breakable) ----
for (x, y) in [(50, 36), (51, 36), (50, 37), (54, 38), (55, 38), (58, 36), (60, 36), (60, 37),
               (52, 42), (53, 42), (57, 41), (58, 43), (2, 18), (13, 18), (2, 35), (12, 35),
               (17, 16), (31, 16), (17, 31), (34, 18), (46, 18), (34, 29), (46, 29),
               (50, 19), (60, 19), (28, 36), (17, 44), (33, 45), (45, 45)]:
    put(x, y, 'b')
# ---- things ----
put(3, 44, 'S')                      # thief entrance / exit
put(56, 7, 'T')                      # treasure chest
put(55, 23, 'K')                     # knight spawn
put(4, 21, 'd'); put(8, 21, 'a'); put(11, 25, 'd')      # armory weapons
put(21, 3, 'H')                      # hammer in a prison cell (near the tunnel)
put(40, 44, 'a')                     # barracks axe
put(27, 40, 'd')                     # kitchen knife
put(37, 4, 'm'); put(42, 4, 'm'); put(39, 8, 'h')       # shrine
put(11, 4, 'm'); put(59, 44, 'm'); put(58, 26, 'h')

rows = [''.join(r) for r in g]
for r in rows: assert len(r) == W
# ---- validation ----
SOLID = set('#Cbkstfx') | {'T'}
def bfs(start, blocked_extra=()):
    seen = {start}; q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            n = (x+dx, y+dy)
            if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen:
                c = rows[n[1]][n[0]]
                if c in SOLID or n in blocked_extra: continue
                seen.add(n); q.append(n)
    return seen
S = (3, 44); T = (56, 7)
reach = bfs(S)
adj = [(T[0]+dx, T[1]+dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))]
assert any(a in reach for a in adj), "chest unreachable"
floor = sum(1 for r in rows for c in r if c not in SOLID)
assert all((x, y) in reach for y in range(H) for x in range(W) if rows[y][x] not in SOLID), "isolated floor"
d1, d2 = (50, 6), (55, 13)
assert not any(a in bfs(S, {d1, d2}) for a in adj), "vault must need a door or the cracked wall"
assert any(a in bfs(S, {d1}) for a in adj) and any(a in bfs(S, {d2}) for a in adj)
open('levels/castle.txt', 'w').write('\n'.join(rows) + '\n')
print('\n'.join(rows)); print('walkable cells:', floor)
