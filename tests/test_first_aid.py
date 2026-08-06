# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The fall-response conversation upgrade (user findings, 2026-08-06).

Three behaviours, all hermetic on the conftest harness:

* **Cadence** - the comfort loop's default is a schedule (60/120/then every
  300 s from detection, `dev.timer_scale` applied), not a fixed 20 s drumbeat.
  `interval_s` stays as the legacy override, which is what every other test in
  the suite runs on.
* **No boring repetition** - consecutive canned comfort lines never share
  identical wording (the facts repeat; the sentence must not).
* **Guidance as data** - `skills/first-aid.md` is keyword-matched on the rails
  in `reply_to`: "i'm cold" earns its warmth sentence, "i'm fine" earns a warm
  acknowledgment and not one word of first aid, and a missing or malformed
  file degrades to the acknowledgment-only fallback without a crash.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from conftest import fall, heard, make_agent, stop, until

from qnet.agent import engine

REAL_SKILLS = Path(__file__).resolve().parents[1] / "skills"

# The words that must never appear in a reply to someone who said they are
# fine: every one of them belongs to a first-aid topic, none to an
# acknowledgment.
FIRST_AID_WORDS_RE = re.compile(r"\b(bleeding|press|cover|still)\b", re.IGNORECASE)


async def reach_call_help(agent, rec) -> None:
    """Walk the silent ladder to call_help - the phase where replies happen."""
    for _ in range(3):
        await heard(agent, silence=True)
    await until(lambda: rec.count("call_emergency") == 1, why="reach call_help")


def comfort_says(bus) -> list[str]:
    # Status updates only: guided replies also ride prio "comfort", but every
    # status line carries the elapsed clause and replies never do.
    return [m["text"] for m in bus.says()
            if m["prio"] == "comfort" and "since I saw you fall" in m["text"]]


# --- the 1/2/5 cadence ----------------------------------------------------


def test_comfort_schedule_first_two_slots(tmp_path) -> None:
    """First status ~60 s after detection, second ~120 s - scaled, and never
    the old 20 s drumbeat. `comfort` config carries only `schedule_s`, so this
    is the default cadence path, not the legacy interval."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(
            tmp_path, timer_scale=0.05, comfort={"schedule_s": [60, 120, 300]}
        )
        assert agent.comfort_schedule_s == [60.0, 120.0, 300.0]
        started = time.monotonic()
        session = await fall(agent)

        # An early call for help escalates immediately, so the phase openings
        # (check at 0, call_help at ~30 s scaled) stay clear of the 60 s and
        # 120 s slots - the slots themselves are what this test measures.
        await heard(agent, "help me")
        await until(lambda: rec.count("call_emergency") == 1, why="call_help via the 30s timer")

        await until(lambda: len(comfort_says(bus)) >= 1, timeout=10, why="the 60s slot")
        first_at = time.monotonic() - started
        await until(lambda: len(comfort_says(bus)) >= 2, timeout=10, why="the 120s slot")
        second_at = time.monotonic() - started

        # 60 x 0.05 = 3.0 s and 120 x 0.05 = 6.0 s, with the suite's usual
        # slack. first_at's floor also proves the 20 s default is gone
        # (20 x 0.05 = 1.0 s would have spoken long before 2.4).
        assert 2.4 <= first_at <= 4.5, f"first status at {first_at:.2f}s, expected ~3.0s (60s x 0.05)"
        assert 5.4 <= second_at <= 7.6, f"second status at {second_at:.2f}s, expected ~6.0s (120s x 0.05)"
        assert 2.0 <= second_at - first_at <= 4.5

        # Consecutive updates carry the same true facts in different words.
        lines = comfort_says(bus)[:2]
        assert lines[0] != lines[1]
        for text in lines:
            assert "Sarah has been messaged" in text
        await stop(agent, session)

    asyncio.run(scenario())


def test_malformed_schedule_degrades_to_default(tmp_path) -> None:
    """A broken schedule_s costs the custom cadence, never the agent."""
    agent, _bus, _rec = make_agent(tmp_path, comfort={"schedule_s": "every so often"})
    assert agent.comfort_schedule_s == list(engine.DEFAULT_COMFORT_SCHEDULE_S)
    # ...and the repeating tail: [60, 120, 300] means 300-gap slots forever.
    assert agent.comfort_offset_s(2) == 300.0
    assert agent.comfort_offset_s(3) == 600.0
    assert agent.comfort_offset_s(4) == 900.0


def test_consecutive_canned_comfort_lines_differ(tmp_path) -> None:
    """The facts repeat; the sentence must not (legacy cadence, so the whole
    existing suite exercises the same rotating shapes)."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=4)
        session = await fall(agent)
        await until(lambda: session.phase == "escalate", why="escalate")
        await until(lambda: len(comfort_says(bus)) >= 4, timeout=8, why="four comfort updates")

        lines = comfort_says(bus)
        for previous, current in zip(lines, lines[1:]):
            assert previous != current, f"consecutive comfort lines repeated: {current!r}"
        assert session.last_comfort_text == lines[-1]
        await stop(agent, session)

    asyncio.run(scenario())


