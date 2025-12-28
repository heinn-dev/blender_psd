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
        row = layout.row(align=True)
        row.prop(props, "active_psd_path", text="")
        row.operator("bpsd.connect_psd", icon='FILE_REFRESH', text="")

        layout.separator()

        # 2. Nested Box Tree
        if len(props.layer_list) > 0:
            
            # Initialize the stack with the main layout
            layout_stack = [layout]
            current_indent = -1
            
            for i, item in enumerate(props.layer_list):
                
                # --- STACK LOGIC ---
                if item.indent > current_indent:
                    for _ in range(item.indent - current_indent):
                        box = layout_stack[-1].box()
                        col = box.column(align=True)
                        layout_stack.append(col)
                
                elif item.indent < current_indent:
                    for _ in range(current_indent - item.indent):
                        if len(layout_stack) > 1:
                            layout_stack.pop()

                current_indent = item.indent
                
                # --- DRAWING THE ITEM ---
                current_layout = layout_stack[-1]
                
                # Create the main row for this item line
                row = current_layout.row(align=True)
                row.alignment = 'LEFT'
                
                # Check if this is the active row
                is_active_row = (i == props.active_layer_index)
                
                # --- 1. Draw Layer/Group Name ---
                icon = 'FILE_FOLDER' if item.layer_type == 'GROUP' else 'IMAGE_DATA'
                
                if item.layer_type == "GROUP":
                    row.label(text=item.name, icon=icon)
                    row.alignment = 'LEFT'
                else:
                    # Create a sub-row just for the layer name button
                    # We highlight it ONLY if the row is active AND we are not looking at the mask
                    layer_sub = row.row(align=True)
                    layer_sub.alert = (is_active_row and not props.active_is_mask)
                    layer_sub.alignment = 'LEFT'
                    
                    op = layer_sub.operator("bpsd.select_layer", text=item.name, icon=icon, emboss=False)
                    op.index = i
                    op.path = item.path
                    op.is_mask = False # Clicking this sets mask mode to False
                
                # --- 2. Draw Mask Button (if exists) ---
                if item.has_mask:
                    # Create a sub-row just for the mask button
                    # Highlight ONLY if row is active AND we ARE looking at the mask
                    mask_sub = row.row(align=True)
                    mask_sub.alert = (is_active_row and props.active_is_mask)
                    mask_sub.alignment = 'RIGHT'
                    
                    op = mask_sub.operator("bpsd.select_layer", text="Mask", icon='MOD_MASK', emboss=False)
                    op.index = i
                    op.path = item.path
                    op.is_mask = True # Clicking this sets mask mode to True

class BPSD_PT_layer_context(bpy.types.Panel):
    bl_label = "Layer Operations"
    bl_idname = "BPSD_PT_layer_context"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'
    bl_parent_id = "BPSD_PT_main_panel" # Nest under main
    
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
        
        # Load Buttons
        row = box.row()
        op = row.operator("bpsd.load_layer", text="Load Texture", icon='TEXTURE')
        op.layer_path = item.path
        
        # Save Button (Explicit)
        row = box.row()
        op = row.operator("bpsd.save_layer", text="Force Save", icon='FILE_TICK')