import bpy
import os

class BPSD_PT_main_panel(bpy.types.Panel):
    bl_label = "Photoshop Sync"
    bl_idname = "BPSD_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpsd_props

        # 1. Connection Header
        sync_col = layout.column(align=True)

        # dropdown
        sync_col.prop(props, "active_psd_image", text="")
        # Check validity from dropdown selection directly (not just active_psd_path)
        is_valid = props.active_psd_image != "NONE" and props.active_psd_image in bpy.data.images

        # Check if dropdown selection matches currently synced file
        is_already_synced = False
        if is_valid and props.active_psd_path and len(props.layer_list) > 0:
            img = bpy.data.images.get(props.active_psd_image)
            if img:
                selected_path = os.path.normpath(bpy.path.abspath(img.filepath))
                synced_path = os.path.normpath(props.active_psd_path)
                is_already_synced = (selected_path == synced_path)

        # connect button (add disconnect too?)
        row = sync_col.row(align=True)
        button_text = "Reload from disk" if is_already_synced else "Sync file"
        row.operator("bpsd.connect_psd", icon='FILE_REFRESH', text=button_text)

        if is_already_synced:
            row.operator("bpsd.stop_sync", text="", icon='X')

        row.enabled = is_valid

        # Show currently synced file
        if props.active_psd_path and len(props.layer_list) > 0:
            sync_col.label(text=f"Synced: {os.path.basename(props.active_psd_path)}", icon='CHECKMARK')
        
        row = sync_col.row(align=True)
        row.prop(props, "auto_sync_incoming", text="Sync from PS", icon='FILE_REFRESH' if props.auto_sync_incoming else 'CANCEL')
        row.prop(props, "auto_refresh_ps", text="Sync to PS", icon='FILE_REFRESH' if props.auto_refresh_ps else 'CANCEL')
        row.enabled = is_valid

        
        if not is_valid: return
        if len(props.layer_list) == 0: return
        
        layout.separator()
        layout.label(text="Layers", icon ="RENDERLAYERS")

        root_box = layout.box()
        # Create an aligned column inside it (just like you do for groups)
        root_col = root_box.column(align=True) 

        # Start the stack with the aligned column
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

            row = current_layout.row(align=True)


            is_active_row = (i == props.active_layer_index)
            ind = current_indent

            if item.layer_type == "GROUP":
                icon = 'FILE_FOLDER'
                ind -= 1
            elif item.layer_type == "SMART":
                icon = 'OUTLINER_DATA_LATTICE'
            elif item.layer_type == "ADJUSTMENT":
                icon = 'CURVE_DATA'
            elif item.layer_type == "UNKNOWN":
                icon = 'FILE'
            else:
                icon = 'IMAGE_DATA'
                
                
            row.separator(factor=min(( max(ind + 2, 0) * 1.2), 8))
            row.alignment = 'LEFT'
            
            if item.is_clipping_mask:
                row.label(text='', icon = 'TRACKING_FORWARDS')
                        
            if item.layer_type in {"GROUP", "SMART", "ADJUSTMENT", "UNKNOWN"}:
                row.label(text=item.name, icon=icon)
            else:
                layer_sub = row.row(align=True)
                layer_sub.alert = (is_active_row and not props.active_is_mask)
                layer_sub.alignment = 'LEFT'

                op = layer_sub.operator( "bpsd.select_layer", text=item.name, icon=icon, emboss=False )
                op.index = i
                op.path = item.path
                op.is_mask = False

            if item.has_mask:
                mask_sub = row.row(align=True)
                mask_sub.alert = (is_active_row and props.active_is_mask)
                mask_sub.alignment = 'LEFT'

                op = mask_sub.operator( "bpsd.select_layer", icon='MOD_MASK', emboss=False, text="" ) #  text="Mask"
                op.index = i
                op.path = item.path
                op.is_mask = True

            if item.layer_type == "GROUP":
                layout_stack.append(current_layout)
                current_indent += 1
    
        psd_name = props.active_psd_path.replace("\\", "/")
        psd_name = psd_name.split("/")[-1]
        layout.box().operator("bpsd.highlight_psd", text=f"{psd_name}", icon='IMAGE_DATA',emboss=False)
        layout.separator()
        
        row = layout.row(align=True)
        row.operator("bpsd.save_all_layers", text="Save", icon='FILE_TICK')
        
        

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
        props = context.scene.bpsd_props
        return props.active_layer_index >= 0 and props.active_layer_path != ""

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpsd_props
        item = props.layer_list[props.active_layer_index]
        
        col = layout.column()
        col.operator("bpsd.reload_all", text="Reload All Synced", icon='FILE_REFRESH')
        col.operator("bpsd.clean_orphans", text="Purge Old Layers", icon='TRASH')
        
        layout.label(text=f"Selected: {item.name}", icon='PREFERENCES')
        
        box = layout.box()
        box = box.row()
        
        row = box.row()
        op = row.operator("bpsd.load_layer", text="Force Load", icon='TEXTURE')
        op.layer_path = item.path
        
        row = box.row()
        op = row.operator("bpsd.save_layer", text="Force Save", icon='FILE_TICK')