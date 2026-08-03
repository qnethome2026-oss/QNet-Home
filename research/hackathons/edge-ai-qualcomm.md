# Qualcomm / Snapdragon / Edge-AI Hackathon Research (Aug 2024 – Aug 2026)

Research compiled 2026-08-03 for QNet Home (Snapdragon Multiverse Hackathon, Aug 3–7 2026).
Goal: understand what judges have actually rewarded in the Qualcomm hackathon ecosystem over
the last two years, so we can pick a technically sharp, non-generic angle for QNet Home.

---

## 0. THE single most important find: our event's own predecessor already ran with our exact kit

**Snapdragon Multiverse Hackathon** is a recurring Qualcomm developer-relations hackathon series
(not a one-off). Editions found, in order:

| Edition | Dates | Location | Devices given to teams |
|---|---|---|---|
| Princeton | Sept 27–28, 2025 | Princeton University | Copilot+ PC (Snapdragon X Series) + tracks: real-time CV, conversational AI, RL agents |
| MIT (IAP) | Jan 24–25, 2026 | MIT Stata Center / CSAIL | Copilot+ PC (Snapdragon X Series) as "central hub" + Samsung Galaxy S25 (Snapdragon 8 Elite) |
| **Bengaluru** | **July 11–12, 2026** | Qualcomm Bengaluru campus | **Snapdragon AI PCs + mobile devices + Arduino UNO Q + Qualcomm AI Cloud 100** |
| **Noida** | **July 18–19, 2026** | Qualcomm Noida campus | **Same kit as Bengaluru** (identical device set to ours) |

The **Bengaluru/Noida July 2026 editions used the *exact same four-device kit* our hackathon is
using** (Copilot+ PC + phone + Arduino UNO Q + AIC100), run only 2–4 weeks before our Aug 3–7
event. This is as close to "read the previous year's winning playbook" as we're going to get.

- Themes/tracks for that kit: "productivity, smart infrastructure, intelligent assistants,
  connected devices and emerging AI-led workflows."
- Judging criteria stated publicly: **"proposal strength, technical approach and real-world
  application potential."** (Broader/vaguer than our stated 100-pt rubric, but the same spirit:
  technical depth + real-world relevance.)
- Official partners for the India editions: OnePlus (mobile) and Sarvam AI (Indic-language AI) —
  a signal Qualcomm likes cross-partner integration stories.

### Winner: "Dragverse" by Team Ghost Map (Noida edition, announced as the top team)
- **Team:** Deepesh Kakkar (Thapar Institute of Engineering & Technology, Patiala) + Adishwar
  Singh, Aditya Kumar, Apoorv Singhal, Aayush Bindal.
- **What it did:** An AI-powered **multi-device pipeline**: phone captures a 3-D scan of a real
  room → Copilot+ PC turns the scan into a **digital twin / simulation** → a robot control policy
  is **trained via reinforcement learning inside that simulation** → the trained policy is
  **deployed onto a physical robot**.
- **Why it likely won:** it is a genuine end-to-end pipeline that uses *every* device in the kit
  for a *different, necessary* stage of the pipeline (phone = sensing/capture, PC = simulation +
  training, physical actuator = deployment) — not just "same app running on multiple screens."
  Judging language explicitly cited "the strength of the proposed multi-device architecture."
  Prize: each member got a Snapdragon X2 Elite Copilot+ PC (~₹2.5 lakh) plus Qualcomm DevRel
  engineering support and an official blog/livestream feature.
- **Takeaway for QNet Home:** the bar for "multi-device" is not just "device A talks to device B" —
  the winning story showed *distinct, non-interchangeable roles per device* with a clear causal
  chain (capture → simulate/train → deploy). QNet Home already has this shape (edge node senses →
  PC agent reasons/decides → edge node/speaker acts), but we should sharpen the pitch to narrate
  it exactly like Dragverse did: "device X did A because only it can, device Y did B because only
  it can."

