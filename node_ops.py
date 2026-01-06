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
    return item.is_visible

def get_immediate_children(layer_list, parent_index):
    children = []

    if parent_index == -1:
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

        if parent_index != -1 and item.indent <= layer_list[parent_index].indent:
            break

        if item.indent == target_indent:
            children.append((i, item))

        i += 1

    return children

def combine_masks(nodes, links, mask1, mask2, x, y, parent=None, layer_id=0):
    if not mask1 and not mask2:
        return None
    if mask1 and not mask2:
        return mask1
    if not mask1 and mask2:
        return mask2

    mul = nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.label = "Mask Combine"
    mul.location = (x, y)
    if parent: mul.parent = parent
    if layer_id > 0: mul["bpsd_layer_id"] = layer_id

    links.new(mask1, mul.inputs[0])
    links.new(mask2, mul.inputs[1])

    return mul.outputs[0]

def combine_opacity(nodes, links, opacity_socket, item_opacity, x, y, parent=None, layer_id=0):
    val = nodes.new('ShaderNodeValue')
    val.outputs[0].default_value = item_opacity
    val.label = "Group Opacity"
    val.location = (x, y)
    if parent: val.parent = parent
    if layer_id > 0: val["bpsd_layer_id"] = layer_id

    item_sock = val.outputs[0]

    if not opacity_socket:
        return item_sock

    mul = nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.label = "Opacity Combine"
    mul.location = (x + 150, y)
    if parent: mul.parent = parent
    if layer_id > 0: mul["bpsd_layer_id"] = layer_id

    links.new(opacity_socket, mul.inputs[0])
    links.new(item_sock, mul.inputs[1])

    return mul.outputs[0]

def inline_mix_logic(nodes, links, blend_mode, opacity, is_visible,
                     socket_mask, socket_layer_color, socket_layer_alpha,
                     socket_bot_color, socket_bot_alpha,
                     location=(0,0), parent=None,
                     socket_clip_alpha=None, layer_id=0,
                     opacity_label="* Opacity",
                     socket_inherited_opacity=None):
    x, y = location

    def set_id(node):
        if layer_id > 0: node["bpsd_layer_id"] = layer_id

    # Alpha * Mask
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
        mul_1.inputs[1].default_value = 1.0

    prev_socket = mul_1.outputs[0]

    if socket_clip_alpha:
        mul_clip = nodes.new('ShaderNodeMath')
        mul_clip.operation = 'MULTIPLY'
        mul_clip.label = "* Clip Alpha"
        mul_clip.location = (x + 100, y)
        set_id(mul_clip)
        if parent: mul_clip.parent = parent

        links.new(prev_socket, mul_clip.inputs[0])
        links.new(socket_clip_alpha, mul_clip.inputs[1])
        prev_socket = mul_clip.outputs[0]

        x += 100

    # Result * Opacity * Visibility
    mul_2 = nodes.new('ShaderNodeMath')
    mul_2.operation = 'MULTIPLY'
    mul_2.label = opacity_label
    mul_2.location = (x + 200, y)
    set_id(mul_2)
    if parent: mul_2.parent = parent

    links.new(prev_socket, mul_2.inputs[0])

    eff_opacity = opacity * (1.0 if is_visible else 0.0)
    mul_2.inputs[1].default_value = eff_opacity

    prev_socket = mul_2.outputs[0]

    # Result * Inherited Opacity
    if socket_inherited_opacity:
        mul_3 = nodes.new('ShaderNodeMath')
        mul_3.operation = 'MULTIPLY'
        mul_3.label = "* Inherited Opacity"
        mul_3.location = (x + 350, y)
        set_id(mul_3)
        if parent: mul_3.parent = parent

        links.new(prev_socket, mul_3.inputs[0])
        links.new(socket_inherited_opacity, mul_3.inputs[1])
        prev_socket = mul_3.outputs[0]
        x += 150

    fac_socket = prev_socket

    if socket_bot_color is None:
        return socket_layer_color, fac_socket, fac_socket

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

    # Mix(Bottom, Layer, Fac)
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


