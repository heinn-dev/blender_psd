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
            # The stack holds the current 'parent' layout to draw into
            layout_stack = [layout]
            current_indent = -1
            
            for i, item in enumerate(props.layer_list):
                
                # --- STACK LOGIC (Simulated Recursion) ---
                
                # If this item is deeper than the previous one, open new boxes
                if item.indent > current_indent:
                    for _ in range(item.indent - current_indent):
                        # Create a box inside the current top of stack
                        box = layout_stack[-1].box()
                        # Make a column inside that box so items align nicely
                        col = box.column(align=True)
                        layout_stack.append(col)
                
                # If this item is shallower, pop back up the stack
                elif item.indent < current_indent:
                    for _ in range(current_indent - item.indent):
                        if len(layout_stack) > 1:
                            layout_stack.pop()

                # Update tracker
                current_indent = item.indent
                
                # --- DRAWING THE ITEM ---
                
                # Draw into whatever is currently at the top of the stack
                current_layout = layout_stack[-1]
                
                # if we are a mask, we draw onto layout_stack[-2]
                
                row = current_layout.row(align=True)
                row.alignment = 'LEFT'
                
                # Selection Highlight
                if i == props.active_layer_index:
                    row = row.row(align=True) # Nested row for cleanly applying alert
                    row.alignment = 'LEFT'
                    row.alert = True
                
                # Icon Logic
                icon = 'FILE_FOLDER' if item.layer_type == 'GROUP' else 'IMAGE_DATA'
                
                # Draw Selector Button
                # Note: We use item.name here, not display_name, 
                # because the boxes provide the visual structure now.
                if item.layer_type == "GROUP":
                    row.label(text=item.name, icon=icon)
                else:
                    op = row.operator("bpsd.select_layer", text=item.name, icon=icon, emboss=False)
                    op.index = i
                    op.path = item.path
                
                if item.has_mask:
                    op = row.operator("bpsd.select_layer", text="Mask", icon='MOD_MASK', emboss=False)
                    op.index = i
                    op.is_mask = True
                    op.path = item.path

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
        op.load_mask = False
        
        # Save Button (Explicit)
        row = box.row()
        op = row.operator("bpsd.save_layer", text="Force Save", icon='FILE_TICK')
        op.layer_path = item.path