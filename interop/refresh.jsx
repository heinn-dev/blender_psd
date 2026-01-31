try {
    if (arguments.length > 0) {
        var targetPath = arguments[0];
        if (targetPath && targetPath.length > 0) {
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
        
        // Wake up the View API with a dummy scroll
/*         try {
            var scrollDesc = new ActionDescriptor();
            var scrollRef = new ActionReference();
            scrollRef.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Vw  "));
            scrollRef.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            
            var offsetDesc = new ActionDescriptor();
            offsetDesc.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 0);
            offsetDesc.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 0);
            
            scrollDesc.putReference(charIDToTypeID("null"), scrollRef);
            scrollDesc.putObject(charIDToTypeID("T   "), charIDToTypeID("Ofst"), offsetDesc);
            
            executeAction(charIDToTypeID("scrl"), scrollDesc, DialogModes.NO);
        } catch(e) {}
 */
        // var viewState = getViewState();

        foundDoc.close(SaveOptions.DONOTSAVECHANGES);
        
        var tFile = new File(targetFile.fsName);
        foundDoc = app.open(tFile);
        
        // Wait a moment for the window to be ready
        // $.sleep(100);

        // restoreViewState(viewState);

        var dummyLayer = foundDoc.artLayers.add();
        dummyLayer.remove();

        foundDoc.save();
    }
}

function getViewState() {
    var state = {};
    
    // 1. Get Layer
    try {
        state.layerName = app.activeDocument.activeLayer.name;
    } catch(e) {}

    // 2. Get Zoom (DOM)
    try {
        state.zoom = app.activeWindow.zoomPercentage;
    } catch(e) {}
        
    // 3. Get Center (ActionManager)
    try {
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
                
                // Try to get zoom from AM if DOM failed
                if (!state.zoom && view.hasKey(charIDToTypeID("Zm  "))) {
                     // Try UnitDouble first (percent)
                     try { state.zoom = view.getUnitDoubleValue(charIDToTypeID("Zm  ")); }
                     catch(z1) {
                        try { state.zoom = view.getDouble(charIDToTypeID("Zm  ")) * 100; } catch(z2) {}
                     }
                }
            }
        }
    } catch(e) {}
    
    return state;
}

function restoreViewState(state) {
    if (!state) return;
    
    // Restore Zoom first
    if (state.zoom) {
        try {
            app.activeWindow.zoomPercentage = state.zoom;
        } catch(e) {}
    }

    // Restore Center via 'scroll' command
    if (state.centerX !== undefined && state.centerY !== undefined) {
        try {
            // Get current center after reopen/zoom
            var ref = new ActionReference();
            ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Vw  "));
            ref.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            var desc = executeActionGet(ref);
            
            if (desc.hasKey(charIDToTypeID("Vw  "))) {
                var view = desc.getObjectValue(charIDToTypeID("Vw  "));
                if (view.hasKey(charIDToTypeID("Cntr"))) {
                    var center = view.getObjectValue(charIDToTypeID("Cntr"));
                    var currentX = center.getUnitDoubleValue(charIDToTypeID("Hrzn"));
                    var currentY = center.getUnitDoubleValue(charIDToTypeID("Vrtc"));
                    
                    var deltaX = state.centerX - currentX;
                    var deltaY = state.centerY - currentY;
                    
                    if (deltaX !== 0 || deltaY !== 0) {
                        var zoomFactor = (state.zoom || 100) / 100;
                        var scrollDesc = new ActionDescriptor();
                        var scrollRef = new ActionReference();
                        scrollRef.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Vw  "));
                        scrollRef.putEnumerated(charIDToTypeID("Dcmn"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
                        
                        var offsetDesc = new ActionDescriptor();
                        offsetDesc.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), deltaX * zoomFactor);
                        offsetDesc.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), deltaY * zoomFactor);
                        
                        scrollDesc.putReference(charIDToTypeID("null"), scrollRef);
                        scrollDesc.putObject(charIDToTypeID("T   "), charIDToTypeID("Ofst"), offsetDesc);
                        
                        executeAction(charIDToTypeID("scrl"), scrollDesc, DialogModes.NO);
                    }
                }
            }
        } catch(e) {}
    }
    
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
}