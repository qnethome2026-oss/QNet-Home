#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Replay a recorded session as live MQTT publishes (T5.2, DESIGN.md §6/§14).

Takes a session ``.jsonl`` file - the exact per-line shape ``run_phase``
appends (§6: ``{"ts":..., "event": "detected"|"say"|"heard"|"phase"|"tool"|
"refusal", ...}``) - and republishes it onto the bus at configurable speed, so
the dashboard (``dashboard/index.html``) can be demoed from a recording with
no agent, no broker-side state and no live incident required.

For each line, two things happen, matching what the real engine does live
(``qnet.agent.engine.Agent.append``/``.say`` - one stream, multiple
destinations, §6):

1. The line is appended to a **cumulative** in-memory log and the *whole*
   session document (``id``, ``room``, ``skill``, ``urgency``, ``phase``,
   ``state``, ``log``) is republished to ``qnet/session/<id>`` - never just
   the new line, because §4 says sessions are published FULL so the dashboard
   never has to reconstruct anything.
2. ``detected``/``say``/``heard`` lines *additionally* get the matching
   room topic (``qnet/<room>/event|say|heard``) - the same room-facing
   messages the real node/agent would have produced. ``phase``/``tool``/
   ``refusal``/``brief`` lines have no room-facing topic in the contract
   (contracts/mqtt.md) - they only ever appear inside the session log.

Session-level fields (``room``, ``skill``, ``urgency``) aren't repeated on
every JSONL line - by design, the file is one room/skill/run (§6's
``<room>__<skill>__<started_at>.jsonl`` naming). This script recovers them
from the filename when it matches that convention, and falls back to
``--room``/``--skill``/``--urgency`` (or a safe default) otherwise - which is
exactly the case for the synthetic demo fixture at
``dev/fixtures/replay_demo.jsonl`` (T5.2: a hand-written fixture, not a real
recording, because no session file existed in ``data/sessions/`` for a
non-fall-response run and running another lane's live G2 script mid-build was
out of scope for this task).

``session.phase`` while the session is open mirrors ``engine.py``'s own rule:
a non-terminal ``phase`` line's ``to`` becomes the new phase; a *terminal*
``to`` (``ok``/``found``/``not_found``/``done``/``resolved``/``closed``/
``cancelled`` - ``qnet.agent.phases.TERMINAL_EXITS``) closes the session
(``state`` becomes ``cancelled`` for the literal ``cancelled`` exit,
``closed`` otherwise) and leaves ``phase`` on whatever it last was - the
engine never "enters" a phase that doesn't exist.

    python dev/replay_session.py data/sessions/kitchen__fall-response__2026-08-05T13-21-32.jsonl --speed 10
    python dev/replay_session.py dev/fixtures/replay_demo.jsonl --speed 20 --room bedroom --skill fall-response

Uses ``paho-mqtt`` the same way ``dev/inject.py`` does - connect, publish at
QoS 1 (contracts/mqtt.md: everything that carries a decision or a person's
words is QoS 1), disconnect.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from qnet.ids import new_ulid

# qnet.agent.phases.TERMINAL_EXITS, duplicated rather than imported: this dev
# tool has no business depending on the engine's internals, only on the wire
# shape (§4/§6) they both implement independently.
TERMINAL_EXITS = frozenset({"ok", "found", "not_found", "done", "resolved", "closed", "cancelled"})
CANCELLED = "cancelled"

# The phase a session starts in, per each shipped skill file (DESIGN §7, §13)
# - used only when the filename/CLI don't already pin ``--room``/``--skill``
# far enough to know it another way. Extend this if a third skill ships.
FIRST_PHASE = {"fall-response": "check", "find-object": "search"}
DEFAULT_URGENCY = {"fall-response": "safety", "find-object": "routine"}

# ``<room>__<skill>__<started_at ISO8601-with-hyphens>.jsonl`` - session_path()
# in qnet/agent/engine.py, verbatim.
FILENAME_RE = re.compile(r"^(?P<room>[^_]+)__(?P<skill>[a-z0-9-]+)__(?P<started>[0-9T-]+)\.jsonl$")


def parse_filename(name: str) -> tuple[str | None, str | None]:
    """``(room, skill)`` from the standard session filename, or ``(None, None)``."""
    match = FILENAME_RE.match(name)
    if not match:
        return None, None
    return match.group("room"), match.group("skill")


