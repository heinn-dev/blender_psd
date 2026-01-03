
// TODO remember xmp, we might not need the meme file
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

        foundDoc.close(SaveOptions.DONOTSAVECHANGES);
        foundDoc = app.open(targetFile);

        var dummyLayer = foundDoc.artLayers.add();
        dummyLayer.remove();

        foundDoc.save();
    }
}