import json
import sys

def parse_map(filepath):
    print(f"Inspecting '{filepath}'...\n")
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filepath}'.")
        return

    # Print map dimensions
    print("--- Map Dimensions ---")
    width = data.get('width', 0)
    height = data.get('height', 0)
    tilewidth = data.get('tilewidth', 0)
    tileheight = data.get('tileheight', 0)
    print(f"Map Size (tiles): {width}x{height}")
    print(f"Tile Size (px):   {tilewidth}x{tileheight}")
    print()

    layers = data.get('layers', [])
    
    # List all layer names
    print("--- Detected Layers ---")
    if not layers:
        print("No layers found.")
    for i, layer in enumerate(layers):
        layer_type = layer.get('type', 'unknown')
        name = layer.get('name', f'unnamed_layer_{i}')
        print(f"- {name} (Type: {layer_type})")
    print()

    # Process tile layers
    for i, layer in enumerate(layers):
        if layer.get('type') == 'tilelayer':
            name = layer.get('name', f'unnamed_layer_{i}')
            print(f"--- Tile Layer: {name} ---")
            
            # Extract 1D data and dimensions
            data_array = layer.get('data', [])
            layer_width = layer.get('width', width)
            layer_height = layer.get('height', height)
            
            if not data_array:
                print("No tile data found in this layer.")
                print()
                continue
                
            # Convert 1D data array to 2D grid matrix
            grid = []
            for y in range(layer_height):
                start_idx = y * layer_width
                end_idx = start_idx + layer_width
                row = data_array[start_idx:end_idx]
                grid.append(row)
                
            # Print unique tile IDs
            unique_tiles = set(data_array)
            print(f"Unique Tile IDs: {sorted(list(unique_tiles))}")
            
            # Print a small 5x5 slice of the grid from the top-left corner
            print("Top-Left 5x5 Slice:")
            slice_height = min(5, layer_height)
            slice_width = min(5, layer_width)
            
            for y in range(slice_height):
                row_slice = grid[y][:slice_width]
                formatted_row = [f"{tile_id:3d}" for tile_id in row_slice]
                print("  [" + ", ".join(formatted_row) + "]")
            print()

if __name__ == "__main__":
    # Use "map.json" by default, or an argument if provided
    filepath = sys.argv[1] if len(sys.argv) > 1 else "map.json"
    parse_map(filepath)
