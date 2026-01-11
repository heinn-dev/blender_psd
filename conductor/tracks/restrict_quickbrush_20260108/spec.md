# Specification: Restrict QuickBrush panel visibility to Paint Mode

## Problem
The QuickBrush panel is currently visible in modes where it might not be applicable or desired, cluttering the UI. The user wants it to only be active/visible when Blender is in "Paint Mode" (specifically Texture Paint mode, as this is a PSD syncing add-on).

## Goal
Modify the `poll` method or the panel registration logic for the QuickBrush panel to ensure it only appears in the 3D Viewport sidebar when the object is in Texture Paint mode.

## Requirements
- The `BPSD_PT_quick_brushes` panel must only be visible in `TEXTURE_PAINT` mode.
- The panel should remain functional as before when in the correct mode.
- Adhere to Blender's native UI feel (it should disappear/appear seamlessly when switching modes).

## Technical Details
- File: `brush_panels.py` (contains `BPSD_PT_quick_brushes`)
- Logic: Update `BPSD_PT_quick_brushes.poll(cls, context)` to check `context.mode == 'PAINT_TEXTURE'` or equivalent.
