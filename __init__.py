
bl_info = {
    "name": "BlenderPSD",
    "author": "Heinn",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar",
    "description": "Example addon",
    "category": "3D View",
}


import os
import bpy

from . import psd_engine
from . import ui_ops
from . import brush_ops
from . import brush_panels
from . import panels
from . import node_ops

# --- DATA STRUCTURES ---

class BPSD_LayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()# type: ignore
    path: bpy.props.StringProperty() # type: ignore
    layer_type: bpy.props.StringProperty() # type: ignore
    indent: bpy.props.IntProperty(default=0)# type: ignore
    layer_id: bpy.props.IntProperty(default=0)# type: ignore
    has_mask: bpy.props.BoolProperty(default=False)# type: ignore
    is_clipping_mask: bpy.props.BoolProperty(default=False)# type: ignore
    is_visible: bpy.props.BoolProperty(default=False)# type: ignore
    hidden_by_parent: bpy.props.BoolProperty(default=False)# type: ignore
    blend_mode: bpy.props.StringProperty(default="NORMAL")# type: ignore
    opacity: bpy.props.FloatProperty(default=1.0)# type: ignore
    clip_base_index: bpy.props.IntProperty(default=-1) # type: ignore

    visibility_override: bpy.props.EnumProperty(
        name="Visibility Override",
        description="Override the visibility of this layer in the node tree",
        items=[
            ('PSD', "Sync (PSD)", "Use visibility from Photoshop"),
            ('SHOW', "Always Show", "Force visible in Blender"),
            ('HIDE', "Always Hide", "Force hidden in Blender"),
        ],
        default='PSD'
    ) # type: ignore


class BPSD_SceneProperties(bpy.types.PropertyGroup):
    # probably needs an rgb(a) toggle?
    
    active_psd_path: bpy.props.StringProperty( name="PSD Path", subtype='FILE_PATH')# type: ignore
    layer_list: bpy.props.CollectionProperty(type=BPSD_LayerItem)# type: ignore
    active_layer_index: bpy.props.IntProperty(default=-1)# type: ignore
    active_layer_path: bpy.props.StringProperty()# type: ignore
    active_is_mask: bpy.props.BoolProperty()# type: ignore
    psd_width: bpy.props.IntProperty()# type: ignore
    psd_height: bpy.props.IntProperty() # type: ignore
    auto_load_on_select: bpy.props.BoolProperty(
        name="Auto-Load",
        description="Automatically load texture when selecting a layer",
        default=True
    ) # type: ignore
    auto_purge: bpy.props.BoolProperty(
        name="Auto-Purge",
        description="Automatically remove orphan layers on a sync",
        default=True
    ) # type: ignore
    auto_refresh_ps: bpy.props.BoolProperty(
        name="Auto-Refresh Photoshop",
        description="Run a JS script to reload the file in Photoshop after saving",
        default=True
    ) # type: ignore
    auto_sync_incoming: bpy.props.BoolProperty(
        name="Auto-Sync from Disk",
        description="Automatically reload textures when the PSD file is saved in Photoshop",
        default=True
    ) # type: ignore

    auto_save_on_image_save: bpy.props.BoolProperty(
        name="Auto-Save on Alt-S",
        description="Automatically sync to PSD when saving an image in Blender (Alt-S)",
        default=False
    ) # type: ignore

    #last_known_mtime: bpy.props.FloatProperty(default=0.0) # type: ignore
    last_known_mtime_str: bpy.props.StringProperty(default="0.0") # type: ignore
    structure_signature: bpy.props.StringProperty() # type: ignore

    show_cat_math: bpy.props.BoolProperty(name="Math", default=True)# type: ignore
    show_cat_light: bpy.props.BoolProperty(name="Light", default=True)# type: ignore
    show_cat_color: bpy.props.BoolProperty(name="Color", default=True)# type: ignore
    show_cat_alpha: bpy.props.BoolProperty(name="Alpha", default=True)# type: ignore
    show_cat_burn: bpy.props.BoolProperty(name="Burn", default=True)# type: ignore
    show_cat_curves: bpy.props.BoolProperty(name="Curves", default=True)# type: ignore
    show_cat_misc: bpy.props.BoolProperty(name="Misc", default=True)# type: ignore
    show_frequent_only: bpy.props.BoolProperty(
        name="Faves Only", 
        description="Only show favourite brushes", 
        default=False
    )# type: ignore

    def get_psd_images(self, context):
        items = []
        
        for img in bpy.data.images:
            if img.filepath.lower().endswith('.psd'):
                items.append((img.name, img.name, img.filepath))
        
        if not items:
            items.append(('NONE', "No Loaded PSDs", "Use Image > Open to load a PSD first"))
            
        return items

    active_psd_image: bpy.props.EnumProperty(
        name="Source PSD",
        description="Select a .psd image currently loaded in Blender",
        items=get_psd_images,
    )# type: ignore
    

class BPSDPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__ # Refers to the module name

    photoshop_exe_path: bpy.props.StringProperty(
        name="Photoshop Executable",
        description="Path to Photoshop.exe (e.g. C:/Program Files/Adobe/Adobe Photoshop 2024/Photoshop.exe)",
        subtype='FILE_PATH',
        default=r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe" # Common default
    ) # type: ignore
    
    ahk_exe_path: bpy.props.StringProperty(
        name="AHK Executable",
        description="Path to AutoHotkey.exe",
        subtype='FILE_PATH',
        default=r"C:\\Program Files\\AutoHotkey\\AutoHotkey.exe" # Common default
    ) # type: ignore

    frequent_brushes: bpy.props.StringProperty(
        name="Frequent Brushes",
        description="Comma-separated list of frequent blend modes",
        default="MIX,SCREEN,MUL,OVERLAY,LIGHTEN,DARKEN,SATURATION,ERASE_ALPHA"
    ) # type: ignore

    show_quick_brushes: bpy.props.BoolProperty(
        name="Show Quick Brushes Panel",
        description="Enable the Quick Brushes panel in the 3D View",
        default=True
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "photoshop_exe_path")
        layout.prop(self, "show_quick_brushes")
        layout.prop(self, "frequent_brushes")


# --- CONNECT OPERATOR ---psd_height

