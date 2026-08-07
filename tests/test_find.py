# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T6.2 - "where's my stuff", end to end in-process (DESIGN.md §13).

Same harness as the fall suite: a fake bus, recorder tools, no broker, no model,
no node. Two halves:

* **the flow** - an ``ask`` becomes a routine session on ``skills/find.md``, the
  search runs, the answer is spoken *in the room the question came from*, and
  the session closes on ``found`` / ``not_found`` / ``done``. Including the row
  of §13's table that actually matters: a node that never answered is named as
  unreached, never quietly counted as "not found".
* **the tool** - ``look_in_rooms`` against a fake fleet of nodes: replies
  collected until the timeout, an early return when everyone has answered, and
  a reply carrying somebody else's ``qid`` ignored outright.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from conftest import StubSpec, fixture, finish, make_agent, until

from qnet.agent import engine
from qnet.tools.look_in_rooms import look_in_rooms

GLASSES = "where are my glasses"
NIGHTSTAND = "on the nightstand"


# --- harness ---------------------------------------------------------------


def looks(replies: list[dict], unreachable: list[str] | None = None, guide: list[dict] | None = None):
    """A ``look_in_rooms`` stub: one canned fleet response per mode, and a call log."""
    calls: list[dict] = []

    async def fake(ctx, object: str, mode: str = "find", room: str | None = None) -> dict:
        calls.append({"object": object, "mode": mode, "room": room})
        if mode == "guide":
            return {"replies": list(guide or []), "unreachable": [], "qid": "q-guide"}
        return {"replies": list(replies), "unreachable": list(unreachable or []), "qid": "q-find"}

    return fake, calls


def find_agent(tmp_path, replies, unreachable=None, guide=None, llm=None, **overrides):
    """An agent whose ``look_in_rooms`` answers with a fixed fleet response."""
    agent, bus, rec = make_agent(tmp_path, llm=llm, **overrides)
    fake, calls = looks(replies, unreachable, guide)
    agent._tools["look_in_rooms"] = StubSpec(fake, engine_only=False)
    return agent, bus, calls


async def ask(agent, text=GLASSES, room="kitchen"):
    """Publish one ``qnet/<room>/ask`` exactly as ``dev/inject.py`` would."""
    msg = fixture("ask_query")
    msg.update({"room": room, "ts": time.time(), "text": text})
    await agent.on_message(f"qnet/{room}/ask", json.dumps(msg).encode())
    return msg


async def search(agent, text=GLASSES, room="kitchen"):
    """One whole find session, start to close."""
    await ask(agent, text, room)
    session = agent.sessions[room]
    await finish(session)
    return session


# --- the flow (§13) --------------------------------------------------------


def test_found_other_room(tmp_path) -> None:
    """The answer names the room it was found in - and is spoken where it was asked."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path,
            replies=[
                {"room": "kitchen", "found": False, "answer": ""},
                {"room": "bedroom", "found": True, "answer": NIGHTSTAND},
            ],
        )
        session = await search(agent)

        # Spoken in the ASKING room, on that room's say topic, and nowhere else.
        assert len(bus.says("kitchen")) == 1
        assert bus.says("bedroom") == []
        answer = bus.said("kitchen")[0]
        assert "bedroom" in answer and NIGHTSTAND in answer
        assert bus.says("kitchen")[0]["prio"] == engine.ROUTINE_PRIO

        # A session like any other - but routine, so it never takes the screen.
        assert session.skill == "find-object"
        assert session.urgency == "routine"
        assert session.final == "found"
        assert session.state == "closed"
        assert bus.sessions()[-1]["urgency"] == "routine"

        # The search itself: one broadcast look for the object the person named.
        assert calls == [{"object": "glasses", "mode": "find", "room": None}]

        # The whole exchange is on disk: the question, the tool, the answer, the exit.
        lines = [json.loads(line) for line in session.path.read_text(encoding="utf-8").splitlines()]
        assert [line["event"] for line in lines] == ["heard", "tool", "say", "phase"]
        assert lines[0]["text"] == GLASSES
        assert lines[-1] == {**lines[-1], "from": "search", "to": "found"}

    asyncio.run(scenario())


def test_found_nowhere(tmp_path) -> None:
    """All rooms answered, none of them saw it - so the answer names them all (§13)."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path,
            replies=[
                {"room": "kitchen", "found": False, "answer": ""},
                {"room": "bedroom", "found": False, "answer": ""},
            ],
        )
        session = await search(agent)

        answer = bus.said("kitchen")[0]
        assert "kitchen" in answer and "bedroom" in answer, answer
        assert "glasses" in answer
        # Nothing about a room it could not reach: it reached them all.
        assert "couldn't reach" not in answer and "could not reach" not in answer
        assert session.final == "not_found"

    asyncio.run(scenario())


