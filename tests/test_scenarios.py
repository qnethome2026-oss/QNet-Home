# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T2.2 / T2.4 - the permanent regression suite (IMPLEMENTATION.md, Phase 2).

"Scenario tests from T2.2 are the regression suite; ``--no-llm`` must never
break." These four are the named ones:

    test_silence_full_escalation      silence -> escalate -> notified -> 911
    test_im_fine_double_check         "i'm fine" is a reply, not a cancel
    test_false_alarm_followup         "false alarm" is a cancel, and it apologises
    test_reentry_single_notification  re-entry never re-alarms the caregiver

The rest guard the v0 spine rules and the comfort loop. Everything runs on the
harness in ``conftest.py``: a fake bus, recorder tools, real timers at 1/20th
scale. No broker, no Telegram, no model.
"""

from __future__ import annotations

import asyncio
import json
import re
import time

from conftest import (
    Recorder,
    events,
    fall,
    finish,
    heard,
    jsonl,
    make_agent,
    stop,
    until,
)

from qnet.agent import engine

CHECK_OPENING = "I saw you fall. Take a breath — are you okay?"
ESCALATE_OPENING = "It's okay — I'm getting you help. Try to get comfortable, and don't strain to move."
CALL_HELP_OPENING = "You haven't answered, so I'm calling emergency services now."


def phase_pairs(lines: list[dict]) -> list[tuple[str, str]]:
    """Every phase transition on disk, in order - "from" -> "to"."""
    return [(line["from"], line["to"]) for line in events(lines, "phase")]


# --- the four named scenarios --------------------------------------------


def test_silence_full_escalation(tmp_path) -> None:
    """Silence walks the whole ladder on engine-owned timers, and nothing else does."""

    async def scenario() -> None:
        # Comfort interval parked well above the run so the say list is exactly
        # the three canned openings - the comfort loop has its own test below.
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        started = time.monotonic()
        session = await fall(agent)

        # The opening is canned and instant: it is said before any timer starts.
        assert bus.said() == [CHECK_OPENING]
        assert bus.says()[0]["prio"] == "safety"

        # The node keeps reporting listen timeouts; the phase timer decides, not them.
        for _ in range(3):
            await heard(agent, silence=True)

        await until(lambda: rec.count("notify_contacts") >= 1, why="escalate's on_enter")
        at_escalate = time.monotonic() - started
        assert 1.2 <= at_escalate <= 3.0, f"escalate at {at_escalate:.2f}s, expected ~1.5s (30s x 0.05)"
        assert session.phase == "escalate"
        assert session.contacts_notified is True
        assert ESCALATE_OPENING in bus.said()

        await until(lambda: rec.count("call_emergency") == 1, why="call_help's on_enter")
        at_call_help = time.monotonic() - started
        assert 0.4 <= at_call_help - at_escalate <= 2.0, f"call_help {at_call_help - at_escalate:.2f}s after escalate"
        assert session.phase == "call_help"
        assert CALL_HELP_OPENING in bus.said()

        # Order matters: contacts before the emergency call, both before any turn.
        assert rec.names() == ["notify_contacts", "call_emergency", "notify_contacts"]
        # ...and the second notify is call_help's own milestone (DESIGN §6's "up
        # to three pings", §7's second template), not a repeat of escalate's.
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == ["escalate", "call_help"]

        # The JSONL is the whole timeline, in order (§6).
        lines = jsonl(session)
        assert lines[0]["event"] == "detected" and lines[0]["kind"] == "fall.detected"
        assert phase_pairs(lines) == [("check", "escalate"), ("escalate", "call_help")]
        assert [line["text"] for line in events(lines, "say")] == [
            CHECK_OPENING,
            ESCALATE_OPENING,
            CALL_HELP_OPENING,
        ]
        assert [line["tool"] for line in events(lines, "tool")] == [
            "notify_contacts",
            "call_emergency",
            "notify_contacts",
        ]
        assert events(lines, "silence") == []
        assert len(events(lines, "heard")) == 3
        # The simulated call is visibly simulated wherever it is rendered (§14).
        emergency = [line for line in events(lines, "tool") if line["tool"] == "call_emergency"][0]
        assert "SIMULATED" in json.dumps(emergency)

        # Every line also went out live on qnet/session/<id> - one mechanism, two
        # destinations. The last document carries the full log.
        assert bus.sessions()[-1]["log"] == session.log
        assert bus.sessions()[-1]["urgency"] == "safety"

        # call_help has no timer and only a manual exit: it waits, as designed.
        assert session.state == "active"
        await stop(agent, session)

    asyncio.run(scenario())


def test_im_fine_double_check(tmp_path) -> None:
    """"I'm fine" is a reply: it routes through the pain question before closing."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        await heard(agent, "i'm fine")
        await until(lambda: engine.PAIN_QUESTION in bus.said(), why="the pain double-check")

        # It really is a question, spoken out loud, before anything closes.
        assert bus.said() == [CHECK_OPENING, engine.PAIN_QUESTION]
        assert session.state == "active"

        await heard(agent, "no")
        await finish(session)

        assert session.final == "ok"          # the exit label (§6's resolution rule)
        assert session.state == "closed"      # the wire contract's vocabulary (§4)
        assert rec.calls == []                # nobody was messaged, nothing was called

        lines = jsonl(session)
        said = [line["text"] for line in events(lines, "say")]
        assert said.index(engine.PAIN_QUESTION) < len(lines)
        assert phase_pairs(lines) == [("check", "ok")]
        assert [(line["text"], line["silence"]) for line in events(lines, "heard")] == [
            ("i'm fine", False),
            ("no", False),
        ]
        assert bus.sessions()[-1]["state"] == "closed"

    asyncio.run(scenario())


