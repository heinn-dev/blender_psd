import os
import numpy as np
import photoshopapi as psapi

def blender_to_psapi_data(blender_image):
    """Converts Blender float pixels to 8-bit planar data for PhotoshopAPI."""
    width, height = blender_image.size
    # Get pixels and convert 0.0-1.0 float to 0-255 uint8
    pixels = np.array(blender_image.pixels)
    pixels = (pixels * 255).astype(np.uint8)
    
    # Reshape to (Height, Width, RGBA)
    pixels = pixels.reshape((height, width, 4))
    
    # Flip vertically (Blender is bottom-up, PSD is top-down)
    pixels = np.flipud(pixels)
    
    # PhotoshopAPI expects planar data: {0: R_array, 1: G_array, 2: B_array, 3: A_array}
    return {
        0: pixels[:, :, 0].copy(), # Red
        1: pixels[:, :, 1].copy(), # Green
        2: pixels[:, :, 2].copy(), # Blue
        -1: pixels[:, :, 3].copy()  # Alpha
    }


def read_file(path):

    try:
        # Open file
        layered_file = psapi.LayeredFile.read(path)
        
        # Helper for recursion
        def parse_layer_structure(layer, current_path=""):
            # Construct path (e.g., "Group/Layer")
            # Note: psapi uses names to find layers, so paths are crucial
            layer_name = layer.name
            full_path = f"{current_path}/{layer_name}" if current_path else layer_name
            
            node = {
                "name": layer_name,
                "path": full_path,
                "type": "GROUP" if isinstance(layer, psapi.GroupLayer_8bit) else "LAYER",
                "has_mask": False,
                "children": []
            }
            
            # Recurse if it's a group
            if node["type"] == "GROUP":
                # Iterate over children (psapi layers are iterable)
                for child in layer:
                    node["children"].append(parse_layer_structure(child, full_path))
                    
            return node

        # Build tree from root layers
        # LayeredFile acts as the root container
        structure = []
        for layer in layered_file:
            structure.append(parse_layer_structure(layer))
            
        return structure

    except Exception as e:
        print(f"BPSD Engine Error (Read Structure): {e}")
        return []

@staticmethod
def read_layer(psd_path, layer_path,fetch_mask=False):
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

        # 1. Get Planar Data {0: R, 1: G, 2: B, 3: A}
        # Arrays are uint8 or uint16 depending on file depth
        planar_data = layer.get_image_data()
        
        # 2. Get Dimensions from one of the channels
        # Note: psapi returns arrays as (Height, Width)
        h, w = planar_data[0].shape
        
        if fetch_mask:
                # Channel -2 is the User Mask
                if -2 in planar_data:
                    mask_arr = planar_data[-2]
                else:
                    print(f"No mask found on {layer_path}")
                    return None, 0, 0
                
                # Flip and Normalize
                mask_arr = np.flipud(mask_arr)
                flat_pixels = (mask_arr.astype(np.float32) / 255.0).flatten()
                
                # Masks are Grayscale, but Blender images are usually RGBA or float buffers.
                # To see it in the image editor, we typically expand it to RGBA 
                # where R=G=B=Mask and A=1.0 (Opaque)
                # OR return it as single channel if you map it to a specific node.
                # Here we make it a visible BW image:
                zeros = np.zeros_like(mask_arr)
                ones = np.full_like(mask_arr, 255)
                
                # Stack as BW Image: R=Mask, G=Mask, B=Mask, A=255
                img_stack = np.stack([mask_arr, mask_arr, mask_arr, ones], axis=-1)
                flat_pixels = (img_stack.astype(np.float32) / 255.0).flatten()
                
                return flat_pixels, w, h

        # 3. Stack into Interleaved (H, W, 4)
        # Handle cases where Alpha (channel 3) might be missing
        r = planar_data[0]
        g = planar_data[1]
        b = planar_data[2]
        
        if 3 in planar_data:
            a = planar_data[-1]
        else:
            # Create fully opaque alpha if missing
            a = np.full((h, w), 255, dtype=r.dtype)

        # Stack and Flip (Blender is Bottom-Up, PSD is Top-Down)
        # Result is (Height, Width, 4)
        img_stack = np.stack([r, g, b, a], axis=-1)
        img_stack = np.flipud(img_stack)
        
        # 4. Normalize to 0.0-1.0 Floats and Flatten
        # Blender expects a single long list of floats
        flat_pixels = (img_stack.astype(np.float32) / 255.0).flatten()
        
        return flat_pixels, w, h

    except Exception as e:
        print(f"BPSD Engine Error (Read Layer): {e}")
        return None, 0, 0

def write_layer(psd_path, layer_path, blender_pixels, width, height, is_mask=False):
    """
    Writes Blender pixels back to the PSD.
    blender_pixels: Flat list or numpy array of floats (0.0-1.0)
    """

    try:
        # 1. Open File
        layered_file = psapi.LayeredFile.read(psd_path)
        layer = layered_file.find_layer(layer_path)

        if not layer:
            print(f"Cannot write. Layer missing: {layer_path}")
            return False

        # Verify dimensions match (Crucial!)
        if width != layer.width or height != layer.height:
            print(f"Dimension Mismatch! PSD: {layer.width}x{layer.height}, Blender: {width}x{height}")
            return False

        # 2. Process Pixels (Float List -> Planar Uint8)
        # Reshape to (H, W, 4)
        pixels = np.array(blender_pixels).reshape((height, width, 4))
        
        # Flip Vertically (Back to Top-Down)
        pixels = np.flipud(pixels)
        
        # Scale to 0-255 uint8
        pixels = (pixels * 255).astype(np.uint8)
        if is_mask:
            # For mask, we only need one channel (Red) from Blender to save as the mask
            mask_data = pixels[:, :, 0] # Take Red channel as the mask value
            
            # Write to Channel -2
            layer[-2] = mask_data
        # Split into channels {0: R, 1: G, ...}
            new_data = {
                0: pixels[:, :, 0],
                1: pixels[:, :, 1],
                2: pixels[:, :, 2],
                -1: pixels[:, :, 3]
            }

        # 3. Update Layer
        # This updates the C++ object in memory
        layer.set_image_data(new_data)
        
        # 4. Write to Disk
        # This commits the changes
        layered_file.write(psd_path)
        
        return True

    except Exception as e:
        print(f"BPSD Engine Error (Write Layer): {e}")
        return False