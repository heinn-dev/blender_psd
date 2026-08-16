"""Blender side of the direct-to-Photoshop layer push.

Instead of rebuilding the whole PSD with photoshopapi and then making Photoshop
close and reopen the document, changed layers are written out as PNGs and
push_layers.jsx drops them straight into the open document. Photoshop then
saves once - which is also what regenerates the flattened composite Blender
previews.

Per Ctrl-S that turns 2 full decodes + 2 full encodes into a single encode, and
because Blender never rewrites the file, layers photoshopapi cannot round-trip
(text, and anything the addon lists as UNKNOWN) are no longer at risk.

Everything degrades to psd_engine.write_all_layers: if Photoshop is closed, the
document is not open, or the push fails, the caller's fallback runs instead.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zlib

import bpy
import numpy as np

from . import psd_engine

BRIDGE_DIRNAME = "bpsd_bridge"

POLL_INTERVAL = 0.15
JOB_TIMEOUT = 120.0
STALE_JOB_AGE = 3600.0

# zlib level 1: the PNG is read back immediately by Photoshop on the same
# machine, so write speed matters far more than size.
PNG_COMPRESS_LEVEL = 1


def bridge_root():
    return os.path.join(tempfile.gettempdir(), BRIDGE_DIRNAME)


def _interop_dir():
    return os.path.join(os.path.dirname(__file__), "interop")


def is_available():
    """True when the push path can be attempted at all.

    Whether Photoshop is running, and whether it has the right document open,
    is answered by the job result rather than probed up front - probing would
    mean another blocking subprocess on every save.
    """
    if sys.platform != 'win32':
        return False
    return os.path.exists(os.path.join(_interop_dir(), "push_layers.jsx"))


# ------------------------------------------------------------------ png

def _png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _write_rgba_png(path, arr):
    """arr: (H, W, 4) uint8, top-left origin.

    Written by hand because the addon only bundles photoshopapi - there is no
    pillow to lean on. The sRGB chunk matters: without it Photoshop can raise a
    missing-profile dialog on open and stall the whole silent workflow.
    """
    h, w = arr.shape[:2]

    raw = np.empty((h, w * 4 + 1), dtype=np.uint8)
    raw[:, 0] = 0                      # filter type 0 (None) per scanline
    raw[:, 1:] = arr.reshape(h, w * 4)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(_png_chunk(b"sRGB", bytes([0])))
        f.write(_png_chunk(b"gAMA", struct.pack(">I", 45455)))
        f.write(_png_chunk(b"IDAT", zlib.compress(raw.tobytes(), PNG_COMPRESS_LEVEL)))
        f.write(_png_chunk(b"IEND", b""))


# ------------------------------------------------------------------ job build

def _serialize_layer(job_dir, index, update):
    """Write one layer's pixels as a PNG for Photoshop to open.

    Masks reuse the same RGBA PNG: the addon already stores a mask as grey in
    all three colour channels with full alpha, so filling the mask channel with
    it picks up the right luminance.
    """
    pixels = psd_engine._prepare_blender_pixels(
        update["pixels"], update["width"], update["height"]
    )

    filename = f"{index}.png"
    _write_rgba_png(os.path.join(job_dir, filename), pixels)

    return {
        "file": filename,
        "layer_id": int(update.get("layer_id") or 0),
        "layer_path": update.get("layer_path") or "",
        "name": update.get("name") or "",
        "is_mask": bool(update["is_mask"]),
    }


def push_updates(psd_path, updates, canvas_w, canvas_h, require_clean=True):
    """Stage a job and launch the JSX. Returns the job dir, or None."""
    root = bridge_root()

    try:
        os.makedirs(root, exist_ok=True)
        job_id = uuid.uuid4().hex
        job_dir = os.path.join(root, job_id)
        os.makedirs(job_dir)

        layers = []
        for i, update in enumerate(updates):
            if update.get("pixels") is None:
                continue
            layers.append(_serialize_layer(job_dir, i, update))

        if not layers:
            shutil.rmtree(job_dir, ignore_errors=True)
            return None

        job = {
            "version": 1,
            "job_id": job_id,
            "psd_path": psd_path,
            "canvas": {"w": int(canvas_w), "h": int(canvas_h)},
            "layers": layers,
            "save": True,
            "require_clean": bool(require_clean),
        }

        with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as f:
            json.dump(job, f)

        runner = os.path.join(_interop_dir(), "launch_push.vbs")
        jsx = os.path.join(_interop_dir(), "push_layers.jsx")
        subprocess.Popen(["wscript", runner, jsx, job_dir])

        _set_in_flight(True)
        return job_dir

    except Exception as e:
        print(f"BPSD Bridge: could not stage job: {e}")
        return None


# ------------------------------------------------------------------ polling

# Set between launching a job and handling its result. Photoshop's save lands
# in the middle of that window, so auto_sync_check has to be told to ignore the
# mtime bump it causes, and a second save must not race the live job.
_in_flight = False


def _set_in_flight(value):
    global _in_flight
    _in_flight = value


def job_in_flight():
    return _in_flight


def _read_result(job_dir):
    path = os.path.join(job_dir, "result.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Photoshop may still be mid-write; retry next tick.
        return None


def _read_fail(job_dir):
    path = os.path.join(job_dir, "fail.txt")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip() or "launch_failed"
    except Exception:
        return "launch_failed"


def start_poll(job_dir, on_done):
    """Watch a job without blocking Blender.

    on_done(result, reason) fires exactly once: reason is None on success.
    """
    deadline = time.monotonic() + JOB_TIMEOUT

    def finish(result, reason):
        _cleanup(job_dir)
        _set_in_flight(False)
        try:
            on_done(result, reason)
        except Exception as e:
            print(f"BPSD Bridge: result handler failed: {e}")

    def poll():
        result = _read_result(job_dir)
        if result is not None:
            finish(result, None if result.get("ok") else (result.get("reason") or "error"))
            return None

        failure = _read_fail(job_dir)
        if failure:
            finish(None, failure)
            return None

        if time.monotonic() > deadline:
            finish(None, "timeout")
            return None

        return POLL_INTERVAL

    bpy.app.timers.register(poll, first_interval=POLL_INTERVAL)


def _cleanup(job_dir):
    shutil.rmtree(job_dir, ignore_errors=True)


def cleanup_stale():
    """Drop job folders left behind by a crash or an abandoned session."""
    root = bridge_root()
    if not os.path.isdir(root):
        return

    now = time.time()
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        try:
            if now - os.path.getmtime(path) > STALE_JOB_AGE:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass
