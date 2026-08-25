import json
from ai_core import DStarLite

def parse_map_to_binary_matrix(filepath):
    # Step 1: Load the JSON map data from the given filepath
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Step 2: Extract the dimensions of the map (defaults to 20x20)
    width = data.get('width', 20)
    height = data.get('height', 20)

    # Step 3: Find the "walls and obstacles" layer from the list of layers
    walls_layer = None
    for layer in data.get('layers', []):
        if layer.get('name') == 'walls and obstacles':
            walls_layer = layer
            break

    if not walls_layer:
        raise ValueError("Layer 'walls and obstacles' not found in the map.")

    walls_data = walls_layer.get('data', [])

    # Step 4: Define the specific tiles we want to treat as walkable.
    # 'rogue_floor_tiles' are IDs that belong to floors despite being in this layer.
    rogue_floor_tiles = {27, 28, 29, 30, 31, 40, 41, 42, 43, 44, 46}
    
    # 'open_archways' are specific (x, y) coordinates we know are passable.
    open_archways = {(2, 16), (2, 17), (15, 11)}

    # Step 5: Build a 20x20 binary matrix. 
    # 0 represents a walkable tile, and 1 represents an impassable tile.
    binary_matrix = []
    for y in range(height):
        row = []
        for x in range(width):
            # Calculate the 1D index corresponding to the 2D (x, y) position
            idx = y * width + x
            
            # The tile ID is stored with flip flags in the highest 3 bits. 
            # We use a bitwise AND to get the true tile ID.
            tile_id = walls_data[idx] & 0x1FFFFFFF
            
            # Step 6: Apply our filtering rules to decide if the tile is walkable.
            # A tile is walkable if its ID is 0, if it's a rogue floor tile, 
            # or if its coordinate is an open archway.
            is_walkable = (tile_id == 0 or 
                           tile_id in rogue_floor_tiles or 
                           (x, y) in open_archways)
            
            if is_walkable:
                row.append(0)  # Walkable
            else:
                row.append(1)  # Impassable
                
        binary_matrix.append(row)

    return binary_matrix

def main():
    # Filepath to our map data
    filepath = "map.json"
    
    # Generate the binary matrix using our parsing function
    binary_matrix = parse_map_to_binary_matrix(filepath)
    
    # Step 7: Convert the binary matrix into a format that DStarLite expects.
    # DStarLite uses path costs, where float('inf') means impassable.
    # We'll map our binary 0 (walkable) to a cost of 1, and 1 (impassable) to infinity.
    dstar_matrix = []
    for row in binary_matrix:
        dstar_row = [1 if val == 0 else float('inf') for val in row]
        dstar_matrix.append(dstar_row)
        
    # Step 8: Initialize the pathfinding AI with our properly formatted cost matrix
    pathfinder = DStarLite(dstar_matrix)
    
    # Phase 1 (Get Key): Run D* Lite from the spawn [1, 18] to the Pot [16, 11].
    print("--- Phase 1: Get Key ---")
    start = [1, 18]
    pot = [16, 11]
    path_phase1 = pathfinder.find_path(start, pot)
    print(f"Path sequence to Key (Pot): {path_phase1}\n")
    
    # Phase 2 (Unlock Door): The planner uses the key to open Door 2.
    print("--- Phase 2: Unlock Door ---")
    # Update the matrix so the tiles for door_2 [9, 16] and [9, 17] are now walkable 0.
    binary_matrix[16][9] = 0
    binary_matrix[17][9] = 0
    # Also update the pathfinder's cost matrix (cost 1 for walkable)
    pathfinder.matrix[16][9] = 1
    pathfinder.matrix[17][9] = 1
    print("Door 2 at [9, 16] and [9, 17] unlocked.\n")
    
    # Phase 3 (Get Chest): Run D* Lite from the Pot [16, 11] to the Chest [11, 10].
    print("--- Phase 3: Get Chest ---")
    chest = [11, 10]
    path_phase3 = pathfinder.find_path(pot, chest)
    print(f"Path sequence to Chest: {path_phase3}\n")
    
    # Combine the routes for the final visualization
    full_path = path_phase1 + path_phase3
    
    # Convert the resulting path to a set of tuples for quick lookups later
    path_set = {tuple(p) for p in full_path}
    
    # Step 10: Print the final 20x20 ASCII map to the terminal.
    # Overlay the resulting path with '*', use '.' for walkable (0), and '#' for walls (1).
    print("--- ASCII Map with Path ---")
    for y in range(len(binary_matrix)):
        row_str = ""
        for x in range(len(binary_matrix[0])):
            # If the current coordinate is in our path set, draw a '*'
            if (x, y) in path_set:
                row_str += "* "
            else:
                # Otherwise, check our binary matrix to draw a floor or a wall
                val = binary_matrix[y][x]
                if val == 0:
                    row_str += ". "
                else:
                    row_str += "# "
        # Print the fully constructed row
        print(row_str)

if __name__ == "__main__":
    main()
