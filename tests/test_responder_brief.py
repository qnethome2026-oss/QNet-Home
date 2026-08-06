# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T6.1 - the responder brief, an interrupt rather than a session (DESIGN.md §12).

"A first responder walks in and says *I'm the first responder, can you tell me
what happened?* - the room answers with a spoken timeline." The three things
that have to be true, and are asserted here:

* **it runs mid-escalation**, because it never enters the session table - and
  the fall session it summarises does not notice: same phase, same timers, same
  tool count afterwards. The comfort loop is paused while the brief speaks and
  resumes on its own.
* **it is a formatter over data that already exists** - every claim in the
  summary came off the session's own JSONL, read live, with no "finalize the
  log" step.
* **a room with no fall on file says so plainly**, and does nothing else.

Hermetic like the rest: the fake bus, the recorder tools, the *real*
``get_session_summary`` (it only reads files), and a fake Gemma whose only job
is to be slow enough to prove the comfort loop is really paused.
"""

from __future__ import annotations

import asyncio
import json
import time

from conftest import StubSpec, events, fall, fixture, finish, heard, jsonl, make_agent, stop, until

from qnet.agent import engine
from qnet.tools.get_session_summary import get_session_summary


class SlowGemma:
    """A model that words the brief - slowly - and declines everything else.

    Slow on purpose: the comfort loop ticks every 100 ms in these tests, so a
    250 ms brief is several missed updates. If the pause were not real, the
    comfort line would land in the middle of the brief.
    """

    def __init__(self, reply: str = "", delay: float = 0.25) -> None:
        self.reply, self.delay = reply, delay
        self.calls: list[tuple[str, list[str], str]] = []

    def word_line(self, kind: str, facts, goal: str = "") -> str | None:
        self.calls.append((kind, list(facts), goal))
        if kind != "brief":
            return None  # the comfort loop words its own line, as it always did
        time.sleep(self.delay)  # in a worker thread: the event loop keeps running
        return self.reply or None

    def classify_reply(self, *args, **kwargs) -> None:
        return None  # the regex classifier decides, exactly as under --no-llm

    def extract_object(self, *args, **kwargs) -> None:
        return None


def brief_agent(tmp_path, llm=None, **overrides):
    """An agent that can actually read a session file back (the real T2.3 tool)."""
    agent, bus, rec = make_agent(tmp_path, llm=llm, **overrides)
    agent._tools["get_session_summary"] = StubSpec(get_session_summary, engine_only=False)
    return agent, bus, rec


async def responder(agent, room: str = "kitchen") -> dict:
    """Say the phrase: `qnet/<room>/ask` with kind=responder_brief, no text (§4)."""
    msg = fixture("ask_responder_brief")
    msg.update({"room": room, "ts": time.time(), "id": f"ask-{room}-{len(agent.sessions)}"})
    await agent.on_message(f"qnet/{room}/ask", json.dumps(msg).encode())
    return msg


def comfort_lines(bus, room: str = "kitchen") -> list[str]:
    return [m["text"] for m in bus.says(room) if m["prio"] == "comfort"]


# --- mid-escalation: the moment the brief exists for -----------------------


def test_brief_mid_escalation(tmp_path) -> None:
    """A live fall session is summarised, unharmed, while the comfort loop waits."""

    async def scenario() -> None:
        gemma = SlowGemma()
        # 0.1 timer scale: escalate's 15 s timer is 1.5 s, comfort every 100 ms.
        agent, bus, rec = brief_agent(tmp_path, llm=gemma, timer_scale=0.1, comfort_interval_s=1)
        session = await fall(agent)

        await heard(agent, "my hip hurts")
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate's on_enter")
        await until(lambda: len(comfort_lines(bus)) >= 2, why="the comfort loop to be running")

        phases_before = [(e["from"], e["to"]) for e in events(session.log, "phase")]
        comfort_before = len(comfort_lines(bus))
        tools_before = rec.names()[:]
        assert session.phase == "escalate"

        msg = await responder(agent)

        # 1. It spoke a timeline, into the room, at safety priority (a fall is live).
        spoken = bus.says()[-1]
        assert spoken["prio"] == "safety"
        text = spoken["text"]

        # 2. ...naming facts that are really in the log: the room, what they
        #    actually said, who was actually messaged, where it actually stands.
        assert "kitchen" in text
        assert "my hip hurts" in text
        assert "Sarah" in text
        assert "escalate" in text
        assert gemma.calls and gemma.calls[-1][0] == "brief"
        assert "timeline" in gemma.calls[-1][2], "the skill file's own goal is what is sent"

        # 3. The fall session did not notice: same phase, same transitions, same
        #    tools, still active. The brief is read-only against the rails.
        assert session.phase == "escalate"
        assert session.state == "active"
        assert [(e["from"], e["to"]) for e in events(session.log, "phase")] == phases_before
        assert rec.names() == tools_before

        # 4. The comfort loop was paused while it spoke - not one update landed
        #    inside the brief - and resumed by itself afterwards.
        assert len(comfort_lines(bus)) == comfort_before, "the comfort loop talked over the brief"
        await until(lambda: len(comfort_lines(bus)) > comfort_before, why="the comfort loop to resume")
        assert session.comfort_paused is False

        # 5. Exactly one `brief` line, in the file it summarised (§12).
        briefs = events(jsonl(session), "brief")
        assert len(briefs) == 1
        assert briefs[0]["ask_id"] == msg["id"]
        assert briefs[0]["spoken"] is True
        assert briefs[0]["text"] == text

        # 6. ...and the engine-owned timer still fires, on its own schedule.
        await until(lambda: session.phase == "call_help", why="escalate's timer", timeout=6)
        await stop(agent, session)

    asyncio.run(scenario())


def test_brief_mid_escalation_without_gemma(tmp_path) -> None:
    """No model, no silence: the engine assembles the same timeline itself (§12)."""

    async def scenario() -> None:
        agent, bus, rec = brief_agent(tmp_path, timer_scale=0.1, comfort_interval_s=1000)
        session = await fall(agent)
        await heard(agent, "i can't get up")
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate's on_enter")

        await responder(agent)

        text = bus.says()[-1]["text"]
        assert text.startswith("Here's what happened.")
        assert "kitchen" in text and "i can't get up" in text and "Sarah" in text
        assert "still open" in text
        assert session.state == "active" and session.phase == "escalate"
        await stop(agent, session)

    asyncio.run(scenario())


# --- after it closed --------------------------------------------------------


def test_brief_after_close(tmp_path) -> None:
    """Ask after it resolves and the summary is the whole arc, ending in its state."""

    async def scenario() -> None:
        agent, bus, rec = brief_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        await heard(agent, "i'm fine")
        await until(lambda: engine.PAIN_QUESTION in bus.said(), why="the pain double-check")
        await heard(agent, "no")
        await finish(session)
        assert session.state == "closed" and session.final == "ok"

        says_before = len(bus.says())
        msg = await responder(agent)

        text = bus.says()[-1]["text"]
        # Detection, what they said, and the state it ended in - §12's list.
        assert "fall was detected" in text and "kitchen" in text
        assert "i'm fine" in text
        assert "not hurt" in text, text
        assert "elapsed" in text
        # No fall is live in the room any more, so this is not a safety line.
        assert bus.says()[-1]["prio"] == engine.ROUTINE_PRIO
        assert len(bus.says()) == says_before + 1, "the brief speaks once"

        # One brief line, appended to the closed session's own file, and the
        # session itself is untouched - still closed, still `ok`.
        lines = jsonl(session)
        assert lines[-1]["event"] == "brief"
        assert lines[-1]["ask_id"] == msg["id"] and lines[-1]["spoken"] is True
        assert len(events(lines, "brief")) == 1
        assert session.state == "closed" and session.final == "ok"
        # The dashboard saw it too - one stream, two destinations (§6).
        assert bus.sessions()[-1]["log"][-1]["event"] == "brief"

    asyncio.run(scenario())


def test_brief_reads_the_latest_file_live(tmp_path) -> None:
    """Ask twice and the second summary knows what happened in between (§12)."""

    async def scenario() -> None:
        agent, bus, rec = brief_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await responder(agent)
        first = bus.says()[-1]["text"]

        await until(lambda: rec.count("call_emergency") == 1, why="the full ladder")
        await responder(agent)
        second = bus.says()[-1]["text"]

        assert "Sarah" not in first, "nobody had been messaged when the first brief was asked"
        assert "Sarah" in second and "emergency services were called" in second
        assert len(events(jsonl(session), "brief")) == 2
        await stop(agent, session)

    asyncio.run(scenario())


# --- a room with no fall on file --------------------------------------------


def test_brief_no_history(tmp_path) -> None:
    """"No fall has been recorded in this room." - and nothing else happens (§12)."""

    async def scenario() -> None:
        agent, bus, rec = brief_agent(tmp_path)

        await responder(agent, room="bedroom")

        assert bus.says("bedroom") == [{"text": engine.NO_FALL_HISTORY, "prio": engine.ROUTINE_PRIO}]
        # Nothing else: no session, no file, no dashboard document, no tool call.
        assert bus.messages == [("qnet/bedroom/say", {"text": engine.NO_FALL_HISTORY,
                                                      "prio": engine.ROUTINE_PRIO})]
        assert agent.sessions == {}
        assert list(tmp_path.glob("*.jsonl")) == []
        assert rec.calls == []

    asyncio.run(scenario())


def test_brief_ignores_a_find_session_in_the_room(tmp_path) -> None:
    """§12 is scoped to fall response: a find session is invisible to the brief."""

    async def scenario() -> None:
        agent, bus, rec = brief_agent(tmp_path)
        # A find session file exists for the room, and only that.
        (tmp_path / "bedroom__find-object__2026-08-05T10-00-00.jsonl").write_text(
            json.dumps({"ts": 100.0, "event": "heard", "text": "where are my glasses", "silence": False}) + "\n",
            encoding="utf-8",
        )

        await responder(agent, room="bedroom")

        assert bus.said("bedroom") == [engine.NO_FALL_HISTORY]

    asyncio.run(scenario())
