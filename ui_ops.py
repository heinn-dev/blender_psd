import bpy
import os
import numpy as np
from . import psd_engine

# --- HELPER ---
def tag_image(image, psd_path, layer_path, is_mask=False):
    image["psd_path"] = psd_path
    image["psd_layer_path"] = layer_path
    image["psd_is_mask"] = is_mask
    image["bpsd_managed"] = True 

def find_loaded_image(psd_path, layer_path, is_mask):
    """Returns the bpy.types.Image if it exists, else None."""
    for img in bpy.data.images:
        if (img.get("psd_path") == psd_path and 
            img.get("psd_layer_path") == layer_path and
            img.get("psd_is_mask", False) == is_mask):
            return img
    return None

def focus_image_editor(context, image):
    """Forces the active Image Editor to show the given image."""
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = image
            break
        
    ts = bpy.context.tool_settings.image_paint
    if ts.mode == "IMAGE":
        ts.canvas = image 

# --- SELECTION OPERATOR ---
class BPSD_OT_select_layer(bpy.types.Operator):
    bl_idname = "bpsd.select_layer"
    bl_label = "Select Layer"
    bl_description = "Select this layer and show it in the Image Editor"
    bl_options = {'INTERNAL'} 
    
    index: bpy.props.IntProperty()
    path: bpy.props.StringProperty()
    is_mask : bpy.props.BoolProperty()
    
    def execute(self, context):
        props = context.scene.bpsd_props
        
        props.active_layer_index = self.index
        props.active_layer_path = self.path
        props.active_is_mask = self.is_mask
        
        existing_img = find_loaded_image(props.active_psd_path, self.path, self.is_mask)
        
        if existing_img:
            focus_image_editor(context, existing_img)
            
        elif props.auto_load_on_select:
            bpy.ops.bpsd.load_layer(
                'EXEC_DEFAULT', 
                layer_path=self.path, 
            )
            # Note: The load_layer op handles the focusing itself upon completion.
            
        return {'FINISHED'}


# --- LOAD OPERATOR ---
class BPSD_OT_load_layer(bpy.types.Operator):
    bl_idname = "bpsd.load_layer"
    bl_label = "Load Layer"
    bl_description = "Load this PSD layer into a Blender Image"
    bl_options = {'REGISTER', 'UNDO'}

    layer_path: bpy.props.StringProperty()

    def execute(self, context):
        # 1. Resolve Data
        props = context.scene.bpsd_props
        psd_path = props.active_psd_path
        is_mask = props.active_is_mask
        
        # If no path arg provided, use selected layer
        target_layer = self.layer_path if self.layer_path else props.active_layer_path

        if not psd_path or not target_layer:
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        # 2. Call Engine
        pixels, w, h = psd_engine.read_layer(psd_path, target_layer, props.psd_width, props.psd_height, fetch_mask=is_mask)
        
        # in photoshop, empty layers have zero pixels
        if pixels is None:
            self.report({'ERROR'}, "Failed to read layer.")
            return {'CANCELLED'}

        # 3. Create Image
        # layer_name = target_layer.split("/")[-1]
        psd_name = props.active_psd_path.replace("\\", "/")
        psd_name = psd_name.split("/")[-1]
        layer_name = psd_name + "/" + target_layer
        img_name = f"{layer_name}_MASK" if is_mask else layer_name

        if img_name in bpy.data.images:
            img = bpy.data.images[img_name]
            if img.size[0] != w or img.size[1] != h:
                img.scale(w, h)
        else:
            img = bpy.data.images.new(img_name, width=w, height=h, alpha=True)

        if len(pixels) > 0:
            img.pixels.foreach_set(pixels)
            
        tag_image(img, psd_path, target_layer, is_mask)
        img.pack()

        # Colorspace
        img.colorspace_settings.name = 'Non-Color' if is_mask else 'sRGB'

        # 4. View It
        focus_image_editor(context, img)
        self.report({'INFO'}, f"Loaded: {img_name}")
        return {'FINISHED'}



