# QNet Home

A privacy-first home safety system built on one event fabric, with capabilities added as pluggable skills. Rooms sense and speak locally; devices exchange small semantic JSON events over MQTT — never video, never audio.

Two capabilities ship today:

- **Fall response.** When someone falls, the room notices, asks if they're alright, listens, and escalates — reassurance out loud, a Telegram to a trusted contact, an emergency call if there's still no answer — narrating each step so the person is never left in silence. A first responder walking in can say *"I'm the first responder, what happened?"* and get a spoken handover.
- **Where's my stuff.** Say *"Hey Home, where are my glasses?"* and every room checks its own camera with an on-device VLM; only text crosses the wire, and the answer is spoken in the room you asked from.

> **Status: running on real hardware, end to end.** Built for the Snapdragon Multiverse hackathon (August 3–7, 2026). NPU fall detection → spoken conversation (on-device Whisper ASR + TTS) → escalation ladder → real two-way Telegram → *simulated* emergency call, and camera-verified "where's my stuff" across two rooms. Design: [`docs/DESIGN.md`](docs/DESIGN.md) · plan + status: [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) · demo script: [`docs/DEMO.md`](docs/DEMO.md) · measured numbers: [`measurements.md`](measurements.md) · per-task evidence: [`verify/`](verify/).

## How it works

Each device does the one job only it can do:

| Device | Role | Responsibility |
| --- | --- | --- |
| Arduino UNO Q ("Ventuno Q"), one per room | Room node | Fall detection (YOLO11 fine-tune on the Hexagon NPU) always on; Qwen VLM for "do you see X" lookups; wake-gated voice — Whisper-small ASR on the NPU + TTS. Raw frames and audio never leave the node; only wake-matched, stripped text is published. |
| Qualcomm IQ-9075 EVK | The hub ("brain") | Mosquitto broker + the agent: Gemma 4 E2B on the Hexagon NPU (via GenieX) runs the conversation inside engine-enforced rails — timers, notifications, and the emergency path fire automatically and never depend on the model. |
| Laptop (Snapdragon X Elite tested) | Dashboard | Floor-plan view with live camera health and previews, a chat-style activity feed, an incident banner with one-click resolve; packaged as a Windows app. |
| Phone | Trusted contact | Two-way Telegram: milestone messages naming the room, and a reply window — answer "OK" to claim an incident before the (simulated) emergency call, or "call 911" to trigger it instantly. |

**Design principles**

- **The agent runs the conversation; the engine guarantees what must not fail.** Timers, contact notifications, and the emergency call are automatic — a slow or wrong model can only ever make the chit-chat worse, never the response.
- **Privacy by construction.** Nodes publish semantic JSON, not media; the "find my stuff" VLM answers in words from inside the room.
- **Skills are data.** Each capability is a markdown file of phases and guidance; adding one touches no engine code.
- **Measured, not asserted.** Every performance number in these docs is tagged measured vs. unmeasured, with the method in [`measurements.md`](measurements.md).

## What you need

| Piece | How many | Notes |
| --- | --- | --- |
| Qualcomm IQ-9075 EVK | 1 | The hub. Vendor Ubuntu 24.04 image (no flashing needed). |
| Arduino UNO Q ("Ventuno Q") | 1 per room, at least 1 | Room nodes. Vendor Ubuntu 24.04 image + Arduino App Lab, as shipped. |
| USB UVC camera | 1 per camera room | Fall detection and/or VLM lookups. Any UVC webcam. |
| USB microphone + speaker | 1 pair per voice room | A headset or separate devices; no echo cancellation needed (the node is half-duplex by design). |
| Laptop | 1 | Dashboard + deploys. Windows on ARM64 is what we run; anything with Python 3.12 and a browser works. |
| Phone with Telegram | 1 per trusted contact | Receives escalations, replies "OK" / "call 911". |

Everything must share one LAN. You'll also create a free Telegram bot (2 minutes, step 4).

> **Substitute your own addresses.** Docs and configs contain *our* lab values — SSH aliases `iq9` / `ventuno` / `ventuno2` and DHCP addresses `10.73.51.x`. Use your own boards' IPs everywhere they appear; [`docs/operations/cold-start.md`](docs/operations/cold-start.md) ("if an IP moved") lists every file that carries one.

## Setup

The path is: prove the code on your laptop → bring up the hub → bring up each room → add secrets → verify the whole house. Each step links the runbook that does it; every runbook states what you're building, the commands, and a verify check so you know it worked before moving on. (Rebuilding later, or recovering a wiped board? The same chain is condensed per-device in [`docs/operations/rebuild.md`](docs/operations/rebuild.md).)

