// interop/push_layers.jsx
//
// Pushes changed layers from Blender straight into the open Photoshop document,
// instead of Blender rewriting the whole PSD and Photoshop reloading it.
//
// Per layer: select it, Select All, Clear, then fill with a pattern defined
// from the PNG Blender wrote. Compositing an opaque-free layer against a
// pattern reproduces the pixels including alpha, and because the layer is never
// created or destroyed its id, name, blend mode, opacity, mask and effects all
// survive. Merging a pasted layer down would lose most of that.
//
// arguments[0] = job folder containing job.json and the layer PNGs
//
// NOTE: `arguments` only exists at script scope, so read it before any function.

var BPSD_JOB_DIR = "";
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    BPSD_JOB_DIR = String(arguments[0]).replace(/\\/g, "/").replace(/\/+$/, "");
}

var BPSD_PATTERN = "BPSD_TEMP_PATTERN";
var bpsdJob = null;
var bpsdDoc = null;
var bpsdApplied = [];
var bpsdSkipped = [];
var bpsdErrors = [];

function sid(s) { return stringIDToTypeID(s); }

function bpsdReadFile(path) {
    var f = new File(path);
    if (!f.exists) return null;
    f.encoding = "UTF-8";
    f.open("r");
    var text = f.read();
    f.close();
    return text;
}

function bpsdWriteFile(path, text) {
    try {
        var f = new File(path);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(text);
        f.close();
        return true;
    } catch (e) {
        return false;
    }
}

function bpsdJsonEscape(s) {
    return String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"')
                    .replace(/[\r\n]/g, " ");
}

function bpsdWriteResult(ok, reason) {
    var parts = [];
    parts.push('"ok":' + (ok ? "true" : "false"));
    if (reason) parts.push('"reason":"' + bpsdJsonEscape(reason) + '"');

    var layers = [];
    for (var i = 0; i < bpsdApplied.length; i++) {
        var a = bpsdApplied[i];
        layers.push('{"name":"' + bpsdJsonEscape(a.name) + '","layer_id":' + a.id +
                    ',"matched_by":"' + a.how + '","is_mask":' + (a.isMask ? "true" : "false") + '}');
    }
    parts.push('"layers":[' + layers.join(",") + ']');

    var skips = [];
    for (var k = 0; k < bpsdSkipped.length; k++) {
        skips.push('"' + bpsdJsonEscape(bpsdSkipped[k]) + '"');
    }
    parts.push('"skipped":[' + skips.join(",") + ']');

    var errs = [];
    for (var j = 0; j < bpsdErrors.length; j++) {
        errs.push('"' + bpsdJsonEscape(bpsdErrors[j]) + '"');
    }
    parts.push('"errors":[' + errs.join(",") + ']');

    bpsdWriteFile(BPSD_JOB_DIR + "/result.json", "{" + parts.join(",") + "}");
}

// ---------------------------------------------------------------- lookup

function bpsdFindDoc(psdPath) {
    var want = new File(psdPath);
    for (var i = 0; i < app.documents.length; i++) {
        try {
            if (app.documents[i].fullName.fsName === want.fsName) return app.documents[i];
        } catch (e) {}
    }
    return null;
}

/*
 * layer_id is photoshopapi's value read from the file, which matches
 * Photoshop's runtime id exactly. The index path and name are fallbacks for
 * when a layer has been recreated in Photoshop since Blender last synced.
 */
function bpsdResolveLayer(doc, spec) {
    var byId = null, byPath = null, byName = null;

    function walk(layers, prefix) {
        for (var i = 0; i < layers.length; i++) {
            var L = layers[i];
            var p = (prefix === "") ? String(i) : prefix + "/" + i;

            if (spec.layer_id && !byId) {
                try { if (L.id === spec.layer_id) byId = L; } catch (e) {}
            }
            if (spec.layer_path && !byPath && p === spec.layer_path) byPath = L;
            if (spec.name && !byName && L.name === spec.name) byName = L;

            if (L.typename === "LayerSet") walk(L.layers, p);
        }
    }
    walk(doc.layers, "");

    if (byId) return { layer: byId, how: "id" };
    if (byPath) return { layer: byPath, how: "path" };
    if (byName) return { layer: byName, how: "name" };
    return { layer: null, how: "none" };
}

// ---------------------------------------------------------------- pattern

function bpsdDefinePattern(pngPath) {
    var src = app.open(new File(pngPath));
    app.activeDocument = src;
    src.selection.selectAll();

    var d = new ActionDescriptor();
    var r = new ActionReference();
    r.putClass(sid("pattern"));
    d.putReference(sid("null"), r);

    var r2 = new ActionReference();
    r2.putProperty(sid("selectionClass"), sid("selection"));
    r2.putEnumerated(sid("document"), sid("ordinal"), sid("targetEnum"));
    d.putReference(sid("using"), r2);
    d.putString(sid("name"), BPSD_PATTERN);

    executeAction(sid("make"), d, DialogModes.NO);

    src.selection.deselect();
    src.close(SaveOptions.DONOTSAVECHANGES);
}

function bpsdFillPattern() {
    var d = new ActionDescriptor();
    d.putEnumerated(sid("using"), sid("fillContents"), sid("pattern"));

    var p = new ActionDescriptor();
    p.putString(sid("name"), BPSD_PATTERN);
    d.putObject(sid("pattern"), sid("pattern"), p);

    d.putUnitDouble(sid("opacity"), sid("percentUnit"), 100);
    d.putEnumerated(sid("mode"), sid("blendMode"), sid("normal"));

    executeAction(sid("fill"), d, DialogModes.NO);
}