# --- SAVE OPERATOR ---
class BPSD_OT_save_layer(bpy.types.Operator):
    bl_idname = "bpsd.save_layer"
    bl_label = "Save Layer"
    bl_description = "Write to PSD"

    # Optional overrides
    layer_path: bpy.props.StringProperty()
    image_name: bpy.props.StringProperty()

    def execute(self, context):
        # Try to find image to save
        img = None
        if self.image_name:
            img = bpy.data.images.get(self.image_name)
        else:
            # Default to active image in editor
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    img = area.spaces.active.image
                    break
        
        if not img:
            self.report({'ERROR'}, "No image found to save.")
            return {'CANCELLED'}

        # Get Metadata
        psd_path = img.get("psd_path", context.scene.bpsd_props.active_psd_path)
        target_layer = img.get("psd_layer_path", self.layer_path)
        is_mask = img.get("psd_is_mask", False)

        if not target_layer:
            self.report({'ERROR'}, "Image is not linked to a PSD layer.")
            return {'CANCELLED'}

        # Write
        pixels = np.array(img.pixels)
        w, h = img.size
        
        success = psd_engine.write_layer(psd_path, target_layer, pixels, w, h, is_mask=is_mask)

        if success:
            # img.is_dirty = False
            self.report({'INFO'}, f"Saved {img.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Write failed.")
            return {'CANCELLED'}

class BPSD_OT_save_all_layers(bpy.types.Operator):
    bl_idname = "bpsd.save_all_layers"
    bl_label = "Save All Modified"
    bl_description = "Save all managed textures that have unsaved changes to the PSD"

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path
        
        updates = []
        processed_images = [] # Keep track to clear dirty flags later

        # 1. Find candidates
        for img in bpy.data.images:
            # Must be part of this PSD
            if img.get("psd_path") != active_psd:
                continue
                
            # Must be marked as ours
            if not img.get("bpsd_managed"):
                continue
                
            # since we do not write to disk on alt-s, we can't do this for now...
            # if not img.is_dirty:
                # continue
            
            # Prepare Data Packet
            layer_path = img.get("psd_layer_path")
            is_mask = img.get("psd_is_mask", False)
            
            if not layer_path: continue

            updates.append({
                'layer_path': layer_path,
                'pixels': np.array(img.pixels), # Accessing pixels is heavy, do it here
                'width': img.size[0],
                'height': img.size[1],
                'is_mask': is_mask
            })
            
            processed_images.append(img)

        if not updates:
            self.report({'INFO'}, "No unsaved changes found.")
            return {'CANCELLED'}

        # 2. Call Engine
        self.report({'INFO'}, f"Batch saving {len(updates)} layers...")
        success = psd_engine.write_all_layers(active_psd, updates)

        # 3. Cleanup
        if success:
            for img in processed_images:
                img.reload() # Optional: Reloads to ensure hash sync, though usually not needed if pixels matched
            self.report({'INFO'}, "Successfully saved all layers.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Batch save failed. Check console.")
            return {'CANCELLED'}
        
class BPSD_OT_clean_orphans(bpy.types.Operator):
    bl_idname = "bpsd.clean_orphans"
    bl_label = "Clean Unused Layers"
    bl_description = "Delete Blender images that no longer match a layer in the current PSD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path
        
        # 1. Build a set of valid paths from the current UI list
        # We need to support both regular layers and masks
        valid_paths = set()
        for item in props.layer_list:
            valid_paths.add(item.path)
        
        images_to_remove = []
        
        # 2. Scan Blender Images
        for img in bpy.data.images:
            # Check if this image belongs to our system
            if not img.get("bpsd_managed"):
                continue
            
            img_psd = img.get("psd_path")
            img_layer = img.get("psd_layer_path")
            
            # Condition A: It belongs to a different PSD entirely (orphaned by file switch)
            if img_psd != active_psd:
                images_to_remove.append(img)
                continue
                
            # Condition B: It belongs to this PSD, but the layer path is gone
            if img_layer not in valid_paths:
                images_to_remove.append(img)
                continue
        
        # 3. Delete them
        count = len(images_to_remove)
        if count == 0:
            self.report({'INFO'}, "No orphaned layers found.")
            return {'CANCELLED'}
            
        for img in images_to_remove:
            bpy.data.images.remove(img)
            
        self.report({'INFO'}, f"Removed {count} orphaned images.")
        return {'FINISHED'}