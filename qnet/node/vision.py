# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""camera -> fall model -> temporal check -> publish (DESIGN.md §5, §8 · T4.2).

Owns the camera. The source is a config string, so a live camera and a recorded
clip run the *same* code path (§8): ``v4l2src device=/dev/video0``, ``filesrc
location=clips/fall01.mp4 ! decodebin``, a bare file path, or a bare device
index all work - parsed here, opened with ``cv2.VideoCapture``.

The model is the YOLO11n fall fine-tune (fallen / sitting / standing), compiled
to a QNN context binary and run on the Hexagon NPU via ``qnn-net-run`` - a CLI,
so every inference pays process spawn + file IO on top of the 34.8 ms execute
(``models/fall-detection/README.md``). That cost is measured and reported, not
hidden; ``--batch`` amortises it over several frames per invocation when
throughput matters more than per-frame latency. There is deliberately no CPU
fallback: the NPU path is the point, and a silent fallback would fake the
latency numbers.

The raw head is ``(1, 7, 8400)`` - 4 box coords + 3 class scores, no NMS, no
objectness - so the letterbox preproc, decode and NMS live here. They are pure
numpy on purpose: the laptop test suite exercises them against a recorded
output tensor with no cv2, no NPU and no camera (``tests/test_vision_logic.py``).

What it publishes (contracts/mqtt.md):

* ``qnet/<room>/event`` - ``fall.detected``, QoS 1, only when the temporal rule
  says so: ``fallen`` in >= N of the last M processed frames (default 5-of-8),
  fire-once, then re-arm after ``rearm_after_s`` OR after ``rearm_frames``
  consecutive upright (sitting/standing) frames. ``conf`` is the median fallen
  confidence over the window that fired.
* ``qnet/<room>/status`` - heartbeat, QoS 0, every 5 s. T0.1 left this payload
  unfrozen ("settled in T4.2"); the shape emitted here is the settlement and is
  recorded in contracts/mqtt.md.

It also writes the newest frame to ``/dev/shm/qnet_<room>_frame.jpg`` (write to
a temp name, ``os.replace`` - readers never see a torn file) so ``look.py``
reads that instead of opening a second capture (§5).

Run it on the node:

    ~/qnet-venv/bin/python -m qnet.node.vision --room kitchen \
        --source "filesrc location=clips/fall01.mp4 ! decodebin" \
        --broker 127.0.0.1 --port 1883
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# cv2 and paho are imported lazily (capture/publish only run on the node);
# everything the hermetic tests touch needs numpy alone.

CLASSES = ("fallen", "sitting", "standing")  # model class ids 0, 1, 2
CLS_FALLEN = 0
INPUT_SIZE = 640  # the model's fixed input edge (NCHW 1x3x640x640)

# On-board defaults - the verified runbook paths (models/fall-detection/README.md).
DEFAULT_MODEL = "/data/local/tmp/quad/models/best.bin"
DEFAULT_BACKEND = "/usr/lib/libQnnHtp.so"


# --------------------------------------------------------------------------
# Pure geometry + decode - no cv2, no IO, unit-tested on the laptop.
# --------------------------------------------------------------------------


def letterbox_params(w: int, h: int, size: int = INPUT_SIZE) -> tuple[float, int, int]:
    """Scale and top-left padding that fit ``w x h`` into ``size x size``.

    Standard YOLO letterbox: uniform scale, centre the result, pad the rest.
    Returned as ``(scale, pad_x, pad_y)`` so boxes can be mapped back with
    :func:`unletterbox_box` - one function computes it, both directions use it.
    """
    scale = min(size / w, size / h)
    new_w, new_h = round(w * scale), round(h * scale)
    return scale, (size - new_w) // 2, (size - new_h) // 2


