# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""subscribe look -> latest frame -> VLM -> publish looked (DESIGN.md §5, §13 · T6.3).

Answers about its own frame only and never sends the frame: only text crosses
the wire (contracts/mqtt.md). The VLM is the node-local Qualcomm LLM/VLM
container (setup/ventuno-vlm/README.md) - an OpenAI-compatible endpoint on
:9001 serving ``qwen3_vl_4b_instruct`` on the Hexagon NPU - called through the
``openai`` client like every other OpenAI-compatible endpoint in the repo (§10).

The frame: prefer what ``vision.py`` exports to ``/dev/shm/qnet_<room>_frame.jpg``
when it is fresh (< ``--fresh-s``, default 3 s - a frame up to a second old is
fine for a stationary object, §13). When it is stale or missing, vision.py is
not running and the camera is therefore free, so grab one frame directly; a
stale export is the last resort. Every reply logs which source was used.
Downscaled to ~640 px before the VLM - §13's biggest single latency lever.

The reply discipline, from the frozen contract:

* ``qid`` is echoed exactly - the reply topics are shared, and the agent drops
  any answer whose qid is not the question it just asked, so a made-up or
  reused qid is an answer to nobody.
* ``room`` respected: ``null`` means every node answers; a named room means
  only that node (guide mode targets the room the person is standing in).
* VLM garbage - empty content (known first-call-after-restart quirk, retried
  once), non-JSON after a retry, wrong types - degrades to ``found=false``
  with an empty answer, logged, never a crash.
* No frame at all, or the VLM unreachable -> **no reply**: the agent then says
  "I couldn't reach the <room>", which is the truth. Answering found=false
  without having looked is exactly the silent lie §13 warns against.

The prompt/parse/trim helpers are pure - no cv2, no network - and unit-tested
on the laptop (``tests/test_look_logic.py``), same split as vision.py.

Run it on the node:

    ~/qnet-venv/bin/python -m qnet.node.look --room kitchen \
        --broker 10.73.51.175 --port 11883
