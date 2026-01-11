# Product Guide: BlenderPSD

## Initial Concept
BlenderPSD is a bi-directional bridge between Blender and Adobe Photoshop, designed to eliminate the friction of manual import/export cycles. It empowers 3D texture artists to maintain a synchronized, non-destructive workflow where complex layered structures—including masks, groups, and blend modes—are preserved and editable in both applications.

## Target Audience
- **Primary:** 3D Texture Artists who rely on Photoshop for high-fidelity hand-painted textures but need to visualize and paint directly on 3D models in Blender.

## Core Value Proposition
- **Seamless Synchronization:** Eliminate the manual "Save As PNG -> Reload Image" loop. Updates in Photoshop reflect in Blender instantly, and vice-versa.
- **Structural Integrity:** Maintain a 1:1 mapping of layer hierarchies. A group or mask in Photoshop exists as a corresponding logical unit in Blender, not just a flattened texture.
- **Bi-Directional Freedom:** Paint in Blender using its 3D projection tools, then switch to Photoshop for advanced 2D adjustments without losing layer separation or fidelity.

## Key Features
- **Real-Time Layer Sync:** Changes to layer visibility, opacity, or content in Photoshop update the Blender node tree automatically.
- **Bi-Directional Editing:** Support for sending texture paint updates from Blender back to specific layers in the PSD.
- **Complex Layer Support:** accurate translation of Photoshop layer groups, clipping masks, and blending modes into Blender's shader nodes.
- **Conflict Management:** A robust warning system that detects unsaved changes or version conflicts in either application, empowering the user to decide which version takes precedence during sync.

## User Workflow
1. **Connect:** Link a Blender material or texture slot to a live PSD file.
2. **Visualize:** See the PSD's layer structure represented in Blender's UI.
3. **Paint (3D):** Select a specific layer in Blender and paint directly on the mesh.
4. **Refine (2D):** Open the same file in Photoshop to adjust curves, add filters, or refine details.
5. **Sync:** Trigger updates manually or automatically, with clear indicators if version conflicts arise.
