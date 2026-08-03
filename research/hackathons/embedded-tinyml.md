# Arduino / Embedded / TinyML Hackathon Research (Aug 2024 – Aug 2026)

Research date: 2026-08-03. Compiled for QNet Home (Snapdragon Multiverse Hackathon, Aug 3-7 2026).

Scope: 9 distinct hackathons/contests covered, ranging from the exact same hackathon series we're
entering (prior editions) down to seminal tinyML contests. For each: winners/top projects, device/model
stack, what made them win, ideas for QNet Home, and overdone patterns to avoid.

---

## 0. TL;DR — most important finding

**We are not the first team to get this exact hardware kit.** The "Snapdragon Multiverse Hackathon" is a
recurring Qualcomm series (Princeton Sept 2025, Bangalore Jul 2026, Noida edition) that hands teams the
*identical* kit description used in our brief: Copilot+ PC (Snapdragon X Series) as hub, a mobile device,
an Arduino UNO Q, and Qualcomm AI Cloud 100 access, judged on "seamless Snapdragon execution" and
"multi-device innovation" (not single-device demos). A Noida-edition team ("Ghost Map", project
"Dragverse") won by building a phone-scan → digital-twin → RL-trained robot-control pipeline that
explicitly used cloud simulation + Copilot+ PC + robot, i.e., a genuine 3-device pipeline, not a hub with
two dumb sensors. This confirms: (a) judges have already seen this format and reward *visible, distinct
work happening on each device* over a "look at events pop up in a PC dashboard" demo, and (b) fall
detection / elderly companion ideas are extremely well-trodden elsewhere (see §5), so our differentiation
has to come from the cross-device choreography and privacy story, demoed with clear per-device proof
points, not from the base use case being novel.

---

## 1. Snapdragon Multiverse Hackathon (Qualcomm's own series — Princeton Sept 2025 / Bangalore Jul 2026 / Noida)

**This is literally our hackathon's prior editions — the single most decision-relevant source.**

- **Princeton (Sep 27-28, 2025):** Teams of 3-5, kit = Copilot+ PC (Snapdragon X Series) as hub +
  bring-your-own Snapdragon device/microcontroller. Three optional tracks (Real-time CV Assistant,
  Conversational AI Companion, RL Agent Arena) but **winners were selected overall, not per track** —
  only two prizes: Top Award (judge score) and Team's Choice (peer vote). Submission requirements already
  mandated: GitHub repo + README + open-source license + **Windows .EXE/.MSIX** + must "run primarily
  on-device." This is the direct ancestor of our current 40/25/20/15 rubric.
- **Bangalore (Jul 11-12, 2026):** Identical kit to ours (Copilot+ PC, mobile device, Arduino UNO Q, AI
  Cloud 100). Three prize categories: **Overall Winner** (technical excellence + "seamless Snapdragon
  execution"), **Multi-Device Innovation** (explicitly: "utilizing two or more devices with distributed
  functionality across form factors" — separate prize track just for this, prize = Ray-Ban Meta AI
  Glasses), and **Popularization Award** ("best captures the imagination" via demo/presentation). No
  predefined tracks; explicit framing: "focus on cross-device orchestration, not single-device solutions."
- **Noida edition — winner "Team Ghost Map," project "Dragverse":** phone-captured 3D scan of a real
  environment → digital twin → RL policy trained in simulation → policy deployed onto a physical robot.
  Team got Snapdragon X2 Elite Copilot+ PCs + Qualcomm Developer Relations support as prize.

**What made it win / stand out:** Judges rewarded a pipeline where *each device does something a single
device couldn't* (phone = sensing/capture, cloud/PC = simulation + RL training, robot = physical
actuation) — a true sim-to-real loop, not just "sensor → dashboard."

**Ideas for QNet Home:**
1. There's a dedicated "Multi-Device Innovation" prize lane in this series — make sure our demo can be
   scored as multi-device even if judges only watch 5 minutes: script the demo to visibly show the UNO Q
   node reacting locally (its own LED/speaker/log), the phone getting a push notification, and the PC
   speaking — in that order, on camera, so the distributed nature is undeniable without reading code.
