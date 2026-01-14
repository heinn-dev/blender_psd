import bpy
import os
from . import ui_ops

def get_icon(layer_type):
    match layer_type:
        case 'GROUP':
            return 'FILE_FOLDER'
        case 'SMART':
            return 'OUTLINER_DATA_LATTICE'
        case 'ADJUSTMENT':
            return 'CURVE_DATA'
        case 'UNKNOWN':
            return 'FILE'
    return 'IMAGE_DATA'

def draw_layer_item(layout, props, item, index, current_indent):
    split = layout.split(factor=0.75)
    row = split.row(align=True)
    vis_row = split.row(align=True)
    vis_row.alignment = 'RIGHT'

    if item.visibility_override != 'PSD':
        vis_row.alert = True

    is_active_row = (index == props.active_layer_index)

    ind = current_indent
    icon = get_icon(item.layer_type)
    
    if item.layer_type == "GROUP":
        ind -= 1

    effective_vis = item.is_visible
    if item.visibility_override == 'SHOW': effective_vis = True
    elif item.visibility_override == 'HIDE': effective_vis = False

    if item.hidden_by_parent:
        eye = "KEYFRAME"
    else:
        eye = "LAYER_ACTIVE" if effective_vis else "LAYER_USED"

    row.separator(factor=min(( max(ind + 2, 0) * 1.2), 8))
    row.alignment = 'LEFT'
    
    
    if item.is_clipping_mask:
        row.label(text='', icon = 'TRACKING_FORWARDS')

    # Determine display name
    display_name = item.name

    # Check for dirty state
    has_unsaved = False
    img_c = ui_ops.find_loaded_image(props.active_psd_path, index, False, item.layer_id)
    if img_c and img_c.is_dirty: has_unsaved = True

    if not has_unsaved and item.has_mask:
        img_m = ui_ops.find_loaded_image(props.active_psd_path, index, True, item.layer_id)
        if img_m and img_m.is_dirty: has_unsaved = True
        
    has_unsaved = has_unsaved or item.is_property_dirty

    if has_unsaved:
        display_name += " *"

    # if item.layer_type in {"GROUP", "ADJUSTMENT", "UNKNOWN"}:
    #     layer_sub = row.row(align=True)
    #     layer_sub.alignment = 'LEFT'
    #     op = layer_sub.operator( "bpsd.select_layer", text=display_name, icon=icon, emboss=False )
    #     op.index = index
    #     op.path = item.path
    #     op.layer_id = item.layer_id
    #     op.is_mask = False
    # else:
    layer_sub = row.row(align=True)
    layer_sub.alert = (is_active_row and not props.active_is_mask)
    layer_sub.alignment = 'LEFT'

    op = layer_sub.operator( "bpsd.select_layer", text=display_name, icon=icon, emboss=False )
    op.index = index
    op.path = item.path
    op.layer_id = item.layer_id
    op.is_mask = False

    if item.has_mask:
        mask_sub = row.row(align=True)
        mask_sub.alert = (is_active_row and props.active_is_mask)
        mask_sub.alignment = 'LEFT'

        op = mask_sub.operator( "bpsd.select_layer", icon='MOD_MASK', emboss=False, text="" )
        op.index = index
        op.path = item.path
        op.layer_id = item.layer_id
        op.is_mask = True
        
        

    op = vis_row.operator("bpsd.toggle_visibility", text="", icon=eye, emboss=False)
    op.index = index

def draw_layer_panel(layout, props, item):
    item = props.layer_list[props.active_layer_index]
    box = layout.box()

    icon = get_icon(item.layer_type)
    # row = box.row(align=True)
    # row.alignment = 'LEFT'
    # row = box.row()
    # row.label(text=f"{item.name}", icon=icon)
    
    col = box.column()
    
    row = col.row()
    row.scale_y = 0.8
    
    sub_row = row.row(align=True)
    sub_row.alignment = 'LEFT'
    sub_row.prop(item, "blend_mode", text="")
    sub_row.separator()
    # sub_row.enabled = False
    
    if item.layer_type == "LAYER":
        sub_row = row.row(align=True)
        sub_row.separator()
        sub_row.alignment = 'RIGHT'
        op = sub_row.operator("bpsd.load_layer", text="", icon='FILE_REFRESH')
        op.layer_path = props.layer_list[props.active_layer_index].path
        op.layer_id = props.active_layer_index
    
    row = col.row()
    # row.alignment = 'LEFT'
    row.prop(item, "opacity", text="Opacity", slider=True)
    row.scale_y = 0.8
    

