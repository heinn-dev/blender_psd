import bpy

class BPSD_PT_quick_brushes(bpy.types.Panel):
    bl_label = "Quick Brushes"
    bl_idname = "BPSD_PT_quick_brushes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BPSD'
    bl_parent_id = "BPSD_PT_main_panel"
    # bl_options = {"DEFAULT_CLOSED"}
    
    # only show if we're painting something...
    @classmethod
    def poll(cls, context):
        # Check preferences
        package_name = __package__
        try:
            prefs = context.preferences.addons[package_name].preferences
            if not prefs.show_quick_brushes:
                return False
        except:
            pass

        return True
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW3D':
                    # Check if the current object in this viewport is in Paint Mode
                    # if bpy.context.view_layer.objects.active:
                    #     if bpy.context.object.mode == 'PAINT_TEXTURE':
                    #         return True
                    return True
                
                # we need another panel in here too hmmmmmm
                
                # # Check the Image Editor (Texture Paint tab)
                # if area.type == 'IMAGE_EDITOR':
                #     for space in area.spaces:
                #         if space.type == 'IMAGE_EDITOR':
                #             if space.mode == 'PAINT':
                #                 return True
            return False
        
        
    # enum in ['MIX', 'DARKEN', 'MUL', 'COLORBURN', 'LINEARBURN', 'LIGHTEN', 
    # 'SCREEN', 'COLORDODGE', 'ADD', 'OVERLAY', 'SOFTLIGHT', 'HARDLIGHT', 
    # 'VIVIDLIGHT', 'LINEARLIGHT', 'PINLIGHT', 'DIFFERENCE', 'EXCLUSION', 
    # 'SUB', 'HUE', 'SATURATION', 'COLOR', 'LUMINOSITY', 'ERASE_ALPHA', 'ADD_ALPHA']
    
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
        brush = context.tool_settings.image_paint.brush

        # Get Preferences for Frequent Brushes
        # In Blender 4.2 Extensions, __package__ is the full ID (e.g. "bl_ext.user_default.blender_psd")
        # In Legacy, it is just "blender_psd"
        package_name = __package__
        prefs = context.preferences.addons[package_name].preferences
        frequent_list = [x.strip() for x in prefs.frequent_brushes.split(',')]

        # ===== FALLOFF SELECT

        layout.label(text="Brush Falloff")
        
        col = layout.column(align=True)
        col.scale_y = 0.8  # Keeping it compact as requested
        
        row = col.row(align=True)
        for i, f_key in enumerate(self.falloff_map.keys()):
            
            data = self.falloff_map[f_key]
            
            # Check if this is the currently active falloff to highlight the button
            is_active = (context.tool_settings.image_paint.brush.curve_preset == f_key)
            
            # We use a generic operator or a custom one to set the property
            op = row.operator("bpsd.qb_brush_falloff", text='', icon=data[1], depress=is_active)  
            op.falloff_mode = f_key
        
        layout.separator()
        props = context.scene.bpsd_props
        
        # ===== BLEND MODE HEADER (TOGGLES)
        # Create a header row for the toggles
        row = layout.row(align=True)
        row.label(text="Blend Mode")
        row.prop(props, "show_frequent_only", toggle=True)

        # Toggle current brush in frequent list
        if brush and brush.blend in self.blend_map:
             is_frequent = brush.blend in frequent_list
             row.operator("bpsd.toggle_frequent", text="", icon='SOLO_ON', depress=is_frequent)

        # Create a second row for category toggles if you want them compact
        # row = layout.row(align=True)
        # row.scale_x = 0.8 # Make toggles smaller to fit
        # row.prop(props, "show_cat_math", toggle=True)
        # row.prop(props, "show_cat_curves", toggle=True)
        # row.prop(props, "show_cat_light", toggle=True)
        # row.prop(props, "show_cat_color", toggle=True)
        # row.prop(props, "show_cat_burn", toggle=True)
        # row.prop(props, "show_cat_alpha", toggle=True)
        
        # ===== DYNAMIC COLUMNS
        # 1. Organize keys by category
        categories = {
            "math": [], "curves": [], "light": [], 
            "color": [], "alpha": [], "burn": [], "misc": []
        }
        
        for key, data in self.blend_map.items():
            tags = data[2]
            # Add to respective lists
            for cat in categories.keys():
                if cat in tags:
                    categories[cat].append(key)
        
        # 2. Create the columns layout
        # We use a row container to hold the vertical columns side-by-side
        main_row = layout.row(align=False)
        main_row.alignment = 'EXPAND' 
        
        # 3. Define which columns to actually draw based on toggles
        cats_to_draw = []
        # if props.show_cat_misc: cats_to_draw.append(("Misc", categories["misc"]))
        # if props.show_cat_curves: cats_to_draw.append(("Curves", categories["curves"]))
        # if props.show_cat_math: cats_to_draw.append(("Math", categories["math"]))
        # if props.show_cat_light: cats_to_draw.append(("Light", categories["light"]))
        # if props.show_cat_burn: cats_to_draw.append(("Burn", categories["burn"]))
        # if props.show_cat_color: cats_to_draw.append(("Color", categories["color"]))
        # if props.show_cat_alpha: cats_to_draw.append(("Alpha", categories["alpha"]))
        for key in categories.keys():
            cats_to_draw.append((key, categories[key.lower()]))
        
        catbox = layout.box()
        # 4. Iterate and Draw
        for cat_name, items in cats_to_draw:
            # Skip empty categories
            if not items: continue
            # else: layout.separator()
            t = 0
            for mode_key in items:
                data = self.blend_map[mode_key]
                tags = data[2]
                if not props.show_frequent_only or mode_key in frequent_list:
                    t += 1
            if t == 0: continue

            # Create a vertical column for this category
            col = catbox.column(align=True)
            col.scale_y = 0.8
            col.alignment ="LEFT"
            # Label for the column (Optional, makes it very tall)
            # col.label(text=cat_name)
            c = 0
            t = 0
            for mode_key in items:

                data = self.blend_map[mode_key]
                tags = data[2]

                # THE FREQUENT FILTER
                # If "Show Frequent Only" is ON, and this item lacks the tag, skip it
                if props.show_frequent_only and mode_key not in frequent_list:
                    continue
                
                if c % 4 == 0:
                    row = col.row(align = True)
                    row.alignment = "LEFT"
                    
                c += 1
                t += 1
                
                display_text = data[0]
                display_icon = data[1]
                is_active = (brush.blend == mode_key)
                
                sub = row.row(align = True)
                sub.alignment = "LEFT"
                op = sub.operator("bpsd.qb_brush_blend", text=display_text, icon=display_icon, depress=is_active)
                op.blend_mode = mode_key
                
            col.separator(factor=.5)

        layout.separator()
        # ===== QUICK TOGGLES
        layout.label(text="Quick toggles")
        
        settings = context.tool_settings.image_paint
        
        if not settings.brush:
            layout.label(text="No Brush", icon='ERROR')
            return
        
        brush = settings.brush
        row = layout.row(align=True)
        
        row.prop(settings, "use_backface_culling", text="Backface", icon='MOD_SOLIDIFY')
        row.prop(settings, "use_occlude", text="Occlude", icon='XRAY')
        row.prop(brush, "use_alpha", text="Paint Alpha", icon='LOCKED') 
        
        row = layout.row(align=True)
        op = row.operator("bpsd.qb_brush_set", text="Eraser")
        op.brush_mode = "ERASE"
        op = row.operator("bpsd.qb_brush_set", text="Brush")
        op.brush_mode = "PAINT"
        # row.prop(settings, "seam_bleed", text="Bleed", icon='MOD_UVPROJECT')
        
        

        
