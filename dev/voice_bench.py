#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Passive voice-loop benchmark - latency legs and drop pressure, from the bus.

Nothing here touches the boards: it subscribes to ``qnet/#`` (like dev/spy.py)
and computes what the wire already shows:

  heard -> say      how long the engine takes to answer speech in a session
  ask -> say        wake-to-response for the idle "hey home ..." path
  deaf windows      node status speaking -> next listening (TTS + guard +
                    stream restart; the mic is closed for the whole gap)
  snapshot pressure qnet/session/+ message rate - the node cancels its
                    in-flight listen on EVERY one of these
  stalls            status heartbeats are due every 5 s; a long gap means the
                    node (or its ASR runner) is wedged

    python dev/voice_bench.py --broker 10.73.51.175 --port 11883
    python dev/voice_bench.py --broker 10.73.51.175 --port 11883 --report verify/bench-run1.txt

Runs until Ctrl-C, then prints (and optionally writes) the summary. Pairing
note: a ``say`` is matched to the newest unanswered ``heard``/``ask`` in the
same room; pending entries expire after 30 s so unanswered speech cannot pair
with a much later comfort line.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import paho.mqtt.client as mqtt

PENDING_EXPIRY_S = 30.0
HEARTBEAT_DUE_S = 5.0
STALL_FACTOR = 3  # a gap past 3 missed heartbeats counts as a stall


def stamp(t: float | None = None) -> str:
    t = time.time() if t is None else t
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 1000):03d}"


def dist(values: list[float]) -> str:
    if not values:
        return "n=0"
    return (
        f"n={len(values)} median={statistics.median(values):.2f}s "
        f"min={min(values):.2f}s max={max(values):.2f}s"
    )


