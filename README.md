# QNet-Home
QNet Home is a proactive home guardian that identifies falls, crises, and risks in real time.

The current hackathon build implements only **elder fall response** and **Find My** (spectacles in the demo). OpenClaw provides the use-case plug-in layer; safety-critical timing and escalation remain deterministic QNet platform services. Child care is only a future extension example, not part of implementation or demo scope.

## Current design documents

- [System design](docs/DESIGN.md) — authoritative product architecture and behavior.
- [Implementation plan](docs/IMPLEMENTATION.md) — ordered tasks and runnable gates.
- [MQTT wire contract](contracts/mqtt.md) — authoritative topics, QoS, payload fields, and compatibility policy.
- [Arduino speech contract](contracts/arduino-speech.md) — verified App CLI ASR/TTS/VAD lifecycle and half-duplex requirements.
- `contracts/fixtures/` — the eight canonical MQTT sample payloads used by tests and future components.

## Implemented Phase-1 runtime

The repository now includes an executable first version of the QHome room-voice
fabric:

- `apps/ventuno-q/qhome-voice-node` is one Arduino App containing ASR, TTS,
  MQTT, continuous rolling transcription, playback deduplication, and a status UI.
- `services/iq9_voice_router` is the deterministic announcement fallback and routes all,
  group, device, and replay announcements.
- `agent/engine.py` opens one safety session per room for a fall, publishes the
  hardcoded first check, mirrors session events to MQTT and one JSONL file, and
  records room replies. It deliberately has no LLM or escalation timers yet.
- `dev/inject.py` publishes canonical fall and ask fixtures for development.
- `infra/mosquitto.conf` exposes MQTT on `1883` and MQTT-over-WebSocket on
  `9001`; the native aMQTT deployment exposes both listeners too.
- `deploy/iq9-native` is the current IQ9 broker/router deployment; `deploy/iq9`
  remains an optional Docker/Mosquitto deployment.
- `config/home.example.yaml` maps spoken room aliases to stable node IDs.
- `config/inventory.example.yaml` records the IQ9 and deployed Ventuno addresses
  without storing passwords; bedroom voice settings live in
  `config/voice-nodes/ventuno-bedroom.json`.
- `config/house.example.yaml` and `config/node.example.yaml` freeze the future
  agent and room-node configuration shapes.
- `scripts/` contains deployment and MQTT/TTS smoke-test helpers.

Run the host-side contract tests with:

```sh
pytest -q tests
```

All Phase-1 host acceptance tests currently pass.

## Run Phase 1 on IQ9

Copy every IQ9 runtime package; `agent/` is required in addition to the older
`services/`, `config/`, and `deploy/` directories:

```sh
cd /Users/munibhavanakonidala/Desktop/hackathon/QNet-Home
rsync -az agent dev contracts services config deploy ubuntu@10.73.51.175:~/QNet-Home/
ssh ubuntu@10.73.51.175
cd ~/QNet-Home
./deploy/iq9-native/setup.sh
./deploy/iq9-native/stop.sh
./deploy/iq9-native/start.sh
./deploy/iq9-native/status.sh
```

`setup.sh` creates `.venv-iq9` and installs paho-mqtt, PyYAML, and aMQTT.
`start.sh` starts one supervisor process which opens ports `1883` and `9001`,
then starts both the Phase-1 agent and deterministic announcement router.

## Run Phase 1 on a Ventuno Q

The device-local `qhome-config.json` must name a unique node/room and point to
the IQ9. Existing installs can keep old unknown keys; Phase 1 defaults the new
VAD sentence timeouts and 500 ms post-TTS guard.

```sh
./scripts/deploy_voice_node.sh 10.73.51.123
ssh arduino@10.73.51.123
arduino-app-cli app stop /home/arduino/ArduinoApps/qhome-voice-node
arduino-app-cli app start /home/arduino/ArduinoApps/qhome-voice-node
arduino-app-cli app logs /home/arduino/ArduinoApps/qhome-voice-node --tail 80
```

App CLI reads `app.yaml`, provisions the `arduino:asr`, `arduino:tts`, and
`arduino:web_ui` bricks/models, then runs `python/main.py`. The combined App is
the only microphone/speaker owner. Its status page is
`http://<ventuno-ip>:7000/`, with JSON at `/api/status`.

The deployed nodes select unquantized Whisper Small with
`"asr_model": "whisper-small"` in `qhome-config.json`. Model installation and
rollback are documented in `contracts/arduino-speech.md`; the repeatable
installer is `scripts/install_whisper_voice_ai_model.sh`.

## Test the Phase-1 fall loop

Watch the wire on IQ9, then inject a fall from another terminal:

```sh
./.venv-iq9/bin/amqtt_sub --url mqtt://127.0.0.1:1883 --topic 'qnet/#' --qos 1
./.venv-iq9/bin/python dev/inject.py --host 127.0.0.1 fall --room living-room
```

Expected result: IQ9 publishes a safety `say`; the living-room Ventuno cancels
ASR if necessary and says “I saw you fall. Are you okay?”; its next
VAD-ended sentence (or timeout) is published on `qnet/living-room/heard`; IQ9
appends that reply under `.runtime/sessions/`. To test TTS alone:

```sh
./scripts/smoke_voice_node.sh 10.73.51.175 living-room
```
