# QNet Home

A privacy-first home system built on one event fabric, with capabilities added as pluggable skills. Rooms sense and speak locally; devices exchange small semantic JSON events over MQTT — never video, never audio.

Two capabilities so far. **Fall response:** when someone falls, the room notices, asks if they're alright, listens, and escalates — reassurance out loud, a Telegram to a trusted contact, an emergency call if there's still no answer — narrating each step so the person is never left in silence. A first responder walking in can ask *"I'm the first responder, what happened?"* and get a spoken timeline. **Where's my stuff:** say *"Hey Home, where are my glasses?"* and every room checks its own camera with an on-device VLM; only text crosses the wire, and the answer is spoken in the room you asked from.

> **Status: running on real hardware.** Built for the Snapdragon Multiverse hackathon (August 3–7, 2026). Both capabilities work end-to-end on the boards today: NPU fall detection → escalation ladder → real Telegram (with a 30 s trusted-contact reply window before the *simulated* emergency call), and camera-verified "where's my stuff" via an on-node VLM. The one stand-in: audio — until the speech service lands, a flagged dashboard composer types what a person would have said, over the identical wire messages. Design: `docs/DESIGN.md` · plan/status: `docs/IMPLEMENTATION.md` · demo script: `docs/DEMO.md` · per-task evidence: `verify/`.

## How it works

Each device does the one job only it can do:

| Device | Role | Responsibility |
| --- | --- | --- |
| Arduino Ventuno Q (per room; one live today) | Room node | Fall detection (YOLOv11 fine-tune on the Hexagon NPU) always on; Qwen3-VL for "do you see X" lookups; STT/TTS via an on-board speech service (in progress). Raw frames and audio never leave the node. |
| Qualcomm IQ-9075 | The brain | Mosquitto broker + the agent: Gemma 4 E2B on the Hexagon NPU (via GenieX) runs the conversation inside engine-enforced rails — timers, notifications, and the emergency path fire automatically and never depend on the model. |
| Snapdragon X Elite laptop | Dashboard | Floor-plan view with live camera health and previews, a chat-style activity feed, and an incident banner with one-click real resolve; packaged as the Windows app. |
| Phone | Trusted contact | Two-way Telegram: milestone messages naming the room, and a reply window — answer "OK" to claim an incident before the (simulated) emergency call, or "call 911" to trigger it instantly. |

**Design principles**

- **The agent runs the conversation; the engine guarantees what must not fail.** Timers, contact notifications, and the emergency call are automatic — a slow or wrong model can only ever make the chit-chat worse, never the response.
- **Privacy by construction.** Nodes publish semantic JSON, not media; the "find my stuff" VLM answers in words from inside the room.
- **Skills are data.** Each capability is a markdown file of phases and guidance; adding one touches no engine code.
- **Measured, not asserted.** Numbers are tagged measured vs. unmeasured, and unmeasured ones don't get claimed.

## Repository layout

```
README.md      this file
LICENSE        GNU AGPL-3.0
docs/          DESIGN.md (the spec) · IMPLEMENTATION.md (plan + status) · DEMO.md (run of show)
qnet/          the code: agent/ (engine, LLM client, Telegram poller), node/ (vision,
               look, stream), tools/ (notify, call, summary, look_in_rooms), app.py
skills/        fall.md · find.md · responder-brief.md — capabilities as data
contracts/     the frozen MQTT wire contract + one fixture per message type
dashboard/     index.html (the product page) · admin.html (the technical portal)
dev/           laptop harness: broker, injector, room simulator, spy, session replay
infra/         mosquitto.conf + systemd units for all six services
packaging/     Windows ARM64 exe + signed MSIX build scripts
scripts/       deploy scripts + demo_fallback.sh (the no-model G2 build, one command)
tests/         130+ hermetic tests (no hardware, no network)
verify/        evidence per task — command output, measurements, postmortems
setup/         device bring-up runbooks (IQ-9075 Gemma/GenieX, Ventuno VLM container)
models/        fall model artifacts + NPU compile runbook (main branch)
```

