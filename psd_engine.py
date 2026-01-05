import numpy as np
import photoshopapi as psapi

def read_file(path):
    try:
        layered_file = psapi.LayeredFile.read(path)

        def parse_layer_structure(layer, current_index_path="", child_index=0, parent_visible=True):
            layer_name = layer.name
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

            if layer_name == "":
                layer_type = "UNKNOWN"
                layer_name = "---"

            node = {
                "name": layer_name,
                "path": index_path,
                "layer_type": layer_type,
                "has_mask": has_mask,
                "is_clipping_mask": layer.clipping_mask,
                "is_visible": layer.is_visible,
                "hidden_by_parent": not parent_visible,
                "layer_id" : layer.layer_id,
                "blend_mode": str(layer.blend_mode).replace("BlendMode.", "").strip(),
                "opacity": layer.opacity,
                "children": []
            }

            if layer_type == "LAYER":
                print(f"Layer {layer_name} has compression {str(layer.compression)}")

            if is_group:
                is_effectively_visible = parent_visible and layer.is_visible

                for i, child in enumerate(layer.layers):
                    node["children"].append(parse_layer_structure(child, index_path, i, is_effectively_visible))

            return node

        structure = []

        for i, layer in enumerate(layered_file.layers):
            structure.append(parse_layer_structure(layer, "", i, True))

        return structure, layered_file.width, layered_file.height

    except Exception as e:
        print(f"BPSD Engine Error (Read Structure): {e}")
        return [], 0, 0


def get_layer_by_index_path(layered_file, index_path):
    indices = [int(i) for i in index_path.split("/")]
    current_layers = layered_file.layers

    layer = None
    for idx in indices:
        if idx < len(current_layers):
            layer = current_layers[idx]
            if hasattr(layer, 'layers'):
                current_layers = layer.layers
        else:
            return None

    return layer

def get_layer(layered_file, layer_id=0, layer_path=""):
    if layer_id and layer_id > 0:
        def search(layers):
            for layer in layers:
                if hasattr(layer, 'layer_id') and layer.layer_id == layer_id:
                    return layer
                if hasattr(layer, 'layers'):
                    found = search(layer.layers)
                    if found: return found
            return None

        found_layer = search(layered_file.layers)
        if found_layer:
            return found_layer

    if layer_path:
        return get_layer_by_index_path(layered_file, layer_path)

    return None


def calculate_union_bounds(layer_x, layer_y, layer_w, layer_h, canvas_w, canvas_h):
    c_x, c_y = 0, 0

    u_x = min(layer_x, c_x)
    u_y = min(layer_y, c_y)
    u_r = max(layer_x + layer_w, c_x + canvas_w)
    u_b = max(layer_y + layer_h, c_y + canvas_h)

    u_w = int(u_r - u_x)
    u_h = int(u_b - u_y)

    offset_l_x = int(layer_x - u_x)
    offset_l_y = int(layer_y - u_y)

    offset_c_x = int(c_x - u_x)
    offset_c_y = int(c_y - u_y)

    return (u_x, u_y, u_w, u_h), (offset_l_x, offset_l_y), (offset_c_x, offset_c_y)

# --- READ LOGIC ---

def paste_to_canvas(canvas, source_arr, canvas_w, canvas_h, offset_x, offset_y):
    src_h, src_w = source_arr.shape

    dst_x1 = max(0, offset_x)
    dst_y1 = max(0, offset_y)
    dst_x2 = min(canvas_w, offset_x + src_w)
    dst_y2 = min(canvas_h, offset_y + src_h)

    src_x1 = dst_x1 - offset_x
    src_y1 = dst_y1 - offset_y
    src_x2 = src_x1 + (dst_x2 - dst_x1)
    src_y2 = src_y1 + (dst_y2 - dst_y1)

    if dst_x2 > dst_x1 and dst_y2 > dst_y1:
        canvas[dst_y1:dst_y2, dst_x1:dst_x2] = source_arr[src_y1:src_y2, src_x1:src_x2]

def _read_layer_internal(layered_file, layer_path, target_w, target_h, fetch_mask, layer_id=0):
    layer = get_layer(layered_file, layer_id, layer_path)
    if not layer: return None

    # --- MASK PATH ---
    if fetch_mask:
        mask_bg = getattr(layer, 'mask_default_color', 255)
        canvas = np.full((target_h, target_w), mask_bg, dtype=np.uint8)

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
            fill_val = 1.0
            if np.issubdtype(dtype, np.integer):
                fill_val = np.iinfo(dtype).max

            opaque_block = np.full((l_h, l_w), fill_val, dtype=dtype)
            paste_to_canvas(c_a, opaque_block, target_w, target_h, layer_left, layer_top)

        img_stack = np.stack([c_r, c_g, c_b, c_a], axis=-1)
        img_stack = np.flipud(img_stack)

        return (img_stack.astype(np.float32) / 255.0).flatten()


