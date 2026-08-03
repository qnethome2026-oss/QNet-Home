# QNet Home — Project Scope v1.0

*Synthesized 2026-08-03 from 16 research reports (50+ hackathons, 8 tech deep dives — full details in `research/`). This is the decision document. Deadline: Aug 7, 1:00 PM.*

---

## 1. What the research changed (read this first)

**About the event itself — this exact hackathon has run before.** Princeton (Sep 2025), MIT (Jan 2026), Columbia (Feb 2026), Bengaluru (Jul 11–12, 2026), Noida (Jul 18–19, 2026) — identical 4-device kit. The Noida winner **Dragverse** won by making each device do one visibly distinct, non-interchangeable job in a single causal chain, and sibling editions literally have a "Multi-Device Innovation" judging lane. Winning writeups at Qualcomm's sibling events all **name exact models + which NPU runs them + a hard number** ("Qwen2.5-7B via QNN on Hexagon NPU", "2× speedup, 35% power reduction"). That is the judging culture we are playing to.

**Fall detection is confirmed commodity** (4+ hackathon clones, commercial products, 430-star GitHub repos). It stays in the demo but as *"the cheapest pluggable sensing skill that proves the architecture"* — never as the headline.

**Our genuine white space (verified against ~60 hackathons + full competitor scan):**
1. **A local home-AI stack on Snapdragon at all.** Frigate (34.8k stars) supports NINE detector backends — Coral, Hailo, OpenVINO, TensorRT, even Apple NPU — and **zero Qualcomm**. Home Assistant doesn't target Copilot+ PCs. Screenshot-able gap.
2. **The agentic response layer.** Every eldercare competitor (SafelyYou, Sensi.AI, AltumView, ha-llmvision) is alert-only — nothing *speaks to the person*, reasons about context, or holds a two-way "Are you OK? — I'm fine, cancel" conversation locally.
3. **Consent-based cloned-parent-voice intervention, sensor-triggered, on-device.** Zero prior art across all sweeps (closest: KindredMind = reactive phone-answering; Coemo = storytelling). This is the demo moment nothing else in the space has shown.
4. **Multi-node semantic-event fusion across heterogeneous silicon** — all fall-detection prior art is single-device.

**Honesty guardrails (judges can check):** HA has had `assist_satellite.start_conversation` since 2024.10 — credit it; our claim is the *policy is decided by a local model, not YAML*. Alexa+ does proactive camera conversations — but cloud, front-door, subscription. Amazon killed Alexa Together; Google gates Gemini for Home behind $10/mo — "the cloud+subscription eldercare model failed; local-first has no monthly fee" is our business slide.

---

## 2. The pitch (one paragraph)

**QNet Home is a privacy-first ambient safety fabric for the home.** Dragonwing edge nodes see and hear locally and publish only tiny semantic JSON events — never video, never audio. A Copilot+ PC agent running entirely on the Hexagon NPU reasons over those events, speaks to the person in the room (two-way, with barge-in and "I'm fine, cancel"), escalates to a caregiver's phone, and — with recorded consent — can intervene in a child's room *in the parent's own voice*, watermarked and verifiable. Every scenario is a pluggable "sensing skill"; the architecture, not the detector, is the product. Sense on Dragonwing, reason on X Elite NPU, respond through the room, escalate to the phone, red-teamed by a 70B on Cloud AI 100.

Named sub-agents for legibility (proven winner pattern): **Sentry** (edge perception), **Guardian** (hub reasoning), **Herald** (voice/response), **Oracle** (cloud red-team).

---

## 3. Architecture — device by device (each does what only it can)

