# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T2.3 - the tool registry (DESIGN.md §11).

No network: the one test that would hit Telegram monkeypatches ``httpx`` with
a fake client instead. No ``pytest-asyncio`` dependency either - every async
tool call is driven with a tiny ``run()`` helper over ``asyncio.run``, which is
all a single awaited coroutine needs.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import httpx
import pytest

import qnet.tools.call_emergency as call_emergency_mod
import qnet.tools.get_session_summary as summary_mod
import qnet.tools.notify_contacts as notify_mod
from qnet.tools import TOOLS, ToolContext, console_print
from qnet.tools.call_emergency import call_emergency
from qnet.tools.get_session_summary import get_session_summary
from qnet.tools.look_in_rooms import look_in_rooms
from qnet.tools.notify_contacts import notify_contacts

CONFIG_TODO = {
    "resident": {"name": "Margaret"},
    "contacts": [{"name": "Sarah", "telegram_chat_id": "TODO"}],
    "telegram_bot_token": "TODO",
    "emergency_number": "911",
    "rooms": {"kitchen": {}, "bedroom": {}},
}

CONFIG_REAL_CREDS = {
    "resident": {"name": "Margaret"},
    "contacts": [{"name": "Sarah", "telegram_chat_id": "555"}],
    "telegram_bot_token": "faketoken",
    "emergency_number": "911",
    "rooms": {"kitchen": {}, "bedroom": {}},
}


def run(coro):
    return asyncio.run(coro)


def make_ctx(config, room="kitchen", session_id="sess-1", logged=None, published=None):
    logged = logged if logged is not None else []
    published = published if published is not None else []

    async def publish(topic, payload):
        published.append((topic, payload))

    def log(event):
        logged.append(event)

    return ToolContext(room=room, session_id=session_id, config=config, publish=publish, log=log)


# --- notify_contacts ------------------------------------------------------


def test_notify_message_contains_room(tmp_path, monkeypatch):
    monkeypatch.setattr(notify_mod, "OUTBOX", tmp_path / "telegram.log")
    ctx = make_ctx(CONFIG_TODO, room="kitchen")

    result = run(notify_contacts(ctx, kind="escalate"))

    assert "kitchen" in result["text"]
    assert "Margaret" in result["text"]
    assert result["channel"] in {"telegram", "console"}


def test_notify_console_fallback_when_todo_creds(tmp_path, monkeypatch):
    outbox = tmp_path / "telegram.log"
    monkeypatch.setattr(notify_mod, "OUTBOX", outbox)
    ctx = make_ctx(CONFIG_TODO, room="bedroom")

    result = run(notify_contacts(ctx, kind="call_help"))

    assert result["delivered"] is False
    assert result["channel"] == "console"
    assert "bedroom" in result["text"]
    # The message is still recorded, even with no real credentials.
    assert outbox.exists()
    lines = outbox.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "call_help"
    assert "ts" in entry and "text" in entry


def test_notify_false_alarm_message(tmp_path, monkeypatch):
    monkeypatch.setattr(notify_mod, "OUTBOX", tmp_path / "telegram.log")
    ctx = make_ctx(CONFIG_TODO, room="kitchen")

    result = run(notify_contacts(ctx, kind="false_alarm"))

    assert "confirmed they're okay" in result["text"]
    assert "kitchen" in result["text"]


def test_notify_delivers_via_telegram_with_real_creds(tmp_path, monkeypatch):
    """Monkeypatch httpx.AsyncClient - no real network call, per the no-network rule."""
    monkeypatch.setattr(notify_mod, "OUTBOX", tmp_path / "telegram.log")

    calls = []

    class FakeResponse:
        status_code = 200

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, data=None, timeout=None):
            calls.append((url, data, timeout))
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    ctx = make_ctx(CONFIG_REAL_CREDS, room="kitchen")
    result = run(notify_contacts(ctx, kind="escalate"))

    assert result["delivered"] is True
    assert result["channel"] == "telegram"
    assert len(calls) == 1
    url, data, timeout = calls[0]
    assert "faketoken" in url
    assert data["chat_id"] == "555"
    assert timeout == 5.0


