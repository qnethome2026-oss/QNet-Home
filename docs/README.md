# QNet Home — documentation map

One page per purpose; the long-standing files keep their paths (code and
`verify/` evidence reference them by name and section — never move or renumber
`DESIGN.md` / `IMPLEMENTATION.md`). Start here, follow one link.

## The spec & plan

| Doc | What it is |
|---|---|
| [`DESIGN.md`](DESIGN.md) | The spec: devices, the frozen MQTT contract, the agent's rails (§6), fall detection (§8), voice (§9), "where's my stuff" (§13). Section numbers are load-bearing — code comments cite "DESIGN §6". |
| [`IMPLEMENTATION.md`](IMPLEMENTATION.md) | The plan with live status: phases, gates (G1–G7), per-task verify blocks, standing rules. |
| [`../contracts/mqtt.md`](../contracts/mqtt.md) | The frozen wire contract — topics, payloads, one fixture per message type. Ports are configuration, not contract. |
| [`../contracts/speech-api.md`](../contracts/speech-api.md) | The speech interface record (closed T0.2) — what the voice node guarantees the agent. |

## Demo day

| Doc | What it is |
|---|---|
| [`DEMO.md`](DEMO.md) | The run of show: pre-flight checklist, beat-by-beat script for both use cases, timer pacing, the real-vs-simulated honesty card. |
| [`operations/demo-modes.md`](operations/demo-modes.md) | Which services each use case actually needs, per device (fall / find / all) — the spec for the D4 mode scripts. |
| [`judging-notes.md`](judging-notes.md) | Submission requirements + rubric, condensed from the hackathon's own pages. |

## Voice integration

| Doc | What it is |
|---|---|
| [`voice-integration-plan.md`](voice-integration-plan.md) | The approved integration plan with phase tracking (A–D4); the current state of the voice lane lives here. |
| [`asr-integration-review.md`](asr-integration-review.md) | The three-pass review of the `asr-tts-mqtt` branch that produced the plan; resolution header on top. |
| [`../setup/ventuno-voice/arduino-speech.md`](../setup/ventuno-voice/arduino-speech.md) | The verified Arduino ASR/TTS runtime runbook (VAD, half-duplex, model provisioning). |
| [`../apps/ventuno-q/qnet-voice-node/`](../apps/ventuno-q/qnet-voice-node/) | The voice node itself — self-contained App Lab package. |

## Operations

**Rebuild a board from a blank image:** [`operations/rebuild.md`](operations/rebuild.md).

**Power everything back on:** wait ~3 minutes, then run `bash scripts/health_check.sh` from the repo root — one read-only command that checks all three boards and prints ALL GREEN or the exact fix.
 (new — the hard-won runbooks)

| Doc | What it is |
|---|---|
| [`operations/cold-start.md`](operations/cold-start.md) | Power everything on: what auto-starts where, expected timings, the full verification sequence, boot-order truth. |
| [`operations/troubleshooting.md`](operations/troubleshooting.md) | Symptom-indexed fixes: camera offline, wrong broker, no fall triggers, VLM/NPU transients, ports, Telegram. |
| [`operations/devices.md`](operations/devices.md) | One section per device: what runs on it, ports, hardware quirks, where credentials live (not here). |

## Devices — bring-up runbooks

| Doc | What it is |
|---|---|
| [`../setup/README.md`](../setup/README.md) | Index of setup folders. |
| [`../setup/iq9-gemma-geniex/README.md`](../setup/iq9-gemma-geniex/README.md) | Gemma 4 E2B under GenieX on the IQ-9075 (:18181) — install, the model-cache bug, `pkill -x` gotcha, measured tok/s. |
| [`../setup/ventuno-voice/arduino-speech.md`](../setup/ventuno-voice/arduino-speech.md) | The Arduino speech runtime the voice node drives. |
| [`../models/fall-detection/README.md`](../models/fall-detection/README.md) | Fall model conversion + NPU deployment: the AI Hub device-catalog workaround, per-board credentials table, measured inference times. |
| [`../infra/`](../infra/) | `mosquitto.conf` (ports 11883/19001 + the switch-back procedure in its header) and the six systemd units — the unit headers double as install docs. |

## Evidence (`verify/` highlights)

Every task leaves command output in [`../verify/`](../verify/); measured numbers
are collected in [`../measurements.md`](../measurements.md). The ones worth
reading first:

- [`INCIDENT-wrong-broker.txt`](../verify/INCIDENT-wrong-broker.txt) — the 26-minute wrong-broker incident and the standing rules that came out of it.
- [`T1.1-resolved.txt`](../verify/T1.1-resolved.txt) — why the broker runs on 11883/19001 (coexistence decision).
- [`E2E-no-speech.txt`](../verify/E2E-no-speech.txt) — first full NPU-to-phone run, including a live LLM failure absorbed by the rails.
- [`T4.2.txt`](../verify/T4.2.txt) — fall detection on the Ventuno NPU: exactly-once semantics, measured fps, NPU-sharing findings.
- [`T6.3.txt`](../verify/T6.3.txt) — on-node VLM lookups: round trips, latency, the silent-MQTT-wedge fix.
- [`D2-bedroom-node.txt`](../verify/D2-bedroom-node.txt) — bedroom board bring-up; two-room find e2e.
- [`D3-voice-deploy.txt`](../verify/D3-voice-deploy.txt) — voice node deployed to the kitchen board; RAM gate; say pipeline on the wire.
- [`T0.5-telegram.txt`](../verify/T0.5-telegram.txt) — Telegram bot setup and where the secrets live.
- [`../clips/README.md`](../clips/README.md) — provenance of the real fall test footage.
