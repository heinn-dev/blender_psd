import bpy
from . import ui_ops

BLEND_MODE_MAP = {
    'NORMAL': 'MIX',
    'MULTIPLY': 'MULTIPLY',
    'SCREEN': 'SCREEN',
    'OVERLAY': 'OVERLAY',
    'DARKEN': 'DARKEN',
    'LIGHTEN': 'LIGHTEN',
    'COLORDODGE': 'DODGE',
    'COLORBURN': 'BURN',
    'LINEARBURN': 'LINEAR_BURN',
    'LINEARDODGE': 'ADD',
    'SOFTLIGHT': 'SOFT_LIGHT',
    'DIFFERENCE': 'DIFFERENCE',
    'EXCLUSION': 'EXCLUSION',
    'SUBTRACT': 'SUBTRACT',
    'DIVIDE': 'DIVIDE',
    'HUE': 'HUE',
    'SATURATION': 'SATURATION',
    'COLOR': 'COLOR',
    'LUMINOSITY': 'VALUE',
    'PASSTHROUGH': 'MIX',
}

def get_blender_blend_mode(psd_mode_str):
    if not psd_mode_str: return 'MIX'
    key = psd_mode_str.upper().strip()
    return BLEND_MODE_MAP.get(key, 'MIX')

def get_effective_visibility(item):
    if item.visibility_override == 'HIDE':
        return False
    if item.visibility_override == 'SHOW':
        return True
    # PSD Mode
    # We ignore hidden_by_parent because the node tree hierarchy naturally handles
    # parent visibility (parent mix node will mute the branch).
    # This allows us to "Force Show" a parent and have children appear.
    return item.is_visible

def get_immediate_children(layer_list, parent_index):
    """
    Returns list of (index, item) for immediate children of the group.
    Assumes strict indentation (parent.indent + 1).
    """
    children = []

    if parent_index == -1:
        # Root level (indent 0)
        target_indent = 0
        start_i = 0
        end_i = len(layer_list)
    else:
        parent = layer_list[parent_index]
        target_indent = parent.indent + 1
        start_i = parent_index + 1
        end_i = len(layer_list)

    i = start_i
    while i < end_i:
        item = layer_list[i]

        # Stop if we exit the group (indent <= parent.indent)
        if parent_index != -1 and item.indent <= layer_list[parent_index].indent:
            break

        if item.indent == target_indent:
            children.append((i, item))

        i += 1

    return children

