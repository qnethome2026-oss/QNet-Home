# Arduino ASR/TTS runtime runbook

> Extracted from branch `asr-tts-mqtt`; operational runbook, not a contract —
> the wire contract is `contracts/mqtt.md`, the speech interface record is
> `contracts/speech-api.md`. Names were updated for the extracted app
> (`qnet-voice-node`, `qnet-config.json`); the runtime observations below were
> verified under the original app name on 2026-08-05 and are otherwise
> unchanged.

This runbook replaces the earlier proposed HTTP `/listen` and `/speak`
service. QNet Home uses Arduino App CLI bricks directly inside one Ventuno Q
application. The application is the sole owner of the microphone and speaker.

**What this builds:** a room node that hears and speaks — Whisper ASR on the
Hexagon NPU plus TTS, running as two containers managed by Arduino App Lab,
driven by the `apps/ventuno-q/qnet-voice-node` application over MQTT.

**Order of operations for a fresh board** (each detailed in the sections
below; condensed per-device in `docs/operations/rebuild.md`):

1. Confirm the runtime versions and USB audio devices (*Verified runtime*).
2. Deploy the app: `bash scripts/deploy_voice_node.sh <board-ip>`, then write
   `qnet-config.json` from `config/voice-nodes/` (room, hub IP, `usb:N`
   mic/speaker indices from `arecord -l` / `aplay -l`).
3. Pick the ASR model (*ASR model provisioning*): the board's **built-in
   `whisper-small-quantized` works out of the box** — no download needed; the
   float `whisper-small` artifact is an optional accuracy upgrade installed
   with `scripts/install_whisper_voice_ai_model.sh`.
4. Start it: `arduino-app-cli app start user:qnet-voice-node`, and install
   `infra/systemd/qnet-voice-app.service` so it survives reboots.
5. Prove it: the *Phase 1 acceptance tests* at the end.

**Outcome:** say the wake phrase in the room and the stripped command appears
on `qnet/<room>/ask`; a `say` on the bus is spoken aloud; raw audio never
leaves the board.

## Verified runtime

Inspected on the living-room Ventuno Q on 2026-08-05:

| Component | Verified value |
|---|---|
| Arduino App CLI | 0.12.1 |
| Arduino App CLI daemon | 0.12.1 |
| `arduino_app_bricks` Python package | 0.11.0 |
| Application container | `qnet-voice-node-main-1` |
| Audio runner container | `qnet-voice-node-audio-analytics-runner-1` |
| ASR implementation | `arduino.app_bricks.asr.local_asr.AutomaticSpeechRecognition` |
| TTS implementation | `arduino.app_bricks.tts.local_tts.TextToSpeech` |
| USB microphones visible in the app | `CARD=Camera,DEV=0`, `CARD=Seri,DEV=0` |
| USB speaker visible in the app | `CARD=Seri,DEV=0` |

The runbook is tied to these observed versions. An Arduino App CLI or App
Bricks upgrade must rerun the Phase 1 speech tests before deployment.

## Lifecycle

`app.yaml` declares `arduino:asr`, `arduino:tts`, and `arduino:web_ui`. Arduino
App CLI provisions the application and audio-analytics runner. The application
constructs one ASR object and one TTS object and explicitly starts both before
entering the user loop:

```python
App.start_brick(asr)
App.start_brick(tts)
```

Only one ASR session and one TTS session may be active on their respective
objects. The QNet controller imposes the stronger rule that ASR and TTS never
overlap with each other.

## ASR

### Supported calls

```python
asr.transcribe(duration: int = 60) -> str
asr.transcribe_sentence(timeout: int = 0) -> str
asr.transcribe_until_cancelled() -> TranscriptionStream
asr.cancel() -> None
asr.is_transcribing() -> bool
```

QNet uses `transcribe_until_cancelled()` for idle listening. One stream stays
open and yields multiple partial/final events, avoiding a blind gap between
utterances. During an active safety session QNet instead uses
`transcribe_sentence(timeout=...)`, which returns after the first finalized
utterance or the hard timeout. Fixed-duration `transcribe` is not used.

### VAD

The installed ASR client creates every server session with a `vad` parameter.
The verified default is 700 ms (`AutomaticSpeechRecognition._DEFAULT_VAD_MS =
700`). The audio runner emits `speech_start`, `speech_end`, partial-text, and
full-text events. The continuous idle stream remains open after each
`full_text`; the safety-session call stops after its first non-empty
`full_text`. Both provide sentence endpointing without a second VAD model or a
second microphone owner.

For Phase 1, QNet uses the supported 700 ms default. A configurable value may be
added later only through a public Arduino API or a small reviewed adapter; QNet
must not depend silently on a private class attribute.

### Silence and timeout

The collector returns an empty string when the session produces no full or
partial text. QNet maps this result to the wire contract as:

```json
{"text": "", "silence": true}
```

An empty string is not an ASR error. Exceptions from service availability,
audio-device state, or a busy session are errors and must be reported through
node status rather than converted to silence.

### Cancellation