def get_interpolation_mode(props):
    return 'Closest' if props.use_closest_interpolation else 'Linear'

def update_interpolation_callback(self, context):
    bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')

def _get_socket_from_image(nodes, image, label, x, y, parent=None, layer_id=0):
    if not image: return None, None
    t_node = nodes.new('ShaderNodeTexImage')
    t_node.image = image
    t_node.label = label
    t_node.location = (x, y)

    if bpy.context and bpy.context.scene:
        props = bpy.context.scene.bpsd_props
        if props:
             t_node.interpolation = get_interpolation_mode(props)

    if parent: t_node.parent = parent
    if layer_id > 0: t_node["bpsd_layer_id"] = layer_id

    if label == "Layer Mask" or label == "Group Mask":
        if t_node.image: t_node.image.colorspace_settings.name = 'Non-Color'
        return t_node.outputs['Color'], None
    else:
        if t_node.image: t_node.image.colorspace_settings.name = 'sRGB'
        return t_node.outputs['Color'], t_node.outputs['Alpha']

def _get_layer_content(nodes, links, props, item, index, x, y, frame):
    col_img = ui_ops.find_loaded_image(props.active_psd_path, index, False, item.layer_id)
    c_sock, a_sock = None, None

    if col_img:
        c_sock, a_sock = _get_socket_from_image(nodes, col_img, "Layer Color", x + 50, y, frame, item.layer_id)
    else:
        rgb = nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        rgb.label = "Placeholder"
        rgb.location = (x + 50, y)
        rgb.parent = frame
        if item.layer_id > 0: rgb["bpsd_layer_id"] = item.layer_id
        c_sock = rgb.outputs[0]

        val = nodes.new('ShaderNodeValue')
        val.outputs[0].default_value = 1.0
        val.location = (x + 50, y - 100)
        val.parent = frame
        if item.layer_id > 0: val["bpsd_layer_id"] = item.layer_id
        a_sock = val.outputs[0]

    m_sock = None
    if item.has_mask:
        mask_img = ui_ops.find_loaded_image(props.active_psd_path, index, True, item.layer_id)
        if mask_img:
            m_sock, _ = _get_socket_from_image(nodes, mask_img, "Layer Mask", x + 50, y - 300, frame, item.layer_id)

    return c_sock, a_sock, m_sock


def _create_item_frame(nodes, item, x, y):
    frame = nodes.new('NodeFrame')
    frame.label = item.name
    frame.use_custom_color = True
    frame.color = (0.2, 0.3, 0.4) if item.layer_type != 'GROUP' else (0.4, 0.3, 0.2)
    frame.location = (x, y)
    if item.layer_id > 0: frame["bpsd_layer_id"] = item.layer_id
    return frame

def _resolve_item_content(nodes, links, props, item, index, x, y, frame,
                          background_col=None, background_alp=None,
                          inherited_mask=None, inherited_opacity_socket=None):
    col, alp, mask = None, None, None
    next_x = x

    if item.layer_type == 'GROUP':
        is_passthrough = (item.blend_mode == 'PASSTHROUGH')

        rec_bg_col = background_col if is_passthrough else None
        rec_bg_alp = background_alp if is_passthrough else None

        rec_inherited_mask = None
        rec_inherited_opacity = None

        group_mask_socket = None
        if item.has_mask:
            mask_img = ui_ops.find_loaded_image(props.active_psd_path, index, True, item.layer_id)
            if mask_img:
                group_mask_socket, _ = _get_socket_from_image(nodes, mask_img, "Group Mask", x + 50, y - 300, frame, item.layer_id)

        if is_passthrough:
            rec_inherited_mask = combine_masks(nodes, links, inherited_mask, group_mask_socket, x + 200, y - 400, frame, item.layer_id)

            eff_opacity = item.opacity if item.is_visible else 0.0
            if not get_effective_visibility(item):
                eff_opacity = 0.0

            rec_inherited_opacity = combine_opacity(nodes, links, inherited_opacity_socket, eff_opacity, x + 200, y - 500, frame, item.layer_id)
        else:
            mask = group_mask_socket

        col, alp, child_end_x = build_hierarchy_recursive(
            nodes, links, props, index,
            rec_bg_col, rec_bg_alp,
            x + 300, y,
            inherited_mask=rec_inherited_mask,
            inherited_opacity_socket=rec_inherited_opacity
        )
        next_x = child_end_x + 200

    else:
        col, alp, mask = _get_layer_content(nodes, links, props, item, index, x, y, frame)

    return col, alp, mask, next_x

