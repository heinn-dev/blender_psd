
bl_info = {
    "name": "BlenderPSD",
    "author": "Heinn",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar",
    "description": "Example addon",
    "category": "3D View",
}


import bpy

from . import psd_engine
from . import ui_ops
from . import panels

# --- DATA STRUCTURES ---
addon_keymaps = []

class BPSD_LayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()# type: ignore
    path: bpy.props.StringProperty() # type: ignore
    layer_type: bpy.props.StringProperty() # type: ignore
    indent: bpy.props.IntProperty(default=0)# type: ignore
    has_mask: bpy.props.BoolProperty(default=False)# type: ignore

class BPSD_SceneProperties(bpy.types.PropertyGroup):
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
    
    
    # probably needs an rgb(a) toggle?


class BPSDPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__ # Refers to the module name

    photoshop_exe_path: bpy.props.StringProperty(
        name="Photoshop Executable",
        description="Path to Photoshop.exe (e.g. C:/Program Files/Adobe/Adobe Photoshop 2024/Photoshop.exe)",
        subtype='FILE_PATH',
        default=r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe" # Common default
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "photoshop_exe_path")

# --- CONNECT OPERATOR ---psd_height

class BPSD_OT_connect_psd(bpy.types.Operator):
    bl_idname = "bpsd.connect_psd"
    bl_label = "Connect"

    def execute(self, context):
        
        props = context.scene.bpsd_props
        path = props.active_psd_path
        
        # file = psd_engine.read_file(path)
        # return {'FINISHED'}
        
        # 1. Read
        tree_data,w,h = psd_engine.read_file(path)
        if not tree_data:
            self.report({'ERROR'}, "Could not read PSD.")
            return {'CANCELLED'}
        
        props.psd_width = w
        props.psd_height = h

        # 2. Populate
        props.layer_list.clear()
        self.flatten_tree(tree_data, props.layer_list, indent=0)
        
        props.active_layer_index = -1
        props.active_layer_path = ""
        
        if props.auto_purge:
            bpy.ops.bpsd.clean_orphans('EXEC_DEFAULT')
        
        self.report({'INFO'}, "Connected!")
        return {'FINISHED'}

    def flatten_tree(self, nodes, collection, indent):
        # Reverse to show top layers first
        for node in nodes: 
            item = collection.add()
            item.name = node['name']
            item.path = node['path']
            item.layer_type = node['type']
            item.has_mask = node.get('has_mask', False)
            item.indent = indent
            
            if node['children']:
                self.flatten_tree(node['children'], collection, indent + 1)

# --- REGISTRATION ---



classes = (
    BPSD_LayerItem,
    BPSD_SceneProperties,
    BPSD_OT_connect_psd,
    ui_ops.BPSD_OT_select_layer,
    ui_ops.BPSD_OT_load_layer,
    ui_ops.BPSD_OT_save_layer,
    ui_ops.BPSD_OT_save_all_layers,
    ui_ops.BPSD_OT_clean_orphans,
    panels.BPSD_PT_main_panel,
    panels.BPSD_PT_layer_context,
    BPSDPreferences
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bpsd_props = bpy.props.PointerProperty(type=BPSD_SceneProperties)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Image Generic', space_type='IMAGE_EDITOR')
        
        # Bind Ctrl+S to OUR operator
        kmi = km.keymap_items.new(
            ui_ops.BPSD_OT_save_layer.bl_idname, 
            'S', 'PRESS', ctrl=True
        )
        addon_keymaps.append((km, kmi))
    
def unregister():
    del bpy.types.Scene.bpsd_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
        

if __name__ == "__main__":
    register()