def test_one_node_silent(tmp_path) -> None:
    """The row worth building: name what was checked AND what could not be reached."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path,
            replies=[{"room": "kitchen", "found": False, "answer": ""}],
            unreachable=["bedroom"],
        )
        session = await search(agent)

        answer = bus.said("kitchen")[0]
        # "I looked in the kitchen and don't see your glasses - I couldn't reach the bedroom."
        assert "looked in the kitchen" in answer
        assert "couldn't reach the bedroom" in answer
        # The claim order matters: checked first, unreached second, never blurred.
        assert answer.index("kitchen") < answer.index("bedroom")
        assert session.final == "not_found"

    asyncio.run(scenario())


def test_followup_routes_to_guide(tmp_path) -> None:
    """"I still don't see them" inside the window -> guide, remembered object (§13)."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path,
            replies=[
                {"room": "kitchen", "found": False, "answer": ""},
                {"room": "bedroom", "found": True, "answer": NIGHTSTAND},
            ],
            guide=[{"room": "bedroom", "found": True, "answer": "left of the lamp, behind the book"}],
        )
        await search(agent)
        assert agent.last_find["object"] == "glasses"

        # They walked to the bedroom and asked again, naming nothing.
        session = await search(agent, "i still don't see them", room="bedroom")

        # A guide look, at the room they are standing in *now*, for the object
        # they never re-named - one `last_find` variable and one if-statement.
        assert calls == [
            {"object": "glasses", "mode": "find", "room": None},
            {"object": "glasses", "mode": "guide", "room": "bedroom"},
        ]
        assert session.phase == "guide"
        assert session.final == "done"
        assert "left of the lamp" in bus.said("bedroom")[0]
        # ...and the kitchen was not spoken to again.
        assert len(bus.says("kitchen")) == 1

    asyncio.run(scenario())


def test_followup_expired(tmp_path) -> None:
    """Outside the two-minute window there is nothing to guide with - so it asks."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path, replies=[{"room": "bedroom", "found": True, "answer": NIGHTSTAND}]
        )
        await search(agent)
        assert len(calls) == 1

        # Two minutes and a bit later (§13's window, config `find.last_find_window_s`).
        agent.last_find["ts"] -= agent.last_find_window_s + 1
        assert agent.find_is_remembered() is False

        await ask(agent, "i still don't see them", room="bedroom")
        await asyncio.sleep(0.05)

        # No guide, no search, no session - just the question back.
        assert len(calls) == 1, "an expired window must not start a look"
        assert bus.said("bedroom") == [engine.WHAT_TO_FIND]
        assert agent.live_session("bedroom") is None

    asyncio.run(scenario())


def test_new_object_new_search(tmp_path) -> None:
    """An ask that names an object is always a fresh search, window or no window."""

    async def scenario() -> None:
        agent, bus, calls = find_agent(
            tmp_path, replies=[{"room": "kitchen", "found": True, "answer": "on the counter"}]
        )
        await search(agent)
        session = await search(agent, "where is my phone")

        assert calls == [
            {"object": "glasses", "mode": "find", "room": None},
            {"object": "phone", "mode": "find", "room": None},
        ]
        assert session.phase == "search" and session.final == "found"
        assert agent.last_find["object"] == "phone"

    asyncio.run(scenario())


def test_safety_session_still_keeps_the_floor(tmp_path) -> None:
    """T2.2's rule survives the new capability: no search mid-fall (§6)."""

    async def scenario() -> None:
        from conftest import fall, stop

        agent, bus, calls = find_agent(tmp_path, replies=[], comfort_interval_s=1000)
        session = await fall(agent)
        await ask(agent)
        await asyncio.sleep(0.05)

        assert calls == []
        assert agent.sessions["kitchen"] is session and session.skill == "fall-response"
        await stop(agent, session)

    asyncio.run(scenario())


