# Tech Stack: BlenderPSD

## Core Language & Runtime
- **Python 3.11+:** The primary logic is written in Python, executing within Blender's embedded environment.

## Primary Frameworks & APIs
- **Blender API (bpy):** Used for all Blender-side operations, including UI panels, operators, node tree manipulation, and scene property management.
- **Blender Extension System:** Uses the modern `blender_manifest.toml` standard for package metadata and distribution.

## Specialized Libraries
- **photoshopapi:** A critical dependency (provided as a pre-built `.whl`) that handles the heavy lifting of reading from and writing to PSD files.

## Inter-Process Communication (IPC) & Interop
- **Adobe Photoshop Scripting (JSX):** Used to automate Photoshop operations from the outside (e.g., refreshing files, checking layer status).
- **Windows Script Host (VBScript):** Employs `silent_runner.vbs` and `check_status.vbs` to execute Photoshop scripts without popping command windows, ensuring a smooth user experience on Windows.
- **AppleScript:** Includes `.scpt` equivalents to ensure future compatibility and feature parity on macOS.

## Configuration & Deployment
- **Wheels:** Project includes a `wheels/` directory to bundle external Python dependencies that are not available by default in Blender's environment.
