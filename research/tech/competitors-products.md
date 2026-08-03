# QNet Home — Prior Art & Competitive Landscape

*Research date: 2026-08-03. Author: research agent. Purpose: let us claim uniqueness **honestly** in front of expert Qualcomm judges, and know exactly which claims will get shot down.*

> Method note: WebSearch budget for this session was exhausted, so verification was done via direct page fetches plus a search proxy (`lite.duckduckgo.com`) and the GitHub API (`gh`) for repo liveness. Every claim below is tagged **[verified]** (I fetched the source this session), **[reported]** (secondary source / search snippet), or **[unverified]** (from prior knowledge, needs a 2-min check before we put it on a slide).

---

## 0. TL;DR — the one thing to internalize

Every *individual* ingredient of QNet Home already exists in the market:

| Ingredient | Who already ships it |
|---|---|
| Camera AI fall detection, 99%+ claimed accuracy | SafelyYou, Kami Fall Detect |
| Privacy-by-architecture eldercare (no video leaves / no camera at all) | Vayyar Care (radar), Sensi.AI (audio-only), Origin AI (Wi-Fi CSI) |
| Proactive, system-initiated conversation with a person | ElliQ (elder companion), **Alexa+ Greetings on Ring doorbells** |
| Local LLM reasoning over camera events | Home Assistant + LLM Vision (1.4k★), Frigate GenAI descriptions |
| Local wake-word → STT → LLM → TTS voice loop | Home Assistant Assist + Voice PE; Willow |
| System-initiated voice conversation as an API primitive | HA `assist_satellite.start_conversation` (since 2024.10) |
| Cloned parent voice speaking to a child | Takara Tomy "Coemo" storytelling speaker; KidsTime AI |
| Cloud LLM narrating what a camera sees | Gemini for Home (Oct 2025), Ring Video Descriptions |

**Nothing ships the composition**: a *fully local, NPU-accelerated, multi-device* loop where distributed sensors emit **semantic events** (not video), a local agent **decides** on a multi-step response, and then **holds a two-way spoken conversation in the room** — optionally in a consented familiar voice — with a measurable latency/bandwidth/energy budget. That composition, plus the Snapdragon-silicon story, is our claim. See §7 for the three defensible claims and §8 for the claims to *drop*.

---

## 1. Commercial elder-monitoring

### 1.1 SafelyYou — the serious incumbent (camera AI + human clinicians)
- Wall-mounted camera + "SafelyYou Guardian" devices (sensors, pendants, buttons) in **senior-living communities** (assisted living / memory care), **not private homes**. **[verified]**
- Claims **>99% accuracy** detecting "on-the-ground events"; a partner community blog cites **99.5%**. **[verified / reported]**
- Claimed outcomes: **45% fall reduction in year 1, 80% ER-visit reduction, +174 days average length of stay, up to $100k NOI uplift per community**. **[verified from safely-you.com]**
- Workflow: staff alerted in seconds → staff watch the fall clip in the **SafelyYou Discover** web portal → **SafelyYou Insight** has remote RNs/OTs/PTs review clips for root-cause analysis; they claim **600k+ on-the-ground events** reviewed. NIA (NIH) grant-funded. **[verified/reported]**
- **What they DON'T do:** nothing speaks to the resident. No two-way voice, no reassurance, no conversation, no agentic escalation ladder. Video **is** retained and **is** reviewed by humans in a cloud portal — the privacy model is "trusted clinicians", not "no video leaves the building". Processing location is not disclosed publicly. B2B enterprise sale, demo-request pricing.
- **Gap we fill:** the response layer, and true no-video privacy. Also consumer/home deployability (one .EXE + two $50-class boards vs. an enterprise contract).