def test_notify_never_raises_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(notify_mod, "OUTBOX", tmp_path / "telegram.log")

    class FailingAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **kw):
            raise httpx.ConnectTimeout("no route to host")

    monkeypatch.setattr(httpx, "AsyncClient", FailingAsyncClient)

    ctx = make_ctx(CONFIG_REAL_CREDS, room="kitchen")
    result = run(notify_contacts(ctx, kind="escalate"))  # must not raise

    assert result["delivered"] is False
    assert result["channel"] == "console"


# --- call_emergency ---------------------------------------------------------


def test_call_emergency_payload_marked_simulated(tmp_path, monkeypatch):
    monkeypatch.setattr(call_emergency_mod, "OUTBOX_DIR", tmp_path)
    logged = []
    ctx = make_ctx(CONFIG_TODO, room="kitchen", session_id="sess-42", logged=logged)

    result = run(call_emergency(ctx))

    # Returned dict is marked SIMULATED.
    assert result["SIMULATED"] is True
    assert result["room"] == "kitchen"
    assert result["session_id"] == "sess-42"
    assert result["reason"] == "no_response_after_escalation"
    assert result["number"] == "911"

    # Exactly one file written, and its content also carries SIMULATED.
    written = list(tmp_path.glob("emergency_*.json"))
    assert len(written) == 1
    on_disk = json.loads(written[0].read_text(encoding="utf-8"))
    assert on_disk["SIMULATED"] is True
    assert on_disk == result

    # The engine's session log heard about it too.
    assert any(e.get("tool") == "call_emergency" for e in logged)


def test_call_emergency_never_raises_if_outbox_unwritable(monkeypatch):
    # Point OUTBOX_DIR at a path that can't be a directory (a file in its place).
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as f:
        bad_dir = Path(f.name)
    monkeypatch.setattr(call_emergency_mod, "OUTBOX_DIR", bad_dir / "nested")

    ctx = make_ctx(CONFIG_TODO, room="kitchen")
    result = run(call_emergency(ctx))  # must not raise despite the bad path

    assert result["SIMULATED"] is True


# --- get_session_summary -----------------------------------------------------


def write_session_file(sessions_dir: Path, room: str, stamp: str, lines: list[dict]) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{room}__fall-response__{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line) + "\n")
    return path


def test_get_session_summary_reads_latest_file(tmp_path):
    sessions_dir = tmp_path / "sessions"

    write_session_file(
        sessions_dir,
        "kitchen",
        "2026-08-01T10-00-00",
        [
            {"ts": 100.0, "event": "detected", "kind": "fall.detected", "conf": 0.9},
            {"ts": 100.1, "event": "say", "text": "old session opening"},
        ],
    )
    # The later file - later start-time stamp in the filename - must win.
    latest_lines = [
        {"ts": 200.0, "event": "detected", "kind": "fall.detected", "conf": 0.87},
        {"ts": 200.1, "event": "say", "text": "I saw you fall. Take a breath — are you okay?"},
        {"ts": 205.6, "event": "heard", "text": "", "silence": True},
        {"ts": 206.0, "event": "phase", "from": "check", "to": "escalate"},
        {"ts": 206.3, "event": "tool", "tool": "notify_contacts", "result": "sent"},
    ]
    write_session_file(sessions_dir, "kitchen", "2026-08-01T10-05-00", latest_lines)

    config = {"storage": {"sessions_dir": str(sessions_dir)}}
    ctx = make_ctx(config, room="kitchen")

    result = run(get_session_summary(ctx))

    assert result.get("no_history") is None
    assert result["file"].endswith("10-05-00.jsonl")
    assert result["started_at"] == 200.0
    assert result["phase"] == "escalate"
    assert result["state"] == "active"  # mid-flow, not yet terminal
    assert result["elapsed_s"] == pytest.approx(6.3, abs=0.01)

    # Events are ordered, and each carries a humanized offset.
    events = result["events"]
    assert [e["event"] for e in events] == ["detected", "say", "heard", "phase", "tool"]
    assert [e["ts"] for e in events] == sorted(e["ts"] for e in events)
    assert events[0]["offset_s"] == 0.0
    assert events[2]["offset_s"] == pytest.approx(5.6, abs=0.01)
    assert "offset_human" in events[0]

    # The old session's content must not leak in.
    assert not any("old session opening" == e.get("text") for e in events)