def unletterbox_box(
    box: tuple[float, float, float, float], scale: float, pad_x: int, pad_y: int
) -> tuple[float, float, float, float]:
    """Map an ``(x1, y1, x2, y2)`` box from model space back to source pixels."""
    x1, y1, x2, y2 = box
    return ((x1 - pad_x) / scale, (y1 - pad_y) / scale, (x2 - pad_x) / scale, (y2 - pad_y) / scale)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_floor: float = 0.45) -> list[int]:
    """Greedy IoU suppression over ``(N, 4)`` xyxy boxes. Returns kept indices.

    Plain numpy - 8400 candidates collapse to a handful after the confidence
    floor, so O(n^2) here is microseconds, not a bottleneck.
    """
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    area = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = np.argsort(scores)[::-1]
    keep: list[int] = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        rest = order[1:]
        iw = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        ih = np.maximum(0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = iw * ih
        iou = inter / (area[i] + area[rest] - inter + 1e-9)
        order = rest[iou <= iou_floor]
    return keep


@dataclass(frozen=True)
class Detection:
    """One decoded box, in model (640x640 letterboxed) pixel space."""

    cls: int  # index into CLASSES
    conf: float  # class score - YOLO11 has no separate objectness
    box: tuple[float, float, float, float]  # x1, y1, x2, y2

    @property
    def name(self) -> str:
        return CLASSES[self.cls]


def decode(raw: np.ndarray, conf_floor: float, iou_floor: float = 0.45) -> list[Detection]:
    """Raw ``(1, 7, 8400)`` YOLO11 head -> per-class-NMS'd detections.

    Rows 0-3 are cx, cy, w, h in input pixels; rows 4-6 are the three class
    scores, already sigmoided by the exported graph. Confidence is the class
    score - no objectness row exists in this head.
    """
    p = raw.reshape(7, -1)
    scores = p[4:7]  # (3, 8400)
    cls = scores.argmax(axis=0)
    conf = scores.max(axis=0)
    mask = conf >= conf_floor
    if not mask.any():
        return []
    cx, cy, w, h = (row[mask] for row in p[:4])
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    cls, conf = cls[mask], conf[mask]
    # Class-aware NMS via the coordinate-offset trick: shift each class into
    # its own disjoint region so one greedy pass never suppresses across classes.
    offset = cls.astype(np.float32)[:, None] * (INPUT_SIZE * 2.0)
    keep = nms(boxes + offset, conf, iou_floor)
    return [
        Detection(int(cls[i]), float(conf[i]), tuple(float(v) for v in boxes[i]))
        for i in keep
    ]


# --------------------------------------------------------------------------
# The temporal rule - N-of-M, fire-once, re-arm. Pure state, unit-tested.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Fired:
    """What the gate hands back the moment the rule fires."""

    conf: float  # median fallen confidence over the window (contracts/mqtt.md)
    frames: str  # the N-of-M rule that fired, e.g. "5/8"


class FallGate:
    """DESIGN §8's temporal check and fire-once logic, one frame at a time.

    Single-frame classifiers flicker, so ``fall.detected`` fires only when
    ``fallen`` appears in >= *n* of the last *m* processed frames. A fallen
    person keeps matching, so after firing the gate goes quiet ("holdoff") and
    re-arms only when either ``rearm_after_s`` elapses or the person is seen
    upright (sitting/standing) for ``rearm_frames`` consecutive frames. On
    re-arm the window is cleared: a fresh event needs fresh evidence, not the
    stale frames that fired the last one.
    """

    def __init__(
        self,
        n: int = 5,
        m: int = 8,
        rearm_after_s: float = 60.0,
        rearm_frames: int = 8,
    ) -> None:
        if not 0 < n <= m:
            raise ValueError(f"need 0 < n <= m, got {n}/{m}")
        self.n, self.m = n, m
        self.rearm_after_s = rearm_after_s
        self.rearm_frames = rearm_frames
        self.window: deque[tuple[bool, float]] = deque(maxlen=m)  # (fallen?, conf)
        self.state = "armed"  # "armed" | "holdoff"
        self.fired_at = 0.0
        self.upright_streak = 0

    def update(self, fallen_conf: float | None, upright: bool, now: float | None = None) -> Fired | None:
        """Feed one processed frame; returns a :class:`Fired` iff the rule fires.

        ``fallen_conf`` is the best above-floor fallen confidence in the frame
        (None if none), ``upright`` is whether the frame instead showed a
        sitting/standing person above the floor.
        """
        now = time.monotonic() if now is None else now

        if self.state == "holdoff":
            # Cooldown re-arm: if they are STILL down when it elapses, the
            # window refills and a reminder event fires ~m frames later -
            # deliberate (§8: armed-but-quiet until upright OR 60 s).
            if now - self.fired_at >= self.rearm_after_s:
                self._rearm()
            else:
                self.upright_streak = self.upright_streak + 1 if upright else 0
                if self.upright_streak >= self.rearm_frames:
                    self._rearm()
                else:
                    return None

        self.window.append((fallen_conf is not None, fallen_conf or 0.0))
        fallen = [conf for hit, conf in self.window if hit]
        if len(fallen) >= self.n:
            self.state = "holdoff"
            self.fired_at = now
            self.upright_streak = 0
            return Fired(conf=round(statistics.median(fallen), 4), frames=f"{self.n}/{self.m}")
        return None

    def _rearm(self) -> None:
        self.state = "armed"
        self.window.clear()
        self.upright_streak = 0


def classify_frame(dets: list[Detection]) -> tuple[float | None, bool]:
    """A frame's verdict for the gate: (best fallen conf | None, upright?).

    ``fallen`` wins over ``sitting``/``standing`` when both are present - a
    frame with any above-floor fallen detection is a fallen frame, full stop.
    """
    fallen = [d.conf for d in dets if d.cls == CLS_FALLEN]
    if fallen:
        return max(fallen), False
    return None, any(d.cls != CLS_FALLEN for d in dets)


# --------------------------------------------------------------------------
# Preprocessing (needs cv2 - node only).
# --------------------------------------------------------------------------


def preprocess(frame_bgr: np.ndarray, size: int = INPUT_SIZE) -> tuple[np.ndarray, tuple[float, int, int]]:
    """BGR frame -> float32 NCHW ``(1, 3, size, size)`` + letterbox params.

    Matches Ultralytics' preproc for this export: letterbox on gray (114),
    BGR->RGB, scale to 0-1. The params come back so decoded boxes can be
    mapped to source pixels.
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    scale, pad_x, pad_y = letterbox_params(w, h, size)
    resized = cv2.resize(frame_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y : pad_y + resized.shape[0], pad_x : pad_x + resized.shape[1]] = resized
    nchw = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(nchw), (scale, pad_x, pad_y)


# --------------------------------------------------------------------------
# NPU runner - qnn-net-run as a subprocess, files in /dev/shm.
# --------------------------------------------------------------------------


class QnnRunner:
    """Runs the QNN context binary via ``qnn-net-run``, one subprocess per call.

    The CLI reloads the context binary every invocation (~50 ms init) on top of
    process spawn and raw-file IO - that is the honest cost of not having
    onnxruntime/QNN bindings on the board, and it is what ``--batch`` amortises:
    an input_list with K lines runs K inferences in one process. The workdir
    lives in ``/dev/shm`` so the per-frame 4.9 MB input never touches flash.
    """

    def __init__(self, model: str = DEFAULT_MODEL, backend: str = DEFAULT_BACKEND, workdir: str | None = None):
        self.model = model
        self.backend = backend
        self.workdir = Path(workdir or (Path("/dev/shm") if Path("/dev/shm").is_dir() else Path(tempfile.gettempdir())) / "qnet_vision")
        self.workdir.mkdir(parents=True, exist_ok=True)
        if not Path(model).is_file():
            raise FileNotFoundError(f"QNN context binary not found: {model}")
        if shutil.which("qnn-net-run") is None:
            raise FileNotFoundError("qnn-net-run not on PATH (apt install qairt-tools)")

    def infer(self, batch: list[np.ndarray], retries: int = 2) -> list[np.ndarray]:
        """K float32 NCHW frames -> K raw ``(1, 7, 8400)`` outputs, one process.

        Retries transient failures: the NPU is shared (a teammate's VLM
        container serves on the same Hexagon), and qnn-net-run occasionally
        loses the fastrpc race and dies - observed live on the Ventuno Q, and
        the identical invocation succeeds immediately after. A room node must
        outlive that, so only a *persistent* failure propagates.
        """
        lines = []
        for i, nchw in enumerate(batch):
            raw = self.workdir / f"input_{i}.raw"
            nchw.astype(np.float32).tofile(raw)
            lines.append(f"images:={raw}")
        (self.workdir / "input_list.txt").write_text("\n".join(lines) + "\n")
        out_dir = self.workdir / "out"
        cmd = [
            "qnn-net-run",
            "--backend", self.backend,
            "--retrieve_context", self.model,
            "--input_list", str(self.workdir / "input_list.txt"),
            "--output_dir", str(out_dir),
        ]
        for attempt in range(retries + 1):
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                break
            if attempt == retries:
                raise RuntimeError(
                    f"qnn-net-run failed {retries + 1}x (rc={proc.returncode}): "
                    f"{proc.stdout[-400:]}{proc.stderr[-400:]}"
                )
            time.sleep(0.2)
        outputs = []
        for i in range(len(batch)):
            raw = np.fromfile(out_dir / f"Result_{i}" / "output_0.raw", dtype=np.float32)
            outputs.append(raw.reshape(1, 7, 8400))
        return outputs


# --------------------------------------------------------------------------
# Source parsing - one config string, three spellings (§8).
# --------------------------------------------------------------------------


def parse_source(source: str) -> str | int:
    """A config source string -> what ``cv2.VideoCapture`` should open.

    Accepts the DESIGN §8 GStreamer spellings without needing a GStreamer
    build of OpenCV (the pip ``opencv-python-headless`` wheel has none):
    ``v4l2src device=/dev/videoN`` -> the device path, ``filesrc
    location=path ! decodebin`` -> the path. A bare integer string is a
    camera index; anything else is a path, handed over untouched.
    """
    s = source.strip()
    for token in s.split():
        if token.startswith("device="):
            return token.removeprefix("device=")
        if token.startswith("location="):
            return token.removeprefix("location=")
    if s.isdigit():
        return int(s)
    return s


def open_source(source: str):
    """Open the parsed source; raises if it will not deliver frames."""
    import cv2

    target = parse_source(source)
    cap = cv2.VideoCapture(target)
    if not cap.isOpened():
        raise RuntimeError(f"could not open source {target!r} (from {source!r})")
    return cap


# --------------------------------------------------------------------------
# The service.
# --------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _atomic_write(path: Path, data: bytes) -> None:
    """Write-then-rename so a concurrent reader (look.py) never sees a torn file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qnet.node.vision",
        description="fall detection on the room node - camera/clip -> NPU -> qnet/<room>/event",
    )
    parser.add_argument("--config", default="config/house.yaml", help="house.yaml (thresholds, room sources)")
    parser.add_argument("--node-config", default=None, help="node.yaml (room identity); default: next to --config")
    parser.add_argument("--room", default=None, help="room id; default: node.yaml's room")
    parser.add_argument("--source", default=None, help="v4l2src/filesrc string, device path, index or file")
    parser.add_argument("--broker", default=None, help="MQTT broker host (default: mqtt.host in house.yaml)")
    parser.add_argument("--port", type=int, default=None, help="MQTT broker port (default: mqtt.port)")
    parser.add_argument("--conf", type=float, default=None, help="confidence floor (default: vision.conf_floor, else 0.5)")
    parser.add_argument("--fire-on", default=None, help='temporal rule "N/M" (default: vision.fire_on, else 5/8)')
    parser.add_argument("--rearm-after", type=float, default=None, help="cooldown seconds (default: vision.rearm_after_s, else 60)")
    parser.add_argument("--rearm-frames", type=int, default=None, help="consecutive upright frames that re-arm (default: vision.rearm_frames, else 8)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="QNN context binary")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="QNN backend .so")
    parser.add_argument("--batch", type=int, default=1, help="frames per qnn-net-run invocation (amortises spawn cost)")
    parser.add_argument("--stride", type=int, default=1, help="process every Nth frame of a file source")
    parser.add_argument("--max-frames", type=int, default=0, help="stop after N processed frames (0 = run forever / to EOF)")
    parser.add_argument("--frame-path", default=None, help="latest-frame JPEG path (default /dev/shm/qnet_<room>_frame.jpg)")
    parser.add_argument("--heartbeat", type=float, default=5.0, help="status interval seconds")
    parser.add_argument("--verbose", action="store_true", help="per-frame decode log")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    house = _load_yaml(config_path)
    node = _load_yaml(Path(args.node_config) if args.node_config else config_path.with_name("node.yaml"))
    vision_cfg = house.get("vision", {}) or {}
    mqtt_cfg = house.get("mqtt", {}) or {}

    broker = args.broker or mqtt_cfg.get("host", "127.0.0.1")
    port = args.port or int(mqtt_cfg.get("port", 1883))
    room = args.room or node.get("room") or "kitchen"
    node_id = node.get("node_id") or f"{room}-01"
    source = args.source or (house.get("rooms", {}).get(room, {}) or {}).get("source") or "/dev/video0"
    conf_floor = args.conf if args.conf is not None else float(vision_cfg.get("conf_floor", 0.5))
    fire_on = args.fire_on or str(vision_cfg.get("fire_on", "5/8"))
    n, m = (int(x) for x in fire_on.split("/"))
    rearm_after = args.rearm_after if args.rearm_after is not None else float(vision_cfg.get("rearm_after_s", 60.0))
    rearm_frames = args.rearm_frames if args.rearm_frames is not None else int(vision_cfg.get("rearm_frames", 8))
    frame_path = Path(args.frame_path or f"/dev/shm/qnet_{room}_frame.jpg")

    import cv2
    import paho.mqtt.client as mqtt

    from qnet.ids import new_ulid

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"vision-{node_id}")
    client.connect(broker, port, keepalive=30)
    client.loop_start()

    runner = QnnRunner(args.model, args.backend)
    gate = FallGate(n, m, rearm_after, rearm_frames)
    cap = open_source(source)
    is_file = not (isinstance(parse_source(source), int) or str(parse_source(source)).startswith("/dev/"))

    print(f"vision: room={room} source={source!r} conf>={conf_floor} rule={n}/{m} "
          f"rearm={rearm_after:g}s|{rearm_frames}f batch={args.batch} -> {broker}:{port}", flush=True)

    started = time.monotonic()
    last_beat = 0.0
    frames = events = 0
    t_pre = t_infer = t_decode = 0.0
    pending: list[tuple[np.ndarray, np.ndarray]] = []  # (frame, nchw) awaiting a batch

    def heartbeat(now: float) -> None:
        # Settled in T4.2 (contracts/mqtt.md): identity + liveness + the two
        # numbers worth graphing. QoS 0 - the next beat is 5 s away.
        nonlocal last_beat
        last_beat = now
        client.publish(f"qnet/{room}/status", json.dumps({
            "node": node_id,
            "room": room,
            "ts": time.time(),
            "state": gate.state,
            "fps": round(frames / (now - started), 2) if now > started else 0.0,
            "frames": frames,
            "detector": "fall-yolo11n@hexagon-npu",
        }), qos=0)

    def flush_batch() -> None:
        """Run the pending frames through the NPU and the gate, publish as needed."""
        nonlocal frames, events, t_infer, t_decode
        if not pending:
            return
        t0 = time.perf_counter()
        outputs = runner.infer([nchw for _, nchw in pending])
        t_infer += time.perf_counter() - t0
        for (frame, _), raw in zip(pending, outputs):
            t1 = time.perf_counter()
            dets = decode(raw, conf_floor)
            fallen_conf, upright = classify_frame(dets)
            fired = gate.update(fallen_conf, upright)
            t_decode += time.perf_counter() - t1
            frames += 1
            if args.verbose:
                best = max(dets, key=lambda d: d.conf, default=None)
                print(f"  frame {frames}: " + (f"{best.name} {best.conf:.2f}" if best else "no detection")
                      + (" -> FIRE" if fired else ""), flush=True)
            if fired:
                events += 1
                payload = {
                    "id": new_ulid(),
                    "ts": time.time(),
                    "room": room,
                    "kind": "fall.detected",
                    "conf": fired.conf,
                    "meta": {"cls": "Fallen", "frames": fired.frames},
                }
                client.publish(f"qnet/{room}/event", json.dumps(payload), qos=1)
                print(f"vision: fall.detected #{events} conf={fired.conf} ({fired.frames})", flush=True)
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                _atomic_write(frame_path, jpg.tobytes())
        pending.clear()

    grabbed = 0
    try:
        heartbeat(time.monotonic())
        while True:
            ok, frame = cap.read()
            if not ok:
                if is_file:
                    break  # EOF - flush and summarise
                time.sleep(0.1)  # camera hiccup: keep the service alive
                continue
            grabbed += 1
            if is_file and args.stride > 1 and (grabbed - 1) % args.stride:
                continue
            t0 = time.perf_counter()
            nchw, _ = preprocess(frame)
            t_pre += time.perf_counter() - t0
            pending.append((frame, nchw))
            if len(pending) >= args.batch:
                flush_batch()
            now = time.monotonic()
            if now - last_beat >= args.heartbeat:
                heartbeat(now)
            if args.max_frames and frames + len(pending) >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        flush_batch()
        cap.release()
        elapsed = time.monotonic() - started
        if frames:
            print(
                f"vision: {frames} frames in {elapsed:.1f}s = {frames / elapsed:.2f} fps | "
                f"per frame: pre {1000 * t_pre / frames:.1f} ms, "
                f"npu(spawn+io+infer) {1000 * t_infer / frames:.1f} ms, "
                f"decode {1000 * t_decode / frames:.1f} ms | events: {events}",
                flush=True,
            )
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