"""

from __future__ import annotations

import argparse
import base64
import json
import queue
import sys
import threading
import time
from pathlib import Path

from qnet.node.vision import parse_source

# cv2, paho and openai are imported lazily (frame/publish/VLM only run on the
# node); everything the hermetic tests touch is stdlib-only.

DEFAULT_VLM_URL = "http://127.0.0.1:9001/v1"
DEFAULT_MODEL = "qwen3_vl_4b_instruct"  # the design's §11 model, w4a16 on the NPU
MAX_EDGE = 640  # §13: feed roughly 640 px, never the camera's native resolution
FRESH_S = 3.0  # shm export older than this means vision.py is not running

LOOK_TOPIC = "qnet/look"
STALE_LOOK_S = 15.0  # a queued look older than this answers a question nobody
                     # is waiting on any more (agent timeout is ~8 s) - dropped
WATCHDOG_S = 5.0  # how often the main thread checks the broker connection

# One JSON-only reply shape for both modes - proven against this exact
# container/model pair (setup/ventuno-vlm/README.md's validation), and the
# machine-parseable half of "one sentence, no rambling". The 4B model is terse
# by default, so the phrase requirement is spelled out - but deliberately with
# NO concrete example phrase: given one, the model parrots it verbatim into
# answers (observed live: a guide reply echoed the example word for word).
_FIND_PROMPT = (
    "You are a home assistant camera looking at one photo of a room. "
    "Is there a {object} visible in this photo? Reply with JSON only, no other "
    'text: {{"found": true/false, "answer": "if found, one short phrase saying '
    "where the {object} is relative to something obvious nearby, naming that "
    'nearby thing; empty string if not found"}}'
)
_GUIDE_PROMPT = (
    "You are a home assistant camera looking at one photo of a room. A person "
    "in this room is looking for their {object} and cannot see it. Reply with "
    'JSON only, no other text: {{"found": true/false, "answer": "if the '
    "{object} is visible, one short sentence guiding them to it, naming the "
    "obvious landmarks it is next to, on, or under; empty string if you "
    'cannot see it"}}'
)


# --------------------------------------------------------------------------
# Pure logic - prompt, parse, trim, routing. Unit-tested on the laptop.
# --------------------------------------------------------------------------


def build_prompt(obj: str, mode: str) -> str:
    """The VLM prompt for one look. Any mode that is not ``guide`` is a find."""
    template = _GUIDE_PROMPT if mode == "guide" else _FIND_PROMPT
    return template.format(object=obj.strip())


def one_sentence(text: str, limit: int = 160) -> str:
    """Post-trim to the contract's one sentence - the prompt asks, this enforces.

    Collapses whitespace, drops wrapping quotes, cuts after the first sentence
    terminator (``.!?`` followed by a space or the end, so "2.5 kg" survives),
    and hard-caps the length so a rambling model can never ramble on the wire.
    """
    text = " ".join(text.split()).strip().strip('"').strip()
    for i, ch in enumerate(text):
        if ch in ".!?" and (i + 1 == len(text) or text[i + 1] == " "):
            text = text[: i + 1]
            break
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def parse_reply(raw: str | None) -> tuple[bool, str] | None:
    """VLM text -> ``(found, answer)``, or None when it is not usable JSON.

    Extracts the outermost ``{...}`` (which also strips markdown fences and any
    prose around them), requires ``found`` to be a bool (the strings "true"/
    "false" are accepted - observed model behaviour), and coerces a missing or
    non-string ``answer`` to "". found=false forces ``answer`` to "" - a
    location for something not seen is by definition confabulated (observed
    live: the model filling it with a prompt example). The caller maps None
    to found=false.
    """
    if not raw:
        return None
    a, b = raw.find("{"), raw.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        obj = json.loads(raw[a : b + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    found = obj.get("found")
    if isinstance(found, str) and found.lower() in ("true", "false"):
        found = found.lower() == "true"
    if not isinstance(found, bool):
        return None
    if not found:
        return False, ""
    answer = obj.get("answer")
    return True, one_sentence(answer if isinstance(answer, str) else "")


def should_answer(payload: object, room: str) -> bool:
    """Is this ``look`` for us? Broadcast (room=null) or addressed to our room.

    Also the malformed-broadcast filter: no usable qid or object means there is
    nothing to echo and nothing to look for, so nothing to say.
    """
    if not isinstance(payload, dict):
        return False
    qid = payload.get("qid")
    obj = payload.get("object")
    if not isinstance(qid, str) or not qid:
        return False
    if not isinstance(obj, str) or not obj.strip():
        return False
    target = payload.get("room")
    return target is None or target == room


def build_looked(qid: str, room: str, found: bool, answer: str) -> dict:
    """The frozen ``looked`` payload (contracts/fixtures/looked.json) - qid echoed."""
    return {"qid": qid, "room": room, "found": bool(found), "answer": answer}


def choose_frame(age_s: float | None, fresh_s: float = FRESH_S) -> str:
    """``"shm"`` when the exported frame is fresh enough, else ``"camera"``.

    ``age_s`` is the export's age (None = no export exists). A stale export
    still beats no frame at all, but that fallback is the caller's last resort,
    not this decision - here stale means "vision.py is not running, the camera
    is free, prefer a *current* frame".
    """
    return "shm" if age_s is not None and age_s <= fresh_s else "camera"


# --------------------------------------------------------------------------
# Frame acquisition (needs cv2 - node only).
# --------------------------------------------------------------------------


def frame_age_s(path: Path, now: float | None = None) -> float | None:
    """Age of the shm export in seconds, or None if it does not exist."""
    try:
        return (time.time() if now is None else now) - path.stat().st_mtime
    except OSError:
        return None


def downscale_jpeg(frame, max_edge: int = MAX_EDGE, quality: int = 85) -> bytes:
    """BGR frame -> JPEG bytes with the long edge capped at ``max_edge`` (§13)."""
    import cv2

    h, w = frame.shape[:2]
    scale = max_edge / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("cv2.imencode failed")
    return jpg.tobytes()


def grab_camera_frame(source: str):
    """One frame straight from the camera, or None if it cannot be opened.

    Only called when vision.py's export is stale/missing, i.e. when nothing
    else holds the device. UVC cameras deliver dark frames while exposure
    settles, so a few are read and the last one kept.
    """
    import cv2

    cap = cv2.VideoCapture(parse_source(source))
    if not cap.isOpened():
        return None
    try:
        frame = None
        for _ in range(3):
            ok, f = cap.read()
            if ok:
                frame = f
        return frame
    finally:
        cap.release()


def acquire_jpeg(frame_path: Path, source: str, fresh_s: float, max_edge: int = MAX_EDGE) -> tuple[bytes, str] | None:
    """The freshest frame we can honestly get, as ≤``max_edge`` JPEG bytes.

    Returns ``(jpeg, used)`` where ``used`` names the source for the logs:
    ``shm`` (fresh export), ``camera`` (direct grab), ``shm-stale(<age>s)``
    (last resort). None means the node genuinely cannot see right now - the
    caller then stays silent and the agent reports the room unreachable.
    """
    import cv2
    import numpy as np

    age = frame_age_s(frame_path)
    if choose_frame(age, fresh_s) == "shm":
        frame = cv2.imdecode(np.fromfile(frame_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            return downscale_jpeg(frame, max_edge), "shm"
    frame = grab_camera_frame(source)
    if frame is not None:
        return downscale_jpeg(frame, max_edge), "camera"
    if age is not None:  # stale export beats no frame at all - flagged in the log
        frame = cv2.imdecode(np.fromfile(frame_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            return downscale_jpeg(frame, max_edge), f"shm-stale({age:.0f}s)"
    return None


# --------------------------------------------------------------------------
# The VLM call - OpenAI-compatible container on the node (§10's one client rule).
# --------------------------------------------------------------------------


class VlmClient:
    """One image + one question -> text, against the node-local container."""

    def __init__(self, base_url: str = DEFAULT_VLM_URL, model: str = DEFAULT_MODEL, timeout: float = 30.0):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key="unused", timeout=timeout)
        self.model = model

    def ask(self, prompt: str, jpeg: bytes, max_tokens: int = 96) -> str:
        """Standard OpenAI content-parts with a base64 data URL - the shape the
        container validated against. ``max_tokens`` bounds decode time: the JSON
        verdict is ~25 tokens, and decode is the latency that scales."""
        b64 = base64.b64encode(jpeg).decode("ascii")
        r = self.client.chat.completions.create(
            model=self.model,
            max_completion_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
                ],
            }],
        )
        return (r.choices[0].message.content or "").strip()


def answer_look(vlm: VlmClient, payload: dict, jpeg: bytes, room: str) -> dict:
    """One look -> one frozen ``looked`` payload. Never raises on VLM output.

    ``room`` is OUR room (node.yaml), never the broadcast's ``room`` field -
    that one is the *target* filter (null = everyone) and the reply must say
    which node answered. Two attempts: the first call after a container
    restart can return empty content (documented quirk), and a non-JSON reply
    gets one re-ask. Anything still unusable is found=false - logged by the
    caller, honest on the wire.
    """
    prompt = build_prompt(payload["object"], payload.get("mode", "find"))
    parsed = None
    for _ in range(2):
        raw = vlm.ask(prompt, jpeg)
        parsed = parse_reply(raw)
        if parsed is not None:
            break
        print(f"look: unusable VLM reply {raw[:120]!r} - retrying once", flush=True)
    found, answer = parsed if parsed is not None else (False, "")
    return build_looked(payload["qid"], room, found, answer)


# --------------------------------------------------------------------------
# The service.
# --------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qnet.node.look",
        description="answer qnet/look broadcasts from this room's own frame and VLM",
    )
    parser.add_argument("--config", default="config/house.yaml", help="house.yaml (mqtt, rooms, look block)")
    parser.add_argument("--node-config", default=None, help="node.yaml (room identity); default: next to --config")
    parser.add_argument("--room", default=None, help="room id; default: node.yaml's room")
    parser.add_argument("--broker", default=None, help="MQTT broker host (default: mqtt.host in house.yaml)")
    parser.add_argument("--port", type=int, default=None, help="MQTT broker port (default: mqtt.port)")
    parser.add_argument("--vlm-url", default=None, help=f"VLM endpoint (default: look.vlm_url, else {DEFAULT_VLM_URL})")
    parser.add_argument("--model", default=None, help=f"VLM model id (default: look.model, else {DEFAULT_MODEL})")
    parser.add_argument("--source", default=None, help="camera fallback source (default: rooms.<room>.source)")
    parser.add_argument("--frame-path", default=None, help="vision.py's export (default /dev/shm/qnet_<room>_frame.jpg)")
    parser.add_argument("--fresh-s", type=float, default=None, help=f"export age that still counts as live (default {FRESH_S})")
    parser.add_argument("--vlm-timeout", type=float, default=30.0, help="per-request VLM timeout seconds")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    house = _load_yaml(config_path)
    node = _load_yaml(Path(args.node_config) if args.node_config else config_path.with_name("node.yaml"))
    mqtt_cfg = house.get("mqtt", {}) or {}
    look_cfg = house.get("look", {}) or {}

    broker = args.broker or mqtt_cfg.get("host", "127.0.0.1")
    port = args.port or int(mqtt_cfg.get("port", 1883))
    room = args.room or node.get("room") or "kitchen"
    node_id = node.get("node_id") or f"{room}-01"
    vlm_url = args.vlm_url or look_cfg.get("vlm_url") or DEFAULT_VLM_URL
    model = args.model or look_cfg.get("model") or DEFAULT_MODEL
    fresh_s = args.fresh_s if args.fresh_s is not None else float(look_cfg.get("fresh_s", FRESH_S))
    source = args.source or (house.get("rooms", {}).get(room, {}) or {}).get("source") or "/dev/video0"
    frame_path = Path(args.frame_path or f"/dev/shm/qnet_{room}_frame.jpg")

    import paho.mqtt.client as mqtt

    vlm = VlmClient(vlm_url, model, timeout=args.vlm_timeout)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"look-{node_id}")
    inbox: queue.Queue = queue.Queue()

    # Three threads, deliberately: paho's network thread must never block (a
    # VLM call can stall for tens of seconds, which would starve the keepalive
    # and silently drop the subscription), so on_message only enqueues; a
    # worker does frame+VLM+publish; and the main thread is a watchdog,
    # because paho's own loop was observed wedged on this board - alive, no
    # socket, never reconnecting - after a Wi-Fi drop (verify/T6.3.txt).

    def on_connect(cl, userdata, flags, reason_code, properties=None):
        cl.subscribe(LOOK_TOPIC, qos=1)
        print(f"look: room={room} model={model} @ {vlm_url} frame={frame_path} "
              f"camera={source!r} -> {broker}:{port} (connected)", flush=True)

    def on_message(cl, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            print(f"look: non-JSON on {msg.topic}, ignored", flush=True)
            return
        if not should_answer(payload, room):
            print(f"look: not for us (room={payload.get('room')!r} qid={payload.get('qid')!r}), ignored", flush=True)
            return
        inbox.put((payload, time.monotonic()))

    def handle(payload: dict) -> None:
        t0 = time.perf_counter()
        got = acquire_jpeg(frame_path, source, fresh_s)
        if got is None:
            # No frame means we cannot honestly claim to have looked - stay
            # silent so the agent reports this room unreachable (§13).
            print(f"look: qid={payload['qid']} NO FRAME (export missing, camera unavailable) - not replying", flush=True)
            return
        jpeg, used = got
        t_frame = time.perf_counter() - t0
        reply = answer_look(vlm, payload, jpeg, room)
        client.publish(f"qnet/{room}/looked", json.dumps(reply), qos=1)
        print(f"look: qid={reply['qid']} object={payload['object']!r} mode={payload.get('mode', 'find')} "
              f"frame={used} ({t_frame:.2f}s) total={time.perf_counter() - t0:.2f}s "
              f"found={reply['found']} answer={reply['answer']!r}", flush=True)

    def worker() -> None:
        while True:
            payload, arrived = inbox.get()
            age = time.monotonic() - arrived
            if age > STALE_LOOK_S:
                # The agent stopped waiting long ago; a reply now is noise.
                print(f"look: qid={payload.get('qid')} arrived {age:.0f}s ago - dropped as stale", flush=True)
                continue
            try:
                handle(payload)
            except Exception as exc:  # noqa: BLE001 - a room node must outlive one bad query
                print(f"look: qid={payload.get('qid')} failed ({exc!r}) - not replying", flush=True)

    threading.Thread(target=worker, daemon=True, name="look-worker").start()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port, keepalive=30)
    client.loop_start()
    try:
        while True:
            time.sleep(WATCHDOG_S)
            if not client.is_connected():
                print("look: broker connection lost - forcing reconnect", flush=True)
                try:
                    client.reconnect()
                except Exception as exc:  # noqa: BLE001 - keep trying, forever
                    print(f"look: reconnect failed ({exc!r}) - retry in {WATCHDOG_S:g}s", flush=True)
    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()
        print("look: stopped", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