def test_get_session_summary_terminal_state(tmp_path):
    sessions_dir = tmp_path / "sessions"
    write_session_file(
        sessions_dir,
        "kitchen",
        "2026-08-01T09-00-00",
        [
            {"ts": 10.0, "event": "detected", "kind": "fall.detected", "conf": 0.9},
            {"ts": 10.1, "event": "say", "text": "opening"},
            {"ts": 40.0, "event": "phase", "from": "check", "to": "ok"},
        ],
    )
    config = {"storage": {"sessions_dir": str(sessions_dir)}}
    ctx = make_ctx(config, room="kitchen")

    result = run(get_session_summary(ctx))

    assert result["phase"] == "ok"
    assert result["state"] == "ok"


def test_get_session_summary_no_history(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    config = {"storage": {"sessions_dir": str(sessions_dir)}}
    ctx = make_ctx(config, room="bedroom")

    result = run(get_session_summary(ctx))

    assert result == {"no_history": True, "room": "bedroom"}


def test_get_session_summary_live_mid_write(tmp_path):
    """Reads whatever is on disk right now - no 'finalize the log' step (DESIGN §12)."""
    sessions_dir = tmp_path / "sessions"
    path = write_session_file(
        sessions_dir,
        "kitchen",
        "2026-08-01T11-00-00",
        [{"ts": 50.0, "event": "detected", "kind": "fall.detected", "conf": 0.9}],
    )
    config = {"storage": {"sessions_dir": str(sessions_dir)}}
    ctx = make_ctx(config, room="kitchen")

    first = run(get_session_summary(ctx))
    assert len(first["events"]) == 1

    # Simulate the session still being written to.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": 50.1, "event": "say", "text": "are you okay"}) + "\n")

    second = run(get_session_summary(ctx))
    assert len(second["events"]) == 2


# --- console_print (Windows cp1252 console safety) --------------------------


def test_console_print_never_raises_on_narrow_console(monkeypatch):
    """Simulates a Windows cp1252 console, which can't encode the Telegram emoji."""

    class NarrowStream:
        def write(self, s):
            s.encode("cp1252")  # raises UnicodeEncodeError on emoji, like the real console
            return len(s)

        def flush(self):
            pass

    monkeypatch.setattr("sys.stdout", NarrowStream())
    console_print("\U0001F534 Possible fall — Margaret, kitchen.")  # must not raise


# --- registry ---------------------------------------------------------------


def test_registry_engine_only_flags():
    assert TOOLS["notify_contacts"].engine_only is True
    assert TOOLS["call_emergency"].engine_only is True
    assert TOOLS["get_session_summary"].engine_only is False
    assert TOOLS["look_in_rooms"].engine_only is False


def test_all_tools_async_and_registered():
    expected = {"notify_contacts", "call_emergency", "get_session_summary", "look_in_rooms"}
    assert expected <= set(TOOLS)
    for name, spec in TOOLS.items():
        assert inspect.iscoroutinefunction(spec.fn), f"{name} must be an async fn"


# --- look_in_rooms (stub) ----------------------------------------------------


def test_look_in_rooms_stub_shape():
    config = {"rooms": {"kitchen": {}, "bedroom": {}}}
    logged = []
    ctx = make_ctx(config, room="kitchen", logged=logged)

    result = run(look_in_rooms(ctx, object="glasses", mode="find"))

    assert result["stub"] is True
    assert result["replies"] == []
    assert set(result["unreachable"]) == {"kitchen", "bedroom"}
    assert any(e.get("tool") == "look_in_rooms" for e in logged)
