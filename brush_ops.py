import bpy

class BPSD_OT_qb_brush_blend(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_blend"
    bl_label = "MIX"
    bl_options = {'REGISTER', 'UNDO'}

    blend_mode: bpy.props.StringProperty()

    def execute(self, context):
        bpy.context.tool_settings.image_paint.brush.blend = self.blend_mode
        return {'FINISHED'}

    @classmethod
    def description(cls, context, properties):
        if properties and properties.is_property_set("blend_mode"):
            mode_key = properties.blend_mode
            return f"Set blend mode to {mode_key}"

        return "Change the brush blending mode"

class BPSD_OT_qb_brush_falloff(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_falloff"
    bl_label = ""
    bl_description = "Set falloff for brush"

    falloff_mode: bpy.props.StringProperty()

    def execute(self, context):
        if context.image_paint_object:
            context.tool_settings.image_paint.brush.curve_preset = self.falloff_mode

        elif context.sculpt_object:
            context.tool_settings.sculpt.brush.curve_preset = self.falloff_mode

        return {'FINISHED'}

class BPSD_OT_qb_brush_set(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_set"
    bl_label = ""
    bl_description = "Set brush settings"

    brush_mode: bpy.props.StringProperty()

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
        brush = context.tool_settings.image_paint.brush
        if not brush:
            return {'CANCELLED'}

        mode = brush.blend

        prefs = context.preferences.addons[__package__].preferences
        current_list = [x.strip() for x in prefs.frequent_brushes.split(',') if x.strip()]

        if mode in current_list:
            current_list.remove(mode)
            self.report({'INFO'}, f"Removed {mode} from Frequent")
        else:
            current_list.append(mode)
            self.report({'INFO'}, f"Added {mode} to Frequent")

        prefs.frequent_brushes = ",".join(current_list)

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        return {'FINISHED'}