function bpsdDeletePattern() {
    try {
        var d = new ActionDescriptor();
        var r = new ActionReference();
        r.putName(sid("pattern"), BPSD_PATTERN);
        d.putReference(sid("null"), r);
        executeAction(sid("delete"), d, DialogModes.NO);
    } catch (e) {}
}

function bpsdSelectMaskChannel() {
    var r = new ActionReference();
    r.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Msk "));
    var d = new ActionDescriptor();
    d.putReference(charIDToTypeID("null"), r);
    executeAction(charIDToTypeID("slct"), d, DialogModes.NO);
}

function bpsdHasMask(layer) {
    try {
        var r = new ActionReference();
        r.putIdentifier(charIDToTypeID("Lyr "), layer.id);
        var desc = executeActionGet(r);
        return desc.hasKey(sid("userMaskEnabled"));
    } catch (e) {
        return false;
    }
}

// ---------------------------------------------------------------- apply

function bpsdApplyLayer(spec) {
    var resolved = bpsdResolveLayer(bpsdDoc, spec);
    var layer = resolved.layer;

    if (!layer) {
        bpsdErrors.push("layer not found: " + (spec.name || spec.layer_path));
        return;
    }

    // Clearing and filling a text or smart-object layer would rasterise it.
    // Those are exactly the layers this whole approach exists to protect, so
    // this is a skip rather than an error: failing the job would send the save
    // down the legacy path, where photoshopapi rewrites the file and damages
    // the very layer we just declined to touch.
    if (!spec.is_mask && layer.kind !== LayerKind.NORMAL) {
        bpsdSkipped.push(layer.name + " (" + layer.kind + ")");
        return;
    }

    if (spec.is_mask && !bpsdHasMask(layer)) {
        bpsdSkipped.push(layer.name + " (no layer mask)");
        return;
    }

    bpsdDefinePattern(BPSD_JOB_DIR + "/" + spec.file);

    app.activeDocument = bpsdDoc;
    bpsdDoc.activeLayer = layer;

    try {
        layer.allLocked = false;
        layer.pixelsLocked = false;
        layer.transparentPixelsLocked = false;
    } catch (e) {}

    if (spec.is_mask) {
        bpsdSelectMaskChannel();
        bpsdDoc.selection.selectAll();
        // A mask has no alpha, so the opaque pattern overwrites it outright.
        bpsdFillPattern();
        bpsdDoc.selection.deselect();
        bpsdDoc.activeChannels = bpsdDoc.componentChannels;
    } else {
        // Target pixels, not the mask, or Clear would wipe the mask instead.
        bpsdDoc.activeChannels = bpsdDoc.componentChannels;
        bpsdDoc.selection.selectAll();
        bpsdDoc.selection.clear();
        bpsdFillPattern();
        bpsdDoc.selection.deselect();
    }

    bpsdDeletePattern();

    bpsdApplied.push({
        name: layer.name,
        id: layer.id,
        how: resolved.how,
        isMask: !!spec.is_mask
    });
}

// Called through suspendHistory so the whole sync collapses into one undo step.
function bpsdApplyAll() {
    for (var i = 0; i < bpsdJob.layers.length; i++) {
        try {
            bpsdApplyLayer(bpsdJob.layers[i]);
        } catch (e) {
            var spec = bpsdJob.layers[i];
            bpsdErrors.push((spec.name || "?") + ": " + e);
            bpsdDeletePattern();
        }
    }
}

// ---------------------------------------------------------------- main

function bpsdMain() {
    if (!BPSD_JOB_DIR) return;

    var text = bpsdReadFile(BPSD_JOB_DIR + "/job.json");
    if (!text) {
        bpsdWriteResult(false, "bad_job");
        return;
    }

    // ExtendScript has no JSON parser, but JSON is valid JS and we wrote it.
    bpsdJob = eval("(" + text + ")");

    bpsdDoc = bpsdFindDoc(bpsdJob.psd_path);
    if (!bpsdDoc) {
        bpsdWriteResult(false, "not_open");
        return;
    }

    if (bpsdJob.require_clean && bpsdDoc.saved === false) {
        bpsdWriteResult(false, "ps_dirty");
        return;
    }

    var prevDialogs = app.displayDialogs;
    var prevRuler = app.preferences.rulerUnits;
    app.displayDialogs = DialogModes.NO;
    app.preferences.rulerUnits = Units.PIXELS;

    try {
        bpsdDoc.suspendHistory("BlenderPSD Sync", "bpsdApplyAll()");

        // Skips do not block the save, but if everything was skipped there is
        // nothing to write and a save would only cost a full re-encode.
        if (bpsdErrors.length === 0 && bpsdApplied.length > 0 && bpsdJob.save !== false) {
            // Photoshop's own save is also what regenerates the flattened
            // composite that Blender previews.
            bpsdDoc.save();
        }
    } catch (e) {
        bpsdErrors.push("apply: " + e);
    }

    app.displayDialogs = prevDialogs;
    app.preferences.rulerUnits = prevRuler;

    bpsdWriteResult(bpsdErrors.length === 0, bpsdErrors.length ? "error" : null);
}

bpsdMain();