def inline_mix_logic(nodes, links, blend_mode, opacity, is_visible,
                     socket_mask, socket_layer_color, socket_layer_alpha,
                     socket_bot_color, socket_bot_alpha,
                     location=(0,0), parent=None,
                     socket_clip_alpha=None, layer_id=0):
    """
    Generates the mixing nodes directly into the tree (No groups).
    Returns (out_color_socket, out_alpha_socket).
    """
    x, y = location

    def set_id(node):
        if layer_id > 0: node["bpsd_layer_id"] = layer_id

    # 1. Calc Factor = LayerAlpha * Mask * Clip * Opacity * Visibility

    # Mul 1: LayerAlpha * Mask
    mul_1 = nodes.new('ShaderNodeMath')
    mul_1.operation = 'MULTIPLY'
    mul_1.label = "Alpha * Mask"
    mul_1.location = (x, y)
    set_id(mul_1)
    if parent: mul_1.parent = parent

    if socket_layer_alpha:
        links.new(socket_layer_alpha, mul_1.inputs[0])
    else:
        mul_1.inputs[0].default_value = 1.0

    if socket_mask:
        links.new(socket_mask, mul_1.inputs[1])
    else:
        mul_1.inputs[1].default_value = 1.0 # No mask = 1.0

    # Mul 1b: Result * Clip Alpha (New Step)
    prev_socket = mul_1.outputs[0]

    if socket_clip_alpha:
        mul_clip = nodes.new('ShaderNodeMath')
        mul_clip.operation = 'MULTIPLY'
        mul_clip.label = "* Clip Alpha"
        mul_clip.location = (x + 100, y) # Shift slightly
        set_id(mul_clip)
        if parent: mul_clip.parent = parent

        links.new(prev_socket, mul_clip.inputs[0])
        links.new(socket_clip_alpha, mul_clip.inputs[1])
        prev_socket = mul_clip.outputs[0]

        # Shift subsequent nodes
        x += 100

    # Mul 2: Result * Opacity * Visibility
    mul_2 = nodes.new('ShaderNodeMath')
    mul_2.operation = 'MULTIPLY'
    mul_2.label = "* Opacity"
    mul_2.location = (x + 200, y)
    set_id(mul_2)
    if parent: mul_2.parent = parent

    links.new(prev_socket, mul_2.inputs[0])

    # Effective Opacity
    eff_opacity = opacity * (1.0 if is_visible else 0.0)
    mul_2.inputs[1].default_value = eff_opacity

    fac_socket = mul_2.outputs[0]

    # --- IF FIRST LAYER (No Bottom) ---
    if socket_bot_color is None:
        # Just return the layer color/alpha (processed by opacity/mask)
        # However, we must ensure we output (Color, Alpha) where Alpha is the Factor.

        # Color: Just pass through the layer color.
        # If the layer has no color input (e.g. error?), default to white?
        # But socket_layer_color should be valid if we are here, or handled by caller.

        return socket_layer_color, fac_socket, fac_socket

    # 2. Calc Out Alpha = Fac + BottomAlpha * (1 - Fac)

    # (1 - Fac)
    sub_1 = nodes.new('ShaderNodeMath')
    sub_1.operation = 'SUBTRACT'
    sub_1.inputs[0].default_value = 1.0
    sub_1.label = "1 - Fac"
    sub_1.location = (x + 400, y - 100)
    set_id(sub_1)
    if parent: sub_1.parent = parent

    links.new(fac_socket, sub_1.inputs[1])

    # Bot * InvFac
    mul_bot = nodes.new('ShaderNodeMath')
    mul_bot.operation = 'MULTIPLY'
    mul_bot.label = "Bot * InvFac"
    mul_bot.location = (x + 600, y - 100)
    set_id(mul_bot)
    if parent: mul_bot.parent = parent

    if socket_bot_alpha:
        links.new(socket_bot_alpha, mul_bot.inputs[0])
    else:
        mul_bot.inputs[0].default_value = 0.0

    links.new(sub_1.outputs[0], mul_bot.inputs[1])

    # Add
    add_alpha = nodes.new('ShaderNodeMath')
    add_alpha.operation = 'ADD'
    add_alpha.label = "Out Alpha"
    add_alpha.location = (x + 800, y - 100)
    set_id(add_alpha)
    if parent: add_alpha.parent = parent

    links.new(fac_socket, add_alpha.inputs[0])
    links.new(mul_bot.outputs[0], add_alpha.inputs[1])

    out_alpha = add_alpha.outputs[0]

    # 3. Calc Out Color = Mix(Bottom, Layer, Fac)

    mix_node = nodes.new('ShaderNodeMix')
    mix_node.data_type = 'RGBA'
    blender_mode = get_blender_blend_mode(blend_mode)
    mix_node.blend_type = blender_mode
    mix_node.label = f"Mix {blender_mode}"
    mix_node.location = (x + 800, y + 100)
    set_id(mix_node)
    if parent: mix_node.parent = parent

    links.new(fac_socket, mix_node.inputs['Factor'])

    if socket_bot_color:
        links.new(socket_bot_color, mix_node.inputs['A'])
    else:
        mix_node.inputs['A'].default_value = (0.0, 0.0, 0.0, 1.0)

    if socket_layer_color:
        links.new(socket_layer_color, mix_node.inputs['B'])
    else:
         mix_node.inputs['B'].default_value = (1.0, 1.0, 1.0, 1.0)

    out_color = mix_node.outputs['Result']

    return out_color, out_alpha, fac_socket


