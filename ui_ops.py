import sys
import bpy
import os
import numpy as np
import photoshopapi as psapi
from . import psd_engine
import subprocess
import time

class BPSD_RuntimeState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BPSD_RuntimeState, cls).__new__(cls)
            cls._instance.dirty_cache = {}
        return cls._instance

    def clear(self):
        self.dirty_cache.clear()

    def get_dirty(self, image_name):
        return self.dirty_cache.get(image_name, False)

    def set_dirty(self, image_name, is_dirty):
        self.dirty_cache[image_name] = is_dirty

runtime_state = BPSD_RuntimeState()

def init_dirty_cache():
    runtime_state.clear()

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
        was_dirty = runtime_state.get_dirty(img.name)
        runtime_state.set_dirty(img.name, current_dirty)

        if was_dirty and not current_dirty:
            if props.auto_save_on_image_save:
                images_to_save.append(img.name)

    if images_to_save:
        def trigger_saves():
            for name in images_to_save:
                try:
                    bpy.ops.bpsd.save_layer('EXEC_DEFAULT', image_name=name)
                except Exception as e:
                    print(f"BPSD Auto-Save Error: {e}")
            return None
        bpy.app.timers.register(trigger_saves, first_interval=0.01)

    return 1

def tag_image(image, psd_path, layer_path, layer_index, is_mask=False, layer_id=0):
    image["psd_path"] = psd_path
    image["psd_layer_path"] = layer_path
    image["psd_layer_index"] = layer_index
    image["psd_is_mask"] = is_mask
    image["psd_layer_id"] = layer_id
    image["bpsd_managed"] = True

def get_psd_group_name(psd_path):
    if not psd_path: return "BPSD_PSD_Output"
    name = os.path.basename(psd_path)
    return f"PSD: {name}"

def find_loaded_image(psd_path, layer_index, is_mask, layer_id=0):
    for img in bpy.data.images:
        if img.get("psd_path") != psd_path: continue
        if img.get("psd_is_mask", False) != is_mask: continue

        if img.get("psd_layer_id") == layer_id:
            return img

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
    elif ts.mode == "MATERIAL":
        obj = context.active_object
        if obj and obj.active_material and obj.active_material.use_nodes:
            mat = obj.active_material
            nodes = mat.node_tree.nodes

            target_node = None
            target_tree = nodes

            for node in nodes:
                if node.type == 'TEX_IMAGE' and node.image == image:
                    target_node = node
                    break

            if not target_node:
                p_path = image.get("psd_path")
                if not p_path:
                     p_path = bpy.path.abspath(image.filepath)

                target_group_name = get_psd_group_name(p_path)
                ng = bpy.data.node_groups.get(target_group_name)
                if ng:
                    for node in ng.nodes:
                        if node.type == 'TEX_IMAGE' and node.image == image:
                            target_node = node
                            target_tree = ng.nodes
                            break

            if target_node:
                target_tree.active = target_node
                target_node.select = True


def run_photoshop_refresh(target_psd_path):
    current_dir = os.path.join(os.path.dirname(__file__), "interop")
    data_path = os.path.join(current_dir, "bpsd_target.txt")

    try:
        with open(data_path, "w", encoding="utf-8") as f:
            f.write(target_psd_path)
    except Exception as e:
        print(f"BPSD Error: {e}")
        return

    if sys.platform == 'win32':
        runner = os.path.join(current_dir, "silent_runner.vbs")
        jsx_script = os.path.join(current_dir, "refresh.jsx")

        if os.path.exists(runner):
            subprocess.Popen(["wscript", runner, jsx_script])

    elif sys.platform == 'darwin':
        jsx_script = os.path.join(current_dir, "refresh.jsx")

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
        return False

    return False


class BPSD_OT_select_layer(bpy.types.Operator):
    bl_idname = "bpsd.select_layer"
    bl_label = "Select Layer"
    bl_description = "Select layer and show it in the Image Editor"
    bl_options = {'INTERNAL'}

    index: bpy.props.IntProperty() # type: ignore
    path: bpy.props.StringProperty() # type: ignore
    is_mask : bpy.props.BoolProperty() # type: ignore
    layer_id: bpy.props.IntProperty(default=0) # type: ignore

    def execute(self, context):
        props = context.scene.bpsd_props

        props.active_layer_index = self.index
        props.active_layer_path = self.path
        props.active_is_mask = self.is_mask

        item = props.layer_list[self.index] if self.index < len(props.layer_list) else None
        if item and item.layer_type == 'SMART' and not self.is_mask:
            self.report({'WARNING'}, "Smart Object layers cannot be saved back to the PSD")

        existing_img = find_loaded_image(props.active_psd_path, self.index, self.is_mask, self.layer_id)

        if existing_img:
            focus_image_editor(context, existing_img)

        elif props.auto_load_on_select:
            bpy.ops.bpsd.load_layer(
                'EXEC_DEFAULT',
                layer_path=self.path,
                layer_id=self.layer_id
            )

        return {'FINISHED'}


