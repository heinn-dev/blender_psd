import bpy

class BPSD_PT_quick_brushes(bpy.types.Panel):
    bl_label = "Quick Brushes"
    bl_idname = "BPSD_PT_quick_brushes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'
    bl_parent_id = "BPSD_PT_main_panel"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        
        if context.mode != 'PAINT_TEXTURE': return False

        package_name = __package__
        try:
            prefs = context.preferences.addons[package_name].preferences
            if not prefs.show_quick_brushes:
                return False
        except:
            pass

        return True

    blend_map = {
    'MIX'           : ['MIX', 'BRUSH_DATA',         ["frequent", "misc"]],
    'SCREEN'        : ['SCR', 'ADD',                ["frequent","curves"]],
    'MUL'           : ['MUL', 'SMOOTHCURVE',        ["frequent", "math"]],
    'OVERLAY'       : ['OVR', 'OVERLAY',            ["frequent","curves"]],
    'ADD'           : ['ADD', 'BRUSH_DATA',         ["math"]],
    'SUB'           : ['SUB', 'BRUSH_DATA',         ["math"]],
    'DIFFERENCE'    : ['DIF', 'SELECT_DIFFERENCE',  ["math"]],
    'EXCLUSION'     : ['EXC', 'PANEL_CLOSE',        ["math"]],
    'LIGHTEN'       : ['LIG', 'LIGHT',              ["frequent","curves"]],
    'DARKEN'        : ['DAR', 'SOLO_ON',            ["frequent","curves"]],
    'HARDLIGHT'     : ['HRD', 'LIGHT_SUN',          ["light"]],
    'SOFTLIGHT'     : ['SOF', 'LIGHT_HEMI',         ["light"]],
    'VIVIDLIGHT'    : ['VIV', 'LIGHT_POINT',        ["light"]],
    'LINEARLIGHT'   : ['LIN', 'LIGHT_HEMI',         ["light"]],
    'PINLIGHT'      : ['PIN', 'LIGHT_SPOT',         ["light"]],
    'HUE'           : ['HUE', 'DISC',               ["color"]],
    'SATURATION'    : ['SAT', 'STRANDS',            ["frequent","color"]],
    'COLOR'         : ['COL', 'IMAGE_RGB_ALPHA',    ["color"]],
    'LUMINOSITY'    : ['LUM', 'LIGHT_DATA',         ["color"]],
    'ERASE_ALPHA'   : ['EAL', 'KEY_RING',           ["frequent","alpha"]],
    'ADD_ALPHA'     : ['AAL', 'KEY_RING_FILLED',    ["alpha"]],
    'COLORDODGE'    : ['CDG', 'TRIA_UP_BAR',        ["burn"]],
    'COLORBURN'     : ['CBN', 'TRIA_DOWN_BAR',      ["burn"]],
    'LINEARBURN'    : ['LBN', 'RESTRICT_COLOR_OFF', ["burn"]],
    }

    falloff_map = {
    'SMOOTH'   : ['Smooth', 'SMOOTHCURVE'],
    'SMOOTHER' : ['Smoother', 'SMOOTHCURVE'],
    'SPHERE'   : ['Sphere', 'SPHERECURVE'],
    'ROOT'     : ['Root',   'ROOTCURVE'],
    'SHARP'    : ['Sharp',  'SHARPCURVE'],
    'LIN'      : ['Linear', 'LINCURVE'],
    'POW4'     : ['Sharper',  'SHARPCURVE'],
    'INVSQUARE' : ['InvSq',  'INVERSESQUARECURVE'],
    'CONSTANT' : ['Const',  'NOCURVE'],
    }

    def draw(self, context):
        layout = self.layout

        tool_settings = context.tool_settings.image_paint
        space = context.space_data

        layout.label(text="Brush Falloff")

        col = layout.column(align=True)
        col.scale_y = 0.8

        row = col.box().row(align=True)
        for i, f_key in enumerate(self.falloff_map.keys()):

            data = self.falloff_map[f_key]

            brush = context.tool_settings.image_paint.brush
            if not brush: continue

            if bpy.app.version < (5, 0, 0):
                is_active = (getattr(brush, "curve_preset", "") == f_key)
            else:
                # Blender 5.0+
                is_active = (getattr(brush, "curve_distance_falloff_preset", "") == f_key)

            op = row.operator("bpsd.qb_brush_falloff", text='', icon=data[1], depress=is_active)
            op.falloff_mode = f_key

        layout.separator()
        props = context.scene.bpsd_props

        package_name = __package__
        prefs = context.preferences.addons[package_name].preferences
        frequent_list = [x.strip() for x in prefs.frequent_brushes.split(',')]

        row = layout.row(align=True)
        row.label(text="Blend Mode")
        row.prop(props, "show_frequent_only", toggle=True)

        brush = context.tool_settings.image_paint.brush
        if brush and brush.blend in self.blend_map:
             is_frequent = brush.blend in frequent_list
             row.operator("bpsd.toggle_frequent", text="", icon='SOLO_ON', depress=is_frequent)

        categories = {
            "math": [], "curves": [], "light": [],
            "color": [], "alpha": [], "burn": [], "misc": []
        }

        for key, data in self.blend_map.items():
            tags = data[2]
            for cat in categories.keys():
                if cat in tags:
                    categories[cat].append(key)

        main_row = layout.row(align=False)
        main_row.alignment = 'EXPAND'

        cats_to_draw = []

        for key in categories.keys():
            cats_to_draw.append((key, categories[key.lower()]))

        catbox = layout.box()

        if props.show_frequent_only:
            col = catbox.column(align=True)
            col.scale_y = 0.8
            col.alignment = "LEFT"

            valid_items = []
            seen = set()
            for cat_name, items in cats_to_draw:
                for mode_key in items:
                    if mode_key in frequent_list and mode_key not in seen:
                        valid_items.append((mode_key, cat_name))
                        seen.add(mode_key)

            prev_cat = None
            row = None
            
            for i, (mode_key, cat_name) in enumerate(valid_items):
                if i % 4 == 0:
                    col.separator()
                    row = col.row(align=True)
                    row.alignment = "LEFT"
                    
                elif prev_cat is not None and cat_name != prev_cat:
                    if i % 4 != 3:
                        col.separator()
                        row = col.row(align=True)
                        row.alignment = "LEFT"
                
                prev_cat = cat_name

                data = self.blend_map[mode_key]
                display_text = data[0]
                display_icon = data[1]
                is_active = (brush.blend == mode_key)

                sub = row.row(align=True)
                sub.alignment = "LEFT"
                op = sub.operator("bpsd.qb_brush_blend", text=display_text, icon=display_icon, depress=is_active)
                op.blend_mode = mode_key
            
            col.separator(factor=.5)

        else:
            for cat_name, items in cats_to_draw:
                if not items: continue

                col = catbox.column(align=True)
                col.scale_y = 0.8
                col.alignment ="LEFT"

                c = 0
                for mode_key in items:

                    data = self.blend_map[mode_key]

                    if c % 4 == 0:
                        row = col.row(align = True)
                        row.alignment = "LEFT"

                    c += 1

                    display_text = data[0]
                    display_icon = data[1]
                    is_active = (brush.blend == mode_key)

                    sub = row.row(align = True)
                    sub.alignment = "LEFT"
                    op = sub.operator("bpsd.qb_brush_blend", text=display_text, icon=display_icon, depress=is_active)
                    op.blend_mode = mode_key

                col.separator(factor=.25)

        layout.separator()

        layout.label(text="Quick toggles")

        settings = context.tool_settings.image_paint

        if not settings.brush:
            layout.label(text="No Brush", icon='ERROR')
            return

        brush = settings.brush
        row = layout.row(align=True)

        row.prop(settings, "use_backface_culling", text="Backface", icon='MOD_SOLIDIFY')
        row.prop(settings, "use_occlude", text="Occlude", icon='XRAY')
        row.prop(brush, "use_alpha", text="Paint Alpha", icon='TEXTURE')

        # layout.separator()
        
        # Erase Row
        row = layout.row(align=True)
        op = row.operator("bpsd.qb_select_brush", text=f"Eraser", icon='BRUSH_DATA')
        op.mode = 'ERASE'
        op = row.operator("bpsd.qb_assign_brush", text="", icon='SOLO_ON')
        op.mode = 'ERASE'
        
        # Paint Row
        # row = layout.row(align=True)
        op = row.operator("bpsd.qb_select_brush", text=f"Brush", icon='BRUSH_DATA')
        op.mode = 'PAINT'
        op = row.operator("bpsd.qb_assign_brush", text="", icon='SOLO_ON')
        op.mode = 'PAINT'
