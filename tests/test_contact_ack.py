# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T-contact-ack - the trusted contact's reply window.

The escalation Telegram became a question: the contact gets 30 s to reply OK
before the (SIMULATED) emergency call fires. These tests pin the whole flow on
the engine rails, hermetically: contact replies are injected straight into
``Agent.on_contact_reply`` (exactly what the poller does with a real Telegram
message), and the poller itself is unit-tested against a fake httpx client.
No broker, no network, no model - same harness as ``test_scenarios.py``.

The rules under test, from the user decision of 2026-08-06:

* an ack ("ok" / "on my way" / ...) within the 30 s window -> the session
  jumps to ``contact_engaged``, speaks the contact's name, and holds off
* no ack -> ``call_help`` at the scaled 30 s, exactly as before
* ack then silence -> the 180 s backstop still calls: an acked-then-silence
  must never strand someone
* a contact's "call 911" -> ``call_help`` immediately, from ``escalate`` and
  from ``contact_engaged`` both
* contact matching is regex on the engine rails - the LLM never routes it
* an unsolicited reply (no escalating safety session) does exactly nothing
"""

from __future__ import annotations

import asyncio
import json
import time

from conftest import events, fall, finish, heard, jsonl, make_agent, stop, until

from qnet.agent import engine, telegram_poller

ENGAGED_OPENING = (
    "Good news — Sarah saw my message and is coming to check on you. "
    "I'll stay with you until they arrive."
)


def phase_pairs(lines: list[dict]) -> list[tuple[str, str]]:
    return [(line["from"], line["to"]) for line in events(lines, "phase")]


# --- the verdict regexes: engine rails, never the LLM ----------------------


def test_contact_verdicts() -> None:
    """The ack set, the emergency set, and the words that are neither."""
    for ack in ("ok", "OK", "okay", "on it", "got it", "omw", "On my way!", "i got this", "handling it"):
        assert engine.contact_verdict(ack) == "ack", ack
    for emergency in ("call 911", "CALL 911 NOW", "please call emergency services", "call emergency", "call 9-1-1"):
        assert engine.contact_verdict(emergency) == "emergency", emergency
    # Emergency wins even when an ack word is in the same message.
    assert engine.contact_verdict("ok, call 911") == "emergency"
    # Word boundaries: these contain the letters, not the words.
    for other in ("looking into who is around", "tokyo is far", "what happened?", ""):
        assert engine.contact_verdict(other) is None, other


# --- ack within the window -> contact_engaged ------------------------------


def test_ack_engages_contact(tmp_path) -> None:
    """Reply OK inside 30 s: no emergency call, and the room hears Sarah's name."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)

        await until(lambda: rec.count("notify_contacts") == 1, why="escalate's on_enter")
        escalated_at = time.monotonic()
        assert session.phase == "escalate"

        await agent.on_contact_reply("Sarah", "ok, on my way")
        await until(lambda: session.phase == "contact_engaged", why="the engine-rails jump")

        # The room is told, by name, grounded in the reply that actually came.
        assert ENGAGED_OPENING in bus.said()
        assert session.engaged_contact == "Sarah"

        # The confirmation went back to the contact - the fourth template,
        # through the same on_enter machinery as every milestone.
        await until(lambda: rec.count("notify_contacts") == 2, why="the hold-off confirmation")
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == ["escalate", "contact_engaged"]

        # The reply is visible everywhere the contract says it is: the session
        # log, the republished session document, and qnet/<room>/contact.
        lines = jsonl(session)
        contact_lines = events(lines, "contact")
        assert [(line["from"], line["text"]) for line in contact_lines] == [("Sarah", "ok, on my way")]
        assert ("escalate", "contact_engaged") in phase_pairs(lines)
        wire = bus.on("qnet/kitchen/contact")
        assert len(wire) == 1
        assert wire[0]["from"] == "Sarah" and wire[0]["text"] == "ok, on my way"
        assert isinstance(wire[0]["ts"], float)
        assert bus.sessions()[-1]["log"] == session.log

        # Past the moment the 30 s (scaled: 1.5 s) timer would have fired:
        # the jump cancelled it, so no emergency call - that is the feature.
        await asyncio.sleep(max(0.0, escalated_at + 2.0 - time.monotonic()))
        assert rec.count("call_emergency") == 0
        assert session.phase == "contact_engaged"
        assert session.state == "active"
        await stop(agent, session)

    asyncio.run(scenario())