class BPSD_OT_load_layer(bpy.types.Operator):
    bl_idname = "bpsd.load_layer"
    bl_label = "Load Layer"
    bl_description = "Load this PSD layer into a Blender Image"
    bl_options = {'REGISTER', 'UNDO'}

    layer_path: bpy.props.StringProperty() # type: ignore
    layer_id: bpy.props.IntProperty(default=0) # type: ignore

    def execute(self, context):
        props = context.scene.bpsd_props
        psd_path = props.active_psd_path
        is_mask = props.active_is_mask

        target_layer = self.layer_path if self.layer_path else props.active_layer_path

        if not psd_path or not target_layer:
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        pixels, w, h = psd_engine.read_layer(psd_path, target_layer, props.psd_width, props.psd_height, fetch_mask=is_mask, layer_id=self.layer_id)

        if pixels is None:
            self.report({'ERROR'}, "Failed to read layer.")
            return {'CANCELLED'}

        layer_idx = props.active_layer_index
        img = find_loaded_image(psd_path, layer_idx, is_mask, self.layer_id)

        if not img:
            psd_name = props.active_psd_path.replace("\\", "/")
            psd_name = psd_name.split("/")[-1]

            display_name = props.layer_list[layer_idx].name if layer_idx < len(props.layer_list) else target_layer
            layer_name = f"{psd_name}/{layer_idx:03d}_{display_name}"
            img_name = f"{layer_name}_MASK" if is_mask else layer_name

            img = bpy.data.images.new(img_name, width=w, height=h, alpha=True)

        if img.size[0] != w or img.size[1] != h:
            img.scale(w, h)

        if len(pixels) > 0:
            img.pixels.foreach_set(pixels)

        tag_image(img, psd_path, target_layer, layer_idx, is_mask, self.layer_id)
        img.pack()

        img.colorspace_settings.name = 'Non-Color' if is_mask else 'sRGB'

        focus_image_editor(context, img)
        self.report({'INFO'}, f"Loaded: {img_name}")
        return {'FINISHED'}


def perform_save_images(context, psd_path, images):
    props = context.scene.bpsd_props

    updates = []
    valid_images = []

    for img in images:
        layer_path = img.get("psd_layer_path")
        is_mask = img.get("psd_is_mask", False)
        layer_id = img.get("psd_layer_id", 0)

        if not layer_path:
            continue

        item = None
        if layer_id > 0:
            for it in props.layer_list:
                if it.layer_id == layer_id:
                    item = it
                    break

        if item and item.layer_type == 'SMART' and not is_mask:
            print(f"Skipping save for Smart Object content: {item.name}")
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
        return {'CANCELLED'}, "No images to save."

    canvas_w = updates[0]['width']
    canvas_h = updates[0]['height']

    success = psd_engine.write_all_layers(psd_path, updates, canvas_w, canvas_h)

    if success:
        if os.path.exists(psd_path):
            props.last_known_mtime_str = str(os.path.getmtime(psd_path))
            props.ps_disk_conflict = False

        for img in valid_images:
            try:
                img.pack()
                runtime_state.set_dirty(img.name, False)
            except Exception as e:
                print(f"Error packing {img.name}: {e}")

        msg = "Saved to disk."
        status = {'FINISHED'}

        if props.auto_refresh_ps:
            if is_photoshop_file_unsaved(psd_path):
                msg = "Saved to disk, but Photoshop refresh skipped (Unsaved changes in PS)."
                status = {'WARNING'}
            else:
                run_photoshop_refresh(psd_path)
                msg = "Saved & Refreshed Photoshop."

        return status, msg

    return {'CANCELLED'}, "Write failed."


