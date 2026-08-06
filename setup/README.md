# setup/

One folder per module/engine setup. Each folder is self-contained: a `README.md` that doubles as the runbook (what was installed, how, verification results, gotchas) plus any test scripts and tools.

| Folder | What it sets up | Status |
|---|---|---|
| [`iq9-gemma-geniex/`](iq9-gemma-geniex/) | The brain LLM: Gemma 4 E2B (Q4_0) under GenieX on the IQ-9075, OpenAI-compatible endpoint on `:18181`, systemd service, tests, browser chat UI | ✅ done 2026-08-05 |
| [`ventuno-vlm/`](ventuno-vlm/) | The room eyes: Qwen3-VL-4B (w4a16) on the Hexagon NPU via the Qualcomm container, `:9001`, replication recipe for new boards | ✅ kitchen 2026-08-05 · bedroom 2026-08-06 |
| [`ventuno-voice/`](ventuno-voice/) | The room ears+voice: Arduino ASR/TTS bricks runbook (whisper-small on the NPU, VAD, half-duplex) behind `apps/ventuno-q/qnet-voice-node` | ✅ kitchen 2026-08-06 |

Everything else that was "planned" here now lives in the main tree: Mosquitto (`infra/mosquitto.conf` + `verify/T1.1-resolved.txt`), the fall model (`models/fall-detection/README.md`), dashboard packaging (`packaging/`). Operational index: [`docs/README.md`](../docs/README.md).