## Setup

**Try it with zero hardware first** (any machine with Python 3.12):

```
python -m venv .venv && .venv/Scripts/pip install aiomqtt amqtt httpx pyyaml openai paho-mqtt pytest
.venv/Scripts/python -m pytest -q            # the hermetic suite
bash scripts/demo_fallback.sh                # the full fall ladder, local broker, no model
```

Then open `dashboard/index.html` in a browser, point ⚙ Settings at `ws://127.0.0.1:9001/mqtt`, run `python dev/broker.py`, and drive the house with `dev/inject.py` / the Settings-flagged typed-voice composer.

**The real deployment** (what the demo runs):

1. **IQ-9075 (the brain):** Gemma 4 E2B via GenieX — runbook in `setup/iq9-gemma-geniex/`. Mosquitto with `infra/mosquitto.conf`. Ship the repo tree + a venv, add `config/house.local.yaml` (Telegram bot token, contact chat ids, `mqtt: {host: 127.0.0.1, port: 11883}` — this file is secret and board-specific, never committed), install `infra/systemd/qnet-agent.service`.
2. **Ventuno Q (a room node):** compile the fall model for the board's Hexagon arch (full recipe incl. the AI Hub device-catalog workaround: `models/fall-detection/README.md`); start the Qualcomm VLM container serving Qwen3-VL on `:9001` (`setup/ventuno-vlm/`); deploy `qnet/node/` with `scripts/deploy_vision_ventuno.sh` / `deploy_look_ventuno.sh`; install the three units (`qnet-vision`, `qnet-look`, `qnet-stream`).
3. **Laptop (the dashboard):** `packaging/build.ps1` → `packaging/make_msix.ps1` for the installable app, or just open `dashboard/index.html`. Certificate trust steps: `packaging/SIGNING.md`.
4. **Phone:** create a Telegram bot via @BotFather, have each trusted contact press Start on it once, put the token + chat ids in `config/house.local.yaml`.

Every service is systemd: boards power-cycle back to a working house with no keystrokes.

## Usage

- **Watch:** the dashboard shows the house as a floor plan — rooms tint with their state, a breathing green dot per camera proves it's live (fps from the node's heartbeat), click a room for its LAN-only camera preview.
- **A fall** (real, or `python dev/inject.py fall --room kitchen`): the room asks aloud, silence escalates — the trusted contacts' phones get *"Reply OK if you can check on Tony — otherwise I'll call emergency services in 30 seconds"*; an `ok` reply holds the (simulated) call and tells Tony who's coming; no reply places it. Cancel any time with "false alarm" — typed, spoken (when speech lands), or the banner's **Mark resolved**.
- **Find things:** `hey home, where are my glasses` (composer or, later, voice) — every room's camera looks via its own on-device VLM and the asking room hears the answer with a landmark ("on the counter, next to the kettle"), or an honest miss naming what was actually checked.
- **First responder:** *"I'm the first responder, what happened?"* → a grounded timeline from the session log.
- **Admin portal** (link in Settings): every message, timing, and a raw wire log.

The full presentation script, timer pacing, and the honest real-vs-simulated card: `docs/DEMO.md`.

## Team

| Name | Email |
| --- | --- |
| Gaurav Mehta | gkmphx@gmail.com |
| Munibhavana Konidala | konidalamunibhavana@gmail.com |
| Amrutha Sai Gattu | amruthsai16@gmail.com |

## License

**GNU Affero General Public License v3.0** — see [`LICENSE`](LICENSE).

QNet Home uses [`melihuzunoglu/human-fall-detection`](https://huggingface.co/melihuzunoglu/human-fall-detection), a YOLOv11 fine-tune carrying Ultralytics' AGPL-3.0 terms. AGPL is strong copyleft, so the project as a whole is released under the same licence.

```
QNet Home — a privacy-first, multi-device home safety system
Copyright (C) 2026 QNet Home contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
