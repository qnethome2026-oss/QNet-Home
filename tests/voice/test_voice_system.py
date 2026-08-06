# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Phase C - the hardware-free conversation harness (voice-integration plan, C1).

REAL ``qnet.agent.engine.Agent`` (the root conftest's ``make_agent`` rig: fake
bus, recorder tools, scaled timers) + REAL ``VoiceController`` + REAL
``MQTTTransport`` message building/validation, glued by an in-process bridge
standing in for the broker. Only three things are fake, and all three already
exist in this suite:

* the **socket layer** - ``MQTTTransport`` keeps every ``publish_*`` builder
  and its ``_on_message`` validation, but its paho client is replaced by
  ``FakePahoClient``, which routes node publishes straight into
  ``Agent.on_message`` instead of a broker (so the frozen wire shapes are
  built and parsed by production code on both ends);
* the **speech bricks** - ``tests.voice.fakes``' FakeASR/FakeTTS, scripted per
  scenario exactly as the controller unit tests script them;
* the **broker** - ``Agent`` publishes into the conftest ``FakeBus`` as
  always; a thin ``BridgeClient`` wrapper additionally delivers ``say`` and
  ``session`` messages into ``MQTTTransport._on_message``, mimicking the two
  subscriptions ``_on_connect`` makes (``qnet/<room>/say``, ``qnet/session/+``).

The controller runs exactly as on the device: ``main.py`` is
``App.run(user_loop=controller.run_once)``, so the harness pump thread is a
``while not stopped: controller.run_once()`` loop. No audio, no network, no
model; every test is hermetic and joins its threads.

What the six scenarios prove is written on each test.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import types

from config import VoiceNodeConfig
from mqtt_transport import MQTTTransport
from speech_backend import ArduinoSpeechBackend
from voice_controller import VoiceController

from qnet.agent import engine
from tests.conftest import StubSpec, fall, finish, make_agent, until
from tests.voice.fakes import BlockUntilCancelled, FakeASR, FakeTTS

ROOM = "kitchen"

# The canned openings, verbatim from skills/fall.md (same constants the
# engine regression suite in tests/test_scenarios.py asserts against).
CHECK_OPENING = "I saw you fall. Take a breath — are you okay?"
ESCALATE_OPENING = "It's okay — I'm getting you help. Try to get comfortable, and don't strain to move."
CALL_HELP_OPENING = ("I haven't heard from you, so I'm calling emergency services for you right now. Help is coming — stay with me.")

# What the agent actually subscribes to (engine.SUBSCRIPTIONS) and what the
# node subscribes to (MQTTTransport._on_connect) - the bridge honours both, so
# a message only crosses if a real broker would have delivered it.
AGENT_TOPIC_RE = re.compile(r"^qnet/[^/]+/(event|ask|heard|looked)$")
SESSION_TOPIC_RE = re.compile(r"^qnet/session/[^/]+$")


def node_config(**overrides) -> VoiceNodeConfig:
    """The kitchen node's config, tightened for test speed (1 s session listens)."""
    settings = dict(
        device_id="ventuno-kitchen",
        room_id=ROOM,
        groups=(),
        mqtt_host="test-bridge",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        microphone_device="usb:1",
        speaker_device="usb:1",
        language="en",
        idle_listen_timeout_seconds=2,
        session_listen_timeout_seconds=1,
        post_tts_guard_ms=0,
        tts_queue_size=20,
        responder_phrase="I am the first responder",
    )
    settings.update(overrides)
    return VoiceNodeConfig(**settings)


class _PahoMessage:
    """The two attributes ``MQTTTransport._on_message`` reads off a paho message."""

    def __init__(self, topic: str, payload: str):
        self.topic = topic
        self.payload = payload.encode("utf-8")


class FakePahoClient:
    """The socket layer under the REAL transport - records and routes, no network.

    ``MQTTTransport._publish_json`` only ever calls ``client.publish`` and
    checks ``result.rc``, so this is the entire surface to replace: every
    payload it receives was built by the production ``publish_query`` /
    ``publish_heard`` / ``publish_responder_brief`` / ``publish_voice_status``.
    """

    def __init__(self, route):
        self.route = route  # (topic, payload_str) -> None, called on publish
        self.published: list[tuple[str, dict]] = []

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        self.published.append((topic, json.loads(payload)))
        self.route(topic, payload)
        return types.SimpleNamespace(rc=0)  # mqtt.MQTT_ERR_SUCCESS