def test_llm_names_the_object_when_the_heuristic_cannot(tmp_path) -> None:
    """The extraction ladder: heuristic -> one model turn -> ask the person (§13)."""

    class Llm:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def extract_object(self, text: str) -> str | None:
            self.seen.append(text)
            return "walking stick"

        def word_line(self, kind, facts, goal="") -> str | None:
            return None  # unusable: the engine words the answer itself

        def classify_reply(self, *a, **kw) -> None:
            return None

    async def scenario() -> None:
        llm = Llm()
        agent, bus, calls = find_agent(
            tmp_path, replies=[{"room": "kitchen", "found": True, "answer": "by the door"}], llm=llm
        )
        session = await search(agent, "my stick has gone walkabout again")

        assert llm.seen == ["my stick has gone walkabout again"]
        assert calls[0]["object"] == "walking stick"
        assert "walking stick" in bus.said("kitchen")[0]
        assert session.final == "found"

    asyncio.run(scenario())


def test_object_heuristic() -> None:
    """The plain-string half of §13's extraction - no model, no network."""
    assert engine.extract_object("where are my glasses") == "glasses"
    assert engine.extract_object("Where is my phone?") == "phone"
    assert engine.extract_object("where's the tv remote") == "tv remote"
    assert engine.extract_object("where did i leave my reading glasses") == "reading glasses"
    assert engine.extract_object("have you seen my keys please") == "keys"
    # User requirement (2026-08-06): everything AFTER the object is noise -
    # a trailing clause must not ride along into the search.
    assert engine.extract_object("where's my glasses i can't find them anywhere") == "glasses"
    assert engine.extract_object("where are my keys please i'm late") == "keys"
    assert engine.extract_object("where is my phone. i need it") == "phone"
    assert engine.extract_object("where's my wallet, i looked everywhere") == "wallet"
    # Compound objects without a clause break still survive intact.
    assert engine.extract_object("where's my water bottle") == "water bottle"
    # "do you see X" - observed live 2026-08-07: this shape missed the
    # heuristic, fell to the 2B model, and the search ran for the object "my".
    assert engine.extract_object("do you see my chair") == "chair"
    assert engine.extract_object("do you find my glasses") == "glasses"
    assert engine.extract_object("do you know where my wallet is") == "wallet"
    # A bare determiner is never a findable object (the live misparse itself).
    assert engine.extract_object("where is my") is None
    # An object-less follow-up names nothing - which is what routes it to guide.
    assert engine.extract_object("i still don't see them") is None
    assert engine.extract_object("where are they") is None
    assert engine.extract_object("") is None


# --- look_in_rooms, against a fake fleet of nodes ---------------------------


class FakeFleet:
    """Nodes that answer a ``qnet/look`` broadcast the way real ones would.

    ``answers`` maps room -> ``(found, answer)``; ``qid`` overrides the echoed
    correlation id for a room, which is how the mismatch case is built.
    """

    def __init__(self, answers: dict, qids: dict | None = None) -> None:
        self.answers, self.qids = answers, qids or {}
        self.published: list[tuple[str, dict]] = []
        self.logged: list[dict] = []
        self.queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, topic: str, payload: dict) -> None:
        self.published.append((topic, payload))
        if topic != "qnet/look":
            return
        for room, (found, answer) in self.answers.items():
            await self.queue.put((
                f"qnet/{room}/looked",
                {"qid": self.qids.get(room, payload["qid"]), "room": room, "found": found, "answer": answer},
            ))

    def subscribe(self, topic_filter: str):
        queue = self.queue

        class _Listen:
            async def __aenter__(self):
                return queue

            async def __aexit__(self, *exc):
                return False

        return _Listen()

    def ctx(self, config: dict):
        from qnet.tools import ToolContext

        return ToolContext(
            room="kitchen",
            session_id="sess-find",
            config=config,
            publish=self.publish,
            log=self.logged.append,
            subscribe=self.subscribe,
        )


CONFIG = {"rooms": {"kitchen": {}, "bedroom": {}}, "find": {"look_timeout_s": 0.4}}


def test_look_in_rooms_collects_replies_and_returns_early() -> None:
    """Everyone answered: the replies come back, and it does not sit out the timeout."""

    async def scenario() -> None:
        fleet = FakeFleet({"kitchen": (False, ""), "bedroom": (True, NIGHTSTAND)})
        config = {"rooms": {"kitchen": {}, "bedroom": {}}, "find": {"look_timeout_s": 5}}

        started = time.monotonic()
        result = await look_in_rooms(fleet.ctx(config), object="glasses", mode="find")
        elapsed = time.monotonic() - started

        assert elapsed < 1.0, "it must not wait out the timeout once every room has answered"
        assert result["unreachable"] == []
        assert {r["room"] for r in result["replies"]} == {"kitchen", "bedroom"}
        found = [r for r in result["replies"] if r["found"]]
        assert found == [{"room": "bedroom", "found": True, "answer": NIGHTSTAND}]

        # One broadcast, on the unqualified topic, carrying the contract's fields.
        assert [topic for topic, _ in fleet.published] == ["qnet/look"]
        payload = fleet.published[0][1]
        assert set(payload) == {"qid", "object", "mode", "room"}
        assert payload["object"] == "glasses" and payload["mode"] == "find" and payload["room"] is None
        assert payload["qid"] == result["qid"]
        assert any(entry.get("tool") == "look_in_rooms" for entry in fleet.logged)

    asyncio.run(scenario())


