"""Phase-1 safety-session skeleton: fall event in, spoken check and log out."""

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


LOGGER = logging.getLogger("qnet.agent")
Publish = Callable[[str, dict[str, Any], int, bool], None]
OPENING = "I saw you fall. Are you okay?"


def _decode(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        data = payload
    else:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def _required(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected) or (expected is str and not value.strip()):
        raise ValueError(f"{key} must be {expected.__name__}")
    return value


def _timestamp(data: dict[str, Any]) -> float:
    value = data.get("ts")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("ts must be numeric")
    return float(value)


@dataclass
class Session:
    session_id: str
    room: str
    path: Path
    phase: str = "check"
    state: str = "active"
    urgency: str = "safety"


class AgentEngine:
    """Deterministic G1 engine with no LLM and no timers yet."""

    def __init__(self, publish: Publish, sessions_dir: str | Path):
        self.publish = publish
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: dict[str, Session] = {}

    def on_message(self, topic: str, payload: bytes | str | dict[str, Any]) -> str | None:
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != "qnet":
            raise ValueError("unsupported topic")
        room, message_type = parts[1], parts[2]
        data = _decode(payload)
        if data.get("room") != room:
            raise ValueError("payload room does not match topic room")
        if message_type == "event":
            return self._on_event(room, data)
        if message_type == "heard":
            return self._on_heard(room, data)
        if message_type == "ask":
            return self._on_ask(room, data)
        raise ValueError("unsupported topic")

    def _on_event(self, room: str, data: dict[str, Any]) -> str:
        _required(data, "id", str)
        _timestamp(data)
        _required(data, "meta", dict)
        if data.get("kind") != "fall.detected":
            raise ValueError("unsupported event kind")
        confidence = data.get("conf")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("conf must be numeric")
        if not 0 <= confidence <= 1:
            raise ValueError("conf must be between 0 and 1")
        if room in self.active_sessions:
            return "ignored-active-session"

        session_id = f"fall-{uuid.uuid4()}"
        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        path = self.sessions_dir / f"{room}__fall-response__{started_at}.jsonl"
        session = Session(session_id, room, path)
        self.active_sessions[room] = session
        self._emit(
            session,
            "detected",
            {"kind": "fall.detected", "conf": float(confidence), "source_event_id": data["id"]},
        )
        say = {
            "id": f"say-{uuid.uuid4()}",
            "ts": time.time(),
            "room": room,
            "text": OPENING,
            "prio": "safety",
        }
        self.publish(f"qnet/{room}/say", say, 1, False)
        self._emit(session, "say", {"text": OPENING, "say_id": say["id"]})
        return session_id

    def _on_heard(self, room: str, data: dict[str, Any]) -> str:
        session = self.active_sessions.get(room)
        if session is None:
            return "ignored-no-session"
        _required(data, "id", str)
        _timestamp(data)
        text = data.get("text")
        silence = data.get("silence")
        if not isinstance(text, str) or not isinstance(silence, bool):
            raise ValueError("heard requires text and silence")
        if silence != (text.strip() == ""):
            raise ValueError("heard text and silence disagree")
        self._emit(session, "heard", {"text": text.strip(), "silence": silence})
        return session.session_id

    def _on_ask(self, room: str, data: dict[str, Any]) -> str:
        _required(data, "id", str)
        _timestamp(data)
        kind = data.get("kind")
        text = data.get("text")
        if not isinstance(text, str):
            raise ValueError("text must be str")
        if kind == "responder_brief":
            if text != "":
                raise ValueError("responder_brief text must be empty")
            # Deliberately exempt from the session table; Phase 6 supplies content.
            return "responder-brief-exempt"
        if room in self.active_sessions:
            return "ignored-safety-session"
        if kind != "query" or not text.strip():
            raise ValueError("query text must be non-empty")
        return "unhandled-query"

    def _emit(self, session: Session, event: str, data: dict[str, Any]) -> None:
        record = {
            "id": session.session_id,
            "ts": time.time(),
            "room": session.room,
            "skill": "fall-response",
            "urgency": session.urgency,
            "phase": session.phase,
            "state": session.state,
            "event": event,
            "data": data,
        }
        with session.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.publish(f"qnet/session/{session.session_id}", record, 1, False)


def main() -> None:
    import paho.mqtt.client as mqtt

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    host = os.getenv("QNET_MQTT_HOST", "127.0.0.1")
    port = int(os.getenv("QNET_MQTT_PORT", "1883"))
    sessions_dir = os.getenv("QNET_SESSIONS_DIR", "data/sessions")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qnet-iq9-agent")

    def publish(topic: str, payload: dict[str, Any], qos: int, retain: bool) -> None:
        result = client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish to {topic} failed with rc={result.rc}")

    engine = AgentEngine(publish, sessions_dir)

    def on_connect(_client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code != 0:
            LOGGER.error("MQTT connection failed: %s", reason_code)
            return
        for topic in ("qnet/+/event", "qnet/+/heard", "qnet/+/ask"):
            _client.subscribe(topic, qos=1)
        LOGGER.info("Phase-1 agent connected to %s:%s", host, port)

    def on_message(_client, _userdata, message) -> None:
        try:
            outcome = engine.on_message(message.topic, message.payload)
            LOGGER.info("Handled %s: %s", message.topic, outcome)
        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            LOGGER.warning("Rejected %s: %s", message.topic, exc)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