class BridgeClient:
    """The agent's client: the conftest FakeBus plus delivery to the node.

    Everything still lands on the FakeBus (so ``bus.said()``/``bus.sessions()``
    keep working); on top of that, anything the node's two subscriptions would
    have received is handed to the REAL ``MQTTTransport._on_message``, bytes
    and all, so the node-side validation path is exercised too.
    """

    def __init__(self, bus, deliver):
        self.bus = bus
        self.deliver = deliver

    async def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        await self.bus.publish(topic, payload, qos)
        self.deliver(topic, payload)


class VoiceSystem:
    """One house: a real agent and a real kitchen voice node, bridged in-process."""

    def __init__(self, tmp_path, *, timer_scale: float = 0.05,
                 comfort_interval_s: float = 1000.0, **agent_overrides):
        self.loop = asyncio.get_running_loop()
        self.errors: list[BaseException] = []
        self._futures: list = []

        self.agent, self.bus, self.recorder = make_agent(
            tmp_path, timer_scale=timer_scale,
            comfort_interval_s=comfort_interval_s, **agent_overrides,
        )
        self.agent.client = BridgeClient(self.bus, self._to_node)

        self.config = node_config()
        self.transport = MQTTTransport(self.config)
        self.transport.client = FakePahoClient(self._to_hub)
        self.transport.connected = True  # what _on_connect would have set

        self.asr = FakeASR()
        self.tts = FakeTTS()
        self.speech = ArduinoSpeechBackend(self.asr, self.tts)
        self.controller = VoiceController(
            speech=self.speech, transport=self.transport, config=self.config,
            sleep_fn=time.sleep,
        )
        # Exactly main.py's wiring.
        self.transport.set_say_handler(self.controller.on_tts_command)
        self.transport.set_session_handler(self.controller.on_session_event)
        self.transport.set_state_provider(self.controller.voice_state)

        self._stop = threading.Event()
        self._pump = threading.Thread(target=self._run, name="voice-pump", daemon=True)

    # --- the bridge -------------------------------------------------------

    def _to_hub(self, topic: str, payload: str) -> None:
        """Node publish (pump thread) -> the agent, if the agent subscribes to it."""
        if AGENT_TOPIC_RE.match(topic):
            self._futures.append(
                asyncio.run_coroutine_threadsafe(
                    self.agent.on_message(topic, payload.encode("utf-8")), self.loop
                )
            )

    def _to_node(self, topic: str, payload: str) -> None:
        """Agent publish (loop thread) -> the node's two subscriptions."""
        if topic == self.transport.say_topic or SESSION_TOPIC_RE.match(topic):
            self.transport._on_message(None, None, _PahoMessage(topic, payload))

    # --- the device loop --------------------------------------------------

    def start(self) -> None:
        self._pump.start()

    def _run(self) -> None:
        # main.py: App.run(user_loop=controller.run_once)
        while not self._stop.is_set():
            try:
                self.controller.run_once()
            except BaseException as exc:  # noqa: BLE001 - surfaced in shutdown
                self.errors.append(exc)
                return

    async def shutdown(self) -> None:
        """Stop the pump, drain the bridge, stop the agent - no threads left."""
        self._stop.set()
        # Unblock whatever listen the pump is inside: a continuous stream on
        # BlockUntilCancelled (cancel) or a bounded queue.get (sentinel).
        self.speech.cancel_listen()
        self.asr.queue_result("")
        if self._pump.ident is not None:
            await asyncio.to_thread(self._pump.join, 3.0)
            if self._pump.is_alive():
                self.errors.append(RuntimeError("pump thread did not stop"))
        for future in list(self._futures):
            try:
                await asyncio.wrap_future(future)
            except BaseException as exc:  # noqa: BLE001
                self.errors.append(exc)
        await self.agent.shutdown()

    # --- what the tests ask -----------------------------------------------

    def node_published(self, kind: str) -> list[dict]:
        """Every payload the node put on ``qnet/kitchen/<kind>``, in order."""
        return [p for t, p in self.transport.client.published if t == f"qnet/{ROOM}/{kind}"]

    @property
    def asks(self) -> list[dict]:
        return self.node_published("ask")

    @property
    def heard(self) -> list[dict]:
        return self.node_published("heard")

    @property
    def spoken(self) -> list[str]:
        return list(self.tts.spoken)

    def replies(self) -> list[str]:
        """Every non-silence transcript that actually left the node."""
        return [h["text"] for h in self.heard if not h["silence"]]


