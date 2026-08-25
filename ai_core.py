import json
import heapq

class DStarLite:
    def __init__(self, matrix):
        self.matrix = matrix
        self.height = len(matrix)
        self.width = len(matrix[0])
        self.U = []
        self.k_m = 0
        self.rhs = {}
        self.g = {}
        self.s_start = None
        self.s_goal = None

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def calculate_key(self, s):
        g_rhs = min(self.g.get(s, float('inf')), self.rhs.get(s, float('inf')))
        return (g_rhs + self.heuristic(self.s_start, s) + self.k_m, g_rhs)

    def get_neighbors(self, s):
        x, y = s
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.matrix[ny][nx] != float('inf'):
                    neighbors.append((nx, ny))
        return neighbors

    def cost(self, u, v):
        return self.matrix[v[1]][v[0]]

    def update_vertex(self, u):
        if u != self.s_goal:
            min_rhs = float('inf')
            for succ in self.get_neighbors(u):
                min_rhs = min(min_rhs, self.g.get(succ, float('inf')) + self.cost(u, succ))
            self.rhs[u] = min_rhs

        # Remove u from priority queue if it exists
        self.U = [item for item in self.U if item[1] != u]
        heapq.heapify(self.U)

        if self.g.get(u, float('inf')) != self.rhs.get(u, float('inf')):
            heapq.heappush(self.U, (self.calculate_key(u), u))

    def top_key(self):
        if self.U:
            return self.U[0][0]
        return (float('inf'), float('inf'))

    def compute_shortest_path(self):
        while self.U and (self.top_key() < self.calculate_key(self.s_start) or self.rhs.get(self.s_start, float('inf')) != self.g.get(self.s_start, float('inf'))):
            k_old, u = heapq.heappop(self.U)
            k_new = self.calculate_key(u)

            if k_old < k_new:
                heapq.heappush(self.U, (k_new, u))
            elif self.g.get(u, float('inf')) > self.rhs.get(u, float('inf')):
                self.g[u] = self.rhs.get(u, float('inf'))
                for pred in self.get_neighbors(u):
                    self.update_vertex(pred)
            else:
                self.g[u] = float('inf')
                for pred in self.get_neighbors(u) + [u]:
                    self.update_vertex(pred)

    def find_path(self, start, goal):
        self.s_start = tuple(start)
        self.s_goal = tuple(goal)
        self.U = []
        self.rhs = {}
        self.g = {}
        self.k_m = 0

        self.rhs[self.s_goal] = 0
        heapq.heappush(self.U, (self.calculate_key(self.s_goal), self.s_goal))

        self.compute_shortest_path()

        path = []
        curr = self.s_start
        if self.g.get(curr, float('inf')) == float('inf'):
            return []

        # Reconstruct path
        while curr != self.s_goal:
            path.append(list(curr))
            min_cost = float('inf')
            next_node = None
            
            for succ in self.get_neighbors(curr):
                c = self.cost(curr, succ) + self.g.get(succ, float('inf'))
                if c < min_cost:
                    min_cost = c
                    next_node = succ
            
            if next_node is None:
                break
            curr = next_node

        path.append(list(self.s_goal))
        return path


class StrategicPlanner:
    def __init__(self, matrix):
        self.matrix = matrix
        self.pathfinder = DStarLite(matrix)
        
    def get_potion(self):
        print("Action: get_potion() executed.")
        
    def get_key(self, current_pos, key_pos):
        print(f"Action: get_key() - Pathing from {current_pos} to {key_pos}...")
        path = self.pathfinder.find_path(current_pos, key_pos)
        return path
        
    def unlock_door(self, door_coord):
        print(f"Action: unlock_door() at {door_coord} executed.")
        
    def get_chest(self):
        print("Action: get_chest() executed.")
        
    def test_planner(self):
        print("Strategic Planner: Need key to progress.")
        
        # Open Door 1: Set to walkable
        self.matrix[16][2] = 1.0  # [2, 16] is x=2, y=16
        self.matrix[17][2] = 1.0  # [2, 17] is x=2, y=17
        
        start = [1, 18]
        target = [16, 11]  # key
        
        path = self.get_key(start, target)
        
        if not path:
            print(f"\nNo valid path found from {start} to {target}. Target may be impassable or unreachable.")
            return

        # Calculate total path cost
        total_cost = 0
        for i in range(len(path) - 1):
            nxt = path[i+1]
            total_cost += self.matrix[nxt[1]][nxt[0]]
            
        print(f"\nTotal Path Cost: {total_cost}")
        
        print("\nResulting Path (Coordinates):")
        for p in path:
            print(p)

        print("\n--- ASCII Map with Path ---")
        path_set = {tuple(p) for p in path}
        for y in range(len(self.matrix)):
            row_str = ""
            for x in range(len(self.matrix[0])):
                if (x, y) in path_set:
                    if [x, y] == start:
                        row_str += "S " # Start
                    elif [x, y] == target:
                        row_str += "T " # Target
                    else:
                        row_str += "* "
                else:
                    val = self.matrix[y][x]
                    if val == float('inf'):
                        row_str += "# "
                    elif val == 11:
                        row_str += "x " # poison skull tile
                    else:
                        row_str += ". "
            print(row_str)

def main():
    filepath = "map.json"
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading map: {e}")
        return

    width = data.get('width', 20)
    height = data.get('height', 20)
    
    walls_layer = next((l for l in data.get('layers', []) if l.get('name') == 'walls and obstacles'), None)
    if not walls_layer:
        print("Error: 'walls and obstacles' layer not found.")
        return

    walls_data = walls_layer.get('data', [])
    
    # These tiles were accidentally placed in the walls layer but are actually floor tiles
    floor_tiles = {27, 28, 29, 30, 31, 40, 41, 42, 43, 44, 46}
    
    # 0 = walkable, 1 = impassable, 85/86 = walkable with +10 cost
    matrix = []
    for y in range(height):
        row = []
        for x in range(width):
            idx = y * width + x
            gid = walls_data[idx]
            tile_id = gid & 0x1FFFFFFF
            
            if tile_id == 85 or tile_id == 86:
                row.append(11) # Base cost 1 + 10 penalty
            elif tile_id != 0 and tile_id not in floor_tiles:
                row.append(float('inf')) # Impassable
            else:
                row.append(1) # Walkable (cost 1)
                
        matrix.append(row)
        
    planner = StrategicPlanner(matrix)
    planner.test_planner()

if __name__ == "__main__":
    main()