# --- guidance as data: skills/first-aid.md --------------------------------


def test_first_aid_file_loads_with_its_provenance(tmp_path) -> None:
    """The shipped file parses, keeps its review flag, and matches in file
    order - head before pain, word boundaries, no match for small talk."""
    agent, _bus, _rec = make_agent(tmp_path)
    fa = agent.first_aid
    assert fa is not None
    assert fa.meta.get("region") == "US-CA"
    assert "DESIGN" in str(fa.meta.get("review"))  # §18: pending human medical review

    assert fa.match("my head hurts today").id == "head"      # specificity: head outranks pain
    assert fa.match("my hip hurts").id == "pain"
    assert fa.match("I think I'm bleeding").id == "bleeding"
    assert fa.match("i'm so cold").id == "cold"
    assert fa.match("help me please").id == "stuck"
    assert fa.match("i'm fine") is None
    assert fa.match("what can i do") is None
    assert fa.match("it's colder in here than usual") is None  # word-boundary: "colder" is not "cold"
    assert fa.match("") is None


def test_cold_reply_carries_the_warmth_guidance(tmp_path) -> None:
    """"i'm cold" mid-call_help earns the cold topic's sentence, canned."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await reach_call_help(agent, rec)
        before = len(bus.said())

        await heard(agent, "i'm cold")
        await until(lambda: len(bus.said()) > before, why="a reply to the person")
        reply = bus.said()[-1]
        cold = agent.first_aid.match("i'm cold")
        assert cold is not None and cold.id == "cold"
        assert reply == engine.REPLY_GUIDED.replace("{guidance}", cold.guidance)
        assert "Cover yourself" in reply and "Help is on the way." in reply
        assert session.phase == "call_help"  # a reply is never an exit
        await stop(agent, session)

    asyncio.run(scenario())


def test_im_fine_reply_has_no_first_aid_content(tmp_path) -> None:
    """"im fine" mid-call_help gets warmth and status posture, zero first aid."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await reach_call_help(agent, rec)
        before = len(bus.said())

        await heard(agent, "im fine")
        await until(lambda: len(bus.said()) > before, why="a reply to the person")
        reply = bus.said()[-1]
        assert reply == engine.REPLY_FALLBACK
        assert not FIRST_AID_WORDS_RE.search(reply), reply
        await stop(agent, session)

    asyncio.run(scenario())