### Arduino UNO Q ×2 — "Sentry" edge nodes
Reality check from research: **no NPU** (4× A53 @2.0 GHz + Adreno 702; QRB2210 datasheet has zero occurrences of "Hexagon/NPU"). Plan accordingly:
- **3-stage detection cascade** (this IS our resource-utilization story): (0) STM32 MCU always-on mic RMS gate at ~mW → (1) continuous lightweight person detection/tracking at 320×240 ≥15 fps with bbox heuristics (aspect-ratio flip <0.6→>1.2 in <1.5 s + centroid drop >25% + static >5 s — the proven Hailo-community dual-condition trick) → (2) 3-second burst of pose model on cropped ROI only, via **Edge Impulse "Linux Arduino UNO Q (GPU)" target** (Adreno-accelerated — the only legitimate accelerator claim on this board; A/B it vs CPU and publish ms/inference).
- **Audio events:** the shipping `audio_classification` brick (glass-break) + `keyword_spotting` brick ("help" wake-gate). Optional `hand-gestures` brick = thumbs-up "I'm OK" no-speech confirm.
- **GStreamer** is native (libcamerasrc; our team's professional edge). Free measurable win: replace the stock brick's JPEG-encode→TCP→JPEG-decode round trip with one tee'd pipeline; publish the CPU% saved.
- Publishes `SemanticEvent` JSON over **MQTT**; plays PCM streamed from hub (ALSA, 30 ms periods, barge-in queue); hosts a tiny **FastMCP server** exposing `node.speak()` / `node.snapshot_pose()` as discoverable tools.
- Hardware: **4 GB SKU**, powered USB-C hub (bring 2–3 spares — known compatibility issue), **USB conference speakerphone per node** (mic+speaker+AEC in one), USB UVC camera. Use `/dev/video2` (video1 is the decoder!).
- Policy: raw video/audio never leaves the node. On escalation only, ONE cropped frame may cross the LAN to the hub (in-home boundary) — disclosed in UI.

### Copilot+ PC — "Guardian" + "Herald" hub
- **LLM runtime: GenieX** (`github.com/qualcomm/geniex`, BSD-3, signed ARM64 installer, Microsoft-signed HTP — no test-signing hacks). `geniex serve` = OpenAI-compatible API on :18181 with tool calling + JSON-constrained output. Measured on X Elite NPU (w4a16, ctx 4096): **Qwen3-1.7B 42 tok/s (triage) → Qwen3-4B 23 tok/s (reasoning) → Qwen3-VL-4B 21 tok/s (only on ambiguity, over the escalation snapshot)**. Tiered = both fast and a defensible optimization story.
- **Reliability pattern (research-mandated):** small models hit 87.9% single-turn but only 22% multi-turn tool calling → **a deterministic state machine decides WHAT to do; the LLM decides WHAT TO SAY + one tool call per turn**, JSON-constrained. Fully defensible on stage ("the trigger logic is legible, not vibes").
- **STT:** Zipformer streaming (9.7 ms/chunk, enables barge-in) for live conversation; Whisper-Base (NPU, ~600× realtime) for transcripts/logs. **TTS:** Kokoro-82M fp32 ONNX CPU (warm neutral voice; note: int8 is 2.2× SLOWER on ARM64 CPU — ship fp32, it's a great counter-intuitive slide) + Windows SAPI as never-fails floor + QAI Hub PiperTTS-EN on NPU (61.5 ms, 100% NPU-resident) if Voice AI SDK access works — the "15× speedup" slide.
- **Cloned parent voice (OPT-IN feature, child scenario only — team decision 2026-08-03):** the elder and system flows always use the neutral warm voice; cloning is a per-household opt-in that parents enable for kids' rooms. Engine: **ElevenLabs standard/instant cloning (cloud, feature-flagged)** — ~75 ms model latency, sub-second to first audio for live free text. At registration (consent recording) we also pre-generate a **local phrase bank** of the canned intervention lines via the same API, so the common case plays at 0 ms and keeps working with the router unplugged; live cloud synthesis is only needed for free-text parent messages. Local cloning (Chatterbox, measured RTF 3.3) drops to a stretch experiment. Every cloned utterance is watermarked locally before playback (**AudioSeal**, MIT, no torchaudio needed — verified detect=1.0 with kokoro negative control=0.0 on this machine); ship `qnet verify <file>` and let a judge run it. **EU AI Act Art. 50 became applicable Aug 2, 2026 — one day before the hackathon** — we comply (machine-readable marking + disclosure) and no other team will have thought of it. Pitch framing: "voice identity is optional, consented, revocable, expiring, and only ever used for the kids' rooms."
- **Telemetry HUD (the 40-point widget):** live per-process NPU % (verified PowerShell counter: `GPU Engine(*luid_<npu>*engtype_Compute)`), battery `DischargeRate` mW on-battery, per-stage latency waterfall (detect→event→decision→first audio), **bytes-per-event vs. the 12.4 MB of video an equivalent cloud camera would have sent**, tokens/joule NPU vs CPU.
- **Packaging:** PyInstaller 6.21 (native win_arm64 wheel, verified) → MSIX via makeappx/signtool (installed, verified). Known landmines documented: no torch on PyPI (use pytorch.org index), no ctranslate2/faster-whisper, opencv-python build fails. Pre-bundle all model weights (a 4 GB first-run download would wreck the 20-pt Deployment score). **Reboot before demo** (Copilot+ features can hold the NPU → QNN error 5005).

### Android phone — "Caregiver" node
- **Native Kotlin + Compose** (PWA fatally blocked: FCM-only push, no LAN foreground service, no mic on http://). **targetSdk 36** (37 makes LAN access a runtime permission that fails as silent timeouts). Foreground service type `connectedDevice` (no 6-hour cap). Own WebSocket to hub — works with the router unplugged.
- Features: actionable alert (Acknowledge / Talk / Escalate), event timeline, **push-to-talk half-duplex into the room** (VOICE_COMMUNICATION source = hardware AEC, PCM over the same WebSocket, ~2.5 h vs a day for WebRTC — and "hold to talk to Mom" demos better), **parent-texts-the-system via RemoteInput directly in the notification** → hub SLM rewrites it into a calm first-person line → speaks in parent's voice in the right room.
- **The phone is also a sensor node:** accelerometer fall detection publishing the IDENTICAL SemanticEvent schema onto the same bus (~1.5 h, zero models). It answers the judge's inevitable question — "what about the bathroom, where you'd never put a camera?" — and proves the bus is device-agnostic. 10-second "I'm fine" cancel countdown = the honest false-positive answer.
- First 30 min with kit phone: `adb shell getprop ro.soc.model` + check for Play Services (if it's a QRD without GMS, FCM is impossible — our local-first push becomes *the only thing that works*, say so).

### Qualcomm AI Cloud 100 — "Oracle" (off the hot path, by design)
- **P0 — digital-twin red-team rig:** Llama-3.1-70B on AI 100 Ultra generates hundreds of adversarial synthetic event traces in our exact schema (fall vs dropped pan vs rough play vs pillow fight), then GRADES the local SLM's decisions → committed `docs/eval-report.md` with confusion matrix + false-alarm rate before/after prompt tuning. Privacy airtight (cloud never sees home data), zero demo-day network risk, and it produces the tests the rubric explicitly rewards. Tagline: *"We red-teamed our home agent with a 70B on AI 100 Ultra."*
- **P1 — opt-in "second opinion" where THE REDACTION is the feature:** only a schema-enforced `RedactedIncident` (enums + floats, no frames/audio/names) can cross the boundary — enforced by a unit test, rendered live in the UI with its byte count next to "what a camera-cloud product would have sent." Default OFF; degrades to local-only when the router is unplugged.
- Access verified: Imagine API `https://aisuite.cirrascale.com/apis/v2`, stock `openai` client (**do NOT use the proprietary python-imagine-sdk — its EULA is incompatible with our required open-source license**). Stateless calls only (the API retains conversations — documented trust boundary). Cache every response to disk; 5 s timeout + local fallback. Day-1: ask organizers which endpoint we get + `GET /v2/models`.
- The killer comparison table, one script: same eval suite on local Qwen3-4B (NPU) vs 70B (AIC100) — tokens/s, TTFT, joules/decision, accuracy, side by side. Proves the local path is sufficient instead of asserting it.

---

## 4. Scenario skills (the pluggable layer)

| Skill | Sensing | Tier | Notes |
|---|---|---|---|
| Fall + no-response | pose cascade (node) | **MUST** | the proven loop: detect → converse → escalate |
| Audio distress | glass-break brick, loud-sound, "help" keyword | **MUST** | second modality = honest "sensor fusion" claim |
| Parent-voice intervention | kid events / parent text | **MUST** | THE demo moment; **opt-in per household, kids' rooms only** (elder flow always uses the neutral voice); consent + watermark UX on screen |
| Open-vocabulary hazard watch | YOLO-World on hub over escalation snapshot | **SHOULD** | parents type "scissors, stove, medication" in config — no retraining. 264 ms text encoder runs once; 110 ms/frame after. Genuinely novel feature |
| Phone accelerometer fall | phone IMU | **SHOULD** | third device class on the same bus |
| Vocal-emotion triage | prosody classifier in the "Are you OK?" loop | **COULD** | proven winner pattern (DispatchAI) |
| Night wandering / freeze-game "fun mode" | same skeleton pipeline | **COULD** | fun mode = memorable 20-second beat reusing the pipeline (HailoGames pattern) |
| Offline response coaching (emergency knowledge pack) | knowledge layer — no sensor | **SHOULD** | `skills/emergency/` shipped: 6 lay-rescuer skills (CPR metronome, recovery position, safe get-up), 16.4 KB total, state machine picks the file, LLM phrases it. Wiring ≈ 1–2 h. See `research/tech/offline-skill-packs.md` |

**Knowledge skills (new layer, 2026-08-03):** sensing skills detect; knowledge skills know what to do next. Measured: the entire authoritative first-aid corpus (IFRC 2020 + AHA 2020 + *Where There Is No Doctor*, 1,011 pages) is **2.5 MB of text**; one distilled scenario skill is ~600 tokens — fits whole in the 1.7B triage context, no RAG. Extends the router-unplug beat: offline detection AND offline "what to do". Full analysis: `research/tech/offline-skill-packs.md`.

Kid-monitoring headline stays (white space: nobody targets 3–9 y/o behavioral danger + spoken intervention), but per research: **pitch ONE primary story (elder) and show the kid scenario as the "same architecture, new skill" proof**, not a 50/50 split.

---

## 5. Scope layers

**MUST (demo-critical, days 1–3):** MQTT SemanticEvent bus + 2 Sentry nodes (cascade + audio brick) + GenieX tiered SLM orchestration with state machine + Kokoro TTS two-way loop with barge-in & "I'm fine, cancel" + caregiver app (alerts, PTT, parent-text) + cloned-voice phrase cache with consent flow + watermark + telemetry HUD + AIC100 eval rig + MSIX + README.
**SHOULD (day 3–4):** YOLO-World hazard config, phone IMU node, redacted cloud second-opinion (live), router-unplug demo beat, network-monitor privacy proof, eval-report with before/after numbers.
**COULD (only if ahead):** OpenClaw interop (our tools as an MCP server + SKILL.md — 2 h, nice "ecosystem" slide since Qualcomm's blog endorses OpenClaw), vocal-emotion triage, fun mode, ggwave acoustic-fallback beat.
**WON'T:** OpenClaw as the orchestrator (its own docs demand "$30k+ of Mac Studios" for local-model agents, ctx 196k — two orders of magnitude off our budget; full analysis in `research/tech/openclaw.md`), local live cloned synthesis (Chatterbox RTF 3.3 — cloning is now ElevenLabs cloud, opt-in, child-only), voice cloning on AIC100 (no TTS exists there — verified 3 ways), Phi Silica (being removed Nov 2026), raw llama.cpp-Hexagon on Windows (test-signing hell), fine-tune-in-cloud-run-on-edge (no weight export exists).

---

## 6. Demo script (4 minutes, every beat earns points)

1. **Cold open (30 s):** mannequin/teammate falls in "kitchen." HUD visible: event JSON (~400 bytes) crosses LAN → Guardian reasons on NPU (utilization spikes on screen) → Herald speaks from the room speaker **< 3 s after the fall**: "I saw you fall, are you OK?" — teammate: "I'm fine, cancel" → barge-in, stand-down. Latency waterfall on screen.
2. **Real escalation (45 s):** second fall, no response → VL confirm on snapshot → caregiver phone buzzes (actionable alert) → judge holds PTT and talks into the room through the node.
3. **Privacy proof (30 s):** packet capture on screen — only JSON on the wire; "a cloud camera would have sent 12.4 MB." **Unplug the router. Do beat 1 again. Everything still works.**
4. **The wow (45 s):** kid's room node reports rough play near the "hazard list" (typed live: "scissors"). Parent (judge's volunteer) gets the alert in a fake meeting, types "Sweetie, put those down, I'll be home soon" into the notification → the room speaks it **in the parent's registered voice**. Then run `qnet verify` on the recording — watermark detected; on a real recording of the parent — not detected. Mention EU AI Act Art. 50 (applicable since *yesterday*).
5. **The architecture close (60 s):** name each device and its irreplaceable job; the CPU-vs-NPU / local-vs-70B comparison table; "swap the sensing skill, same fabric" + eval-report red-teamed by AI 100 Ultra.

---

## 7. Day-by-day (team of 3–5)

- **Day 1 (Aug 3, rest of day):** kit triage (phone getprop, AIC100 endpoint email, UNO Q flash + camera + speakerphone), GenieX pull + serve + first tool call, Kokoro TTS hello-world, MQTT bus + event schema PR, ElevenLabs cloning spike (verify instant-clone tier + generate first phrase bank), Edge Impulse GPU-vs-CPU A/B on node. **PyInstaller→MSIX hello-world spike (packaging risk dies today).**
- **Day 2:** Sentry cascade end-to-end → hub state machine → TTS out (the MUST loop closes today); Kotlin app skeleton + WebSocket alerts; consent recording + phrase cache; HUD counters.
- **Day 3:** two-way voice with barge-in; PTT; parent-text flow; AIC100 eval rig + first eval-report; second node + second room; YOLO-World if on schedule.
- **Day 4 (Aug 6):** freeze features noon. Benchmark table run (all numbers), packaging final, README/license/tests, demo rehearsal ×3 including router-unplug, video recording as backup.
- **Aug 7 morning:** buffer + submission by 1:00 PM. Nothing new after Day 4 noon.

## 8. Rubric self-check
- **Technical 40:** tiered NPU models with named tok/s, cascade energy story, live NPU%/mW HUD, tokens/joule, bytes-vs-video ratio, quantization-tradeoff slide (w8a16 for detection, fp32-beats-int8-on-CPU counter-example), eval-report.
- **Innovation 25:** response layer + cloned-voice intervention + open-vocab hazards + semantic-event fabric; honest prior-art slide (Frigate gap screenshot).
- **Deployment 20:** MSIX with bundled weights, setup wizard (discover nodes → name rooms → pair phone → record consent voice), from-scratch README tested by a teammate who didn't write it.
- **Presentation 15:** named agents, one-sentence pitch, rehearsed live beats + backup video, architecture diagram.