def read_layer(psd_path, layer_path, target_w, target_h, fetch_mask=False, layer_id=0):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        flat_data = _read_layer_internal(layered_file, layer_path, target_w, target_h, fetch_mask, layer_id)
        if flat_data is None: return None, 0, 0
        return flat_data, target_w, target_h
    except Exception as e:
        print(f"BPSD Read Error: {e}")
        return None, 0, 0

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
            layer_id = req.get('layer_id', 0)

            pixels = _read_layer_internal(layered_file, path, w, h, mask, layer_id)

            if pixels is not None:
                results[(layer_index, mask)] = pixels

        return results
    except Exception as e:
        print(f"BPSD Batch Read Error: {e}")
        return {}


# --- WRITE LOGIC ---

def _prepare_blender_pixels(blender_pixels, width, height):
    pixels = np.array(blender_pixels).reshape((height, width, 4))
    pixels = np.flipud(pixels)
    return (pixels * 255).astype(np.uint8)

def _write_mask(layer, pixels, canvas_w, canvas_h):
    try:
        mask_data = pixels[:, :, 0] # Red Channel as Mask
        layer.mask = mask_data
        layer.mask_position = psapi.geometry.Point2D(canvas_w / 2, canvas_h / 2)
        return True
    except Exception as e:
        print(f"BPSD Mask Write Error: {e}")
        return False

def _write_color_channels(layer, pixels, canvas_w, canvas_h):
    planar_data = layer.get_image_data()

    b_data = {
        0: pixels[:, :, 0],
        1: pixels[:, :, 1],
        2: pixels[:, :, 2],
        -1: pixels[:, :, 3]
    }

    if not planar_data:
        layer.set_image_data(b_data, width=canvas_w, height=canvas_h)
        layer.center_x = canvas_w / 2
        layer.center_y = canvas_h / 2
        return True

    l_w = layer.width
    l_h = layer.height
    l_x = int(layer.center_x - (l_w / 2))
    l_y = int(layer.center_y - (l_h / 2))

    (u_x, u_y, u_w, u_h), (offset_l_x, offset_l_y), (offset_c_x, offset_c_y) = calculate_union_bounds(
        l_x, l_y, l_w, l_h, canvas_w, canvas_h
    )

    new_planar_data = {}
    all_channels = set(planar_data.keys()) | set(b_data.keys())
    valid_channels = {k for k in all_channels if k >= -1}

    dtype = np.uint8
    if planar_data:
        dtype = next(iter(planar_data.values())).dtype

    for ch in valid_channels:
        union_arr = np.zeros((u_h, u_w), dtype=dtype)

        if ch in planar_data:
            old_arr = planar_data[ch]
            h, w = old_arr.shape
            if h <= u_h and w <= u_w:
                union_arr[offset_l_y:offset_l_y+h, offset_l_x:offset_l_x+w] = old_arr

        if ch in b_data:
            new_arr = b_data[ch]
            if new_arr.dtype != dtype:
                new_arr = new_arr.astype(dtype)

            union_arr[offset_c_y:offset_c_y+canvas_h, offset_c_x:offset_c_x+canvas_w] = new_arr

        new_planar_data[ch] = union_arr

    try:
        layer.set_image_data(new_planar_data, width=u_w, height=u_h)
        layer.center_x = u_x + (u_w / 2)
        layer.center_y = u_y + (u_h / 2)
        return True
    except Exception as e:
        print(f"BPSD Write Union Error: {e}")
        return False

def write_to_layered_file(layered_file, layer_path, blender_pixels, canvas_w, canvas_h, is_mask, layer_id=0):
    layer = get_layer(layered_file, layer_id, layer_path)
    if not layer:
        print(f"Can't save {layer_path} (ID: {layer_id}) ?")
        return False

    pixels = _prepare_blender_pixels(blender_pixels, canvas_w, canvas_h)

    if is_mask:
        return _write_mask(layer, pixels, canvas_w, canvas_h)
    else:
        return _write_color_channels(layer, pixels, canvas_w, canvas_h)

def write_all_layers(psd_path, updates, canvas_w, canvas_h):
    try:
        layered_file = psapi.LayeredFile.read(psd_path)
        count = 0
        for data in updates:
            w = data.get('width', canvas_w)
            h = data.get('height', canvas_h)

            if write_to_layered_file(layered_file, data['layer_path'], data['pixels'],
                                   w, h, data['is_mask'], data.get('layer_id', 0)):
                count += 1

        if count > 0:
            layered_file.write(psd_path)
            return True
        return False

    except Exception as e:
        print(f"BPSD Batch Save Error: {e}")
        return False

def write_layer(psd_path, layer_path, blender_pixels, width, height, is_mask=False, layer_id=0):
    update = {
        'layer_path': layer_path,
        'pixels': blender_pixels,
        'width': width,
        'height': height,
        'is_mask': is_mask,
        'layer_id': layer_id
    }
    return write_all_layers(psd_path, [update], width, height)
