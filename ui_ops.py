import sys
import bpy
import os
import numpy as np
from . import psd_engine
import subprocess
import time

# --- HELPER ---
def tag_image(image, psd_path, layer_path, layer_index, is_mask=False, layer_id=0):
    image["psd_path"] = psd_path
    image["psd_layer_path"] = layer_path
    image["psd_layer_index"] = layer_index
    image["psd_is_mask"] = is_mask
    image["psd_layer_id"] = layer_id
    image["bpsd_managed"] = True

def find_loaded_image(psd_path, layer_index, is_mask, layer_id=0):
    """Returns the bpy.types.Image if it exists, else None."""
    for img in bpy.data.images:
        if img.get("psd_path") != psd_path: continue
        if img.get("psd_is_mask", False) != is_mask: continue

        # 1. Try ID Match
        if layer_id > 0:
            if img.get("psd_layer_id") == layer_id:
                return img

        # 2. Fallback to Index
        elif img.get("psd_layer_index") == layer_index:
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

def is_photoshop_file_unsaved(target_psd_path):
    """
    Asks Photoshop if the specific file has unsaved changes.
    Returns True (Unsaved), False (Clean/Closed), or None (Error).
    """
    current_dir = os.path.dirname(__file__)
    
    try:
        if sys.platform == 'win32':
            vbs_checker = os.path.join(current_dir, "check_status.vbs")
            if not os.path.exists(vbs_checker): return None
            
            # Run VBS and capture output
            # cscript.exe runs in console mode (allowing stdout capture)
            result = subprocess.check_output(
                ["cscript", "//Nologo", vbs_checker, target_psd_path], 
                encoding='utf-8'
            )
            return "TRUE" in result.strip()

        elif sys.platform == 'darwin':
            # AppleScript One-Liner
            # "modified" property returns boolean
            cmd = f'''
            tell application id "com.adobe.Photoshop"
                set targetPath to "{target_psd_path}"
                repeat with d in documents
                    if (posix path of (file path of d as alias)) is targetPath then
                        return modified of d
                    end if
                end repeat
            end tell
            '''
            result = subprocess.check_output(["osascript", "-e", cmd], encoding='utf-8')
            return "true" in result.lower()

    except Exception:
        # If Photoshop isn't running or script fails, assume safe to proceed
        return False
        
    return False