**Step 0 — try it with zero hardware (optional, 5 minutes).**
Any machine with Python 3.12:

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -q          # 200+ hermetic tests, no hardware, no network
bash scripts/demo_fallback.sh              # the full fall ladder on a local broker, no model
```

Then open [`dashboard/index.html`](dashboard/index.html) in a browser, run `python dev/broker.py`, point ⚙ Settings at `ws://127.0.0.1:9001/mqtt`, and drive the house from [`dev/sim.html`](dev/sim.html) or `python dev/inject.py fall --room kitchen`. You get the entire product loop — dashboard, escalation, Telegram-fallback log — with no boards at all.

**Step 1 — laptop toolchain.**
Same three commands as step 0 (venv, `pip install -e ".[dev]"`, `pytest -q`). The laptop is where deploys, the dashboard, and the test suite live.

**Step 2 — the hub (IQ-9075).** Three services, in order:

1. *The LLM.* Install GenieX and pull Gemma 4 E2B onto the NPU → [`setup/iq9-gemma-geniex/README.md`](setup/iq9-gemma-geniex/README.md). Outcome: an OpenAI-compatible endpoint on `:18181`, kept alive by [`infra/systemd/geniex-serve.service`](infra/systemd/geniex-serve.service).
2. *The broker.* Install mosquitto with [`infra/mosquitto.conf`](infra/mosquitto.conf) (MQTT on `11883`, WebSocket on `19001`). Outcome: the event fabric every device talks on.
3. *The engine.* Ship the repo, create a venv, install [`infra/systemd/qnet-agent.service`](infra/systemd/qnet-agent.service) → steps in [`docs/operations/rebuild.md`](docs/operations/rebuild.md) § IQ-9075. Outcome: the brain, listening on the bus.

**Step 3 — each room node (Ventuno Q).** Per board, from [`docs/operations/rebuild.md`](docs/operations/rebuild.md) § Ventuno Q:

1. *Vision.* Python venv + camera + the fall model. The model is a YOLO11n fine-tune from [`melihuzunoglu/human-fall-detection`](https://huggingface.co/melihuzunoglu/human-fall-detection), compiled to Hexagon NPU binaries via Qualcomm AI Hub — **the compiled `.bin` for both board types is committed** ([`models/fall-detection/`](models/fall-detection/)), so you don't need a conversion account; the full recipe is in [`models/fall-detection/README.md`](models/fall-detection/README.md) if you want to reproduce it.
2. *VLM lookups.* Start the Qwen VLM container on `:9001` → [`setup/ventuno-vlm/README.md`](setup/ventuno-vlm/README.md).
3. *Voice.* Deploy the App Lab voice app (`bash scripts/deploy_voice_node.sh <board-ip>`), install the Whisper artifact, write the per-room config → [`setup/ventuno-voice/arduino-speech.md`](setup/ventuno-voice/arduino-speech.md).
4. *Autostart.* Install the board's systemd units from [`infra/systemd/`](infra/systemd/) — each unit's header comment is its own install doc.

**Step 4 — secrets (Telegram).**
Create a bot via **@BotFather**, have each trusted contact press Start on it once, then on the hub create `config/house.local.yaml` with the bot token, the contacts' chat ids, and `mqtt: {host: 127.0.0.1, port: 11883}`. This file is gitignored, board-specific, and never committed — [`config/house.yaml`](config/house.yaml) shows every field with a `TODO` placeholder. Without it, notifications fall back to the console and `data/outbox/telegram.log`, so you can defer this step.

**Step 5 — verify the whole house.**

```bash
bash scripts/health_check.sh
```

One read-only command that checks every service on every board and prints **`ALL GREEN - the house is demo-ready`** — or the exact fix for whatever isn't. Boards power-cycle back to a working house with no keystrokes ([`docs/operations/cold-start.md`](docs/operations/cold-start.md)).

## What runs where

| Device | Service | What it does | Install & docs |
| --- | --- | --- | --- |
| IQ-9075 | `mosquitto` | The MQTT event fabric (`11883` tcp, `19001` ws) | [`infra/mosquitto.conf`](infra/mosquitto.conf) |
| IQ-9075 | `geniex-serve` | Gemma 4 E2B on the NPU, OpenAI-compatible API on `:18181` | [`infra/systemd/geniex-serve.service`](infra/systemd/geniex-serve.service) · [runbook](setup/iq9-gemma-geniex/README.md) |
| IQ-9075 | `qnet-agent` | The engine: skills, timers, escalation, Telegram, LLM calls | [`infra/systemd/qnet-agent.service`](infra/systemd/qnet-agent.service) · [rebuild](docs/operations/rebuild.md) |
| Ventuno (camera room) | `qnet-vision` | Fall detection on the Hexagon NPU, exactly-once events | [`infra/systemd/qnet-vision.service`](infra/systemd/qnet-vision.service) · [model](models/fall-detection/README.md) |
| Ventuno (each) | `qnet-look` | "Do you see X?" — answers via the room's own VLM | [`infra/systemd/qnet-look.service`](infra/systemd/qnet-look.service) · [VLM](setup/ventuno-vlm/README.md) |
| Ventuno (each) | `qnet-stream` | LAN-only camera preview for the dashboard (`:8090`) | [`infra/systemd/qnet-stream.service`](infra/systemd/qnet-stream.service) |
| Ventuno (each) | `qnet-voice-node` app | Wake word, on-NPU Whisper ASR, TTS — the room's ears and voice | [`infra/systemd/qnet-voice-app.service`](infra/systemd/qnet-voice-app.service) · [runbook](setup/ventuno-voice/arduino-speech.md) · [app](apps/ventuno-q/qnet-voice-node/) |
| Laptop | dashboard | [`dashboard/index.html`](dashboard/index.html) (product) + [`admin.html`](dashboard/admin.html) (wire-level portal) — open from `file://`, no server | [`packaging/`](packaging/) builds the Windows exe/MSIX |

## Usage

- **Watch.** Open the dashboard (the packaged app, or `dashboard/index.html` in any browser) and set ⚙ Settings → hub to `ws://<hub-ip>:19001/mqtt`. Rooms tint with their state, a breathing green dot per camera proves it's live, click a room for its LAN-only preview.
- **A fall** — real (lie down in view of the camera) or injected (`python dev/inject.py --port 11883 fall --room kitchen`). The room asks aloud, listens, and escalates on silence: trusted contacts get *"Reply OK if you can check on Tony — otherwise I'll call emergency services in 30 seconds"*; an `OK` reply holds the (simulated) call and tells Tony who's coming; no reply places it. Cancel any time with "false alarm" — spoken, typed, or the banner's **Mark resolved**.
- **Find things.** Say *"Hey Home, where are my keys?"* near any room node. Every room's camera looks via its own on-device VLM; the room you asked from speaks the answer with a landmark ("on the counter, next to the kettle") — or an honest miss naming what was actually checked.
- **First responder.** Say *"I'm the first responder — give me a summary of what happened."* → a spoken, grounded handover from the session log: condition first, then what was done, then where things stand.
- **Tune & inspect.** The admin portal (link in dashboard Settings) shows every message and timing. On-board calibration portal for fall thresholds: `dev/vision_tuner.py`. Voice-loop latency from the bus: `dev/voice_bench.py`.

The full presentation script, timer pacing, and the honest real-vs-simulated card: [`docs/DEMO.md`](docs/DEMO.md).

## Repository layout

```
README.md        this file — start here
LICENSE          GNU AGPL-3.0
docs/            DESIGN.md (spec) · IMPLEMENTATION.md (plan+status) · DEMO.md · operations/ runbooks
qnet/            the code: agent/ (engine, LLM client, Telegram), node/ (vision, look, stream), app.py
apps/            ventuno-q/qnet-voice-node — the App Lab voice app (ASR/TTS/MQTT)
skills/          fall.md · find.md · responder-brief.md · first-aid.md — capabilities as data
contracts/       the frozen MQTT wire contract + one fixture per message type
config/          house.yaml (template) · node.yaml · voice-nodes/*.json — secrets go in *.local.yaml
dashboard/       index.html (product page) · admin.html (technical portal)
dev/             laptop harness: broker, injector, room simulator, spy, replay, latency bench
infra/           mosquitto.conf + systemd units for every service (headers = install docs)
models/          fall model: source, ONNX, compiled NPU binaries for both boards, recipe
packaging/       Windows ARM64 exe + signed MSIX build scripts
scripts/         deploys, health_check.sh, demo_fallback.sh (no-hardware demo)
setup/           device bring-up runbooks (IQ-9075 LLM · Ventuno VLM · Ventuno voice)
tests/           200+ hermetic tests (no hardware, no network)
verify/          evidence per task — command output, measurements, postmortems
measurements.md  every measured number, with method
```

Deep dive → the [documentation map](docs/README.md) indexes every doc, including notes & references.

## Team

| Name | Email |
| --- | --- |
| Amrutha Sai Gattu | amruthsai16@gmail.com |
| Gaurav K Mehta | gkmphx@gmail.com |
| Munibhavana Konidala | konidalamunibhavana@gmail.com |

## License

**GNU Affero General Public License v3.0** — see [`LICENSE`](LICENSE).

QNet Home uses [`melihuzunoglu/human-fall-detection`](https://huggingface.co/melihuzunoglu/human-fall-detection), a YOLO11 fine-tune carrying Ultralytics' AGPL-3.0 terms. AGPL is strong copyleft, so the project as a whole is released under the same licence.

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
