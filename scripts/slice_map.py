import os
import math
from PIL import Image

# CONFIGURATION
INPUT_IMAGE = "frontend/img/World_Map_8k.webp" 
OUTPUT_DIR = "frontend/img/tiles"
TILE_SIZE = 256

def slice_map():
    print(f"Loading {INPUT_IMAGE}...")
    try:
        im = Image.open(INPUT_IMAGE)
    except:
        print(f"Error: Could not find {INPUT_IMAGE}")
        return

    # Standard powers of 2 sizing:
    # Zoom 0: 256px  (1 tile)
    # Zoom 1: 512px  (2x2)
    # Zoom 2: 1024px (4x4)
    # Zoom 3: 2048px (8x8)
    # Zoom 4: 4096px (16x16)
    # Zoom 5: 8192px (32x32) - Native Resolution
    
    for zoom in range(0, 6): # 0 to 5
        print(f"Processing Zoom Level {zoom}...")
        
        # Calculate target dimension: 256 * 2^zoom
        target_size = TILE_SIZE * (2 ** zoom)
        
        # Resize image for this zoom level
        # LANCZOS for high quality downscaling
        resized_im = im.resize((target_size, target_size), Image.Resampling.LANCZOS)
        
        width, height = resized_im.size
        
        # Calculate how many columns/rows
        cols = math.ceil(width / TILE_SIZE)
        rows = math.ceil(height / TILE_SIZE)
        
        # Create zoom directory
        zoom_dir = os.path.join(OUTPUT_DIR, str(zoom))
        if not os.path.exists(zoom_dir):
            os.makedirs(zoom_dir)
            
        for x in range(cols):
            # Create X directory (Leaflet structure is /z/x/y.png)
            x_dir = os.path.join(zoom_dir, str(x))
            if not os.path.exists(x_dir):
                os.makedirs(x_dir)
                
            for y in range(rows):
                # Calculate pixel coordinates
                left = x * TILE_SIZE
                top = y * TILE_SIZE
                right = min(left + TILE_SIZE, width)
                bottom = min(top + TILE_SIZE, height)
                
                # Crop
                tile = resized_im.crop((left, top, right, bottom))
                
                # If tile is smaller than TILE_SIZE (edges), we must pad it to keep the grid consistent
                if tile.size != (TILE_SIZE, TILE_SIZE):
                    new_tile = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
                    new_tile.paste(tile, (0, 0))
                    tile = new_tile
                
                output_path = os.path.join(x_dir, f"{y}.png")
                tile.save(output_path, "PNG")

    print("✅ Done! Standard pyramid tiles generated in /frontend/img/tiles/")

if __name__ == "__main__":
    slice_map()