### 1.2 Vayyar Care — radar, "no camera, no sound"
- Israeli company; wall-mounted RF sensing (Vayyar's core technology is **4D imaging radar**; the product page only commits to "records the daily life of your residents **without camera or sound**"). **[verified for the marketing claim; radar specifics [unverified] on that page]**
- Detects **falls**, unusual movement patterns, behavioural trends → immediate staff alerts + analytics for staffing/NOI. Enterprise senior-care facilities; demo-request pricing. **[verified]**
- **What they DON'T do:** zero voice interaction, zero conversational response, no LLM reasoning, no semantic multi-modal fusion. Alert-and-dashboard only.
- **Walabot HOME** was Vayyar's consumer wall-mounted fall detector (~$150 + monitoring subscription); consumer availability appears to have ended. **[unverified — check before mentioning]**
- **Gap we fill:** radar is a *better sensor* than our camera for privacy optics, but it is a dead-end for *situational understanding* — radar can't tell you the person is reaching for a chair, that a knife is out, or that a child is climbing a bookshelf. Our semantic-event abstraction is sensor-agnostic; say out loud that radar is a drop-in future node.

### 1.3 Amazon — Alexa Together (dead) → Alexa Emergency Assist → Alexa+
- **Alexa Together was discontinued.** Amazon's own forum answer states "effective **June 25, 2024**, Alexa Together will no longer be supported", pointing users to **Alexa Emergency Assist**; some third-party blogs say May 2025. Use the safe phrasing: *"Amazon shut down its eldercare subscription (Alexa Together) in 2024 and replaced it with a much thinner emergency-calling add-on."* **[reported, conflicting dates]**
- **Alexa+** (generative-AI Alexa) announced **Feb 2025**, expanded to the web via Alexa.com **Jan 2026**, generally available to everyone in the U.S. **Feb 4, 2026**. Cloud. **[verified via Wikipedia]**
- **Alexa+ Greetings** (with Ring): Alexa **proactively speaks to and converses with a visitor at the door**, recognizes delivery personnel, gives package instructions; uses Ring **Video Descriptions** to know who's there, plus **Familiar Faces** for personalized welcomes. **[verified/reported — aboutamazon.com, ring.com/support, PCWorld]**
- **This is the single most dangerous piece of prior art for us**, because it is "AI sees a person and talks to them, unprompted, in natural conversation." Our honest differentiators vs. it: (a) it's **100% cloud** (Ring video goes up, Alexa+ reasons in AWS), (b) it's at the *front door* / commerce context, not an in-home *safety* loop, (c) no distributed multi-node semantic fusion, (d) no NPU/latency/energy story, (e) it can't speak in *your* voice.
- **Signal to exploit:** the biggest player in the space *killed* its eldercare product. Aging-in-place is under-served precisely because the cloud/subscription model didn't work — a local-first architecture with no per-month cloud cost is a legitimate business argument.

### 1.4 Google — no fall detection in the home; cloud Gemini instead
- **Gemini for Home** launched **October 2025**, replacing Google Assistant on Nest devices: natural-language **AI descriptions of camera events**, conversational video-history search, summaries; **Gemini Live** for hotword-free multi-turn conversation. Advanced features gated behind **Google Home Premium ($10/mo or $100/yr)**, which replaced Nest Aware. **[verified/reported]**
- New Nest Cams "built for Gemini" (2K HDR, wider FOV). **[reported]**
- **No fall detection for elderly on Nest cameras/hubs** appears in any 2025–2026 material. **[reported — searched specifically, nothing found]**
- Google's fall detection lives on the **wrist** (Pixel Watch Fall Detection / Personal Safety) and its Soli-based Nest Hub work was **sleep sensing**, not falls. **[unverified detail, safe to state generically]**
- **Gap we fill:** Google proves the market wants "the camera explains what it saw in words" — and does it in the cloud, for a subscription, with no ability to act or converse in-room about a safety event. We do the same class of reasoning on a 45-TOPS NPU with no subscription and no upload.

### 1.5 Apple Watch — the gold-standard wearable baseline
- Series 4 and later / SE / Ultra: hard-fall detection from wrist IMU; taps + alarm; if the wearer is **immobile for ~60s** it auto-dials emergency services and messages emergency contacts. **[unverified detail level — Apple support page fetch was truncated; state generically]**
- **What it DON'T do:** requires the device to be **worn and charged** (the #1 real-world failure mode for elders — the reason camera/radar vendors exist), no environmental context (what room, what hazard, was there a second person), no reassurance, no situational reasoning, no kid use case.
- **Use in the pitch:** "the best-selling fall detector in the world doesn't work if it's on the nightstand." That single line justifies ambient sensing without insulting the incumbent.

### 1.6 Kami Fall Detect (Kami Vision / Kami Home)
- Camera-based **Vision AI** fall detection marketed for aging-in-place and businesses; "no pendant, watch, or bracelet"; 24/7 live view, low-light detection, smart alerts (people/vehicle/animal), cloud storage, emergency-response service tie-in. **[reported — product pages render via JS, so only snippets verified]**
- Positions explicitly against wearables: claims "better fall detection and root-cause analysis than traditional wearables, alerts, and bed rails."
- **What they DON'T do:** no in-room conversational response; cloud storage + cloud alerts; consumer camera trust problem (a camera in the bedroom that streams to a vendor cloud).
- **Gap we fill:** identical use case, opposite privacy architecture, plus the response loop.

### 1.7 Sensi.AI — the closest thing to our "semantic events, no video" thesis
- **Audio-only** "care pods" placed in the home; proprietary audio analytics detect **falls, pain, cognitive changes, care anomalies**, with transcripts and family alerts; markets itself as the *"world's first in-home virtual care agent"* and now as an **"Agentic Operating System for Senior Care"** with named agents ("Olly" for operations, "Sally" for growth). HIPAA-compliant; sells to **home-care agencies** — claims coverage of **>80% of major U.S. home-care networks**. **[verified/reported]**
- **What they DON'T do:** the "agents" are **back-office/ops agents for the agency**, not an agent that talks to the senior. No voice interaction with the senior is described. No vision. Processing location undisclosed (HIPAA cloud strongly implied). B2B.
- **Why this matters to us:** they own the phrase "in-home virtual care agent" in the *cloud/B2B* framing. We must be precise: ours is an **on-device agent that intervenes with the person in the room**, theirs is a cloud agent that produces insights for a care agency. Also note they chose audio-only for privacy — a strong external validation of the "sense richly, transmit semantically" idea.

### 1.8 Origin Wireless / Origin AI — Wi-Fi sensing
- "AI SENSING" turns existing Wi-Fi into a sensor using **100% uncompressed CSI**; products **TruShield** (home security) and **TruPresence**; motion and human-presence detection everywhere, no added hardware. Investors/partners include **Verizon Ventures, Alarm.com, SCOA**. **[verified]**
- Fall detection and breathing monitoring are part of the wider Wi-Fi-sensing narrative but were **not** substantiated on the site content I fetched; 802.11bf not mentioned. **[unverified]**
- **Gap we fill:** Wi-Fi sensing is coarse (motion/presence class), can't distinguish semantics, and has nothing to do with response. Again: a future sensing node, not a competitor to the architecture.

### 1.9 Cherish Health
- Radar-based ("Cherish Serenity") contactless fall + vitals monitoring, healthcare-oriented, FDA-clearance narrative. **[unverified — homepage fetch returned only nav chrome. Do not cite specifics without checking.]**

### 1.10 ElliQ (Intuition Robotics) — the proactive-conversation incumbent
- Tabletop companion "robot" (desk-lamp form factor, 8" screen) for older adults: photos, video calls, brain games, health/wellness reminders, and — critically — it is **proactive**: it initiates check-ins rather than waiting for a wake word, and sends caregiver alerts when it detects e.g. poor sleep or illness. **[verified/reported]**
- Cameras and microphones **always on**; explicitly **not a medical device**; **no fall detection**; positions itself as *less* intrusive than "a camera or sensor". Subscription-based (~$250 device + membership; free 12-month premium in the pre-order offer). **Washington State Medicaid covers ElliQ.** Heavy 2026 press (NYT Feb 2026; Fortune Jul/Aug 2026 comparing it to OpenAI's rumored device). **[verified/reported]**
- **What they DON'T do:** no environmental sensing/safety detection (no falls, no hazards), single-device (no multi-room, no distributed nodes), cloud LLM, no local NPU story, no cross-room orchestration, no familiar-voice cloning.
- **Why this matters:** ElliQ proves *proactive spoken interaction with elders is a validated, reimbursed product category* — great for our "this is a real market" slide — while leaving the entire *safety-triggered* branch empty. Frame QNet Home as "ElliQ's proactivity, triggered by SafelyYou-class sensing, running entirely on local silicon."

### 1.11 Addison Care / Electronic Caregiver
- Marketed as "Addison": care companion, health management, 24/7 physician consult, emergency response, telecare coaching; a **hybrid software + human** model; current site copy says **"non-invasive tools with no cameras or wearables required."** **[verified]**
- Historically Addison Care was pitched as a **3D animated virtual caregiver avatar** on in-home displays (the closest existing thing to "an AI character that talks to you about your health at home") — but the current site does **not** feature the avatar, fall detection, or vitals, suggesting a repositioning. **[unverified — the avatar history is from prior knowledge; the current-site absence is verified.]**
- **Gap we fill:** an avatar/persona with human call-center fallback is a service business; there is no local-silicon, sensor-triggered, multi-device story.

---

## 2. Privacy-first local home AI (the OSS field we're actually playing in)

*This is the section expert judges will probe hardest, because several of them will run Home Assistant at home.*

### 2.1 Frigate NVR — 34.8k★, extremely alive (last push 2026-08-03) **[verified via GitHub API]**
- "Complete and local NVR with realtime AI object detection for IP cameras", MQTT, deep Home Assistant integration.
- 2025–2026 feature set: **GenAI object descriptions**, **semantic search**, **GenAI review summaries**, **face recognition**, **license-plate recognition**, bird classification, custom state/object classification. **[verified]**
- **Semantic search runs fully locally** on **Jina CLIP v1/v2** embeddings (small variant quantized on CPU; large can use GPU). Frigate also now supports **triggers**: fire on thumbnail similarity to a reference image or on a description match → notify, add sub-label, or attach attributes. **[verified]**
- Detector/accelerator support: Coral EdgeTPU, **Hailo-8/8L**, Intel OpenVINO, **Apple Silicon NPU**, AMD ROCm, NVIDIA TensorRT/ONNX, Jetson, CPU, DeepStack/CodeProject.AI; community: MemryX MX3, **Rockchip RKNN**, Synaptics SL1680, DeGirum. Models: YOLOv3/4/7/9, YOLO-NAS, YOLOx, RF-DETR, D-FINE/DEIMv2, SSDLite MobileNet v2. **[verified]**
- 🔥 **Two hard gaps, both verified from the docs:**
  1. **No Qualcomm / QNN / Snapdragon / Hexagon detector exists. None. Not even community-tier.** Apple's NPU is supported; Qualcomm's is not.
  2. **No pose estimation at all** — "the documentation focuses exclusively on object detection." So *no* fall detection primitive.
- **What they DON'T do:** no TTS, no two-way audio, no voice, no agentic multi-step action, no fall detection, no cross-device semantic bus (MQTT events are camera-object events, not situational semantics).
- **How to use this:** the biggest, best-loved local-AI home vision project in the world has **zero Snapdragon NPU support and zero pose/fall capability**. That is a factual, checkable, judge-pleasing statement of the gap we're filling — and a concrete "future work / upstream contribution" line for the pitch.

### 2.2 Home Assistant — 89.7k★, the platform we will be compared to
- **Assist** (voice assistant) since **2023.2**; docs current at **2026.7.4**. Local STT/TTS, wake word, ESP32 satellites, **Voice Preview Edition** hardware, optional LLM conversation agent for conversational requests. **[verified]**
- **Ollama integration**: local conversation agent, **tool calling to control HA** — but explicitly **experimental**, with documented caveats: "only models that support Tools may control Home Assistant", "smaller models may not reliably maintain a conversation when controlling Home Assistant is enabled", expose **fewer than 25 entities**. No vision/image input documented for the Ollama integration. **[verified]**
- ⚠️ **`assist_satellite.announce` and `assist_satellite.start_conversation` exist and have since HA 2024.10.** HA can *proactively speak* and can *initiate a conversation* on a satellite. **[verified]** → **We cannot claim to have invented proactive/system-initiated voice.** Claim the closed *sense→reason→converse→act* loop and the silicon, not the primitive.
- **AI Task** (HA **2025.7**): a building-block integration where automations ask an AI to generate text/structured data or images, **including analyzing camera images** (documented example: count birds in a coop from a camera). **[verified]**
- **What HA DOESN'T do:** (a) no edge sensing nodes that do on-board vision inference and emit semantic events — HA satellites are microphones/speakers, and cameras are streams pulled to the hub; (b) no NPU acceleration on Windows-on-ARM (HA is a Linux/container product; **HA doesn't target Copilot+ PCs at all**); (c) no voice cloning; (d) LLM control is experimental and entity-scoped, not situation-scoped; (e) the whole sense→decide→speak→escalate chain must be hand-authored by the user as YAML automations — **there is no agent that decides what to do about a situation it wasn't told about in advance.**
- **The most honest framing:** *"Everything we do could in principle be bolted together in Home Assistant with five integrations, a custom component, and a weekend of YAML — on x86 Linux, with no NPU, no on-board edge inference, and no cloned voice. We built it as one installable Windows-on-Snapdragon app where the agent, not the YAML, decides."*
- Ecosystem note: **Rhasspy is archived (repo archived 2025-10-06, 2.75k★)** and **rhasspy/wyoming-satellite is also archived** (last push 2026-01-24, 1.24k★) — the OSS local-voice world consolidated into HA/OHF-Voice (`OHF-Voice/intents`, 612★, active). **[verified via GitHub API]** Don't cite Rhasspy as a live competitor; cite it as evidence that fragmented local-voice stacks died and a *packaged* experience wins.

### 2.3 LLM Vision (`valentinfrlch/ha-llmvision`) — 1.4k★, v1.7.0, last push 2026-08-01 **[verified]**
- **This is our nearest OSS neighbour.** HA integration that analyzes **images, videos, live camera feeds, and Frigate events** with multimodal LLMs. Providers: OpenRouter, OpenAI, Anthropic, Google Gemini, AWS Bedrock, Azure, Groq, and **local Ollama / Open WebUI / LocalAI** or any OpenAI-compatible endpoint. Features: **Memory** (remembers people/pets/objects), **Timeline** of camera events for dashboards, sensor updates from extracted data, and an **Event Summary blueprint** for AI-summarized camera notifications. **[verified]**
- Companion project: `remimikalsen/ollama_vision` (local Ollama vision analysis). **[reported]**
- **What it DOESN'T do:** no TTS/voice output or two-way conversation documented; no fall detection or eldercare use case documented; no edge inference (frames are pulled to the hub/cloud); no orchestration across heterogeneous devices; no NPU.
- **Risk:** an expert judge can say "that's LLM Vision + a TTS automation." Our answer must be the *two-way conversation with the person*, the **on-node inference so frames never leave the room**, the **NPU numbers**, and the **cloned voice** — plus the fact that no local-Ollama-on-a-Copilot+-PC path exists today.

### 2.4 Scrypted — 5.8k★, active (2026-08-03) **[verified]**
- "High performance video integration and automation platform": bridges cameras into **HomeKit (incl. HomeKit Secure Video → iCloud), Google Home/Nest Hub/Chromecast/Android TV, Alexa/Echo, Home Assistant**; **Scrypted NVR** plugin adds 24/7 recording + "smart detections" with desktop/mobile apps. **[verified]**
- **What it DOESN'T do:** it's plumbing. No LLM reasoning, no agent, no voice loop, no fall detection, no NPU-on-Snapdragon.
- Relevant only as evidence that "camera-integration hub" is a solved, crowded space — so we must not present ourselves as an NVR.

### 2.5 Viam — robotics/IoT fleet platform
- Hardware abstraction into APIs, SDKs (Python/Go/TypeScript), **cloud fleet management**, OTA updates for software **and ML models**, canary deploys/rollbacks, modular registry of drivers + ML models, built-in motion & vision building blocks. **[verified]**
- **What it DOESN'T do / what's unclear:** the marketing site does not commit to offline operation, agentic LLM behaviour, or on-device-only inference; the model is "treat hardware as a single machine **in the cloud**." **[verified — absence noted]**
- **Use in the pitch:** Viam is the closest thing to "a platform for multi-device orchestration" — and it is cloud-managed and robot-centric. If a judge asks "why not just use Viam", the answer is: cloud dependency, no local agent/LLM reasoning layer, no voice loop, and no Snapdragon NPU path.

### 2.6 Willow — alive, but marginal
- `HeyWillow/willow` (repo moved from `toverainc/`), **3.09k★, not archived, last push 2026-08-01**; ESP32-S3 based local voice assistant ("Amazon Echo/Google Home competitive alternative"), Apache-2.0, with **Willow Inference Server** (510★, last push **2026-02-12**) doing ASR/STT, TTS and LLM over WebRTC/REST/WS; HA integration. **[verified via GitHub API]**
- Caveat: **`heywillow.io` did not resolve** from this environment (DNS ENOTFOUND) even though the repo README still points there — the docs site appears down/moved. **[verified this session]**
- **What it DOESN'T do:** voice in/out only. No vision, no sensing, no agent, no orchestration, no cloned voice, no Snapdragon.

### 2.7 Ambianic.ai — the dead ancestor of our exact thesis
- `ambianic/ambianic-edge` (110★, **last push 2023-05-01**) and `ambianic/fall-detection` (115★, **last push 2021-11-07**) — "privacy-preserving edge AI for elderly home care", explicitly no-cloud, with a Python fall-detection library. Devpost entry exists ("Remote elderly home care via privacy-preserving surveillance"). **[verified via GitHub API; Devpost link already in `research/hackathons/health-assistive.md`]**
- **Read this as a warning and a gift:** somebody built "privacy-preserving edge fall detection" and it died from having no response layer, no packaging, and no silicon story. Cite it if challenged on novelty of the privacy idea — and then point at exactly what they lacked.

---

## 3. Academic / open-source fall detection — a commodity

GitHub, sorted by stars (all recently touched, so these are living reference implementations judges may know) **[verified via `gh search repos`]**:

| Repo | ★ | Approach |
|---|---|---|
| `cwlroda/falldetection_openpifpaf` | 430 | OpenPifPaf human pose |
| `taufeeque9/HumanFallDetection` | 349 | Real-time, **multi-person & multi-camera** |
| `AdrianNunez/Fall-Detection-with-CNNs-and-Optical-Flow` | 239 | Paper reproduction, CNN + optical flow |
| `harishrithish7/Fall-Detection` | 189 | CCTV feed |
| `radar-lab/mmfall` | 152 | **4D mmWave radar** + variational recurrent autoencoder |
| `JJN123/Fall-Detection` | 150 | Keras/TF, non-invasive |
| `zhahoi/yolov8-pose-fall-detection` | 126 | YOLOv8-pose keypoint geometry, **ncnn** |
| `ambianic/fall-detection` | 115 | Library, dormant since 2021 |
| `chizhanyuefeng/Realtime-Fall-Detection-for-RNN` | 113 | ADL + fall, TF |
| `Y-B-Class-Projects/Human-Fall-Detection` | 97 | — |
| `DarkSZChao/MMWave-radar-human-tracking-and-fall-detection` | 77 | mmWave multi-human |
| `CrystalMiaoshu/PAFBenchmark` | 82 | **Neuromorphic/event-camera** fall dataset |

Datasets/benchmarks:
- **UR Fall Detection (URFD)**, Kwolek & Kepski, *Computer Methods and Programs in Biomedicine* 117(3), Dec 2014, pp. 489–501: **70 sequences (30 falls, 40 ADL)**, 2× Microsoft Kinect (depth PNG16 + RGB), PS Move (60 Hz) and x-IMU (256 Hz) accelerometers, plus 11 pre-extracted depth features in CSV. **CC BY-NC-SA 4.0, academic non-commercial.** **[verified]**
- Others commonly cited: **Le2i**, **SisFall**, **MobiAct**, **UP-Fall**, `YifeiYang210/Fall_Detection_dataset` (95★). **[unverified naming beyond the GitHub one]**

**Implication:** pose-based fall detection is a **coursework-grade commodity**. This matches what our other research files already concluded (`research/hackathons/health-assistive.md`: "thoroughly overdone across at least 4+ independent hackathons"; `vision-safety.md`: "YOLOv8-pose + keypoint-band heuristic is a well-worn hackathon/community pattern"). Two consequences:
1. **Never present fall detection as the innovation.** Present it as the *cheapest possible* instantiation of a pluggable sensing skill.
2. **Do borrow the license-clean parts** for accuracy: URFD is NC-only, so use it for *evaluation talking points* only, and be careful not to ship NC data in an open-source repo with a permissive license.

---

## 4. Child / baby monitoring AI

| Product | Detects | Processing | Voice behaviour |
|---|---|---|---|
| **Cubo Ai** (Gen 3) | **Covered-face**, **rollover**, **cry**, **cough**, sleep analytics, temperature/humidity; "AI detection 6× faster than before"; CTIA Cybersecurity Certified; 3-day continuous playback **[verified]** | Not disclosed **[verified absence]** | **Two-way audio** (manual) + **selectable-duration lullabies** **[verified]**. Danger-zone/crossing-line not found on the US site **[verified absence — likely exists in app as "Danger Zone"; unverified]** |
| **Nanit** | **Breathing motion** via CV + "Breathing Wear" (no contact sensor), sleep/wake states + parent-proximity detection, **cry/cough/motion** notifications, temp/humidity, 1080p, AES-256 **[verified]** | Not disclosed **[verified absence]** | Two-way communication included; **no conversational AI, no agentic behaviour** **[verified]**. Subscriptions: Sleep (trial), Memories **$120/yr**, Milestones **$300/yr** **[verified]** |
| **Miku (Pro)** | Contact-free **breathing + sleep** via proprietary "SensorFusion", sound/environment; ages up to 7+ **[verified]** | **Explicitly on-device**: "core functions happen within the device so that critical monitoring is lag-free… with or without an internet connection" **[verified]** | No two-way audio or AI voice features mentioned; app playlists only. Membership $9.99/mo; company operating as of Aug 2026 **[verified]** |
| Also in category (from `research/hackathons/voice-multimodal.md`) | Hubble Connected AI Vision, Maxi-Cosi See Pro 360° — "AI interprets baby cries + video alerts" is a shipping commercial category | | |

**What none of them do:** target **toddlers/older kids** rather than infants; detect **behavioural/danger semantics** (fighting, knife/outlet access, climbing, drawing on walls, screen-time); **intervene by speaking**; speak in the **parent's voice**; accept a **parent's text message and voice it in the room**; or reason across rooms.

**Gap we fill (and this is our strongest *use-case* novelty):** the child-monitoring market is 100% **infant, vitals, passive-alerting**. The "3–9-year-old alone in the living room, and the system de-escalates in mum's voice" scenario is genuinely unoccupied. Nearest prior art for cloned parent voice is **storytelling**: Takara Tomy's "Coemo" AI speaker that reads bedtime stories in a cloned parent's voice, and **KidsTime AI** (record a sample → AI stories narrated in your cloned voice). **[reported]** Neither is sensor-triggered, neither is safety, neither is local. Everything else in voice-cloning search results is **scam/fraud coverage** — which is exactly why our **explicit consent + local-only + on-device clone** framing is a feature, not a footnote. Expect a judge question on abuse potential; have the consent/registration flow and "the clone never leaves the device" answer ready.

---

## 5. Agentic home orchestrators — the state of the art

| System | Sensing | Reasoning | Response | Local? | Multi-device semantic bus? |
|---|---|---|---|---|---|
| HA + Assist + Ollama + LLM Vision | cameras pulled to hub, mics | local SLM, tool calls (experimental, <25 entities) | TTS, `start_conversation`, device control | ✅ (x86/Linux, CPU/GPU) | ❌ (entity/state bus, no edge inference nodes) |
| Frigate (+HA) | cameras → hub | GenAI descriptions/summaries, CLIP semantic triggers | MQTT events, notifications | ✅ | ❌ |
| Gemini for Home | Nest cams/mics | **cloud** Gemini | descriptions, Gemini Live conversation, device control | ❌ | ❌ |
| Alexa+ / Ring | Ring cams/doorbells | **cloud** LLM | **proactive spoken conversation with visitor**, Familiar Faces | ❌ | ❌ |
| ElliQ | on-device cams/mics | cloud (undisclosed) | **proactive spoken companionship**, caregiver alerts | ❌ | ❌ (single device) |
| Sensi.AI | audio pods | cloud analytics + ops agents | agency/family alerts | ❌ | partially (multi-pod, but pods → cloud) |
| Viam | any hardware | user code, cloud-managed ML | user code | ⚠️ cloud-managed | ⚠️ (fleet, not semantic) |
| Willow | mic | remote/self-hosted inference server | TTS, HA intents | ✅ | ❌ |
| **QNet Home** | **2× UNO Q nodes doing on-board GStreamer vision/audio inference** | **local SLM/VLM on Hexagon NPU** | **two-way in-room conversation, cloned voice, tools, escalation ladder** | ✅ **fully** | ✅ **semantic events only** |

Also relevant from our own prior research: the Hailo community "B-AIby Monitor" (baby monitor on Pi 5 + Hailo-8L) and a GLaDOS-persona local voice agent (`research/hackathons/vision-safety.md`) — evidence that (a) the persona/character layer reads as inventive to judges, and (b) hobbyists have already done "Pi + accelerator + baby/fall monitor".

---

## 6. The white-space map (what nobody occupies)

1. **Distributed on-node inference with a semantic-event contract.** Everyone else either streams video to a hub/cloud (Frigate, Nest, Ring, Kami, SafelyYou) or uses a single self-contained sensor with a fixed detector (Vayyar, Miku, Sensi pods). Nobody publishes a *sensor-agnostic semantic event schema* that lets a heterogeneous fleet (camera node, audio node, radar node, phone) feed one local agent.
2. **A local agent that decides on a response ladder for a situation nobody pre-scripted.** HA can announce and can start a conversation — but a human must have written the YAML for that exact trigger. An SLM choosing *"speak first, wait for reply, if no reply in 20s flicker the lights, if still nothing call the daughter, if she doesn't answer escalate"* is not something any shipping local system does.
3. **Two-way spoken conversation *about a detected safety event*, fully local.** Alexa+ Greetings does two-way at the door, in the cloud, for logistics. Nobody does it in-room, for safety, on-device.
4. **Consented voice identity as a response modality.** Cloned voice exists for storytelling and for fraud. Nobody uses "who the voice sounds like" as a *deliberate intervention parameter* chosen by an agent ("this child responds to mum; use mum").
5. **Qualcomm NPU in the local-home-AI ecosystem, at all.** Frigate supports Coral, Hailo, OpenVINO, ROCm, TensorRT, RKNN, Synaptics, MemryX, **and Apple's NPU — but not Qualcomm's**. Home Assistant does not run on Copilot+ PCs as a target platform. There is effectively **no local home-AI stack on Windows-on-Snapdragon** today. Qualcomm's own developer blogs (Nexa AI agents on Hexagon NPU, Mar 2026; LLMWare local agentic AI on Snapdragon X, May 2026) show the company is pushing exactly this direction — we are building the home-orchestration exemplar of a strategy Qualcomm is publicly advertising. **[reported — qualcomm.com/developer/blog links via search proxy; fetch and cite properly before the slide goes final]**
6. **The bandwidth/energy argument, quantified.** Nobody in this landscape publishes "semantic events cost N bytes/event vs M Mbps of H.264." That number is free ammunition for the 40-pt technical criterion and it is a *privacy* argument and an *efficiency* argument at once.

---

## 7. Differentiation statement + the 3 claims we can defend

### The statement (use this wording)

> Every part of the elder- and child-safety stack exists today — but split across products that each give up something essential. SafelyYou and Kami see the fall but need your video in their cloud and can only page a human. Vayyar and Sensi protect privacy by seeing less, and can only raise an alert. ElliQ and Alexa+ can hold a proactive conversation, but only in the cloud and only about things it wasn't the sensor for. Frigate and Home Assistant are properly local, but their cameras are streams to a hub, their LLM control is experimental, their responses are hand-written YAML, and **neither has a single line of Qualcomm NPU support**.
>
> **QNet Home is the first fully local, NPU-accelerated, multi-device agentic loop for the home:** distributed Snapdragon edge nodes run their own vision/audio inference and publish **only semantic events** — bytes, not frames — over the LAN; a local SLM/VLM on the Copilot+ PC's Hexagon NPU **interprets the situation and chooses a multi-step response**; and the system **talks with the person in the room** — optionally in a consented, locally-cloned familiar voice — before it escalates to a human. Swap the sensing skill and the same architecture covers a different scenario, with the same measured latency, bandwidth and energy envelope.

### Claim 1 — "Semantic events, not video: privacy and bandwidth as an *architecture*, with numbers."
- **Why it survives scrutiny:** the alternatives are (a) stream video to a hub (Frigate/Scrypted/Nest/Ring), (b) stream to a vendor cloud (SafelyYou, Kami), or (c) preserve privacy by degrading the sensor (Vayyar radar, Sensi audio, Origin Wi-Fi). We keep a rich sensor *and* transmit almost nothing, because inference happens on the node.
- **How to prove it in the demo:** a live counter — *bytes of semantic events emitted* vs *bytes an equivalent 1080p H.264 stream would have cost over the same window*, ratio shown as a single number. Plus: pull the WAN cable and everything still works.
- **Honesty guard:** don't say we invented privacy-preserving edge AI (Ambianic 2021, Sensi, Vayyar). Say we made it *semantically expressive and fleet-agnostic*, and we quantified it.

### Claim 2 — "A closed sense→reason→**converse**→escalate loop, decided by a local model, not by pre-written rules."
- **Why it survives scrutiny:** HA has the *primitives* (`assist_satellite.announce`, `start_conversation`, since 2024.10) but the *policy* is human YAML; HA's own docs call LLM device control experimental and cap it at <25 entities. Alexa+ Greetings has the conversation but in the cloud and for parcels. SafelyYou/Vayyar/Kami/Sensi have **no response layer at all** — they page a human. Nobody has an on-device agent that assesses a safety situation and *negotiates* with the person before escalating.
- **How to prove it in the demo:** the escalation ladder must visibly *branch on the person's answer*. "Are you OK?" → *"I'm fine, I just sat down"* → agent stands down and logs, no caregiver call. Then run it again with silence → lights flicker → caregiver call. Same code, no new YAML: that contrast is the whole 25-pt innovation score.
- **Honesty guard:** explicitly credit HA's primitives on the slide. Credibility with expert judges is worth more than the claim.

### Claim 3 — "Right model, right silicon: the first local home-AI orchestrator on Windows-on-Snapdragon, with per-stage NPU numbers across four heterogeneous devices."
- **Why it survives scrutiny (this is the checkable one):** Frigate's detector list includes **Apple's NPU** and eight other backends and **no Qualcomm/QNN entry**; Home Assistant does not target Copilot+ PCs; Willow's inference server is CUDA-oriented; Viam is cloud-managed. Meanwhile Qualcomm's own dev blogs are pushing on-device agentic AI on Hexagon. We are the missing exemplar, and we can show a per-stage latency/utilization table (node inference → event → SLM reasoning → TTS → speaker) with the NPU graph live.
- **How to prove it:** metrics panel throughout the demo — end-to-end detect→speech latency, tokens/s on NPU vs CPU baseline, NPU utilization, bytes/event, and a watt or thermal figure if obtainable. A CPU-vs-NPU A/B on the same prompt is the single most persuasive 10 seconds available to us.
- **Bonus (a 4th, softer claim):** **consented voice identity as an agent-selectable response parameter.** Existing cloned-parent-voice products are storytelling toys (Coemo, KidsTime AI); the rest of the internet's voice-cloning corpus is fraud coverage. "The clone is created and stored on-device, never uploaded, requires explicit registration consent, and the agent *chooses* the voice most likely to be obeyed" is novel and demo-able. Keep it as the emotional beat, not the technical claim, and lead the abuse question yourself.

---

## 8. Claims to DROP (they will be shot down)

- ❌ "First privacy-preserving on-device fall detection" — Ambianic (2021), Vayyar, Sensi, dozens of GitHub repos.
- ❌ "Fall detection is our innovation" — a 430★-and-below GitHub commodity; our own hackathon research files already flag it as the most-repeated demo in the space.
- ❌ "First proactive/system-initiated voice in the home" — HA `start_conversation` (2024.10), ElliQ, Alexa+ Greetings.
- ❌ "First LLM reasoning over camera events locally" — Frigate GenAI + LLM Vision with local Ollama, 1.4k★.
- ❌ "First voice cloning in a consumer home device" — Takara Tomy Coemo, KidsTime AI.
- ❌ "No one else notifies caregivers / detects danger for kids" — Cubo Ai, Nanit, Miku, Hubble all alert; Cubo does covered-face/rollover/cry/cough.
- ⚠️ Careful with "agentic": **Sensi.AI already brands itself an "Agentic Operating System for Senior Care"** and claims to be the "world's first in-home virtual care agent." Always qualify ours as **on-device / in-room / intervening**, never just "agentic care."

---

## 9. Judge-question rehearsal (expect all five)

1. *"Isn't this Home Assistant + Frigate + LLM Vision + a TTS automation?"* → "Architecturally similar, and we credit them. Three differences: their cameras are streams to a hub while our nodes infer on-board and emit bytes; their response policy is human-authored YAML while ours is a model deciding a ladder; and neither runs on Snapdragon silicon — Frigate supports nine detector backends including Apple's NPU and zero Qualcomm ones. Here are our per-stage NPU numbers."
2. *"SafelyYou already does this at 99% accuracy."* → "In senior-living communities, with video going to a cloud portal for clinician review, and with a human as the only responder. We're consumer-installable, no video leaves the room, and the system talks to the person before it calls anyone."
3. *"Alexa+ can already talk to someone at my door."* → "In the cloud, about parcels. Ours is in-room, about a safety event, offline, and it can speak in a voice the person trusts."
4. *"Why is fall detection interesting? It's a student project."* → "It isn't — it's the cheapest sensing skill we could plug into the bus to prove the bus. Watch: [swap skill] same architecture, different scenario, no code change in the hub."
5. *"Voice cloning is a deepfake risk."* → Lead with it: on-device only, explicit registration with recorded consent, clone never leaves the device, audit log of every utterance spoken in a cloned voice, and a spoken disclosure mode. (Note the search corpus for "cloned parent voice" is dominated by scam warnings — judges will have this reflex.)

---

## 10. Concrete follow-ups (cheap, high value)

- [ ] Fetch and cite properly: `qualcomm.com/developer/blog/2026/03/run-nexa-ai-agents-locally-on-snapdragon-pc-with-hexagon-npu` and `qualcomm.com/developer/blog/2026/05/local-agentic-ai-with-llmware-on-pcs-with-snapdragon-x-series` — internal judges will respond well to being aligned with their own dev-relations narrative.
- [ ] Verify Walabot HOME's discontinuation and Cherish Health specifics before naming them on a slide.
- [ ] Pin the Alexa Together end-of-support date to one citable source (Amazon forum answer says 2024-06-25).
- [ ] Confirm whether Cubo Ai's app has a "Danger Zone" / crossing-line feature (affects how empty we claim the toddler-danger space is).
- [ ] Screenshot Frigate's detector list (no Qualcomm) and HA's Ollama caveats (<25 entities, experimental) for the "gap" slide — these are the two most checkable, most persuasive artifacts in this whole document.

---

## Sources

**Elder monitoring**
- SafelyYou Safety AI — https://www.safely-you.com/safelyyou-safety-ai/
- SafelyYou / NIA small-business spotlight — https://www.nia.nih.gov/news/nia-funded-small-business-spotlight-safelyyou-trains-ai-improve-care-older-adults
- ONELIFE Senior Living on SafelyYou (clinician review of clips) — https://www.onelifeseniorliving.com/blog/how-onelife-senior-living-uses-safelyyou-to-enhance-resident-safety-and-peace-of-mind
- Valage Senior Living on SafelyYou (99.5%) — https://valageatcarsonvalley.com/blog/valage-senior-living-safelyyou-fall-detection/
- Vayyar Care — https://vayyar.com/care/
- Amazon Alexa (Alexa+ dates) — https://en.wikipedia.org/wiki/Amazon_Alexa
- Alexa Together end of support (Amazon forum) — https://www.amazonforum.com/s/question/0D56Q0000DKo8aKSQR/
- "Alexa Together Discontinued? Best Alternatives (2026)" — https://www.besidecare.com/blog/what-to-use-now-that-alexa-together-is-gone/
- Alexa Together launch (Amazon) — https://www.aboutamazon.com/news/devices/alexa-together-launches-to-help-customers-remotely-care-for-loved-ones
- Alexa+ Greetings with Ring — https://www.aboutamazon.com/ ; Ring support — https://ring.com/support ; PCWorld coverage of Alexa+ greeting visitors
- Gemini for Home (Oct 2025) — https://blog.google/
- Apple Watch Fall Detection — https://support.apple.com/en-us/108896
- Kami Fall Detect — https://kamihome.com/products/fall-detect/ ; https://kamivision.com/en/us/fall-detection ; https://kami-ai.com/solutions/kami-fall-detect
- Sensi.AI — https://www.sensi.ai/ ; https://www.sensi.ai/product/ ; case study — https://kozak-ag.com/portfolio/sensi-ai
- Origin Wireless / Origin AI — https://www.originwirelessai.com/
- Cherish Health — https://cherishhealth.com/
- ElliQ — https://elliq.com/ ; NYT (Feb 2026) and Fortune (Jul 2026) coverage
- Electronic Caregiver / Addison — https://www.electroniccaregiver.com/

**Local / privacy-first home AI (OSS)**
- Frigate docs (features) — https://docs.frigate.video/
- Frigate object detectors (no Qualcomm; no pose) — https://docs.frigate.video/configuration/object_detectors
- Frigate semantic search (Jina CLIP, triggers) — https://docs.frigate.video/configuration/semantic_search
- Frigate repo (34.8k★, active) — https://github.com/blakeblackshear/frigate
- Home Assistant voice control — https://www.home-assistant.io/voice_control/
- HA Ollama integration (tools, <25 entities, experimental) — https://www.home-assistant.io/integrations/ollama/
- HA Assist Satellite (`announce`, `start_conversation`, 2024.10) — https://www.home-assistant.io/integrations/assist_satellite/
- HA AI Task (2025.7, camera analysis) — https://www.home-assistant.io/integrations/ai_task/
- HA blog — https://www.home-assistant.io/blog/
- LLM Vision (1.4k★, v1.7.0) — https://github.com/valentinfrlch/ha-llmvision ; Event Summary blueprint — https://deepwiki.com/valentinfrlch/ha-llmvision/4.1-event-summary
- Ollama Vision for HA — https://github.com/remimikalsen/ollama_vision
- Scrypted — https://scrypted.app/ ; https://github.com/koush/scrypted
- Viam — https://www.viam.com/
- Willow — https://github.com/HeyWillow/willow ; inference server — https://github.com/toverainc/willow-inference-server (docs at heywillow.io currently not resolving)
- Rhasspy (archived 2025-10-06) — https://github.com/rhasspy/rhasspy ; wyoming-satellite (archived) — https://github.com/rhasspy/wyoming-satellite ; OHF-Voice intents — https://github.com/OHF-Voice/intents
- Ambianic — https://github.com/ambianic/ambianic-edge ; https://github.com/ambianic/fall-detection ; Devpost — https://devpost.com/software/remote-elderly-home-care-via-privacy-preserving-surveillance

**Fall detection research / datasets**
- UR Fall Detection Dataset — http://fenix.ur.edu.pl/~mkepski/ds/uf.html (Kwolek & Kepski, CMPB 117(3), 2014, 489–501)
- `cwlroda/falldetection_openpifpaf`, `taufeeque9/HumanFallDetection`, `AdrianNunez/Fall-Detection-with-CNNs-and-Optical-Flow`, `radar-lab/mmfall`, `zhahoi/yolov8-pose-fall-detection`, `DarkSZChao/MMWave-radar-human-tracking-and-fall-detection`, `CrystalMiaoshu/PAFBenchmark` — via https://github.com/search?q=fall+detection&s=stars

**Child monitoring**
- Cubo Ai — https://us.getcubo.com/
- Nanit — https://www.nanit.com/
- Miku — https://mikucare.com/
- Takara Tomy AI speaker cloning parent voices — https://gizmodo.com/smart-speaker-takara-tomy-ai-deepfake-voice-parents-kid-1848997168
- KidsTime AI voice cloning for family stories — https://www.kidstimeai.com/blog/voice-bonding.html

**Snapdragon / on-device agents**
- Nexa AI agents locally on Snapdragon X with Hexagon NPU — https://www.qualcomm.com/developer/blog/2026/03/run-nexa-ai-agents-locally-on-snapdragon-pc-with-hexagon-npu
- Local agentic AI with LLMWare on Snapdragon X — https://www.qualcomm.com/developer/blog/2026/05/local-agentic-ai-with-llmware-on-pcs-with-snapdragon-x-series
- Community Snapdragon AI stack — https://github.com/gaiagent0/snapdragon-ai-stack

**Internal cross-references**
- `research/hackathons/health-assistive.md` (fall detection overdone across 4+ hackathons)
- `research/hackathons/vision-safety.md` (YOLOv8-pose fall detection is a worn pattern; persona layer reads as inventive)
- `research/hackathons/smart-home-iot.md` (eldercare-privacy-camera market has normalized on-device no-video alerting)
- `research/hackathons/voice-multimodal.md` (baby-cry AI is a shipping commercial category)
