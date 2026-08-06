# Troubleshooting — by symptom

*Back to the [docs index](../README.md). Cold-boot procedure:
[`cold-start.md`](cold-start.md). Everything here was hit for real; each entry
cites its evidence file.*

## Camera offline / preview dead / vision "active" but frozen

- **USB re-enumeration** (`/dev/video0` vanished overnight; vision hung
  mid-read for 13 h while systemd still said *active*): both kitchen units now
  use the stable `/dev/v4l/by-id/...` path instead of `/dev/videoN` — that is
  the recurrence-proof fix (D0 pre-flight,
  [`voice-integration-plan.md`](../voice-integration-plan.md)). The bedroom
  unit already uses the BRIO's by-id path
  ([`qnet-look-bedroom.service`](../../infra/systemd/qnet-look-bedroom.service)).
  (The repo unit files now carry the by-id path too. A vision stall watchdog
  remains a noted follow-up, not built.)
- **Vision stalled** (heartbeat stopped, frame stale): `ssh ventuno 'sudo
  systemctl restart qnet-vision'` — the shm frame should be fresh within
  seconds ([`cold-start.md`](cold-start.md) step 4 checks this).
- **Aim / placement**: the camera must see the whole fall area and the subject
  must be reasonably large in frame — the model detects bodies, not faces; a
  person at extreme close range correctly yields *no* detection
  (`verify/T4.2.txt` §6), and D2's BRIO spent its first minutes pointing at
  the ceiling. Check what the camera actually sees via
  `http://<board>:8090/<room>.jpg` before blaming the model.

## Agent silent / asks vanish without a journal trace → WRONG BROKER

The one incident that cost 26 minutes (`verify/INCIDENT-wrong-broker.txt`):
the board's `config/house.local.yaml` was overwritten with the laptop's copy,
which lacks the `mqtt:` block, so the agent fell back to `:1883` — a foreign
stack — while our broker had no agent at all.

**Standing rules:**

1. **NEVER scp a laptop `house.local.yaml` to a board.** Board copies are
   board-specific by design (`mqtt: {host: 127.0.0.1, port: 11883}` + only
   boards are localhost to the broker). Edit board copies in place.
2. **After ANY agent restart, read the connect line:**
   `ssh iq9 'journalctl -u qnet-agent --no-pager | grep connected | tail -1'`
   → must say `127.0.0.1:11883`.
3. If a teammate voice node ever joins our broker, its STT must be wake-gated
   node-side (`contracts/mqtt.md`: `ask.text` is the transcript with the wake
   phrase stripped) — ungated STT arriving as asks was part of this incident.

## No fall triggers

Checklist, in the order that actually finds it:

1. **Subject too small in frame** — re-aim / move closer (see camera section
   above).
2. **Screen replay is a weaker signal than a real fall.** Playing a fall clip
   on a screen in front of the camera yields fallen confidence around
   ~0.4–0.5, vs ~0.85+ [M] from real footage fed directly to the pipeline
   (`verify/T4.2.txt`). With the shipped floor of 0.6 a screen replay may
   never fire — that is the floor doing its job, not a bug.
3. **Current `conf_floor` status: 0.6 everywhere, reaffirmed by experiment.**
   0.35 was tried live during the screen-replay rehearsal (2026-08-06) and
   **reverted the same day**: at that floor the model scored `fallen` up to
   0.52 on a *blank wall* — the screen-replay signal band (0.40–0.52) is
   indistinguishable from empty-scene noise (full table:
   `measurements.md`, "Fall-model threshold probe"). If you ever find a board
   running below 0.6, restore it: check `~/qnet-node/config/house.yaml`
   `vision.conf_floor` on the board (and `systemctl cat qnet-vision` for a
   `--conf` override), set 0.6, `sudo systemctl restart qnet-vision`.
