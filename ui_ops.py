import sys
import bpy
import os
import numpy as np
from . import psd_engine
import tempfile
import subprocess

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
        

def run_photoshop_refresh(target_psd_path):
    current_dir = os.path.dirname(__file__)
    data_path = os.path.join(current_dir, "bpsd_target.txt")
    
    try:
        with open(data_path, "w", encoding="utf-8") as f:
            f.write(target_psd_path)
    except Exception as e:
        print(f"BPSD Error: {e}")
        return

    # 2. Select Runner based on OS
    if sys.platform == 'win32':
        runner = os.path.join(current_dir, "silent_runner.vbs")
        jsx_script = os.path.join(current_dir, "refresh.jsx")
        
        if os.path.exists(runner):
            subprocess.Popen(["wscript", runner, jsx_script])
            
    elif sys.platform == 'darwin':
        # --- MACOS (AppleScript / osascript) ---
        # Note: Mac doesn't need the intermediate runner file as much, 
        # but to keep parity we can use 'osascript' to run a line of code.
        
        jsx_script = os.path.join(current_dir, "refresh.jsx")
        
        # AppleScript command to run the JSX file without activating the app
        cmd = f'tell application id "com.adobe.Photoshop" to do javascript file "{jsx_script}"'
        subprocess.Popen(["osascript", "-e", cmd])
        
    else:
        print("Linux is not supported for Photoshop interop.")

# --- SELECTION OPERATOR ---
class BPSD_OT_select_layer(bpy.types.Operator):
    bl_idname = "bpsd.select_layer"
    bl_label = "Select Layer"
    bl_description = "Select this layer and show it in the Image Editor"
    bl_options = {'INTERNAL'} 
    
    index: bpy.props.IntProperty()# type: ignore
    path: bpy.props.StringProperty()# type: ignore
    is_mask : bpy.props.BoolProperty()# type: ignore
    
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

    layer_path: bpy.props.StringProperty()  # type: ignore

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
    layer_path: bpy.props.StringProperty()# type: ignore
    image_name: bpy.props.StringProperty()# type: ignore

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
        
        # we shouldn't write to GROUP or SMART, unless we're writing the mask...
        success = psd_engine.write_layer(psd_path, target_layer, pixels, w, h, is_mask=is_mask)

        if success:
            # img.is_dirty = False
            self.report({'INFO'}, f"Saved {img.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Write failed.")
            return {'CANCELLED'}

# --- SAVE ALL OPERATOR ---
class BPSD_OT_save_all_layers(bpy.types.Operator):
    bl_idname = "bpsd.save_all_layers"
    bl_label = "Save All Modified"
    bl_description = "Save all managed textures that have unsaved changes to the PSD"

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path
        
        updates = []
        processed_images = [] # Keep track to clear dirty flags later
        
        # we shouldn't write to GROUP or SMART, unless we're writing the mask...
        for img in bpy.data.images:
            if img.get("psd_path") != active_psd:
                continue
                
            if not img.get("bpsd_managed"):
                continue
                
            # since we do not write to disk on alt-s, we can't do this for now...
            # if not img.is_dirty:
                # continue
            
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

        self.report({'INFO'}, f"Batch saving {len(updates)} layers...")
        success = psd_engine.write_all_layers(active_psd, updates)

        if success:
            # for img in processed_images:
                # img.reload() # Optional: Reloads to ensure hash sync, though usually not needed if pixels matched
                
            if props.auto_refresh_ps:
                run_photoshop_refresh(props.active_psd_path)
                self.report({'INFO'}, "Saved & Triggered Photoshop Refresh.")
            else:
                self.report({'INFO'}, "Saved to disk.")
                
            self.report({'INFO'}, "Successfully saved all layers.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Batch save failed. Check console.")
            return {'CANCELLED'}

# --- PURGE OPERATOR ---
class BPSD_OT_clean_orphans(bpy.types.Operator):
    bl_idname = "bpsd.clean_orphans"
    bl_label = "Clean Unused Layers"
    bl_description = "Delete Blender images that no longer match a layer in the current PSD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path
        
        valid_paths = set()
        for item in props.layer_list:
            valid_paths.add(item.path)
        
        images_to_remove = []
        
        for img in bpy.data.images:
            if not img.get("bpsd_managed"):
                continue
            
            img_psd = img.get("psd_path")
            img_layer = img.get("psd_layer_path")
            
            if img_psd != active_psd:
                images_to_remove.append(img)
                continue
                
            if img_layer not in valid_paths:
                images_to_remove.append(img)
                continue
        
        count = len(images_to_remove)
        if count == 0:
            self.report({'INFO'}, "No orphaned layers found.")
            return {'CANCELLED'}
            
        for img in images_to_remove:
            bpy.data.images.remove(img)
            
        self.report({'INFO'}, f"Removed {count} orphaned images.")
        return {'FINISHED'}
    
class BPSD_OT_reload_all(bpy.types.Operator):
    bl_idname = "bpsd.reload_all"
    bl_label = "Reload Loaded Layers"
    bl_description = "Force re-read all currently loaded textures from the PSD"
    
    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path
        
        # 1. Identify which images need reloading
        images_to_reload = []
        requests = []
        
        for img in bpy.data.images:
            if img.get("psd_path") != active_psd: continue
            if not img.get("bpsd_managed"): continue
            
            # We use the existing image dimensions as the target
            # (Assuming the PSD canvas size hasn't changed. 
            # If it has, user should probably re-connect first to update props)
            l_path = img.get("psd_layer_path")
            is_mask = img.get("psd_is_mask", False)
            
            images_to_reload.append(img)
            requests.append({
                'layer_path': l_path,
                'width': img.size[0],
                'height': img.size[1],
                'is_mask': is_mask
            })
            
        if not requests:
            self.report({'INFO'}, "No layers to reload.")
            return {'CANCELLED'}
            
        # 2. Batch Read
        self.report({'INFO'}, f"Reloading {len(requests)} layers...")
        results = psd_engine.read_all_layers(active_psd, requests)
        
        # 3. Update Blender Images
        success_count = 0
        for img in images_to_reload:
            key = (img["psd_layer_path"], img.get("psd_is_mask", False))
            
            if key in results:
                try:
                    img.pixels = results[key]
                    img.update()
                    # Reset dirty flag since we just synced with disk
                    img.is_dirty = False 
                    success_count += 1
                except Exception as e:
                    print(f"Failed to update image {img.name}: {e}")
        
        self.report({'INFO'}, f"Reloaded {success_count} layers.")
        return {'FINISHED'}