def _process_composite_unit(nodes, links, props, base_item, base_idx, clipping_layers, current_col, current_alp, x_loc, y_loc,
                            inherited_mask=None, inherited_opacity_socket=None):
    cursor_x = x_loc

    frame = _create_item_frame(nodes, base_item, cursor_x, y_loc)

    base_col, base_alp, base_mask, content_end_x = _resolve_item_content(
        nodes, links, props, base_item, base_idx, cursor_x, y_loc, frame,
        background_col=current_col, background_alp=current_alp,
        inherited_mask=inherited_mask, inherited_opacity_socket=inherited_opacity_socket
    )

    if base_item.layer_type == 'GROUP':
        if base_item.blend_mode == 'PASSTHROUGH':
             if base_col is None:
                 pass

             cursor_x = content_end_x
             return base_col, base_alp, cursor_x

        if base_col is None:
            nodes.remove(frame)
            return current_col, current_alp, cursor_x
        cursor_x = content_end_x

    eff_base_mask = combine_masks(nodes, links, inherited_mask, base_mask, cursor_x + 100, y_loc, frame, base_item.layer_id)

    eff_opacity = base_item.opacity if base_item.layer_type in ['LAYER', 'SMART', 'GROUP'] else 0.0

    iso_col, iso_alp, iso_fac = inline_mix_logic(
        nodes, links, 'NORMAL', eff_opacity, get_effective_visibility(base_item),
        eff_base_mask, base_col, base_alp,
        None, None,
        location=(cursor_x + 300, y_loc), parent=frame,
        layer_id=base_item.layer_id, opacity_label="* Opacity",
        socket_inherited_opacity=inherited_opacity_socket
    )

    clip_mask_socket = iso_fac
    group_accum_col = iso_col
    group_accum_alp = iso_alp

    cursor_x += 1000

    for clip_idx, clip_item in clipping_layers:
        c_frame = _create_item_frame(nodes, clip_item, cursor_x, y_loc + 100)

        c_col, c_alp, c_mask, c_end_x = _resolve_item_content(
            nodes, links, props, clip_item, clip_idx, cursor_x, y_loc + 100, c_frame,
            inherited_mask=inherited_mask, inherited_opacity_socket=inherited_opacity_socket
        )

        if clip_item.layer_type == 'GROUP':
             if c_col is None:
                 nodes.remove(c_frame)
                 continue

             mix_x = c_end_x + 300
        else:
             mix_x = cursor_x + 300

        c_eff_opacity = clip_item.opacity if clip_item.layer_type in ['LAYER', 'SMART', 'GROUP'] else 0.0

        c_eff_mask = combine_masks(nodes, links, inherited_mask, c_mask, mix_x - 100, y_loc + 200, c_frame, clip_item.layer_id)

        c_res_col, c_res_alp, c_fac = inline_mix_logic(
            nodes, links, clip_item.blend_mode, c_eff_opacity, get_effective_visibility(clip_item),
            c_eff_mask, c_col, c_alp,
            group_accum_col, group_accum_alp,
            location=(mix_x, y_loc), parent=c_frame,
            socket_clip_alpha=clip_mask_socket,
            layer_id=clip_item.layer_id, opacity_label="* Opacity",
            socket_inherited_opacity=inherited_opacity_socket
        )

        group_accum_col = c_res_col
        group_accum_alp = c_res_alp

        if clip_item.layer_type == 'GROUP':
            cursor_x = c_end_x + 1000
        else:
            cursor_x += 1000

    final_col, final_alp, final_fac = inline_mix_logic(
        nodes, links, base_item.blend_mode, 1.0, True,
        None, group_accum_col, group_accum_alp,
        current_col, current_alp,
        location=(cursor_x, y_loc), parent=frame,
        layer_id=base_item.layer_id, opacity_label="* Group Final Mix"
    )

    return final_col, final_alp, cursor_x + 1200