def test_no_ack_still_calls_at_scaled_30s(tmp_path) -> None:
    """Nobody replies: the ladder is exactly what it always was, on the new clock."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        started = time.monotonic()
        session = await fall(agent)

        await until(lambda: rec.count("call_emergency") == 1, why="call_help's on_enter")
        at_call = time.monotonic() - started
        # 30 s check + 30 s escalate at 0.05 scale = 3.0 s. The escalate leg is
        # the one this change stretched (15 -> 30 s), so pin the total.
        assert 2.4 <= at_call <= 4.5, f"call_help at {at_call:.2f}s, expected ~3.0s (60s x 0.05)"
        assert session.phase == "call_help"
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == ["escalate", "call_help"]
        assert events(jsonl(session), "contact") == []
        await stop(agent, session)

    asyncio.run(scenario())


def test_ack_then_silence_backstop_calls(tmp_path) -> None:
    """An acked-then-silence must not strand someone: 180 s later, call_help."""

    async def scenario() -> None:
        # 0.01 scale: check 0.3 s, escalate 0.3 s, backstop 1.8 s.
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.01, comfort_interval_s=1000)
        session = await fall(agent)

        await until(lambda: rec.count("notify_contacts") == 1, why="escalate's on_enter")
        await agent.on_contact_reply("Sarah", "omw")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")
        engaged_at = time.monotonic()

        await until(lambda: rec.count("call_emergency") == 1, why="the backstop", timeout=6)
        backstop = time.monotonic() - engaged_at
        assert 1.4 <= backstop <= 3.2, f"backstop at {backstop:.2f}s, expected ~1.8s (180s x 0.01)"
        assert session.phase == "call_help"
        # All three milestones went out, in order, each exactly once (SIMULATED
        # call included - the recorder's payload carries the marker).
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == [
            "escalate", "contact_engaged", "call_help",
        ]
        emergency = [l for l in events(jsonl(session), "tool") if l["tool"] == "call_emergency"]
        assert len(emergency) == 1 and "SIMULATED" in json.dumps(emergency[0])
        await stop(agent, session)

    asyncio.run(scenario())


# --- the contact's "call 911" ----------------------------------------------


def test_contact_call_911_from_escalate(tmp_path) -> None:
    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate")
        asked_at = time.monotonic()

        await agent.on_contact_reply("Sarah", "call 911")
        await until(lambda: rec.count("call_emergency") == 1, why="the immediate call")
        # Immediate means the reply did it, not the 1.5 s (scaled) timer.
        assert time.monotonic() - asked_at < 1.0
        assert session.phase == "call_help"
        assert ("escalate", "call_help") in phase_pairs(session.log)
        await stop(agent, session)

    asyncio.run(scenario())


def test_contact_call_911_from_contact_engaged(tmp_path) -> None:
    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate")
        await agent.on_contact_reply("Sarah", "ok")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")
        changed_mind_at = time.monotonic()

        await agent.on_contact_reply("Sarah", "actually call emergency services")
        await until(lambda: rec.count("call_emergency") == 1, why="the immediate call")
        # Long before the 9 s (scaled 180 s) backstop: the reply did it.
        assert time.monotonic() - changed_mind_at < 1.0
        assert session.phase == "call_help"
        assert ("contact_engaged", "call_help") in phase_pairs(session.log)
        await stop(agent, session)

    asyncio.run(scenario())


# --- replies that must do nothing ------------------------------------------


def test_unsolicited_reply_is_dropped(tmp_path) -> None:
    """No session at all: log-drop - nothing published, nothing created."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path)
        await agent.on_contact_reply("Sarah", "ok")
        await asyncio.sleep(0.02)
        assert agent.sessions == {}
        assert bus.messages == []
        assert rec.calls == []

    asyncio.run(scenario())