Source snippets for this section were pulled from Qualcomm's own event pages and an Indian press
writeup (see Sources). No Bengaluru-specific (as opposed to Noida) winner name could be confirmed
from public sources at time of writing — treat "Dragverse" as the flagship/global winner of the
July 2026 India series.

---

## 1. Windows on Snapdragon AI Hackathon (Devpost, Jan 13 – Feb 24, 2025)

- **What:** Global, fully virtual, $20,000-prize hackathon: build Windows apps using models from
  **Qualcomm AI Hub**, running on-device on Snapdragon X Series NPUs (via ONNX Runtime, TFLite,
  or Qualcomm AI Engine Direct/QNN). Sponsor-run and judge-scored by Qualcomm.
- **Judging rubric (5 dimensions):** technological implementation & code quality; UX/design;
  potential impact; idea creativity/uniqueness; **optimization of QAI Hub models with on-device
  performance metrics** — i.e., they explicitly scored *measured* NPU performance, not just "it
  runs."
- **Winners (from the Devpost project gallery):**
  1. **AudioNova** — local AI voice generation/transformation using **Whisper optimized for
     Snapdragon X** (NPU-accelerated). 1st place.
  2. **Snapdragon AI: Multilingual Translator** — real-time on-device translation across
     languages, no internet. 2nd place.
  3. **Civil Dialog** — a moderated "safe discourse" chat app filtering trolling/insults locally.
     3rd place.
- **Ideas for QNet Home:**
  - The rubric explicitly rewards *quantified* on-device performance metrics — we should report
    concrete NPU utilization/latency numbers for our SLM/VLM and TTS/STT pipeline stages, not just
    claim "runs on-device."
  - Voice transformation (AudioNova) winning 1st place validates that **on-device voice
    cloning/transformation is judge-legible and impressive** — reinforces our "speak in the
    parent's cloned voice" feature as a strong, demoable differentiator, not a gimmick.
  - "No internet dependency" / local-only framing is a repeated, judge-rewarded talking point
    across nearly every winner in every contest below — make our "only semantic events leave the
    edge node, never video/audio" privacy claim front-and-center and demonstrably testable (e.g.
    show Wireshark/network monitor with zero video bytes leaving the LAN).

---

## 2. Qualcomm Edge AI Developer Hackathon — Bengaluru (June 14–15, 2025)

- **What:** First global edition of Qualcomm's "Edge AI Developer Hackathon" series (distinct
  from Snapdragon Multiverse), open track, prizes: Snapdragon-powered ASUS laptops, POCO F6
  Deadpool Edition phones, blog/Discord features.
- **Notable winning app categories reported:** an LLM-driven **spontaneous gameplay commentary**
  app, and a **real-time posture coaching** app (full winner blog page was paywalled behind a
  cookie-consent gate at fetch time; category descriptions confirmed via secondary coverage).
- **Idea for QNet Home:** "real-time posture coaching" is adjacent to pose-estimation fall
  detection — evidence that **pose-estimation-based coaching/monitoring apps are a recurring,
  moderately common genre** in this ecosystem. Fall detection specifically wasn't a named winner
  here, but the adjacent genre (posture/motion analysis via vision pipeline) is clearly something
  judges have already seen — reinforce the point in Section 6 below.

## 3. Qualcomm Edge AI Developer Hackathon — Korea ("on-device AI developers," Feb 2026)

Five winning teams (full detail obtained):

| Team | Project | Stack | Notable angle |
|---|---|---|---|
| E.M.Pilot | Local AI email client | Tauri/React + YOLOv8 + **Qwen2-7B-Instruct** + EasyOCR + Nomic-Embed | privacy + zero subscription |
| FileFairy | Semantic file search/auto-rename | SvelteKit + FastAPI + LanceDB + Nomic-Embed + **Qwen3-4B** via Ollama/ONNX | fully local RAG over filesystem |
| emerGen | Emergency-response voice/text assistant | **Llama-3.2-3B-Instruct** + Whisper-Base-En + vector DB, no cloud | disaster-guidance domain |
| Medly | Speech→plain-language medical explainer | **Qwen2.5-7B-Instruct** + biomedical-NER, ran on Galaxy Book4 Edge (X1E-80-100, Hexagon NPU, QNN) | adjustable reading levels (Child/Student/Adult) |
| MyStoryPal | Collaborative kids' storybook generator | **Llama-3.2-3B-Instruct** + Stable Diffusion v2.1 + CLIP, all on NPU | illustration every 4 sentences |

