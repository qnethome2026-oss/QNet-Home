# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Experimental fall-detection engine: IM SDK front half (T8.1, flagged OFF).

Same room-node contract as :mod:`qnet.node.vision` — same model, same
``decode``/``FallGate``, same MQTT payloads on the same topics — but the
front half (camera/clip capture, decode, letterbox resize, dashboard frame
export) runs inside a GStreamer pipeline built from the Qualcomm IM SDK
plugins instead of OpenCV:

    v4l2src/filesrc ! decodebin ! videoconvert ! NV12 ! tee
      ├─ qtimlvconverter (aspect-preserving centre letterbox)
      │    ! UINT8 (1,640,640,3) tensors ! fdsink  ──► this process
      └─ jpegenc ! multifilesink (dashboard preview export)

Python receives raw 640x640x3 uint8 frames over a pipe, does the two cheap
steps GStreamer cannot (float/255 + HWC→CHW, ~2 ms), and everything from
``qnn-net-run`` onward is byte-for-byte the mainline path.

Why uint8/NHWC and not the model's own float/NCHW: on the Ventuno's host
build, ``qtimlvconverter``'s float/planar output path emits all-zero tensors
(GLES engine cannot get a GPU context headless; the ocv fallback lacks the
planar conversion and segfaults on float; fcv is not compiled in). The
uint8/interleaved path — the one every stock IM SDK model exercises — was
verified good on real clips (setup/ventuno-imsdk/README.md has the whole
investigation). Hence the split.

Confidence floor: defaults to **0.45** (mainline: 0.5). The IM SDK
preprocessing reads systematically ~0.03-0.05 lower on fallen confidences
(pad-0 vs pad-114, NV12 chroma subsampling, different scaler); 0.45 restored
exact gate-fire parity on the fall-01 + adl-01 regression clips (Stage 2,
verify/T-imsdk-fall.txt). Override with ``--conf`` as usual.

This module must NEVER run alongside qnet-vision (both own the camera):
``infra/systemd/qnet-vision-imsdk.service`` carries ``Conflicts=`` both ways,
and ``scripts/bring_up.sh --imsdk`` is the supported switch.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from qnet.node.vision import (
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    INPUT_SIZE,
    FallGate,
    QnnRunner,
    classify_frame,
    decode,
    parse_source,
)

DETECTOR = "fall-yolo11n@imsdk-gst"
ENGINE = "imsdk"
IMSDK_CONF_FLOOR = 0.45  # measured offset vs mainline 0.5 - see module docstring
FRAME_BYTES = INPUT_SIZE * INPUT_SIZE * 3  # one UINT8 NHWC tensor off the pipe


# --------------------------------------------------------------------------
# Pure helpers - hermetically tested on the laptop (tests/test_vision_imsdk.py).
# --------------------------------------------------------------------------


def is_camera_path(target: str) -> bool:
    """Device node = camera; anything else (incl. /dev/shm/... files) = clip."""
    return target.startswith("/dev/") and not target.startswith("/dev/shm/")


def gst_source(source: str) -> str:
    """The DESIGN §8 source spellings -> the pipeline's source fragment.

    A ``v4l2src``/``filesrc`` spelling is honoured; a bare device node is a
    camera; anything else is a file. The two chains differ deliberately:

    * Files use the explicit ``qtdemux ! h264parse ! v4l2h264dec`` hardware
      chain with NV12 caps straight off the decoder — inserting a software
      ``videoconvert`` there breaks negotiation against the decoder's DMA
      buffers (measured: qtdemux "reason error (-5)"), and plain ``decodebin``
      auto-plugging fails the same way. Clips must therefore be H.264 mp4
      (``v4l2h264enc`` transcodes anything on the board in seconds).
    * Cameras deliver system-memory YUY2/MJPEG, where ``decodebin !
      videoconvert`` is the correct generic front.
    """
    target = str(parse_source(source))
    if is_camera_path(target):
        return f"v4l2src device={target} ! decodebin ! videoconvert"
    return f"filesrc location={target} ! qtdemux ! h264parse ! v4l2h264dec"