def build_hierarchy_recursive(nodes, links, props, parent_index,
                              bottom_color_socket, bottom_alpha_socket,
                              x_loc, y_loc):
    """
    Recursive function to build the stack.
    parent_index: -1 for root.
    Returns (final_color_socket, final_alpha_socket, next_x_loc)
    """

    # Get children indices
    children = get_immediate_children(props.layer_list, parent_index)

    # We iterate REVERSE (Bottom-to-Top) for compositing order
    current_col = bottom_color_socket
    current_alp = bottom_alpha_socket

    cursor_x = x_loc

    # Store effective alphas for clipping
    layer_alpha_map = {}

    for idx, item in reversed(children):

        # Create Frame
        frame = nodes.new('NodeFrame')
        frame.label = item.name
        frame.use_custom_color = True
        frame.color = (0.2, 0.3, 0.4) if item.layer_type != 'GROUP' else (0.4, 0.3, 0.2)
        frame.location = (cursor_x, y_loc)
        if item.layer_id > 0: frame["bpsd_layer_id"] = item.layer_id

        # --- IF GROUP ---
        if item.layer_type == 'GROUP':

            is_passthrough = (item.blend_mode.lower() == 'passthrough')

            # 1. Determine Input for Group Internal Stack
            if is_passthrough:
                g_in_col = current_col
                g_in_alp = current_alp
            else:
                # Normal Group: Start Fresh (First layer determines base)
                g_in_col = None
                g_in_alp = None

            # 2. Recurse
            g_out_col, g_out_alp, child_end_x = build_hierarchy_recursive(
                nodes, links, props, idx,
                g_in_col, g_in_alp,
                cursor_x + 300, y_loc
            )

            # 3. Mix Group Result onto Main Chain
            # Both PassThrough and Normal groups now mix onto the chain
            # (PassThrough uses MIX via blend_mode map)

            mask_socket = None
            if item.has_mask:
                mask_img = ui_ops.find_loaded_image(props.active_psd_path, idx, True, item.layer_id)
                if mask_img:
                    m_node = nodes.new('ShaderNodeTexImage')
                    m_node.image = mask_img
                    m_node.label = "Group Mask"
                    m_node.location = (child_end_x + 50, y_loc - 300)
                    m_node.parent = frame
                    if item.layer_id > 0: m_node["bpsd_layer_id"] = item.layer_id
                    if m_node.image: m_node.image.colorspace_settings.name = 'Non-Color'
                    mask_socket = m_node.outputs['Color']

            # Resolve Clipping
            socket_clip_alpha = None
            if item.is_clipping_mask and item.clip_base_index in layer_alpha_map:
                socket_clip_alpha = layer_alpha_map[item.clip_base_index]

            res_col, res_alp, fac_socket = inline_mix_logic(
                nodes, links, item.blend_mode, item.opacity, get_effective_visibility(item),
                mask_socket, g_out_col, g_out_alp,
                current_col, current_alp,
                location=(child_end_x + 200, y_loc),
                parent=frame,
                socket_clip_alpha=socket_clip_alpha,
                layer_id=item.layer_id
            )
            current_col = res_col
            current_alp = res_alp

            # Store Factor for future clipping masks
            layer_alpha_map[idx] = fac_socket

            cursor_x = child_end_x + 1000

        # --- IF LAYER ---
        else:
            # Color
            col_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
            if col_img:
                t_node = nodes.new('ShaderNodeTexImage')
                t_node.image = col_img
                t_node.label = "Layer Color"
                t_node.location = (cursor_x + 50, y_loc)
                t_node.parent = frame
                if item.layer_id > 0: t_node["bpsd_layer_id"] = item.layer_id
                if t_node.image: t_node.image.colorspace_settings.name = 'sRGB'

                layer_color_socket = t_node.outputs['Color']
                layer_alpha_socket = t_node.outputs['Alpha']
            else:
                # Placeholder / No Image
                rgb = nodes.new('ShaderNodeRGB')
                rgb.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
                rgb.label = "Placeholder"
                rgb.location = (cursor_x + 50, y_loc)
                rgb.parent = frame
                if item.layer_id > 0: rgb["bpsd_layer_id"] = item.layer_id

                layer_color_socket = rgb.outputs[0]

                val = nodes.new('ShaderNodeValue')
                val.outputs[0].default_value = 1.0
                val.location = (cursor_x + 50, y_loc - 100)
                val.parent = frame
                if item.layer_id > 0: val["bpsd_layer_id"] = item.layer_id
                layer_alpha_socket = val.outputs[0]

            # Mask
            mask_socket = None
            if item.has_mask:
                mask_img = ui_ops.find_loaded_image(props.active_psd_path, idx, True, item.layer_id)
                if mask_img:
                    m_node = nodes.new('ShaderNodeTexImage')
                    m_node.image = mask_img
                    m_node.label = "Layer Mask"
                    m_node.location = (cursor_x + 50, y_loc - 300)
                    m_node.parent = frame
                    if item.layer_id > 0: m_node["bpsd_layer_id"] = item.layer_id
                    if m_node.image: m_node.image.colorspace_settings.name = 'Non-Color'
                    mask_socket = m_node.outputs['Color']

            # Mix
            effective_opacity = item.opacity
            if item.layer_type not in ['LAYER', 'SMART']:
                 effective_opacity = 0.0 # Hide adjustment layers for now

            # Resolve Clipping
            socket_clip_alpha = None
            if item.is_clipping_mask and item.clip_base_index in layer_alpha_map:
                socket_clip_alpha = layer_alpha_map[item.clip_base_index]

            res_col, res_alp, fac_socket = inline_mix_logic(
                nodes, links, item.blend_mode, effective_opacity, get_effective_visibility(item),
                mask_socket, layer_color_socket, layer_alpha_socket,
                current_col, current_alp,
                location=(cursor_x + 300, y_loc),
                parent=frame,
                socket_clip_alpha=socket_clip_alpha,
                layer_id=item.layer_id
            )

            current_col = res_col
            current_alp = res_alp

            # Store Factor for future clipping masks
            layer_alpha_map[idx] = fac_socket

            cursor_x += 1200

    return current_col, current_alp, cursor_x


