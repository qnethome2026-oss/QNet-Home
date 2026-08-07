# The speech interface — machine-referenced record (closes T0.2)

*DESIGN §9 stated our requirements (R1–R6) and left the interface as
placeholders for the speech owner to fill. The interface is now real: the voice
node is an Arduino App Lab application (`apps/ventuno-q/qnet-voice-node/`)
using the Arduino ASR/TTS bricks, extracted from the `asr-tts-mqtt` branch and
adapted (wake gate wired node-side, our frozen wire contract accepted —
`docs/asr-integration-review.md` has the history). This file is the interface
record the adapter, mock, and tests reference; the full verified runtime detail
is `setup/ventuno-voice/arduino-speech.md`.*

Agreed with the speech owner (Munibhavana Konidala), 2026-08-06 — implemented
by extraction from her branch, changes flagged for her PR review.

## The shape

Not an HTTP service. In-process Arduino bricks inside one App Lab app that is
the sole owner of the microphone and speaker:

| Operation | Call | Semantics |
|---|---|---|
| Idle listen | `asr.transcribe_until_cancelled()` | One long-lived stream; runner-side VAD (700 ms [M]) emits partial/final events per utterance; no blind gap between utterances |
| Session listen | `asr.transcribe_sentence(timeout=15)` | Returns first finalized utterance or empty string at the hard timeout |
| Cancel listen | `asr.cancel()` | Sets the session's cancel event (no-op when idle); may still return a stale partial — callers tag generations and discard |
| Speak | `tts.speak(text)` | Synchronous; returns after all PCM is written; +500 ms guard for the ALSA tail [M] |
| Listening? | `asr.is_transcribing()` | State check |

## The requirements, satisfied (R1–R6 ↔ implementation)

| Req | How the interface satisfies it |
|---|---|
| R1 never capture while playing | Single-threaded audio loop; in-flight listen cancelled before `tts.speak`; cancelled-generation results discarded; 500 ms post-TTS guard. Verified by unit tests + system harness. |
| R2 playback completion knowable | `tts.speak` blocks until PCM written. |
| R3 service-side VAD endpointing | Runner-side VAD (700 ms default [M]); the node never touches raw audio frames. |
| R4 bounded listen, distinguishable silence | `transcribe_sentence(timeout)`; empty result maps to `{"text": "", "silence": true}`; errors go to node status, never converted to silence. |
| R5 all local | Whisper-small compiled to QNN, executing on the Hexagon NPU [M]; TTS on-device; only post-wake-gate text ever leaves the node, and transcripts are excluded from logs and the WebUI. |
| R6 listen cancellation | `asr.cancel()` + generation tagging; startup race closed by a bounded watchdog. |

## Wire behaviour (the node side of contracts/mqtt.md)

- Publishes `ask kind=query` ONLY on a wake-phrase match, with the wake phrase
  stripped; responder phrase checked first, any state; everything else is
  discarded on-node.
- During an active session (learned from `qnet/session/+` snapshots) publishes
  `heard {text, silence}` after each bounded listen.
- Consumes `say {text, prio}` — any prio accepted (`routine` mapped to lowest),
  >1024 chars truncated, QoS-1 duplicates deduped, failed playback retryable.
- Heartbeats `qnet/<room>/status {node, room, ts, state}` every 5 s,
  non-retained QoS 0 (same staleness rule as every other node).

## Numbers ([M] = measured, from the runbook's verified runtime)

- VAD endpoint: 700 ms after end of speech [M]
- Post-TTS guard: 500 ms [M]
- Session listen bound: 15 s (config)
- ASR model: whisper-small float16 on HTP v75 [M]; `whisper-small-quantized`
  (w8a16) is the documented one-line rollback under memory pressure;
  whisper-medium is gated off (documented incompatibility)
- End-of-speech → `heard` on the bus: to be measured on-device (T3.1 gate)