class BPSD_OT_save_layer(bpy.types.Operator):
    bl_idname = "bpsd.save_layer"
    bl_label = "Save Layer"
    bl_description = "Write to PSD"
    bl_options = {'REGISTER'}

    layer_path: bpy.props.StringProperty() # type: ignore
    image_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        img = None
        if self.image_name:
            img = bpy.data.images.get(self.image_name)
        else:
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    img = area.spaces.active.image
                    break

        if not img:
            self.report({'ERROR'}, "No image found to save.")
            return {'CANCELLED'}

        psd_path = img.get("psd_path", context.scene.bpsd_props.active_psd_path)

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

class BPSD_OT_save_all_layers(bpy.types.Operator):
    bl_idname = "bpsd.save_all_layers"
    bl_label = "Save All Modified"
    bl_description = "Save all managed textures that have unsaved changes to the PSD (Shift-click to force save all)"

    force: bpy.props.BoolProperty(default=False) # type: ignore

    def invoke(self, context, event):
        self.force = event.shift
        return self.execute(context)

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path

        images_to_save = []

        for img in bpy.data.images:
            if img.get("psd_path") != active_psd:
                continue

            if not img.get("bpsd_managed"):
                continue

            if not self.force and not img.is_dirty:
                continue

            if not img.get("psd_layer_path"):
                continue

            images_to_save.append(img)

        if not images_to_save:
            msg = "No layers loaded." if self.force else "No unsaved changes found."
            self.report({'INFO'}, msg)
            return {'CANCELLED'}

        action = "Force saving" if self.force else "Batch saving"
        self.report({'INFO'}, f"{action} {len(images_to_save)} layers...")

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
                            pass

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
                    img.pack()
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
            if item.visibility_override == 'PSD':
                if item.is_visible and not item.hidden_by_parent:
                    item.visibility_override = 'HIDE'
                else:
                    item.visibility_override = 'SHOW'

            elif item.visibility_override == 'HIDE':
                 item.visibility_override = 'SHOW'

            elif item.visibility_override == 'SHOW':
                 item.visibility_override = 'HIDE'

        try:
            bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')
        except Exception:
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

        for i, item in enumerate(props.layer_list):
            if item.layer_type == "UNKNOWN":
                continue

            if item.layer_type not in ["GROUP", "ADJUSTMENT"]:
                requests.append({
                    'layer_path': item.path,
                    'layer_index': i,
                    'width': props.psd_width,
                    'height': props.psd_height,
                    'is_mask': False,
                    'layer_id': item.layer_id
                })

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
            if idx >= len(props.layer_list): continue
            item = props.layer_list[idx]

            img = find_loaded_image(active_psd, idx, is_mask, item.layer_id)

            if not img:
                display_name = item.name
                layer_name = f"{psd_name}/{idx:03d}_{display_name}"
                img_name = f"{layer_name}_MASK" if is_mask else layer_name

                img = bpy.data.images.new(img_name, width=props.psd_width, height=props.psd_height, alpha=True)

            if img.size[0] != props.psd_width or img.size[1] != props.psd_height:
                img.scale(props.psd_width, props.psd_height)

            if len(pixels) > 0:
                img.pixels.foreach_set(pixels)

            tag_image(img, active_psd, item.path, idx, is_mask, item.layer_id)
            img.pack()

            img.colorspace_settings.name = 'Non-Color' if is_mask else 'sRGB'

            count += 1

        self.report({'INFO'}, f"Loaded {count} images.")
        return {'FINISHED'}


class BPSD_OT_debug_rw_test(bpy.types.Operator):
    bl_idname = "bpsd.debug_rw_test"
    bl_label = "Debug: Read/Write Test"
    bl_description = "Debug: Read active PSD and write back as file_1.psd (bypassing engine)"

    def execute(self, context):
        props = context.scene.bpsd_props
        active_psd = props.active_psd_path

        if not active_psd or not os.path.exists(active_psd):
            self.report({'ERROR'}, "No active PSD file found.")
            return {'CANCELLED'}

        try:
            self.report({'INFO'}, f"Reading {active_psd}...")
            layered_file = psapi.LayeredFile.read(active_psd)

            dir_name = os.path.dirname(active_psd)
            file_name = os.path.basename(active_psd)
            name, ext = os.path.splitext(file_name)
            output_path = os.path.join(dir_name, f"{name}_1{ext}")

            self.report({'INFO'}, f"Writing to {output_path}...")
            layered_file.write(output_path)

            self.report({'INFO'}, "Debug RW Test Complete.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Debug RW Failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
