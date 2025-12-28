
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

class BPSD_LayerItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty() 
    layer_type: bpy.props.StringProperty() 
    indent: bpy.props.IntProperty(default=0)
    has_mask: bpy.props.BoolProperty(default=False)

class BPSD_SceneProperties(bpy.types.PropertyGroup):
    active_psd_path: bpy.props.StringProperty(
        name="PSD Path", subtype='FILE_PATH'
    )
    layer_list: bpy.props.CollectionProperty(type=BPSD_LayerItem)
    active_layer_index: bpy.props.IntProperty(default=-1)
    active_layer_path: bpy.props.StringProperty()
    active_is_mask: bpy.props.BoolProperty()
    psd_width: bpy.props.IntProperty()
    psd_height: bpy.props.IntProperty()
    
    # probably needs an rgb(a) toggle?

# --- CONNECT OPERATOR ---psd_height

class BPSD_OT_connect_psd(bpy.types.Operator):
    bl_idname = "bpsd.connect_psd"
    bl_label = "Connect"

    def execute(self, context):
        props = context.scene.bpsd_props
        path = props.active_psd_path
        
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
    panels.BPSD_PT_main_panel,
    panels.BPSD_PT_layer_context,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bpsd_props = bpy.props.PointerProperty(type=BPSD_SceneProperties)

def unregister():
    del bpy.types.Scene.bpsd_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()