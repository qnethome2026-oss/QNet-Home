# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The loop and the rails (DESIGN.md §6).

The agent decides what to say, which allowed tool to call, and whether a phase
goal is met. The engine guarantees everything consequential regardless of the
model:

* timers fire on schedule; a missing ``timer`` simply means no timer
* ``on_enter`` actions run before the agent's first turn, once per session
* tools outside the current phase are refused and logged
* cancel is an engine-level interrupt matched before the agent sees a transcript
* nobody is left in silence - the comfort loop speaks grounded facts (§6, T2.4)
* the responder brief is an interrupt, not a session (§12)
* every session writes ``data/sessions/<room>__<skill>__<started_at>.jsonl``
  and publishes the identical stream to ``qnet/session/<id>``

Exit resolution, one rule: an exit whose name matches a phase id jumps to that
phase; any other name ends the session with that label as its final state.

**T2.2 - the rails are real.** A fall now opens a session and hands it to
``run_session``, which walks ``skills/fall.md``'s phases via ``run_phase``
(DESIGN §6's pseudocode, line for line) until an exit or a cancel. What is
still stubbed: the LLM. ``decide`` routes every turn through ``classify_reply``,
a small regex mapping (the ``--no-llm`` mode, and the only mode there is until
T3.4 swaps the classifier for Gemma).

Two design ambiguities resolved here, both flagged in the code where they bite:

1. **``on_enter_done`` is keyed by (phase, action), not action alone.** §6's
   pseudocode writes ``a not in session.on_enter_done``; taken literally,
   ``call_help``'s ``notify_contacts`` would be swallowed by ``escalate``'s and
   §7's second Telegram template ("calling emergency services now") could never
   be sent, contradicting §6's "up to three short pings per fall session". The
   (phase, action) key satisfies both: re-entering ``escalate`` never re-alarms
   the caregiver, and reaching ``call_help`` sends its own milestone once.
2. **A session's ``state`` stays inside the wire contract's vocabulary**
   (``active | closed | cancelled``, §4) while the exit label that ended it
   (``ok``, ``resolved``, ...) is kept on ``session.final`` and written into the
   closing ``phase`` line's ``to`` field. No contract change, no lost fact.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import aiomqtt

from qnet.agent import phases as phaselib
from qnet.ids import new_ulid

log = logging.getLogger("qnet.agent")

# What the agent listens to. `looked` and `status` join in T6.2 / T4.2.
SUBSCRIPTIONS = ("qnet/+/event", "qnet/+/ask", "qnet/+/heard")

FALL_TRIGGER = "fall.detected"
DEFAULT_SESSIONS_DIR = "data/sessions"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
DEFAULT_BROKER = "127.0.0.1"
DEFAULT_PORT = 1883

# §6: "if nothing has been spoken for ~20 s the engine gives the agent a turn".
DEFAULT_COMFORT_INTERVAL_S = 20.0

# The pain double-check (§3, §6) - canned, so it is reachable with no model at
# all. "I'm fine" must never close a session without passing through this.
PAIN_QUESTION = "Any pain? Did you hit your head?"

# Cancel is an engine-level interrupt on EXPLICIT phrases only (§6). Word
# boundaries, so "stopped" and "cancelled the paper" do not close a session -
# and "i'm fine" is deliberately absent: it is a reply, not a cancel.
CANCEL_RE = re.compile(r"\b(cancel|stop|never\s*mind|nevermind|false\s+alarm)\b")

# The terminal label the engine itself produces when the cancel matcher fires.
CANCELLED = "cancelled"


def is_cancel(text: str) -> bool:
    """Explicit-phrase cancel matching, checked before anything else (§6)."""
    return bool(CANCEL_RE.search((text or "").lower()))


@dataclass
class Action:
    """One turn's decision: say | tool | exit | wait. One action per turn (§6)."""

    kind: str  # "say" | "tool" | "exit" | "wait"
    text: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    exit: str = ""

    @property
    def name(self) -> str:
        """What to put in a refusal line."""
        return self.tool or self.exit or self.kind


# --- the --no-llm mind (T3.4 replaces this) -------------------------------

_FINE_RE = re.compile(r"\b(fine|ok|okay|okey|yes|yeah|yep|alright|all right|good|great)\b")
_TROUBLE_RE = re.compile(r"\b(no|nope|not|help|hurt|hurts|hurting|pain|painful|sore|bleeding|"
                         r"can't|cant|cannot|stuck|dizzy|broken)\b")
_PAIN_RE = re.compile(r"\b(pain|painful|hurt|hurts|hurting|sore|ache|aches|aching|head|hit|hip|"
                      r"bleeding|yes|yeah|yep|think so)\b")
_NO_PAIN_RE = re.compile(r"\b(no|nope|nothing|none|didn't|didnt|don't|dont|nowhere|fine|ok|okay|good)\b")


def classify_reply(phase: phaselib.Phase, session: "Session", text: str) -> Action:
    """Map one transcript to one action, with regexes and no model at all.

    This is the whole of ``--no-llm`` - the mode DESIGN §15 calls the fallback
    build and IMPLEMENTATION's "Definition of done" says must never break.
    **T3.4 swaps this one function for a Gemma call** (``agent/llm.py``); the
    engine around it, the rails, the timers and the logging do not change,
    which is the point of keeping the mapping in one place.

    It is deliberately phase-shaped rather than fall-shaped: it reads the
    phase's declared exits, so a skill with different phase names still works.

    * a ``check``-shaped phase (offers both ``ok`` and ``escalate``):
      trouble words escalate; "fine/ok/yes" does **not** close - it asks the
      pain double-check first, and only "no/nothing" after that closes ``ok``.
      Anything unreadable escalates: ambiguity resolves toward help (§6).
    * an ``escalate``-shaped phase (offers ``check``): any coherent reply goes
      back to reassess.
    * anything else (``call_help``, whose only exit is the manual ``resolved``):
      keep listening. No regex may declare a responder has arrived.
    """
    said = (text or "").strip().lower()
    if not said:
        return Action("wait")

    if "ok" in phase.exits and "escalate" in phase.exits:
        if session.awaiting_pain_answer:
            session.awaiting_pain_answer = False
            if _PAIN_RE.search(said):
                return Action("exit", exit="escalate")
            if _NO_PAIN_RE.search(said):
                return Action("exit", exit="ok")
            return Action("exit", exit="escalate")
        if _TROUBLE_RE.search(said):
            return Action("exit", exit="escalate")
        if _FINE_RE.search(said):
            session.awaiting_pain_answer = True
            return Action("say", text=PAIN_QUESTION)
        return Action("exit", exit="escalate")

    if "check" in phase.exits:
        # "they respond coherently - go back and reassess how they are" (§7).
        return Action("exit", exit="check") if len(said) >= 2 else Action("wait")

    return Action("wait")


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
    # (phase_id, action) - see the module docstring, ambiguity 1.
    on_enter_done: set[tuple[str, str]] = field(default_factory=set)
    contacts_notified: bool = False
    emergency_called: bool = False
    awaiting_pain_answer: bool = False
    final: str = ""
    detected_at: float = 0.0
    last_say_at: float = 0.0
    inbox: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None

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


def elapsed_phrase(seconds: float) -> str:
    """"about 45 seconds" / "about 1 minute and 25 seconds" - accurate, never vague.

    Rounded to the nearest 5 s, so the spoken claim is within 2.5 s of the truth
    (T2.4's verify block allows ±5 s). The comfort loop says what is actually
    happening; a rounded number is still a true one, a made-up one is not.
    """
    total = max(0, int(round(max(0.0, seconds) / 5.0) * 5))
    minutes, secs = divmod(total, 60)
    if not minutes:
        return f"{secs} seconds"
    unit = "minute" if minutes == 1 else "minutes"
    if not secs:
        return f"{minutes} {unit}"
    return f"{minutes} {unit} and {secs} seconds"


class Agent:
    """The MQTT client, the session table and the phase engine. One per house."""

    def __init__(
        self,
        config: dict | None = None,
        broker: str = DEFAULT_BROKER,
        port: int = DEFAULT_PORT,
        use_llm: bool = True,
        tools: Mapping[str, Any] | None = None,
        client: Any = None,
    ) -> None:
        self.config = config or {}
        self.broker = broker
        self.port = port
        self.use_llm = use_llm
        storage = self.config.get("storage") or {}
        self.sessions_dir = Path(storage.get("sessions_dir", DEFAULT_SESSIONS_DIR))
        self.skills_dir = Path(storage.get("skills_dir", DEFAULT_SKILLS_DIR))
        self.sessions: dict[str, Session] = {}
        self.client = client
        self._pending: set[asyncio.Task] = set()

        # Tests inject a recorder registry; production resolves qnet.tools lazily
        # so this module never hard-depends on another lane's task landing.
        self._tools = tools
        # Timers scaled so a 30 s phase is testable in 1.5 s (dev.timer_scale).
        self.timer_scale = float((self.config.get("dev") or {}).get("timer_scale", 1.0) or 1.0)
        comfort = self.config.get("comfort") or {}
        self.comfort_interval_s = float(
            self.config.get("comfort_interval_s", comfort.get("interval_s", DEFAULT_COMFORT_INTERVAL_S))
        )
        # Which phases get the comfort loop. §6 names escalate and call_help;
        # the data-driven rule that picks exactly those two out of any skill is
        # "a safety phase that has already taken action on the person's behalf".
        self.comfort_phases: set[str] | None = (
            set(comfort["phases"]) if isinstance(comfort.get("phases"), list) else None
        )
        self.skill = phaselib.load_skill(self.skills_dir / "fall.md", tools=self.tools)

    @property
    def tools(self) -> Mapping[str, Any]:
        """The tool registry (DESIGN §11), resolved as late as possible."""
        if self._tools is not None:
            return self._tools
        try:
            from qnet.tools import TOOLS
        except Exception:  # noqa: BLE001 - T2.3 may not have landed yet
            log.warning("qnet.tools has no TOOLS registry - engine actions will log as unavailable")
            self._tools = {}
            return self._tools
        self._tools = TOOLS
        return self._tools

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
            log.info(
                "skill %s: phases %s | timer_scale %g | comfort every %gs",
                self.skill.name,
                " -> ".join(self.skill.phase_ids),
                self.timer_scale,
                self.comfort_interval_s * self.timer_scale,
            )
            try:
                async for message in client.messages:
                    try:
                        await self.on_message(str(message.topic), message.payload)
                    except Exception:  # a bad message must never take the agent down
                        log.exception("dropping message on %s", message.topic)
            finally:
                await self.shutdown()

    async def shutdown(self) -> None:
        """Stop every session task - nothing half-written on the way out."""
        tasks = [s.task for s in self.sessions.values() if s.task and not s.task.done()]
        tasks += [t for t in self._pending if not t.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

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

    def record(self, session: Session, line: dict) -> dict:
        """Append one log line to the session and its file, synchronously.

        Split out of ``append`` so a tool's ``ctx.log`` (a plain callable, per
        the T2.3 interface) lands in the file in call order, and so the engine
        can tell whether a tool logged its own line - see ``run_tool``.
        """
        # Every line carries `ts` and `event` first, in that order (§6).
        entry = {"ts": line.get("ts", round(time.time(), 1)), **{k: v for k, v in line.items() if k != "ts"}}
        session.log.append(entry)
        with session.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    async def append(self, session: Session, line: dict) -> dict:
        """One log line, two destinations - the file and the bus, not two mechanisms.

        The line goes on disk the instant it happens and the whole session (with
        its log so far) goes out on ``qnet/session/<id>``, so the dashboard
        renders MQTT messages rather than reconstructing anything.
        """
        entry = self.record(session, line)
        await self.publish(f"qnet/session/{session.id}", session.wire())
        return entry

    def _schedule(self, coro) -> None:
        """Fire-and-forget, with a reference kept so the task is not collected."""
        task = asyncio.ensure_future(coro)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def say(self, session: Session, text: str, prio: str) -> None:
        """Speak into the room the session belongs to, and log the line."""
        await self.publish(f"qnet/{session.room}/say", {"text": text, "prio": prio})
        session.last_say_at = time.monotonic()
        await self.append(session, {"event": "say", "text": text})

    # --- triggers ---------------------------------------------------------

    async def on_event(self, room: str, msg: dict) -> None:
        """`qnet/<room>/event` - the only kind in v1 is `fall.detected` (§4)."""
        if msg.get("kind") != self.skill.trigger:
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
            skill=self.skill.name,
            urgency=self.skill.urgency,
            phase=self.skill.first.id,
            path=session_path(self.sessions_dir, room, self.skill.name, time.time()),
            detected_at=detected_at,
            last_say_at=time.monotonic(),  # the comfort clock starts now, not at epoch
        )
        self.sessions[room] = session
        log.info("[%s] session %s open (%s) -> %s", room, session.id, session.skill, session.path.name)

        await self.append(
            session,
            {"ts": round(detected_at, 1), "event": "detected", "kind": msg["kind"], "conf": msg.get("conf")},
        )
        session.task = asyncio.ensure_future(self.run_session(session))

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

        Still acknowledged only: composing the summary is one LLM call over the
        room's latest fall file, which is T6.1. The stub line goes into the
        session it *would* summarise, because that is where §12 says the real
        ``brief`` line lands.
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
        """`qnet/<room>/heard` - hand the transcript to the phase that is listening.

        The engine does not interpret anything here: the listen loop inside
        ``run_phase`` logs it, checks it for cancel, and only then gives it to
        the agent's turn.
        """
        session = self.live_session(room)
        if session is None:
            log.info("[%s] heard with no live session - ignored", room)
            return
        text, silence = msg.get("text", ""), bool(msg.get("silence"))
        log.info("[%s] heard %s", room, "(silence)" if silence else repr(text))
        await session.inbox.put((text, silence))

    # --- the rails (§6) ---------------------------------------------------

    async def run_session(self, session: Session) -> None:
        """Walk the skill's phases until an exit ends the session."""
        skill = self.skill
        phase = skill.first
        try:
            while True:
                outcome = await self.run_phase(phase, session)
                kind, target = skill.resolve_exit(outcome)
                await self.append(session, {"event": "phase", "from": phase.id, "to": target})
                if kind == "jump":
                    log.info("[%s] %s -> %s", session.room, phase.id, target)
                    session.phase = target
                    phase = skill.phase(target)
                    continue
                await self.close(session, CANCELLED if target == CANCELLED else "closed", target)
                return
        except asyncio.CancelledError:
            raise
        except Exception:  # a broken turn must not strand the session silently
            log.exception("[%s] session %s failed in phase %s", session.room, session.id, session.phase)
            await self.close(session, "closed", "error")

    async def close(self, session: Session, state: str, final: str) -> None:
        """End the session: contract-vocabulary ``state``, exit label as ``final``."""
        session.state = state
        session.final = final
        log.info("[%s] session %s %s (%s)", session.room, session.id, state, final)
        await self.publish(f"qnet/session/{session.id}", session.wire())

    async def run_phase(self, phase: phaselib.Phase, session: Session) -> str:
        """DESIGN §6's ``run_phase``, line for line. Returns the exit taken.

        Canned opening first (instant, cannot be skipped), then the ``on_enter``
        actions - so by the time the model would get a turn, the caregiver has
        already been messaged. Then the listen loop, under an engine-owned
        timer, with the cancel matcher ahead of everything else.
        """
        session.phase = phase.id
        if phase.opening:
            await self.say(session, phase.opening, "safety")

        for action in phase.on_enter:
            key = (phase.id, action)
            if key in session.on_enter_done:
                continue
            session.on_enter_done.add(key)
            await self.run_tool(session, action, phase=phase, kind=phase.id)

        deadline = time.monotonic() + phase.timer.after_s * self.timer_scale if phase.timer else None
        comfort = self.comforts(phase)

        while True:
            timeout = self._next_wake(session, deadline, comfort)
            try:
                text, silence = await asyncio.wait_for(session.inbox.get(), timeout)
            except (TimeoutError, asyncio.TimeoutError):
                if deadline is not None and time.monotonic() >= deadline - 1e-3:
                    log.info("[%s] %s timer fired after %gs -> %s",
                             session.room, phase.id, phase.timer.after_s * self.timer_scale, phase.timer.goto)
                    return phase.timer.goto
                if comfort:
                    await self.comfort(session)
                continue

            await self.append(session, {"event": "heard", "text": text, "silence": silence})
            if silence:
                # "Silence during a session is published as {silence: true} and
                # the phase timer decides what happens next" (§9).
                continue
            if is_cancel(text):
                # Checked before the agent ever sees the transcript (§6).
                if session.contacts_notified:
                    # "Nobody should be left worrying because the system
                    # escalated and then went quiet."
                    await self.run_tool(session, "notify_contacts", phase=phase, kind="false_alarm")
                log.info("[%s] cancel matched %r - closing from %s", session.room, text, phase.id)
                return CANCELLED

            action = await self.decide(phase, session, text)
            if action.kind == "wait":
                continue
            if not self.allows(phase, action):
                await self.append(
                    session,
                    {"event": "refusal", "tool": action.name, "phase": phase.id, "kind": action.kind},
                )
                log.info("[%s] refused %s %r outside phase %s", session.room, action.kind, action.name, phase.id)
                continue
            if action.kind == "exit":
                return action.exit
            await self.perform(session, phase, action)

    def _next_wake(self, session: Session, deadline: float | None, comfort: bool) -> float | None:
        """How long to wait for a transcript: the timer, or the next comfort line."""
        now = time.monotonic()
        waits = []
        if deadline is not None:
            waits.append(deadline - now)
        if comfort:
            waits.append(session.last_say_at + self.comfort_interval_s * self.timer_scale - now)
        return max(0.0, min(waits)) if waits else None

    def comforts(self, phase: phaselib.Phase) -> bool:
        """Does the comfort loop run in this phase? §6 says escalate and call_help.

        Data-driven rather than hardcoded: a phase of a ``safety`` skill that
        fires ``on_enter`` actions is one where the engine has already acted on
        the person's behalf - exactly ``escalate`` and ``call_help`` in
        ``fall.md``, and the right default for any future safety skill. A
        ``comfort.phases`` list in the config overrides it outright.
        """
        if self.comfort_phases is not None:
            return phase.id in self.comfort_phases
        return self.skill.urgency == "safety" and bool(phase.on_enter)

    async def comfort(self, session: Session) -> None:
        """Never leave them in silence (§6, T2.4) - one grounded, true update.

        Grounded in the session log, never filler: what has actually been done
        and how long it has actually been. Positioning guidance is said once in
        the opening and never repeated here (fall.md's Guidance).
        """
        quiet_for = time.monotonic() - session.last_say_at
        if quiet_for < self.comfort_interval_s * self.timer_scale:
            # Something else just spoke - drop this update rather than overlap
            # it. There is exactly one speaker per session by construction.
            return
        await self.say(session, self.comfort_line(session), "comfort")

    def comfort_line(self, session: Session) -> str:
        """Assemble the update from facts the session log actually holds."""
        facts = []
        if session.contacts_notified:
            facts.append(f"{self.contact_name()} has been messaged")
        if session.emergency_called:
            facts.append("emergency services are on the way")
        facts.append(f"it's been about {elapsed_phrase(time.time() - session.detected_at)} since I saw you fall")
        if len(facts) > 1:
            body = ", ".join(facts[:-1]) + ", and " + facts[-1]
        else:
            body = facts[0]
        return f"I'm still here with you. {body[0].upper()}{body[1:]}."

    def contact_name(self) -> str:
        """The first configured contact's name - the caregiver we say out loud."""
        contacts = self.config.get("contacts") or []
        first = contacts[0] if contacts else {}
        return (first or {}).get("name") or "your contact"

    # --- the agent's turn -------------------------------------------------

    async def decide(self, phase: phaselib.Phase, session: Session, text: str) -> Action:
        """One action per turn. Gemma lands here in T3.4; today it is regexes."""
        if self.use_llm:
            # DESIGN §6: "If Gemma is unavailable, the engine still walks the
            # phases on their timers using the canned openings." Until T3.4
            # there is no client at all, so every mode is the canned one.
            log.debug("llm mode requested but agent/llm.py is T3.3/T3.4 - using the canned classifier")
        return classify_reply(phase, session, text)

    def allows(self, phase: phaselib.Phase, action: Action) -> bool:
        """The rails: the phase's allowlist and its declared exits (§6, §11)."""
        if action.kind == "say":
            return True
        if action.kind == "exit":
            return phase.allows_exit(action.exit)
        if action.kind == "tool":
            return phase.allows_tool(action.tool, self.tools)
        return False

    async def perform(self, session: Session, phase: phaselib.Phase, action: Action) -> None:
        """Execute an allowed non-exit action."""
        if action.kind == "say":
            await self.say(session, action.text, "safety")
        elif action.kind == "tool":
            await self.run_tool(session, action.tool, phase=phase, **action.args)

    async def run_tool(self, session: Session, name: str, phase: phaselib.Phase | None = None, **args) -> Any:
        """Call a registered tool and make sure exactly one ``tool`` line is logged.

        The T2.3 tools log their own line through ``ctx.log``; if a tool does
        not (or is not registered yet), the engine writes the line itself. Kwargs
        are filtered against the tool's signature, so ``call_emergency(ctx)`` and
        ``notify_contacts(ctx, kind=...)`` are both called correctly from one
        call site.
        """
        spec = self.tools.get(name)
        marker = len(session.log)

        if spec is None:
            # T2.3 not loaded: make the absence loud rather than silent, and
            # keep the SIMULATED word attached to the emergency path (§14).
            simulated = name == "call_emergency"
            log.warning("TOOL %s not registered - %s", name, "SIMULATED emergency call" if simulated else "not sent")
            entry: dict = {"event": "tool", "tool": name, "result": "unavailable"}
            if simulated:
                entry["detail"] = {"SIMULATED": True, "note": "no call_emergency tool registered"}
            await self.append(session, entry)
            result: Any = None
        else:
            ctx = self.tool_context(session)
            try:
                result = await spec.fn(ctx, **_supported(spec.fn, args))
            except Exception as exc:  # a tool should never raise; if it does, log the fact
                log.exception("tool %s failed", name)
                result = {"error": repr(exc)}
            if len(session.log) == marker:
                await self.append(session, {"event": "tool", "tool": name, "result": _result_word(result),
                                            "detail": result if isinstance(result, dict) else None})
            else:
                # The tool logged its own line; publish so the dashboard sees it.
                await self.publish(f"qnet/session/{session.id}", session.wire())

        if name == "notify_contacts":
            # "Tracked with one boolean, set the moment any notification goes
            # out" (§6) - including the console fallback, which is still a
            # notification the caregiver's follow-up must match.
            session.contacts_notified = True
        if name == "call_emergency":
            session.emergency_called = True
        return result

    def tool_context(self, session: Session):
        """The T2.3 ``ToolContext`` - room, session id, config, publish, log."""
        def _log(event: dict) -> None:
            self.record(session, event)

        try:
            from qnet.tools import ToolContext
        except Exception:  # noqa: BLE001 - keep the engine runnable without T2.3
            from types import SimpleNamespace as ToolContext  # type: ignore[assignment]
        return ToolContext(
            room=session.room,
            session_id=session.id,
            config=self.config,
            publish=self.publish,
            log=_log,
        )


def _supported(fn, args: dict) -> dict:
    """Only pass kwargs the tool actually declares (or everything, if it takes **kwargs)."""
    if not args:
        return {}
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return args
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return args
    return {k: v for k, v in args.items() if k in params}


def _result_word(result: Any) -> str:
    """One word for the log line's ``result`` field (contracts/fixtures/session.json)."""
    if isinstance(result, dict):
        for key in ("result", "status", "channel"):
            if isinstance(result.get(key), str):
                return result[key]
        if result.get("SIMULATED"):
            return "SIMULATED"
        if "error" in result:
            return "error"
        return "sent"
    return "sent" if result is None else str(result)


async def run(
    config: dict,
    use_llm: bool = True,
    broker: str | None = None,
    port: int | None = None,
) -> int:
    """Connect to the broker and serve sessions until Ctrl-C."""
    mqtt_cfg = config.get("mqtt") or {}
    try:
        agent = Agent(
            config=config,
            broker=broker or mqtt_cfg.get("host", DEFAULT_BROKER),
            port=port or mqtt_cfg.get("port", DEFAULT_PORT),
            use_llm=use_llm,
        )
    except phaselib.SkillError as exc:
        # Load-time validation, loud and early: a bad skill file stops the agent
        # at startup rather than misbehaving mid-incident (T2.1).
        log.error("skill file rejected: %s", exc)
        return 2
    if not use_llm:
        log.info("--no-llm: phases, timers and the canned classifier - no model in the loop")

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
        await agent.shutdown()
    return 0