class Bench:
    """Accumulates per-message facts; ``report()`` turns them into the summary."""

    def __init__(self) -> None:
        self.started = time.time()
        self.pending_heard: dict[str, float] = {}
        self.pending_ask: dict[str, float] = {}
        self.heard_to_say: list[float] = []
        self.ask_to_say: list[float] = []
        self.heard_count = 0
        self.silence_count = 0
        self.say_count = 0
        self.snapshot_count = 0
        self.snapshot_sessions: set[str] = set()
        self.first_snapshot_at: float | None = None
        self.last_snapshot_at: float | None = None
        self.speaking_since: dict[str, float] = {}
        self.deaf_windows: list[float] = []
        self.last_status_at: dict[str, float] = {}
        self.stalls: list[tuple[str, float]] = []
        self.node_errors: list[tuple[str, str]] = []

    # -- message handling -------------------------------------------------

    def on_message(self, topic: str, payload: bytes) -> None:
        t = time.time()
        try:
            body = json.loads(payload.decode("utf-8", "replace"))
        except (ValueError, UnicodeDecodeError):
            body = {}
        parts = topic.split("/")
        if len(parts) == 3 and parts[0] == "qnet":
            if parts[1] == "session":
                self._on_snapshot(parts[2], t)
                return
            room, leaf = parts[1], parts[2]
            handler = getattr(self, f"_on_{leaf}", None)
            if handler is not None:
                handler(room, body, t)

    def _on_heard(self, room: str, body: dict, t: float) -> None:
        if body.get("silence"):
            self.silence_count += 1
            print(f"{stamp(t)} [{room}] heard: silence", flush=True)
            return
        self.heard_count += 1
        self.pending_heard[room] = t
        print(f"{stamp(t)} [{room}] heard ({len(body.get('text') or '')} chars) - waiting for say", flush=True)

    def _on_ask(self, room: str, body: dict, t: float) -> None:
        self.pending_ask[room] = t
        print(f"{stamp(t)} [{room}] ask kind={body.get('kind')}", flush=True)

    def _on_say(self, room: str, body: dict, t: float) -> None:
        self.say_count += 1
        note = ""
        for pending, series, label in (
            (self.pending_heard, self.heard_to_say, "heard->say"),
            (self.pending_ask, self.ask_to_say, "ask->say"),
        ):
            asked_at = pending.pop(room, None)
            if asked_at is not None and t - asked_at <= PENDING_EXPIRY_S:
                series.append(t - asked_at)
                note = f"  <-- {label} {t - asked_at:.2f}s"
                break
        print(f"{stamp(t)} [{room}] say prio={body.get('prio')} ({len(body.get('text') or '')} chars){note}", flush=True)

    def _on_status(self, room: str, body: dict, t: float) -> None:
        last = self.last_status_at.get(room)
        if last is not None and t - last > HEARTBEAT_DUE_S * STALL_FACTOR:
            self.stalls.append((room, t - last))
            print(f"{stamp(t)} [{room}] !! status silent for {t - last:.1f}s (node stall?)", flush=True)
        self.last_status_at[room] = t
        state = body.get("state")
        # Prefer the node's own clock for the deaf window - both edges then
        # come from one machine and Wi-Fi jitter cancels out.
        node_ts = body.get("ts") if isinstance(body.get("ts"), (int, float)) else t
        if state == "speaking":
            self.speaking_since[room] = node_ts
        elif state == "listening":
            since = self.speaking_since.pop(room, None)
            if since is not None:
                self.deaf_windows.append(node_ts - since)
                print(f"{stamp(t)} [{room}] deaf window {node_ts - since:.2f}s (speaking -> listening)", flush=True)
        elif state == "error":
            self.node_errors.append((room, str(body.get("error", ""))))
            print(f"{stamp(t)} [{room}] !! node error: {body.get('error')}", flush=True)

    def _on_snapshot(self, session_id: str, t: float) -> None:
        self.snapshot_count += 1
        self.snapshot_sessions.add(session_id)
        if self.first_snapshot_at is None:
            self.first_snapshot_at = t
        self.last_snapshot_at = t
        # One line per 20 keeps the live feed readable at storm rates.
        if self.snapshot_count % 20 == 0:
            print(f"{stamp(t)} !! {self.snapshot_count} session snapshots so far "
                  f"(delivery pressure; the node cancels only on idle<->session flips)", flush=True)

    # -- summary ----------------------------------------------------------

    def report(self) -> str:
        lines = [
            "voice_bench summary",
            f"  window: {stamp(self.started)} -> {stamp()} ({time.time() - self.started:.0f}s)",
            f"  heard->say latency : {dist(self.heard_to_say)}",
            f"  ask->say latency   : {dist(self.ask_to_say)}",
            f"  deaf windows       : {dist(self.deaf_windows)} (TTS + guard + ASR restart)",
            f"  heard published    : {self.heard_count} speech + {self.silence_count} silence",
            f"  say published      : {self.say_count}",
        ]
        if self.snapshot_count:
            span = (self.last_snapshot_at or 0) - (self.first_snapshot_at or 0)
            rate = self.snapshot_count / span if span > 0 else float(self.snapshot_count)
            lines.append(
                f"  session snapshots  : {self.snapshot_count} across {len(self.snapshot_sessions)} session(s)"
                f" ({rate:.2f}/s while active; the node cancels only on idle<->session flips)"
            )
        else:
            lines.append("  session snapshots  : 0")
        unanswered = len(self.pending_heard) + len(self.pending_ask)
        if unanswered:
            lines.append(f"  unanswered at exit : {unanswered} heard/ask never got a say")
        if self.stalls:
            worst = max(gap for _room, gap in self.stalls)
            lines.append(f"  node stalls        : {len(self.stalls)} status gaps >{HEARTBEAT_DUE_S * STALL_FACTOR:.0f}s (worst {worst:.1f}s)")
        if self.node_errors:
            lines.append(f"  node errors        : {len(self.node_errors)} (last: {self.node_errors[-1][1]!r})")
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python dev/voice_bench.py", description=__doc__.splitlines()[0])
    parser.add_argument("--broker", default="127.0.0.1", metavar="HOST")
    parser.add_argument("--port", type=int, default=11883)
    parser.add_argument("--report", metavar="FILE", help="also write the summary here on exit")
    parser.add_argument("--duration", type=float, metavar="SECONDS",
                        help="exit (with the summary) after this long - for scripted runs")
    args = parser.parse_args(argv)

    bench = Bench()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe("qnet/#", qos=1)
        print(f"# voice_bench: {args.broker}:{args.port} qnet/# - Ctrl-C for the summary", flush=True)

    def on_message(client, userdata, msg):
        try:
            bench.on_message(msg.topic, msg.payload)
        except Exception as exc:  # keep watching even on a malformed message
            print(f"# voice_bench: error on {msg.topic}: {exc!r}", flush=True)

    # Unique client id: duplicate ids kick each other off the broker (T6.3).
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"qnet-bench-{os.getpid()}-{int(time.time()) % 10000}",
    )
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(args.broker, args.port, keepalive=30)
    try:
        if args.duration:
            deadline = time.time() + args.duration
            while time.time() < deadline:
                client.loop(timeout=1.0)
            client.disconnect()
        else:
            client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()
    summary = bench.report()
    print("\n" + summary, flush=True)
    if args.report:
        with open(args.report, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n\n")
        print(f"# voice_bench: appended to {args.report}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
