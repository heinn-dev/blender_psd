try {
    var scriptFile = new File($.fileName);
    var scriptFolder = scriptFile.parent;
    var paramFile = new File(scriptFolder + "/bpsd_target.txt");
    
    if (paramFile.exists) {
        paramFile.open("r");
        var targetPath = paramFile.read();
        paramFile.close();
        targetPath = targetPath.replace(/^\s+|\s+$/g, '');
        
        if (targetPath.length > 0) {
            refreshDocument(targetPath);
        }
    }
} catch(e) { }

function refreshDocument(pathStr) {
    var targetFile = new File(pathStr);
    var foundDoc = null;
    
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].fullName.fsName === targetFile.fsName) {
            foundDoc = app.documents[i];
            break;
        }
    }

    if (foundDoc) {

        // just use default photoshop dialog? might b confusing
        if (foundDoc.saved === false) {
            alert("BPSD Sync Aborted:\n\n'" + foundDoc.name + "' has unsaved changes in Photoshop.\n\nPlease save or revert your changes in Photoshop before syncing from Blender.");
            return;
        }

        app.activeDocument = foundDoc;
        var viewState = getViewState();

        foundDoc.close(SaveOptions.DONOTSAVECHANGES);
        foundDoc = app.open(targetFile);

        restoreViewState(viewState);

        var dummyLayer = foundDoc.artLayers.add();
        dummyLayer.remove();

        foundDoc.save();
    }
}

function getViewState() {
    var state = {};
    try {
        state.layerName = app.activeDocument.activeLayer.name;
        state.zoom = app.activeWindow.zoomPercentage;
        
        var ref = new ActionReference();
        ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Vw  "));
        ref.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var desc = executeActionGet(ref);
        
        if (desc.hasKey(charIDToTypeID("Vw  "))) {
            var view = desc.getObjectValue(charIDToTypeID("Vw  "));
            if (view.hasKey(charIDToTypeID("Cntr"))) {
                var center = view.getObjectValue(charIDToTypeID("Cntr"));
                state.centerX = center.getUnitDoubleValue(charIDToTypeID("Hrzn"));
                state.centerY = center.getUnitDoubleValue(charIDToTypeID("Vrtc"));
            }
        }
    } catch(e) {}
    return state;
}

function restoreViewState(state) {
    if (!state) return;
    
    // Restore Layer
    if (state.layerName) {
        try {
            var desc = new ActionDescriptor();
            var ref = new ActionReference();
            ref.putName(charIDToTypeID("Lyr "), state.layerName);
            desc.putReference(charIDToTypeID("null"), ref);
            desc.putBoolean(charIDToTypeID("MkVs"), false);
            executeAction(charIDToTypeID("slct"), desc, DialogModes.NO);
        } catch(e) {}
    }
    
    // Restore Zoom
    if (state.zoom) {
        try {
            app.activeWindow.zoomPercentage = state.zoom;
        } catch(e) {}
    }

    // Restore Center
    if (state.centerX !== undefined && state.centerY !== undefined) {
        try {
            var desc = new ActionDescriptor();
            var ref = new ActionReference();
            ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Vw  "));
            ref.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            
            var viewDesc = new ActionDescriptor();
            var centerDesc = new ActionDescriptor();
            centerDesc.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), state.centerX);
            centerDesc.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), state.centerY);
            viewDesc.putObject(charIDToTypeID("Cntr"), charIDToTypeID("Pnt "), centerDesc);
            
            desc.putReference(charIDToTypeID("null"), ref);
            desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Vw  "), viewDesc);
            executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);
        } catch(e) {}
    }
}