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
        
        # 1. Update the UI List Selection
        props.active_layer_index = self.index
        props.active_layer_path = self.path
        props.active_is_mask = self.is_mask
        
        # 2. Attempt to find the matching image in Blender
        self.sync_image_editor(context, self.path)
        
        return {'FINISHED'}

    def sync_image_editor(self, context, layer_path):
        """Finds the specific Blender image (Layer or Mask) and displays it."""
        props = context.scene.bpsd_props
        current_psd = props.active_psd_path
        
        # What are we looking for?
        target_wants_mask = props.active_is_mask
        
        target_img = None
        
        for img in bpy.data.images:
            # 1. Check File and Layer Paths
            if (img.get("psd_path") != current_psd or 
                img.get("psd_layer_path") != layer_path):
                continue
            
            # 2. Check Type Match (Image vs Mask)
            # Default to False if tag is missing (assumes it's a color layer)
            img_is_mask = img.get("psd_is_mask", False)
            
            if img_is_mask == target_wants_mask:
                target_img = img
                break # Found the exact match
        
        # 3. Update the Editor
        if target_img:
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = target_img
                    
            # figure something out for materials too, maybe a switchable "active texture" texture
            # mat = bpy.context.object.active_material
            # slot = mat.texture_slots[mat.active_texture_index]
            # slot.texture = target_img
            ts = bpy.context.tool_settings.image_paint
            if ts.mode == "IMAGE":
                ts.canvas = target_img 

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
        self.focus_image_in_editor(context, img)
        self.report({'INFO'}, f"Loaded: {img_name}")
        return {'FINISHED'}

    def focus_image_in_editor(self, context, image):
        if context.active_object and context.active_object.type == 'MESH':
            bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
        
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = image
                break

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