# --- scenario 1: fall -> "i'm fine" -> pain check -> resolved --------------


def test_fall_im_fine_pain_check_resolved(tmp_path) -> None:
    """The headline conversation, end to end through the real node.

    Proves: the engine's opening is built as a wire `say`, validated and
    spoken by the node; the node's bounded session listen publishes the reply
    as a frozen-shape `heard`; "I'm fine" does NOT close the session but gets
    the engine's pain double-check spoken in the room; a clean denial closes
    `ok` - and nothing else was ever spoken.
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path, timer_scale=0.2)  # check timer: 6 s of headroom
        try:
            sysm.start()
            session = await fall(sysm.agent)

            await until(lambda: CHECK_OPENING in sysm.spoken, why="opening spoken by the node")
            sysm.asr.queue_result("i'm fine")

            await until(lambda: engine.PAIN_QUESTION in sysm.spoken, why="pain double-check spoken")
            # The natural denial - contains "hurt", which the regex mind used to
            # misread as pain until _NEGATED_PAIN_RE (found by this harness).
            sysm.asr.queue_result("no i'm not hurt")

            await finish(session)
            assert session.state == "closed" and session.final == "ok"
            # The spoken sequence, exactly - no comfort line, no stray say.
            assert sysm.spoken == [CHECK_OPENING, engine.PAIN_QUESTION]
            # Both replies crossed the wire in the frozen {text, silence} shape.
            assert sysm.replies() == ["i'm fine", "no i'm not hurt"]
            assert all(set(h) == {"text", "silence"} for h in sysm.heard)
            # And nobody was alarmed on the way.
            assert sysm.recorder.names() == []
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


# --- scenario 2: silence -> escalate -> SIMULATED call ---------------------


def test_silence_walks_the_ladder_to_simulated_call(tmp_path) -> None:
    """Nobody answers: the node's listens time out, the engine's timers act.

    Proves: the node's bounded listens publish explicit `{"", silence: true}`
    heards (not nothing); the engine's check timer escalates on schedule with
    the caregiver notified; the escalate timer reaches call_help with the
    SIMULATED emergency call recorded; and both safety openings were actually
    spoken in the room by the node.
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path, timer_scale=0.05)  # 1.5 s / 1.5 s ladder
        try:
            sysm.start()
            session = await fall(sysm.agent)

            await until(lambda: ESCALATE_OPENING in sysm.spoken, timeout=8,
                        why="escalate opening spoken")
            await until(lambda: CALL_HELP_OPENING in sysm.spoken, timeout=8,
                        why="call_help opening spoken")
            await until(lambda: sysm.recorder.count("call_emergency") == 1, timeout=5,
                        why="SIMULATED call recorded")
            await until(lambda: sysm.recorder.count("notify_contacts") == 2, timeout=5,
                        why="call_help's own caregiver ping")

            assert session.phase == "call_help" and session.live
            assert [k["kind"] for k in sysm.recorder.kwargs("notify_contacts")] == [
                "escalate", "call_help",
            ]
            # Silence crossed the wire as a fact, in the frozen heard shape.
            assert {"text": "", "silence": True} in sysm.heard
            # The session log carries the SIMULATED word (§14's demo guarantee).
            assert any(
                line.get("tool") == "call_emergency" and line.get("result") == "SIMULATED"
                for line in session.log
            )
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


# --- scenario 3: wake-gated find, spoken answer ----------------------------