def gst_command(source: str, fd: int, preview_path: str) -> list[str]:
    """The full gst-launch argv. ``fd`` is the write end of our tensor pipe."""
    return [
        "gst-launch-1.0", "-q",
        *gst_source(source).split(),
        "!", "video/x-raw,format=NV12",
        "!", "tee", "name=t",
        "t.", "!", "queue", "!", "qtimlvconverter", "image-disposition=centre",
        "!", f"neural-network/tensors,type=UINT8,dimensions=(int)<<1,{INPUT_SIZE},{INPUT_SIZE},3>>",
        "!", "fdsink", f"fd={fd}", "sync=false",
        "t.", "!", "queue", "!", "videoconvert", "!", "jpegenc", "quality=80",
        "!", "multifilesink", f"location={preview_path}",
    ]


def frames_from_fd(fd: int, frame_bytes: int = FRAME_BYTES):
    """Yield exact ``frame_bytes`` chunks from ``fd`` until EOF.

    The pipe delivers arbitrary read sizes; a frame is complete only at
    ``frame_bytes``. A short final chunk (pipeline died mid-frame) is
    dropped, not yielded - callers restart the pipeline on EOF.
    """
    buf = bytearray()
    while True:
        chunk = os.read(fd, 1 << 20)
        if not chunk:
            return
        buf += chunk
        while len(buf) >= frame_bytes:
            yield bytes(buf[:frame_bytes])
            del buf[:frame_bytes]


def tensor_from_frame(frame: bytes) -> np.ndarray:
    """One UINT8 NHWC frame off the pipe -> float32 NCHW (1,3,640,640), 0-1.

    The two steps GStreamer's working path cannot do for this model; they are
    the entire Python share of preprocessing (~2 ms).
    """
    hwc = np.frombuffer(frame, dtype=np.uint8).reshape(INPUT_SIZE, INPUT_SIZE, 3)
    return np.ascontiguousarray(hwc.transpose(2, 0, 1)[None].astype(np.float32) / 255.0)