class BPSD_OT_connect_psd(bpy.types.Operator):
    bl_idname = "bpsd.connect_psd"
    bl_label = "Connect"
    bl_description = "Keep the selected file in sync"

    def execute(self, context):

        props = context.scene.bpsd_props

        # ALWAYS resolve path from the current dropdown selection (Explicit Sync)
        if props.active_psd_image != 'NONE':
            img = bpy.data.images.get(props.active_psd_image)
            if img:
                abs_path = bpy.path.abspath(img.filepath)
                props.active_psd_path = os.path.normpath(abs_path)

        path = props.active_psd_path
        
        # file = psd_engine.read_file(path)
        # return {'FINISHED'}
        
        # 1. Read
        tree_data,w,h = psd_engine.read_file(path)
        if not tree_data:
            self.report({'ERROR'}, "Could not read PSD.")
            return {'CANCELLED'}
        
        for layer in tree_data:
            if layer['layer_type'] == "UNKNOWN":
                self.report({'WARNING'}, f"A layer could not be read, this might cause data loss upon save!")
                
        
        props.psd_width = w
        props.psd_height = h

        # 2. Populate
        props.layer_list.clear()
        self.flatten_tree(tree_data, props.layer_list, indent=0)

        # 3. Resolve Clipping Bases (Iterate Bottom-to-Top)
        indent_map = {} # Maps indent level -> current base index
        # We iterate backwards because the list is Top-to-Bottom, but bases are below clipping masks
        for i in range(len(props.layer_list) - 1, -1, -1):
            item = props.layer_list[i]

            if item.is_clipping_mask:
                # This layer is a clipping mask, so it must clip to the current base at this indent
                if item.indent in indent_map:
                    item.clip_base_index = indent_map[item.indent]
            else:
                # This is a normal layer, so it becomes the new base for this indent level
                indent_map[item.indent] = i

        # 4. Calculate Structure Signature
        sig_parts = []
        for item in props.layer_list:
            # Include fields that determine node structure
            # Note: We exclude Name (just a label) and Blend Mode for non-groups (just a value update)
            # This allows the "Update Nodes" operator to handle these changes without a full regeneration warning.

            # Base topology
            part = f"{item.layer_id}:{item.layer_type}:{item.indent}:{item.is_clipping_mask}:{item.has_mask}"

            # Groups use blend mode for topology (Passthrough vs Normal)
            if item.layer_type == 'GROUP':
                part += f":{item.blend_mode}"

            sig_parts.append(part)
        props.structure_signature = "|".join(sig_parts)

        props.active_layer_index = -1
        props.active_layer_path = ""
        
        if props.auto_purge:
            bpy.ops.bpsd.clean_orphans('EXEC_DEFAULT')
        
        bpy.ops.bpsd.reload_all('EXEC_DEFAULT')

        if os.path.exists(props.active_psd_path):
            props.last_known_mtime_str = str(os.path.getmtime(props.active_psd_path))

        # Also reload the main PSD image in Blender if it exists
        if props.active_psd_image != 'NONE':
            main_img = bpy.data.images.get(props.active_psd_image)
            if main_img:
                main_img.reload()

        # 5. Auto-Update Node Tree
        # Update the node group if it exists (global update), regardless of active object
        ng = bpy.data.node_groups.get("BPSD_PSD_Output")
        if ng:
            stored_sig = ng.get("bpsd_structure_signature", "")

            if stored_sig != props.structure_signature:
                print("BPSD: Structure changed, regenerating nodes...")
                bpy.ops.bpsd.create_psd_nodes('EXEC_DEFAULT')
            else:
                print("BPSD: Structure match, updating node values...")
                bpy.ops.bpsd.update_psd_nodes('EXEC_DEFAULT')

        self.report({'INFO'}, "Connected!")
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        # The button is clickable if a valid PSD is selected in the dropdown
        props = context.scene.bpsd_props
        return props.active_psd_image != 'NONE' and props.active_psd_image in bpy.data.images

    def flatten_tree(self, nodes, collection, indent):
        # Reverse to show top layers first
        for node in nodes:
            item = collection.add()
            item.name = node['name']
            item.path = node['path']
            item.layer_type = node['layer_type']
            item.layer_id = node.get('layer_id', 0)
            item.has_mask = node.get('has_mask', False)
            item.indent = indent
            item.is_clipping_mask = node['is_clipping_mask']
            item.is_visible = node['is_visible']
            item.hidden_by_parent = node.get('hidden_by_parent', False)
            item.blend_mode = node.get('blend_mode', 'NORMAL')
            item.opacity = node.get('opacity', 1.0)

            if node['children']:
                self.flatten_tree(node['children'], collection, indent + 1)


class BPSD_OT_stop_sync(bpy.types.Operator):
    bl_idname = "bpsd.stop_sync"
    bl_label = "Stop Sync"
    bl_description = "Stop syncing the current file"

    def execute(self, context):
        props = context.scene.bpsd_props
        props.layer_list.clear()
        props.active_psd_path = ""
        props.active_layer_index = -1
        props.active_layer_path = ""
        props.last_known_mtime_str = "0.0"

        self.report({'INFO'}, "Sync stopped")
        return {'FINISHED'}


class BPSD_OT_highlight_psd(bpy.types.Operator):
    bl_idname = "bpsd.highlight_psd"
    bl_label = "Highlight PSD"
    bl_description = "Show the main PSD file in the Image Editor"

    def execute(self, context):
        props = context.scene.bpsd_props

        if props.active_psd_image == 'NONE':
            self.report({'WARNING'}, "No PSD file loaded.")
            return {'CANCELLED'}

        img = bpy.data.images.get(props.active_psd_image)
        if not img:
            self.report({'ERROR'}, "Image not found.")
            return {'CANCELLED'}

        # Use the helper from ui_ops to focus the image editor
        ui_ops.focus_image_editor(context, img)
        props.active_layer_index = -1

        return {'FINISHED'}


