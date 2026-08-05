#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Watch the bus - ``mosquitto_sub -t 'qnet/#' -v``, in Python.

Windows has no mosquitto-clients, and every Verify block in
docs/IMPLEMENTATION.md is written against a subscriber printing topic + payload.
This is that subscriber, and it stays useful long after the spine: it is how you
see what the agent actually put on the wire.

    python dev/spy.py                        # everything, forever
    python dev/spy.py -t 'qnet/kitchen/say'  # one topic
    python dev/spy.py -C 1                   # exit after one message

Prefixes each line with a wall clock so 2-second assertions are checkable.
"""

from __future__ import annotations

import argparse
import sys
import time

import paho.mqtt.client as mqtt


def main(argv: list[str] | None = None) -> int:
    """Subscribe and print ``<time> <topic> <payload>`` per message."""
    parser = argparse.ArgumentParser(prog="python dev/spy.py", description="Print every message on the bus.")
    parser.add_argument("--broker", default="127.0.0.1", metavar="HOST")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("-t", "--topic", default="qnet/#", help="topic filter (default: qnet/#)")
    parser.add_argument("-C", "--count", type=int, default=0, help="exit after N messages (0 = never)")
    args = parser.parse_args(argv)

    seen = 0

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(args.topic, qos=1)
        print(f"# spy: {args.broker}:{args.port} {args.topic}", flush=True)

    def on_message(client, userdata, msg):
        nonlocal seen
        stamp = time.strftime("%H:%M:%S") + f".{int(time.time() % 1 * 1000):03d}"
        print(f"{stamp} {msg.topic} {msg.payload.decode('utf-8', 'replace')}", flush=True)
        seen += 1
        if args.count and seen >= args.count:
            client.disconnect()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qnet-spy")
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(args.broker, args.port, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()
        print("# spy: stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