def test_false_alarm_followup(tmp_path) -> None:
    """"False alarm" mid-escalation cancels - and un-worries the caregiver."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        await until(lambda: rec.count("notify_contacts") == 1, why="escalate's on_enter")
        assert session.contacts_notified is True

        await heard(agent, "false alarm")
        await finish(session)

        assert session.state == "cancelled"
        assert session.final == "cancelled"
        # Exactly one follow-up, and it says what it is (§6, §7's third template).
        assert rec.count("notify_contacts") == 2
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == ["escalate", "false_alarm"]
        assert rec.count("call_emergency") == 0

        lines = jsonl(session)
        assert phase_pairs(lines) == [("check", "escalate"), ("escalate", "cancelled")]
        follow_up = events(lines, "tool")[-1]
        assert follow_up["tool"] == "notify_contacts" and follow_up.get("kind") == "false_alarm"
        assert bus.sessions()[-1]["state"] == "cancelled"

    asyncio.run(scenario())


def test_reentry_single_notification(tmp_path) -> None:
    """escalate -> check -> escalate must not send the caregiver a second alarm."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        await until(lambda: rec.count("notify_contacts") == 1, why="the first escalate")

        # A coherent reply mid-escalation takes escalate's `check` exit (§7).
        await heard(agent, "i'm still here")
        await until(lambda: session.phase == "check", why="the jump back to check")

        # ...then they go quiet again and the 30 s timer re-escalates.
        def escalated_twice() -> bool:
            return len([p for p in phase_pairs(session.log) if p == ("check", "escalate")]) == 2

        await until(escalated_twice, why="the second escalate")
        await asyncio.sleep(0.1)  # ample time for a re-fire, well inside escalate's 0.75 s

        assert session.phase == "escalate"
        assert rec.count("notify_contacts") == 1, "on_enter must be once per session, not per entry"
        assert rec.count("call_emergency") == 0

        lines = jsonl(session)
        assert phase_pairs(lines) == [("check", "escalate"), ("escalate", "check"), ("check", "escalate")]
        assert len(events(lines, "tool")) == 1
        await stop(agent, session)

    asyncio.run(scenario())


# --- the comfort loop (T2.4) ---------------------------------------------


def test_comfort_loop_speaks_grounded_updates(tmp_path) -> None:
    """Never leave them in silence - and never say anything that is not true (§6)."""

    async def scenario() -> None:
        # 4 s comfort interval at 0.05 scale = 200 ms between updates.
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=4)
        session = await fall(agent)
        await until(lambda: session.phase == "escalate", why="escalate")

        await until(lambda: len(bus.says()) >= 5, why="four comfort updates", timeout=6)
        comfort = [m for m in bus.says() if m["prio"] == "comfort"]
        assert len(comfort) >= 3

        for line in comfort:
            text = line["text"]
            # Grounded in what actually happened: a fact from the tool log...
            assert "Sarah has been messaged" in text
            # ...and an elapsed time that is true (T2.4: within +/-5 s).
            match = re.search(r"about (?:(\d+) minutes? and )?(\d+) seconds", text) or re.search(
                r"about (\d+) minutes?()", text
            )
            assert match, text
            claimed = int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
            assert abs(claimed - (time.time() - session.detected_at)) <= 5, text
            # The positioning line is said once, in the opening - never repeated.
            assert "get comfortable" not in text

        # Nothing overlaps: one speaker per session, strictly ordered lines.
        stamps = [line["ts"] for line in events(jsonl(session), "say")]
        assert stamps == sorted(stamps)

        # Once the emergency call has gone out, the update says so.
        await until(lambda: session.emergency_called, why="call_help")
        await until(
            lambda: any("emergency services are on the way" in m["text"] for m in bus.says()[-4:]),
            why="the update to mention the call",
            timeout=6,
        )
        await stop(agent, session)

    asyncio.run(scenario())