def test_wake_gated_find_speaks_the_location(tmp_path) -> None:
    """"hey home where are my glasses i can't find them anywhere", system-wide.

    Proves: the wake gate publishes exactly ONE ask carrying only the
    post-phrase remainder (the background "News is on." never leaves the
    node); the engine cuts the trailing clause and broadcasts a look for
    "glasses" (the REAL look_in_rooms tool, subscribe-then-publish); an
    injected `looked` reply comes back through the agent's own fanout; and
    the answer naming the room and the landmark is spoken by the node.
    """

    async def scenario() -> None:
        from qnet.tools.look_in_rooms import look_in_rooms as real_look

        sysm = VoiceSystem(
            tmp_path,
            rooms={ROOM: {}},                 # who look_in_rooms waits for
            find={"look_timeout_s": 3.0},
        )
        # The one registry substitution: the REAL broadcast-and-listen tool in
        # place of the conftest recorder stub (the documented seam for tests
        # that care about the answer).
        sysm.agent._tools["look_in_rooms"] = StubSpec(real_look, engine_only=False)
        try:
            sysm.start()
            sysm.asr.queue_result(
                "News is on. hey home where are my glasses i can't find them anywhere"
            )

            await until(lambda: sysm.bus.on("qnet/look"), why="look broadcast")
            look = sysm.bus.on("qnet/look")[-1]
            assert look["object"] == "glasses"      # trailing clause cut by the engine
            assert look["mode"] == "find"

            # Exactly one ask left the node: the gate consumed the window, and
            # only the post-wake remainder is on the wire.
            assert [a["kind"] for a in sysm.asks] == ["query"]
            assert sysm.asks[0]["text"] == "where are my glasses i can't find them anywhere"
            assert "News" not in sysm.asks[0]["text"]

            # The kitchen node answers - through the agent's own looked fanout.
            await sysm.agent.on_message(
                f"qnet/{ROOM}/looked",
                json.dumps({
                    "qid": look["qid"], "room": ROOM, "found": True,
                    "answer": "on the counter next to the kettle",
                }).encode(),
            )

            await until(
                lambda: any("counter next to the kettle" in text for text in sysm.spoken),
                why="answer spoken",
            )
            assert (
                "I found your glasses in the kitchen, on the counter next to the kettle."
                in sysm.spoken
            )
            assert len(sysm.asks) == 1  # still exactly one - nothing re-triggered
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


def test_plain_chatter_never_reaches_the_agent(tmp_path) -> None:
    """Room chatter with no wake phrase: zero asks, zero anything, system-wide.

    Proves: at the system level the wake gate is the node's activation
    decision - an entire idle listen full of background speech routes nothing
    into the bridge, so the agent's bus stays empty (T6.4's soak, scripted).
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path)
        try:
            for chatter in (
                "the kettle is boiling",
                "what a lovely morning",
                "did you see the news today? i can't believe it",
            ):
                sysm.asr.queue_result(chatter)
            # One production loop turn, driven directly (no pump): the idle
            # stream drains every final through the gate.
            await asyncio.to_thread(sysm.controller.run_once)

            assert sysm.asks == []
            assert sysm.heard == []
            assert sysm.bus.messages == []  # the agent never heard a thing
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


# --- scenario 4: responder brief mid-escalation ----------------------------


def test_responder_brief_mid_escalation_then_comfort_resumes(tmp_path) -> None:
    """"I'm the first responder, what happened" while the ladder is climbing.

    Proves: the responder phrase outranks everything in the node's session
    listen and publishes a responder_brief ask (no wake phrase needed); the
    engine's interrupt reads the live session file and the brief - grounded
    in what actually happened - is spoken in the room; and the comfort loop,
    paused for the brief, speaks again afterwards.
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path, timer_scale=0.1, comfort_interval_s=6.0)
        try:
            sysm.start()
            session = await fall(sysm.agent)

            await until(lambda: CHECK_OPENING in sysm.spoken, why="opening spoken")
            sysm.asr.queue_result("help")  # a call for help - straight to escalate
            await until(lambda: ESCALATE_OPENING in sysm.spoken, timeout=6,
                        why="escalation spoken")
            assert session.contacts_notified

            sysm.asr.queue_result("I'm the first responder, what happened")
            await until(
                lambda: any(text.startswith("Here's what happened") for text in sysm.spoken),
                timeout=6, why="brief spoken",
            )

            # The ask was kind=responder_brief, built by the real transport.
            assert [a["kind"] for a in sysm.asks] == ["responder_brief"]
            brief_at = next(
                i for i, text in enumerate(sysm.spoken) if text.startswith("Here's what happened")
            )
            brief = sysm.spoken[brief_at]
            # Grounded in the session's own file: the detection and the reply.
            assert "fall was detected in the kitchen" in brief
            assert '"help"' in brief

            # The comfort loop resumes and speaks - after the brief.
            await until(
                lambda: any(
                    text.startswith("I'm still here with you") for text in sysm.spoken[brief_at + 1:]
                ),
                timeout=8, why="comfort loop resumed after the brief",
            )
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