class BPSD_OT_create_psd_nodes(bpy.types.Operator):
    bl_idname = "bpsd.create_psd_nodes"
    bl_label = "Create PSD Node Network"
    bl_description = "Generate a full node network for the current PSD stack"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props

        if not props.active_psd_path or len(props.layer_list) == 0:
            self.report({'ERROR'}, "No PSD loaded.")
            return {'CANCELLED'}

        # Ensure all textures are loaded so we don't generate placeholders
        bpy.ops.bpsd.load_all_layers('EXEC_DEFAULT')

        # Check if we can proceed
        group_name = "BPSD_PSD_Output"
        ng = bpy.data.node_groups.get(group_name)

        obj = context.active_object
        has_active_material = (obj and obj.active_material)

        if not ng and not has_active_material:
            self.report({'ERROR'}, "No active object/material to create the node group in.")
            return {'CANCELLED'}

        # Create/Get Root Group
        if ng:
             ng.nodes.clear()
        else:
             ng = bpy.data.node_groups.new(name=group_name, type='ShaderNodeTree')
             ng.interface.new_socket(name="Out Color", in_out='OUTPUT', socket_type='NodeSocketColor')
             ng.interface.new_socket(name="Out Alpha", in_out='OUTPUT', socket_type='NodeSocketFloat')

        # Store Signature
        ng["bpsd_structure_signature"] = props.structure_signature

        nodes = ng.nodes
        links = ng.links

        # Output Node
        output_node = nodes.new('NodeGroupOutput')
        output_node.location = (2000, 0)

        # Build Hierarchy
        final_col, final_alp, end_x = build_hierarchy_recursive(
            nodes, links, props, -1,
            None, None,
            -500, 0
        )

        if final_col is None:
             # Fallback for empty PSD
             start_rgb = nodes.new('ShaderNodeRGB')
             start_rgb.outputs[0].default_value = (0.0, 0.0, 0.0, 0.0)
             start_rgb.location = (0, 0)
             final_col = start_rgb.outputs[0]

             start_val = nodes.new('ShaderNodeValue')
             start_val.outputs[0].default_value = 0.0
             start_val.location = (0, -200)
             final_alp = start_val.outputs[0]

        output_node.location = (end_x + 200, 0)
        links.new(final_col, output_node.inputs['Out Color'])
        links.new(final_alp, output_node.inputs['Out Alpha'])

        # Instantiate in Material (If valid context)
        if has_active_material:
            mat = obj.active_material
            if not mat.use_nodes: mat.use_nodes = True

            root_node = None
            for n in mat.node_tree.nodes:
                if n.type == 'GROUP' and n.node_tree == ng:
                    root_node = n
                    break

            if not root_node:
                root_node = mat.node_tree.nodes.new('ShaderNodeGroup')
                root_node.node_tree = ng
                root_node.location = (0, 300)

            root_node.label = "PSD Output"
            root_node.select = True
            mat.node_tree.nodes.active = root_node

        self.report({'INFO'}, "Created/Updated PSD Node Network")
        return {'FINISHED'}


