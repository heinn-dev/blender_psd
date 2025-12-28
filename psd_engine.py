

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
        
        # Check for mask (Channel -2)
        # psapi usually loads channels into the layer object
        # We assume has_mask if channel -2 exists in the underlying data
        if is_group:
            has_mask = layer.has_mask()
        else:
            has_mask = -2 in layer.get_image_data()

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
        
    return structure

    # except Exception as e:
        # print(f"BPSD Engine Error (Read Structure): {e}")
        # return []

def read_layer(psd_path, layer_path, fetch_mask=False):
    """
    Reads a specific layer's pixels.
    Returns: (flat_float_pixels, width, height) tuple for Blender.
    """
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        layer = layered_file.find_layer(layer_path)
        
        if not layer:
            print(f"Layer not found: {layer_path}")
            return None, 0, 0
        
        is_group = isinstance(layer, psapi.GroupLayer_8bit)

        # a group can have mask data, but no image data...
        # Get Data
        planar_data = layer.get_image_data()
        if not planar_data: return None, 0, 0

        h, w = planar_data[0].shape
        
        # Mask is channel -2
        mask = None
        if -2 in planar_data:
            mask_arr = planar_data[-2]
            mask_arr = np.flipud(mask_arr)
            
            # ough.....
            # Expand mask to RGBA for visualization (White mask, opaque alpha)
            # or just R=G=B=Mask
            ones = np.full_like(mask_arr, 255)
            img_stack = np.stack([mask_arr, mask_arr, mask_arr, ones], axis=-1)
            
            mask = (img_stack.astype(np.float32) / 255.0).flatten()
            
            
        r = planar_data[0]
        g = planar_data[1]
        b = planar_data[2]
        
        if -1 in planar_data:
            a = planar_data[-1]
        else:
            a = np.full((h, w), 255, dtype=r.dtype)

        img_stack = np.stack([r, g, b, a], axis=-1)
        img_stack = np.flipud(img_stack)
        
        flat_pixels = (img_stack.astype(np.float32) / 255.0).flatten()
        return flat_pixels, mask, w, h

    except Exception as e:
        print(f"BPSD Engine Error (Read Layer): {e}")
        return None, 0, 0

def write_layer(psd_path, layer_path, blender_pixels, width, height, is_mask=False):
    """
    Writes Blender pixels back to the PSD.
    """
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        layer = layered_file.find_layer(layer_path)

        if not layer: return False
        if width != layer.width or height != layer.height:
            print("Dimension mismatch")
            return False

        # Reshape & Flip
        pixels = np.array(blender_pixels).reshape((height, width, 4))
        pixels = np.flipud(pixels)
        pixels = (pixels * 255).astype(np.uint8)

        if is_mask:
            # Use Red channel for mask
            mask_data = pixels[:, :, 0]
            layer[-2] = mask_data
        else:
            new_data = {
                0: pixels[:, :, 0],
                1: pixels[:, :, 1],
                2: pixels[:, :, 2],
                -1: pixels[:, :, 3]
            }
            layer.set_image_data(new_data)

        layered_file.write(psd_path)
        return True

    except Exception as e:
        print(f"BPSD Engine Error (Write Layer): {e}")
        return False