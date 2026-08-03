# Phone Exotica: What the Snapdragon Android Handset Can Uniquely Do for QNet Home (Aug 2026 sweep)

Scope: capabilities possible **on the phone** (Snapdragon 8-class, NPU) that could add genuine wow to QNet Home without becoming a bolted-on party trick — i.e., each idea is scored on whether it *proves* the crux (privacy-by-construction / never-transmit-raw-media, multi-device fabric, agentic in-room response) or just decorates it.

Cross-reference: `research/tech/mobile-role.md` already made hard calls for the MVP — push-to-talk over WebRTC, phone accelerometer fall-detection YES, phone-as-camera-node NO, phone-SLM-as-main-flow NO. Everything below is framed as *additive* to that scope, not a re-litigation of it, and I flag where an idea would need the team to knowingly override a prior decision.

---

## TOP 10 — ranked by (wow × crux-fit) / build-risk

### 1. Acoustic presence/breathing sensing via phone speaker+mic — camera-free "is the room occupied / is the child breathing" signal
**What it is:** A real, productized research lineage — not vaporware. UW's **BreathJunior** (UW Medicine + Allen School, spun out as **Sound Life Sciences, Inc.**) plays inaudible/white-noise acoustic chirps from a smart-speaker-class device and demodulates the reflected signal off a sleeping infant's chest to extract respiratory rate; validated against NICU vital-sign monitors on real babies. Sibling academic systems using the **exact same speaker+mic hardware a phone has**: **SonarBeat** (ACM, contact-free respiration via smartphone sonar), **Breeze** (ACM, real-time breathing-phase detection + biofeedback via phone mic only), **Wi-Tracker** (IEEE, ultrasound emitted by phone speaker, reflection received by phone mic, for airflow/breathing), and a 2026 MDPI paper "Smartphone-Based Acoustic Sensing for Breathing and Heartbeat Detection" confirming the technique is still active research as of this year.
**Why it's the #1 idea:** This is the single most direct, legible proof of "privacy-by-construction" available to the team. A phone (or later, a $5 speaker+mic module on an edge node) sitting on a nightstand can report `{"room":"kids_bedroom","presence":true,"breathing_rate_bpm":22,"event":"normal"}` as a semantic JSON event — **while physically incapable of transmitting audio content**, because the pipeline only ever computes a chirp cross-correlation, never decodes speech. That is a stronger privacy argument than "we chose not to send the video," because there's provably no microphone-content channel to the network at all if you architect it as chirp-in/reflection-out only.
**Feasibility in ~1 day:** Medium. The DSP (emit repeating FMCW/chirp near/at the edge of audible range, cross-correlate echoes, extract chest-wall periodicity) is well-published and there are open implementations to adapt (Breeze's algorithm is documented in enough detail to reimplement the core correlation in a few hours of Python/Kotlin). Main risk: getting a robust, demo-room-noise-tolerant signal in one day is the hard part, not the concept. Recommend building it as a **standalone kiosk demo** (phone taped to a crib mockup) rather than integrating into the main pipeline under time pressure — a working side-booth beats a flaky main-stage moment.
**Demo beat:** "This is the kids' room. There is no camera and no microphone-that-transmits-audio in this room. Watch the caregiver app light up with a breathing-rate trace anyway" — then show the phone's network traffic (or lack thereof) live, e.g. via a packet monitor, to hammer the point.

### 2. On-device speaker-turn / speaker-verification as the anti-deepfake consent gate for cloned-parent-voice
**What it is:** Qualcomm + Nexa AI + pyannoteAI announced (2026) that **pyannote's speaker-diarization-community-1 model now runs 100% on-device on Qualcomm NPU via NexaSDK ("Day-0 support")** — "who speaks when," across "phones, PCs, IoT, XR, automotive." There's also a community port of pyannote-audio's segmentation model running directly on Android (GitHub `pyannote/pyannote-audio` discussion #1773, APKs available), and a hosted variant "Pyannote-NPU" on ModelScope under NexaAIDev.
**Why it matters for QNet Home specifically:** The team's own scope has an ElevenLabs cloned-parent-voice feature for kids' rooms — the single most "trust us" element of the whole pitch, and the thing most likely to draw a "isn't this exactly the deepfake-risk everyone's worried about?" question from judges. Wiring an **on-device speaker-embedding/verification check on the caregiver's own phone** as the gate that must pass before the hub is even allowed to synthesize in the cloned voice turns that liability into the strongest Innovation-score beat in the deck: "the cloned voice cannot be invoked by anyone but the verified parent, and that verification never leaves their phone."
**Feasibility in ~1 day:** Medium-high if scoped narrowly — you don't need full diarization, just a one-shot speaker-embedding match (enroll once, verify on each cloned-voice trigger) using a small embedding model on-device (pyannote's segmentation/embedding model, or even a lighter ECAPA-TDNN-class model already common in these toolchains). The NexaSDK path is proven on Snapdragon NPU (announced Day-0); if it targets Windows-on-Snapdragon primarily, run it on the **PC hub** as the verification step, with the phone contributing the enrollment sample — still a legitimate "phone participates in the trust chain" story even if the embedding math runs on the hub.
**Demo beat:** Live: caregiver says "unlock story mode" → system verifies caregiver's voiceprint on-device → cloned voice activates. Then have a team member try the same phrase in a different voice → explicit on-stage rejection. This is a 20-second beat with outsized judge impact.

