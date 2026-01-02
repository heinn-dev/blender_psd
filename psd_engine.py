import bpy
import os
import numpy as np

import photoshopapi as psapi

def read_file(path):

    try:
        layered_file = psapi.LayeredFile.read(path)

        def parse_layer_structure(layer, current_index_path="", child_index=0):
            layer_name = layer.name
            # Use index-based path for unique identification
            index_path = f"{current_index_path}/{child_index}" if current_index_path else str(child_index)

            is_group = False

            match layer:
                case psapi.GroupLayer_8bit():
                    layer_type = "GROUP"
                    is_group = True

                case psapi.AdjustmentLayer_8bit():
                    layer_type = "ADJUSTMENT"

                case psapi.SmartObjectLayer_8bit():
                    layer_type = "SMART"

                case psapi.Layer_8bit():
                    layer_type = "LAYER"

                case _:
                    layer_type = "UNKNOWN"

            has_mask = layer.has_mask()

            # this happened when adjustment layers weren't a thing, safe to assume it's broke if null name?
            if layer_name == "":
                layer_type = "UNKNOWN"
                layer_name = "---"

            node = {
                "name": layer_name,
                "path": index_path,  # Now stores index path like "0/2/1"
                "layer_type": layer_type,
                "has_mask": has_mask,
                "is_clipping_mask": layer.clipping_mask,
                "is_visible": layer.is_visible,
                "children": []
            }

            # print(f"loaded {layer_name}, it is a {layer_type} layer, has mask : {has_mask}")

            if is_group:
                for i, child in enumerate(layer.layers):
                    node["children"].append(parse_layer_structure(child, index_path, i))

            return node

        structure = []

        for i, layer in enumerate(layered_file.layers):
            structure.append(parse_layer_structure(layer, "", i))

        return structure, layered_file.width, layered_file.height

    except Exception as e:
        print(f"BPSD Engine Error (Read Structure): {e}")
        return []


def get_layer_by_index_path(layered_file, index_path):
    """Navigate to a layer using an index-based path like '0/2/1'."""
    indices = [int(i) for i in index_path.split("/")]
    current_layers = layered_file.layers

    layer = None
    for idx in indices:
        if idx < len(current_layers):
            layer = current_layers[idx]
            # If this is a group, descend into its children for the next index
            if hasattr(layer, 'layers'):
                current_layers = layer.layers
        else:
            return None

    return layer

# --- HELPER: Internal Read Logic (Refactored) ---
def _read_layer_internal(layered_file, layer_path, target_w, target_h, fetch_mask):
    layer = get_layer_by_index_path(layered_file, layer_path)
    if not layer: return None

    # --- MASK PATH ---
    if fetch_mask:
        canvas = np.full((target_h, target_w), 255, dtype=np.uint8)
        
        try:
            mask_arr = layer.mask
        except:
            mask_arr = None

        if mask_arr is not None and mask_arr.size > 0:
            mh, mw = mask_arr.shape
            center_x = layer.mask_position.x
            center_y = layer.mask_position.y
            mask_left = int(center_x - (mw / 2))
            mask_top = int(center_y - (mh / 2))
            
            paste_to_canvas(canvas, mask_arr, target_w, target_h, mask_left, mask_top)
        
        canvas = np.flipud(canvas)
        ones = np.full_like(canvas, 255)
        img_stack = np.stack([canvas, canvas, canvas, ones], axis=-1)
        return (img_stack.astype(np.float32) / 255.0).flatten()

    # --- COLOR PATH ---
    else:
        planar_data = layer.get_image_data()
        if not planar_data:
            return np.zeros(target_w * target_h * 4, dtype=np.float32)

        first_key = next(iter(planar_data))
        dtype = planar_data[first_key].dtype

        c_r = np.zeros((target_h, target_w), dtype=dtype)
        c_g = np.zeros((target_h, target_w), dtype=dtype)
        c_b = np.zeros((target_h, target_w), dtype=dtype)
        c_a = np.zeros((target_h, target_w), dtype=dtype)

        l_w = layer.width
        l_h = layer.height
        layer_left = int(layer.center_x - (l_w / 2))
        layer_top = int(layer.center_y - (l_h / 2))

        if 0 in planar_data: paste_to_canvas(c_r, planar_data[0], target_w, target_h, layer_left, layer_top)
        if 1 in planar_data: paste_to_canvas(c_g, planar_data[1], target_w, target_h, layer_left, layer_top)
        if 2 in planar_data: paste_to_canvas(c_b, planar_data[2], target_w, target_h, layer_left, layer_top)
        
        if -1 in planar_data:
            paste_to_canvas(c_a, planar_data[-1], target_w, target_h, layer_left, layer_top)
        else:
            opaque_block = np.full((l_h, l_w), 0, dtype=dtype) #transparent by default
            paste_to_canvas(c_a, opaque_block, target_w, target_h, layer_left, layer_top)

        img_stack = np.stack([c_r, c_g, c_b, c_a], axis=-1)
        img_stack = np.flipud(img_stack)
        
        return (img_stack.astype(np.float32) / 255.0).flatten()

