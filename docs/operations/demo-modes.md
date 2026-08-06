# Demo modes — per-use-case service sets

*Back to the [docs index](../README.md). Status: **scripts to be generated —
see [`voice-integration-plan.md`](../voice-integration-plan.md) phase D4.**
Today this page is the spec: the intent, and the manual service lists a human
runs. When the mode scripts exist, this page is their contract.*

## Intent

One command per demo mode — `fall`, `find`, `all` — that starts exactly the
services that use case needs (and verifies them, per
[`cold-start.md`](cold-start.md)), so a rehearsal never runs half a fleet by
accident and a broken service outside the demoed use case can't eat rehearsal
time. Stopping the complement is optional; the modes are about *knowing what
must be up*, not about minimalism for its own sake.

## Mode `fall` — use case 1 (fall response)

| Device | Needed | Not needed |
|---|---|---|
| IQ-9075 | `mosquitto`, `geniex-serve`, `qnet-agent` | — |
| Ventuno kitchen | `qnet-vision` (detection) · `qnet-voice-node` app (spoken ask/answer) · `qnet-stream` (the Beat-0 preview) | `qnet-look`, VLM container |
| Ventuno bedroom | nothing | all of it |
| Laptop | dashboard | — |
| Phone | Telegram chat open | — |

## Mode `find` — use case 2 ("where's my stuff")

| Device | Needed | Not needed |
|---|---|---|
| IQ-9075 | `mosquitto`, `geniex-serve`, `qnet-agent` | — |
| Ventuno kitchen | `qnet-look` + VLM container · `qnet-voice-node` app (ask + spoken answer) | `qnet-vision` (look falls back to a direct camera grab), `qnet-stream` |
| Ventuno bedroom | `qnet-look` + VLM container | `qnet-stream` (nice for aiming, not needed for the beat) |
| Laptop | dashboard | — |
| Phone | nothing | — |

## Mode `all` — the full run of show

Everything in [`cold-start.md`](cold-start.md)'s table, verified by its full
sequence. This is what [`DEMO.md`](../DEMO.md) assumes.

## Notes for the script author (D4)

- Start commands are `systemctl start ...` per device plus
  `arduino-app-cli app start /home/arduino/ArduinoApps/qnet-voice-node` for
  the voice app; verification is the relevant subset of the cold-start
  sequence (is-active, right-broker check, heartbeat spy, endpoints).
- `geniex-serve` stays in every mode: the rails run without the LLM, but a
  demo without wording isn't the demo — and the fallback story
  (`DEMO.md §6`) covers a mid-run death either way.
- The composer fallback (`dev/inject.py`, dashboard composer) needs nothing
  extra started — it rides the same broker.