class FactSpy:
    """A stand-in LLM that records every word_line fact list and answers nothing,
    so the engine's canned path speaks and the PROMPT content is assertable."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def word_line(self, kind: str, facts, goal: str = "") -> None:
        self.calls.append((kind, list(facts)))
        return None

    def classify_reply(self, phase, session_context, heard_text: str) -> None:
        return None

    def extract_object(self, text: str) -> None:
        return None


def test_reply_prompt_carries_guidance_only_when_matched(tmp_path) -> None:
    """The rails choose what the model may see: a matched topic arrives as one
    'relevant guidance' fact; an unmatched reply's prompt holds no first-aid
    content at all; and the previous spoken line rides along as the
    do-not-reuse instruction."""

    async def scenario() -> None:
        spy = FactSpy()
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000, llm=spy)
        session = await fall(agent)
        await reach_call_help(agent, rec)

        before = len(bus.said())
        await heard(agent, "i'm cold")
        await until(lambda: len(bus.said()) > before, why="the cold reply")
        kind, facts = spy.calls[-1]
        assert kind == "reply"
        assert any("relevant guidance" in f and "Cover yourself" in f for f in facts)

        await heard(agent, "im fine")
        await until(lambda: len(bus.said()) > before + 1, why="the fine reply")
        kind, facts = spy.calls[-1]
        assert kind == "reply"
        assert not any("guidance" in f for f in facts), facts
        assert not any(FIRST_AID_WORDS_RE.search(f) for f in facts if "do not reuse" not in f), facts
        # The previous spoken line (the cold reply) is passed as an instruction.
        assert any("do not reuse this wording" in f for f in facts)
        await stop(agent, session)

    asyncio.run(scenario())


# --- degradation: missing or malformed file = feature off ------------------


def skills_dir_with(tmp_path: Path, first_aid_text: str | None) -> Path:
    """A skills dir holding the real fall.md and the given first-aid.md, if any."""
    skdir = tmp_path / "skills"
    skdir.mkdir()
    (skdir / "fall.md").write_text(
        (REAL_SKILLS / "fall.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    if first_aid_text is not None:
        (skdir / "first-aid.md").write_text(first_aid_text, encoding="utf-8")
    return skdir


MALFORMED_VARIANTS = (
    "no frontmatter at all\n\n## pain\nkeywords: pain\nStay still.\n",
    "---\nregion: US-CA\n---\n\n## pain\nStay still, no keywords line here.\n",
)


def test_missing_or_malformed_first_aid_degrades_to_fallback(tmp_path) -> None:
    """No file, or a broken one: replies still answer (REPLY_FALLBACK), the
    fall ladder is untouched, nothing crashes."""

    async def scenario(first_aid_text: str | None, label: str) -> None:
        base = tmp_path / label
        base.mkdir()
        skdir = skills_dir_with(base, first_aid_text)
        agent, bus, rec = make_agent(
            base,
            timer_scale=0.05,
            comfort_interval_s=1000,
            storage={"sessions_dir": str(base), "skills_dir": str(skdir)},
        )
        assert agent.first_aid is None
        session = await fall(agent)
        await reach_call_help(agent, rec)
        before = len(bus.said())

        await heard(agent, "i'm cold")  # would have matched, but the feature is off
        await until(lambda: len(bus.said()) > before, why="the fallback reply")
        assert bus.said()[-1] == engine.REPLY_FALLBACK
        assert session.phase == "call_help"
        await stop(agent, session)

    async def all_variants() -> None:
        await scenario(None, "missing")
        for index, text in enumerate(MALFORMED_VARIANTS):
            await scenario(text, f"malformed{index}")

    asyncio.run(all_variants())


def test_reply_prompt_is_a_caregiver_not_a_chatbot() -> None:
    """User finding (2026-08-06): "what is speech to text?" mid-incident got a
    general-assistant answer. The reply prompt must pin the persona (QNet, not
    a general-purpose assistant) and instruct off-topic redirection."""
    from qnet.agent import llm as llmlib
    client = llmlib.LlmClient.__new__(llmlib.LlmClient)
    prompt = llmlib.LlmClient._word_prompt(client, "reply", ["the person just said: \"what is speech to text\""], "")
    assert "NOT a general-purpose assistant" in prompt
    assert "do NOT answer it" in prompt
    assert "Never explain your own workings" in prompt
