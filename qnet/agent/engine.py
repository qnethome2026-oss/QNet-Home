# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The loop and the rails (DESIGN.md §6).

The agent decides what to say, which allowed tool to call, and whether a phase
goal is met. The engine guarantees everything consequential regardless of the
model:

* timers fire on schedule; a missing ``timer`` simply means no timer
* ``on_enter`` actions run before the agent's first turn, once per SESSION
* tools outside the current phase are refused and logged
* cancel is an engine-level interrupt matched before the agent sees a transcript
* the responder brief is an interrupt, not a session (§12)
* every session writes ``data/sessions/<room>__<skill>__<started_at>.jsonl``
  and publishes the identical stream to ``qnet/session/<id>``

Exit resolution, one rule: an exit whose name matches a phase id jumps to that
phase; any other name ends the session with that label as its final state.

**T1.3 - the skeleton.** What is real here: the asyncio MQTT client, the session
table with §6's two rules (one session per room, safety wins), the responder
brief's exemption from both, and the log stream with its two destinations (the
JSONL file and ``qnet/session/<id>``, one mechanism). What is not here yet:
phases, timers, cancel matching, tools, the LLM - a fall opens a session, gets
the canned opening line, and then sits in ``check`` recording what it hears.
That machinery lands in T2.1/T2.2, and ``run_phase`` below is its seam.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import aiomqtt

from qnet.ids import new_ulid

log = logging.getLogger("qnet.agent")

# What the agent listens to. `looked` and `status` join in T6.2 / T4.2.
SUBSCRIPTIONS = ("qnet/+/event", "qnet/+/ask", "qnet/+/heard")

# The fall skill's identity and its first phase (DESIGN.md §7). Hardcoded for
# the skeleton; T2.1's loader reads all of this out of skills/fall.md.
FALL_SKILL = "fall-response"
FALL_URGENCY = "safety"
FALL_FIRST_PHASE = "check"
FALL_OPENING = "I saw you fall. Take a breath — are you okay?"

DEFAULT_SESSIONS_DIR = "data/sessions"
DEFAULT_BROKER = "127.0.0.1"
DEFAULT_PORT = 1883


@dataclass
class Session:
    """One skill run, trigger to exit - and its own file, open for its life (§6)."""

    id: str
    room: str
    skill: str
    urgency: str
    phase: str
    path: Path
    state: str = "active"
    log: list[dict] = field(default_factory=list)
    on_enter_done: set[str] = field(default_factory=set)

    @property
    def live(self) -> bool:
        """A live session is one the one-per-room rule protects."""
        return self.state == "active"

    def wire(self) -> dict:
        """The `qnet/session/<id>` payload - contracts/fixtures/session.json."""
        return {
            "id": self.id,
            "room": self.room,
            "skill": self.skill,
            "urgency": self.urgency,
            "phase": self.phase,
            "state": self.state,
            "log": self.log,
        }


def session_path(sessions_dir: Path, room: str, skill: str, started_at: float) -> Path:
    """``<room>__<skill>__<started_at ISO8601>.jsonl`` (§6).

    The colons of a real ISO 8601 time are illegal in a Windows filename and
    ugly everywhere, so the time separators are hyphens:
    ``kitchen__fall-response__2026-08-05T21-14-03.jsonl``. Sorting is unaffected,
    which is the whole point of putting the timestamp in the name -
    "the latest fall in the kitchen" stays ``sorted(glob(...))[-1]``.
    """
    stamp = datetime.fromtimestamp(started_at).strftime("%Y-%m-%dT%H-%M-%S")
    return sessions_dir / f"{room}__{skill}__{stamp}.jsonl"


