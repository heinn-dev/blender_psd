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

def blender_to_psapi_data(blender_image):
    """Converts Blender float pixels to 8-bit planar data for PhotoshopAPI."""
    width, height = blender_image.size
    # Get pixels and convert 0.0-1.0 float to 0-255 uint8
    pixels = np.array(blender_image.pixels)
    pixels = (pixels * 255).astype(np.uint8)
    
    # Reshape to (Height, Width, RGBA)
    pixels = pixels.reshape((height, width, 4))
    
    # Flip vertically (Blender is bottom-up, PSD is top-down)
    pixels = np.flipud(pixels)
    
    # PhotoshopAPI expects planar data: {0: R_array, 1: G_array, 2: B_array, 3: A_array}
    return {
        0: pixels[:, :, 0].copy(), # Red
        1: pixels[:, :, 1].copy(), # Green
        2: pixels[:, :, 2].copy(), # Blue
        -1: pixels[:, :, 3].copy()  # Alpha
    }

class BPSD_OT_load_layer(bpy.types.Operator):
    bl_idname = "bpsd.load_layer"
    bl_label = "Load Layer"
    
    layer_path: bpy.props.StringProperty()

    def execute(self, context):
        global test_layered_file
        if not test_layered_file:
            test_layered_file = psapi.LayeredFile.read(testPSDpath)

        # Retrieve the layer by path (e.g., "Group/LayerName")
        layer = test_layered_file.find_layer(self.layer_path)
        
        # Extract planar data and merge to a PIL image for conversion
        # psapi returns {channel_index: numpy_array}
        img_data = layer.get_image_data()
        
        for key, value in img_data.items():
            print (key, value)
        # Reconstruct RGBA for Blender
        h, w = img_data[0].shape
        rgba = np.stack([img_data[0], img_data[1], img_data[2], img_data[-1]], axis=-1)
        # what's the order??? I think just -1 for alpha, -2 for clip mask
        # empty layers have no data, either don't load or blank it out?
        # https://photoshopapi.readthedocs.io/en/latest/python/layers/image.html#photoshopapi.ImageLayer_8bit.get_image_data

        rgba = np.flipud(rgba) # Flip for Blender
        
        # Create Blender Image
        img_name = layer.name
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])
            
        bl_image = bpy.data.images.new(img_name, width=w, height=h, alpha=True)
        # Normalize and flatten for Blender's .pixels
        bl_image.pixels = (rgba.astype(np.float32) / 255.0).flatten()


        # unslop this stuff

        if context.active_object and context.active_object.type == 'MESH':
            bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
            # 2. Find any Image Editor and point it to our new texture
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    # This sets the image in the editor
                    area.spaces.active.image = bl_image
        
        # bl_image.alpha_mode = 'STRAIGHT'
        # bl_image.colorspace_settings.name = 'sRGB'

        # Trigger the UI update
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = bl_image

        # Optional: Set the editor to Paint mode specifically
        
        self.report({'INFO'}, f"Loaded: {img_name}")
        return {'FINISHED'}

class BPSD_OT_save_layer(bpy.types.Operator):
    bl_idname = "bpsd.save_layer"
    bl_label = "Save Layer"
    
    layer_path: bpy.props.StringProperty()
    bl_image_name: bpy.props.StringProperty()

    def execute(self, context):
        global test_layered_file
        try:
            layered_file = psapi.LayeredFile.read(testPSDpath)
        except Exception as e:
            self.report({'ERROR'}, f"Could not read PSD: {e}")
            return {'CANCELLED'}

        if not layered_file or self.bl_image_name not in bpy.data.images:
            return {'CANCELLED'}

        bl_image = bpy.data.images[self.bl_image_name]
        layer = layered_file.find_layer(self.layer_path)
        
        # Convert Blender pixels to PSAPI format
        new_data = blender_to_psapi_data(bl_image)
        
        # Update layer pixels (Direct replacement in memory)
        for channel_id, data in new_data.items():
            layer[channel_id] = data
            
        # Write back to file
        layered_file.write(testPSDpath)
        
        self.report({'INFO'}, f"Saved {bl_image.name} back to PSD")
        return {'FINISHED'}

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