# --- SELECTION OPERATOR ---
class BPSD_OT_select_layer(bpy.types.Operator):
    bl_idname = "bpsd.select_layer"
    bl_label = "Select Layer"
    bl_description = "Select layer and show it in the Image Editor"
    bl_options = {'INTERNAL'}

    index: bpy.props.IntProperty()# type: ignore
    path: bpy.props.StringProperty()# type: ignore
    is_mask : bpy.props.BoolProperty()# type: ignore
    layer_id: bpy.props.IntProperty(default=0)# type: ignore

    def execute(self, context):
        props = context.scene.bpsd_props

        props.active_layer_index = self.index
        props.active_layer_path = self.path
        props.active_is_mask = self.is_mask

        existing_img = find_loaded_image(props.active_psd_path, self.index, self.is_mask, self.layer_id)

        if existing_img:
            focus_image_editor(context, existing_img)

        elif props.auto_load_on_select:
            bpy.ops.bpsd.load_layer(
                'EXEC_DEFAULT',
                layer_path=self.path,
                layer_id=self.layer_id
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
    layer_id: bpy.props.IntProperty(default=0)  # type: ignore

    def execute(self, context):
        # 1. Resolve Data
        props = context.scene.bpsd_props
        psd_path = props.active_psd_path
        is_mask = props.active_is_mask

        # If no path arg provided, use selected layer
        target_layer = self.layer_path if self.layer_path else props.active_layer_path
        # Note: If called without args, self.layer_id defaults to 0.
        # But usually we call it via select_layer which passes it.
        # If manual call, we might miss ID, but that falls back to path.

        if not psd_path or not target_layer:
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        # 2. Call Engine
        pixels, w, h = psd_engine.read_layer(psd_path, target_layer, props.psd_width, props.psd_height, fetch_mask=is_mask, layer_id=self.layer_id)

        # in photoshop, empty layers have zero pixels
        if pixels is None:
            self.report({'ERROR'}, "Failed to read layer.")
            return {'CANCELLED'}

        # 3. Create Image
        # Include layer index to disambiguate layers with identical names
        psd_name = props.active_psd_path.replace("\\", "/")
        psd_name = psd_name.split("/")[-1]
        layer_idx = props.active_layer_index
        # Get display name from layer list (target_layer is now an index path like "0/2")
        display_name = props.layer_list[layer_idx].name if layer_idx < len(props.layer_list) else target_layer
        layer_name = f"{psd_name}/{layer_idx:03d}_{display_name}"
        img_name = f"{layer_name}_MASK" if is_mask else layer_name

        if img_name in bpy.data.images:
            img = bpy.data.images[img_name]
            if img.size[0] != w or img.size[1] != h:
                img.scale(w, h)
        else:
            img = bpy.data.images.new(img_name, width=w, height=h, alpha=True)

        if len(pixels) > 0:
            img.pixels.foreach_set(pixels)

        tag_image(img, psd_path, target_layer, layer_idx, is_mask, self.layer_id)
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
        layer_id = img.get("psd_layer_id", 0)

        if not target_layer:
            self.report({'ERROR'}, "Image is not linked to a PSD layer.")
            return {'CANCELLED'}

        # Write
        pixels = np.array(img.pixels)
        w, h = img.size

        # we shouldn't write to GROUP or SMART, unless we're writing the mask...
        success = psd_engine.write_layer(psd_path, target_layer, pixels, w, h, is_mask=is_mask, layer_id=layer_id)

        if success:
            img.pack()
            self.report({'INFO'}, f"Saved {img.name}")

            # Also reload the main PSD image in Blender if it exists
            # (Since we wrote to the file, the composite might have changed)
            # props = context.scene.bpsd_props
            # if props.active_psd_image != 'NONE':
            #     main_img = bpy.data.images.get(props.active_psd_image)
            #     if main_img:
            #         main_img.reload()

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
            # I mean we can, just not really clear, hmm..
            if not img.is_dirty:
                continue
            
            layer_path = img.get("psd_layer_path")
            is_mask = img.get("psd_is_mask", False)
            layer_id = img.get("psd_layer_id", 0)

            if not layer_path: continue

            updates.append({
                'layer_path': layer_path,
                'pixels': np.array(img.pixels), # Accessing pixels is heavy, do it here
                'width': img.size[0],
                'height': img.size[1],
                'is_mask': is_mask,
                'layer_id': layer_id
            })

            processed_images.append(img)

        if not updates:
            self.report({'INFO'}, "No unsaved changes found.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Batch saving {len(updates)} layers...")
        success = psd_engine.write_all_layers(active_psd, updates,props.psd_width, props.psd_height)

        # we have to let photoshop save so we can reload
        # if os.path.exists(props.active_psd_path):
        #     props.last_known_mtime_str = str(os.path.getmtime(props.active_psd_path))
        
        if success:
            # Pack all images that were successfully saved
            for img in processed_images:
                try:
                    img.pack()
                except:
                    pass

            # Cleanup...
            if props.auto_refresh_ps:
                if is_photoshop_file_unsaved(props.active_psd_path):
                    self.report({'WARNING'}, "Saved to disk, but Photoshop refresh skipped (Unsaved changes in PS).")
                else:
                    run_photoshop_refresh(props.active_psd_path)
                    self.report({'INFO'}, "Saved & Refreshed Photoshop.")
            else:
                self.report({'INFO'}, "Saved to disk.")

            # Also reload the main PSD image in Blender if it exists
            # (In case the save operation modified the PSD structure/composite)
            # if props.active_psd_image != 'NONE':
            #     main_img = bpy.data.images.get(props.active_psd_image)
            #     if main_img:
            #         # time.sleep(.2)
            #         main_img.reload()

            return {'FINISHED'}

# --- PURGE OPERATOR ---
class BPSD_OT_clean_orphans(bpy.types.Operator):
    bl_idname = "bpsd.clean_orphans"
    bl_label = "Clean Unused Layers"
    bl_description = "Delete Blender images from the current PSD that no longer exist in the layer list"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path

        valid_paths = set()
        valid_ids = set()

        for item in props.layer_list:
            valid_paths.add(item.path)
            if item.layer_id > 0:
                valid_ids.add(item.layer_id)

        images_to_remove = []

        for img in bpy.data.images:
            if not img.get("bpsd_managed"):
                continue

            img_psd = img.get("psd_path")
            img_layer = img.get("psd_layer_path")
            img_id = img.get("psd_layer_id", 0)

            # Only clean images from the current active PSD
            if img_psd != active_psd:
                continue

            # Check if layer still exists
            keep = False
            if img_id > 0:
                if img_id in valid_ids:
                    keep = True
            else:
                # Fallback for legacy or ID-less layers
                if img_layer in valid_paths:
                    keep = True

            if not keep:
                images_to_remove.append(img)

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
            l_index = img.get("psd_layer_index")
            l_id = img.get("psd_layer_id", 0)
            is_mask = img.get("psd_is_mask", False)

            # --- REMAPPING LOGIC ---
            # If we have an ID, we try to find where this layer went in the new structure
            found_item = None
            if l_id > 0:
                for i, item in enumerate(props.layer_list):
                    if item.layer_id == l_id:
                        found_item = item
                        new_index = i
                        break

            # If we found it by ID, and the path/index changed, update the image metadata
            if found_item:
                if found_item.path != l_path or new_index != l_index:
                    print(f"BPSD: Remapping layer {l_path} -> {found_item.path}")

                    # Update Metadata
                    img["psd_layer_path"] = found_item.path
                    img["psd_layer_index"] = new_index

                    l_path = found_item.path
                    l_index = new_index

                    # Rename Image
                    psd_name = os.path.basename(active_psd)
                    new_name = f"{psd_name}/{l_index:03d}_{found_item.name}"
                    if is_mask: new_name += "_MASK"

                    if img.name != new_name:
                        try:
                            img.name = new_name
                        except:
                            pass # Name collision or something, not critical

            images_to_reload.append(img)
            requests.append({
                'layer_path': l_path,
                'layer_index': l_index,
                'width': img.size[0],
                'height': img.size[1],
                'is_mask': is_mask,
                'layer_id': l_id
            })

        if not requests:
            self.report({'INFO'}, "No layers to reload.")
            return {'CANCELLED'}

        # 2. Batch Read
        self.report({'INFO'}, f"Reloading {len(requests)} layers...")
        results = psd_engine.read_all_layers(active_psd, requests)

        if os.path.exists(props.active_psd_path):
            props.last_known_mtime_str = str(os.path.getmtime(props.active_psd_path))

        # 3. Update Blender Images
        success_count = 0
        for img in images_to_reload:
            key = (img.get("psd_layer_index"), img.get("psd_is_mask", False))

            if key in results:
                try:
                    img.pixels = results[key]
                    img.update()
                    img.pack() # Ensure data is saved
                    success_count += 1
                except Exception as e:
                    print(f"Failed to update image {img.name}: {e}")

        # 4. Reload the main PSD file if it's loaded in Blender
        if props.active_psd_image != 'NONE':
            main_img = bpy.data.images.get(props.active_psd_image)
            if main_img:
                main_img.reload()

        self.report({'INFO'}, f"Reloaded {success_count} layers.")
        return {'FINISHED'}