def test_comfort_drops_rather_than_overlapping(tmp_path) -> None:
    """If something else just spoke, the update is dropped, not queued behind it."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=4)
        session = await fall(agent)
        await until(lambda: session.phase == "escalate", why="escalate")
        await until(lambda: any(m["prio"] == "comfort" for m in bus.says()), why="the first update")

        spoken = len(bus.says())
        session.last_say_at = time.monotonic()  # as if a say had just gone out
        await agent.comfort(session)
        assert len(bus.says()) == spoken, "an update must never follow hard on another line"
        await stop(agent, session)

    asyncio.run(scenario())


def test_elapsed_phrase_is_accurate() -> None:
    """The spoken clock rounds, but never lies (T2.4: within +/-5 s)."""
    assert engine.elapsed_phrase(0) == "0 seconds"
    assert engine.elapsed_phrase(44) == "45 seconds"
    assert engine.elapsed_phrase(60) == "1 minute"
    assert engine.elapsed_phrase(85) == "1 minute and 25 seconds"
    assert engine.elapsed_phrase(120) == "2 minutes"
    for seconds in range(0, 400):
        phrase = engine.elapsed_phrase(seconds)
        match = re.match(r"(?:(\d+) minutes? ?(?:and )?)?(?:(\d+) seconds)?$", phrase)
        assert match, phrase
        claimed = int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
        assert abs(claimed - seconds) <= 5


# --- the rails, and the v0 rules that must survive the rewrite ------------


def test_cancel_phrases_only(tmp_path) -> None:
    """The explicit four close a session; "i'm fine" is not one of them (§6)."""
    assert engine.is_cancel("cancel")
    assert engine.is_cancel("stop")
    assert engine.is_cancel("never mind")
    assert engine.is_cancel("false alarm")
    assert engine.is_cancel("no wait, false alarm!")
    assert not engine.is_cancel("i'm fine")
    assert not engine.is_cancel("i'm ok, i just need a minute")
    # Word boundaries, so ordinary speech that merely contains the letters does not
    # close a live fall session.
    assert not engine.is_cancel("i stopped to rest")
    assert not engine.is_cancel("i cancelled my appointment yesterday")

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await heard(agent, "never mind")
        await finish(session)
        assert session.state == "cancelled"
        # Cancelled before anyone was told, so there is nothing to take back.
        assert rec.calls == []

    asyncio.run(scenario())


def test_out_of_phase_tool_is_refused(tmp_path) -> None:
    """The rails: a tool outside the phase's allowlist is logged, never executed."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        # Stand in for a model that tries to place the emergency call itself.
        async def rogue(phase, session_, text):
            return engine.Action("tool", tool="call_emergency")

        agent.decide = rogue
        await heard(agent, "hello")
        await until(lambda: events(session.log, "refusal"), why="the refusal line")

        refusal = events(session.log, "refusal")[0]
        assert refusal["tool"] == "call_emergency" and refusal["phase"] == "check"
        assert rec.count("call_emergency") == 0
        assert session.state == "active"
        await stop(agent, session)

    asyncio.run(scenario())


def test_duplicate_fall_ignored(tmp_path) -> None:
    """T1.3's rule survived the rewrite: one session per room (§6)."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        files_before = sorted(p.name for p in tmp_path.glob("*.jsonl"))
        says_before = len(bus.says())

        await fall(agent)  # the detector fires again mid-session
        await asyncio.sleep(0.05)

        assert sorted(p.name for p in tmp_path.glob("*.jsonl")) == files_before
        assert len(bus.says()) == says_before
        assert agent.sessions["kitchen"] is session
        await stop(agent, session)

    asyncio.run(scenario())


def test_safety_session_keeps_the_floor(tmp_path) -> None:
    """A wake phrase mid-escalation is ignored entirely: safety wins (§6)."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        says_before = len(bus.says())

        ask = {"id": "01J", "ts": time.time(), "room": "kitchen", "text": "where are my glasses", "kind": "query"}
        await agent.on_message("qnet/kitchen/ask", json.dumps(ask).encode())
        await asyncio.sleep(0.05)

        assert len(bus.says()) == says_before
        assert session.state == "active" and session.skill == "fall-response"
        await stop(agent, session)

    asyncio.run(scenario())


