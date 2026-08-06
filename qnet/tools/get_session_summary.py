# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""get_session_summary - the room's latest fall-response timeline (DESIGN.md §11, §12).

**Invoked by the engine in the responder-brief interrupt** - the LLM only
words the result into a spoken sentence (§12); it does not decide *whether*
to call this. Not ``engine_only`` in the registry sense (that flag is reserved
for actions that must never even be offered to the model, per DESIGN §11's
table); this one just isn't wired to the fall skill's own `tools:` allowlist.

**"The latest" is a filesystem question** (§6):
``sorted(glob(f"data/sessions/{room}__fall-response__*.jsonl"))[-1]``. No
index, no database - the filename carries the room and the start time, so
sorting the names sorts the sessions. The file is read **live**: whatever has
been appended so far, including mid-escalation, is exactly what gets
summarised - there is no "finalize the log" step to wait for (§12).

No file for the room -> ``{"no_history": True, "room": room}``, matching §12's
"No fall has been recorded in this room."

**A note on inferring state from the file** (flagged for the engine
integration): the JSONL schema frozen in `contracts/mqtt.md` defines six log
line kinds - ``detected``, ``say``, ``heard``, ``phase``, ``tool``,
``refusal`` - and none of them is an explicit "session state" line. DESIGN §6's
exit-resolution rule is the only documented way to recover it from the log
alone: "an exit whose name matches a phase id jumps to that phase; any other
name ends the session with that label as its final state." So the last
``phase`` line's ``to`` field is either a known fall-response phase (session
still active, mid-flow) or a terminal label (``ok``, ``resolved``, or
whatever the cancel path logs) - and this module treats it that way. If the
engine ends up logging a different, more explicit state marker, this is the
one place to update.
"""

from __future__ import annotations

import glob
import json
import time
from pathlib import Path

from qnet.tools import ToolContext, register

DEFAULT_SESSIONS_DIR = "data/sessions"
SKILL = "fall-response"

# The fall skill's phase ids (skills/fall.md, DESIGN §7). A "phase" log line
# whose `to` is NOT one of these is a terminal exit label, not a phase jump -
# see the module docstring's note on inferring state.
KNOWN_FALL_PHASES = {"check", "escalate", "call_help"}


def _humanize_offset(offset_s: float) -> str:
    """``+0s`` / ``+9s`` / ``+1m30s`` - a human-readable "how far into it" tag."""
    whole = round(offset_s)
    sign = "-" if whole < 0 else "+"
    whole = abs(whole)
    if whole < 60:
        return f"{sign}{whole}s"
    minutes, seconds = divmod(whole, 60)
    return f"{sign}{minutes}m{seconds:02d}s"


def _sessions_dir(config: dict) -> Path:
    storage = (config or {}).get("storage") or {}
    return Path(storage.get("sessions_dir", DEFAULT_SESSIONS_DIR))


def _latest_file(sessions_dir: Path, room: str) -> Path | None:
    pattern = str(sessions_dir / f"{room}__{SKILL}__*.jsonl")
    matches = sorted(glob.glob(pattern))
    return Path(matches[-1]) if matches else None


@register("get_session_summary")
async def get_session_summary(ctx: ToolContext, room: str | None = None) -> dict:
    """Read the room's latest fall-response session file, live, and structure it."""
    target_room = room or ctx.room

    try:
        sessions_dir = _sessions_dir(ctx.config)
        path = _latest_file(sessions_dir, target_room)
        if path is None:
            return {"no_history": True, "room": target_room}

        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"no_history": True, "room": target_room}

    events: list[dict] = []
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue  # a partially-written last line, mid-write - skip, don't crash
        events.append(entry)

    if not events:
        return {"no_history": True, "room": target_room}

    started_at = events[0].get("ts")
    last_ts = events[-1].get("ts", started_at)

    last_phase_to = None
    for entry in events:
        if entry.get("event") == "phase" and "to" in entry:
            last_phase_to = entry["to"]

    if last_phase_to and last_phase_to not in KNOWN_FALL_PHASES:
        current_phase = last_phase_to
        state = last_phase_to  # terminal exit label doubles as the final state
    else:
        current_phase = last_phase_to or "check"
        state = "active"

    timeline = []
    for entry in events:
        ts = entry.get("ts", started_at)
        offset_s = round((ts - started_at) if started_at is not None else 0.0, 1)
        timeline.append({**entry, "offset_s": offset_s, "offset_human": _humanize_offset(offset_s)})

    elapsed_s = round((last_ts - started_at), 1) if started_at is not None and last_ts is not None else None

    try:
        ctx.log(
            {
                "event": "tool",
                "tool": "get_session_summary",
                "result": f"{len(events)} events, phase={current_phase}",
            }
        )
    except Exception:
        pass

    return {
        "room": target_room,
        "file": path.name,
        "started_at": started_at,
        "events": timeline,
        "phase": current_phase,
        "state": state,
        "elapsed_s": elapsed_s,
        "read_at": round(time.time(), 1),
    }
