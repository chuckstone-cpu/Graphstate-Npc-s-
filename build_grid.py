import json

def build_grid(filepath="map.json"):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading map: {e}")
        return

    width = data.get('width', 20)
    height = data.get('height', 20)
    layers = data.get('layers', [])
    
    # Find "walls and obstacles" layer
    walls_layer = None
    for layer in layers:
        if layer.get('name') == 'walls and obstacles':
            walls_layer = layer
            break
            
    if not walls_layer:
        print("Error: 'walls and obstacles' layer not found.")
        return
        
    walls_data = walls_layer.get('data', [])
    
    # Build Walkable Matrix
    # 0 = walkable floor, 1 = obstacle/wall
    matrix = []
    
    # These tiles were accidentally placed in the walls layer but are actually floor tiles
    floor_tiles = {27, 28, 29, 30, 31, 46}
    
    for y in range(height):
        row = []
        for x in range(width):
            idx = y * width + x
            gid = walls_data[idx]
            # Strip Tiled bitwise flip/rotation flags
            tile_id = gid & 0x1FFFFFFF
            
            if tile_id != 0 and tile_id not in floor_tiles:
                row.append(1) # obstacle
            else:
                row.append(0) # walkable
        matrix.append(row)
        
    # Carve out the doorways (hardcoded open archways)
    matrix[16][2] = 0  # [2, 16]
    matrix[17][2] = 0  # [2, 17]
    matrix[11][15] = 0 # [15, 11]
        
    # Define Entity Coordinates (Grid [x, y])
    entities = {
        "npc_spawn": [1, 18],
        "potion": [3, 10],
        "pot_key": [16, 11],
        "chest_goal": [11, 10],
        "door_1": [2, 16],
        "door_2": [9, 16],
        "door_3": [16, 16]
    }
    
    # Map entities to ASCII characters for visualization
    entity_chars = {
        "npc_spawn": "N",
        "potion": "P",
        "pot_key": "K",
        "chest_goal": "C",
        "door_1": "D",
        "door_2": "D",
        "door_3": "D"
    }
    
    print("--- Visual 20x20 ASCII Map ---")
    
    # Print column headers
    col_header1 = "   " + " ".join([str(x // 10) if x >= 10 else " " for x in range(width)])
    col_header2 = "   " + " ".join([str(x % 10) for x in range(width)])
    print(col_header1)
    print(col_header2)
    
    for y in range(height):
        line_chars = []
        for x in range(width):
            char = None
            # Check if any entity is at this position
            for name, coords in entities.items():
                if coords == [x, y]:
                    char = entity_chars[name]
                    break
            
            if char:
                line_chars.append(char)
            elif matrix[y][x] == 1:
                line_chars.append("#")
            else:
                line_chars.append(".")
        print(f"{y:2d} " + " ".join(line_chars))
        
    print("\n--- Verification: Entity Spawn Positions ---")
    all_valid = True
    for name, (ex, ey) in entities.items():
        if 0 <= ex < width and 0 <= ey < height:
            is_walkable = (matrix[ey][ex] == 0)
            status_text = "OK" if is_walkable else "FAIL"
            print(f"{name:12}: [{ex:2d}, {ey:2d}] -> {status_text} (Walkable: {is_walkable})")
            if not is_walkable:
                all_valid = False
        else:
            print(f"{name:12}: [{ex:2d}, {ey:2d}] -> OUT OF BOUNDS")
            all_valid = False
            
    if all_valid:
        print("\nSUCCESS: All entities are on valid walkable (.) tiles.")
    else:
        print("\nWARNING: One or more entities are placed on an obstacle (#) or out of bounds.")

if __name__ == "__main__":
    build_grid()
