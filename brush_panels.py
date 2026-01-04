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

        for key in categories.keys():
            cats_to_draw.append((key, categories[key.lower()]))
        
        catbox = layout.box()
        
        # instead of making a new column for each category, just use a separator?
        # BUT still 4 max per row, hmmm
        for cat_name, items in cats_to_draw:
            if not items: continue
            t = 0
            for mode_key in items:
                data = self.blend_map[mode_key]
                tags = data[2]
                if not props.show_frequent_only or mode_key in frequent_list:
                    t += 1
            if t == 0: continue

            col = catbox.column(align=True)
            col.scale_y = 0.8
            col.alignment ="LEFT"
            
            c = 0
            for mode_key in items:

                data = self.blend_map[mode_key]
                tags = data[2]

                if props.show_frequent_only and mode_key not in frequent_list:
                    continue
                
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
        
        
        
        

        
