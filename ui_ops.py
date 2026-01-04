import sys
import bpy
import os
import numpy as np
from . import psd_engine
import subprocess
import time

# --- CACHE & WATCHER ---
DIRTY_STATE_CACHE = {}

def init_dirty_cache():
    DIRTY_STATE_CACHE.clear()
    # for img in bpy.data.images:
        # DIRTY_STATE_CACHE[img.name] = img.is_dirty

def image_dirty_watcher():
    context = bpy.context
    if not hasattr(context, "scene") or not context.scene:
        return 1

    props = context.scene.bpsd_props

    images_to_save = []
    for img in bpy.data.images:
        if not img.get("bpsd_managed"):
            continue

        current_dirty = img.is_dirty
        was_dirty = DIRTY_STATE_CACHE.get(img.name, False)
        DIRTY_STATE_CACHE[img.name] = current_dirty

        # Transition: Dirty -> Clean (User Saved)
        if was_dirty and not current_dirty:
            if props.auto_save_on_image_save:
                images_to_save.append(img.name)

    if images_to_save:
        def trigger_saves():
            for name in images_to_save:
                # print(f"BPSD: Detected save on {name}, syncing to PSD...")
                try:
                    bpy.ops.bpsd.save_layer('EXEC_DEFAULT', image_name=name)
                except Exception as e:
                    print(f"BPSD Auto-Save Error: {e}")
            return None
        bpy.app.timers.register(trigger_saves, first_interval=0.01)

    return 1

# --- HELPER ---
def tag_image(image, psd_path, layer_path, layer_index, is_mask=False, layer_id=0):
    image["psd_path"] = psd_path
    image["psd_layer_path"] = layer_path
    image["psd_layer_index"] = layer_index
    image["psd_is_mask"] = is_mask
    image["psd_layer_id"] = layer_id
    image["bpsd_managed"] = True

def find_loaded_image(psd_path, layer_index, is_mask, layer_id=0):
    for img in bpy.data.images:
        if img.get("psd_path") != psd_path: continue
        if img.get("psd_is_mask", False) != is_mask: continue

        # 1. Try ID Match
        # if layer_id > 0:
        if img.get("psd_layer_id") == layer_id:
            return img

        # 2. Fallback to Index
        elif img.get("psd_layer_index") == layer_index:
            return img

    return None