def test_look_in_rooms_ignores_a_mismatched_qid() -> None:
    """A reply echoing somebody else's qid is not an answer to this question."""

    async def scenario() -> None:
        fleet = FakeFleet(
            {"kitchen": (False, ""), "bedroom": (True, NIGHTSTAND)},
            qids={"bedroom": "an-older-question"},
        )
        result = await look_in_rooms(fleet.ctx(CONFIG), object="glasses", mode="find")

        assert [r["room"] for r in result["replies"]] == ["kitchen"]
        assert result["unreachable"] == ["bedroom"], "a stale answer must not count as a reply"

    asyncio.run(scenario())


def test_look_in_rooms_reports_the_silent_room() -> None:
    """A node that never answers is `unreachable`, not "looked and saw nothing"."""

    async def scenario() -> None:
        fleet = FakeFleet({"kitchen": (False, "")})
        started = time.monotonic()
        result = await look_in_rooms(fleet.ctx(CONFIG), object="glasses", mode="find")

        assert time.monotonic() - started == pytest.approx(0.4, abs=0.35)
        assert [r["room"] for r in result["replies"]] == ["kitchen"]
        assert result["unreachable"] == ["bedroom"]

    asyncio.run(scenario())


def test_look_in_rooms_guide_targets_one_room() -> None:
    """`guide` asks the room the person is standing in, and expects only that one."""

    async def scenario() -> None:
        fleet = FakeFleet({"bedroom": (True, "left of the lamp")})
        result = await look_in_rooms(fleet.ctx(CONFIG), object="glasses", mode="guide", room="bedroom")

        assert fleet.published[0][1]["room"] == "bedroom"
        assert fleet.published[0][1]["mode"] == "guide"
        assert result["unreachable"] == []
        assert result["replies"][0]["answer"] == "left of the lamp"

    asyncio.run(scenario())


def test_engine_hears_looked_replies(tmp_path) -> None:
    """The real tool, driven by the real engine: `subscribe` carries the replies.

    No stubbed fleet here - ``Agent.subscribe`` fans the bus's own ``looked``
    messages out to the tool that is waiting on them, which is the one piece of
    plumbing T6.2 added to ``ToolContext``.
    """

    async def scenario() -> None:
        agent, bus, _rec = make_agent(
            tmp_path,
            rooms={"kitchen": {}, "bedroom": {}},
            find={"look_timeout_s": 3},
        )
        agent._tools["look_in_rooms"] = StubSpec(look_in_rooms, engine_only=False)

        await ask(agent)
        session = agent.sessions["kitchen"]
        await until(lambda: bus.on("qnet/look"), why="the look broadcast")
        qid = bus.on("qnet/look")[0]["qid"]

        for room, found, answer in (("kitchen", False, ""), ("bedroom", True, NIGHTSTAND)):
            reply = {"qid": qid, "room": room, "found": found, "answer": answer}
            await agent.on_message(f"qnet/{room}/looked", json.dumps(reply).encode())

        await finish(session, timeout=5)
        assert session.final == "found"
        assert NIGHTSTAND in bus.said("kitchen")[0]
        assert agent._listeners == [], "the listener must be released when the search ends"

    asyncio.run(scenario())


def test_unknown_room_traffic_is_dropped(tmp_path) -> None:
    """A coexisting stack on the shared broker publishes STT chatter under
    rooms this house never configured - observed live, 60 junk sessions.
    Configured houses drop unknown-room event/ask/heard outright."""
    import asyncio

    async def run() -> None:
        agent, _bus, _calls = find_agent(tmp_path, replies=[], rooms={"kitchen": {}, "bedroom": {}})
        await agent.on_message(
            "qnet/living-room/ask",
            b'{"id": "01X", "ts": 1.0, "room": "living-room", "text": "where is my sanity", "kind": "query"}',
        )
        assert agent.sessions.get("living-room") is None

    asyncio.run(run())
