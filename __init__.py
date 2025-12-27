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
import sys
import numpy as np
import psd_engine
import ui_ops
# from PIL import Image

for path in sys.path:
    if "extensions" in path and "blender_psd" in path:
        print(f"FOUND EXTENSION PATH: {path}")
try:
    import photoshopapi as psapi
    print("SUCCESS: psapi imported!")
except ImportError as e:
    print(f"FAILED: {e}")

testPSDpath = "C:\\Users\\Kirill\\AppData\\Roaming\\Blender Foundation\\Blender\\4.4\\extensions\\user_default\\blender_psd\\test.psd"
test_layered_file = None





def draw_layer_tree(layout, layers, path=""):
    for layer in layers:
        current_path = f"{path}/{layer.name}" if path else layer.name
        row = layout.row()
        
        if isinstance(layer, psapi.GroupLayer_8bit):
            box = layout.box()
            box.label(text=layer.name, icon='FILE_FOLDER')
            draw_layer_tree(box, layer.layers, current_path) 
        else:
            row.label(icon='IMAGE_DATA') # text=layer.name, 
            # Load Button
            load_op = row.operator("bpsd.load_layer", text=layer.name)
            load_op.layer_path = current_path
            
            # Save Button (Only if image exists in Blender)
            if layer.name in bpy.data.images:
                save_op = row.operator("bpsd.save_layer", text="Save")
                save_op.layer_path = current_path
                save_op.bl_image_name = layer.name


class MYADDON_PT_panel(bpy.types.Panel):
    global test_layered_file

    bl_label = "Blender PSD"
    bl_idname = "BPSD_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'

    def draw(self, context):
        global test_layered_file
        layout = self.layout

        try:
            if test_layered_file is None:
                test_layered_file = psapi.LayeredFile.read(testPSDpath)

            draw_layer_tree(layout, test_layered_file.layers);
        except Exception as e:
           print({e})



def find_by_id(layers, id):
    for layer in layers:
        if layer.layer_id == id:
            return layer
        elif layer.is_group():
            return find_by_id(layer)

def register():
    global test_layered_file
    bpy.utils.register_class(MYADDON_PT_panel)
    bpy.utils.register_class(BPSD_OT_load_layer)
    bpy.utils.register_class(BPSD_OT_save_layer)
    
def unregister():
    bpy.utils.unregister_class(MYADDON_PT_panel)
    bpy.utils.unregister_class(BPSD_OT_load_layer)
    bpy.utils.unregister_class(BPSD_OT_save_layer)

def image_update_callback():
    # iterate through all images we know are in the psd, if is_dirty is false just save em?
    # .... or just timer it
    print("Image was modified or saved!")

# Subscribe to the 'is_dirty' property of images
subscribe_to = bpy.types.Image, "is_dirty"

bpy.msgbus.subscribe_rna(
    key=subscribe_to,
    owner=bpy.context.window_manager,
    args=(),
    notify=image_update_callback,
)

if __name__ == "__main__":
    register()