def auto_sync_check():
    context = bpy.context
    if not context.scene: return 1.0
    
    props = context.scene.bpsd_props
    path = props.active_psd_path

    if not props.auto_sync_incoming or not path or not os.path.exists(path):
        return 2.0

    # SAFETY CHECK: Reload main PSD if modified in Blender (since we can't save it back)
    if props.active_psd_image != 'NONE':
        main_img = bpy.data.images.get(props.active_psd_image)
        if main_img and main_img.is_dirty:
            print(f"BPSD: Reverting accidental changes to {main_img.name}")
            main_img.reload()

    try:
        # 1. Get exact OS time
        current_mtime = os.path.getmtime(path)
        
        # 2. Get stored time (High Precision)
        try:
            stored_mtime = float(props.last_known_mtime_str)
        except ValueError:
            stored_mtime = 0.0
        
        # 3. Comparison with Epsilon (Threshold)
        # We check if the difference is significant (> 0.01 seconds)
        # This prevents loops caused by micro-jitter
        if abs(current_mtime - stored_mtime) > 0.01:

            # Check for dirty layers
            has_unsaved = False
            for img in bpy.data.images:
                if img.get("bpsd_managed") and img.get("psd_path") == path and img.is_dirty:
                    has_unsaved = True
                    break

            if has_unsaved:
                print("BPSD: Photoshop file updated, but Auto-Sync skipped due to unsaved changes in Blender.")
                props.last_known_mtime_str = str(current_mtime) # Acknowledge change to prevent looping
                return 1.0

            # print(f"BPSD: Change detected. Disk: {current_mtime} != Stored: {stored_mtime}")

            # Update IMMEDIATELY to prevent double-triggering next tick
            props.last_known_mtime_str = str(current_mtime)
            
            if context.window:
                # bpy.ops.bpsd.reload_all('EXEC_DEFAULT')
                bpy.ops.bpsd.connect_psd('EXEC_DEFAULT')
                
    except Exception as e:
        print(f"BPSD Watcher Error: {e}")
        
    return 1.0

# --- WATCHERS ---
# Moved to ui_ops.py to prevent circular dependency loops

# --- REGISTRATION ---

classes = (
    BPSDPreferences,
    BPSD_LayerItem,
    BPSD_SceneProperties,
    BPSD_OT_connect_psd,
    BPSD_OT_stop_sync,
    BPSD_OT_highlight_psd,
    ui_ops.BPSD_OT_select_layer,
    ui_ops.BPSD_OT_load_layer,
    ui_ops.BPSD_OT_save_layer,
    ui_ops.BPSD_OT_save_all_layers,
    ui_ops.BPSD_OT_clean_orphans,
    ui_ops.BPSD_OT_reload_all,
    ui_ops.BPSD_OT_toggle_visibility,
    ui_ops.BPSD_OT_load_all_layers,

    panels.BPSD_PT_main_panel,
    
    brush_ops.BPSD_OT_qb_brush_blend,
    brush_ops.BPSD_OT_qb_brush_falloff,
    brush_ops.BPSD_OT_qb_brush_set,
    brush_ops.BPSD_OT_toggle_frequent,
    brush_panels.BPSD_PT_quick_brushes,
    panels.BPSD_PT_layer_context,
    panels.BPSD_PT_nodes,
    node_ops.BPSD_OT_create_layer_node,
    node_ops.BPSD_OT_create_layer_frame,
    node_ops.BPSD_OT_create_group_nodes,
    node_ops.BPSD_OT_create_psd_nodes,
    node_ops.BPSD_OT_update_psd_nodes,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bpsd_props = bpy.props.PointerProperty(type=BPSD_SceneProperties)

    # Initialize Cache
    ui_ops.init_dirty_cache()

    bpy.app.timers.register(ui_ops.image_dirty_watcher, persistent=True)
    bpy.app.timers.register(auto_sync_check, persistent=True)

def unregister():
    del bpy.types.Scene.bpsd_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    try:
        bpy.app.timers.unregister(ui_ops.image_dirty_watcher)
    except:
        pass

    try:
        bpy.app.timers.unregister(auto_sync_check)
    except:
        pass

if __name__ == "__main__":
    register()