class BPSD_PT_main_panel(bpy.types.Panel):
    bl_label = "Photoshop Sync"
    bl_idname = "BPSD_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpsd_props

        sync_col = layout.column(align=True)

        sync_col.prop(props, "active_psd_image", text="")
        is_valid = props.active_psd_image != "NONE" and props.active_psd_image in bpy.data.images

        is_already_synced = False
        if is_valid and props.active_psd_path and len(props.layer_list) > 0:
            img = bpy.data.images.get(props.active_psd_image)
            if img:
                selected_path = os.path.normpath(bpy.path.abspath(img.filepath))
                synced_path = os.path.normpath(props.active_psd_path)
                is_already_synced = (selected_path == synced_path)

        
        row = sync_col.row(align=True)
        button_text = "Reload from disk" if is_already_synced else "Sync file"
        row.operator("bpsd.connect_psd", icon='FILE_REFRESH', text=button_text)
        if is_already_synced:
            row.operator("bpsd.stop_sync", icon='X')
        row.enabled = is_valid
        
        sync_col.label(text=f"Synced: {os.path.basename(props.active_psd_path)}", icon='CHECKMARK')

        row = sync_col.row(align=True)
        row.prop(props, "auto_sync_incoming", text="Sync from PS", icon='UV_SYNC_SELECT' if props.auto_sync_incoming else 'CANCEL')
        row.prop(props, "auto_refresh_ps", text="Sync to PS", icon='UV_SYNC_SELECT' if props.auto_refresh_ps else 'CANCEL')
        row.enabled = is_valid


        if not is_valid: return
        if len(props.layer_list) == 0: return

        layout.separator()
        layout.label(text="Layers", icon ="RENDERLAYERS")

        root_box = layout.box()
        root_col = root_box.column(align=True)

        layout_stack = [root_col]
        current_indent = 0

        for i, item in enumerate(props.layer_list):

            if item.indent < current_indent:
                for _ in range(current_indent - item.indent):
                    if len(layout_stack) > 1:
                        layout_stack.pop()
                current_indent = item.indent

            parent_layout = layout_stack[-1]

            if item.layer_type == "GROUP":
                box = parent_layout.box()
                current_layout = box.column(align=True)
            else:
                current_layout = parent_layout

            draw_layer_item(current_layout, props, item, i, current_indent)

            if item.layer_type == "GROUP":
                layout_stack.append(current_layout)
                current_indent += 1

        if props.active_layer_index >= 0 and props.active_layer_index < len(props.layer_list):
            draw_layer_panel(layout, props, item)


        psd_name = props.active_psd_path.replace("\\", "/")
        psd_name = psd_name.split("/")[-1]
        
        row_hl = layout.box().row(align=True)
        row_hl.operator("bpsd.highlight_psd", text=f"{psd_name}", icon='IMAGE_DATA',emboss=False)
        
        # Check current state for icon/depress
        is_preview = False
        target_group_name = ui_ops.get_psd_group_name(props.active_psd_path)
        ng = bpy.data.node_groups.get(target_group_name)
        if ng:
             for node in ng.nodes:
                if node.get("bpsd_output_toggle"):
                    if node.inputs['Factor'].default_value > 0.5:
                        is_preview = True
                    break

        icon_toggle = 'HIDE_OFF' if is_preview else 'NODETREE'
        row_hl.operator("bpsd.toggle_output_mode", text="", icon=icon_toggle, depress=is_preview)


            
        layout.separator()

        row = layout.row(align=True)
        row.operator("bpsd.create_psd_nodes", icon='SHADING_RENDERED', text="Make Nodes")
        row.operator("bpsd.update_psd_nodes", icon='FILE_REFRESH', text="Update Nodes")

        icon_interp = 'ALIASED' if props.use_closest_interpolation else 'ANTIALIASED'
        row.prop(props, "use_closest_interpolation", text="", icon=icon_interp, toggle=True)

        row = layout.row(align=True)
        
        row.operator("bpsd.save_all_layers", text="Save", icon='FILE_TICK')
        row.prop(props, "auto_save_on_image_save", text="", icon='FILE_REFRESH' if props.auto_save_on_image_save else 'FILE_TICK', toggle=True)
        
        # has_dirty_props = False
        # for item in props.layer_list:
        #     if item.is_property_dirty:
        #         has_dirty_props = True
        #         break
        
        row.alert = props.ps_is_dirty or props.ps_disk_conflict
        warn = None
        if props.ps_is_dirty:
            warn = layout.column()
            row = warn.row(align=True)
            row.alert = True
            row.label(text="Photoshop has unsaved changes!", icon='ERROR')

        if props.ps_disk_conflict:
            warn = layout.column()
            row = warn.row(align=True)
            row.alert = True
            row.label(text="Disk file changed! Save will overwrite.", icon='ERROR')
            

        layout.separator()
        
        # layout.operator("bpsd.debug_rw_test", icon='FILE_REFRESH', text="Debug RW Test")


class BPSD_PT_layer_context(bpy.types.Panel):
    bl_label = "Debug"
    bl_idname = "BPSD_PT_layer_context"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'
    bl_parent_id = "BPSD_PT_main_panel"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.bpsd_props is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpsd_props

        has_active_layer = (props.active_layer_index >= 0 and
                            props.active_layer_index < len(props.layer_list) and
                            props.active_layer_path != "")

        col = layout.column()
        col.operator("bpsd.reload_all", text="Reload All Synced", icon='FILE_REFRESH')
        col.operator("bpsd.clean_orphans", text="Purge Old Layers", icon='TRASH')

        if has_active_layer:
            item = props.layer_list[props.active_layer_index]
            layout.label(text=f"Selected: {item.name}", icon='PREFERENCES')
        else:
            layout.label(text="Selected: None", icon='PREFERENCES')

        box = layout.box()
        box = box.row()
        box.enabled = has_active_layer

        row = box.row()
        op = row.operator("bpsd.load_layer", text="Force Load", icon='TEXTURE')
        if has_active_layer:
            op.layer_path = props.layer_list[props.active_layer_index].path

        row = box.row()
        op = row.operator("bpsd.save_layer", text="Force Save", icon='FILE_TICK')

        layout.separator()
        layout.label(text="Node Operations")

        col = layout.column()
        col.enabled = has_active_layer
        col.operator("bpsd.create_layer_node", icon='NODETREE')
        col.operator("bpsd.create_layer_frame", icon='FRAME_PREV')

        col = layout.column()
        col.operator("bpsd.create_group_nodes", icon='FILE_FOLDER')

        layout.separator()
        layout.operator("bpsd.debug_rw_test", icon='FILE_REFRESH', text="Debug RW Test")