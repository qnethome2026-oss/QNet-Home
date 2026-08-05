# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T3.3 - the replay harness, against the real Gemma on the real board.

Everything else in ``tests/`` is hermetic; this file is the one that needs
hardware, so every test is marked ``live`` and ``pytest tests/`` skips the lot
(``addopts = -m "not live"`` in pyproject). To run it:

    ssh -o BatchMode=yes -N -L 18181:127.0.0.1:18181 iq9    &   # the endpoint is
    .venv/Scripts/python -m pytest tests/test_llm_replay.py -m live -q -s

(the GenieX server listens on the device's localhost only, so the tunnel is what
makes ``127.0.0.1:18181`` mean anything from a laptop; ``-s`` shows the
scoreboard).

What it pins down, in the order the risks matter:

1. **Ten scripted replies -> the classification the engine acts on**, scored,
   with a >= 9/10 bar. Not a "does it respond" smoke test: these are the
   sentences a person on a kitchen floor actually says, including the two that
   have to resolve toward help (gibberish, and a reply that ignores the
   question entirely).
2. **Every outbound body carries GenieX's two fields** - and none of the four
   that crash v0.3.18. This is a wire-level assertion on the real request, not
   a code review: the setup log's Finding 3 was a real crashed server.
3. **A model that will not answer with one of its options costs exactly one
   retry**, then returns ``None`` - never an exception, never a guess.
4. **Silence never reaches the model at all** - the engine handles it before
   the seam, which is what keeps the phase timer in charge of an unanswered
   question.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import fall, heard, make_agent, until

from qnet.agent import engine
from qnet.agent import llm as llmlib
from qnet.agent import phases as phaselib

pytestmark = pytest.mark.live

PASS_BAR = 9        # of 10 variants
LATENCY_BAR_S = 6.0  # per call, wall clock, through the tunnel


def context(phase, awaiting_pain: bool) -> dict:
    """The exact context dict the engine hands over at that point in a session.

    Built by calling the engine's own ``llm_context`` (a pure function of its
    phase and session) rather than by hand, so the harness can never drift into
    scoring a prompt that production does not send.
    """
    session = SimpleNamespace(room="kitchen", awaiting_pain_answer=awaiting_pain, contacts_notified=False)
    return engine.Agent.llm_context(None, phase, session)


# The ten. Nine are spoken replies in `check` (the flag is "are they answering
# the pain double-check?"); the tenth is silence, which the engine is supposed
# to swallow before the client is ever consulted.
VARIANTS: list[tuple[str, str, bool]] = [
    ("i'm fine", "ok", False),
    ("i am okay thanks", "ok", False),
    ("my hip hurts", "escalate", False),
    ("no", "escalate", False),                 # "no" to "are you okay?"...
    ("help me please", "escalate", False),
    ("i can't get up", "escalate", False),
    ("yes i hit my head", "escalate", True),   # ...and this one answers the pain question
    ("asdf gwqk", "escalate", False),          # total gibberish -> toward help
    ("what time is it", "escalate", False),    # off-topic: they never answered
]

FORBIDDEN = ("response_format", "enable_json", "grammar", "grammar_string")


class RequestSpy:
    """Wraps the ``openai`` client so the harness sees every outbound body.

    Shaped like the one call ``LlmClient.ask`` makes
    (``client.chat.completions.create(**body)``), so it is a drop-in and the
    code under test is the shipped code, not a variant of it.
    """

    def __init__(self, inner) -> None:
        self.inner = inner
        self.bodies: list[dict] = []
        self.latencies: list[float] = []
        self.stub = None  # set to a canned response and nothing goes on the wire
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **body):
        self.bodies.append(body)
        started = time.monotonic()
        response = self.stub if self.stub is not None else self.inner.chat.completions.create(**body)
        self.latencies.append(time.monotonic() - started)
        return response

    @property
    def calls(self) -> int:
        return len(self.bodies)

    def reset(self) -> None:
        self.bodies.clear()
        self.latencies.clear()


def canned(content: str):
    """A response object shaped like the SDK's, for the invalid-reply path."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture(scope="module")
def live():
    """A warmed client pointed at the tunnel, plus the spy that watched it.

    Warm-up is deliberate and excluded from the latency bar: the first request
    after a service restart includes the ~12 s model load (setup log, step 8),
    which is a property of the server's cold start, not of a turn.
    """
    from openai import OpenAI

    inner = OpenAI(
        base_url=llmlib.BASE_URL,
        api_key=llmlib.API_KEY,
        timeout=llmlib.TIMEOUT_S,
        max_retries=0,
    )
    try:
        models = [m.id for m in inner.models.list().data]
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no GenieX endpoint at {llmlib.BASE_URL} ({exc.__class__.__name__}) - is the tunnel up?")
    assert any(m.startswith(llmlib.MODEL) for m in models), f"{llmlib.MODEL} not served; got {models}"

    spy = RequestSpy(inner)
    client = llmlib.LlmClient(client=spy)
    assert client.ask("Say OK and nothing else.", 0.0, 8) is not None, "warm-up request failed"
    spy.reset()
    client.calls = 0
    return client, spy


@pytest.fixture(scope="module")
def check_phase():
    """``fall.md``'s first phase - the real one, not a fixture of it."""
    skill = phaselib.load_skill(Path(__file__).resolve().parents[1] / "skills" / "fall.md", tools=None)
    return skill.phase("check")


