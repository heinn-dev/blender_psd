/* refresh.jsx
    Reads 'bpsd_target.txt' from the same folder to determine which file to refresh.
*/

try {
    // 1. Determine where this script is located
    var scriptFile = new File($.fileName);
    var scriptFolder = scriptFile.parent;
    
    // 2. Read the Sidecar File (bpsd_target.txt)
    var paramFile = new File(scriptFolder + "/bpsd_target.txt");
    
    if (paramFile.exists) {
        paramFile.open("r");
        var targetPath = paramFile.read(); // Read the path
        paramFile.close();
        
        // Trim whitespace just in case
        // (ExtendScript doesn't always have .trim(), so use regex)
        targetPath = targetPath.replace(/^\s+|\s+$/g, '');
        
        if (targetPath.length > 0) {
            refreshDocument(targetPath);
        }
    }

} catch(e) {
    // Fail silently or alert for debugging
    // alert("BPSD Error: " + e);
}

function refreshDocument(pathStr) {
    var targetFile = new File(pathStr);
    var foundDoc = null;
    
    // Find open doc
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].fullName.fsName === targetFile.fsName) {
            foundDoc = app.documents[i];
            break;
        }
    }

    if (foundDoc) {
        // Reload logic
        foundDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.open(targetFile);
    }
}