# --------------------------------------------------------------------------
# The service.
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qnet.node.vision_imsdk",
        description="EXPERIMENTAL fall detection - IM SDK GStreamer front half (flag-gated; mainline is qnet.node.vision)",
    )
    parser.add_argument("--room", default="kitchen")
    parser.add_argument("--source", required=True, help="v4l2src/filesrc string, device path or file")
    parser.add_argument("--broker", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--conf", type=float, default=IMSDK_CONF_FLOOR,
                        help=f"confidence floor (default {IMSDK_CONF_FLOOR}; mainline uses 0.5 - see docstring)")
    parser.add_argument("--fire-on", default="5/8")
    parser.add_argument("--rearm-after", type=float, default=60.0)
    parser.add_argument("--rearm-frames", type=int, default=8)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--node-id", default=None)
    parser.add_argument("--frame-path", default=None)
    parser.add_argument("--heartbeat", type=float, default=5.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if shutil.which("gst-launch-1.0") is None:
        print("vision_imsdk: gst-launch-1.0 not found (this engine runs on the board)", file=sys.stderr)
        return 2

    import paho.mqtt.client as mqtt

    from qnet.ids import new_ulid

    room = args.room
    node_id = args.node_id or f"{room}-01"
    n, m = (int(x) for x in args.fire_on.split("/"))
    frame_path = Path(args.frame_path or f"/dev/shm/qnet_{room}_frame.jpg")
    preview_tmp = frame_path.with_name(frame_path.stem + "_imsdk.jpg")
    is_camera = is_camera_path(str(parse_source(args.source)))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"vision-imsdk-{node_id}")
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    runner = QnnRunner(args.model, args.backend)
    gate = FallGate(n, m, args.rearm_after, args.rearm_frames)

    print(f"vision_imsdk: room={room} source={args.source!r} conf>={args.conf} rule={n}/{m} "
          f"batch={args.batch} -> {args.broker}:{args.port} [EXPERIMENTAL {ENGINE} engine]", flush=True)

    started = time.monotonic()
    last_beat = last_mirror = 0.0
    frames = events = 0
    t_infer = 0.0
    pending: list[np.ndarray] = []

    def heartbeat(now: float) -> None:
        nonlocal last_beat
        last_beat = now
        client.publish(f"qnet/{room}/status", json.dumps({
            "node": node_id,
            "room": room,
            "ts": time.time(),
            "state": gate.state,
            "fps": round(frames / (now - started), 2) if now > started else 0.0,
            "frames": frames,
            "detector": DETECTOR,
        }), qos=0)

    def mirror_preview(now: float) -> None:
        """Publish the tee's newest JPEG under the canonical frame path.

        multifilesink rewrites its file in place (torn reads possible), so the
        canonical path look/stream consume gets an os.replace'd copy instead.
        """
        nonlocal last_mirror
        if now - last_mirror < 0.5 or not preview_tmp.is_file():
            return
        last_mirror = now
        staging = frame_path.with_name(frame_path.name + ".tmp")
        try:
            staging.write_bytes(preview_tmp.read_bytes())
            os.replace(staging, frame_path)
        except OSError:
            pass  # preview is best-effort; detection must not die for it

    def flush_batch() -> None:
        nonlocal frames, events, t_infer
        if not pending:
            return
        t0 = time.perf_counter()
        outputs = runner.infer(pending)
        t_infer += time.perf_counter() - t0
        for raw in outputs:
            dets = decode(raw, args.conf)
            fallen_conf, upright = classify_frame(dets)
            fired = gate.update(fallen_conf, upright)
            frames += 1
            if args.verbose:
                best = max(dets, key=lambda d: d.conf, default=None)
                print(f"  frame {frames}: " + (f"{best.name} {best.conf:.2f}" if best else "no detection")
                      + (" -> FIRE" if fired else ""), flush=True)
            if fired:
                events += 1
                client.publish(f"qnet/{room}/event", json.dumps({
                    "id": new_ulid(),
                    "ts": time.time(),
                    "room": room,
                    "kind": "fall.detected",
                    "conf": fired.conf,
                    "meta": {"cls": "Fallen", "frames": fired.frames, "engine": ENGINE},
                }), qos=1)
                print(f"vision_imsdk: fall.detected #{events} conf={fired.conf} ({fired.frames})", flush=True)
        pending.clear()

    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    cmd = gst_command(args.source, write_fd, str(preview_tmp))
    if args.verbose:
        print("vision_imsdk: " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, pass_fds=(write_fd,),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(write_fd)  # ours would keep the pipe open past pipeline death

    try:
        heartbeat(time.monotonic())
        for frame in frames_from_fd(read_fd):
            pending.append(tensor_from_frame(frame))
            if len(pending) >= args.batch:
                flush_batch()
            now = time.monotonic()
            if now - last_beat >= args.heartbeat:
                heartbeat(now)
            mirror_preview(now)
            if args.max_frames and frames + len(pending) >= args.max_frames:
                break
        # EOF: normal end for a clip; for a camera the pipeline died - the
        # systemd unit's Restart= brings the whole engine back clean.
        if is_camera:
            print("vision_imsdk: pipeline ended unexpectedly (camera source) - exiting for restart",
                  file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        flush_batch()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.close(read_fd)
        elapsed = time.monotonic() - started
        if frames:
            print(f"vision_imsdk: {frames} frames in {elapsed:.1f}s = {frames / elapsed:.2f} fps | "
                  f"npu(spawn+io+infer) {1000 * t_infer / frames:.1f} ms/frame | events: {events}", flush=True)
        client.loop_stop()
        client.disconnect()
    return 0 if not is_camera else 1  # camera EOF is a failure -> systemd restarts


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