`asr.cancel()` sets the active session's cancellation event and is a no-op when
there is no active session. Worker loops observe that event at roughly 100–200
ms polling boundaries before cleanup.

Cancellation does not guarantee an empty result: the collector intentionally
falls back to the most recent partial transcript when no full transcript was
received. Therefore the QNet controller must tag each listen generation and
discard every result from a generation cancelled to make way for TTS. It must
not infer intentional cancellation from an exception alone.

While idle, QNet retains at most 10 seconds of finalized text plus the latest
partial. This preserves a short "Hey Home" that Whisper may omit from the final
event. The buffer is cleared before every TTS playback so speaker output can
never be joined to a later user request.

## TTS

### Supported calls

```python
tts.speak(text: str) -> None
tts.cancel() -> None
```

`tts.speak` is synchronous in the installed implementation: it holds an active
session lock, streams synthesis results, and writes all PCM chunks to the ALSA
speaker before returning. Concurrent calls on the same object raise a busy
error.

The library does not explicitly drain the final hardware playback buffer after
the last ALSA write. QNet therefore retains a configurable post-TTS guard
(default 500 ms) before reopening ASR. Phase 1 verifies the guard on the real
speaker and increases it if loopback speech is observed.

## Half-duplex invariant

The voice controller is a single audio owner with this transition:

```text
LISTENING
  -> cancel listen when SAY arrives
  -> discard the cancelled listen result
  -> SPEAKING
  -> wait for speak() to return
  -> POST_TTS_GUARD
  -> LISTENING
```

The MQTT callback may enqueue speech and request ASR cancellation, but only the
application's audio-control loop may start ASR or TTS. Safety-priority speech is
processed before comfort-priority speech. No code may open a second microphone
or speaker handle.

## Model provisioning

Arduino App CLI owns ASR/TTS runner and model provisioning declared by
`app.yaml`. QNet's IQ9 setup scripts do not download speech models. A node is
ready only after the runner is healthy and a real ASR and TTS inference succeeds;
catalog metadata alone is not proof that a model is loaded.

### Active ASR model

The deployed living-room and bedroom nodes use float/unquantized Whisper Small:

```json
{"asr_model": "whisper-small"}
```

The application applies that setting with `asr.model = config.asr_model` before
starting the ASR brick. The audio-analytics runner resolves the name from its
model registry and executes the QNN encoder and decoder on Qualcomm HTP. MQTT
does not carry audio and does not select the model; it only carries completed
text and speech commands after the local ASR/TTS calls.

Install a previously obtained and hardware-tested Voice AI QNN artifact with:

```sh
./scripts/install_whisper_voice_ai_model.sh \
  <ventuno-ip> <artifact-directory> whisper-small
```

The artifact directory must contain `encoder.bin`, `decoder.bin`, and
`metadata.json`. The installer adds `config.json` and the matching Whisper Small
vocabulary, then atomically places the model at:

```text
/var/lib/arduino-app-cli/models/audio-analytics/asr/
  whisper_small-voice_ai-float-qualcomm_qcs8275
```

Restart the App after installation. Acceptance requires runner logs containing
both `Available ASR models: ['whisper-small', ...]` and a transcription request
with `model=whisper-small`. The artifact deployed on 2026-08-05 was preflighted
with `qnn-net-run` and then exercised by real runner transcription on both
Ventuno Q devices.

The built-in `whisper-small-quantized` directory is deliberately retained as a
rollback. To revert, set `"asr_model": "whisper-small-quantized"` in the
device's `qnet-config.json` and restart the App; no model copy is required.

### Whisper Medium compatibility gate

Do not select `whisper-medium` in a deployed node until its exact Qualcomm
Voice AI package passes a live runner transcription. A generic Medium QNN
context can execute its encoder directly on the QCS8275 HTP, but adapting that
generic package to the Arduino registry failed inside the bundled Voice AI
wrapper while registering the 24-layer decoder caches. The runner dropped its
HTTP response, so catalog discovery alone is not an acceptance result.

The official Qualcomm `v0.59.0` Voice AI artifact is cached locally at
`models/asr/whisper_medium-voice_ai-float-qualcomm_sa7255p` (ignored by Git).
Unlike a generic export, it includes its own Voice AI encoder, `config.json`,
and `vocab.bin`; the installer must preserve those files. Its manifest declares
file-based support and not streaming support, while QNet's current live adapter
uses streaming/VAD. The live nodes therefore remain on `whisper-small` unless
that exact package proves compatible or the adapter gains a tested file-based
capture path.

## Phase 1 acceptance tests

- A `say` arriving during ASR cancels listening and starts TTS promptly.
- A partial result from the cancelled listen is discarded.
- Multiple VAD-finalized utterances are produced by one continuous ASR session.
- A wake phrase emitted only as a partial is preserved in the rolling text sent to IQ9.
- ASR remains inactive until TTS returns and the post-playback guard ends.
- Silence returns cleanly at timeout and is distinct from an error.
- Fifty listen/speak cycles complete without a busy error or deadlock.
- The microphone does not transcribe the node's own speaker output.
- Device identifiers remain valid after a node reboot.