def test_reply_during_check_phase_is_dropped(tmp_path) -> None:
    """Before escalation the contact has not even been messaged - no routing."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=1.0, comfort_interval_s=1000)
        session = await fall(agent)
        assert session.phase == "check"

        await agent.on_contact_reply("Sarah", "ok")
        await asyncio.sleep(0.05)
        assert session.phase == "check"
        assert events(session.log, "contact") == []
        assert bus.on("qnet/kitchen/contact") == []
        await stop(agent, session)

    asyncio.run(scenario())


def test_second_ack_in_contact_engaged_changes_nothing(tmp_path) -> None:
    """A second "ok" is noted (logged) but re-alarms and re-jumps nothing."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate")
        await agent.on_contact_reply("Sarah", "ok")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")
        await until(lambda: rec.count("notify_contacts") == 2, why="the confirmation")

        await agent.on_contact_reply("Sarah", "got it")
        await asyncio.sleep(0.1)
        assert session.phase == "contact_engaged"
        assert rec.count("notify_contacts") == 2  # no second confirmation
        assert len(events(session.log, "contact")) == 2  # both replies on the record
        await stop(agent, session)

    asyncio.run(scenario())


# --- the person's own exits still work from contact_engaged -----------------


def test_cancel_phrases_work_in_contact_engaged(tmp_path) -> None:
    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate")
        await agent.on_contact_reply("Sarah", "on my way")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")

        await heard(agent, "false alarm")
        await finish(session)
        assert session.state == "cancelled"
        assert rec.count("call_emergency") == 0
        # The caregiver is un-worried, exactly as from escalate (§6).
        assert [k["kind"] for k in rec.kwargs("notify_contacts")] == [
            "escalate", "contact_engaged", "false_alarm",
        ]

    asyncio.run(scenario())


def test_person_reply_in_contact_engaged_reassesses(tmp_path) -> None:
    """The person speaking still routes as always: back to check, pain gate intact."""

    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=1000)
        session = await fall(agent)
        await until(lambda: rec.count("notify_contacts") == 1, why="escalate")
        await agent.on_contact_reply("Sarah", "ok")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")

        await heard(agent, "i think i'm alright now")
        await until(lambda: session.phase == "check", why="the reassess jump")
        assert ("contact_engaged", "check") in phase_pairs(session.log)

        # "I'm fine" still goes through the pain double-check before closing.
        await heard(agent, "i'm fine")
        await until(lambda: engine.PAIN_QUESTION in bus.said(), why="the pain double-check")
        await heard(agent, "no")
        await finish(session)
        assert session.state == "closed" and session.final == "ok"
        assert rec.count("call_emergency") == 0

    asyncio.run(scenario())


# --- the comfort loop stays alive, and stays true ---------------------------


def test_comfort_continues_in_contact_engaged(tmp_path) -> None:
    async def scenario() -> None:
        agent, bus, rec = make_agent(tmp_path, timer_scale=0.05, comfort_interval_s=4)
        session = await fall(agent)
        await until(lambda: session.phase == "escalate", why="escalate")
        await agent.on_contact_reply("Sarah", "omw")
        await until(lambda: session.phase == "contact_engaged", why="the engagement")

        await until(
            lambda: any(
                m["prio"] == "comfort" and "Sarah is on the way" in m["text"] for m in bus.says()
            ),
            why="a grounded comfort update naming the engaged contact",
            timeout=6,
        )
        assert rec.count("call_emergency") == 0
        await stop(agent, session)

    asyncio.run(scenario())


# --- the poller: getUpdates parsing, offset, backlog (mock httpx) ----------


class FakeResponse:
    def __init__(self, body) -> None:
        self._body = body

    def json(self):
        return self._body


class FakeClient:
    """Hands out queued getUpdates bodies and records every request."""

    def __init__(self, bodies) -> None:
        self.bodies = list(bodies)
        self.calls: list[dict] = []

    async def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        return FakeResponse(self.bodies.pop(0) if self.bodies else {"ok": True, "result": []})


def update(update_id: int, chat_id: str, text: str) -> dict:
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


CONFIG = {
    "telegram_bot_token": "fake:token",
    "contacts": [{"name": "Sarah", "telegram_chat_id": "555"}],
}


