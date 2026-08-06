#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Local dev MQTT broker - a laptop stand-in for Mosquitto on the IQ-9075 (T1.1).

Production is Mosquitto on the brain (``infra/mosquitto.conf``); this exists
only because Windows has no mosquitto package and the spine has to be
developable on a laptop. Same two listeners as the real config, so nothing
downstream can tell the difference: MQTT/TCP on 1883 and MQTT-over-WebSocket on
9001 (``dev/sim.html`` and the dashboard use the latter).

    python dev/broker.py        # foreground, Ctrl-C to stop

Pure Python (``amqtt``, in the ``[dev]`` extra) - no service to install.
"""

from __future__ import annotations

import asyncio
import logging

from amqtt.broker import Broker

HOST = "127.0.0.1"
CONFIG = {
    "listeners": {
        "default": {"type": "tcp", "bind": f"{HOST}:1883", "max_connections": 50},
        "ws": {"type": "ws", "bind": f"{HOST}:9001", "max_connections": 50},
    },
    "timeout_disconnect_delay": 2,
}


async def serve() -> None:
    """Start both listeners and stay up until cancelled."""
    broker = Broker(CONFIG)
    await broker.start()
    print(f"dev broker: mqtt tcp://{HOST}:1883  ws://{HOST}:9001  (Ctrl-C to stop)", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("dev broker: stopped", flush=True)