4. **See what the model actually reads — detwatch.** Debug technique from the
   rehearsal session: a small script at `/tmp/detwatch.py` **on the kitchen
   board** (not in the repo — recreate as a stripped `vision.py` loop that
   publishes each frame's top detections instead of gating them) publishes
   live model readings to `qnet/kitchen/detwatch`; watch from the laptop with
   `dev/spy.py --broker 10.73.51.175 --port 11883 -t qnet/kitchen/detwatch`.
   This tells you in one minute whether the problem is signal strength
   (readings near the floor) or plumbing (no readings at all).

## VLM: first call returns empty

First look/describe call after the container starts can return an empty
answer; the identical retry succeeds. Retry once before restarting anything.
`node/look.py` treats found=false with empty answer as an honest miss, so an
empty *first* answer can masquerade as "not found" — if the very first find of
a session misses implausibly, ask again.

## NPU-sharing transients (fastrpc)

`qnn-net-run` intermittently fails while the VLM container is busy — rc=11 or
a burst of `Failed to create transport for device, error: 1002` / `Failed to
load skel` — with the identical invocation succeeding seconds later
(`verify/T4.2.txt` §8). `vision.py` retries ×3 with 0.2 s backoff and rides
through; a persistent failure still propagates loudly. Demo implication: a
fall during VLM generation may be *delayed* ~0.5 s by a retry cycle, never
lost. If failures persist beyond retries, check whether both VLM containers
and vision are hammering the NPU simultaneously.

## Mosquitto ports (why 11883/19001, and switching back)

Non-standard on purpose: a teammate's stack held `:1883`/`:9001` on the IQ9
and the user chose coexistence (`verify/T1.1-resolved.txt`). Ports are
configuration, not contract. Her stack was retired in D1, so 1883/9001 are
free — but ports stay 11883/19001 **through the demo**. The switch-back
procedure lives in the header of
[`infra/mosquitto.conf`](../../infra/mosquitto.conf): change the two listener
numbers, update `config/house.yaml`'s `mqtt:` block, restart mosquitto.

## Telegram messages not arriving

- Token + contact chat ids live **only** in `config/house.local.yaml` —
  gitignored, merged over `house.yaml` at agent startup
  (`verify/T0.5-telegram.txt`). It does not travel with a clone: the machine
  running `qnet.agent` must have it next to `house.yaml`.
- The local-overlay rules are the wrong-broker rules: the file is
  board-specific, never copy the laptop's over a board's (the board copy also
  carries the `mqtt:` block — see the wrong-broker section).
- Every attempted send is appended to `data/outbox/telegram.log` on the agent
  machine — check there first to split "not sent" from "not delivered".
- Console note: the message templates carry emoji by design; printing tool
  results in a cp1252 Windows console needs `PYTHONIOENCODING=utf-8` (the tool
  itself always writes utf-8).

## Voice node misbehaving

- Heartbeat missing on `qnet/kitchen/status` (`kitchen-voice-01`): check
  `arduino-app-cli app list`, then the two containers
  (`docker ps` → `qnet-voice-node-main-1`,
  `qnet-voice-node-audio-analytics-runner-1`).
- Wrong mic: this board's working config is mic `usb:2`, speaker `usb:1` —
  both the Seri headset; `usb:1` capture is the camera's mic
  (`verify/D3-voice-deploy.txt` §1 has the ALSA mapping).
- RAM pressure: flip `qnet-config.json` `asr_model` to
  `whisper-small-quantized` and restart the app — the rollback model is
  already registered on the board.
- A dead microphone never kills a demo beat: the dashboard's flagged composer
  is the rehearsed fallback ([`DEMO.md`](../DEMO.md)).


## Voice chain wedges (observed live 2026-08-06, both cured by one restart)

Symptoms: the house goes mute (TTS `ConnectionError`/`RemoteDisconnected` in
`docker logs qnet-voice-node-main-1`) and/or nothing is transcribed (runner
logs `Failed to decode audio chunk. Data field length: 0`, zero `full_text`
events) — while the voice heartbeat may still claim `listening` (known health
blind spot: the node does not yet notice a silent runner).

Fix: `ssh ventuno 'arduino-app-cli app restart user:qnet-voice-node'` — both
containers restart, models reload (~45 s). Verify: publish a routine say and
watch the heartbeat run listening→speaking→idle with zero new ConnectionErrors.

Aggravating factor (fixed): the original 20 s comfort metronome sent a TTS
request every cycle during long sessions — the 1/2/5-minute schedule cuts that
load ~15×.
