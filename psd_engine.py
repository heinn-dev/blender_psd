import bpy
import os
import numpy as np

import photoshopapi as psapi


def read_file(path):
    
    try:
        layered_file = psapi.LayeredFile.read(path)
        
        def parse_layer_structure(layer, current_path=""):
            layer_name = layer.name
            full_path = f"{current_path}/{layer_name}" if current_path else layer_name
            
            is_group = isinstance(layer, psapi.GroupLayer_8bit)
            
            match layer:
                case psapi.GroupLayer_8bit():
                    layer_type = "GROUP"
                    is_group = True

                case psapi.SmartObjectLayer_8bit():
                    layer_type = "SMART"
                    is_group = False

                case _:
                    layer_type = "LAYER"
                    is_group = False
            
            has_mask = layer.has_mask()

            node = {
                "name": layer_name,
                "path": full_path,
                "type": layer_type,
                "has_mask": has_mask,
                "children": []
            }
            
            if is_group:
                for child in layer.layers:
                    node["children"].append(parse_layer_structure(child, full_path))
                    
            return node

        structure = []
        
        for layer in layered_file.layers:
            structure.append(parse_layer_structure(layer))
            
        return structure, layered_file.width, layered_file.height

    except Exception as e:
        print(f"BPSD Engine Error (Read Structure): {e}")
        return []

def read_layer(psd_path, layer_path, target_w, target_h, fetch_mask=False):
    
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        layer = layered_file.find_layer(layer_path)
        
        if not layer: return None, 0, 0

        # --- MASK READING ---
        if fetch_mask:
            # 1. Create Blank White Canvas (Opaque)
            canvas = np.full((target_h, target_w), 255, dtype=np.uint8)
            
            # 2. Check if Mask Exists
            try:
                # Some groups report has_mask=True but might fail getting data if empty
                mask_arr = layer.mask
            except:
                mask_arr = None

            if mask_arr is not None and mask_arr.size > 0:
                mh, mw = mask_arr.shape
                
                # Calculate Top-Left from Center
                center_x = layer.mask_position.x
                center_y = layer.mask_position.y
                mask_left = int(center_x - (mw / 2))
                mask_top = int(center_y - (mh / 2))
                
                # Paste
                paste_to_canvas(canvas, mask_arr, target_w, target_h, mask_left, mask_top)
            
            # 3. Finalize
            canvas = np.flipud(canvas)
            ones = np.full_like(canvas, 255)
            img_stack = np.stack([canvas, canvas, canvas, ones], axis=-1)
            return (img_stack.astype(np.float32) / 255.0).flatten(), target_w, target_h

        # --- COLOR READING ---
        else:
            planar_data = layer.get_image_data()
            if not planar_data:
                # Completely Empty Layer? Return Transparent
                return np.zeros(target_w * target_h * 4, dtype=np.float32), target_w, target_h

            # 1. Determine safe dtype
            first_key = next(iter(planar_data))
            dtype = planar_data[first_key].dtype

            # 2. Initialize Full Canvas Channels
            # R,G,B default to 0 (Black). Alpha defaults to 0 (Transparent).
            c_r = np.zeros((target_h, target_w), dtype=dtype)
            c_g = np.zeros((target_h, target_w), dtype=dtype)
            c_b = np.zeros((target_h, target_w), dtype=dtype)
            c_a = np.zeros((target_h, target_w), dtype=dtype)

            # 3. Calculate Offsets
            # Layer coordinates are also center-based or top-left based depending on API
            # Assuming consistency with Mask, we use center logic if available, else standard left/top
            l_w = layer.width
            l_h = layer.height
            
            # Using Center provides better sub-pixel conversion if API uses floats
            layer_left = int(layer.center_x - (l_w / 2))
            layer_top = int(layer.center_y - (l_h / 2))

            # 4. Paste Channels
            if 0 in planar_data: paste_to_canvas(c_r, planar_data[0], target_w, target_h, layer_left, layer_top)
            if 1 in planar_data: paste_to_canvas(c_g, planar_data[1], target_w, target_h, layer_left, layer_top)
            if 2 in planar_data: paste_to_canvas(c_b, planar_data[2], target_w, target_h, layer_left, layer_top)
            
            # Alpha Handling
            if -1 in planar_data:
                paste_to_canvas(c_a, planar_data[-1], target_w, target_h, layer_left, layer_top)
            else:
                # If layer has RGB but NO Alpha channel, it implies opacity...
                # BUT only within the layer bounds. 
                # So we create a temporary opaque block and paste THAT into the alpha canvas.
                opaque_block = np.full((l_h, l_w), 255, dtype=dtype)
                paste_to_canvas(c_a, opaque_block, target_w, target_h, layer_left, layer_top)

            # 5. Stack & Flip
            img_stack = np.stack([c_r, c_g, c_b, c_a], axis=-1)
            img_stack = np.flipud(img_stack)
            
            return (img_stack.astype(np.float32) / 255.0).flatten(), target_w, target_h

    except Exception as e:
        print(f"BPSD Engine Error: {e}")
        import traceback
        traceback.print_exc()
        return None, 0, 0

