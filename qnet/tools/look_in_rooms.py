# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""look_in_rooms - ask every node to look for an object, right now (DESIGN.md §11, §13).

**Invoked by the LLM, in ``find.md``** - the only tool in this file that the
model actually chooses to call. This is the T2.3 **stub**: the real thing
(T6.2, §13) broadcasts ``qnet/look``, collects ``qnet/<room>/looked`` replies
for up to ~8 s, and reports which rooms answered and which didn't. Wiring
that up needs the real broadcast/collect machinery the engine doesn't have
yet, so for now this returns canned "nobody answered" data with the right
*shape* - every room from ``house.yaml`` reported as unreachable - so
``find.md`` and its tests have something to call against before T6.2 lands.

Keeping the signature right now (``object``, ``mode``, ``room``) means T6.2
only replaces this function's body, never its call sites.
"""

from __future__ import annotations

from qnet.tools import ToolContext, register


@register("look_in_rooms")
async def look_in_rooms(ctx: ToolContext, object: str, mode: str = "find", room: str | None = None) -> dict:
    """Stub for T6.2 - no broadcast happens yet; every configured room is 'unreachable'."""
    rooms = list(((ctx.config or {}).get("rooms") or {}).keys())

    try:
        ctx.log(
            {
                "event": "tool",
                "tool": "look_in_rooms",
                "result": f"stub - no broadcast (T6.2); object={object!r} mode={mode} room={room!r}",
            }
        )
    except Exception:
        pass

    return {"stub": True, "replies": [], "unreachable": rooms}