def focus_image_editor(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = image
            break
        
    ts = bpy.context.tool_settings.image_paint
    if ts.mode == "IMAGE":
        ts.canvas = image 
        

def run_photoshop_refresh(target_psd_path):
    current_dir = os.path.join(os.path.dirname(__file__), "interop")
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
    current_dir = os.path.join(os.path.dirname(__file__), "interop")

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
            scpt_checker = os.path.join(current_dir, "check_status.scpt")
            if not os.path.exists(scpt_checker): return None

            result = subprocess.check_output(
                ["osascript", scpt_checker, target_psd_path],
                encoding='utf-8'
            )
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


# --- SAVE HELPER ---
def perform_save_images(context, psd_path, images):
    """
    Shared logic to save a list of Blender images back to a PSD file.
    Returns (status_set, message_string).
    """
    props = context.scene.bpsd_props

    updates = []
    valid_images = []

    for img in images:
        # Basic validation
        layer_path = img.get("psd_layer_path")
        is_mask = img.get("psd_is_mask", False)
        layer_id = img.get("psd_layer_id", 0)

        # If passed via save_layer (single), we might have loose requirements,
        # but generally we need a layer path.
        if not layer_path:
            continue

        updates.append({
            'layer_path': layer_path,
            'pixels': np.array(img.pixels),
            'width': img.size[0],
            'height': img.size[1],
            'is_mask': is_mask,
            'layer_id': layer_id
        })
        valid_images.append(img)

    if not updates:
        return {'CANCELLED'}, "No valid images to save."

    # Determine Canvas Size from the first valid image
    # This ensures that even if props are out of sync, we match the actual image data we are sending.
    # This preserves the behavior of the original save_layer which used img.size.
    canvas_w = updates[0]['width']
    canvas_h = updates[0]['height']

    # Perform the write
    # We use the inferred canvas size from the images to prevent reshape errors.
    success = psd_engine.write_all_layers(psd_path, updates, canvas_w, canvas_h)

    if success:
        # Pack and update cache
        for img in valid_images:
            try:
                img.pack()
                DIRTY_STATE_CACHE[img.name] = False
            except Exception as e:
                print(f"Error packing {img.name}: {e}")

        # Photoshop Refresh
        msg = "Saved to disk."
        status = {'FINISHED'}

        if props.auto_refresh_ps:
            # check if we are saving to the active PSD to run the refresh
            # (If saving an image from another PSD, we might not want to refresh the active one?
            #  But usually we only work on one.)
            if is_photoshop_file_unsaved(psd_path):
                msg = "Saved to disk, but Photoshop refresh skipped (Unsaved changes in PS)."
                status = {'WARNING'} # Or just INFO with warning msg
            else:
                run_photoshop_refresh(psd_path)
                msg = "Saved & Refreshed Photoshop."

        return status, msg

    return {'CANCELLED'}, "Write failed."


# --- SAVE OPERATOR ---
class BPSD_OT_save_layer(bpy.types.Operator):
    bl_idname = "bpsd.save_layer"
    bl_label = "Save Layer"
    bl_description = "Write to PSD"
    bl_options = {'REGISTER'}

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

        # Handle manual override case
        if not img.get("psd_layer_path") and self.layer_path:
            img["psd_layer_path"] = self.layer_path

        if not img.get("psd_layer_path"):
            self.report({'ERROR'}, "Image is not linked to a PSD layer.")
            return {'CANCELLED'}

        status, msg = perform_save_images(context, psd_path, [img])

        if 'CANCELLED' in status:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        elif 'WARNING' in status:
            self.report({'WARNING'}, msg)
            return {'FINISHED'}
        else:
            self.report({'INFO'}, msg)
            return {'FINISHED'}

# --- SAVE ALL OPERATOR ---
class BPSD_OT_save_all_layers(bpy.types.Operator):
    bl_idname = "bpsd.save_all_layers"
    bl_label = "Save All Modified"
    bl_description = "Save all managed textures that have unsaved changes to the PSD"

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path

        images_to_save = []

        for img in bpy.data.images:
            if img.get("psd_path") != active_psd:
                continue

            if not img.get("bpsd_managed"):
                continue

            if not img.is_dirty:
                continue

            if not img.get("psd_layer_path"):
                continue

            images_to_save.append(img)

        if not images_to_save:
            self.report({'INFO'}, "No unsaved changes found.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Batch saving {len(images_to_save)} layers...")

        status, msg = perform_save_images(context, active_psd, images_to_save)

        if 'CANCELLED' in status:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        elif 'WARNING' in status:
            self.report({'WARNING'}, msg)
            return {'FINISHED'}
        else:
            self.report({'INFO'}, msg)
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

            if img_psd != active_psd:
                continue

            keep = False
            if img_id > 0:
                if img_id in valid_ids:
                    keep = True
            else:
                if img_layer in valid_paths:
                    keep = True

            if not keep:
                images_to_remove.append(img)

        count = len(images_to_remove)
        if count == 0:
            # self.report({'INFO'}, "No orphaned layers found.")
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

        images_to_reload = []
        requests = []

        for img in bpy.data.images:
            if img.get("psd_path") != active_psd: continue
            if not img.get("bpsd_managed"): continue

            l_path = img.get("psd_layer_path")
            l_index = img.get("psd_layer_index")
            l_id = img.get("psd_layer_id", 0)
            is_mask = img.get("psd_is_mask", False)

            found_item = None
            if l_id > 0:
                for i, item in enumerate(props.layer_list):
                    if item.layer_id == l_id:
                        found_item = item
                        new_index = i
                        break

            if found_item:
                if found_item.path != l_path or new_index != l_index:
                    print(f"BPSD: Remapping layer {l_path} -> {found_item.path}")

                    img["psd_layer_path"] = found_item.path
                    img["psd_layer_index"] = new_index

                    l_path = found_item.path
                    l_index = new_index

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

        if props.active_psd_image != 'NONE':
            main_img = bpy.data.images.get(props.active_psd_image)
            if main_img:
                main_img.reload()

        self.report({'INFO'}, f"Reloaded {success_count} layers.")
        return {'FINISHED'}

class BPSD_OT_toggle_visibility(bpy.types.Operator):
    bl_idname = "bpsd.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Override visibility (Click to toggle HIDE/SHOW, Shift-Click to reset to PSD)"

    index: bpy.props.IntProperty() # type: ignore

    def invoke(self, context, event):
        props = context.scene.bpsd_props
        item = props.layer_list[self.index]

        if event.shift:
            item.visibility_override = 'PSD'
        else:
            # Simple Toggle Logic relative to current effective state

            # If currently syncing (PSD)
            if item.visibility_override == 'PSD':
                # If currently visible -> Force Hide
                if item.is_visible and not item.hidden_by_parent:
                    item.visibility_override = 'HIDE'
                # If currently hidden -> Force Show
                else:
                    item.visibility_override = 'SHOW'

            # If currently Force Hiding -> Force Show
            elif item.visibility_override == 'HIDE':
                 item.visibility_override = 'SHOW'

            # If currently Force Showing -> Force Hide
            elif item.visibility_override == 'SHOW':
                 item.visibility_override = 'HIDE'

        # Trigger node update to reflect visibility changes immediately
        try:
            bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
        except Exception:
            # If the node group doesn't exist or operator fails, we just ignore it
            pass

        return {'FINISHED'}


class BPSD_OT_load_all_layers(bpy.types.Operator):
    bl_idname = "bpsd.load_all_layers"
    bl_label = "Load All Layers"
    bl_description = "Load textures for all layers in the list"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path

        requests = []

        # Identify which layers need loading
        for i, item in enumerate(props.layer_list):
            if item.layer_type in ["GROUP", "ADJUSTMENT", "UNKNOWN"]:
                continue

            # Color
            requests.append({
                'layer_path': item.path,
                'layer_index': i,
                'width': props.psd_width,
                'height': props.psd_height,
                'is_mask': False,
                'layer_id': item.layer_id
            })

            # Mask
            if item.has_mask:
                 requests.append({
                    'layer_path': item.path,
                    'layer_index': i,
                    'width': props.psd_width,
                    'height': props.psd_height,
                    'is_mask': True,
                    'layer_id': item.layer_id
                })

        if not requests:
            self.report({'INFO'}, "No layers to load.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Loading {len(requests)} textures...")
        results = psd_engine.read_all_layers(active_psd, requests)

        count = 0
        psd_name = os.path.basename(active_psd)

        for (idx, is_mask), pixels in results.items():
            # Create or Get Image
            if idx >= len(props.layer_list): continue
            item = props.layer_list[idx]

            # Naming convention from load_layer
            display_name = item.name
            layer_name = f"{psd_name}/{idx:03d}_{display_name}"
            img_name = f"{layer_name}_MASK" if is_mask else layer_name

            img = bpy.data.images.get(img_name)
            if not img:
                 img = bpy.data.images.new(img_name, width=props.psd_width, height=props.psd_height, alpha=True)

            # Resize if needed
            if img.size[0] != props.psd_width or img.size[1] != props.psd_height:
                img.scale(props.psd_width, props.psd_height)

            if len(pixels) > 0:
                img.pixels.foreach_set(pixels)

            # Tag it
            tag_image(img, active_psd, item.path, idx, is_mask, item.layer_id)
            img.pack()

            # Colorspace
            img.colorspace_settings.name = 'Non-Color' if is_mask else 'sRGB'

            count += 1

        self.report({'INFO'}, f"Loaded {count} images.")
        return {'FINISHED'}