def paste_to_canvas(canvas, source_arr, canvas_w, canvas_h, offset_x, offset_y):
    """
    Reads FROM source_arr (Layer) and writes TO canvas (Blender).
    Clips source_arr to fit within the canvas window.
    """
    src_h, src_w = source_arr.shape
    
    # Destination (Canvas) bounds
    dst_x1 = max(0, offset_x)
    dst_y1 = max(0, offset_y)
    dst_x2 = min(canvas_w, offset_x + src_w)
    dst_y2 = min(canvas_h, offset_y + src_h)

    # Source (Layer) bounds
    src_x1 = dst_x1 - offset_x
    src_y1 = dst_y1 - offset_y
    src_x2 = src_x1 + (dst_x2 - dst_x1)
    src_y2 = src_y1 + (dst_y2 - dst_y1)

    if dst_x2 > dst_x1 and dst_y2 > dst_y1:
        canvas[dst_y1:dst_y2, dst_x1:dst_x2] = source_arr[src_y1:src_y2, src_x1:src_x2]

# --- HELPER 2: Stamp/Update (For Writing) ---
def stamp_from_canvas(target_layer_arr, canvas_arr, offset_x, offset_y):
    """
    Reads FROM canvas_arr (Blender) and writes TO target_layer_arr (Layer).
    Only updates the pixels of target_layer_arr that overlap with the canvas.
    """
    layer_h, layer_w = target_layer_arr.shape
    canvas_h, canvas_w = canvas_arr.shape
    
    # We are calculating the Intersection of the Canvas relative to the Layer.
    
    # Coordinates of the "Update Window" in Layer Space
    # offset_x is "Where does the Layer start relative to Canvas (0,0)?"
    # Therefore, the Canvas starts at -offset_x relative to the Layer.
    
    # Let's verify the coordinate system:
    # Canvas (0,0) is the global origin.
    # Layer is at (layer_left, layer_top).
    # We want to copy pixels FROM Canvas TO Layer.
    
    # Destination (Layer) Window
    # The canvas covers the region (0, 0) to (canvas_w, canvas_h) in global space.
    # Converted to Layer Space: (-offset_x, -offset_y)
    
    # Intersection of "Layer Rect (0,0,w,h)" and "Canvas Rect (-x, -y, cw, ch)"
    
    # Layer (Dest) Bounds
    dst_x1 = max(0, -offset_x)
    dst_y1 = max(0, -offset_y)
    dst_x2 = min(layer_w, canvas_w - offset_x)
    dst_y2 = min(layer_h, canvas_h - offset_y)
    
    # Canvas (Source) Bounds
    # Map back to canvas coordinates
    src_x1 = dst_x1 + offset_x
    src_y1 = dst_y1 + offset_y
    src_x2 = src_x1 + (dst_x2 - dst_x1)
    src_y2 = src_y1 + (dst_y2 - dst_y1)

    # Perform the Stamp
    if dst_x2 > dst_x1 and dst_y2 > dst_y1:
        target_layer_arr[dst_y1:dst_y2, dst_x1:dst_x2] = canvas_arr[src_y1:src_y2, src_x1:src_x2]

