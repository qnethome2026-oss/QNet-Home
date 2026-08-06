#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T2.4's verify harness - watch the comfort loop for real, at real speed.

    python dev/broker.py &
    python -m qnet.agent --config config/house.yaml --no-llm &
    python dev/soak_comfort.py --minutes 2

Injects one fall, then plays silence for the whole window (a `heard` with
``silence: true`` every 10 s, exactly as a node's listen timeout would), and
watches ``qnet/<room>/say``. It asserts what DESIGN §6 promises and prints each
assertion with the evidence:

    [ ] >= 4 comfort utterances, gaps between speech 15-30 s (never > 35 s)
    [ ] zero overlapping speech (say timestamps strictly sequential)
    [ ] every elapsed-time claim within +/-5 s of the truth

Exits 0 if every check passes, 1 otherwise. Nothing here knows about the
engine's internals - it only reads the bus, like the room does.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qnet.ids import new_ulid  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"

# "it's been about 1 minute and 25 seconds" / "about 45 seconds"
ELAPSED_RE = re.compile(r"about (?:(\d+) minutes? (?:and )?)?(?:(\d+) seconds)?")

MAX_SILENCE_S = 35.0      # §6: never leave them in silence
GAP_MIN_S, GAP_MAX_S = 15.0, 30.0
WANT_COMFORT = 4


def claimed_seconds(text: str) -> int | None:
    """The elapsed time a comfort line claims out loud, in seconds."""
    match = ELAPSED_RE.search(text)
    if not match or not (match.group(1) or match.group(2)):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python dev/soak_comfort.py", description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=float, default=2.0, help="how long to stay silent (default: 2)")
    parser.add_argument("--room", default="kitchen")
    parser.add_argument("--broker", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args(argv)

    window = args.minutes * 60.0
    heard_gap = 10.0
    said: list[tuple[float, str, str]] = []   # (t, prio, text)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"qnet-soak-{new_ulid()[:8]}")

    def on_connect(c, userdata, flags, reason_code, properties=None):
        c.subscribe(f"qnet/{args.room}/say", qos=1)

    def on_message(c, userdata, msg):
        payload = json.loads(msg.payload.decode("utf-8"))
        said.append((time.time(), payload.get("prio", ""), payload.get("text", "")))
        print(f"  {time.time() - t0:6.1f}s  say[{payload.get('prio')}] {payload.get('text')}", flush=True)

    client.on_connect, client.on_message = on_connect, on_message
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()
    time.sleep(0.5)

    fall = json.loads((FIXTURES / "event_fall.json").read_text(encoding="ascii"))
    fall["id"], fall["ts"], fall["room"] = new_ulid(), round(time.time(), 1), args.room
    t0 = time.time()
    client.publish(f"qnet/{args.room}/event", json.dumps(fall), qos=1).wait_for_publish(timeout=5)
    print(f"soak: injected fall in {args.room}; staying silent for {args.minutes:g} minute(s)\n", flush=True)

    next_heard = t0 + heard_gap
    # Run the whole window, then linger (capped) for a pending update rather than
    # cutting the last gap in half - the run is 120 s, the loop speaks at ~20 s.
    hard_stop = t0 + window + 40.0
    while time.time() < hard_stop:
        if time.time() >= t0 + window and sum(1 for _, prio, _ in said if prio == "comfort") >= WANT_COMFORT:
            break
        if time.time() >= next_heard:
            client.publish(f"qnet/{args.room}/heard", json.dumps({"text": "", "silence": True}), qos=1)
            next_heard += heard_gap
        time.sleep(0.1)

    client.loop_stop()
    client.disconnect()

    elapsed = time.time() - t0
    comfort = [(t, text) for t, prio, text in said if prio == "comfort"]
    times = [t for t, _, _ in said]
    gaps = [(times[i] - times[i - 1]) for i in range(1, len(times))]
    first_gap = times[0] - t0 if times else elapsed

    print(f"\nsoak: {elapsed:.0f}s watched, {len(said)} utterances, {len(comfort)} of them comfort updates")
    checks: list[tuple[bool, str]] = []

    checks.append((len(comfort) >= WANT_COMFORT, f">= {WANT_COMFORT} comfort utterances: {len(comfort)}"))

    worst = max([first_gap, *gaps]) if times else elapsed
    checks.append((worst <= MAX_SILENCE_S, f"never more than {MAX_SILENCE_S:g}s of silence: worst gap {worst:.1f}s"))

    # The first two gaps are the phase ladder (30 s check, 15 s escalate); every
    # gap after call_help opens is the comfort loop's own interval.
    loop_gaps = gaps[2:] if len(gaps) > 2 else []
    ok_gaps = all(GAP_MIN_S <= g <= GAP_MAX_S for g in loop_gaps)
    checks.append(
        (
            bool(loop_gaps) and ok_gaps,
            f"comfort gaps within {GAP_MIN_S:g}-{GAP_MAX_S:g}s: "
            + ", ".join(f"{g:.1f}" for g in loop_gaps),
        )
    )

    sequential = all(times[i] - times[i - 1] > 1.0 for i in range(1, len(times)))
    checks.append((sequential, "zero overlapping speech (say timestamps strictly sequential)"))

    claims = [(t, text, claimed_seconds(text)) for t, text in comfort]
    unchecked = [text for _, text, value in claims if value is None]
    errors = [(abs(value - (t - t0)), text) for t, text, value in claims if value is not None]
    worst_error = max((e for e, _ in errors), default=0.0)
    checks.append(
        (
            bool(errors) and not unchecked and worst_error <= 5.0,
            f"every elapsed-time claim within +/-5s of truth: worst {worst_error:.1f}s"
            + (f" (unparsed: {unchecked})" if unchecked else ""),
        )
    )

    grounded = all("has been messaged" in text for _, text in comfort)
    checks.append((grounded, "every update states a fact from the tool log, not filler"))

    print()
    for ok, line in checks:
        print(f"  [{'x' if ok else ' '}] {line}")
    passed = all(ok for ok, _ in checks)
    print(f"\nsoak: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
