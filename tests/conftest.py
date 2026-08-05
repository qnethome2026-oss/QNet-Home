# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The scenario harness: a fake bus, recorder tools, and a scaled clock.

Three deliberate choices, so the regression suite in ``test_scenarios.py`` stays
fast, hermetic and honest:

* **A fake MQTT layer, not a broker.** ``FakeBus`` is exactly what
  ``Agent.publish`` needs (``publish(topic, payload, qos)``), so every message
  the agent puts on the wire is captured in order with nothing mocked inside the
  engine. The real broker path is covered end-to-end by
  ``scripts/demo_fallback.sh`` (Gate G2).
* **Recorder tools, never the real registry.** ``qnet/tools/`` belongs to
  another lane; these tests assert what the *engine* does, so they inject stubs
  with the shipped ``ToolSpec``-shaped interface (``.fn`` async, ``.engine_only``).
  One stub logs through ``ctx.log`` like the real ``notify_contacts`` does and
  one does not, so both halves of the engine's "exactly one tool line" rule are
  exercised.
* **``dev.timer_scale``.** 0.05 turns fall.md's 30 s / 15 s ladder into
  1.5 s / 0.75 s, so a full escalation takes ~2.5 s of wall clock and the test
  still exercises the real timers - no monkeypatched clock, no faked sleep.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from qnet.agent import engine

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"


def fixture(name: str) -> dict:
    """The frozen wire fixture, same source of truth as dev/inject.py (T0.1)."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="ascii"))


class FakeBus:
    """In-process stand-in for the broker - records everything published."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.messages.append((topic, json.loads(payload)))

    # --- what the tests actually ask it -----------------------------------

    def on(self, topic: str) -> list[dict]:
        return [payload for t, payload in self.messages if t == topic]

    def says(self, room: str = "kitchen") -> list[dict]:
        """Every `say` for a room, in order."""
        return self.on(f"qnet/{room}/say")

    def said(self, room: str = "kitchen") -> list[str]:
        return [m["text"] for m in self.says(room)]

    def sessions(self) -> list[dict]:
        """Every `qnet/session/<id>` document, in order (the dashboard's feed)."""
        return [p for t, p in self.messages if t.startswith("qnet/session/")]


@dataclass
class StubSpec:
    """The two fields the engine reads off a ``qnet.tools.ToolSpec``."""

    fn: Callable
    engine_only: bool = True


@dataclass
class Recorder:
    """Every engine-invoked tool call, in order, with its kwargs."""

    calls: list[tuple[str, dict]] = field(default_factory=list)

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def count(self, name: str) -> int:
        return self.names().count(name)

    def kwargs(self, name: str) -> list[dict]:
        return [args for n, args in self.calls if n == name]


def recorder_tools(recorder: Recorder) -> dict[str, StubSpec]:
    """A registry shaped like ``qnet.tools.TOOLS``, recording instead of acting."""

    async def notify_contacts(ctx, kind: str = "escalate") -> dict:
        recorder.calls.append(("notify_contacts", {"kind": kind}))
        # The shipped tool logs its own line through ctx.log; mirror that so the
        # engine's "don't double-log" path is under test.
        ctx.log({"event": "tool", "tool": "notify_contacts", "result": "console", "kind": kind})
        return {"delivered": False, "channel": "console", "text": f"[{kind}] recorded"}

    async def call_emergency(ctx) -> dict:
        recorder.calls.append(("call_emergency", {}))
        # No ctx.log here: the engine must write the tool line itself.
        return {"SIMULATED": True, "number": "911", "room": ctx.room}

    async def look_in_rooms(ctx, object: str, mode: str = "find", room: str | None = None) -> dict:
        recorder.calls.append(("look_in_rooms", {"object": object, "mode": mode, "room": room}))
        return {"found": False, "rooms": []}

    return {
        "notify_contacts": StubSpec(notify_contacts, engine_only=True),
        "call_emergency": StubSpec(call_emergency, engine_only=True),
        "look_in_rooms": StubSpec(look_in_rooms, engine_only=False),
    }


def make_agent(
    tmp_path: Path,
    recorder: Recorder | None = None,
    timer_scale: float = 0.05,
    comfort_interval_s: float = 20.0,
    **config_overrides: Any,
) -> tuple[engine.Agent, FakeBus, Recorder]:
    """An agent wired to a fake bus and recorder tools, with scaled timers."""
    recorder = recorder or Recorder()
    config = {
        "resident": {"name": "Margaret"},
        "contacts": [{"name": "Sarah", "telegram_chat_id": "TODO"}],
        "emergency_number": "911",
        "storage": {"sessions_dir": str(tmp_path)},
        "comfort": {"interval_s": comfort_interval_s},
        "dev": {"timer_scale": timer_scale},
    }
    config.update(config_overrides)
    bus = FakeBus()
    agent = engine.Agent(config=config, use_llm=False, tools=recorder_tools(recorder), client=bus)
    return agent, bus, recorder


# --- driving one incident -------------------------------------------------


async def fall(agent: engine.Agent, room: str = "kitchen") -> engine.Session:
    """Inject the frozen fall fixture, exactly as dev/inject.py would."""
    msg = fixture("event_fall")
    msg["room"] = room
    msg["ts"] = time.time()
    await agent.on_message(f"qnet/{room}/event", json.dumps(msg).encode())
    session = agent.sessions[room]
    await asyncio.sleep(0)  # let run_session reach its first await
    return session


async def heard(agent: engine.Agent, text: str = "", room: str = "kitchen", silence: bool = False) -> None:
    """Publish what the room heard - a transcript, or a listen that timed out."""
    payload = {"text": "" if silence else text, "silence": silence}
    await agent.on_message(f"qnet/{room}/heard", json.dumps(payload).encode())


async def until(predicate: Callable[[], bool], timeout: float = 5.0, why: str = "") -> None:
    """Wait for something the engine does on its own schedule (a timer, a tool)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"timed out after {timeout}s waiting for {why or 'condition'}")


async def finish(session: engine.Session, timeout: float = 5.0) -> None:
    """Wait for a session that ends on its own (an exit, not a manual stop)."""
    assert session.task is not None
    await asyncio.wait_for(asyncio.shield(session.task), timeout)


async def stop(agent: engine.Agent, session: engine.Session) -> None:
    """Stop a session that would otherwise wait forever (call_help has no timer)."""
    if session.task and not session.task.done():
        session.task.cancel()
        try:
            await session.task
        except asyncio.CancelledError:
            pass
    await agent.shutdown()


def jsonl(session: engine.Session) -> list[dict]:
    """The session's file on disk - the thing a responder brief will read (§6, §12)."""
    return [json.loads(line) for line in session.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def events(lines: list[dict], kind: str) -> list[dict]:
    return [line for line in lines if line.get("event") == kind]