Six more shortlisted, incl. **Famigo AI** — "family AI assistant" with **voice interface and
memory sharing** (very close conceptually to our kid-monitoring pillar) and **Seecurity** —
real-time on-screen privacy protection.

- **Ideas for QNet Home:**
  1. Small (3B–7B) instruct LLMs (Llama-3.2-3B, Qwen2.5-7B/Qwen3-4B) running fully on Hexagon NPU
     via QNN are the *de facto* standard model size class for this hardware class in 2025–2026 —
     validates our SLM choice; we should pick something in this same 3B–8B range and cite QNN.
  2. **Famigo AI ("family AI assistant" with voice + memory sharing) already existed as a
     shortlisted concept** — a warning sign that "family assistant with voice" alone is not
     unique enough; our differentiator must be the **cross-device semantic-event architecture +
     the parent-voice-cloning intervention mechanic + the two distinct use cases (elder fall
     response and kid monitoring) sharing one reusable pipeline**, not just "a family assistant."
  3. emerGen shows judges reward **voice-and-text dual-input** assistants for
     emergency/care contexts — matches our "two-way voice conversation" fall-response feature;
     lean into that as validated territory.

## 4. Edge Impulse Hackathon 2025 (Oct 30 – Nov 30, 2025; winners announced Dec 18, 2025)

Not Qualcomm-run but heavily Qualcomm/Dragonwing-adjacent (targets Qualcomm-based SBCs like Rubik
Pi 3 / QCS6490, plus generic MCUs). >1,000 developers, 156 submissions, 5 winners:

1. **Ocean Water Quality Classification** (Best Overall) — ESP32-S3 + sensor fusion, Edge Impulse
   model, **99.4% accuracy, 2ms inference**, LoRa → Home Assistant dashboard. Won on measured
   accuracy + measured latency + real public-health framing + strong docs (GitHub, demo video,
   public EI project).
2. **TotTalk Box** (Best Edge AI App) — Raspberry Pi 3 + webcam, Edge Impulse YOLO Pro (20-class,
   256 images) + Whisper, int8-quantized, **fully offline, no screen** toddler speech-coaching
   toy.
3. **Dendritic NN Impulse Block** (Best Model Development) — custom PyTorch block, keyword
   spotting, **90% compression, no accuracy loss** — ecosystem-extension play.
4. **Sane.AI** (Impact Award) — underground water-leak detection via geophone + 1D-CNN on a
   Samsung Galaxy Tab A9+, **87.7% accuracy** with temporal false-positive filtering.
5. **Albaricoque** (Student Award) — **camera-free** perimeter/gate intrusion detection: Arduino
   Nano 33 BLE Sense Rev2 + 4×PIR + 3×ultrasonic sensor fusion, **86.1% accuracy**, explicitly
   pitched as **privacy-preserving because there is no camera at all**.
- **Ideas for QNet Home:**
  1. Every single winner reported a **specific accuracy % and a specific inference-time number**.
     This is the clearest, most consistent signal in all the research: **judges/organizers expect
     a hard number, not a vibe.** We must benchmark and quote: fall-detection pose-model accuracy
     on our test clips, end-to-end event-to-TTS-response latency in ms, and NPU vs CPU power draw.
  2. Albaricoque's "no camera = privacy" framing is exactly our pitch (edge nodes emit semantic
     events, not video) — but it shows a judge-tested way to *state* it: emphasize the *absence*
     of a capability (no raw stream ever leaves the device) as the security/privacy claim, backed
     by a concrete architecture diagram, not just a promise.