# --- 1. the scoreboard ----------------------------------------------------


def test_ten_variants_classify(live, check_phase, tmp_path) -> None:
    """Ten replies, ten expected decisions, >= 9 right. Printed, not just asserted."""
    client, spy = live
    spy.reset()
    rows: list[tuple[str, str, str, float, bool]] = []

    for text, expected, awaiting_pain in VARIANTS:
        started = time.monotonic()
        got = client.classify_reply(check_phase, context(check_phase, awaiting_pain), text)
        rows.append((text, expected, str(got), time.monotonic() - started, got == expected))

    # #10: silence. The engine answers it on its own - the client must not even
    # be asked, or an unanswered question would cost a model call every listen
    # window and the phase timer would be racing the device.
    calls_before = spy.calls
    silence_ok = asyncio.run(_silence_never_reaches_the_model(tmp_path, client, spy))
    rows.append(("(silence)", "engine handles it", "no request" if silence_ok else "REQUEST SENT",
                 0.0, silence_ok))
    assert spy.calls == calls_before, "silence must not produce a single outbound request"

    score = sum(1 for row in rows if row[-1])
    width = max(len(r[0]) for r in rows)
    print(f"\n  T3.3 replay scoreboard - live Gemma 4 E2B on the IQ-9075 ({llmlib.BASE_URL})")
    for text, expected, got, seconds, ok in rows:
        print(f"  [{'x' if ok else ' '}] {text:<{width}}  expected {expected:<17} got {got:<17} {seconds:5.2f}s")
    spoken = [row for row in rows if row[0] != "(silence)"]
    print(f"  score {score}/{len(rows)}   per-call max {max(r[3] for r in spoken):.2f}s "
          f"mean {sum(r[3] for r in spoken) / len(spoken):.2f}s   requests {spy.calls}")

    assert score >= PASS_BAR, f"scored {score}/{len(rows)}, bar is {PASS_BAR}"


async def _silence_never_reaches_the_model(tmp_path, client, spy) -> bool:
    """Drive a real session with the real client and stay quiet."""
    agent, bus, _rec = make_agent(tmp_path, llm=client, timer_scale=0.05, comfort_interval_s=1000)
    session = await fall(agent)
    before = spy.calls
    await heard(agent, silence=True)      # a listen window that timed out
    await heard(agent, text="")           # ...and a transcript with nothing in it
    await asyncio.sleep(0.1)
    quiet = spy.calls == before
    if session.task and not session.task.done():
        session.task.cancel()
        try:
            await session.task
        except asyncio.CancelledError:
            pass
    await agent.shutdown()
    return quiet


# --- 2. what went out on the wire ----------------------------------------


def test_every_request_carries_the_geniex_fields(live, check_phase) -> None:
    """`enable_think: false` + `max_completion_tokens` on every call - and no crashers.

    Both are GenieX's own names; OpenAI's ``think``/``max_tokens`` are silently
    ignored by the server, which is exactly the kind of bug that only shows up
    as "the model is slow and rambles" in a demo (setup log, Finding 1).
    """
    client, spy = live
    spy.reset()
    client.classify_reply(check_phase, {}, "my hip hurts")
    client.word_line("comfort", ["Sarah has been messaged", "it's been about 30 seconds since I saw you fall"])
    assert spy.calls >= 2

    for body in spy.bodies:
        extra = body.get("extra_body") or {}
        assert extra.get("enable_think") is False, body
        assert isinstance(extra.get("max_completion_tokens"), int), body
        assert extra["max_completion_tokens"] > 0
        assert body["model"] == llmlib.MODEL
        # Finding 3: these four crash v0.3.18. Never sent, at any nesting.
        assert not any(key in body or key in extra for key in FORBIDDEN), body
        # Finding 2: SDK-native tool-calling returns null tool_calls - unused.
        assert "tools" not in body and "tool_choice" not in body


def test_calls_are_inside_the_latency_budget(live, check_phase) -> None:
    """Every call under 6 s wall clock, through the tunnel, warm model."""
    client, spy = live
    spy.reset()
    for text, _expected, awaiting_pain in VARIANTS[:4]:
        client.classify_reply(check_phase, context(check_phase, awaiting_pain), text)
    client.word_line("comfort", ["Sarah has been messaged", "emergency services are on the way"])
    worst = max(spy.latencies)
    print(f"\n  per-call latency: max {worst:.2f}s, mean {sum(spy.latencies)/len(spy.latencies):.2f}s "
          f"over {len(spy.latencies)} calls (bar {LATENCY_BAR_S}s)")
    assert worst < LATENCY_BAR_S, f"slowest call {worst:.2f}s >= {LATENCY_BAR_S}s"


