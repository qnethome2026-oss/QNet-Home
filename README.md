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
| Arduino UNO Q ("Ventuno Q"), one per room | Room node | • Fall detection (YOLO11 fine-tune on the Hexagon NPU), always on<br>• Qwen VLM for "do you see X" lookups<br>• Wake-gated voice: Whisper-small ASR on the NPU + TTS<br>• Raw frames and audio never leave the node — only wake-matched, stripped text is published |
| Qualcomm IQ-9075 EVK | The hub ("brain") | • Mosquitto broker — the event fabric<br>• Gemma 4 E2B on the Hexagon NPU (via GenieX)<br>• The agent: runs the conversation inside engine-enforced rails — timers, notifications, and the emergency path fire automatically and never depend on the model |
| Laptop (Snapdragon X Elite tested) | Dashboard | • Floor-plan view with live camera health and previews<br>• Chat-style activity feed<br>• Incident banner with one-click resolve<br>• Packaged as a Windows app |
| Phone | Trusted contact | • Two-way Telegram: milestone messages naming the room<br>• Reply "OK" to claim an incident before the (simulated) emergency call<br>• Reply "call 911" to trigger it instantly |

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

Everything must share one LAN. You'll also create a free Telegram bot (2 minutes, [Guide 4](setup/guides/04-telegram.md)).

> **Substitute your own addresses.** Docs and configs contain *our* lab values — SSH aliases `iq9` / `ventuno` / `ventuno2` and DHCP addresses `10.73.51.x`. Use your own boards' IPs everywhere they appear; [`docs/operations/cold-start.md`](docs/operations/cold-start.md) ("if an IP moved") lists every file that carries one.

## Setup

Five guides, in order — each one is explicit, numbered, copy-paste-able, and says what you're building, the exact commands, and how to verify it worked before moving on:

| # | Guide | What you end up with |
| --- | --- | --- |
| 1 | [The laptop](setup/guides/01-laptop.md) | The repo installed, 200+ tests green — and optionally the **entire product running with zero hardware** (local broker + dashboard + room simulator) |
| 2 | [The hub (IQ-9075)](setup/guides/02-hub-iq9075.md) | Gemma 4 E2B on the NPU (`:18181`), the MQTT broker (`11883`/`19001`), and the agent — the brain, listening |
| 3 | [A room node (Ventuno Q)](setup/guides/03-room-node-ventuno.md) | A room that watches (fall detection), looks (its own VLM), streams a preview, and hears/speaks — repeat per room |
| 4 | [Telegram](setup/guides/04-telegram.md) | Real phones in the loop: escalation questions out, "OK" / "call 911" replies steering the house |
| 5 | [First run](setup/guides/05-first-run.md) | [`health_check.sh`](scripts/health_check.sh) → **ALL GREEN**, then both capabilities exercised end to end |

Notes for the impatient:

- **No hardware? Start and stop at [Guide 1](setup/guides/01-laptop.md)** — [`scripts/demo_fallback.sh`](scripts/demo_fallback.sh) plus the dashboard against [`dev/broker.py`](dev/broker.py) runs the whole loop on one machine.
- **The fall model is pre-compiled and committed** ([`models/fall-detection/`](models/fall-detection/)) — a YOLO11n fine-tune from [`melihuzunoglu/human-fall-detection`](https://huggingface.co/melihuzunoglu/human-fall-detection), compiled for both boards' Hexagon NPUs via Qualcomm AI Hub. You don't need a conversion account; the full recipe is in [`models/fall-detection/README.md`](models/fall-detection/README.md) if you want to reproduce it.
- **Telegram is deferrable** — without it, notifications fall back to the console and a log file; everything else works.
- **Rebuilding or recovering a wiped board?** The same chain, condensed per-device: [`docs/operations/rebuild.md`](docs/operations/rebuild.md). The deep runbooks behind the guides (full session transcripts, gotchas, measured numbers) live in [`setup/`](setup/README.md).

## What runs where

| Device | Service | What it does | Install & docs |
| --- | --- | --- | --- |
| IQ-9075 | `mosquitto` | The MQTT event fabric (`11883` tcp, `19001` ws) | • [`infra/mosquitto.conf`](infra/mosquitto.conf)<br>• [Guide 2, Step 3](setup/guides/02-hub-iq9075.md) |
| IQ-9075 | `geniex-serve` | Gemma 4 E2B on the NPU, OpenAI-compatible API on `:18181` | • [`geniex-serve.service`](infra/systemd/geniex-serve.service)<br>• [LLM runbook](setup/iq9-gemma-geniex/README.md) |
| IQ-9075 | `qnet-agent` | The engine: skills, timers, escalation, Telegram, LLM calls | • [`qnet-agent.service`](infra/systemd/qnet-agent.service)<br>• [Guide 2](setup/guides/02-hub-iq9075.md) |
| Ventuno (camera room) | `qnet-vision` | Fall detection on the Hexagon NPU, exactly-once events | • [`qnet-vision.service`](infra/systemd/qnet-vision.service)<br>• [Model README](models/fall-detection/README.md) |
| Ventuno (each) | `qnet-look` | "Do you see X?" — answers via the room's own VLM | • [`qnet-look.service`](infra/systemd/qnet-look.service)<br>• [VLM runbook](setup/ventuno-vlm/README.md) |
| Ventuno (each) | `qnet-stream` | LAN-only camera preview for the dashboard (`:8090`) | • [`qnet-stream.service`](infra/systemd/qnet-stream.service) |
| Ventuno (each) | `qnet-voice-node` app | Wake word, on-NPU Whisper ASR, TTS — the room's ears and voice | • [`qnet-voice-app.service`](infra/systemd/qnet-voice-app.service)<br>• [Voice runbook](setup/ventuno-voice/arduino-speech.md)<br>• [The app itself](apps/ventuno-q/qnet-voice-node/) |
| Laptop | dashboard | [`index.html`](dashboard/index.html) (product) + [`admin.html`](dashboard/admin.html) (wire-level portal) — open from `file://`, no server | • [`packaging/`](packaging/) builds the Windows exe/MSIX |

## Usage

- **Watch.** Open the dashboard (the packaged app, or [`dashboard/index.html`](dashboard/index.html) in any browser) and set ⚙ Settings → hub to `ws://<hub-ip>:19001/mqtt`. Rooms tint with their state, a breathing green dot per camera proves it's live, click a room for its LAN-only preview.
- **A fall** — real (lie down in view of the camera) or injected with [`dev/inject.py`](dev/inject.py) (`python dev/inject.py --port 11883 fall --room kitchen`). The room asks aloud, listens, and escalates on silence: trusted contacts get *"Reply OK if you can check on Tony — otherwise I'll call emergency services in 30 seconds"*; an `OK` reply holds the (simulated) call and tells Tony who's coming; no reply places it. Cancel any time with "false alarm" — spoken, typed, or the banner's **Mark resolved**.
- **Find things.** Say *"Hey Home, where are my keys?"* near any room node. Every room's camera looks via its own on-device VLM; the room you asked from speaks the answer with a landmark ("on the counter, next to the kettle") — or an honest miss naming what was actually checked.
- **First responder.** Say *"I'm the first responder — give me a summary of what happened."* → a spoken, grounded handover from the session log: condition first, then what was done, then where things stand.
- **Tune & inspect.** The admin portal (link in dashboard Settings) shows every message and timing. On-board calibration portal for fall thresholds: [`dev/vision_tuner.py`](dev/vision_tuner.py). Voice-loop latency from the bus: [`dev/voice_bench.py`](dev/voice_bench.py).

The full presentation script, timer pacing, and the honest real-vs-simulated card: [`docs/DEMO.md`](docs/DEMO.md).

## Repository layout

| Where | What lives there |
| --- | --- |
| [`docs/`](docs/README.md) | [`DESIGN.md`](docs/DESIGN.md) (spec) · [`IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) (plan+status) · [`DEMO.md`](docs/DEMO.md) · [`operations/`](docs/operations/) runbooks |
| [`qnet/`](qnet/) | The code: `agent/` (engine, LLM client, Telegram), `node/` (vision, look, stream), `app.py` |
| [`apps/`](apps/ventuno-q/qnet-voice-node/) | `ventuno-q/qnet-voice-node` — the App Lab voice app (ASR/TTS/MQTT) |
| [`skills/`](skills/) | `fall.md` · `find.md` · `responder-brief.md` · `first-aid.md` — capabilities as data |
| [`contracts/`](contracts/) | The frozen MQTT wire contract + one fixture per message type |
| [`config/`](config/) | `house.yaml` (template) · `node.yaml` · `voice-nodes/*.json` — secrets go in gitignored `*.local.yaml` |
| [`dashboard/`](dashboard/) | `index.html` (product page) · `admin.html` (technical portal) |
| [`dev/`](dev/) | Laptop harness: broker, injector, room simulator, spy, replay, latency bench |
| [`infra/`](infra/) | `mosquitto.conf` + systemd units for every service (headers = install docs) |
| [`models/`](models/fall-detection/) | Fall model: source, ONNX, compiled NPU binaries for both boards, recipe |
| [`packaging/`](packaging/) | Windows ARM64 exe + signed MSIX build scripts |
| [`scripts/`](scripts/) | Deploys, `health_check.sh`, `demo_fallback.sh` (no-hardware demo) |
| [`setup/`](setup/README.md) | Step-by-step [`guides/`](setup/guides/01-laptop.md) + device bring-up runbooks (IQ-9075 LLM · Ventuno VLM · Ventuno voice) |
| [`tests/`](tests/) | 200+ hermetic tests (no hardware, no network) |
| [`verify/`](verify/) | Evidence per task — command output, measurements, postmortems |
| [`measurements.md`](measurements.md) | Every measured number, with method |
| [`LICENSE`](LICENSE) | GNU AGPL-3.0 |

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