2. "Runs primarily on-device" + Windows .EXE/.MSIX is a hard requirement pattern across editions — treat
   packaging as a first-class engineering task from Day 1, not a Day-4 afterthought (see also Kavach,
   §4, which is a Windows/desktop AI device for exactly our target demographic and already won a contest
   with a *packaged app*).
3. Consider whether AI Cloud 100 can play a distinctive role analogous to Dragverse's "cloud does the
   heavy simulation/training, edge does the light stuff" split — e.g., AIC100 batch-processes anonymized
   event logs for a "weekly wellbeing summary" or fine-tunes/quantizes a small on-device model, giving us
   a concrete, demoable reason to touch all 4 pieces of hardware instead of 3.

---

## 2. "Invent the Future with Arduino UNO Q and App Lab" (Arduino + Qualcomm + Edge Impulse, via Hackster, 2026)

Global contest launched ~March 2026, 300 free UNO Q boards given away, run jointly by Arduino, Qualcomm
Technologies, and Edge Impulse. **Submissions close Aug 30, 2026; winners announced ~Sept 25, 2026** — so
no winners exist yet (still open as of our hackathon date), but the submissions gallery shows what the
early ecosystem is building, which doubles as "what's already been done on UNO Q":

- **Image Quality Labs** — adds Raspberry Pi Camera Module compatibility to UNO Q; confirms the board's
  Linux side supports standard **V4L2, GStreamer, and OpenCV** camera pipelines (this is squarely our
  team's expertise area).
- **Smart Mirror w/ "Video Object Detection Brick"** — a reusable "brick" that continuously analyzes a
  USB camera feed with a pretrained model; shows App Lab's brick/module packaging pattern for vision.
- **Autonomous Quality Control Station** — camera + UNO Q inspecting products on a conveyor for defects.
- **BirdFeedR** — object detection ("bird-only" feeder) running on UNO Q.
- Arduino's own App Lab docs ship an **audio classification example** runnable on UNO Q as an SBC with
  pre-loaded/uploaded audio (no extra hardware needed) — i.e., audio-event classification on UNO Q is a
  documented first-party pattern, not something we'd be inventing from scratch.

**Hardware reality check (important for technical scoring):** The UNO Q's Linux side runs on the
**Qualcomm Dragonwing QRB2210** — quad-core Cortex-A53 @ 2.0GHz + **Adreno 702 GPU (845MHz), no discrete
NPU**. GPU-accelerated TFLite inference is reported at **sub-100ms latency**; benchmarks cite ~12.5×
throughput vs. classic Uno R3 and ~4.2× vs Uno R4 WiFi for the MCU side (STM32U585 @ 160MHz on Zephyr).
Two 13MP-capable ISPs support dual cameras. **Implication:** the UNO Q nodes should be pitched as doing
*lightweight, GPU-accelerated GStreamer/TFLite inference* (pose keypoints, audio-event classifiers) — the
heavy VLM/SLM reasoning belongs on the Copilot+ PC's Hexagon NPU, not on the UNO Q. This is exactly our
seed architecture, so cite the sub-100ms GPU inference figure as evidence the split is deliberate/measured,
not just "camera streams events."

**Ideas for QNet Home:**
1. Explicitly say "no NPU on the edge node by design" in our pitch — semantic-event extraction runs on the
   UNO Q's Adreno GPU via GStreamer+TFLite (sub-100ms), while the NPU-class reasoning (SLM/VLM, TTS,
   voice-clone synthesis) is deliberately centralized on the Copilot+ PC's Hexagon NPU. That's a genuine,
   measurable "resource utilization" story for the 40-pt technical rubric instead of hand-waving "edge AI."
2. Use App Lab's "Brick" concept language in our own repo/README ("Vision Brick," "Audio Brick") — judges
   who've seen the Arduino/Qualcomm contest will recognize the pattern and it signals platform fluency.
3. Since first-party audio classification examples already exist for UNO Q, don't spend hackathon time
   proving audio classification is *possible* on UNO Q — spend it on the harder differentiator (the
   cross-device semantic protocol and the parent-voice-cloning response), which nobody in these galleries
   has done.

---

## 3. Edge Impulse Hackathon 2025 (virtual, Oct 30 – Nov 30, 2025, 1,000+ participants)

