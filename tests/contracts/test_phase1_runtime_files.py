# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_broker_configs_expose_tcp_and_websocket() -> None:
    for relative in ("infra/mosquitto.conf", "deploy/iq9/mosquitto/mosquitto.conf"):
        config = (ROOT / relative).read_text(encoding="utf-8")
        assert "listener 1883" in config
        assert "listener 9001" in config
        assert "protocol websockets" in config
    native = (ROOT / "services/iq9_native/main.py").read_text(encoding="utf-8")
    assert '"type": "ws"' in native
    assert "QHOME_MQTT_WEBSOCKET_PORT" in native


def test_deployments_include_phase1_agent() -> None:
    native = (ROOT / "services/iq9_native/main.py").read_text(encoding="utf-8")
    compose = (ROOT / "deploy/iq9/docker-compose.yaml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "services/iq9_voice_router/Dockerfile").read_text(encoding="utf-8")
    assert '"agent.engine"' in native
    assert "agent:" in compose and '"agent.engine"' in compose
    assert "COPY agent /app/agent" in dockerfile


def test_status_ui_uses_arduino_exposed_path() -> None:
    javascript = (
        ROOT / "apps/ventuno-q/qhome-voice-node/assets/app.js"
    ).read_text(encoding="utf-8")
    assert "fetch('/api/status'" in javascript
