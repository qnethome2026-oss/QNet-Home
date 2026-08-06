# Voice integration — plan and live tracking

*The approved plan for integrating the `asr-tts-mqtt` voice node into QNet Home,
with progress tracked in place. Review evidence: `docs/asr-integration-review.md`.
Branch: `voice-integration` → one PR to `main` at the end. Decisions locked:
node-side wake gating · everything AGPL · one shared mosquitto (hers retires) ·
ports stay 11883/19001 until after the demo · voice on the kitchen board first
(bedroom = stretch) · laptop phases first, device phases when hardware is
available · modular: the voice node is a self-contained App Lab package, the
frozen MQTT contract is the boundary, zero engine/tool/dashboard changes.*

## Status at a glance

| Phase | What | State |
|---|---|---|
| A | Extraction + re-license | ✅ done — Checkpoint V-AB (`8dfecf6`) |
| B | Five blocker fixes, test-driven | ✅ done — Checkpoint V-AB (`8dfecf6`) |
| C | Hardware-free conversation harness + docs | ✅ done — Checkpoint V-C |
| D0 | Device pre-flight (IPs, services, right-broker check) | ✅ done 2026-08-06 |
| D1 | Retire her IQ9 stack | ✅ done 2026-08-06 (user authorized on Muni's behalf) |
| D2 | Second Ventuno bring-up (bedroom: VLM + look + stream) | ✅ done 2026-08-06 |
| D3 | Voice node on the kitchen board (RAM gate → G3 checklist → wake soak) | 🔨 deployed 2026-08-06: app running, both whisper models registered, heartbeat + say proven on wire, RAM gate passed on float (`verify/D3-voice-deploy.txt`); G3 in-room checklist + T6.4 wake soak await a human |
| D4 | Voice-first rehearsals ×2, contact-ack live, packaging, merge PR | ⬜ awaiting devices |

## Phase A — Extraction + re-license ✅

Her `qhome-voice-node` App Lab package → `apps/ventuno-q/qnet-voice-node/`
(renamed throughout; MIT LICENSE not imported; our AGPL header on every file),
plus `scripts/{deploy_voice_node,install_whisper_voice_ai_model}.sh`,
`setup/ventuno-voice/arduino-speech.md` (runbook), `config/voice-nodes/*.json`
(kitchen new; bedroom fixed to `.175:11883`), her tests+fakes → `tests/voice/`,
`docs/judging-notes.md`. Her parallel mini-system (agent, router, embedded
broker, contract dialect, docs) deliberately NOT extracted.

**Gate A evidence:** suite 125 → 150 green · `grep -ri qhome` over new files
empty · SPDX audit clean. Independently re-verified by the orchestrator.

## Phase B — Blocker fixes ✅

- **B1 wake gate wired** (the structural fix): responder phrase checked first;
  wake detection over the rolling window (split "Hey Home" survives); only the
  stripped post-phrase remainder is ever published; otherwise nothing leaves
  the node; transcripts scrubbed from logs and WebUI; `wake_phrase` config
  (default "hey home", tolerant regex kept).
- **B2 contract conformance**: her validators accept our frozen fixtures
  byte-for-byte (`tests/voice/test_contract_conformance.py`); `say` needs only
  `{text, prio}`, `routine` mapped, >1024 truncated; session snapshots parse;
  outbound `heard` trimmed to `{text, silence}`.
- **B3 reliability**: failed TTS no longer permanently consumes a safety line
  (remember-on-success + inflight set); exponential ASR-failure backoff
  (0.25→10 s); retained-LWT status replaced by our 5 s non-retained heartbeat
  `{node, room, ts, state: idle|listening|speaking|error}`.

**Gate B evidence:** suite 178 green (voice suite 53, conformance 11/11) ·
byte-compile clean. Independently re-verified.

## Phase C — Hardware-free system glue ✅

**Gate C evidence:** 7 system tests in `tests/voice/test_voice_system.py` (real
agent + real controller + real transport validation, fake audio bricks, in-
process bridge) — fall→"i'm fine"→pain-check→resolved · silence→SIMULATED call
· wake-gated find speaks the location (chatter publishes nothing) · responder
brief mid-escalation · false-alarm cancel · half-duplex interrupt. Suite **186**
hermetic (+7 live deselected) · `demo_fallback.sh` 12/12 (QNET_TIMER_SCALE=0.05)
· dashboard self-tests 119/119. Stub `qnet/node/voice.py` retired;
`contracts/speech-api.md` written (T0.2 closed); DESIGN §9 filled; DEMO v1.0
voice-first. **Bonus find by the harness:** the --no-llm mind classified
"no i'm not hurt" as pain (no negation handling) — fixed with
`_NEGATED_PAIN_RE` + tests; denials resolve, ambiguity still escalates.

1. **Conversation harness** `tests/voice/test_voice_system.py`: REAL agent
   engine + REAL VoiceController + fake ASR/TTS bricks + in-process bus.
   Scripted, no audio, no network: fall→"i'm fine"→pain-check→"no"→resolved ·
   silence→escalate→SIMULATED call · wake-gated find ("hey home where are my
   glasses i can't find them" → gated ask → look → spoken answer) · responder
   brief mid-escalation · "false alarm" cancel · half-duplex interrupt (say
   during listen → cancel, speak, resume).
2. Retire `qnet/node/voice.py` stub; write `contracts/speech-api.md` (T0.2
   closes — the interface record, from the arduino-speech runbook).
3. Docs: DESIGN §9 interface table filled (numbers marked [M] from the
   runbook), §5 modules updated; IMPLEMENTATION status (T0.2 ✓, T1.4 ✓,
   T3.1 → pending-device); DEMO.md voice-first beats (typed composer demoted
   to fallback); review doc gains a resolution header; README device table.

**Gate C:** full suite green · `scripts/demo_fallback.sh` 12/12 ·
dashboard self-tests 119/119 · branch pushed.

## Phase D — Device phases (start on the user's "devices available" signal)

**D0 pre-flight ✅ (2026-08-06):** all three boards reachable at their known
IPs (Ventuno-2 = 10.73.51.178, password without the @); IQ9 3/3 services on OUR
broker; Ventuno-1 3/3 active. **Incident found+fixed:** the kitchen USB camera
re-enumerated overnight (/dev/video0 vanished) and vision hung mid-read for
13 h while "active" — both kitchen units now use the stable /dev/v4l/by-id/
path (recurrence-proof) and vision recovered to 2.66 fps. Follow-up noted: a
stall watchdog for vision. Ventuno-2 inventory: Docker + BRIO camera + 13 GiB
free RAM; Muni's old app parked (containers exited); whisper artifacts likely
on-board (D3 install source candidate).

**D1 retire her stack ✅ (2026-08-06, user authorized on Muni's behalf):** her
`stop.sh` reported the pidfile instance already gone; the original orphan (PID
3674, cmdline-verified `services.iq9_native.main`) was SIGTERM'd by exact PID.
`ss` confirms **1883 and 9001 free** — first time this hackathon; her `status.sh`
agrees ("not running"); her checkout left intact. Gate passed: fall inject →
opening say on our broker → false-alarm cancel, agent unaffected. Ports remain
11883/19001 through the demo (switch-back now unblocked as the documented
post-hackathon step — `infra/mosquitto.conf` header).

**D2 second Ventuno (bedroom):** inventory the board (may carry her old app —
park it) → QAIRT apt install (gotchas: `models/fall-detection/README.md`) →
Qualcomm VLM container Qwen3-VL-4B :9001 (`setup/ventuno-vlm/README.md`) →
deploy look + stream (NO vision — fall stays kitchen-only) → bedroom systemd
units (`--room bedroom`) → `config/house.yaml` bedroom source.
*Gate:* `dev/inject.py look` answered by BOTH rooms; live find returns
"found in bedroom…" for an object placed there; both heartbeats green.

**D3 voice on the kitchen board:** whisper QNN artifact from Muni →
`install_whisper_voice_ai_model.sh` → `deploy_voice_node.sh` → App Lab start,
config `config/voice-nodes/ventuno-kitchen.json`. **RAM gate:** `free -m`
before/after; headroom < ~0.8 GiB → `whisper-small-quantized` rollback;
record in `measurements.md`.
*Gate:* G3 in-the-room checklist verbatim (audible ask → spoken "I'm fine" →
pain check → resolved; silence path → SIMULATED call; responder phrase →
audible brief) + T6.4 wake soak (10 min room chatter → 0 false asks; 5 wake
trials ≥ 4/5).

**D4 close-out:** two full voice-first rehearsals with reset between (DEMO.md);
live contact-ack rehearsal (phones, "ok" reply — closes
`verify/T-contact-ack.txt` Part 2); packaging rebuild; **the single PR**
`voice-integration → main`; tag `voice-integrated`.

## Coordination items

- Muni: sign-off note sent (wake-gate reversal, validator relaxations, AGPL);
  whisper artifact for install; presence for D1.
- User: submission form by 1 PM Aug 7 (independent — `main` already satisfies
  the judging requirements); "devices available" signal starts D0.