def make_poller(tmp_path, replies: list | None = None, **kwargs):
    async def on_reply(name: str, text: str) -> None:
        (replies if replies is not None else []).append((name, text))

    return telegram_poller.TelegramPoller(
        CONFIG, on_reply, state_path=tmp_path / "offset.json", **kwargs
    )


def test_poller_enabled_gate() -> None:
    """No real token or no real chat id -> the poller must never start."""
    assert telegram_poller.enabled(CONFIG) is True
    assert telegram_poller.enabled({}) is False
    assert telegram_poller.enabled({"telegram_bot_token": "TODO",
                                    "contacts": [{"name": "Sarah", "telegram_chat_id": "555"}]}) is False
    assert telegram_poller.enabled({"telegram_bot_token": "fake:token",
                                    "contacts": [{"name": "Sarah", "telegram_chat_id": "TODO"}]}) is False
    assert telegram_poller.enabled({"telegram_bot_token": "fake:token", "contacts": []}) is False


def test_poller_parses_and_routes_contact_messages(tmp_path) -> None:
    async def scenario() -> None:
        replies: list = []
        poller = make_poller(tmp_path, replies)
        client = FakeClient([{"ok": True, "result": [
            update(70, "555", "ok on my way"),
            update(71, "999", "hello?"),          # not a configured contact
            {"update_id": 72, "message": {"chat": {"id": "555"}}},  # no text (sticker)
        ]}])
        updates = await poller.poll(client, 20)
        for u in updates:
            await poller.handle(u)
        # Only the configured contact's text message routed, mapped to a name.
        assert replies == [("Sarah", "ok on my way")]
        assert poller.offset == 72  # advanced past everything seen

    asyncio.run(scenario())


def test_poller_offset_advances_and_persists(tmp_path) -> None:
    async def scenario() -> None:
        poller = make_poller(tmp_path)
        poller.offset = 100  # as if initialized earlier
        client = FakeClient([{"ok": True, "result": [update(101, "555", "ok")]}])
        await poller.poll(client, 20)
        assert client.calls[0]["params"]["offset"] == 101  # asks past what it has
        assert poller.offset == 101
        poller._save_offset()

        # A restarted poller resumes from disk - no replay of update 101.
        again = make_poller(tmp_path)
        assert again.offset == 101
        client2 = FakeClient([{"ok": True, "result": []}])
        await again.poll(client2, 20)
        assert client2.calls[0]["params"]["offset"] == 102

    asyncio.run(scenario())


def test_poller_first_start_skips_backlog(tmp_path) -> None:
    """CRITICAL: old chat messages must never route into a live session."""

    async def scenario() -> None:
        replies: list = []
        poller = make_poller(tmp_path, replies)
        assert poller.offset is None  # never ran before
        client = FakeClient([
            {"ok": True, "result": [update(40, "555", "hi"), update(41, "555", "test test")]},
            {"ok": True, "result": [update(42, "555", "ok")]},
            {"ok": True, "result": []},
        ])
        await poller.skip_backlog(client)
        assert replies == []            # nothing routed, however ack-shaped
        assert poller.offset == 42      # the high-water mark
        # ...and it survives a restart, so the drain never runs twice.
        assert make_poller(tmp_path).offset == 42

    asyncio.run(scenario())


def test_poller_first_start_with_empty_backlog(tmp_path) -> None:
    async def scenario() -> None:
        poller = make_poller(tmp_path)
        await poller.skip_backlog(FakeClient([{"ok": True, "result": []}]))
        assert poller.offset == 0  # initialized, so the drain never re-runs
        assert make_poller(tmp_path).offset == 0

    asyncio.run(scenario())


def test_poller_survives_api_failure(tmp_path) -> None:
    """A failed or not-ok poll returns None and raises nothing - ears never crash."""

    async def scenario() -> None:
        poller = make_poller(tmp_path)

        class BrokenClient:
            async def get(self, *a, **kw):
                raise OSError("network down")

        assert await poller.poll(BrokenClient(), 20) is None
        assert await poller.poll(FakeClient([{"ok": False}]), 20) is None
        assert await poller.poll(FakeClient(["not a dict"]), 20) is None

    asyncio.run(scenario())
