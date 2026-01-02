import bpy

class BPSD_OT_qb_brush_blend(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_blend"
    bl_label = "MIX"
    # bl_description = "Set brush to blend mode"
    bl_options = {'REGISTER', 'UNDO'}
    
    blend_mode: bpy.props.StringProperty()  # type: ignore
    
    def execute(self, context):
        bpy.context.tool_settings.image_paint.brush.blend = self.blend_mode
        return {'FINISHED'}

    @classmethod
    def description(cls, context, properties):
        # 'properties' holds the values you set in the UI 
        # (e.g., op.blend_mode = 'MIX')
        
        if properties and properties.is_property_set("blend_mode"):
            mode_key = properties.blend_mode
            
            # Return the description from the map, or a fallback
            return f"Set blend mode to {mode_key}"
            
        return "Change the brush blending mode"

class BPSD_OT_qb_brush_falloff(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_falloff"
    bl_label = ""
    bl_description = "Set falloff for brush"
    
    falloff_mode: bpy.props.StringProperty()  # type: ignore
    
    def execute(self, context):
        # Apply to image paint
        if context.image_paint_object:
            context.tool_settings.image_paint.brush.curve_preset = self.falloff_mode
        # Apply to sculpt if that's where you are
        elif context.sculpt_object:
            context.tool_settings.sculpt.brush.curve_preset = self.falloff_mode
            
        return {'FINISHED'}
    
class BPSD_OT_qb_brush_set(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_set"
    bl_label = ""
    bl_description = "Set brush settings"
    
    brush_mode: bpy.props.StringProperty()  # type: ignore
    
    def execute(self, context):

        if self.brush_mode == "PAINT":
            bpy.ops.bpsd.qb_brush_blend('EXEC_DEFAULT', blend_mode='MIX')
            bpy.ops.bpsd.qb_brush_falloff('EXEC_DEFAULT', falloff_mode='SMOOTH')
            pass
        elif self.brush_mode == "ERASE":
            bpy.ops.bpsd.qb_brush_blend('EXEC_DEFAULT', blend_mode='ERASE_ALPHA')
            bpy.ops.bpsd.qb_brush_falloff('EXEC_DEFAULT', falloff_mode='CONSTANT')
            pass


        return {'FINISHED'}

class BPSD_OT_toggle_frequent(bpy.types.Operator):
    bl_idname = "bpsd.toggle_frequent"
    bl_label = "Toggle Frequent"
    bl_description = "Add or remove current brush from frequent category"

    def execute(self, context):
        from . import brush_panels

        # Get current blend mode
        brush = context.tool_settings.image_paint.brush
        if not brush:
            return {'CANCELLED'}

        mode = brush.blend

        # Access the map
        b_map = brush_panels.BPSD_PT_quick_brushes.blend_map

        if mode in b_map:
            data = b_map[mode]
            tags = data[2]

            if "frequent" in tags:
                tags.remove("frequent")
                self.report({'INFO'}, f"Removed {mode} from Frequent")
            else:
                tags.append("frequent")
                self.report({'INFO'}, f"Added {mode} to Frequent")

            # Force redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

        return {'FINISHED'}