# --- scenario 5: "false alarm" cancels, then silence -----------------------


def test_false_alarm_cancels_and_nothing_more_is_spoken(tmp_path) -> None:
    """Mid-ladder cancel: the engine interrupt fires and the room goes quiet.

    Proves: "false alarm" heard through the real node cancels the session on
    the engine rails (before any classifier); the caregiver gets the
    false-alarm follow-up (recorded tool, kind=false_alarm); the cancelled
    session snapshot reaches the node and clears its active session; and
    afterwards the node speaks nothing further.
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path, timer_scale=0.2)  # wide windows; comfort parked
        try:
            sysm.start()
            session = await fall(sysm.agent)

            await until(lambda: CHECK_OPENING in sysm.spoken, why="opening spoken")
            sysm.asr.queue_result("help")
            await until(lambda: ESCALATE_OPENING in sysm.spoken, timeout=8,
                        why="mid-ladder: escalation spoken")

            sysm.asr.queue_result("false alarm")
            await finish(session)

            assert session.state == "cancelled" and session.final == "cancelled"
            assert [k["kind"] for k in sysm.recorder.kwargs("notify_contacts")] == [
                "escalate", "false_alarm",
            ]
            assert sysm.recorder.count("call_emergency") == 0

            # The cancelled snapshot reached the node: back to idle listening.
            await until(
                lambda: sysm.controller.status_snapshot()["active_session_id"] is None,
                why="node saw the session end",
            )
            # And nothing further is ever spoken - wait out two comfort
            # intervals' worth of scaled time to prove the quiet is real.
            goodbye = sysm.spoken
            await asyncio.sleep(1.0)
            # "help" now earns the guided reply right after the escalate
            # opening (first-aid match on an exit-causing utterance).
            assert sysm.spoken == goodbye
            assert goodbye[:2] == [CHECK_OPENING, ESCALATE_OPENING]
            assert len(goodbye) == 3 and "Help is on the way" in goodbye[2]
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())


# --- scenario 6: half-duplex - a say lands mid-listen ----------------------


def test_say_during_active_idle_listen_cancels_speaks_resumes(tmp_path) -> None:
    """Half-duplex under fire, with the say originating from the real agent.

    Proves: an agent say arriving while the node's idle ASR stream is open
    cancels that listen (generation marked, ASR cancel actually called), the
    line is spoken, and a fresh idle listen opens afterwards - the node never
    talks over its own ears and never stops listening after speaking.
    """

    async def scenario() -> None:
        sysm = VoiceSystem(tmp_path)
        cancels: list[float] = []
        real_cancel = sysm.asr.cancel
        sysm.asr.cancel = lambda: (cancels.append(time.monotonic()), real_cancel())[-1]

        try:
            # One final that wakes the house with an object-less request (the
            # agent answers WHAT_TO_FIND - a real engine say, no session), then
            # a listen that stays open until cancelled: the say must arrive
            # while the stream is provably active.
            sysm.asr.queue_result("hey home find it")
            sysm.asr.queue_result(BlockUntilCancelled())
            sysm.start()

            await until(lambda: engine.WHAT_TO_FIND in sysm.spoken,
                        why="the agent's say spoken through the interrupt")
            assert cancels, "the say must cancel the active idle listen"
            assert [a["text"] for a in sysm.asks] == ["find it"]

            # Generation sequencing: exactly one ASR stream existed before the
            # say (the pump takes the queued say before ever reopening one),
            # so any second stream is a listen opened AFTER speaking. It may
            # consume the scripted BlockUntilCancelled and stay open - which
            # is a live listen, i.e. exactly the resumption being proven.
            await until(lambda: sysm.asr.continuous_session_count >= 2,
                        why="idle listening resumed after the say")

            # The wire status stream agrees: speaking came after a listening
            # status, and listening was published again after speaking.
            states = [s["state"] for s in sysm.node_published("status")]
            spoke = states.index("speaking")
            assert "listening" in states[:spoke]
            assert "listening" in states[spoke + 1:]
        finally:
            await sysm.shutdown()
        assert sysm.errors == []

    asyncio.run(scenario())