def test_pain_after_fine_escalates(tmp_path) -> None:
    """fall.md's guidance: pain or a hit head escalates even after "I'm fine"."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await heard(agent, "yes i'm okay")
        await until(lambda: engine.PAIN_QUESTION in bus.said(), why="the pain double-check")
        await heard(agent, "well my hip hurts")
        await until(lambda: rec.count("notify_contacts") == 1, why="escalation on reported pain")
        assert session.phase == "escalate"
        assert phase_pairs(session.log)[0] == ("check", "escalate")
        await stop(agent, session)

    asyncio.run(scenario())


def test_heard_without_a_session_is_ignored(tmp_path) -> None:
    """No session, no listener - a stray transcript must not create one."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path)
        await heard(agent, "hello?")
        await asyncio.sleep(0.02)
        assert agent.sessions == {}
        assert bus.messages == []

    asyncio.run(scenario())


def test_recorder_registry_is_the_only_tool_source(tmp_path) -> None:
    """These tests never touch qnet/tools - the engine takes the registry it is given."""
    recorder = Recorder()
    agent, _bus, rec = make_agent(tmp_path, recorder=recorder)
    assert rec is recorder
    assert set(agent.tools) == {"notify_contacts", "call_emergency", "look_in_rooms"}
    assert agent.tools["call_emergency"].engine_only is True


def test_pain_denial_with_the_pain_word_resolves(tmp_path) -> None:
    """"no, i'm not hurt" contains "hurt" - without negation handling the
    --no-llm mind escalated an explicit denial (found by the voice system
    harness, tests/voice/test_voice_system.py). Denials resolve; bare "hurt"
    still escalates; ambiguity still errs toward escalation."""
    from qnet.agent.engine import classify_reply, _NEGATED_PAIN_RE
    assert _NEGATED_PAIN_RE.search("no, i'm not hurt")
    assert _NEGATED_PAIN_RE.search("no i am not in pain")
    assert _NEGATED_PAIN_RE.search("nothing hurts")
    assert not _NEGATED_PAIN_RE.search("my hip hurts")
    assert not _NEGATED_PAIN_RE.search("yes it hurts")
    # "no... but my head hurt when i fell" - the negation window is 2 words,
    # so a far-away pain word still escalates (the safe direction).
    assert not _NEGATED_PAIN_RE.search("no idea what happened but my head really seriously hurts")


def test_help_me_gets_an_answer_not_the_status_recording(tmp_path) -> None:
    """Live finding (2026-08-06): "Help me" / "What can I do?" mid-call_help
    earned only the next timed status line. An unrouted utterance in a safety
    session now gets a responsive reply - and since skills/first-aid.md, a
    responsive one: "help me" keyword-matches its stuck topic and the canned
    reply carries that topic's sentence, while "what can i do" matches nothing
    and gets the acknowledgment-only fallback. Either way it resets the
    comfort clock instead of stacking on it."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        for _ in range(3):
            await heard(agent, silence=True)
        await until(lambda: rec.count("call_emergency") == 1, why="reach call_help")
        before = len(bus.said())

        await heard(agent, text="help me")
        await until(lambda: len(bus.said()) > before, why="a reply to the person")
        stuck = agent.first_aid.match("help me")
        assert stuck is not None and stuck.id == "stuck"
        assert bus.said()[-1] == engine.REPLY_GUIDED.replace("{guidance}", stuck.guidance)

        await heard(agent, text="what can i do")
        await until(lambda: len(bus.said()) > before + 1, why="a second reply")
        assert bus.said()[-1] == engine.REPLY_FALLBACK
        # Still in call_help - answering is not an exit, and silence heards
        # never trigger it (no chatty replies to timeouts).
        assert session.phase == "call_help"
        prev = len(bus.said())
        await heard(agent, silence=True)
        await asyncio.sleep(0.2)
        assert len(bus.said()) == prev

    asyncio.run(scenario())


def test_head_hurts_transcript_no_stupid_replay(tmp_path) -> None:
    """The 2026-08-06 live transcript, as a regression: (1) "i'm not okay my
    head hurts" escalates AND earns the head guidance, not just the generic
    opening; (2) "but my head hurts, what should i do" jumps back to check
    WITHOUT replaying "I saw you fall - are you okay?" and gets the guidance
    answered instead."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        assert bus.said().count(CHECK_OPENING) == 1

        await heard(agent, text="i'm not okay my head hurts")
        await until(lambda: session.phase == "escalate", why="pain words escalate")
        await until(lambda: any("lying down" in t for t in bus.said()),
                    why="head guidance follows the escalate opening")

        await heard(agent, text="but my head hurts, what should i do")
        await until(lambda: session.phase == "check", why="responding jumps back to check")
        # a moment for the revisit reply to land
        await until(lambda: sum(1 for t in bus.said() if "lying down" in t) >= 2,
                    why="the question gets the guidance answered again")
        # THE bug: the opening must not replay on re-entry.
        assert bus.said().count(CHECK_OPENING) == 1

    asyncio.run(scenario())
