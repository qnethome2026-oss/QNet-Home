# setup/

One folder per module/engine setup. Each folder is self-contained: a `README.md` that doubles as the runbook (what was installed, how, verification results, gotchas) plus any test scripts and tools.

**Building the house from scratch? Start with [`guides/`](guides/01-laptop.md)** — five explicit, numbered, copy-paste guides (laptop → hub → room nodes → Telegram → first run). The folders below are the deep runbooks behind them: full session transcripts, gotchas, and measured numbers. Rebuilding one device: [`docs/operations/rebuild.md`](../docs/operations/rebuild.md).

| Guide | What it walks you through |
|---|---|
| [`guides/01-laptop.md`](guides/01-laptop.md) | Toolchain, tests, and the zero-hardware demo |
| [`guides/02-hub-iq9075.md`](guides/02-hub-iq9075.md) | LLM + broker + agent on the IQ-9075 |
| [`guides/03-room-node-ventuno.md`](guides/03-room-node-ventuno.md) | One board → a full room (vision, VLM, stream, voice) |
| [`guides/04-telegram.md`](guides/04-telegram.md) | Bot creation, chat ids, secrets file, live test |
| [`guides/05-first-run.md`](guides/05-first-run.md) | Whole-house verification + both capabilities |

| Folder | What it sets up | Status |
|---|---|---|
| [`iq9-gemma-geniex/`](iq9-gemma-geniex/) | The brain LLM: Gemma 4 E2B (Q4_0) under GenieX on the IQ-9075, OpenAI-compatible endpoint on `:18181`, systemd service, tests, browser chat UI | ✅ done 2026-08-05 |
| [`ventuno-vlm/`](ventuno-vlm/) | The room eyes: Qwen3-VL-4B (w4a16) on the Hexagon NPU via the Qualcomm container, `:9001`, replication recipe for new boards | ✅ kitchen 2026-08-05 · bedroom 2026-08-06 |
| [`ventuno-voice/`](ventuno-voice/) | The room ears+voice: Arduino ASR/TTS bricks runbook (whisper-small on the NPU, VAD, half-duplex) behind `apps/ventuno-q/qnet-voice-node` | ✅ kitchen 2026-08-06 |

Everything else that was "planned" here now lives in the main tree: Mosquitto (`infra/mosquitto.conf` + `verify/T1.1-resolved.txt`), the fall model (`models/fall-detection/README.md`), dashboard packaging (`packaging/`). Operational index: [`docs/README.md`](../docs/README.md).