def build_hierarchy_recursive(nodes, links, props, parent_index, bottom_color_socket, bottom_alpha_socket, x_loc, y_loc,
                              inherited_mask=None, inherited_opacity_socket=None):
    children = get_immediate_children(props.layer_list, parent_index)
    reversed_children = list(reversed(children))

    current_col = bottom_color_socket
    current_alp = bottom_alpha_socket
    cursor_x = x_loc

    i = 0
    count = len(reversed_children)

    while i < count:
        idx, item = reversed_children[i]

        clipping_layers = []
        j = i + 1
        while j < count:
            next_idx, next_item = reversed_children[j]
            if next_item.is_clipping_mask:
                clipping_layers.append((next_idx, next_item))
                j += 1
            else:
                break

        i = j

        current_col, current_alp, cursor_x = _process_composite_unit(
            nodes, links, props, item, idx, clipping_layers,
            current_col, current_alp, cursor_x, y_loc,
            inherited_mask=inherited_mask, inherited_opacity_socket=inherited_opacity_socket
        )

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

        bpy.ops.bpsd.load_all_layers('EXEC_DEFAULT')

        group_name = "BPSD_PSD_Output"
        ng = bpy.data.node_groups.get(group_name)

        obj = context.active_object
        has_active_material = (obj and obj.active_material)

        if not ng and not has_active_material:
            self.report({'ERROR'}, "No active object/material to create the node group in.")
            return {'CANCELLED'}

        if ng:
             ng.nodes.clear()
             ng.interface.clear()
        else:
             ng = bpy.data.node_groups.new(name=group_name, type='ShaderNodeTree')
        ng.interface.new_socket(name="Out Color", in_out='OUTPUT', socket_type='NodeSocketColor')
        ng.interface.new_socket(name="Out Alpha", in_out='OUTPUT', socket_type='NodeSocketFloat')
        ng.interface.new_socket(name="Out Shader", in_out='OUTPUT', socket_type='NodeSocketShader')

        ng["bpsd_structure_signature"] = props.structure_signature

        nodes = ng.nodes
        links = ng.links

        output_node = nodes.new('NodeGroupOutput')
        output_node.location = (2000, 0)

        final_col, final_alp, end_x = build_hierarchy_recursive(
            nodes, links, props, -1,
            None, None,
            -500, 0
        )

        if final_col is None:
             start_rgb = nodes.new('ShaderNodeRGB')
             start_rgb.outputs[0].default_value = (0.0, 0.0, 0.0, 0.0)
             start_rgb.location = (0, 0)
             final_col = start_rgb.outputs[0]

             start_val = nodes.new('ShaderNodeValue')
             start_val.outputs[0].default_value = 0.0
             start_val.location = (0, -200)
             final_alp = start_val.outputs[0]

        output_node.location = (end_x + 200, 0)

        psd_tex = None
        if props.active_psd_image != 'NONE':
            main_img = bpy.data.images.get(props.active_psd_image)
            if main_img:
                psd_tex = nodes.new('ShaderNodeTexImage')
                psd_tex.image = main_img
                psd_tex.label = "PSD Preview"
                psd_tex.location = (end_x - 300, 200)
                psd_tex["bpsd_psd_preview"] = True

        output_mix = nodes.new('ShaderNodeMix')
        output_mix.data_type = 'RGBA'
        output_mix.blend_type = 'MIX'
        output_mix.label = "Output Toggle"
        output_mix.location = (end_x + 50, 100)
        output_mix["bpsd_output_toggle"] = True
        output_mix.inputs['Factor'].default_value = 0.0

        links.new(final_col, output_mix.inputs['A'])
        if psd_tex:
            links.new(psd_tex.outputs['Color'], output_mix.inputs['B'])
        else:
            output_mix.inputs['B'].default_value = (0.5, 0.5, 0.5, 1.0)

        links.new(output_mix.outputs['Result'], output_node.inputs['Out Color'])
        links.new(final_alp, output_node.inputs['Out Alpha'])

        transparent = nodes.new('ShaderNodeBsdfTransparent')
        transparent.location = (end_x - 100, -200)
        transparent.label = "Transparent"

        emission = nodes.new('ShaderNodeEmission')
        emission.location = (end_x - 100, -350)
        emission.label = "Color Emission"
        links.new(output_mix.outputs['Result'], emission.inputs['Color'])

        mix_shader = nodes.new('ShaderNodeMixShader')
        mix_shader.location = (end_x + 50, -250)
        mix_shader.label = "Alpha Mix"
        links.new(final_alp, mix_shader.inputs['Fac'])
        links.new(transparent.outputs['BSDF'], mix_shader.inputs[1])
        links.new(emission.outputs['Emission'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'], output_node.inputs['Out Shader'])

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

            mat_output = None
            for n in mat.node_tree.nodes:
                if n.type == 'OUTPUT_MATERIAL' and n.get("bpsd_managed"):
                    mat_output = n
                    break

            if not mat_output:
                mat_output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
                mat_output["bpsd_managed"] = True
                mat_output.location = (root_node.location.x + 300, root_node.location.y - 100)

            mat.node_tree.links.new(root_node.outputs['Out Shader'], mat_output.inputs['Surface'])

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

        ng = bpy.data.node_groups.get("BPSD_PSD_Output")
        if not ng:
            self.report({'ERROR'}, "PSD Node Group 'BPSD_PSD_Output' not found.")
            return {'CANCELLED'}

        stored_sig = ng.get("bpsd_structure_signature", "")
        if stored_sig != props.structure_signature:
            self.report({'WARNING'}, "Structure signature mismatch. Changes to hierarchy/masking require full regeneration.")

        layer_map = {item.layer_id: item for item in props.layer_list if item.layer_id > 0}

        target_interp = get_interpolation_mode(props)

        count = 0
        for node in ng.nodes:
            if node.type == 'TEX_IMAGE':
                 if node.interpolation != target_interp:
                     node.interpolation = target_interp
                     count += 1

            lid = node.get("bpsd_layer_id", 0)
            if lid > 0 and lid in layer_map:
                item = layer_map[lid]

                if node.type == 'FRAME':
                    if node.label != item.name:
                        node.label = item.name

                if node.type == 'MATH' and node.label == "* Opacity":
                     eff_opacity = item.opacity * (1.0 if get_effective_visibility(item) else 0.0)
                     if node.inputs[1].default_value != eff_opacity:
                        node.inputs[1].default_value = eff_opacity
                        count += 1

                if node.type == 'VALUE' and node.label == "Group Opacity":
                     eff_opacity = item.opacity * (1.0 if get_effective_visibility(item) else 0.0)
                     if node.outputs[0].default_value != eff_opacity:
                        node.outputs[0].default_value = eff_opacity
                        count += 1

                if node.type == 'MIX_RGB' or node.type == 'MIX':
                    if node.label.startswith("Mix "):
                         blender_mode = get_blender_blend_mode(item.blend_mode)

                         if hasattr(node, "blend_type") and node.blend_type != blender_mode:
                             node.blend_type = blender_mode
                             node.label = f"Mix {blender_mode}"
                             count += 1

        self.report({'INFO'}, f"Updated {count} nodes.")
        return {'FINISHED'}