class Agent:
    """The MQTT client and the session table. One instance per house."""

    def __init__(
        self,
        config: dict | None = None,
        broker: str = DEFAULT_BROKER,
        port: int = DEFAULT_PORT,
        use_llm: bool = True,
    ) -> None:
        self.config = config or {}
        self.broker = broker
        self.port = port
        self.use_llm = use_llm
        storage = self.config.get("storage") or {}
        self.sessions_dir = Path(storage.get("sessions_dir", DEFAULT_SESSIONS_DIR))
        self.sessions: dict[str, Session] = {}
        self.client: aiomqtt.Client | None = None

    # --- the fabric ------------------------------------------------------

    async def serve(self) -> None:
        """Connect, subscribe, and dispatch messages until cancelled."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        async with aiomqtt.Client(self.broker, self.port, identifier="qnet-agent") as client:
            self.client = client
            for topic in SUBSCRIPTIONS:
                await client.subscribe(topic, qos=1)
            log.info("connected %s:%s - subscribed %s", self.broker, self.port, " ".join(SUBSCRIPTIONS))
            log.info("sessions dir %s", self.sessions_dir.resolve())
            async for message in client.messages:
                try:
                    await self.on_message(str(message.topic), message.payload)
                except Exception:  # a bad message must never take the agent down
                    log.exception("dropping message on %s", message.topic)

    async def publish(self, topic: str, payload: dict) -> None:
        """Everything that carries a decision or a person's words is QoS 1."""
        assert self.client is not None
        await self.client.publish(topic, json.dumps(payload), qos=1)

    async def on_message(self, topic: str, payload: bytes) -> None:
        """Route one message by topic. `<room>` is the node's identity (§4)."""
        parts = topic.split("/")
        if len(parts) != 3:
            return
        _, room, kind = parts
        msg = json.loads(payload)
        if kind == "event":
            await self.on_event(room, msg)
        elif kind == "ask":
            await self.on_ask(room, msg)
        elif kind == "heard":
            await self.on_heard(room, msg)

    # --- the session table (§6) ------------------------------------------

    def live_session(self, room: str) -> Session | None:
        """The room's live session, if it has one."""
        session = self.sessions.get(room)
        return session if session and session.live else None

    async def append(self, session: Session, line: dict) -> None:
        """One log line, two destinations - the file and the bus, not two mechanisms.

        The line goes on disk the instant it happens and the whole session (with
        its log so far) goes out on ``qnet/session/<id>``, so the dashboard
        renders MQTT messages rather than reconstructing anything.
        """
        # Every line carries `ts` and `event` first, in that order (§6).
        entry = {"ts": line.get("ts", round(time.time(), 1)), **{k: v for k, v in line.items() if k != "ts"}}
        session.log.append(entry)
        with session.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        await self.publish(f"qnet/session/{session.id}", session.wire())

    async def say(self, session: Session, text: str, prio: str) -> None:
        """Speak into the room the session belongs to, and log the line."""
        await self.publish(f"qnet/{session.room}/say", {"text": text, "prio": prio})
        await self.append(session, {"event": "say", "text": text})

    # --- triggers ---------------------------------------------------------

    async def on_event(self, room: str, msg: dict) -> None:
        """`qnet/<room>/event` - the only kind in v1 is `fall.detected` (§4)."""
        if msg.get("kind") != "fall.detected":
            log.info("[%s] ignoring unknown event kind %r", room, msg.get("kind"))
            return

        existing = self.live_session(room)
        if existing:
            # One session per room: a new trigger for a room that already has a
            # live session is ignored (§6). Not an error - the detector is
            # allowed to fire again; the engine simply does not start twice.
            log.info("[%s] fall ignored - session %s already live (one per room)", room, existing.id)
            return

        detected_at = float(msg.get("ts") or time.time())
        session = Session(
            id=new_ulid(),
            room=room,
            skill=FALL_SKILL,
            urgency=FALL_URGENCY,
            phase=FALL_FIRST_PHASE,
            path=session_path(self.sessions_dir, room, FALL_SKILL, time.time()),
        )
        self.sessions[room] = session
        log.info("[%s] session %s open (%s) -> %s", room, session.id, session.skill, session.path.name)

        await self.append(
            session,
            {"ts": round(detected_at, 1), "event": "detected", "kind": msg["kind"], "conf": msg.get("conf")},
        )
        # The opening is canned: instant, and it cannot be skipped (§7).
        await self.say(session, FALL_OPENING, "safety")

    async def on_ask(self, room: str, msg: dict) -> None:
        """`qnet/<room>/ask` - a query, or the responder brief interrupt (§12)."""
        if msg.get("kind") == "responder_brief":
            await self.on_responder_brief(room, msg)
            return

        session = self.live_session(room)
        if session and session.urgency == "safety":
            # Safety wins: a wake phrase is ignored entirely while a safety
            # session is running in that room - the fall response keeps the
            # floor rather than being derailed into a search (§6).
            log.info("[%s] ask kind=query ignored - safety session %s has the floor", room, session.id)
            return
        if session:
            log.info("[%s] ask kind=query ignored - session %s already live (one per room)", room, session.id)
            return
        # The find skill is T6.2; until then a query with no session is a no-op
        # rather than a fake answer.
        log.info("[%s] ask kind=query %r - no find skill yet (T6.2), ignored", room, msg.get("text", ""))

    async def on_responder_brief(self, room: str, msg: dict) -> None:
        """Not a session - an engine-level interrupt, exempt from both rules (§12).

        T1.3 acknowledges it and stops there: composing the summary is one LLM
        call over the room's latest fall file, which is T6.1. The stub line goes
        into the session it *would* summarise, because that is where §12 says
        the real ``brief`` line lands.
        """
        session = self.live_session(room)
        if session is None:
            log.info("[%s] responder brief - no live session to summarise (stub, T6.1)", room)
            return
        log.info("[%s] responder brief acknowledged against session %s (stub, T6.1)", room, session.id)
        await self.append(
            session,
            {
                "event": "brief",
                "ask_id": msg.get("id"),
                "state": "acknowledged",
                "note": "responder brief is an interrupt, not a session; composed in T6.1",
            },
        )

    async def on_heard(self, room: str, msg: dict) -> None:
        """`qnet/<room>/heard` - what was said, while a session is listening."""
        session = self.live_session(room)
        if session is None:
            log.info("[%s] heard with no live session - ignored", room)
            return
        text, silence = msg.get("text", ""), bool(msg.get("silence"))
        log.info("[%s] heard %s", room, "(silence)" if silence else repr(text))
        # T2.2 puts cancel matching and the agent's turn here; v0 just records.
        await self.append(session, {"event": "heard", "text": text, "silence": silence})


async def run_phase(phase, session):
    """Run one phase to its exit. The rails land in T2.2 (DESIGN.md §6)."""
    raise NotImplementedError("phases, timers and cancel are T2.1/T2.2")


async def run(
    config: dict,
    use_llm: bool = True,
    broker: str | None = None,
    port: int | None = None,
) -> int:
    """Connect to the broker and serve sessions until Ctrl-C."""
    mqtt_cfg = config.get("mqtt") or {}
    agent = Agent(
        config=config,
        broker=broker or mqtt_cfg.get("host", DEFAULT_BROKER),
        port=port or mqtt_cfg.get("port", DEFAULT_PORT),
        use_llm=use_llm,
    )
    if not use_llm:
        log.info("--no-llm: accepted, inert in T1.3 - the canned-openings path is T2.2")

    # A quiet ticker so a Windows selector loop notices Ctrl-C between messages
    # instead of sleeping on the socket until the next one arrives.
    async def tick() -> None:
        while True:
            await asyncio.sleep(0.25)

    ticker = asyncio.create_task(tick())
    try:
        await agent.serve()
    except aiomqtt.MqttError as exc:
        log.error("broker %s:%s - %s", agent.broker, agent.port, exc)
        return 1
    finally:
        ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ticker
    return 0
