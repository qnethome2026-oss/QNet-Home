# setup/

One folder per module/engine setup. Each folder is self-contained: a `README.md` that doubles as the runbook (what was installed, how, verification results, gotchas) plus any test scripts and tools.

| Folder | What it sets up | Status |
|---|---|---|
| [`iq9-gemma-geniex/`](iq9-gemma-geniex/) | The brain LLM: Gemma 4 E2B (Q4_0) under GenieX on the IQ-9075, OpenAI-compatible endpoint on `:18181`, systemd service, tests, browser chat UI | ✅ done 2026-08-05 |

Planned (per `docs/DESIGN.md`): Mosquitto broker (IQ-9075), speech service (Ventuno Q), node VLM — Qwen3-VL-4B via GenieX (Ventuno Q), fall-detection model (Ventuno Q), dashboard packaging (laptop).
