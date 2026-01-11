# Plan: Photoshop Alert on Blender Dirty Conflict

## Phase 1: State Persistence & Interop Foundation
- [x] Task: Create a new JSX script `interop/alert.jsx` that accepts an alert message and displays a modal in Photoshop. [commit: ff721fb]
- [x] Task: Update `interop/check_status.vbs` (and `.scpt`) to accept an optional argument for triggering the alert, which calls the new JSX logic. [commit: 453620e]
- [ ] Task: Update `BPSD_SceneProperties` in `__init__.py` to include `last_known_ps_dirty_state` (BoolProperty, not persistent to file).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: State Persistence & Interop Foundation' (Protocol in workflow.md)

## Phase 2: Logic & Integration (TDD)
- [ ] Task: Create a test for the logic: "If falling edge (Clean -> Dirty) AND Blender is dirty, then Alert."
- [ ] Task: Modify `ps_status_check` to implement the logic: Compare current status vs `last_known_ps_dirty_state` and invoke the interop if the condition is met.
- [ ] Task: Update `last_known_ps_dirty_state` at the end of the check cycle.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Logic & Integration (TDD)' (Protocol in workflow.md)

## Phase 3: Final Verification
- [ ] Task: Manual end-to-end verification: Open synced file, edit in Blender, edit in Photoshop, verify alert.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Verification' (Protocol in workflow.md)
