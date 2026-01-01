
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
from . import panels

# --- DATA STRUCTURES ---

class BPSD_LayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()# type: ignore
    path: bpy.props.StringProperty() # type: ignore
    layer_type: bpy.props.StringProperty() # type: ignore
    indent: bpy.props.IntProperty(default=0)# type: ignore
    has_mask: bpy.props.BoolProperty(default=False)# type: ignore
    is_clipping_mask: bpy.props.BoolProperty(default=False)# type: ignore


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
    
    #last_known_mtime: bpy.props.FloatProperty(default=0.0) # type: ignore
    last_known_mtime_str: bpy.props.StringProperty(default="0.0") # type: ignore

    # --- HELPER: Dynamic Dropdown Generator ---
    def get_psd_images(self, context):
        """
        Scans loaded Blender images for .psd files.
        Returns a list of tuples: (identifier, display_name, description)
        """
        items = []
        
        # 1. Iterate through all loaded images
        for img in bpy.data.images:
            # Check filename extension (case insensitive)
            if img.filepath.lower().endswith('.psd'):
                # Identifier must be unique (Image Name), Display is Name, Desc is Path
                items.append((img.name, img.name, img.filepath))
        
        # 2. Fallback if empty
        if not items:
            items.append(('NONE', "No Loaded PSDs", "Use Image > Open to load a PSD first"))
            
        return items

    # --- HELPER: Update Handler ---
    def on_psd_selection_update(self, context):
        """
        Triggered when the user picks a new PSD from the dropdown.
        Automatically resolves the absolute path for the engine.
        """
        selected_name = self.active_psd_image
        
        if selected_name == 'NONE':
            self.active_psd_path = ""
            return

        img = bpy.data.images.get(selected_name)
        if img:
            # Convert relative Blender path (//texture.psd) to Absolute System Path
            abs_path = bpy.path.abspath(img.filepath)
            
            # Clean up path (remove trailing slashes, resolve symlinks)
            abs_path = os.path.normpath(abs_path)
            
            self.active_psd_path = abs_path
            
            # Optional: Auto-Connect on switch? 
            # Usually better to wait for user to click "Connect" to avoid lag.
    
    active_psd_image: bpy.props.EnumProperty(
        name="Source PSD",
        description="Select a .psd image currently loaded in Blender",
        items=get_psd_images,
        update=on_psd_selection_update
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "photoshop_exe_path")


# --- CONNECT OPERATOR ---psd_height

class BPSD_OT_connect_psd(bpy.types.Operator):
    bl_idname = "bpsd.connect_psd"
    bl_label = "Connect"
    bl_description = "Keep the selected file in sync"

    def execute(self, context):

        props = context.scene.bpsd_props

        # Resolve path from dropdown if not already set
        if not props.active_psd_path and props.active_psd_image != 'NONE':
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
        
        props.active_layer_index = -1
        props.active_layer_path = ""
        
        if props.auto_purge:
            bpy.ops.bpsd.clean_orphans('EXEC_DEFAULT')
        
        bpy.ops.bpsd.reload_all('EXEC_DEFAULT')

        if os.path.exists(props.active_psd_path):
            props.last_known_mtime = os.path.getmtime(props.active_psd_path)

        # Also reload the main PSD image in Blender if it exists
        if props.active_psd_image != 'NONE':
            main_img = bpy.data.images.get(props.active_psd_image)
            if main_img:
                main_img.reload()

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
            item.has_mask = node.get('has_mask', False)
            item.indent = indent
            item.is_clipping_mask = node['is_clipping_mask']

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


def auto_sync_check():
    context = bpy.context
    if not context.scene: return 1.0
    
    props = context.scene.bpsd_props
    path = props.active_psd_path
    
    if not props.auto_sync_incoming or not path or not os.path.exists(path):
        return 2.0
        
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
            
            print(f"BPSD: Change detected. Disk: {current_mtime} != Stored: {stored_mtime}")
            
            # Update IMMEDIATELY to prevent double-triggering next tick
            props.last_known_mtime_str = str(current_mtime)
            
            if context.window:
                # bpy.ops.bpsd.reload_all('EXEC_DEFAULT')
                bpy.ops.bpsd.connect_psd('EXEC_DEFAULT')
                
    except Exception as e:
        print(f"BPSD Watcher Error: {e}")
        
    return 1.0

# --- REGISTRATION ---

classes = (
    BPSD_LayerItem,
    BPSD_SceneProperties,
    BPSD_OT_connect_psd,
    BPSD_OT_stop_sync,
    ui_ops.BPSD_OT_select_layer,
    ui_ops.BPSD_OT_load_layer,
    ui_ops.BPSD_OT_save_layer,
    ui_ops.BPSD_OT_save_all_layers,
    ui_ops.BPSD_OT_clean_orphans,
    ui_ops.BPSD_OT_reload_all,
    panels.BPSD_PT_main_panel,
    panels.BPSD_PT_layer_context,
    BPSDPreferences
)

addon_keymaps= []

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bpsd_props = bpy.props.PointerProperty(type=BPSD_SceneProperties)
    
    # wm = bpy.context.window_manager
    # kc = wm.keyconfigs.addon
    # if kc:
    #     km = kc.keymaps.new(name='Image Generic', space_typfe='IMAGE_EDITOR')
        
    #     # uggh.... I don't remember if this respects anything about masks.
    #     # Bind Ctrl+S to OUR operator
    #     kmi = km.keymap_items.new(
    #         ui_ops.BPSD_OT_save_layer.bl_idname, 
    #         'S', 'PRESS', ctrl=True
    #     )
    #     addon_keymaps.append((km, kmi))
        
    bpy.app.timers.register(auto_sync_check, persistent=True)
    
def unregister():
    del bpy.types.Scene.bpsd_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    if auto_sync_check in bpy.app.timers.is_registered:
        bpy.app.timers.unregister(auto_sync_check)
        
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
        

if __name__ == "__main__":
    register()