# --- ENGINE ---

# (read_file and read_layer remain unchanged from previous correct version)

def write_all_layers(psd_path, updates):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        count = 0
        for data in updates:
            if write_to_layered_file(layered_file, data['layer_path'], data['pixels'], 
                                   data['width'], data['height'], data['is_mask']):
                count += 1

        if count > 0:
            layered_file.write(psd_path)
            return True
        return False

    except Exception as e:
        print(f"BPSD Batch Save Error: {e}")
        return False

def write_to_layered_file(layered_file, layer_path, blender_pixels, canvas_w, canvas_h, is_mask):
    """
    Updates the layer by "stamping" the Blender Canvas onto the existing Layer data.
    Preserves layer size and position.
    """
    layer = layered_file.find_layer(layer_path)
    if not layer: return False

    # 1. Parse Blender Data (The Canvas)
    pixels = np.array(blender_pixels).reshape((canvas_h, canvas_w, 4))
    pixels = np.flipud(pixels) # Flip to match Top-Left origin
    pixels = (pixels * 255).astype(np.uint8)

    # 2. Get Existing Layer Geometry
    # We need to know where the layer is to calculate the overlap
    if is_mask:
        try:
            # Mask Coordinates (Center)
            cx, cy = layer.mask_position.x, layer.mask_position.y
            
            # We need the existing mask data to know its size
            # If the layer has no mask, we can't "update" it in place easily 
            # without assuming we create a new one matching canvas.
            if not layer.has_mask():
                # Fallback: Create new mask matching canvas exactly
                layer.mask = pixels[:, :, 0]
                layer.mask_position = psapi.geometry.Point2D(canvas_w/2, canvas_h/2)
                return True
                
            current_arr = layer.mask
            h, w = current_arr.shape
            
            # Calculate Top-Left
            layer_left = int(cx - (w / 2))
            layer_top = int(cy - (h / 2))
            
            # Stamp!
            stamp_from_canvas(current_arr, pixels[:, :, 0], layer_left, layer_top)
            
            # Set Back
            layer.mask = current_arr
            # Do NOT update mask_position, keep original
            
        except Exception as e:
            print(f"BPSD Mask Write Error: {e}")
            return False

    else:
        # Color Layer Logic
        planar_data = layer.get_image_data()
        if not planar_data:
            # If layer is empty, we initialize it to Canvas Size
            new_data = {
                0: pixels[:, :, 0], 1: pixels[:, :, 1], 2: pixels[:, :, 2], -1: pixels[:, :, 3]
            }
            layer.set_image_data(new_data, width=canvas_w, height=canvas_h)
            layer.center_x = canvas_w / 2
            layer.center_y = canvas_h / 2
            return True

        # Existing Geometry
        l_w = layer.width
        l_h = layer.height
        layer_left = int(layer.center_x - (l_w / 2))
        layer_top = int(layer.center_y - (l_h / 2))
        
        # 3. Stamp Channels
        # We iterate through channels. If Blender has data for it, we stamp.
        # Note: Blender always provides RGBA.
        
        # Helper wrapper to reduce copy-paste
        def do_stamp(channel_idx, blender_slice):
            if channel_idx in planar_data:
                target_arr = planar_data[channel_idx]
                stamp_from_canvas(target_arr, blender_slice, layer_left, layer_top)
                planar_data[channel_idx] = target_arr
            # else: Optional: Add channel if missing? 
            # Usually better to respect original channel structure.

        do_stamp(0, pixels[:, :, 0]) # R
        do_stamp(1, pixels[:, :, 1]) # G
        do_stamp(2, pixels[:, :, 2]) # B
        do_stamp(-1, pixels[:, :, 3]) # A
        
        # 4. Write Back
        # We pass the modified planar_data back.
        # Important: We do NOT pass width/height arguments, forcing it to keep existing dims.
        layer.set_image_data(planar_data) 
        
    return True