# --- EXISTING FUNCTIONS (Simplified wrappers) ---

def read_layer(psd_path, layer_path, target_w, target_h, fetch_mask=False):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        flat_data = _read_layer_internal(layered_file, layer_path, target_w, target_h, fetch_mask)
        if flat_data is None: return None, 0, 0
        return flat_data, target_w, target_h
    except Exception as e:
        print(f"BPSD Read Error: {e}")
        return None, 0, 0

# --- NEW BATCH FUNCTION ---

def read_all_layers(psd_path, requests):
    results = {}
    try:
        layered_file = psapi.LayeredFile.read(psd_path)

        for req in requests:
            path = req['layer_path']
            layer_index = req.get('layer_index')
            w = req['width']
            h = req['height']
            mask = req['is_mask']

            # if req['layer_type'] in ['SPECIAL','UNKNOWN']: continue

            pixels = _read_layer_internal(layered_file, path, w, h, mask)

            if pixels is not None:
                # Key the result by layer_index AND mask type so we can map it back easily
                results[(layer_index, mask)] = pixels

        return results
    except Exception as e:
        print(f"BPSD Batch Read Error: {e}")
        return {}

def paste_to_canvas(canvas, source_arr, canvas_w, canvas_h, offset_x, offset_y):
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
    layer_h, layer_w = target_layer_arr.shape
    canvas_h, canvas_w = canvas_arr.shape
      
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

def write_all_layers(psd_path, updates, canvas_w, canvas_h):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        count = 0
        for data in updates:
            if write_to_layered_file(layered_file, data['layer_path'], data['pixels'], 
                                   canvas_w, canvas_h, data['is_mask']):
                count += 1

        if count > 0:
            layered_file.write(psd_path)
            return True
        return False

    except Exception as e:
        print(f"BPSD Batch Save Error: {e}")
        return False

def write_to_layered_file(layered_file, layer_path, blender_pixels, canvas_w, canvas_h, is_mask):
    layer = get_layer_by_index_path(layered_file, layer_path)
    if not layer:
        print(f"Can't save {layer_path} ?")
        return False

    print(f"Saving {layer_path}, as mask : {is_mask}")
    # 1. Parse Blender Data
    pixels = np.array(blender_pixels).reshape((canvas_h, canvas_w, 4))
    pixels = np.flipud(pixels)
    pixels = (pixels * 255).astype(np.uint8)

    # --- MASK PATH ---
    if is_mask:
        try:
            # Photoshop auto-crops masks, making them too small to "Stamp" into 
            # if we paint new areas in Blender.
            # We simply replace the mask with the full Blender Canvas to ensure
            # all strokes are captured.
            
            mask_data = pixels[:, :, 0] # Red Channel as Mask
            
            # This automatically resizes the mask buffer to match our data
            layer.mask = mask_data
            
            # Re-center the mask to the Canvas Center
            layer.mask_position = psapi.geometry.Point2D(canvas_w / 2, canvas_h / 2)
            
            return True
            
        except Exception as e:
            print(f"BPSD Mask Write Error: {e}")
            return False

    # --- COLOR PATH ---
    else:
        # We always overwrite the layer with the full canvas data.
        # This ensures that painting outside the original layer bounds works as expected.

        new_data = {
            0: pixels[:, :, 0],
            1: pixels[:, :, 1],
            2: pixels[:, :, 2],
            -1: pixels[:, :, 3]
        }

        # Check if the layer originally had data to preserve any non-standard behavior?
        # Actually, for a sync workflow, we want Blender to be the source of truth for the pixels.

        try:
            layer.set_image_data(new_data, width=canvas_w, height=canvas_h)
            layer.center_x = canvas_w / 2
            layer.center_y = canvas_h / 2
        except Exception as e:
            print(f"BPSD Write Color Error: {e}")
            return False

        return True

def write_layer(psd_path, layer_path, blender_pixels, width, height, is_mask=False):
    layered_file = psapi.LayeredFile.read(psd_path)
    write_to_layered_file(layered_file, layer_path, blender_pixels, width, height, is_mask)
    print("writing...")
    layered_file.write(psd_path)
    print("done")
    
    return True