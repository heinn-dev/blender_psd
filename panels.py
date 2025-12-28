import bpy

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
        col = layout.column(align=True)
        row = col.row(align=True)
        
        # A. The Dropdown (ALWAYS ENABLED)
        # We draw this directly into the main row
        row.prop(props, "active_psd_image", text="") 
        
        # B. The Connect Button (CONDITIONALLY ENABLED)
        # We check if we have a valid path
        is_valid = (props.active_psd_path != "")
        # Create a sub-layout inside the row just for the button.
        # This keeps the visual alignment (stuck together) but isolates the 'enabled' state.
        sub = row.row(align=True)
        sub.enabled = is_valid
        sub.operator("bpsd.connect_psd", icon='FILE_REFRESH', text="Sync this file")
        row.prop(props, "auto_sync_incoming", text="", icon='FILE_REFRESH' if props.auto_sync_incoming else 'CANCEL')

        # Optional: Debug Path Label
        if is_valid:
            col.label(text=f"Path: {props.active_psd_path}", icon='FILE_FOLDER')

        if len(props.layer_list) > 0:
            col = layout.column(align=True)
            
            row = col.row(align=True)
            row.operator("bpsd.save_all_layers", text="Save All Changes", icon='FILE_TICK')
            
            row.prop(props, "auto_refresh_ps", text="", icon='FILE_REFRESH')
            row.operator("bpsd.reload_all", text="Reload All", icon='FILE_REFRESH')
            
            row = col.row(align=True)
            row.operator("bpsd.clean_orphans", text="Purge Old Layers", icon='TRASH')
            
        layout.separator()
        layout.label(text="Layers", icon ="RENDERLAYERS")
        layout.separator()

        if len(props.layer_list) == 0:
            return

        layout_stack = [layout]
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
            row.alignment = 'LEFT'

            is_active_row = (i == props.active_layer_index)

            if item.layer_type == "GROUP":
                icon = 'FILE_FOLDER'
            elif item.layer_type == "SMART":
                icon = 'OUTLINER_DATA_LATTICE'
            else:
                icon = 'IMAGE_DATA'

            if item.layer_type in {"GROUP", "SMART"}:
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

                op = mask_sub.operator( "bpsd.select_layer", text="Mask", icon='MOD_MASK', emboss=False )
                op.index = i
                op.path = item.path
                op.is_mask = True

            if item.layer_type == "GROUP":
                layout_stack.append(current_layout)
                current_indent += 1

class BPSD_PT_layer_context(bpy.types.Panel):
    bl_label = "Layer Operations"
    bl_idname = "BPSD_PT_layer_context"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'
    bl_parent_id = "BPSD_PT_main_panel"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.bpsd_props
        return props.active_layer_index >= 0 and props.active_layer_path != ""

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpsd_props
        item = props.layer_list[props.active_layer_index]
        
        layout.label(text=f"Selected: {item.name}", icon='PREFERENCES')
        
        box = layout.box()
        
        row = box.row()
        op = row.operator("bpsd.load_layer", text="Force Load", icon='TEXTURE')
        op.layer_path = item.path
        
        row = box.row()
        op = row.operator("bpsd.save_layer", text="Force Save", icon='FILE_TICK')