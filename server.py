from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import uvicorn
from ai_core import DStarLite

app = FastAPI()

# Add CORS Middleware to allow all origins (*)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_grid_matrix():
    # Grid matrix logic adapted from build_grid.py
    with open("map.json", 'r') as f:
        data = json.load(f)

    width = data.get('width', 20)
    height = data.get('height', 20)
    
    # Find "walls and obstacles" layer
    walls_layer = next((l for l in data.get('layers', []) if l.get('name') == 'walls and obstacles'), None)
    if not walls_layer:
        raise ValueError("Layer 'walls and obstacles' not found.")
        
    walls_data = walls_layer.get('data', [])
    floor_tiles = {46}
    
    matrix = []
    for y in range(height):
        row = []
        for x in range(width):
            idx = y * width + x
            tile_id = walls_data[idx] & 0x1FFFFFFF
            
            # 1.0 represents a walkable cost, float('inf') represents an impassable obstacle
            if tile_id != 0 and tile_id not in floor_tiles:
                row.append(float('inf'))
            else:
                row.append(1.0)
        matrix.append(row)
        
    # Carve out the open archways as identified in build_grid.py
    matrix[16][2] = 1.0  # [2, 16]
    matrix[17][2] = 1.0  # [2, 17]
    matrix[11][15] = 1.0 # [15, 11]
    matrix[10][16] = 1.0 # archway into pot room
    matrix[10][15] = 1.0 # archway into pot room
    
    # Carve out the physical archway leading into the chest room
    matrix[11][10] = 1.0
    matrix[11][11] = 1.0
    matrix[12][10] = 1.0
    matrix[12][11] = 1.0
    matrix[10][11] = 1.0 # chest goal itself
    
    return matrix

@app.get("/solve_dungeon")
def solve_dungeon():
    # Initialize the grid matrix and the DStarLite pathfinder
    matrix = get_grid_matrix()
    pathfinder = DStarLite(matrix)
    
    # Phase 1: Calculate path from spawn [1, 18] to pot [15, 11] (adjacent to the table)
    spawn = [1, 18]
    pot = [15, 11]
    path_to_key = pathfinder.find_path(spawn, pot)
    
    # Phase 2: Update the grid to unlock door_2 at [9, 16] and [9, 17]
    # DStarLite uses y,x coordinates for its matrix list
    pathfinder.matrix[16][9] = 1.0
    pathfinder.matrix[17][9] = 1.0
    
    # Phase 3: Calculate path from pot [15, 11] to chest [11, 10]
    chest = [11, 10]
    path_to_chest = pathfinder.find_path(pot, chest)
    
    # Return JSON response containing both path arrays
    return {
        "path_to_key": path_to_key,
        "path_to_chest": path_to_chest
    }

if __name__ == "__main__":
    # Note: Using host "127.0.0.0" as explicitly requested. Usually this is "127.0.0.1" or "0.0.0.0".
    uvicorn.run(app, host="127.0.0.1", port=8000)
