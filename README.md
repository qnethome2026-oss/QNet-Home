# QNet Home

A privacy-first home system built on one event fabric, with capabilities added as pluggable skills. Rooms sense and speak locally; devices exchange small semantic JSON events over MQTT — never video, never audio.

Two capabilities so far. **Fall response:** when someone falls, the room notices, asks if they're alright, listens, and escalates — reassurance out loud, a Telegram to a trusted contact, an emergency call if there's still no answer — narrating each step so the person is never left in silence. A first responder walking in can ask *"I'm the first responder, what happened?"* and get a spoken timeline. **Where's my stuff:** say *"Hey Home, where are my glasses?"* and every room checks its own camera with an on-device VLM; only text crosses the wire, and the answer is spoken in the room you asked from.

> **Status: in development.** Built for the Snapdragon Multiverse hackathon (August 3–7, 2026). Design is complete (`docs/DESIGN.md`), the build plan is `docs/IMPLEMENTATION.md`, and the brain's LLM is already serving on-device (`setup/`). Setup and usage instructions land as components do.

## How it works

Each device does the one job only it can do:

| Device | Role | Responsibility |
| --- | --- | --- |
| Arduino Ventuno Q ×2 | Room node | Fall detection (YOLOv11 fine-tune) always on; STT/TTS via an on-board speech service; Qwen3-VL for "do you see X" lookups. Raw frames and audio never leave the node. |
| Qualcomm IQ-9075 | The brain | Mosquitto broker + the agent: Gemma 4 E2B on the Hexagon NPU (via GenieX) runs the conversation inside engine-enforced rails — timers, notifications, and the emergency path fire automatically and never depend on the model. |
| Snapdragon X Elite laptop | Dashboard | Live session feed, color-coded, with a full-screen takeover on safety events; packaged as the Windows app. |
| Phone | Trusted contact | Telegram messages at milestones — escalated, help called, resolved/false alarm — each naming the room. |

**Design principles**

- **The agent runs the conversation; the engine guarantees what must not fail.** Timers, contact notifications, and the emergency call are automatic — a slow or wrong model can only ever make the chit-chat worse, never the response.
- **Privacy by construction.** Nodes publish semantic JSON, not media; the "find my stuff" VLM answers in words from inside the room.
- **Skills are data.** Each capability is a markdown file of phases and guidance; adding one touches no engine code.
- **Measured, not asserted.** Numbers are tagged measured vs. unmeasured, and unmeasured ones don't get claimed.

## Repository layout

```
README.md     this file
LICENSE       GNU AGPL-3.0
docs/         DESIGN.md (the spec) · IMPLEMENTATION.md (the build plan)
setup/        device setup logs and runbooks (IQ-9075 LLM serving, tests)
scratch/      rough exploration: research reports, scoping docs, spikes (dev branch)
```

Application code will live under `qnet/` as it is written.

## Setup

_Not yet available._ From-scratch installation instructions, dependencies, and a packaged Windows build will be documented here once the application is runnable.

## Usage

_Not yet available._

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
