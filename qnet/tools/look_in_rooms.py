# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""look_in_rooms - ask every node to look for an object, right now (DESIGN.md §11, §13).

Broadcast ``qnet/look`` -> collect ``qnet/<room>/looked`` -> report **what was
actually checked**. That last clause is the whole reason this tool is more than
one publish: a node can be down, busy running its own VLM, or off the network,
and §13 is explicit that "silently reporting 'not found' when you only managed
to check half the house is the kind of thing that makes people stop trusting a
system." So the return value separates the rooms that answered from the rooms
that did not, and the engine's wording (§13's three-row table) is built from
that distinction.

The rules, all from §13 and ``contracts/mqtt.md``:

* one ``qid`` per call, echoed by every reply; a reply carrying **any other
  qid is ignored** - the broadcast topic is shared, and a late answer to the
  previous question must never be read as an answer to this one
* the expected rooms come from ``house.yaml``'s ``rooms:`` map, so the tool
  knows how many nodes it is waiting for without any registration protocol
* ``mode: guide`` targets one room (``room=``), and then that is the only room
  expected - the person is already standing in it
* wait up to ``find.look_timeout_s`` (default 8 s, §13's ceiling rather than
  its goal), and **return early the moment every expected room has answered**,
  which is the normal case and keeps the answer inside §13's ~6 s budget
* only text crosses the wire: the node sends a sentence, never a frame

Never raises: no ``subscribe`` capability (an older ``ToolContext``), a publish
that fails, a malformed reply - each degrades into "that room did not answer",
which is a fact the engine already knows how to say out loud.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from qnet.ids import new_ulid
from qnet.tools import ToolContext, register

log = logging.getLogger("qnet.tools.look")

LOOK_TOPIC = "qnet/look"
LOOKED_FILTER = "qnet/+/looked"
DEFAULT_TIMEOUT_S = 8.0          # §13's ceiling; T6.3 lowers it to measured + 1 s


def look_timeout_s(config: dict | None) -> float:
    """``find.look_timeout_s``, or the flat ``look_timeout_s``, or 8 s (§13)."""
    config = config or {}
    raw = config.get("look_timeout_s")
    if raw is None:
        raw = ((config.get("find") or {}) if isinstance(config.get("find"), dict) else {}).get("look_timeout_s")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else DEFAULT_TIMEOUT_S


def expected_rooms(config: dict | None, mode: str, room: str | None) -> list[str]:
    """Who this call is waiting for: one room in ``guide``, the house in ``find``."""
    if mode == "guide" and room:
        return [room]
    return list(((config or {}).get("rooms") or {}).keys())


@register("look_in_rooms")
async def look_in_rooms(ctx: ToolContext, object: str, mode: str = "find", room: str | None = None) -> dict:
    """Broadcast one look, collect the replies, and say which rooms went quiet."""
    qid = new_ulid()
    expected = expected_rooms(ctx.config, mode, room)
    timeout = look_timeout_s(ctx.config)
    payload = {"qid": qid, "object": object, "mode": mode, "room": room if mode == "guide" else None}

    replies: list[dict] = []
    answered: set[str] = set()

    try:
        if ctx.subscribe is None:
            # An older ToolContext: we can still ask, we just cannot hear the
            # answers. Say so honestly rather than pretending nobody looked.
            log.warning("look_in_rooms: no subscribe capability - broadcasting blind")
            await ctx.publish(LOOK_TOPIC, payload)
        else:
            async with ctx.subscribe(LOOKED_FILTER) as inbox:
                # Subscribe *before* publishing: a fast node can answer before
                # the next await, and a dropped reply looks like a dead room.
                await ctx.publish(LOOK_TOPIC, payload)
                deadline = time.monotonic() + timeout
                while expected and not answered >= set(expected):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        _topic, message = await asyncio.wait_for(inbox.get(), remaining)
                    except (TimeoutError, asyncio.TimeoutError):
                        break
                    reply = _reply(message, qid)
                    if reply is None:
                        continue
                    if reply["room"] in answered:
                        continue  # QoS 1 is at-least-once; one answer per room
                    answered.add(reply["room"])
                    replies.append(reply)
    except Exception as exc:  # noqa: BLE001 - a tool never raises (§11)
        log.exception("look_in_rooms failed")
        _log(ctx, f"error - {exc!r}", qid)
        return {"replies": replies, "unreachable": [r for r in expected if r not in answered],
                "qid": qid, "object": object, "mode": mode, "error": repr(exc)}

    unreachable = [r for r in expected if r not in answered]
    found = [r["room"] for r in replies if r.get("found")]
    _log(ctx, f"{len(replies)}/{len(expected)} answered"
              + (f", found in {', '.join(found)}" if found else ", not found")
              + (f", unreachable: {', '.join(unreachable)}" if unreachable else ""), qid)

    return {"replies": replies, "unreachable": unreachable, "qid": qid, "object": object, "mode": mode}


def _reply(message: Any, qid: str) -> dict | None:
    """One ``looked`` payload, validated against this call's qid and the contract."""
    if not isinstance(message, dict):
        return None
    if message.get("qid") != qid:
        # Not ours: a stale answer to the previous question, or another agent's.
        log.info("look_in_rooms: ignoring looked with qid %r (waiting on %r)", message.get("qid"), qid)
        return None
    room = message.get("room")
    if not isinstance(room, str) or not room:
        return None
    return {"room": room, "found": bool(message.get("found")), "answer": str(message.get("answer") or "")}


def _log(ctx: ToolContext, result: str, qid: str) -> None:
    """One ``tool`` line, in the engine's own log shape - never fatal if it fails."""
    try:
        ctx.log({"event": "tool", "tool": "look_in_rooms", "result": result, "qid": qid})
    except Exception:  # noqa: BLE001 - logging must not break a search
        pass