# --- 3. the failure path --------------------------------------------------


def test_invalid_reply_retries_once_then_gives_up(live, check_phase) -> None:
    """A model that answers off-menu costs one retry and then ``None``.

    Stubbed at the transport, so the shipped parse/retry path runs for real -
    and nothing is executed on the strength of an answer that was not one of
    the phase's exits. The engine's regex takes the turn from there.
    """
    client, spy = live
    spy.reset()
    spy.stub = canned("Well, it rather depends on how they said it.")
    try:
        assert client.classify_reply(check_phase, {}, "i think i'm alright") is None
        assert spy.calls == 2, f"expected 1 attempt + exactly 1 retry, saw {spy.calls}"
        assert "one word" in spy.bodies[1]["messages"][0]["content"].lower(), "the retry must be the terser prompt"
        assert len(spy.bodies[1]["messages"][0]["content"]) < len(spy.bodies[0]["messages"][0]["content"])
    finally:
        spy.stub = None


def test_thinking_channel_is_stripped_and_a_dead_endpoint_is_survivable(check_phase) -> None:
    """Belt-and-braces, both directions - neither needs the device.

    The strip is a no-op while ``enable_think`` works; it is the thing that
    saves the turn if a GenieX release ever ignores the flag again.
    """
    assert llmlib.strip_thinking("<|channel>thought\nhmm...<channel|>escalate") == "escalate"
    assert llmlib.strip_thinking("escalate") == "escalate"

    dead = llmlib.LlmClient(base_url="http://127.0.0.1:1/v1", timeout_s=1.0)
    assert dead.classify_reply(check_phase, {}, "my hip hurts") is None   # never raises
    assert dead.word_line("comfort", ["Sarah has been messaged"]) is None


# --- 4. the seam, end to end (T3.4) --------------------------------------


def test_engine_escalates_on_the_models_decision(live, tmp_path) -> None:
    """The whole T3.4 path: heard -> Gemma -> engine action -> caregiver messaged.

    And the audit line: a session that escalated because a model said so must
    say so on disk.
    """
    client, spy = live
    spy.reset()

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, llm=client, timer_scale=1.0, comfort_interval_s=1000)
        session = await fall(agent)
        await heard(agent, "my hip hurts a bit")
        # Generous: the device serves one request at a time, so a teammate's
        # long generation can put a whole turn (or its retry) behind theirs.
        await until(lambda: rec.count("notify_contacts") == 1, why="escalation on the model's decision", timeout=40)

        assert session.phase == "escalate"
        audit = [line for line in session.log if line.get("event") == "llm"]
        assert audit and audit[0]["decision"] == "escalate" and audit[0]["source"] == "gemma", audit
        print(f"\n  engine seam: heard 'my hip hurts a bit' -> {audit[0]['decision']} in {audit[0]['ms']} ms")

        # ...and the comfort loop's line is the model's words over the engine's facts.
        line = await agent.comfort_text(session)
        print(f"  comfort line: {line}")
        assert len(line) <= llmlib.MAX_LINE_CHARS
        assert "Sarah has been messaged" in agent.comfort_line(session)
        worded = [entry for entry in session.log if entry.get("kind") == "comfort"]
        assert worded and worded[-1]["source"] == "gemma", worded

        if session.task and not session.task.done():
            session.task.cancel()
            try:
                await session.task
            except asyncio.CancelledError:
                pass
        await agent.shutdown()

    asyncio.run(scenario())


def test_the_double_check_survives_the_model(live, tmp_path) -> None:
    """"I'm fine" -> the pain question -> "no" -> closed ok. The G3 headline.

    The one sequence where the model has to get *both* halves right and the
    engine has to keep the ritual: an "ok" first time only buys the canned
    question, and the same word ("no") means opposite things on either side of
    it. Under ``--no-llm`` this is ``test_im_fine_double_check``; this is the
    same walk with Gemma making both calls.
    """
    client, spy = live
    spy.reset()

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, llm=client, timer_scale=1.0, comfort_interval_s=1000)
        session = await fall(agent)

        def decisions() -> list[tuple[str, str]]:
            return [(e["heard"], e["decision"]) for e in session.log if e.get("event") == "llm"]

        await heard(agent, "i'm fine")
        await until(lambda: engine.PAIN_QUESTION in bus.said(), why="the pain double-check", timeout=40)
        assert session.state == "active", "an 'ok' must never close on its own"

        await heard(agent, "no")
        # 40 s, not 15: a queued device can cost a 6 s timeout plus its retry
        # before the regex fallback even gets the turn (and it still closes).
        await asyncio.wait_for(asyncio.shield(session.task), 40)
        assert session.final == "ok" and session.state == "closed", decisions()
        assert rec.calls == [], "nobody should have been messaged"

        print(f"\n  double-check: {decisions()}")
        assert decisions() == [("i'm fine", "ok"), ("no", "ok")]

    asyncio.run(scenario())
