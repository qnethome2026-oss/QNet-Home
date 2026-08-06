# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Tools - one file per tool, registered in a dict (DESIGN.md §11).

Adding a tool never edits the engine. Not every tool is something the LLM
chooses to call; anything consequential enough that it must not depend on the
model is invoked by the engine directly:

    notify_contacts      engine, on_enter    Telegram, one HTTPS POST
    call_emergency       engine, on_enter    SIMULATED - renders the payload
    look_in_rooms        LLM, in find.md     broadcast look, collect looked
    get_session_summary  engine, brief       latest fall-response session file

Session logging follows the same rule and is not a tool at all (§6).

This module defines the interface the engine (T2.2+) codes against -
``ToolContext``, ``ToolSpec`` and the ``TOOLS`` registry - and nothing else.
Each tool lives in its own file and registers itself with ``@register(...)``
when imported; the imports at the bottom of this file are what populates
``TOOLS``, exactly once, at import time.

A tool never raises. Every tool function catches its own failures and returns
an error-shaped dict instead - the engine treats a tool's outcome as a fact
to log and act on, never as an exception to handle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolContext:
    """What every tool is handed - never more than this (T2.3 interface).

    **T6.2 added exactly one field, optional and last.** ``look_in_rooms`` is
    the first tool that has to *listen* as well as speak: it broadcasts
    ``qnet/look`` and then waits for ``qnet/<room>/looked`` replies (§13). Every
    other tool ignores ``subscribe``, every existing call site still constructs
    a context the same way, and a context built without it (an older caller, a
    test) leaves it ``None`` - which ``look_in_rooms`` treats as "I can publish
    but I cannot hear", not as a crash.
    """

    room: str
    session_id: str
    config: dict                      # parsed house.yaml
    publish: Any                      # async (topic: str, payload: dict) -> None
    log: Any                          # (event: dict) -> None - appends to session log
    subscribe: Any = None             # (topic_filter: str) -> async ctx mgr -> Queue[(topic, dict)]


@dataclass
class ToolSpec:
    """One registry entry. ``engine_only`` tools are never in the LLM's toolset."""

    fn: Any                           # async (ctx, **args) -> dict
    engine_only: bool = False


TOOLS: dict[str, ToolSpec] = {}


def console_print(msg: str) -> None:
    """``print()`` that never raises when the console's codepage can't show emoji.

    Telegram templates carry emoji (DESIGN §7); a Windows console defaults to
    cp1252, which can't encode them, and a plain ``print()`` there raises
    ``UnicodeEncodeError`` - the exact kind of thing "a tool never raises"
    (§11) is meant to rule out even in a fallback/error path. Falls back to an
    ASCII-safe rendering (``\\U0001f534`` instead of the character) rather than
    losing the line.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="backslashreplace").decode("ascii"))


def register(name: str, *, engine_only: bool = False):
    """Decorator: add ``fn`` to ``TOOLS`` under ``name`` when its module loads."""

    def decorator(fn):
        TOOLS[name] = ToolSpec(fn=fn, engine_only=engine_only)
        return fn

    return decorator


# Importing each module runs its `@register(...)` calls, populating TOOLS.
# Order doesn't matter - each file is independent, per DESIGN §11's "adding a
# tool never edits the engine."
from qnet.tools import call_emergency as _call_emergency  # noqa: E402,F401
from qnet.tools import get_session_summary as _get_session_summary  # noqa: E402,F401
from qnet.tools import look_in_rooms as _look_in_rooms  # noqa: E402,F401
from qnet.tools import notify_contacts as _notify_contacts  # noqa: E402,F401
