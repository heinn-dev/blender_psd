import bpy
import numpy as np
from . import ui_ops

def get_temp_image_name(layer_item):
    return f"Temp_LayerID_{layer_item.layer_id}"

def ensure_temp_image(context, layer_item, width, height):
    name = get_temp_image_name(layer_item)
    img = bpy.data.images.get(name)
    if not img:
        img = bpy.data.images.new(name, width=width, height=height, alpha=True)
    else:
        if img.size[0] != width or img.size[1] != height:
            img.scale(width, height)
    
    # Tag for orphan cleanup
    props = context.scene.bpsd_props
    img["bpsd_managed"] = True
    img["bpsd_is_temp"] = True
    img["psd_path"] = props.active_psd_path
    img["psd_layer_id"] = layer_item.layer_id
    
    return img

class BPSD_OT_edit_channels(bpy.types.Operator):
    bl_idname = "bpsd.edit_channels"
    bl_label = "Edit Channels"
    bl_description = "Create a temporary texture to edit specific channels"
    
    def execute(self, context):
        props = context.scene.bpsd_props
        idx = props.active_layer_index
        if idx < 0: return {'CANCELLED'}
        item = props.layer_list[idx]
        
        # Get Source Image
        source_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
        if not source_img:
            # Try to load it automatically
            bpy.ops.bpsd.load_layer('EXEC_DEFAULT', layer_path=item.path, layer_id=item.layer_id)
            source_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
            
            if not source_img:
                self.report({'WARNING'}, "Layer image could not be loaded.")
                return {'CANCELLED'}
            
        width = source_img.size[0]
        height = source_img.size[1]
        
        # Create Temp Image
        temp_img = ensure_temp_image(context, item, width, height)
        
        arr = np.empty(width * height * 4, dtype=np.float32)
        source_img.pixels.foreach_get(arr)
        
        arr_reshaped = arr.reshape(-1, 4)
        
        is_only_alpha = item.temp_channel_a and not (item.temp_channel_r or item.temp_channel_g or item.temp_channel_b)
        is_only_rgb = not item.temp_channel_a and (item.temp_channel_r or item.temp_channel_g or item.temp_channel_b)
        
        if is_only_alpha:
            # Alpha Mask Mode: Visualize Alpha as Grayscale, force opaque
            # Copy Source Alpha to RGB
            alpha_data = arr_reshaped[:, 3].copy()
            arr_reshaped[:, 0] = alpha_data
            arr_reshaped[:, 1] = alpha_data
            arr_reshaped[:, 2] = alpha_data
            arr_reshaped[:, 3] = 1.0
        else:
            # Zero out unselected channels to allow clear editing?
            # If I want to edit Red, I usually want to see what is already there in Red.
            # But if G, B are unselected, maybe I should zero them so they don't distract?
            if not item.temp_channel_r: arr_reshaped[:, 0] = 0
            if not item.temp_channel_g: arr_reshaped[:, 1] = 0
            if not item.temp_channel_b: arr_reshaped[:, 2] = 0
            
            if is_only_rgb:
                 # Force Opaque so alpha doesn't interfere with color editing
                 arr_reshaped[:, 3] = 1.0
            # Else (Mixed Mode): Keep Source Alpha (already in arr)
        
        temp_img.pixels.foreach_set(arr.ravel())
        temp_img.pack() 
        
        # Focus on Temp Image
        ui_ops.focus_image_editor(context, temp_img)
        
        # Update State
        item.temp_channel_active = True
        
        # Update Nodes
        try:
            bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
        except:
            pass
        
        return {'FINISHED'}

class BPSD_OT_save_channels(bpy.types.Operator):
    bl_idname = "bpsd.save_channels"
    bl_label = "Save Channels"
    bl_description = "Merge changes back to the layer"
    
    def execute(self, context):
        props = context.scene.bpsd_props
        idx = props.active_layer_index
        item = props.layer_list[idx]
        
        source_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
        temp_img = bpy.data.images.get(get_temp_image_name(item))
        
        if not source_img or not temp_img:
             self.report({'ERROR'}, "Missing images.")
             # Force reset state to avoid getting stuck
             item.temp_channel_active = False
             try:
                 bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
             except:
                 pass
             return {'CANCELLED'}
             
        width = source_img.size[0]
        height = source_img.size[1]
        
        if temp_img.size[0] != width or temp_img.size[1] != height:
             self.report({'ERROR'}, "Dimension mismatch!")
             return {'CANCELLED'}
             
        # Read both
        source_arr = np.empty(width * height * 4, dtype=np.float32)
        source_img.pixels.foreach_get(source_arr)
        source_reshaped = source_arr.reshape(-1, 4)
        
        temp_arr = np.empty(width * height * 4, dtype=np.float32)
        temp_img.pixels.foreach_get(temp_arr)
        temp_reshaped = temp_arr.reshape(-1, 4)
        
        is_only_alpha = item.temp_channel_a and not (item.temp_channel_r or item.temp_channel_g or item.temp_channel_b)

        if is_only_alpha:
             # Read from Temp Red (visual representation of alpha) -> Write to Source A
             source_reshaped[:, 3] = temp_reshaped[:, 0] 
        else:
            # Write back selected channels
            if item.temp_channel_r: source_reshaped[:, 0] = temp_reshaped[:, 0]
            if item.temp_channel_g: source_reshaped[:, 1] = temp_reshaped[:, 1]
            if item.temp_channel_b: source_reshaped[:, 2] = temp_reshaped[:, 2]
            if item.temp_channel_a: source_reshaped[:, 3] = temp_reshaped[:, 3]
        
        source_img.pixels.foreach_set(source_arr.ravel())
        source_img.pack()
        # source_img.is_dirty = True # Read-only
        
        # Mark property dirty to trigger save pick-up
        item.is_bpsd_dirty = True
        
        # Cleanup
        item.temp_channel_active = False
        bpy.data.images.remove(temp_img)
        
        # Update Nodes
        try:
            bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
        except:
            pass
        
        # Focus back
        ui_ops.focus_image_editor(context, source_img)
        
        return {'FINISHED'}

class BPSD_OT_cancel_channels(bpy.types.Operator):
    bl_idname = "bpsd.cancel_channels"
    bl_label = "Cancel Channel Edit"
    bl_description = "Discard changes and return to normal mode"
    
    def execute(self, context):
        props = context.scene.bpsd_props
        idx = props.active_layer_index
        item = props.layer_list[idx]
        
        # Cleanup
        item.temp_channel_active = False
        
        name = get_temp_image_name(item)
        temp_img = bpy.data.images.get(name)
        if temp_img:
            bpy.data.images.remove(temp_img)
            
        # Update Nodes
        try:
            bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
        except:
            pass
        
        # Find original image
        source_img = ui_ops.find_loaded_image(props.active_psd_path, idx, False, item.layer_id)
        if source_img:
            ui_ops.focus_image_editor(context, source_img)
            
        return {'FINISHED'}
