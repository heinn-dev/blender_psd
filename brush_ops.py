import bpy

class BPSD_OT_qb_brush_blend(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_blend"
    bl_label = "MIX"
    bl_options = {'REGISTER', 'UNDO'}

    blend_mode: bpy.props.StringProperty() # type: ignore

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

    falloff_mode: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        brush = None
        if context.image_paint_object:
            brush = context.tool_settings.image_paint.brush
        elif context.sculpt_object:
            brush = context.tool_settings.sculpt.brush

        if brush:
            if bpy.app.version < (5, 0, 0):
                if hasattr(brush, "curve_preset"):
                    brush.curve_preset = self.falloff_mode
            else:
                 if hasattr(brush, "curve_distance_falloff_preset"):
                     brush.curve_distance_falloff_preset = self.falloff_mode

        return {'FINISHED'}

class BPSD_OT_qb_brush_set(bpy.types.Operator):
    bl_idname = "bpsd.qb_brush_set"
    bl_label = ""
    bl_description = "Set brush settings"

    brush_mode: bpy.props.StringProperty() # type: ignore

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

class BPSD_OT_qb_select_brush(bpy.types.Operator):
    bl_idname = "bpsd.qb_select_brush"
    bl_label = "Select Brush"
    bl_description = "Select the assigned quick brush"

    mode: bpy.props.EnumProperty(items=[('PAINT', "Paint", ""), ('ERASE', "Erase", "")]) # type: ignore

    @classmethod
    def poll(cls, context):
        # Only allow if panel is visible (preference enabled) and in paint mode
        if context.mode != 'PAINT_TEXTURE': return False
        try:
             prefs = context.preferences.addons[__package__].preferences
             if not prefs.show_quick_brushes: return False
        except:
             return False
        return True

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        slot = prefs.paint_slot if self.mode == 'PAINT' else prefs.erase_slot
        
        # Check if initialized (name is default) and set defaults if needed
        # Actually, properties have defaults, so we just check if it feels "empty" or default
        # But user might have set name to "Custom Brush" manually.
        # Let's trust the slot.
        
        brush = context.tool_settings.image_paint.brush
        if not brush:
            self.report({'WARNING'}, "No active brush to update.")
            return {'CANCELLED'}
        
        # Apply settings
        brush.blend = slot.blend
        brush.strength = slot.strength
        brush.color = slot.color
        brush.secondary_color = slot.secondary_color
        # heh, we don't really want this to be a per-brush thing
        # brush.use_alpha = slot.use_alpha
        brush.stroke_method = slot.stroke_method
        
        if bpy.app.version < (5, 0, 0):
            if slot.curve_preset and hasattr(brush, "curve_preset"):
                brush.curve_preset = slot.curve_preset
        else:
             if slot.curve_preset and hasattr(brush, "curve_distance_falloff_preset"):
                 brush.curve_distance_falloff_preset = slot.curve_preset
             
        return {'FINISHED'}

class BPSD_OT_qb_assign_brush(bpy.types.Operator):
    bl_idname = "bpsd.qb_assign_brush"
    bl_label = "Assign Brush"
    bl_description = "Assign current brush settings to this slot"

    mode: bpy.props.EnumProperty(items=[('PAINT', "Paint", ""), ('ERASE', "Erase", "")]) # type: ignore

    def execute(self, context):
        brush = context.tool_settings.image_paint.brush
        if not brush: return {'CANCELLED'}
        
        prefs = context.preferences.addons[__package__].preferences
        slot = prefs.paint_slot if self.mode == 'PAINT' else prefs.erase_slot
        
        slot.name = brush.name
        slot.blend = brush.blend
        slot.strength = brush.strength
        slot.color = brush.color
        slot.secondary_color = brush.secondary_color
        slot.use_alpha = brush.use_alpha
        slot.stroke_method = brush.stroke_method
        
        # Falloff
        if bpy.app.version < (5, 0, 0):
             if hasattr(brush, "curve_preset"):
                 slot.curve_preset = brush.curve_preset
        else:
             if hasattr(brush, "curve_distance_falloff_preset"):
                 slot.curve_preset = brush.curve_distance_falloff_preset
            
        self.report({'INFO'}, f"Saved settings to {self.mode} slot")
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
