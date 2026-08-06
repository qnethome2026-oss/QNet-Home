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
* a trusted contact's Telegram reply is matched on the rails too
  (T-contact-ack): an ack during ``escalate`` -> ``contact_engaged`` (with a
  180 s backstop to ``call_help``), "call 911" -> ``call_help`` immediately -
  the LLM never sees or routes contact text
* nobody is left in silence - the comfort loop speaks grounded facts (§6, T2.4)
* the responder brief is an interrupt, not a session (§12)
* every session writes ``data/sessions/<room>__<skill>__<started_at>.jsonl``
  and publishes the identical stream to ``qnet/session/<id>``

Exit resolution, one rule: an exit whose name matches a phase id jumps to that
phase; any other name ends the session with that label as its final state.

**T2.2 - the rails are real.** A fall now opens a session and hands it to
``run_session``, which walks ``skills/fall.md``'s phases via ``run_phase``
(DESIGN §6's pseudocode, line for line) until an exit or a cancel.

**T3.4 - Gemma is in the loop, behind the flag.** ``decide`` asks
``agent/llm.py`` to classify the reply and falls back to ``classify_reply``'s
regex mapping whenever the model returns ``None``; the comfort loop asks it to
word the update from the engine's own facts and falls back to the assembled
sentence. Two properties hold by construction: ``--no-llm`` is exactly the
code path it always was (no client is built, so not one branch differs), and
the model can only ever choose *between decisions the phase already allows* -
timers, ``on_enter`` actions, the pain double-check, the refusals and the
logging are all engine-owned either way.

**T6.1 / T6.2 - the second capability set.** The responder brief (§12) is an
engine-level *interrupt*: pause the comfort loop, read the room's latest fall
file, one LLM call to word the timeline, speak it, resume - it never enters the
session table, so the one-session-per-room rule cannot block it. The find flow
(§13) is an ordinary routine session on ``skills/find.md``, plus one ``last_find``
variable and one if-statement for the "I still don't see them" follow-up.
Neither touched the fall path: the phases, the timers, the cancel matcher and
the notification rules are exactly what they were.

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
3. **The engine calls ``look_in_rooms``; the model only words the answer.**
   ``find.md`` lists it in the phase's ``tools:`` allowlist as DESIGN §13 shows,
   and the allowlist is still checked (``phase.allows_tool``) - but SDK-native
   tool-calling does not work on GenieX v0.3.18 (§10, measured), so a phase whose
   entire job is one broadcast cannot depend on the model emitting a tool call.
   The search fires on phase entry, exactly like an ``on_enter`` action, and the
   model's job is the same as everywhere else in this system: wording facts the
   engine already has. Same rails, same refusal path, no tool-calling risk.
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

from qnet.agent import llm as llmlib
from qnet.agent import phases as phaselib
from qnet.ids import new_ulid

log = logging.getLogger("qnet.agent")

# What the agent listens to. `status` joins in T4.2; `looked` is T6.2's - the
# replies to `qnet/look`, which reach `look_in_rooms` through `Agent.subscribe`.
SUBSCRIPTIONS = ("qnet/+/event", "qnet/+/ask", "qnet/+/heard", "qnet/+/looked")

FALL_TRIGGER = "fall.detected"
DEFAULT_SESSIONS_DIR = "data/sessions"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
DEFAULT_BROKER = "127.0.0.1"
DEFAULT_PORT = 1883

# §6: "if nothing has been spoken for ~20 s the engine gives the agent a turn".
DEFAULT_COMFORT_INTERVAL_S = 20.0

# §13: "the agent remembers the last find result for 2 minutes". One variable,
# one if-statement - no conversation history, no session linking.
DEFAULT_LAST_FIND_WINDOW_S = 120.0

# The one line §12 specifies word for word, for a room with no fall on file.
NO_FALL_HISTORY = "No fall has been recorded in this room."

# What to say when someone woke the house without naming anything to look for
# and there is no remembered search to fall back on (§13's follow-up window).
WHAT_TO_FIND = "What should I look for?"

# `say.prio` for anything that is neither a safety line nor the fall comfort
# loop: a find answer, and a brief asked in a room with no live fall session.
ROUTINE_PRIO = "routine"

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


# --- trusted-contact replies: engine rails, never the LLM (T-contact-ack) --
#
# The escalation Telegram is a question ("Reply OK if you can check on
# {resident} - otherwise I'll call emergency services in 30 seconds"), and the
# reply is matched HERE, exactly like cancel: the model never sees contact
# text and never routes it. Word boundaries and short-message tolerance - a
# bare "ok" or "omw" is a normal phone reply.
CONTACT_ACK_RE = re.compile(r"\b(?:ok|okay|on it|got it|omw|on my way|i got this|handling)\b")

# "call 911" / "call emergency (services)" from a contact summons help
# immediately. Checked FIRST, so "ok, call 911" calls rather than engages.
CONTACT_EMERGENCY_RE = re.compile(r"\bcall\s+(?:911|9-1-1|emergency(?:\s+services)?)\b")

# fall.md's ladder, by name. Contact replies route only into a live safety
# session sitting in one of CONTACT_PHASES - the phases where the contact has
# already been alarmed and the emergency call is pending or placed. A reply
# with no such session is log-dropped: an unsolicited "ok" must do nothing.
ESCALATE_PHASE = "escalate"
CONTACT_ENGAGED_PHASE = "contact_engaged"
CALL_HELP_PHASE = "call_help"
CONTACT_PHASES = frozenset({ESCALATE_PHASE, CONTACT_ENGAGED_PHASE, CALL_HELP_PHASE})


def contact_verdict(text: str) -> str | None:
    """What a contact's reply means on the rails: "emergency", "ack" or nothing."""
    said = (text or "").lower()
    if CONTACT_EMERGENCY_RE.search(said):
        return "emergency"
    if CONTACT_ACK_RE.search(said):
        return "ack"
    return None


# --- "where are my glasses" -> "glasses" (§13) ----------------------------

# The wake phrase is already stripped node-side (§13: it is a plain string check
# on the transcript, and only the remainder is published), so these match the
# question itself. Deliberately a handful of literal shapes rather than anything
# clever: the model is the fallback, and asking the person is the fallback's
# fallback - both better than a house-wide search for a misparse.
_OBJECT_RES = (
    re.compile(r"\bwhere(?:'s|s| is| are)\s+(?P<obj>.+)$"),
    re.compile(r"\bwhere did (?:i|we) (?:leave|put)\s+(?P<obj>.+)$"),
    re.compile(r"\b(?:have you seen|has anyone seen|can you (?:see|find)|look for|find|locate)\s+(?P<obj>.+)$"),
    re.compile(r"\bi (?:can't|cant|cannot) find\s+(?P<obj>.+)$"),
)
_DETERMINER_RE = re.compile(r"^(?:my|the|a|an|our|his|her|their|some)\s+")
_TRAILER_RE = re.compile(r"\s*\b(?:please|anywhere|again|for me|right now|now)\b\s*$")
_EDGE_PUNCT_RE = re.compile(r"^[\s\"'`.,!?]+|[\s\"'`.,!?]+$")

# "where's my glasses i can't find them anywhere" - the capture runs to the end
# of the sentence, so everything after the object must be cut, not just known
# trailers. Clause punctuation ends the object outright; so does any word that
# starts a new thought. The rare compound this costs ("salt and pepper" ->
# "salt") still finds the right shelf; the trailing-clause misparse it prevents
# ("glasses i can't find them anywhere") finds nothing at all.
_CLAUSE_PUNCT_RE = re.compile(r"[.,;!?]")
_CLAUSE_STARTERS = frozenset(
    {"i", "i'm", "im", "i've", "ive", "we", "you", "and", "but", "so", "or",
     "because", "cause", "cos", "since", "please", "thanks", "thank",
     "anywhere", "somewhere"}
)


def _cut_trailing_clause(obj: str) -> str:
    obj = _CLAUSE_PUNCT_RE.split(obj, 1)[0].strip()
    kept: list[str] = []
    for word in obj.split():
        if word in _CLAUSE_STARTERS:
            break
        kept.append(word)
    return " ".join(kept)

# A question that names only a pronoun has named nothing: "where are they" is
# exactly the follow-up §13 routes to `guide` off the remembered object.
_PRONOUN_OBJECTS = frozenset(
    {"it", "them", "they", "those", "these", "that", "this", "one", "thing", "things", "something", "anything"}
)


def extract_object(text: str) -> str | None:
    """The thing to look for, or ``None`` if the sentence named nothing (§13).

    ``None`` is a real answer, not a failure: it is what routes an object-less
    follow-up to `guide`, and what makes the engine ask rather than guess.
    """
    said = _EDGE_PUNCT_RE.sub("", (text or "").strip().lower())
    if not said:
        return None
    for pattern in _OBJECT_RES:
        match = pattern.search(said)
        if not match:
            continue
        obj = _cut_trailing_clause(match.group("obj").strip())
        obj = _EDGE_PUNCT_RE.sub("", obj)
        obj = _EDGE_PUNCT_RE.sub("", _TRAILER_RE.sub("", _DETERMINER_RE.sub("", obj)).strip())
        if not obj or obj in _PRONOUN_OBJECTS or len(obj.split()) > 4:
            return None
        return obj
    return None


def name_rooms(rooms: list[str], joiner: str = "and") -> str:
    """"the kitchen and the bedroom" - what was actually checked, said out loud."""
    named = [f"the {room}" for room in rooms]
    if not named:
        return ""
    if len(named) == 1:
        return named[0]
    return ", ".join(named[:-1]) + f" {joiner} " + named[-1]


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
    **T3.4 put Gemma in front of it, not in place of it** (``agent/llm.py``):
    every turn the model declines to answer lands here unchanged, which is the
    point of keeping the mapping in one place.

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
    # The contact who acknowledged the escalation question (T-contact-ack) -
    # the name the contact_engaged opening speaks, grounded in a real reply.
    engaged_contact: str = ""
    # The responder brief pauses the comfort loop while it speaks (§12), so the
    # two never talk over each other. Read-only against phases and timers.
    comfort_paused: bool = False
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


def brief_line(facts: list[str]) -> str:
    """The engine's own responder brief - the timeline as one spoken paragraph.

    What gets said when Gemma is unavailable or unusable (§12's one LLM call is
    wording, not content), and the floor under every brief: every clause here
    came off the session's own JSONL.
    """
    if not facts:
        return NO_FALL_HISTORY
    body = ". ".join(fact[0].upper() + fact[1:] if fact else fact for fact in facts)
    return f"Here's what happened. {body}."


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
        llm: Any = None,
    ) -> None:
        self.config = config or {}
        self.broker = broker
        self.port = port
        self.use_llm = use_llm
        self.llm = llm if llm is not None else (self._build_llm() if use_llm else None)
        storage = self.config.get("storage") or {}
        self.sessions_dir = Path(storage.get("sessions_dir", DEFAULT_SESSIONS_DIR))
        self.skills_dir = Path(storage.get("skills_dir", DEFAULT_SKILLS_DIR))
        self.sessions: dict[str, Session] = {}
        self.client = client
        self._pending: set[asyncio.Task] = set()
        # Topic-filter -> queue, for tools that have to listen as well as speak
        # (T6.2's `look_in_rooms`). See `subscribe`.
        self._listeners: list[tuple[re.Pattern[str], asyncio.Queue]] = []
        # §13's whole follow-up mechanism: {object, results, ts}, or nothing.
        find_cfg = self.config.get("find") or {}
        self.last_find: dict | None = None
        self.last_find_window_s = float(find_cfg.get("last_find_window_s", DEFAULT_LAST_FIND_WINDOW_S))
        # §4: the rooms this house knows. None (no rooms: map, e.g. minimal
        # test configs) means accept everything; a configured map means inbound
        # traffic for any other room id is dropped in on_message.
        rooms_cfg = self.config.get("rooms")
        self.room_ids: set[str] | None = set(rooms_cfg.keys()) if isinstance(rooms_cfg, dict) and rooms_cfg else None

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
        self.find_skill = self._load_optional("find.md")
        self.brief_skill = self._load_optional("responder-brief.md", interrupt=True)

    def _load_optional(self, filename: str, interrupt: bool = False) -> Any:
        """A second-capability skill file, or ``None`` - never a dead agent (T6.1/T6.2).

        ``fall.md`` is load-or-die: a house whose fall response will not start is
        broken, and §6's rails are the whole safety argument. These two are not:
        a missing or malformed ``find.md`` costs the house its search feature and
        nothing else, so it is logged loudly and the fall path is untouched -
        "degraded, not broken", the same rule the LLM gets (§6).
        """
        path = self.skills_dir / filename
        try:
            if interrupt:
                return phaselib.load_interrupt_skill(path)
            return phaselib.load_skill(path, tools=self.tools)
        except phaselib.SkillError as exc:
            log.error("skill file %s rejected (%s) - that capability is off, the fall path is not", filename, exc)
            return None

    def _build_llm(self) -> Any:
        """The Gemma client, or ``None`` - never an exception at startup (T3.4).

        ``llm.base_url`` in house.yaml is optional; the default is the
        on-device GenieX endpoint. Constructing the client opens no socket, so
        a brain that is down costs nothing here - it shows up as a ``None``
        decision at the first turn and the regex classifier takes over.
        """
        base_url = (self.config.get("llm") or {}).get("base_url", llmlib.BASE_URL)
        try:
            client = llmlib.LlmClient(base_url=base_url)
        except Exception as exc:  # noqa: BLE001 - e.g. openai not installed
            log.warning("no LLM client (%s) - running on the canned classifier", exc)
            return None
        log.info("llm %s (%s) - regex classifier stays as the fallback", base_url, llmlib.MODEL)
        return client

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
            self.start_contact_poller()
            try:
                async for message in client.messages:
                    try:
                        await self.on_message(str(message.topic), message.payload)
                    except Exception:  # a bad message must never take the agent down
                        log.exception("dropping message on %s", message.topic)
            finally:
                await self.shutdown()

    def start_contact_poller(self) -> None:
        """Start the inbound-Telegram poller, if the config makes it possible.

        Only ``serve`` calls this, and only when the bot token and at least one
        contact chat id are real - so tests, ``--no-llm`` dev runs and a
        template config all run with no network and no poller at all
        (T-contact-ack). The task lives in ``_pending``: ``shutdown`` cancels
        it with everything else.
        """
        from qnet.agent import telegram_poller

        if not telegram_poller.enabled(self.config):
            log.info("telegram poller off - no real bot token/contact chat id in config")
            return
        poller = telegram_poller.TelegramPoller(self.config, self.on_contact_reply)
        self._schedule(poller.run())
        log.info(
            "telegram poller up - contact replies route on the engine rails (contacts: %s)",
            ", ".join(poller.contacts.values()),
        )

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

    def subscribe(self, topic_filter: str):
        """Listen to a topic filter for as long as the ``async with`` block lasts.

        The one capability T6.2 had to add to ``ToolContext``: ``look_in_rooms``
        broadcasts ``qnet/look`` and then has to *hear* the ``looked`` replies
        (§13). Rather than give tools their own MQTT client - a second
        connection, a second subscription, a second thing to fail - the engine
        fans its own already-dispatched messages out to whoever is listening.

        Yields an ``asyncio.Queue`` of ``(topic, payload)``. Registration
        happens before the caller publishes anything, and deregistration is in a
        ``finally``, so a fast node cannot answer into a queue nobody holds and
        a timed-out search cannot leak a listener.
        """
        agent = self
        pattern = _topic_pattern(topic_filter)

        @contextlib.asynccontextmanager
        async def _listen():
            queue: asyncio.Queue = asyncio.Queue()
            entry = (pattern, queue)
            agent._listeners.append(entry)
            try:
                yield queue
            finally:
                with contextlib.suppress(ValueError):
                    agent._listeners.remove(entry)

        return _listen()

    def fanout(self, topic: str, msg: dict) -> None:
        """Hand one already-parsed message to every matching listener."""
        for pattern, queue in list(self._listeners):
            if pattern.match(topic):
                queue.put_nowait((topic, msg))

    async def on_message(self, topic: str, payload: bytes) -> None:
        """Route one message by topic. `<room>` is the node's identity (§4)."""
        msg = json.loads(payload)
        # Listeners first, and for every topic: a `looked` reply belongs to
        # whichever tool is waiting on it, not to the room-and-kind router.
        self.fanout(topic, msg)
        parts = topic.split("/")
        if len(parts) != 3:
            return
        _, room, kind = parts
        # §4: <room> is an id from config's rooms: map. The broker is shared
        # infrastructure on a workshop LAN, and a coexisting stack was observed
        # live-publishing STT chatter under rooms this house has never heard of
        # - 60 junk sessions before this guard. Unknown rooms are dropped
        # loudly, sessions are never opened for them.
        if kind in ("event", "ask", "heard") and self.room_ids is not None and room not in self.room_ids:
            log.info("[%s] %s dropped - room not in this house's config", room, kind)
            return
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
        if self.find_skill is None:
            log.warning("[%s] ask kind=query %r - no find skill loaded, ignored", room, msg.get("text", ""))
            return

        text = msg.get("text", "")
        obj, mode = extract_object(text), "find"
        if obj is None and self.find_is_remembered():
            # §13's deliberately dumb rule: an ask that names no object, inside
            # the window, is "I still don't see them" - the remembered object,
            # and the room they are speaking from *now*.
            obj, mode = self.last_find["object"], "guide"  # type: ignore[index]
            log.info("[%s] object-less ask inside the window -> guide for %r", room, obj)
        elif obj is None and self.llm is not None:
            # The heuristic missed; give the model one short, closed-answer turn
            # before falling back to asking the person (§13).
            obj = await asyncio.to_thread(self.llm.extract_object, text)
            log.info("[%s] heuristic found no object in %r - llm said %r", room, text, obj)
        if obj is None:
            log.info("[%s] no object named and nothing remembered - asking", room)
            await self.publish(f"qnet/{room}/say", {"text": WHAT_TO_FIND, "prio": ROUTINE_PRIO})
            return

        await self.start_find(room, msg, obj, mode)

    # --- "where's my stuff" (§13) ----------------------------------------

    def find_is_remembered(self) -> bool:
        """Is there a find result inside §13's two-minute follow-up window?

        House-wide on purpose, not per room: the whole point of the follow-up is
        that they walked into the *other* room and still can't see it.
        """
        if not self.last_find:
            return False
        return (time.time() - float(self.last_find.get("ts") or 0)) <= self.last_find_window_s

    async def start_find(self, room: str, msg: dict, obj: str, mode: str) -> Session:
        """Open a routine session on ``find.md`` and hand it to ``run_find``.

        A session like any other - one per room, logged to its own file, on the
        dashboard's feed - but ``routine``, so it never takes the screen over
        from a fall (§14), and with no timers and no ``on_enter`` actions,
        which §13 says is the whole difference between the two skills.
        """
        skill = self.find_skill
        phase = skill.phase("search" if mode == "find" else "guide")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        session = Session(
            id=new_ulid(),
            room=room,
            skill=skill.name,
            urgency=skill.urgency,
            phase=phase.id,
            path=session_path(self.sessions_dir, room, skill.name, time.time()),
            detected_at=float(msg.get("ts") or time.time()),
            last_say_at=time.monotonic(),
        )
        self.sessions[room] = session
        log.info("[%s] session %s open (%s/%s, looking for %r) -> %s",
                 room, session.id, session.skill, phase.id, obj, session.path.name)
        # The question itself is the first line of the timeline. It is a
        # transcript, so it is a `heard` line - no new log event kind, and the
        # dashboard renders it with no change (contracts/mqtt.md).
        await self.append(session, {"event": "heard", "text": msg.get("text", ""), "silence": False})
        session.task = asyncio.ensure_future(self.run_find(session, phase, obj, mode))
        return session

    async def run_find(self, session: Session, phase: phaselib.Phase, obj: str, mode: str) -> None:
        """One search or one guide: look, say what was found, close. No timers.

        The search fires on phase entry rather than on a model's tool call - see
        the module docstring, ambiguity 3 - and the phase's allowlist is still
        what authorises it.
        """
        try:
            result = await self.look(session, phase, obj, mode)
            facts, spoken, outcome = self.find_facts(session, obj, mode, result)
            await self.say(session, await self.find_text(session, facts, spoken), ROUTINE_PRIO)
            self.remember_find(obj, result)
            await self.append(session, {"event": "phase", "from": phase.id, "to": outcome})
            await self.close(session, "closed", outcome)
        except asyncio.CancelledError:
            raise
        except Exception:  # a broken search must not strand the session silently
            log.exception("[%s] find session %s failed in phase %s", session.room, session.id, phase.id)
            await self.close(session, "closed", "error")

    async def look(self, session: Session, phase: phaselib.Phase, obj: str, mode: str) -> dict:
        """Call ``look_in_rooms`` - through the phase's allowlist, like any tool."""
        if not phase.allows_tool("look_in_rooms", self.tools):
            await self.append(
                session, {"event": "refusal", "tool": "look_in_rooms", "phase": phase.id, "kind": "tool"}
            )
            log.warning("[%s] look_in_rooms is not allowed in phase %s", session.room, phase.id)
            return {}
        result = await self.run_tool(
            session,
            "look_in_rooms",
            phase=phase,
            object=obj,
            mode=mode,
            room=session.room if mode == "guide" else None,
        )
        return result if isinstance(result, dict) else {}

    def find_facts(self, session: Session, obj: str, mode: str, result: dict) -> tuple[list[str], str, str]:
        """§13's three-row table: the facts, the engine's own sentence, the exit.

        | replies | what it says |
        |---|---|
        | all answered, one found it | "They're in the bedroom, on the nightstand." |
        | all answered, none found it | "I looked in the kitchen and the bedroom and I don't see them." |
        | some didn't answer | "I looked in the kitchen and don't see them - I couldn't reach the bedroom." |

        The third row is the one worth building, and it is why the tool returns
        ``unreachable`` separately: a "not found" that only checked half the
        house must not sound like a "not found" that checked all of it.
        """
        replies = [r for r in (result.get("replies") or []) if isinstance(r, dict)]
        unreachable = [str(r) for r in (result.get("unreachable") or [])]
        searched = [str(r.get("room")) for r in replies]
        found = [r for r in replies if r.get("found")]

        if mode == "guide":
            return self.guide_facts(session, obj, replies)

        if found:
            # No "is"/"are": one wording that is right for both "my phone" and
            # "my glasses", with no pluralisation guess about a spoken noun.
            where = " and ".join(
                f"in the {r['room']}" + (f", {r['answer']}" if r.get("answer") else "") for r in found
            )
            facts = [f"the {obj} were found {where}"]
            if unreachable:
                facts.append(f"{name_rooms(unreachable)} did not answer")
            return facts, f"I found your {obj} {where}.", "found"

        if searched and unreachable:
            facts = [
                f"I looked in {name_rooms(searched)} and did not see the {obj}",
                f"I could not reach {name_rooms(unreachable, joiner='or')}",
            ]
            spoken = (f"I looked in {name_rooms(searched)} and don't see your {obj} — "
                      f"I couldn't reach {name_rooms(unreachable, joiner='or')}.")
            return facts, spoken, "not_found"

        if searched:
            facts = [f"I looked in {name_rooms(searched)} and did not see the {obj}"]
            return facts, f"I looked in {name_rooms(searched)} and I don't see your {obj}.", "not_found"

        if unreachable:
            facts = [f"no room answered - I could not reach {name_rooms(unreachable, joiner='or')}"]
            spoken = (f"I couldn't reach {name_rooms(unreachable, joiner='or')}, "
                      f"so I wasn't able to look for your {obj}.")
            return facts, spoken, "not_found"

        return ([f"there are no rooms I can look in for the {obj}"],
                f"I don't have any rooms I can look in for your {obj}.", "not_found")

    def guide_facts(self, session: Session, obj: str, replies: list[dict]) -> tuple[list[str], str, str]:
        """They are in the right room and still can't see it (§13's `guide`)."""
        mine = next((r for r in replies if r.get("room") == session.room), None) or (replies[0] if replies else None)
        if mine and mine.get("found") and mine.get("answer"):
            facts = [
                f"the person is in the {session.room} and cannot see their {obj}",
                f"the {mine['room']} camera says the {obj} are {mine['answer']}",
            ]
            return facts, f"Look {mine['answer']}.", "done"
        if mine and mine.get("found"):
            facts = [f"the {obj} are somewhere in the {session.room}, with no more detail than that"]
            return facts, f"They should be there in the {session.room} — have another look around.", "done"
        facts = [f"I looked again in the {session.room} and still cannot see the {obj}"]
        return facts, f"I looked again and I still can't see your {obj} in the {session.room}.", "done"

    async def find_text(self, session: Session, facts: list[str], fallback: str) -> str:
        """The engine's own sentence, always - the model no longer words find answers.

        This used to hand the facts to Gemma for wording, like comfort lines.
        Observed live (2026-08-06): facts said "no room answered - I could not
        reach the kitchen or the bedroom" and the model worded "The item is in
        the living room. The living room camera reported that the item is
        there." - a fabricated location, spoken. A search answer IS the safety
        content of this skill; there is nothing for a model to add to "it's on
        the counter next to the kettle" that is worth that risk, so the
        deterministic sentence (which --no-llm always used) is now the only
        path. The facts still land in the session log for the brief.
        """
        del session, facts  # kept for call-site symmetry with comfort_text
        return fallback

    def remember_find(self, obj: str, result: dict) -> None:
        """§13's ``last_find``: one object, its results, and when (2-minute life)."""
        self.last_find = {"object": obj, "results": result, "ts": time.time()}

    # --- the responder brief (§12) ---------------------------------------

    async def on_responder_brief(self, room: str, msg: dict) -> None:
        """Not a session - an engine-level interrupt, exempt from both rules (§12).

        The sequence, exactly as §12 writes it: pause the comfort loop -> read
        the room's latest fall file -> one LLM call to word the timeline ->
        speak it -> resume. The fall session's phases and timers never notice:
        nothing here touches ``session.phase``, its inbox or its deadline, and
        the pause is one boolean the comfort loop checks.

        It is exempt from the one-session-per-room rule because it never enters
        the session table - which matters, since a responder arriving
        mid-escalation is exactly when the brief is needed.
        """
        live = self.live_session(room)
        # A find session in the room is not something to speak over carefully -
        # only a live *safety* session owns the comfort loop and the safety
        # priority (§12 is scoped to fall response).
        safety = live if (live is not None and live.urgency == "safety") else None
        if safety is not None:
            safety.comfort_paused = True
            log.info("[%s] responder brief - comfort loop paused for session %s", room, safety.id)
        try:
            summary = await self.session_summary(room)
            if not summary or summary.get("no_history"):
                log.info("[%s] responder brief - no fall on file", room)
                await self.speak_brief(room, NO_FALL_HISTORY, safety)
                return
            text = await self.brief_text(summary)
            await self.speak_brief(room, text, safety)
            await self.log_brief(room, summary, msg, text)
        finally:
            if safety is not None:
                # Resume with a fresh interval: the room has just been spoken
                # to, so an immediate comfort line would talk over the brief.
                safety.last_say_at = time.monotonic()
                safety.comfort_paused = False
                log.info("[%s] responder brief done - comfort loop resumed", room)

    async def speak_brief(self, room: str, text: str, safety: Session | None) -> None:
        """Speak into the asking room. `safety` prio only if a fall is live there.

        Published directly rather than through ``say``: the brief is not the
        session's line, and §12 gives it exactly one log line of its own.
        """
        await self.publish(f"qnet/{room}/say", {"text": text, "prio": "safety" if safety else ROUTINE_PRIO})

    async def session_summary(self, room: str) -> dict | None:
        """``get_session_summary`` - engine-invoked, the LLM only words it (§11)."""
        spec = self.tools.get("get_session_summary")
        fn = getattr(spec, "fn", None)
        if fn is None:
            try:
                from qnet.tools.get_session_summary import get_session_summary as fn  # type: ignore[no-redef]
            except Exception:  # noqa: BLE001 - no summary tool at all
                log.warning("[%s] responder brief - get_session_summary is not available", room)
                return None
        try:
            return await fn(self.brief_context(room), **_supported(fn, {"room": room}))
        except Exception:  # noqa: BLE001 - a tool never raises, but a brief never crashes either
            log.exception("[%s] get_session_summary failed", room)
            return None

    def brief_context(self, room: str):
        """A ``ToolContext`` for the interrupt - it logs nowhere, by design.

        §12 allows the brief exactly one line in the file it summarised, so the
        summary read must not append a `tool` line to a session that is still
        running. Everything else is the ordinary context.
        """
        try:
            from qnet.tools import ToolContext
        except Exception:  # noqa: BLE001 - keep the engine runnable without T2.3
            from types import SimpleNamespace as ToolContext  # type: ignore[assignment]
        live = self.live_session(room)
        return ToolContext(
            room=room,
            session_id=live.id if live else "",
            config=self.config,
            publish=self.publish,
            log=lambda event: None,
            subscribe=self.subscribe,
        )

    async def brief_text(self, summary: dict) -> str:
        """One LLM call over the timeline, with the engine's own summary underneath.

        The same rule as everywhere else: the model words facts it is handed and
        may invent none of them, and if it is unavailable, slow or unusable the
        engine speaks its own assembled timeline. A first responder standing in
        the room gets an answer either way - never silence, never a crash.
        """
        facts = self.brief_facts(summary)
        fallback = brief_line(facts)
        if self.llm is None:
            return fallback
        goal = getattr(self.brief_skill, "goal", "") or ""
        line = await asyncio.to_thread(self.llm.word_line, "brief", facts, goal)
        log.info("brief worded by %s", "gemma" if line else "the engine")
        return line or fallback

    def brief_facts(self, summary: dict) -> list[str]:
        """The timeline §12 asks for, as facts, out of the file's own log lines.

        Detection, what the person said, what was done and when, current status,
        total elapsed - and nothing that is not on disk.
        """
        room = summary.get("room") or "this room"
        events = summary.get("events") or []
        started = summary.get("started_at")
        now = time.time()
        resident = self.resident_name()

        def when(entry: dict) -> str:
            offset = float(entry.get("offset_s") or 0.0)
            # "after 0 seconds" is what a formatter says; "moments after the
            # fall" is what a person says, and both are equally true.
            return "moments after the fall" if offset < 2.5 else f"{elapsed_phrase(offset)} after the fall"

        facts: list[str] = []
        detected = next((e for e in events if e.get("event") == "detected"), None)
        ago = elapsed_phrase(now - float(started)) if started else None
        opening = f"a fall was detected in the {room}"
        if detected and detected.get("conf") is not None:
            opening += f", with {int(round(float(detected['conf']) * 100))} percent confidence"
        facts.append(opening + (f", {ago} ago" if ago else ""))
        if (self.config.get("resident") or {}).get("name"):
            facts.append(f"the resident here is {resident}")

        silences, quoted = 0, 0
        for entry in events:
            kind = entry.get("event")
            if kind == "heard":
                said = (entry.get("text") or "").strip()
                if entry.get("silence") or not said:
                    silences += 1
                elif quoted < 4:
                    quoted += 1
                    facts.append(f'{when(entry)} {resident} said "{said}"')
            elif kind == "tool":
                tool, result = entry.get("tool"), entry.get("result")
                if tool == "notify_contacts":
                    if entry.get("kind") == "false_alarm":
                        facts.append(f"{when(entry)} the contact {self.contact_name()} was told it was a false alarm")
                    else:
                        facts.append(f"{when(entry)} the contact {self.contact_name()} was messaged")
                elif tool == "call_emergency":
                    facts.append(f"{when(entry)} emergency services were called (simulated)")
                elif tool:
                    facts.append(f"{when(entry)} {tool} ran ({result})")
        if silences:
            facts.append(f"{resident} did not answer {silences} time{'s' if silences > 1 else ''}")

        state, phase = summary.get("state"), summary.get("phase")
        if state == "active":
            facts.append(f"right now the response is still open, at the {phase} stage")
        elif state == "ok":
            facts.append(f"it closed when {resident} said they were not hurt")
        elif state == "cancelled":
            facts.append("it was cancelled as a false alarm")
        elif state == "resolved":
            facts.append("it was closed as resolved")
        else:
            facts.append(f"it ended ({state})")

        elapsed = (now - float(started)) if (state == "active" and started) else summary.get("elapsed_s")
        if elapsed is not None:
            facts.append(f"total elapsed time is {elapsed_phrase(float(elapsed))}")
        return facts

    async def log_brief(self, room: str, summary: dict, msg: dict, text: str) -> None:
        """The one ``brief`` line, into the file it summarised (§12).

        If that file belongs to a session this agent still holds, the line goes
        through ``record`` so the dashboard sees it live too; otherwise (a
        session closed before a restart, or closed and replaced in the table) it
        is appended straight to the file, because the file is the record.
        """
        line = {
            "ts": round(time.time(), 1),
            "event": "brief",
            "ask_id": msg.get("id"),
            "spoken": True,
            "text": text,
        }
        path = self.sessions_dir / str(summary.get("file") or "")
        session = self.sessions.get(room)
        if session is not None and session.path.name == path.name:
            self.record(session, line)
            await self.publish(f"qnet/session/{session.id}", session.wire())
            return
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("[%s] could not append the brief line to %s", room, path)

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
        await session.inbox.put(("heard", text, silence))

    # --- trusted-contact replies (T-contact-ack) --------------------------

    async def on_contact_reply(self, name: str, text: str) -> None:
        """Route one Telegram reply from a configured contact - engine rails only.

        The target is the room whose safety session is escalating (most
        recently active if several). No such session -> log-drop: an
        unsolicited "ok" must do nothing, publish nothing, crash nothing.

        An accepted reply is (a) appended to the session log as a ``contact``
        line, (b) republished with the session document like every log line,
        and (c) published on ``qnet/<room>/contact`` (contracts/mqtt.md). What
        it *does* is decided inside ``run_phase`` - same seam as a transcript.
        """
        session = self.contact_target()
        if session is None:
            log.info("contact reply from %s dropped - no escalating safety session: %r", name, text)
            return
        verdict = contact_verdict(text)
        log.info("[%s] contact %s replied %r -> %s", session.room, name, text, verdict or "noted")
        await self.append(session, {"event": "contact", "from": name, "text": text})
        await self.publish(
            f"qnet/{session.room}/contact",
            {"from": name, "text": text, "ts": round(time.time(), 1)},
        )
        await session.inbox.put(("contact", name, verdict))

    def contact_target(self) -> Session | None:
        """The live safety session a contact reply belongs to, if any.

        Most recently active wins when several rooms are escalating at once -
        "active" measured by the last log line, which is the last thing that
        actually happened in the session.
        """
        live = [
            s for s in self.sessions.values()
            if s.live and s.urgency == "safety" and s.phase in CONTACT_PHASES
        ]
        if not live:
            return None
        return max(live, key=lambda s: (s.log[-1]["ts"] if s.log else s.detected_at))

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
            await self.say(session, self.spoken_opening(session, phase.opening), "safety")

        for action in phase.on_enter:
            key = (phase.id, action)
            if key in session.on_enter_done:
                continue
            session.on_enter_done.add(key)
            await self.run_tool(session, action, phase=phase, kind=phase.id)

        deadline = time.monotonic() + phase.timer.after_s * self.timer_scale if phase.timer else None
        comfort = self.comforts(phase)

        while True:
            # The responder brief pauses the loop while it speaks (§12). Dropped
            # from the wake calculation as well as from `comfort`, so a paused
            # loop waits on the phase timer instead of spinning on a due update.
            timeout = self._next_wake(session, deadline, comfort and not session.comfort_paused)
            try:
                item = await asyncio.wait_for(session.inbox.get(), timeout)
            except (TimeoutError, asyncio.TimeoutError):
                if deadline is not None and time.monotonic() >= deadline - 1e-3:
                    log.info("[%s] %s timer fired after %gs -> %s",
                             session.room, phase.id, phase.timer.after_s * self.timer_scale, phase.timer.goto)
                    return phase.timer.goto
                if comfort:
                    await self.comfort(session)
                continue

            if item[0] == "contact":
                # Already logged and published by on_contact_reply; here the
                # rails decide what the reply *does* in this phase.
                outcome = self.contact_action(phase, session, item[1], item[2])
                if outcome is not None:
                    return outcome
                continue

            _, text, silence = item
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

    def contact_action(self, phase: phaselib.Phase, session: Session, name: str, verdict: str | None) -> str | None:
        """What a routed contact reply does: a phase to jump to, or nothing.

        Engine rails end to end (T-contact-ack) - the LLM is never consulted:

        * ``emergency`` ("call 911") -> ``call_help`` immediately, from any
          contact phase that is not already placing the call.
        * ``ack`` ("ok" / "on my way" / ...) during ``escalate`` ->
          ``contact_engaged``: the contact takes the 30 s window, the session
          speaks their name, and the 180 s backstop timer starts. In
          ``contact_engaged`` a second ack changes nothing; in ``call_help``
          it is too late - the call already went out.
        * anything else was worth logging (on_contact_reply did) and does
          nothing.

        Both jumps are guarded on the phase actually existing in the loaded
        skill, so a skill without the ladder can never end a session with a
        phase name as its final state.
        """
        if verdict == "emergency":
            if phase.id != CALL_HELP_PHASE and CALL_HELP_PHASE in self.skill.phase_ids:
                log.info("[%s] contact %s asked for emergency services -> %s", session.room, name, CALL_HELP_PHASE)
                return CALL_HELP_PHASE
            return None
        if (
            verdict == "ack"
            and phase.id == ESCALATE_PHASE
            and CONTACT_ENGAGED_PHASE in self.skill.phase_ids
        ):
            session.engaged_contact = name
            log.info("[%s] contact %s acknowledged -> %s", session.room, name, CONTACT_ENGAGED_PHASE)
            return CONTACT_ENGAGED_PHASE
        return None

    def spoken_opening(self, session: Session, text: str) -> str:
        """A canned opening with its name placeholders filled in.

        Literal replacement, deliberately not ``str.format`` - a stray brace in
        a skill file must never crash a safety phase. ``{contact}`` is the
        contact who actually acknowledged (falling back to the first configured
        contact), ``{resident}`` is the resident - both grounded in config or
        in a real reply, never guessed.
        """
        return (
            text.replace("{contact}", session.engaged_contact or self.contact_name())
            .replace("{resident}", self.resident_name())
        )

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
        if session.comfort_paused:
            # A responder brief has the floor (§12). Not a missed update - the
            # loop resumes with a fresh interval the moment the brief is spoken.
            return
        quiet_for = time.monotonic() - session.last_say_at
        if quiet_for < self.comfort_interval_s * self.timer_scale:
            # Something else just spoke - drop this update rather than overlap
            # it. There is exactly one speaker per session by construction.
            return
        await self.say(session, await self.comfort_text(session), "comfort")

    async def comfort_text(self, session: Session) -> str:
        """Gemma words the update; the engine chooses the facts (T3.4).

        The model gets the *same* facts the ``--no-llm`` sentence is assembled
        from - what the tool log actually holds - so the wording differs
        between modes but the claims cannot. Anything unusable (too long,
        empty, timed out) falls back to the assembled sentence.
        """
        if self.llm is None:
            return self.comfort_line(session)
        facts = self.comfort_facts(session)
        started = time.monotonic()
        line = await asyncio.to_thread(self.llm.word_line, "comfort", facts)
        await self.append(
            session,
            {
                "event": "llm",
                "phase": session.phase,
                "kind": "comfort",
                "facts": facts,
                "source": "gemma" if line else "fallback",
                "ms": round((time.monotonic() - started) * 1000),
            },
        )
        return line or self.comfort_line(session)

    def comfort_facts(self, session: Session) -> list[str]:
        """What the session log actually holds - the only claims either mode may make."""
        facts = []
        if session.contacts_notified:
            facts.append(f"{self.contact_name()} has been messaged")
        if session.engaged_contact:
            # Set only by a real acknowledgement (T-contact-ack), so this
            # claim is as grounded as the tool facts around it.
            facts.append(f"{session.engaged_contact} is on the way")
        if session.emergency_called:
            facts.append("emergency services are on the way")
        facts.append(f"it's been about {elapsed_phrase(time.time() - session.detected_at)} since I saw you fall")
        return facts

    def comfort_line(self, session: Session) -> str:
        """Assemble the update from facts the session log actually holds."""
        facts = self.comfort_facts(session)
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

    def resident_name(self) -> str:
        """Whose house this is - the person who fell, never the contact.

        Both names appear in a responder brief, and a 2B model *will* blur them
        if the facts leave the speaker implicit: the first live run produced
        "Sarah said my hip hurts" from a fact that read 'they said "my hip
        hurts"'. Naming the resident in the fact itself fixes it at the source,
        which is the right place - the model may only rearrange what it is given.
        """
        return ((self.config.get("resident") or {}).get("name") or "the person").strip()

    # --- the agent's turn -------------------------------------------------

    async def decide(self, phase: phaselib.Phase, session: Session, text: str) -> Action:
        """One action per turn: Gemma first, the regex classifier underneath (T3.4).

        The seam is one call and one fallback. Gemma returns a *decision word*
        from the phase's closed option set (``llm.options_for``) - never an
        action - so the consequential half stays here: the pain double-check is
        still engine-owned, the rails still refuse anything out of phase, and a
        ``None`` (timeout, unparseable answer, brain down) simply means the
        regex mapping runs exactly as it does under ``--no-llm``.

        Every decision is logged - ``{"event": "llm", ...}`` - because a system
        that can escalate on a model's say-so has to be auditable afterwards.
        """
        if self.llm is not None and (text or "").strip() and llmlib.options_for(phase):
            started = time.monotonic()
            decision = await asyncio.to_thread(
                self.llm.classify_reply, phase, self.llm_context(phase, session), text
            )
            action = self.llm_action(phase, session, decision)
            await self.append(
                session,
                {
                    "event": "llm",
                    "phase": phase.id,
                    "heard": text,
                    "decision": decision,
                    "source": "gemma" if action is not None else "fallback",
                    "ms": round((time.monotonic() - started) * 1000),
                },
            )
            if action is not None:
                log.info("[%s] llm %s -> %s", session.room, phase.id, decision)
                return action
            log.info("[%s] llm gave no usable decision - canned classifier", session.room)
        return classify_reply(phase, session, text)

    def llm_context(self, phase: phaselib.Phase, session: Session) -> dict:
        """The few session facts the prompt may mention - nothing speculative.

        ``asked`` is the question actually on the table, which is the context
        the transcript is meaningless without: mid-double-check the person is
        answering *"any pain?"*, not *"are you okay?"*, and the same word means
        opposite things in the two. Hence ``note``, the one sentence the model
        cannot read off the skill file - ``fall.md``'s escalate condition says
        "they say no", but a "no" to the pain question is the *reassuring*
        answer. Measured worth: 24/25 with it, 20/25 without (T3.3 verify).

        It lives here rather than in ``llm.py`` because the double-check is the
        engine's ritual: ``llm_action`` owns it, so its wording belongs beside
        it, and ``llm.py`` stays a template that renders whatever it is given.
        """
        return {
            "room": session.room,
            "asked": PAIN_QUESTION if session.awaiting_pain_answer else phase.opening,
            "awaiting_pain_answer": session.awaiting_pain_answer,
            "contacts_notified": session.contacts_notified,
            "note": (
                'Note: "no" or "nothing" here means they have no pain and did not hit their head.'
                if session.awaiting_pain_answer
                else ""
            ),
        }

    def llm_action(self, phase: phaselib.Phase, session: Session, decision: str | None) -> Action | None:
        """A decision word -> the same ``Action`` the regex would have produced.

        Identical semantics to ``classify_reply``, including the one that
        matters most: **"ok" never closes a session on its own.** The first
        "I'm fine" asks the canned pain question (§3, §6) and only an "ok"
        *after* that takes the exit - a headline behaviour the model is not
        allowed to skip, however confident it sounds.
        """
        if decision is None or decision not in llmlib.options_for(phase):
            return None
        if "ok" in phase.exits and "escalate" in phase.exits:
            if decision == "escalate":
                session.awaiting_pain_answer = False
                return Action("exit", exit="escalate")
            if session.awaiting_pain_answer:
                session.awaiting_pain_answer = False
                return Action("exit", exit="ok")
            session.awaiting_pain_answer = True
            return Action("say", text=PAIN_QUESTION)
        if decision == "wait":
            return Action("wait")
        return Action("exit", exit=decision)

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
            subscribe=self.subscribe,
        )


def _topic_pattern(topic_filter: str) -> re.Pattern[str]:
    """An MQTT topic filter as a regex: ``+`` is one level, ``#`` is the rest."""
    parts = []
    for level in topic_filter.split("/"):
        if level == "+":
            parts.append("[^/]+")
        elif level == "#":
            parts.append(".*")
        else:
            parts.append(re.escape(level))
    return re.compile("^" + "/".join(parts) + "$")


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
