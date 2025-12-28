

import bpy
import os
import numpy as np

import photoshopapi as psapi

# --- FUNCTIONAL ENGINE ---

def read_file(path):
    """
    Opens the PSD and returns a recursive dictionary tree of the structure.
    """

    layered_file = psapi.LayeredFile.read(path)
    
    def parse_layer_structure(layer, current_path=""):
        # Construct path (e.g., "Group/Layer")
        layer_name = layer.name
        full_path = f"{current_path}/{layer_name}" if current_path else layer_name
        
        is_group = isinstance(layer, psapi.GroupLayer_8bit)
        
        has_mask = layer.has_mask()

        node = {
            "name": layer_name,
            "path": full_path,
            "type": "GROUP" if is_group else "LAYER",
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

    # except Exception as e:
        # print(f"BPSD Engine Error (Read Structure): {e}")
        # return []

def read_layer(psd_path, layer_path, target_w , target_h , fetch_mask=False):
    """
    Reads a specific layer's pixels.
    If fetching a mask, uses 'mask_position' (Center) to composite it 
    correctly onto a white canvas matching the color layer's dimensions.
    """
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        layer = layered_file.find_layer(layer_path)
        
        if not layer:
            return None, 0, 0

        # probably fine?
        layer_left = 0
        layer_top = 0

        # --- MASK PATH ---
        if fetch_mask:
            canvas = np.full((target_h, target_w), 255, dtype=np.uint8)
            mask_arr = layer.mask
            mh, mw = mask_arr.shape
            
            center_x = layer.mask_position.x
            center_y = layer.mask_position.y
            
            mask_left = int(center_x - (mw / 2))
            mask_top = int(center_y - (mh / 2))
            
            rel_x = mask_left - layer_left
            rel_y = mask_top - layer_top

            # Destination (Canvas) bounds
            dst_x1 = max(0, rel_x)
            dst_y1 = max(0, rel_y)
            dst_x2 = min(target_w, rel_x + mw)
            dst_y2 = min(target_h, rel_y + mh)

            src_x1 = dst_x1 - rel_x
            src_y1 = dst_y1 - rel_y
            src_x2 = src_x1 + (dst_x2 - dst_x1)
            src_y2 = src_y1 + (dst_y2 - dst_y1)

            # paste in the overlap
            if dst_x2 > dst_x1 and dst_y2 > dst_y1:
                canvas[dst_y1:dst_y2, dst_x1:dst_x2] = mask_arr[src_y1:src_y2, src_x1:src_x2]
            else:
                print(f"Mask exists but is outside layer bounds. (Offsets: {rel_x}, {rel_y})")

            canvas = np.flipud(canvas)

            ones = np.full_like(canvas, 255)
            img_stack = np.stack([canvas, canvas, canvas, ones], axis=-1)
            
            flat_pixels = (img_stack.astype(np.float32) / 255.0).flatten()
            return flat_pixels, target_w, target_h

        else:
            # I think blank layers have no data by default?
            planar_data = layer.get_image_data()
            
            r = planar_data[0] if 0 in planar_data else np.full((target_h, target_w), 255, dtype=np.uint8)
            g = planar_data[1] if 1 in planar_data else np.zeros_like(r)
            b = planar_data[2] if 2 in planar_data else np.zeros_like(r)
            
            a = planar_data[-1] if -1 in planar_data else np.full((target_h, target_w), 0, dtype=r.dtype)

            img_stack = np.stack([r, g, b, a], axis=-1)
            img_stack = np.flipud(img_stack)
            
            flat_pixels = (img_stack.astype(np.float32) / 255.0).flatten()
            return flat_pixels, target_w, target_h

    except Exception as e:
        print(f"BPSD Engine Error: {e}")
        return None, 0, 0

def write_layer(psd_path, layer_path, blender_pixels, width, height, is_mask=False):
    layered_file = psapi.LayeredFile.read(psd_path)
    write_to_layered_file(layered_file, layer_path, blender_pixels, width, height, is_mask)
    layered_file.write(psd_path)
    return True

def write_to_layered_file(layered_file, layer_path, blender_pixels, width, height, is_mask):
    layer = layered_file.find_layer(layer_path)

    if not layer: return False
    
    # this does happen for layers, they have different size from colors
    # compare this with psd_width and psd_height instead, but we'll think about this later
    # if width != layer.width or height != layer.height:
    #     print("Dimension mismatch")
    #     return False

    pixels = np.array(blender_pixels).reshape((height, width, 4))
    pixels = np.flipud(pixels)
    pixels = (pixels * 255).astype(np.uint8)

    if is_mask:
        mask_data = pixels[:, :, 0]
        layer.mask = mask_data
        layer.mask_position = psapi.geometry.Point2D(width / 2, height / 2)
    else:
        new_data = {
            0: pixels[:, :, 0],
            1: pixels[:, :, 1],
            2: pixels[:, :, 2],
            -1: pixels[:, :, 3]
        }
        layer.set_image_data(new_data)

    return True

def write_all_layers(psd_path, updates):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        
        layers_updated_count = 0

        for data in updates:
            layer_path = data['layer_path']
            width = data['width']
            height = data['height']
            is_mask = data['is_mask']
            pixels = np.array(data['pixels'])
            
            if write_to_layered_file(layered_file, layer_path, pixels, width, height, is_mask):
                layers_updated_count += 1

        if layers_updated_count > 0:
            layered_file.write(psd_path)
            return True
        else:
            print("No valid layers were found to update.")
            return False

    except Exception as e:
        print(f"BPSD Batch Save Error: {e}")
        return False