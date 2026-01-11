# Product Guidelines: BlenderPSD

## UI/UX Philosophy: Minimalist & Integrated
The add-on should be invisible until needed. It must feel like a native extension of Blender’s existing toolset, avoiding visual clutter and intrusive notifications.

### 1. Visual Style & Representation
- **Native Aesthetic:** Adhere strictly to Blender's standard UI widgets, spacing, and icon sets. The layer list should feel familiar to users of the Outliner or Image Editor.
- **Inline Layer Status:** Use clear, minimalist status indicators directly within the layer list. A user should be able to glance at their layer stack and immediately identify which layers are synced, which are locally modified (dirty), and which have external conflicts.
- **Minimalist Communication:** Avoid verbose dialogs. Use subtle UI cues and tooltips for routine status updates. Reserve toast notifications for significant events or errors that require immediate attention.

### 2. Data Integrity & Safety
- **Strict Confirmation:** "Safety First" is the default. Any operation that risks overwriting unsaved changes in either Blender or Photoshop must require an explicit user confirmation.
- **Conflict Transparency:** Never resolve version conflicts automatically. Clearly flag when the disk version (PSD) and the memory version (Blender) have diverged, providing the user with the information needed to make an informed choice.

### 3. Integration Strategy
- **Sidebar-Native:** The primary control center resides in the 3D Viewport sidebar (`N-panel`), organized into logical categories (Connect, Layers, Tools).
- **Contextual Awareness:** The UI should dynamically update based on the selected object, material, or active layer, ensuring that relevant tools are always at the user's fingertips.

### 4. Performance & Scalability
- **Pragmatic Implementation:** Avoid premature optimization. Maintain the highest visual fidelity possible until performance bottlenecks are identified.
- **Deferred Complexity:** Implement complex performance-saving features (like resolution-swapping or background processing) only when necessary to maintain a responsive user experience in production-scale files.