class BPSD_OT_create_layer_node(bpy.types.Operator):
    bl_idname = "bpsd.create_layer_node"
    bl_label = "Add Layer Node"
    bl_description = "Creates a node setup for this layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        idx = props.active_layer_index
        if idx < 0: return {'CANCELLED'}
        item = props.layer_list[idx]

        obj = context.active_object
        if not obj or not obj.active_material: return {'CANCELLED'}
        mat = obj.active_material
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        frame = nodes.new('NodeFrame')
        frame.label = item.name
        frame.location = (0,0)

        col_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
        if col_img:
            t_node = nodes.new('ShaderNodeTexImage')
            t_node.image = col_img
            t_node.parent = frame
            t_node.location = (0,0)
            l_col = t_node.outputs['Color']
            l_alp = t_node.outputs['Alpha']
        else:
            return {'CANCELLED'}

        inline_mix_logic(
             nodes, links, item.blend_mode, item.opacity, get_effective_visibility(item),
             None, l_col, l_alp,
             None, None,
             location=(300,0), parent=frame
        )
        return {'FINISHED'}

class BPSD_OT_create_layer_frame(bpy.types.Operator):
    bl_idname = "bpsd.create_layer_frame"
    bl_label = "Create Layer Frame"
    bl_description = "Alias for create layer node"
    bl_options = {'REGISTER', 'UNDO'}
    layer_index: bpy.props.IntProperty(default=-1) # type: ignore

    def execute(self, context):
        return bpy.ops.bpsd.create_layer_node('EXEC_DEFAULT')

class BPSD_OT_create_group_nodes(bpy.types.Operator):
    bl_idname = "bpsd.create_group_nodes"
    bl_label = "Create Group Nodes (Debug)"
    bl_description = "Generate recursive nodes for the first found group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        group_idx = -1
        for i, item in enumerate(props.layer_list):
            if item.layer_type == 'GROUP':
                group_idx = i
                break
        if group_idx == -1: return {'CANCELLED'}

        obj = context.active_object
        if not obj or not obj.active_material: return {'CANCELLED'}
        mat = obj.active_material
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        start_rgb = nodes.new('ShaderNodeRGB')
        start_rgb.location = (0,0)
        start_val = nodes.new('ShaderNodeValue')
        start_val.location = (0,-200)

        build_hierarchy_recursive(
            nodes, links, props, group_idx,
            start_rgb.outputs[0], start_val.outputs[0],
            300, 0
        )
        return {'FINISHED'}

class BPSD_OT_update_psd_nodes(bpy.types.Operator):
    bl_idname = "bpsd.update_psd_nodes"
    bl_label = "Update Node Values"
    bl_description = "Update opacity, visibility and blend modes without regenerating the graph"

    def execute(self, context):
        props = context.scene.bpsd_props

        # 1. Validation
        # Find the node group
        ng = bpy.data.node_groups.get("BPSD_PSD_Output")
        if not ng:
            self.report({'ERROR'}, "PSD Node Group 'BPSD_PSD_Output' not found.")
            return {'CANCELLED'}

        # Check signature (Optional strict check)
        stored_sig = ng.get("bpsd_structure_signature", "")
        if stored_sig != props.structure_signature:
            self.report({'WARNING'}, "Structure signature mismatch. Changes to hierarchy/masking require full regeneration.")
            # We proceed anyway to attempt best-effort update for things like opacity

        # 2. Iterate Layers and Update Nodes
        layer_map = {item.layer_id: item for item in props.layer_list if item.layer_id > 0}

        count = 0
        for node in ng.nodes:
            lid = node.get("bpsd_layer_id", 0)
            if lid > 0 and lid in layer_map:
                item = layer_map[lid]

                # Update Frame Name
                if node.type == 'FRAME':
                    if node.label != item.name:
                        node.label = item.name

                # Update Opacity / Visibility
                # Look for "* Opacity" math node
                if node.type == 'MATH' and node.label == "* Opacity":
                     eff_opacity = item.opacity * (1.0 if get_effective_visibility(item) else 0.0)
                     if node.inputs[1].default_value != eff_opacity:
                        node.inputs[1].default_value = eff_opacity
                        count += 1

                # Update Blend Mode
                if node.type == 'MIX_RGB' or node.type == 'MIX': # Handle both for safety (MixRGB is deprecated in 3.4+)
                    if node.label.startswith("Mix "):
                         blender_mode = get_blender_blend_mode(item.blend_mode)

                         # Check blend_type property if it exists
                         if hasattr(node, "blend_type") and node.blend_type != blender_mode:
                             node.blend_type = blender_mode
                             node.label = f"Mix {blender_mode}"
                             count += 1

        self.report({'INFO'}, f"Updated {count} nodes.")
        return {'FINISHED'}