Winners (full list, per Edge Impulse's own recap blog):

| Award | Project | Stack | Why it won |
|---|---|---|---|
| Best Overall | Ocean Water Quality Classification (bacteria contamination) | ESP32-S3, turbidity/pH/TDS/temp sensor fusion, LoRa | 99.4% accuracy, **2ms** inference on raw sensor data — cited concrete numbers |
| Best Edge AI Application | TotTalk Box (toddler language learning) | Raspberry Pi 3, YOLO object detection, Whisper, int8 quantization | Fully offline/no-screen, privacy-first, social-good framing |
| Best Model Development | Dendritic NN Impulse Block (keyword spotting "Hello World") | Custom PyTorch block, MFCC features | 90% model compression with no accuracy loss — a *tooling* contribution, not just an app |
| Impact Award ("AI for good") | Sane.AI (underground water-leak detection) | Samsung Galaxy Tab A9+, geophone, 1D-CNN, Android app | Real infrastructure problem, non-camera sensing |
| Student Award | Albaricoque (privacy-preserving perimeter security, no camera) | Arduino Nano 33 BLE Sense Rev2, PIR + ultrasonic, int8 quant | **Privacy-by-design (no camera at all)** was the explicit hook that won a dedicated award |

**Ideas for QNet Home:**
1. "Albaricoque" proves judges specifically reward "no camera / no video, privacy by construction" as an
   award-worthy angle on its own — this validates our semantic-events-only architecture as a real judging
   lever, not just a nice-to-have. Say it explicitly in the pitch: "we never transmit pixels or audio
   waveforms off the edge node — only structured events" and be ready to show the wire protocol.
2. TotTalk Box shows "offline, no big-tech cloud, works for a vulnerable population" is a proven winning
   narrative shape — matches our elderly/kid framing closely; borrow its "fully local, no internet
   required for the core loop" claim if we can make it true (flag: TTS voice cloning may need cloud unless
   we run a local voice-cloning model on the PC's NPU — verify feasibility early).
3. Concrete latency numbers ("2ms inference," "sub-100ms GPU inference") are what separates "Best Overall"
   from generic entries — instrument our own pipeline (UNO Q event → PC agent decision → TTS speaking)
   and put real millisecond numbers in the README and demo slide.

---

## 4. STM32 Edge AI Contest 2025 (Elektor / ST)

| Prize | Project | Stack | Why it won |
|---|---|---|---|
| 1st (€2,500) | EasyGimbal — AI camera gimbal | STM32N6570-DK (has NPU), MoveNet pose estimation, custom motor-isolation board, 3D-printed mechanics | Polished hardware integration + "creator-friendly automated cameraman" narrative |
| 2nd (€1,500) | Ninja Fruit — gesture-controlled game | STM32N6570-DK, MoveNet pose estimation, LCD | Fun demo of **fast on-device pose AI**, multiple modes/difficulty — showmanship |
| 3rd (€1,000) | NeuroSense — mental-health monitor | STM32N6570-DK w/ NPU, YOLOv8-based emotion model, EEG signal acquisition, TouchGFX UI | "Strong engineering + societal impact," multimodal fusion (face + speech + EEG) |

**Ideas for QNet Home:**
1. MoveNet pose estimation running live on-device (even on a lower-power NPU-equipped MCU board) is a
   proven, judge-tested building block for our fall-detection pipeline — if GPU/CPU budget is tight on the
   UNO Q, MoveNet-Lightning-class models are the safe, precedented choice over a heavier full-body model.
2. NeuroSense shows multimodal fusion (vision + audio + a third signal) reads as more technically serious
   than single-modality detection — for kid-monitoring, consider fusing pose (rough play) + audio (yelling
   detection) + maybe just motion/vibration as a third cheap signal, and say "sensor fusion" explicitly in
   the pitch since judges reward that phrase when it's backed by an actual second signal.
3. Showmanship: Ninja Fruit topped a technical-scoring contest with a literal game demo. A short, fun,
   interactive live demo moment (e.g., have someone actually stage a "fall" or a toy fight in front of
   judges and watch the system respond in real time) beats a slide-only walkthrough.

---

## 5. DigiKey "Smart Home & Wearables Project Contest 2025" (with Circuit Digest, results Apr 2026)

- **1st place — "Kavach" (Ashish Joy), ₹1,30,000:** an AI-assisted **desktop device for elderly users who
  struggle with smartphones/modern interfaces**, providing communication and smart-home support. This is
  the closest direct precedent to our elderly use case that we found anywhere in this research — it
  *already won a major contest with almost our exact framing* (AI companion device, elderly, smart-home
  control, simplified interface).
- 2nd place — "Find My Book" (AI/IoT smart library navigation), 3rd — "Gesture Link" (assistive comms for
  differently-abled users). 10 additional "most creative" awards (₹8,500 each).

**Overdone-pattern warning:** Elderly-companion / "AI device for people who can't use smartphones" is a
recurring, contest-winning category (Kavach here; fall-detection wearables win Hackaday-style contests
going back to 2016-2017 — see e.g. "Elderly Autonomous Fall Detection," "Fall Detector Wearable for
Elderly and Clinics" on Hackaday.io). **Fall detection alone is not novel and will not read as innovative
to judges who've seen these contests.** The differentiation must be: (a) multi-device/edge-privacy
architecture (nobody in this list does semantic-event-only, cross-room, multi-node), and (b) the
parent-voice-cloning twist for kid monitoring, which we found **zero prior-art hits for** in hackathon
context (see below) — that is our most defensible "non-obvious" angle for the 25-pt Innovation score.

**Ideas for QNet Home:**
1. Cite Kavach as evidence the *market/judge appetite* for this category is proven — but pivot the pitch
   language away from "AI elderly companion" (generic, already-won-elsewhere) toward "reusable
   multi-device semantic-event orchestration platform, demonstrated via two very different household
   scenarios" — sell the architecture, use the scenarios as demos.
2. Kavach's win reinforces that a clean, simplified desktop-app UX matters for elderly-facing tools —
   invest real design time in the caregiver-facing / elderly-facing UI, not just the backend agent logic.

---

## 6. Hailo Hackathon 2024-2025 (internal Hailo employee hackathon, Raspberry Pi 5 + Hailo AI HAT+)

60 Hailo employees, 24-hour internal hackathon on Raspberry Pi 5 + Hailo-8 AI HAT+ accelerator. Judged on
**Diversity & Creativity, Real-World Impact, Implementation Quality** (a 3-axis rubric worth noting as a
template, structurally similar to our 4-category rubric). Specific winning project names weren't publicly
enumerated in available sources, but the event's own framing — "powerful AI applications can be developed
in just 24 hours with the right tools" — is a useful morale/pitch data point: dedicated AI-accelerator
hardware (Hailo-8, or in our case AIC100 + Hexagon NPU) is explicitly marketed as enabling ambitious scope
within hackathon time constraints; use this as validation for scoping aggressively rather than conservatively.

**Idea for QNet Home:** Frame our AIC100 usage (even if a limited integration, e.g., running the SLM/VLM
inference or a batch anomaly-detection job on cloud AIC100 to offload the PC) as intentional "right tool
for the job" hardware-accelerator matching — this is a technical-score talking point judges in accelerator-
sponsored hackathons consistently reward.

---

## 7. Hackster "Smart Homes on the Edge" / "Building for Voice" (Snips + Seeed, seminal, ~2018)

Older but seminal voice-first smart-home contest (Snips, pre-Sonos-acquisition open voice assistant
company) — 1st place won a Maker Faire feature, 2nd a MacBook Pro, 3rd a Seeed gift card. Specific
winning project names weren't retrievable, but the contest's very existence establishes: **on-device,
privacy-first voice assistants for the home are an almost decade-old genre** by now — meaning "local voice
assistant" alone is not novel; judges have effectively seen this idea class since 2018. What's *not* been
done in that genre, based on this and all other research here, is **voice-cloned, consent-registered,
context-aware intervention** (i.e., the system speaking *as* a specific trusted person rather than a
generic assistant voice) — every voice-smart-home project we found uses a neutral TTS voice.

**Idea for QNet Home:** The parent-voice-cloning feature is the single most differentiated element in our
seed idea relative to the entire body of research gathered here (fall detection: done to death; local
voice assistants: done since 2018; multi-device orchestration: done in the Snapdragon Multiverse series
itself; **consent-based cloned-voice intervention as an agent tool-call: not found anywhere**). Lead the
pitch with this, and make sure the demo actually plays back a cloned voice live, since that's the visceral
"wow" moment nothing else in this research has.

---

## 8. tinyML Foundation "Eyes on Edge: tinyML Vision Challenge" (Hackster, seminal 2021)

One of the original vision-focused tinyML contests (predates the current UNO Q-era wave by 4+ years).
Establishes computer-vision-on-microcontroller as a long-running, well-covered genre — meaning generic
"we ran object detection on an edge device" claims read as dated/unremarkable to any judge who follows
this space. **Overdone pattern:** basic single-class object/gesture detection demos, camera-triggered
alerts. What separates recent winners (per §3, §4 above) from 2021-era submissions is (a) multimodal
fusion, (b) explicit privacy framing, (c) measured latency/accuracy numbers, and (d) an actuation/response
loop rather than just detection+alert. QNet Home's full loop (detect → reason → speak → escalate) already
clears that bar structurally — make sure the demo actually shows the full loop end-to-end, not just
detection.

---

## 9. ACM/IEEE TinyML Design Contest @ ICCAD (academic, since 2021/2022)

Academic contest (e.g., 2022 edition on life-threatening ventricular-arrhythmia detection from ECG,
GaTech EIC Lab team took 1st). Establishes the pattern of rigorous **energy/latency/accuracy tri-axis
reporting** as the norm in serious tinyML evaluation — winning academic entries report joules-per-
inference, not just accuracy. **Idea for QNet Home:** for the 40-pt "Technical Implementation" score,
prepare at minimum: (1) per-inference latency on the UNO Q edge pipeline, (2) end-to-end event-to-response
latency (fall detected → agent decision → TTS starts speaking), (3) some notion of "on-device vs.
cloud/PC-NPU" compute split with rough power/perf justification. Even rough measured numbers will
out-score competitors' unmeasured claims, based on how consistently these contests reward it.

---

## Ranked "Top ideas for QNet Home" from this domain research

1. **Lead with the architecture, not the scenario.** Fall detection (Kavach, Hackaday elderly-fall
   projects going back to 2017) and local voice assistants (Snips-era "Smart Homes on the Edge," 2018) are
   both saturated categories on their own. Our defensible innovation is the *reusable multi-device
   semantic-event bus across heterogeneous Snapdragon hardware* — pitch that first, use elderly/kid as two
   proof-of-concept scenarios of the same platform, exactly the framing that won the Multi-Device
   Innovation prize lane at the Bangalore Snapdragon Multiverse edition.
2. **The parent-voice-cloning intervention is our strongest, least-contested differentiator** — nothing in
   9 hackathons of research does consent-based cloned-voice agent responses. Make it live in the demo
   (not just described), since it's the one moment nothing else in this research space has shown.
3. **State the compute split explicitly and back it with numbers**: UNO Q edge nodes do GStreamer +
   GPU-accelerated TFLite (Adreno 702, no NPU, cite sub-100ms) for pose/audio event extraction only; the
   Copilot+ PC's Hexagon NPU runs the SLM/VLM reasoning + TTS/voice-clone synthesis; AIC100 optionally
   handles a heavier/batched job (e.g., periodic wellbeing summarization or model fine-tune/quantization).
   This mirrors what won: Dragverse's device-by-device division of labor and the STM32/Edge-Impulse
   winners' concrete latency citations (2ms, sub-100ms, 90% compression).
4. **"No pixels/audio leave the edge node" is a proven standalone award category** (Edge Impulse's
   Albaricoque Student Award, purpose-built as a no-camera privacy system) — state our semantic-event-only
   protocol explicitly and show the actual event schema/wire format in the demo or README as proof, not
   just a claim.
5. **Package early.** Every relevant contest (Snapdragon Multiverse series itself, Kavach as a desktop
   app) requires or rewards a real installable artifact — a Windows .EXE/.MSIX is contractually required
   for our judging rubric's Deployment/Accessibility 20 pts and should be built and tested well before
   Aug 7, not left to the last hours.
6. **Borrow MoveNet-class lightweight pose estimation** as the fall/rough-play detector — it's the
   precedented, judge-tested choice (STM32 contest 1st and 2nd place both used MoveNet) and is light enough
   to plausibly run within the UNO Q's Adreno-GPU/no-NPU budget.
7. **Add one more cheap signal for "sensor fusion" credibility.** NeuroSense (3rd place, STM32 contest)
   won partly by fusing three signal types. We already have vision (pose) + audio (loud-sound); consider
   whether a trivial third signal (e.g., simple motion/vibration, or door/light state from the smart-light
   integration) can be name-dropped as fusion without adding much build risk.
2b. **De-risk OpenClaw before committing hackathon time to it.** As of research date, OpenClaw
   (formerly Clawdbot/Moltbot, renamed Jan 2026) states native Windows support is "experimental" and
   full functionality requires **WSL2**; ARM single-board Linux computers are explicitly unsupported
   (this refers to Linux ARM SBCs, not Windows-on-ARM PCs, but it's a signal the ARM64 Windows path is
   less traveled). Given only ~4 build days, spike this on Day 1: if OpenClaw+WSL2 on the Snapdragon
   Copilot+ PC has any friction, have a lightweight custom agent-loop fallback (direct SLM/VLM tool-calling
   loop) ready rather than losing a full day to framework setup.
8. **Instrument everything for the 40-pt technical score.** Across every recent winning entry we found
   (Edge Impulse 2ms/99.4%, STM32N6 sub-100ms-class inference, UNO Q's own documented sub-100ms
   GPU-TFLite figure), concrete measured numbers consistently separate top prizes from also-rans. Log and
   report: edge inference latency, end-to-end event-to-spoken-response latency, and a rough compute/power
   split rationale across the four devices.

---

## Sources

- [Arduino and Qualcomm Launch Hackster's First Developer Contest of 2026](https://www.prnewswire.com/apac/news-releases/arduino-and-qualcomm-launch-hacksters-first-developer-contest-of-2026-global-competition-kicks-off-with-300-arduino-uno-q-boards-and-opportunities-to-showcase-edge-ai-innovation-302703213.html)
- [Invent the Future with Arduino UNO Q and App Lab — Hackster.io](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
- [Invent the Future — rules](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab/rules)
- [Invent the Future — FAQ](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab/faq)
- [Image Quality Labs gives the Arduino UNO Q Eyes / Raspberry Pi Camera Module compatibility — Hackster News](https://www.hackster.io/news/image-quality-labs-gives-the-arduino-uno-q-eyes-adds-raspberry-pi-camera-module-compatibility-b888150b11cc)
- [Arduino Releases a New App Lab for the Arduino UNO Q — Hackster News](https://www.hackster.io/news/arduino-releases-a-new-app-lab-for-the-arduino-uno-q-promises-big-quality-of-life-gains-b0dca6ec3c8f)
- [Say Hello to the Smart Mirror Powered by Arduino UNO Q — Hackster News](https://www.hackster.io/news/say-hello-to-the-smart-mirror-powered-by-arduino-uno-q-183232997036)
- [BirdFeedR — Hackster](https://www.hackster.io/ishotjr/birdfeedr-the-bird-only-feeder-powered-by-arduino-uno-q-2c3259)
- [Running ML/AI on Arduino UNO Q — Hackster](https://www.hackster.io/vsupacha/running-ml-ai-on-arduino-uno-q-59ff07)
- [Trying Python+Arduino with Arduino UNO Q — Hackster](https://www.hackster.io/vsupacha/trying-python-arduino-with-arduino-uno-q-2fa4df)
- [The Arduino Uno Q is a weird hybrid SBC — Jeff Geerling](https://www.jeffgeerling.com/blog/2025/arduino-uno-q-weird-hybrid-sbc/)
- [Arduino Uno Q Review: The board with two brains — Tom's Hardware](https://www.tomshardware.com/raspberry-pi/arduino-uno-q-review)
- [Hands-On with the Arduino UNO Q — Hackster News](https://www.hackster.io/news/hands-on-with-the-arduino-uno-q-74eabc1bd962)
- [Qualcomm Introduces The Arduino Uno Q Linux-Capable SBC — Hackaday](https://hackaday.com/2025/10/07/qualcomm-introduces-the-arduino-uno-q-linux-capable-sbc/)
- [Arduino UNO Q with Qualcomm AI Chip — ResearchGate paper](https://www.researchgate.net/publication/399652115_Arduino_UNO_Q_with_Qualcomm_AI_Chip_Enabling_Next-Generation_Edge_Intelligence_for_Embedded_AI_Prototyping)
- [Arduino is acquired by Qualcomm / UNO Q hybrid board — ARMdevices.net](https://armdevices.net/2025/11/16/arduino-is-acquired-by-qualcomm-uno-q-hybrid-linux-rtos-board-with-dragonwing-qrb2210-app-lab/)
- [Arduino UNO Q: Dragonwing QRB2210 + STM32U585 — ARMdevices.net](https://armdevices.net/2026/01/16/arduino-uno-q-dragonwing-qrb2210-stm32u585-debian-linux-edge-ai-robotics/)
- [UNO Q | Arduino Documentation](https://docs.arduino.cc/hardware/uno-q/)
- [Edge Impulse Hackathon 2025: And the Winners Are...](https://www.edgeimpulse.com/blog/edge-impulse-contest-2025-winners/)
- [Edge Impulse Hackathon 2025 — forum recap](https://forum.edgeimpulse.com/t/edge-impulse-hackathon-2025-and-the-winners-are/17370)
- [STM32 Edge AI Contest 2025: The Winners — Elektor Magazine](https://www.elektormagazine.com/news/stm32-edge-ai-contest-winners)
- [DigiKey Announces Winners of Smart Home & Wearables Project Contest 2025 with Circuit Digest](https://www.electronicsmedia.info/2026/04/14/winners-of-smart-home-wearables-project-contest-2025/)
- [DigiKey Smart Home & Wearables Contest — Semiconductor for You](https://www.semiconductorforu.com/digikey-announces-winners-of-smart-home-wearables-project-contest-2025-with-circuit-digest/)
- [Hailo Hackathon 2025: Edge AI Innovative Ideas on Raspberry Pi](https://hailo.ai/blog/hailo-hackathon-2024-2025-pushing-the-limits-of-ai-innovation-on-raspberry-pi/)
- [Snapdragon Multiverse Hackathon | Princeton](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon | Bangalore](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)
- [Snapdragon Multiverse Hackathon | MIT CSAIL](https://www.csail.mit.edu/event/snapdragon-multiverse-hackathon)
- [Team led by city youth emerges winner at Qualcomm hackathon (Ghost Map / Dragverse) — The Tribune](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [Snapdragon Multiverse Hackathon Bangalore 2026 — Internshala](https://internshala.com/competitions/snapdragon-multiverse-hackathon-bengaluru/)
- [New Hackster Developer Contest: Submit Smart Home Voice Projects — Snips Blog / Medium](https://medium.com/snips-ai/hackster-developer-contest-submit-your-smart-home-voice-projects-5926ea78bfe2)
- [Smart Homes on the Edge — Hackster.io](https://www.hackster.io/contests/building-for-voice)
- [Eyes on Edge: tinyML Vision Challenge! — Hackster.io](https://www.hackster.io/contests/tinyml-vision)
- [2022 ACM/IEEE TinyML Design Contest @ ICCAD — Winners](https://tinymlcontest.github.io/TinyML-Design-Contest/Winners.html)
- [TinyML Design Contest for Life-Threatening Ventricular Arrhythmia Detection (paper)](https://arxiv.org/pdf/2305.05105)
- [Fall Detector Wearable for Elderly and Clinics — Hackaday.io](https://hackaday.io/project/11067-fall-detector-wearable-for-elderly-and-clinics)
- [Hackaday Prize Entry: Elderly Autonomous Fall Detection](https://hackaday.com/2017/09/04/hackaday-prize-entry-elderly-autonomous-fall-detection/)
- [What is OpenClaw? — DigitalOcean](https://www.digitalocean.com/resources/articles/what-is-openclaw)
- [OpenClaw Docs — Introduction](https://clawdocs.org/getting-started/introduction)
- [Chatterbox voice cloning — Home Assistant Community](https://community.home-assistant.io/t/chatterbox-voice-cloning/962806)
- [I Cloned My Own Voice for My Smart Home! — fixtSE](https://fixtse.com/blog/chatterbox-in-home-assistant)
