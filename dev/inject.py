#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The event injector - a complete stand-in for rooms (T1.2, DESIGN.md §5).

Publishes any frozen fixture (``contracts/fixtures/*.json``) on its contract
topic (``contracts/mqtt.md``), with the CLI's overrides applied. Because
``heard`` and ``looked`` are here too, every brain-side path - the fall loop and
the find flow - is drivable from a script with no cameras, no microphone and no
speech service.

    python dev/inject.py fall   --room kitchen
    python dev/inject.py heard  --room kitchen --text "i'm fine"
    python dev/inject.py heard  --room kitchen --silence
    python dev/inject.py ask    --room kitchen --kind query --text "where are my glasses"
    python dev/inject.py ask    --room kitchen --kind responder_brief
    python dev/inject.py looked --room bedroom --qid q1 --found --answer "on the nightstand"
    python dev/inject.py look   --object glasses --qid t1            # broadcast, all rooms
    python dev/inject.py look   --object glasses --mode guide --room bedroom

The fixture is the shape and this file never invents fields: it loads the
fixture, overrides what the CLI was given, refreshes ``id``/``ts`` where the
contract has them, and publishes at QoS 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from qnet.ids import new_ulid

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"


def fixture(name: str) -> dict:
    """Load a frozen fixture. Read-only: contracts are sacred."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="ascii"))


def build_fall(args: argparse.Namespace) -> tuple[str, dict]:
    """qnet/<room>/event - a fall the node detected."""
    msg = fixture("event_fall")
    msg["id"] = new_ulid()
    msg["ts"] = round(time.time(), 1)
    msg["room"] = args.room
    if args.conf is not None:
        msg["conf"] = args.conf
    return f"qnet/{args.room}/event", msg


def build_heard(args: argparse.Namespace) -> tuple[str, dict]:
    """qnet/<room>/heard - the person's reply, or a listen window that timed out."""
    msg = fixture("heard")
    if args.silence:
        msg["text"], msg["silence"] = "", True
    else:
        msg["text"], msg["silence"] = args.text, False
    return f"qnet/{args.room}/heard", msg


def build_ask(args: argparse.Namespace) -> tuple[str, dict]:
    """qnet/<room>/ask - a query, or a first-responder brief request."""
    msg = fixture("ask_query" if args.kind == "query" else "ask_responder_brief")
    msg["id"] = new_ulid()
    msg["ts"] = round(time.time(), 1)
    msg["room"] = args.room
    if args.kind == "responder_brief":
        msg["text"] = ""  # the contract: the room is the whole request
    elif args.text is not None:
        msg["text"] = args.text
    return f"qnet/{args.room}/ask", msg


def build_looked(args: argparse.Namespace) -> tuple[str, dict]:
    """qnet/<room>/looked - fake a node's VLM reply to a look broadcast."""
    msg = fixture("looked")
    msg["qid"] = args.qid
    msg["room"] = args.room
    msg["found"] = args.found
    if args.answer is not None:
        msg["answer"] = args.answer
    elif not args.found:
        msg["answer"] = ""  # nothing seen, nothing to describe
    return f"qnet/{args.room}/looked", msg


def build_look(args: argparse.Namespace) -> tuple[str, dict]:
    """qnet/look - fake the agent's broadcast, to drive a real node's look.py."""
    msg = fixture("look")
    msg["qid"] = args.qid or new_ulid()
    msg["object"] = args.object
    msg["mode"] = args.mode
    msg["room"] = args.room  # None = every node answers (the contract's null)
    return "qnet/look", msg


def build_parser() -> argparse.ArgumentParser:
    """One subcommand per message type a room can send."""
    parser = argparse.ArgumentParser(
        prog="python dev/inject.py",
        description="Publish a frozen fixture on its contract topic (contracts/mqtt.md).",
    )
    parser.add_argument("--broker", default="127.0.0.1", metavar="HOST", help="broker host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=1883, help="broker port (default: 1883)")
    subs = parser.add_subparsers(dest="cmd", required=True)

    fall = subs.add_parser("fall", help="publish a fall.detected event")
    fall.add_argument("--room", default="kitchen")
    fall.add_argument("--conf", type=float, default=None, help="override model confidence")
    fall.set_defaults(build=build_fall)

    heard = subs.add_parser("heard", help="play the person's reply, or a timeout")
    heard.add_argument("--room", default="kitchen")
    mode = heard.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", help="what they said")
    mode.add_argument("--silence", action="store_true", help="the listen window timed out")
    heard.set_defaults(build=build_heard)

    ask = subs.add_parser("ask", help="publish a query or a responder-brief request")
    ask.add_argument("--room", default="kitchen")
    ask.add_argument("--kind", choices=["query", "responder_brief"], default="query")
    ask.add_argument("--text", default=None, help="transcript, wake phrase stripped (query only)")
    ask.set_defaults(build=build_ask)

    looked = subs.add_parser("looked", help="fake a node's VLM reply")
    looked.add_argument("--room", default="kitchen")
    looked.add_argument("--qid", required=True)
    found = looked.add_mutually_exclusive_group(required=True)
    found.add_argument("--found", dest="found", action="store_true")
    found.add_argument("--not-found", dest="found", action="store_false")
    looked.add_argument("--answer", default=None, help="one sentence of location")
    looked.set_defaults(build=build_looked)

    look = subs.add_parser("look", help="fake the agent's look broadcast")
    look.add_argument("--object", default="glasses", help="what to look for")
    look.add_argument("--mode", choices=["find", "guide"], default="find")
    look.add_argument("--room", default=None, help="target one room (guide); default: broadcast to all")
    look.add_argument("--qid", default=None, help="correlation id (default: a fresh ULID)")
    look.set_defaults(build=build_look)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Build one message and publish it at QoS 1."""
    args = build_parser().parse_args(argv)
    topic, msg = args.build(args)
    payload = json.dumps(msg)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"qnet-inject-{new_ulid()[:8]}")
    client.connect(args.broker, args.port, keepalive=15)
    client.loop_start()
    info = client.publish(topic, payload, qos=1)
    info.wait_for_publish(timeout=5)
    client.loop_stop()
    client.disconnect()

    print(f"{topic} {payload}")
    return 0 if info.is_published() else 1


if __name__ == "__main__":
    sys.exit(main())
