"""Publish frozen contract fixtures for development and demo recovery."""

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"


def build_message(args: argparse.Namespace) -> tuple[str, dict]:
    fixture_name = {
        "fall": "event.json",
        "query": "ask-query.json",
        "responder_brief": "ask-responder-brief.json",
    }[args.command]
    data = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    data["id"] = f"inject-{uuid.uuid4()}"
    data["ts"] = time.time()
    data["room"] = args.room
    if args.command == "query":
        data["text"] = args.text
    topic_type = "event" if args.command == "fall" else "ask"
    return f"qnet/{args.room}/{topic_type}", data


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=1883)
    commands = result.add_subparsers(dest="command", required=True)
    fall = commands.add_parser("fall")
    fall.add_argument("--room", required=True)
    ask = commands.add_parser("ask")
    ask.add_argument("--room", default="living-room")
    ask.add_argument("--kind", choices=("query", "responder_brief"), required=True)
    ask.add_argument("--text", default="")
    return result


def main() -> None:
    import paho.mqtt.publish as publish

    args = parser().parse_args()
    if args.command == "ask":
        args.command = args.kind
        if args.command == "query" and not args.text.strip():
            raise SystemExit("--text is required for kind=query")
    topic, payload = build_message(args)
    publish.single(topic, json.dumps(payload, separators=(",", ":")), qos=1, hostname=args.host, port=args.port)
    print(f"published {payload['id']} to {topic}")


if __name__ == "__main__":
    main()