def say_prio(text: str) -> str:
    """Best-effort ``say.prio`` (§4: ``safety`` | ``comfort``) - the JSONL log
    line doesn't carry it (only ``text`` does, §6), so this recognises the
    comfort loop's own grounded-update opener (``engine.comfort_line``)."""
    return "comfort" if text.startswith("I'm still here with you") else "safety"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python dev/replay_session.py",
        description="Replay a recorded session .jsonl as live MQTT publishes.",
    )
    parser.add_argument("session_file", type=Path, help="path to a session .jsonl (one JSON object per line, §6)")
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier (default 1.0; --speed 10 = 10x real time)")
    parser.add_argument("--broker", default="127.0.0.1", metavar="HOST")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--room", default=None, help="override the room (default: parsed from the filename)")
    parser.add_argument("--skill", default=None, help="override the skill (default: parsed from the filename)")
    parser.add_argument("--urgency", choices=["safety", "routine"], default=None,
                         help="override urgency (default: safety for fall-response, routine otherwise)")
    parser.add_argument("--quiet", action="store_true", help="don't print each publish")
    return parser


def load_lines(path: Path) -> list[dict]:
    """Every non-blank line, parsed as one JSON object - a bad line is a hard error.

    Replaying garbage as though it were a real session would defeat the whole
    point of this tool (dashboard verification), so this never skips a
    malformed line silently.
    """
    lines: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"replay: {path}:{lineno}: not valid JSON: {exc}") from exc
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.session_file.exists():
        print(f"replay: no such file: {args.session_file}", file=sys.stderr)
        return 1
    lines = load_lines(args.session_file)
    if not lines:
        print(f"replay: {args.session_file} has no log lines", file=sys.stderr)
        return 1

    fn_room, fn_skill = parse_filename(args.session_file.name)
    room = args.room or fn_room or "kitchen"
    skill = args.skill or fn_skill or "fall-response"
    urgency = args.urgency or DEFAULT_URGENCY.get(skill, "routine")
    if not (args.room or fn_room) or not (args.skill or fn_skill):
        print(
            f"replay: {args.session_file.name!r} doesn't match "
            f"<room>__<skill>__<started_at>.jsonl - using room={room!r} skill={skill!r} "
            f"(override with --room/--skill)",
            file=sys.stderr,
        )

    session_id = new_ulid(float(lines[0].get("ts", time.time())))
    phase = FIRST_PHASE.get(skill, "check")
    state = "active"
    log: list[dict] = []

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"qnet-replay-{new_ulid()[:8]}")
    client.connect(args.broker, args.port, keepalive=15)
    client.loop_start()

    def publish(topic: str, payload: dict) -> None:
        body = json.dumps(payload)
        info = client.publish(topic, body, qos=1)
        info.wait_for_publish(timeout=5)
        if not args.quiet:
            print(f"{topic} {body}")

    print(
        f"replay: {args.session_file} -> session {session_id} "
        f"({room}/{skill}, urgency={urgency}) at {args.speed}x, {len(lines)} lines",
        file=sys.stderr,
    )

    prev_ts: float | None = None
    for line in lines:
        ts = float(line.get("ts", time.time()))
        if prev_ts is not None and args.speed > 0:
            delay = max(0.0, (ts - prev_ts) / args.speed)
            if delay:
                time.sleep(delay)
        prev_ts = ts

        log.append(line)
        event = line.get("event")

        if event == "phase":
            to = line.get("to")
            if to in TERMINAL_EXITS:
                state = CANCELLED if to == CANCELLED else "closed"
                # session.phase is NOT updated on a terminal exit (§6: "any
                # other name ends the session" - it never becomes a phase).
            else:
                phase = to

        session_doc = {
            "id": session_id,
            "room": room,
            "skill": skill,
            "urgency": urgency,
            "phase": phase,
            "state": state,
            "log": log,
        }
        publish(f"qnet/session/{session_id}", session_doc)

        if event == "detected":
            publish(f"qnet/{room}/event", {
                "id": new_ulid(ts),
                "ts": round(ts, 1),
                "room": room,
                "kind": line.get("kind", "fall.detected"),
                "conf": line.get("conf", 0.85),
                # The JSONL line only ever carries kind+conf (§6); meta is
                # synthesized here since the original detector detail isn't
                # in the log to replay - flagged rather than silently faked
                # as something more specific.
                "meta": {"cls": "Fallen", "frames": "5/8"},
            })
        elif event == "say":
            text = line.get("text", "")
            publish(f"qnet/{room}/say", {"text": text, "prio": say_prio(text)})
        elif event == "heard":
            publish(f"qnet/{room}/heard", {"text": line.get("text", ""), "silence": bool(line.get("silence"))})

    client.loop_stop()
    client.disconnect()

    print(f"replay: done - {len(lines)} lines published, session {session_id} final state={state!r} phase={phase!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