### 3. BLE RSSI room-presence using the edge nodes you're already deploying (no new hardware)
**What it is:** The Arduino UNO Q (QRB2210) ships with a **WCBN3536A radio: dual-band Wi-Fi 5 + Bluetooth 5.1**. Every edge node you're already placing in each room is, for free, a BLE beacon/scanner. Pair that with Android's **Ranging API (Android 16, `android.ranging`)**, which unifies UWB / BLE Channel Sounding / Wi-Fi NAN RTT / BLE RSSI behind one `RangingManager` — or, more realistically for a 1-day build, just raw BLE RSSI proximity (`BluetoothLeScanner`, no special permission drama beyond `NEARBY_DEVICES`).
**Why it matters:** Gives you "which room is the caregiver's phone in" as a **first-class semantic event**, generated from infrastructure you're building anyway — this is exactly the "multi-device fabric" crux: nodes that already exist for safety-sensing incidentally do presence/localization too, with zero extra sensors and no camera anywhere near the loop.
**Feasibility in ~1 day:** High for coarse RSSI-threshold "nearest node" logic (a few hours). Low-medium if you chase true UWB or BLE Channel Sounding precision — the UNO Q has no UWB radio, and BLE Channel Sounding needs Bluetooth Core 6.0 hardware on both ends (most 2025-26 flagships don't have it yet); don't attempt true cm-precision ranging in the time you have. Ship RSSI trilateration/nearest-node, not lab-grade ranging.
**Demo beat:** Caregiver walks from kitchen to nursery holding phone; a room-presence chip on the dashboard silently updates "caregiver: nursery" — then the agentic layer uses that fact ("caregiver is already in the room, skip the push notification, just speak locally") to visibly *change its own behavior*. That behavior change is the wow, not the localization tech itself.

### 4. GenieX Android app: the *same* on-device LLM/VLM runtime on phone as on the PC hub
**What it is:** Qualcomm's GenieX (the runtime QNet Home already uses on the PC hub) ships an Android reference app (`geniex.aihub.qualcomm.com/en/run/android`) requiring **Snapdragon 8 Elite or 8 Elite Gen 5**, running models via either the `llama.cpp` GGUF path (e.g. `unsloth/Qwen3-VL-2B-Instruct-GGUF`) or Qualcomm AI Hub's `qairt` path (e.g. `Qwen3-4B-Instruct-2507`), targeting **Hexagon NPU** with GPU/CPU fallback. Snapdragon 8 Elite Gen 5 specs: **~100 TOPS NPU (up from 40-45 TOPS prior gen), ~220 tok/s on-device LLM generation (vs ~70 tok/s prior gen)** — both figures reported this year.
**Why it matters:** "One runtime, one model family, three device classes (X Elite PC hub, 8 Elite phone, AIC100 offline eval)" is a clean, technically-verifiable slide for the 40-point Technical criterion — actual apples-to-apples tok/s-per-watt numbers across the fabric, not marketing.
**Feasibility in ~1 day:** High to stand up the app and get a Qwen3 tier answering text queries on-device on the phone; VLM (image) path exists in the reference app but has **no live camera integration documented** — treat any vision use as a manual, opt-in, single-shot capture, not continuous sensing (this deliberately avoids re-opening the "phone as camera node" decision the team already closed out as NO for the main flow).
**Demo beat:** Side-by-side tok/s counter: same prompt, same Qwen3 tier, running on the PC hub's Hexagon NPU and the phone's Hexagon NPU simultaneously, both fully offline. Optional stretch: a manual "caregiver holds phone up to something, gets an on-device VLM opinion, nothing leaves the phone" bonus utility — pitch explicitly as a *caregiver tool*, never as part of the always-on safety pipeline, to stay consistent with the team's existing no-phone-camera-in-main-flow stance.

### 5. Community QAI Hub ecosystem is vision-classic; the exotic stuff lives one layer out (NexaSDK, GenieX), not in the official sample gallery
**What it is:** `aihub.qualcomm.com/mobile` today only ships three official Android sample apps: super-resolution, image classification, semantic segmentation. The genuinely new-in-2026 audio/agentic capabilities (diarization, LLM/VLM chat) are arriving through **partner SDKs riding the same NPU stack** — NexaSDK (item 2) and GenieX (item 4) — not through Qualcomm's own sample-app repo.
**Why it matters:** Saves the team from burning a day hunting for an official "exotic" demo app that doesn't exist yet; point the search instead at the runtime layer.
**Feasibility:** N/A (this is a navigation note, not a build item).
**Demo beat:** None directly — informs where else to look.

### 6. Barometer-based floor detection as a cheap disambiguator for multi-floor homes
**What it is:** Most flagship Android phones (including Snapdragon 8-class devices) expose a barometric pressure sensor (`Sensor.TYPE_PRESSURE`). Differential pressure changes reliably signal floor transitions (stairs/elevator) in indoor-positioning literature.
**Why it matters:** If the demo house-in-a-box has more than one "floor" (even a curtained-off second area on a table), barometer + BLE room-presence together disambiguate "which floor, which room" without any additional sensor class — reinforcing the "many cheap, boring, privacy-safe signals fused together beat one camera" narrative.
**Feasibility in ~1 day:** Medium — the sensor read is trivial; getting a *reliable* threshold in a noisy expo-hall HVAC environment in one day is the risk. Treat as a stretch nice-to-have, not a headline beat.
**Demo beat:** Minor supporting detail only; don't lead with it.

### 7. Magnetometer/compass fingerprinting for indoor localization — mention, don't build
**What it is:** Commercial-grade indoor positioning (e.g., IndoorAtlas-style) uses magnetic-field-anomaly fingerprinting from the phone's magnetometer, calibrated via a walking survey of the space.
**Why it's ranked low:** Needs a calibration walk of the actual venue floor plan before it's useful — that's real setup time the team won't have, and a booth layout that changes hour-to-hour (as expo layouts do) breaks the fingerprint map.
**Feasibility in ~1 day:** Low. Do not build; noted for completeness only.

### 8. Phone-as-satellite bedside voice terminal — already scoped as "MAYBE" in mobile-role.md; the exotic upgrade is WebRTC-grade full-duplex + barge-in
**What it is:** The team already has a push-to-talk decision on record and a bedside-terminal "MAYBE." The frontier-in-2026 exotic upgrade path is full WebRTC voice: OpenAI's rebuilt WebRTC voice infrastructure is reported hitting **~400ms round-trip latency** for realtime voice with barge-in this year — a concrete external benchmark to cite if the team decides late in the week that a from-scratch WebRTC upgrade is worth the risk for the finale demo room specifically.
**Why it's ranked here, not higher:** It directly conflicts with a decision already made ("choose push-to-talk, not WebRTC" — mobile-role.md §5) for good reasons documented there (4-day build risk). Only revisit if push-to-talk is rock-solid by day 3 and there's spare capacity, and even then, scope it to one showcase room, not the whole fabric.
**Feasibility in ~1 day:** Low-medium (this is a multi-day investment, per the team's own prior analysis).
**Demo beat:** Full-duplex interrupt-mid-sentence in the finale room, if pursued — genuinely wow, but explicitly gated on spare capacity.

### 9. ML Kit GenAI APIs / Gemini Nano via AICore — on-phone smart summarization of the day's semantic-event log, fully offline
**What it is:** As of 2026, Android's ML Kit GenAI APIs (backed by Gemini Nano/AICore) are being opened to third-party developers more broadly (reports of Android 17 removing the walled-garden restriction, zero per-inference cost, zero cloud round-trip), for tasks like summarization, proofreading, rewriting.
**Why it matters:** Could let the caregiver phone locally summarize "what happened in the house today" from the accumulated semantic JSON events into a natural-language digest, entirely offline, on a *second* on-device model family — a nice diversity point ("we're not religiously tied to one vendor's runtime; the fabric is heterogeneous by design").
**Feasibility in ~1 day:** Medium — device-dependent. AICore/Gemini Nano availability is not guaranteed across all Snapdragon Android OEM builds; verify on the actual hackathon kit device before committing any demo minutes to it. If it's not present on your specific phone, this collapses to zero feasibility — check first, build second.
**Demo beat:** "Good night, here's your day" digest, generated locally on the phone from events the fabric already emitted — reinforces "semantic JSON events are useful raw material for more than just alerts."

### 10. PocketPal AI and similar community on-device SLM chat apps — useful as a fallback reference, not a differentiator
**What it is:** PocketPal AI (Android/iOS, 1M+ downloads) runs Danube, Phi, Gemma-2, Qwen locally, "100% private, no cloud required," 6-8GB RAM. Confirms the "local SLM chat on a phone" pattern is mainstream enough that judges have likely seen it — meaning it is **not** a wow item on its own.
**Why it's ranked last:** Exactly because it's *not* exotic anymore — if the team was tempted to demo "look, an LLM chat running locally on the phone" as a standalone flex, that ship has sailed for a judging panel that's seen a dozen of these. The only way it adds value to QNet Home is wired into the fabric (item 4, GenieX, same-runtime-everywhere story) rather than shown in isolation.
**Feasibility:** High, but low marginal wow — don't spend a build slot on this in isolation.

---

## Honorable mentions swept and explicitly rejected/deprioritized

- **True UWB ranging** (Apple Nearby Interaction-equivalent on Android via `androidx.core.uwb` / Android 16 Ranging module): real, cm-precision, FiRa-standard — but needs a UWB radio on *both* ends, and the UNO Q edge nodes have no UWB chip (BLE 5.1 only). Would require adding a UWB dev board per room, which is new hardware you don't have days for. Use BLE RSSI (item 3) instead.
- **BLE Channel Sounding** (Bluetooth Core 6.0 distance-ranging feature, rolling out on very recent flagships): more precise than RSSI, but hardware support on both the phone and any edge node is not guaranteed on this kit — don't gate a demo beat on hardware you haven't verified in-hand.
- **WiFi CSI-based sensing** (through-wall presence/vital-signs via WiFi channel state info): compelling on paper, but requires either rooted Android access to raw CSI or specialized WiFi chipsets most phone WiFi stacks don't expose to apps — not buildable in days on stock Android.
- **Phone as always-on camera sensing node**: explicitly out of scope per the team's own prior decision (mobile-role.md §6.4); only reappears above (item 4) as an opt-in, manual, single-shot caregiver *tool*, never as a continuous sensor.

---

## Sources

- [BreathJunior — UW News](https://www.washington.edu) (UW Medicine / Allen School infant-breathing acoustic sensing via smart speaker; NICU validation; commercialized via Sound Life Sciences, Inc.)
- [Smartphone-Based Acoustic Sensing for Breathing and Heartbeat Detection — MDPI Sensors 2026](https://www.mdpi.com/1424-8220/26/14/4591)
- [Respiratory Biofeedback Using Acoustic Sensing with Smartphones — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352648323000156) (Breeze)
- [SonarBeat: Sonar Phase for Breathing Beat Monitoring with Smartphones — ACM](https://dl.acm.org/doi/10.1145/3436822)
- [Wi-Tracker: Contactless Breathing Airflow Detection on Smartphone — IEEE Xplore](https://ieeexplore.ieee.org/document/9951134)
- [Breeze: Smartphone-based Acoustic Real-time Detection of Breathing — ACM](https://dl.acm.org/doi/10.1145/3369835)
- [Nexa AI / pyannoteAI / Qualcomm — on-device speaker diarization on Qualcomm NPU (LinkedIn announcement)](https://www.linkedin.com/posts/nexa-ai_pyannotes-brand-new-model-speaker-diarization-community-activity-7378819382237388800-DWrN)
- [Pyannote-NPU model card — ModelScope (NexaAIDev)](https://www.modelscope.cn/models/NexaAIDev/Pyannote-NPU)
- [Run pyannote-audio on Android — GitHub discussion](https://github.com/pyannote/pyannote-audio/discussions/1773)
- [NexaSDK — GitHub](https://github.com/NexaAI/nexa-sdk)
- [Qualcomm AI Hub GenieX — Android Quickstart](https://geniex.aihub.qualcomm.com/en/run/android/quickstart)
- [Qualcomm AI Hub GenieX — Android Install](https://geniex.aihub.qualcomm.com/en/run/android/install)
- [Qwen3-4B model card — Qualcomm AI Hub](https://aihub.qualcomm.com/mobile/models/qwen3_4b)
- [Qualcomm AI Hub — mobile sample apps](https://aihub.qualcomm.com/mobile)
- [Android Ranging API (Android 16) — Android Developers](https://developer.android.com/develop/connectivity/ranging)
- [Ultra Wideband — Android Open Source Project](https://source.android.com/docs/core/connect/uwb)
- [Ultra-wideband (UWB) communication — Android Developers](https://developer.android.com/develop/connectivity/uwb)
- [UWB Nearby Interaction with phones — NXP AppCodeHub GitHub](https://github.com/nxp-appcodehub/dm-uwb-nearby-interaction-with-phones)
- [OpenAI WebRTC overhaul cuts voice AI latency to ~400ms — reported 2026]
- [ML Kit GenAI APIs (Gemini Nano / AICore) — Google for Developers](https://developer.android.com) (ML Kit GenAI documentation)
- [PocketPal AI — Android on-device SLM chat app](https://play.google.com) (Google Play listing)
- Internal: `research/tech/mobile-role.md` (existing team decisions on phone scope — push-to-talk vs WebRTC, accelerometer fall detection, no phone-camera main-flow)
- Arduino UNO Q hardware notes: QRB2210 SoC, WCBN3536A radio module — Wi-Fi 5 dual-band + Bluetooth 5.1 (per Arduino UNO Q product documentation)