## 5. Qualcomm x Meta ExecuTorch Hackathon (lablab.ai, June 27–28, 2026, San Francisco)

- **What:** On-site, 150-person cap, teams of 3–5, challenge = "take a PyTorch model to
  ExecuTorch and run it locally on a Samsung Galaxy S25 Ultra," privacy-first / no cloud.
  Prizes: Meta Quest 3 (top teams), Ray-Ban Meta AI Glasses (Team's Choice), Qualcomm DevRel +
  App Store publishing support.
- **Notable projects:** **Project Hermes** (Android accessibility + real-time translation
  assistant across text/camera/voice, Kotlin + ExecuTorch/QNN), **SnapOn** (offline multimodal
  "point camera + ask" assistant for people/objects/documents/scenes, Snapdragon NPU + ExecuTorch,
  explicitly "total privacy, no cloud"), plus **EchoWalk** and **Beacon** (named but not detailed
  in available sources).
- **Ideas for QNet Home:** ExecuTorch + QNN on-device multimodal (camera+voice) assistants are a
  currently very "hot" genre for Qualcomm-sponsored contests — good validation that our
  vision+audio→agent pipeline is on-trend, but also a crowd signal: **generic "point your phone,
  ask a question" assistants are becoming common** — our distributed *home* (not single-device)
  angle and the two-way proactive intervention (system speaks first, unprompted) is the
  differentiator to keep hammering, since none of these projects show unprompted proactive
  agent-initiated intervention — they're all reactive query-response.

## 6. MIT Reality Hack 2025 (Jan 2025, sponsored by Qualcomm with RB3 Gen 2 dev kits)

Three category winners using the Qualcomm **RB3 Gen 2** (QCS6490-class robotics/vision dev kit):

- **Neuroveil** (Best AI) — synced brainwave signals between two people via OpenBCI, custom model
  identifying signal source, inference on RB3 Gen 2 in Docker.
- **FarSight** (Best Social Impact, inspired by the LA wildfires) — a **rover** running object
  detection for people/pets/fire-hotspots + air-quality/temperature sensing, RB3 Gen 2 for
  inference, VR display for firefighters; **3D-printed mounts fusing the RB3 dev kit with an
  Arduino board** on the same chassis.
- **RealityBridge** (Best IoT) — handheld RB3 Gen 2 "scanner" that classifies real-world objects
  and **publishes the latest high-confidence detection to a Redis server**, consumed by a separate
  VR/Unity app (via SketchFab API) to spawn matching 3D models — i.e., a working
  **publish-semantic-event / subscribe-and-act architecture across two different devices**,
  exactly the QNet Home pattern (edge node emits event → separate consumer decides what to do).
- **Ideas for QNet Home:**
  1. RealityBridge is direct precedent that **"detector device publishes a small semantic event
     (label + confidence) to a lightweight broker (Redis/MQTT), consumer device subscribes and
     acts"** is a proven, judge-rewarded pattern — validates our exact architecture choice; cite
     it as precedent when we explain why we didn't just stream video.
  2. FarSight shows Qualcomm judges reward **actually combining the Arduino board with the
     Qualcomm compute board physically/functionally**, not treating the Arduino as an afterthought
     — good justification for giving the Arduino UNO Q real sensing/actuation responsibility
     (e.g., driving the room speaker/lights or reading a physical button/mic array) rather than
     just running a Python script on its Linux side.

## 7. NYU Hackathon ("Why NYU Hackathon Winners Choose Snapdragon X Elite," July 2025)

- Confirmed to exist via Qualcomm developer blog title; full article body was not retrievable
  (JS-rendered/blocked). Headline framing ("From Old to Elite: how NYU hack winners embraced
  Snapdragon X") suggests a case-study angle about migrating existing projects to run on
  Snapdragon X Elite NPU rather than cloud/GPU — consistent with the broader pattern of
  "on-device NPU migration" being a story Qualcomm likes to publish, reinforcing that **framing
  our submission explicitly around "why we chose NPU-on-device over cloud, and what we measured"**
  is a narrative Qualcomm's own DevRel already amplifies.

## 8. Adjacent ecosystem signal: Qualcomm's own dev-blog is already pointing at our exact stack

While researching, Qualcomm's developer blog (as of ~July 2026) surfaced these directly relevant,
very recent posts — not hackathon results, but they tell us what Qualcomm itself is currently
promoting, which is a strong proxy for what judges (often Qualcomm engineers) will find exciting
right now:

- **"How to connect Gmail to OpenClaw: GOG skill setup for vibe coders"** (May 2026) — confirms
  **OpenClaw is a Qualcomm-endorsed/blogged agent framework**, built around a **"skills" plugin
  system** (GOG = Google Operations Gateway skill giving OAuth access to Gmail/Calendar/
  Drive/Sheets/Docs). Qualcomm's own framing: agents should go "from conversationalists to
  executors," and the vision explicitly includes **multi-device orchestration with minimal user
  instruction**. This directly legitimizes our OpenClaw + tool-calling architecture — we are
  building exactly what Qualcomm's DevRel is currently evangelizing, so our pitch can explicitly
  say "we extend Qualcomm's own OpenClaw skills model to a new skill category: real-world home
  safety events," which is a strong, judge-legible hook.
- **"The Arduino UNO Q Board: Unpack the Dual-Brain Power for Next-Gen Edge AI"** (May 2026) —
  confirms hardware detail: UNO Q = **Qualcomm Dragonwing QRB2210 SoC (Debian Linux, Adreno 702
  GPU)** for AI/CV workloads, **+ STMicro STM32U585 MCU (Zephyr/Arduino Core)** for real-time
  control, bridged via RPC. Good to cite exact chip names in our technical writeup for
  credibility.
- **"On-Device Agentic AI Workflows with Qualcomm Hexagon NPU and LLMWare.ai"** (May 2026) — shows
  Qualcomm promoting agentic pipelines (Jira-ticket triage → AI summary → email) via
  Windows ML/ONNX Runtime/QNN and small NPU-resident models; no hard perf numbers given (a gap we
  can beat by publishing our own numbers).
- **GenieX** (June 2026 dev preview) — new Qualcomm/Nexa-AI open-source runtime combining
  llama.cpp + Qualcomm AI Runtime for one-line-of-code LLM inference on NPU/GPU/CPU across
  Windows/Android/Linux ARM64; supports "multimodal and agentic workflows." Worth evaluating as an
  alternative/complement to whatever inference runtime we pick for the PC's SLM/VLM, since it's
  brand-new and Qualcomm will likely want to see teams using it.

---

## Overdone / saturated ideas to avoid or clearly differentiate from

1. **Generic offline translators / transcription / meeting-note apps** — extremely common
   (multiple winners across Windows-on-Snapdragon and Korea hackathons). Not our territory, fine.
2. **"Point your phone/camera and ask a question" multimodal assistants** (SnapOn, Hermes,
   E.M.Pilot) — a very hot, increasingly saturated genre. QNet Home is *not* this (we're
   proactive/ambient, not query-driven), but be ready for judges to lump us in — explicitly call
   out "unprompted, agent-initiated intervention across rooms" as the distinction in the pitch.
3. **"Family assistant" with voice** (Famigo AI, Korea shortlist) already exists as a concept.
   Differentiate hard on: (a) multi-room heterogeneous-device sensing with semantic-event-only
   privacy model, (b) the parent-voice-cloning intervention mechanic, (c) one reusable
   architecture serving two very different use cases (elder safety + kid monitoring).
4. **Fall detection / posture coaching via pose estimation** is a well-trodden research area
   generally (multiple 2024–2026 arXiv/MDPI papers) and adjacent to a named Bengaluru-hackathon
   winner category ("real-time posture coaching"). It is *not* yet directly a named Qualcomm
   hackathon winner as literal "fall detection," so it's not disqualifying — but judges have seen
   the pose-estimation-on-edge genre before. **Don't pitch "fall detection" as the innovation** —
   pitch the **distributed semantic-event architecture + the caregiver conversation/escalation
   loop + reusable multi-room framework** as the innovation, with fall detection as merely one of
   several event types the framework already handles (this matches exactly how the rubric weights
   "Use-Case & Innovation" at only 25/100 vs. "Technical Implementation" at 40/100 — architecture
   and measured performance should be the star, not the sensor trick).
5. **Robot-arm / sim-to-real RL demos** (Dragverse) just won the immediate predecessor event —
   if any other team tries to replicate that exact demo, it will look derivative; we are not
   competing in that lane anyway.

---

## Ranked "Top ideas for QNet Home" from this domain research

1. **Publish hard numbers, not vibes.** Every single winning project across Edge Impulse, WoS-AI,
   and Korea hackathons cited a specific accuracy % and/or inference latency in ms, and WoS-AI's
   rubric explicitly scores "on-device performance metrics." Build a benchmark table into our
   pitch deck: fall/event-detection accuracy on test clips, end-to-end sense→speak latency (ms),
   NPU utilization %, and power draw comparison NPU-vs-CPU. This is worth real points on the
   40-pt Technical Implementation criterion and is the single most differentiating, low-cost thing
   we can do before Aug 7.

2. **Narrate the architecture the way Dragverse (our direct predecessor's winner) did:** name each
   device and state the one thing only it can do in the causal chain (Arduino UNO Q senses via
   GStreamer + emits a semantic event with zero raw media → Copilot+ PC's OpenClaw agent reasons,
   decides, and speaks/calls tools → AIC100 in the cloud optionally handles heavier
   voice-cloning/inference offload → edge node executes local actuation like lights/speaker).
   Multi-device *role distinctness*, not multi-device *presence*, is what won.

3. **Explicitly position on top of OpenClaw's own "skills" model** (Qualcomm's own May-2026 blog
   post on OpenClaw + GOG skill) — frame QNet Home as "a new class of OpenClaw skill: ambient
   home-safety events," which ties our project directly to a framework Qualcomm DevRel is already
   promoting internally. This is a rhetorical anchor a Qualcomm-employee judge will recognize
   immediately.

4. **Use the "absence" framing for privacy, backed by proof, not promise** (per Albaricoque's
   camera-free pitch and our own "no video ever leaves the room" claim): show a live
   network-monitor/packet-capture during the demo proving only small JSON semantic events cross
   the LAN — never raw video/audio. A visual proof beats a slide claim.

5. **Do NOT lead with "fall detection."** It's a well-known genre (research papers, adjacent
   hackathon category "posture coaching") and risks reading as generic under the 25-pt
   Use-Case/Innovation criterion. Lead with the **reusable distributed-agent architecture** and
   the **parent-voice-cloning consented intervention** twist — no comparable Qualcomm-hackathon
   winner has been found using cloned/consented voice as the response modality; this looks like a
   genuinely unclaimed angle.

6. **Pick a 3B–8B instruct SLM/VLM and say so by name with the runtime**, matching what nearly
   every 2025–2026 winner used (Llama-3.2-3B-Instruct, Qwen2.5-7B-Instruct, Qwen3-4B) via
   QNN/ONNX Runtime/Qualcomm AI Engine Direct. Evaluate the brand-new **GenieX** runtime
   (llama.cpp + Qualcomm AI Runtime, one-line inference, explicit agentic-workflow support,
   released June 2026) as a fast path to NPU-resident inference if our current stack is behind
   schedule — it is new enough that using it may itself be a small "why we picked cutting-edge
   Qualcomm tooling" talking point.

7. **Treat the Arduino UNO Q as a real actor, not a prop** (per FarSight's judged win for
   physically fusing the Arduino with the vision compute board): give it genuine
   sensing/actuation duty (e.g., mic array trigger, physical light/speaker control, or a
   button-based caregiver ack) rather than only running GStreamer as a background service —
   judges have rewarded teams that visibly use every kit device for something load-bearing.

8. **Consider a lightweight pub/sub layer (MQTT/Redis-style) between the edge nodes and the PC
   agent**, mirroring RealityBridge's judge-rewarded "detector publishes event → separate consumer
   subscribes and acts" pattern from MIT Reality Hack — this is both a sound engineering choice
   and a legible architecture diagram for judges who have seen (and rewarded) this exact shape
   before.

---

## Sources

- [Snapdragon Multiverse Hackathon | Princeton](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon | MIT CSAIL](https://www.csail.mit.edu/event/snapdragon-multiverse-hackathon)
- [Snapdragon Multiverse Hackathon | Bangalore](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)
- [Snapdragon Multiverse Hackathon | Noida](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-noida)
- [Qualcomm India Opens Registrations for Snapdragon Multiverse Hackathon (press release)](https://vmpl.scnwire.com/2026/06/qualcomm-india-opens-registrations-for.html)
- [Team led by city youth emerges winner at Qualcomm hackathon — The Tribune](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [Windows on Snapdragon AI Hackathon — Devpost](https://wos-ai.devpost.com/)
- [Windows on Snapdragon AI Hackathon — Project Gallery](https://wos-ai.devpost.com/project-gallery)
- [Edge AI developer hackathon in Bengaluru: and the winners are... — Qualcomm](https://www.qualcomm.com/developer/blog/2025/11/qualcomm-edge-ai-developer-hackathon-2025-bengaluru)
- [On-device AI hackathon in Korea: winners and highlights — Qualcomm](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea)
- [Edge Impulse Hackathon 2025: And the Winners Are...](https://www.edgeimpulse.com/blog/edge-impulse-contest-2025-winners/)
- [What a Year! Recapping Edge Impulse's 2025](https://www.edgeimpulse.com/blog/edge-impulse-2025-in-review/)
- [[Recap] Qualcomm x Meta ExecuTorch Hackathon — lablab.ai](https://lablab.ai/ai-hackathons/qualcomm-x-meta-executorch-hackathon)
- [Qualcomm RB3 Gen 2 development kit at MIT Reality Hack 2025 — Qualcomm](https://www.qualcomm.com/developer/blog/2025/02/rb3-gen-2-development-kit-mit-reality-hack-2025)
- [From Old to Elite: how NYU hack winners embraced Snapdragon X — Qualcomm](https://www.qualcomm.com/developer/blog/2025/07/from-old-to-elite-how-nyu-hack-winners-embraced-snapdragon)
- [How to connect Gmail to OpenClaw: GOG skill setup for vibe coders — Qualcomm](https://www.qualcomm.com/developer/blog/2026/05/connect-gmail-openclaw-gog-skill)
- [The Arduino UNO Q Board: Unpack the Dual-Brain Power for Next-Gen Edge AI — Qualcomm](https://www.qualcomm.com/developer/blog/2026/05/the-arduino-uno-q-board--unpack-the-dual-brain-power-for-next-ge)
- [On-Device Agentic AI Workflows with Qualcomm Hexagon NPU and LLMWare.ai — Qualcomm](https://www.qualcomm.com/developer/blog/2026/05/local-agentic-ai-with-llmware-on-pcs-with-snapdragon-x-series)
- [GenieX developer preview: run generative AI on Qualcomm chipsets — Qualcomm](https://www.qualcomm.com/developer/blog/2026/06/geniex-developer-preview)
- [Qualcomm India next-gen innovation global Edge AI Hackathon — VARINDIA](https://www.varindia.com/news/qualcomm-india-powers-next-gen-innovation-with-global-edge-ai-hackathon)
- [Qualcomm India Launches Global Edge AI Developer Hackathon Series — PR Newswire](https://www.prnewswire.com/in/news-releases/qualcomm-india-launches-global-edge-ai-developer-hackathon-series-302466732.html)
