# Plan: Restrict QuickBrush panel visibility to Paint Mode

This plan outlines the steps to restrict the QuickBrush panel visibility to Texture Paint mode.

## Phase 1: Analysis & Test Setup
- [ ] Task: Analyze `brush_panels.py` and `brush_ops.py` to confirm current panel logic.
- [ ] Task: Create a unit test to verify current visibility behavior (mocking Blender context).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Analysis & Test Setup' (Protocol in workflow.md)

## Phase 2: Implementation (TDD)
- [ ] Task: Update visibility tests to expect the panel to be hidden in non-paint modes.
- [ ] Task: Implement the mode check in `BPSD_PT_quick_brushes.poll`.
- [ ] Task: Verify tests pass with the new implementation.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Implementation (TDD)' (Protocol in workflow.md)

## Phase 3: Final Verification
- [ ] Task: Perform manual verification in Blender to ensure the panel behaves as expected.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Verification' (Protocol in workflow.md)
