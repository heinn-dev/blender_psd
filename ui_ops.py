import bpy
import photoshopapi as psapi

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