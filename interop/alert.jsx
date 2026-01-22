// interop/alert.jsx
// Displays an alert in Photoshop. Accepts an optional message via the arguments array.

var msg = "Warning: Unsaved changes detected in Blender.\nSave changes in Blender, and press F12 to reload file from disk to restore sync.";

if (typeof arguments !== 'undefined' && arguments.length > 0 && arguments[0]) {
    msg = arguments[0];
}

alert(msg);
