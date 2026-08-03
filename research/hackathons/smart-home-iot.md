# Smart-Home / IoT Hackathon & Contest Research (Aug 2024 – Aug 2026)

Research for QNet Home (Snapdragon Multiverse Hackathon, Aug 3-7 2026). Goal: find winning patterns in smart-home/IoT competitions, identify overdone ideas, and extract concrete, actionable ideas for our pitch and technical build.

---

## 1. Home Assistant Voice Assistant Community Contest (2023-2024)

The most influential *local-first* smart-home contest of the last two years — Home Assistant's own community, judged by HA core devs, ~for the "Year of the Voice" initiative.

**Winners / notable projects:**
- **Bender Voice Assistant** (dirtyharriv) — Most Creative Satellite Idea. Custom wake word, in-character custom voice, 3D-printed enclosure with LEDs. ([thread](https://community.home-assistant.io/t/bender-voice-assistant/682041))
- **homeThing S3** (landonr) — Best Starting Guides. iPod-style remote: rotary dial, screen, IR blaster, mic, speaker, battery, fully open-source PCB + ESPHome config. ([thread](https://community.home-assistant.io/t/homething-s3-ipod-smart-home-remote-with-voice-control/702666))
- **View Assist** (dinki) — Best Voice Experiences. Turns an Android tablet into an Echo-Show-like visual UI for Assist. ([thread](https://community.home-assistant.io/t/view-assist-visual-feedback-for-assist-voice-assistant-on-an-android-tablet-install-info-provided-on-wiki/699659))
- **HA-Visual-Voice-Assistant** (Rellu) — Community Choice winner. AI-generated character videos as visual feedback for voice commands, swappable characters/languages. ([thread](https://community.home-assistant.io/t/voice-assistant-contest-ha-visual-voice-assistant/687593))
- Runner-up: S3 Box firmware hack enabling text display "previously considered impossible" — patch later merged into official firmware.

**What made these win:** not raw capability but *character/personality* (custom wake words, voices, visual feedback) and *polish of the physical object* (3D printing, PCB design). Pure "it detects X and sends an alert" entries did not headline; **presence, personality, and delight** did.

**Ideas for QNet Home:**
- Give the room-speaker persona a light "character" layer (name, consistent tone) distinct from a generic TTS voice — judges reward personality, not just function.
- A visual feedback surface (even a simple LED ring / small screen state on the Arduino node) reads as "voice assistant is alive" to judges watching a demo — cheap, high perceived polish.

**Architecture note (for our report on event-bus patterns):** HA's own **Wyoming protocol** (rhasspy/wyoming-satellite, [GitHub](https://github.com/rhasspy/wyoming-satellite)) is the reference for distributed voice satellites talking to a central brain over a lightweight local protocol — conceptually identical to what we're doing between UNO Q nodes and the Copilot+ PC, but for audio streaming rather than semantic events. The **Home Assistant Voice Preview Edition** ($59, late 2024) deliberately splits jobs across chips (ESP32-S3 for networking/orchestration, XMOS XU316 DSP for echo-cancellation/beamforming/noise suppression) — a "split-brain" hardware pattern worth citing as precedent for our Arduino-node/PC split. ([Notebookcheck coverage](https://www.notebookcheck.net/Home-Assistant-launches-new-privacy-first-voice-assistant-hardware.937193.0.html), [Wyoming integration](https://www.home-assistant.io/integrations/wyoming/))

---

## 2. Nordic Semiconductor "Make it Matter!" (Hackster.io, 2023-2024)

759 participants, 82 countries, 61 finalists — the largest recent Matter-focused hardware contest.

**Winners:**
- **Posture-detection lighting** (Jens) — ML model distinguishes good/bad posture, nudges via smart lights when posture degrades. Cross-modality feedback (vision → lighting actuator).
- **Smart turtle habitat controller** — praised for clean multi-endpoint Matter implementation (temperature, humidity, feeding — several Matter clusters on one device).
- **Wildcard: indoor garden assistant** (Philipp Manstein).
- 10 runners-up, various home-automation submissions.
([Hackster contest page](https://www.hackster.io/contests/makeitmatter), [Nordic announcement](https://www.nordicsemi.com/Nordic-news/2023/09/Nordic-Semiconductor-and-Hacksterio-launch-Make-it-Matter-design-competition))

**What made these win:** technically clean protocol integration (multiple Matter endpoints/clusters correctly wired) + a clear "detect condition → nudge behavior change" loop, not raw novelty of sensor.

**Idea for QNet Home:** the "detect a condition, then *actuate* a calm/behavior-changing response" loop (posture → light nudge) is structurally identical to our "fall/distress detected → speak reassurance + flicker lights" loop. This validates the pattern but confirms it's now common — we need to win on the *conversational/agentic* depth (two-way dialog, tool-calling, voice cloning) on top of it, not the detect→actuate loop alone.

---

## 3. Qualcomm Edge AI Developer Hackathon — Korea (~Feb 2026) — MOST DIRECTLY RELEVANT

Same sponsor family as our event; explicitly Snapdragon X Elite NPU-focused, so its winners are the closest available signal for **how Qualcomm judges score on-device AI**. ([Qualcomm recap](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea))

**5 winning teams:**
1. **E.M.Pilot** — on-device AI email client (Qwen2-7B-Instruct, YOLOv8, EasyOCR, Nomic-Embed-Text; Tauri/React + Flask). Judges: *"All data stays private, and you get high performance without extra costs."*
2. **File Fairy** — semantic file search/auto-rename (Qwen3-4B, Nomic-Embed-Text, LanceDB vector DB). Judges praised "lightning-fast similarity searches," privacy-first architecture.
3. **emerGen** (Team UNIDs) — emergency-response assistant: Llama-3.2-3B-Instruct + Whisper-Base-En + vector DB retrieval of disaster guidelines, voice/text Q&A. Judges liked that it needed **no fine-tuning** — a pragmatic edge architecture.
4. **Medly** (Team Synaptix) — real-time medical-jargon translator on the Snapdragon X Elite NPU; Qwen2.5-7B-Instruct + Live Caption + Tesseract OCR, adjustable reading level, PDF report gen. Judges: *"All AI computations processed directly on device's NPU for maximum speed."*
5. **MyStoryPal** — children's co-created storybook app; Llama-3.2-3B-Instruct + Stable Diffusion v2.1 + CLIP, auto-illustrates every 4 sentences. Judges liked the **language-learning + generative art loop for kids**.

**Shortlisted (6 more):** WINE Lab (secure messenger), Paperclip (tone-aware writing assistant), Seecurity (screen-privacy protection), **Famigo AI (family voice assistant)**, Team Rocket (itinerary planner), Jae2 (window-arrangement optimizer).

**Cross-cutting pattern:** every single winner explicitly leaned on **"processed entirely on NPU / on-device / no cloud"** as the phrase judges quoted back. This is a strong signal: **explicit, named NPU/on-device framing + measurable "why this is fast/private" is what got called out**, not just a cool app idea. None of the 5 winners were multi-device — they were all single-PC apps. This is actually good news for us: a genuinely multi-device architecture (2 UNO Q edge nodes + PC + phone + cloud AIC100) is a step up in ambition versus what won at a sibling Qualcomm event, IF we can demonstrate the same crisp "why is this fast/private" story per device.

**Related — Famigo (academic, not this hackathon but same name/space):** an IEEE paper, *"Famigo: A Privacy-Preserving Hybrid Voice Assistant for Multi-User Family Environments"* ([IEEE Xplore](https://ieeexplore.ieee.org/document/11385934/)), describes a **parallel-repository architecture** that keeps each family member's private memory separate from shared household knowledge, combining lightweight on-device voice processing with cloud LLM/RAG, reporting **2-3s end-to-end latency**. This is a close conceptual cousin to our multi-user household problem (parent vs. kid vs. elderly resident all interacting with the same home AI) — worth citing as prior art and worth differentiating from (we do fully local SLM/VLM reasoning on the PC NPU, not cloud RAG, and add semantic-event ingestion from remote nodes, not just voice).

**Ideas for QNet Home:**
- Explicitly quote NPU utilization and latency numbers for each stage of our pipeline (Arduino pose-estimation inference time, PC SLM/VLM decision latency, TTS/STT latency) — mirror the "processed directly on device's NPU" framing that every Korea winner got credited for.
- Consider a lightweight "family memory separation" angle (kid profile vs. elderly-resident profile vs. parent profile) inspired by Famigo's parallel-repository idea — reinforces our privacy pitch without needing cloud RAG.

---

## 4. Samsung Developer Conference 2024 — SmartThings Innovation Challenge

Samsung's first-ever SmartThings hackathon-style challenge, run alongside SDC24 (Oct 3, 2024, San Jose). Two challenge themes (new SmartThings feature/enhancement, or new driver); finalists pitched live to judges; winners got a 55" Frame TV. ([Samsung blog](https://blog.smartthings.com/developers/sdc24-smartthings-innovation-challenge-win-a-samsung-frame-tv/))

Detailed winner project write-ups were not publicly indexed (no Devpost-style gallery), which itself is a data point: **Samsung's ecosystem challenge did not generate lasting public case studies** the way Hackster/Devpost communities do — suggesting big-platform vendor hackathons (SmartThings, Alexa) get less durable community mindshare than open, judged-portfolio contests (Hackster, HA community, Qualcomm's own series). For our own presentation/documentation scoring (15 pts), this argues for a genuinely thorough public writeup (README, video, architecture diagram) since that's exactly what separates a memorable entry from a forgotten one a year later.

---

## 5. AWS "Reinventing Healthy Spaces" (Hackster.io + AWS IoT EduKit)

$10,000 across 8 winners (1 grand prize + 2 runners-up + 5 finalists), using AWS IoT EduKit reference hardware for indoor-environment/health use cases. ([contest](https://www.hackster.io/contests/Healthy-Spaces-with-AWS))

- **1st: Markel Robregado.**
- **2nd: Steve Kasuya** — automatic ventilation system: CO2 monitor + fan actuator triggered by sensor thresholds, closed feedback loop.
- **3rd: Mick Jacobsson.**

**Pattern:** winning entries were narrow, well-instrumented **sense → decide → actuate** loops with a clear numeric trigger (CO2 ppm threshold), not broad platforms. **Idea for QNet Home:** for each of our two use cases (fall/elder response, kid monitoring), make sure we can name the exact numeric trigger/threshold (e.g., pose-estimation confidence + limb-angle heuristic for "fall," dB threshold + duration for "loud sound/distress cry," time-of-day + motion pattern for "TV time / dangerous play") — judges reward legible, inspectable logic over "the AI figures it out" hand-waving.

---

## 6. Penn President's Innovation Prize 2025 — "Sync Labs" (elder-care, not a hackathon but a major judged competition)

$150K total prize. Sensors disguised as **picture frames** placed in kitchen/bathroom detect eating habits, bathroom frequency/duration, falls, and presence — **entirely on-device, no video streamed or recorded.** Pitch: lets one caregiver serve **3x more seniors/day**. ([Penn Today](https://penntoday.upenn.edu/news/penn-students-develop-ai-driven-solution-transform-senior-care))

**Directly overlapping competitor concept to our elder-care use case** — and it's not alone:
- **AltumView "Sentinare"** (commercial product, [altumview.ca](https://www.altumview.ca/)) — converts people into **stick-figure skeletons on-device** before any data leaves the sensor. Detects: falls (up to 6m range, including *slow* falls), bed-leaving, wandering into restricted zones, overstay/absence in a zone, hand-wave for help, sit/stand/lie activity stats, optional face recognition. Marketed explicitly for bedrooms/bathrooms because no video ever leaves the device.
- **EdgeCare.ai** — "privacy-first edge AI... zero video ever leaves the home," passive cameras, no wearables.
- **Veron Care** — radar-based (not camera) room monitoring for a privacy angle.

**CRITICAL TAKEAWAY — fall detection + "no video, only skeleton/pose" is an OVERDONE, commercially saturated idea.** There is an entire sub-industry (Sentinare, EdgeCare.ai, Veron Care, Sync Labs, plus dozens of hackathon "elderly fall detection" GitHub repos going back to 2016-era Hackster/Hackaday projects, e.g. [Hackaday "Elderly Autonomous Fall Detection"](https://hackaday.io/project/26983/logs), [Hackster fall-detection-for-the-elderly](https://www.hackster.io/coderscafe/fall-detection-for-the-elderly-698924)) built on exactly "pose/skeleton on-device, no video, detect fall, alert caregiver." If we pitch "fall detection with privacy-preserving pose estimation" as our headline, judges who've seen *any* of this space will read it as generic.

**How to differentiate (what none of these commercial/prize competitors do):**
1. None of them **talk back**. They're alert-only pipelines (detect → notify caregiver app). Our two-way voice conversation ("Are you OK? Should I call someone?") with an on-device SLM/VLM reasoning about context and *escalating intelligently* (not just threshold-alert) is the differentiator — that's an agentic layer none of Sentinare/EdgeCare/Sync Labs have.
2. None of them are **multi-device, cross-room, orchestrated** — they're single-sensor-to-app products. Our architecture (2+ heterogeneous edge nodes + a reasoning hub + phone + optional cloud burst to AIC100) is the "multi-device AI orchestration" story the hackathon explicitly wants, and it's not what the eldercare-privacy-camera market is building.
3. **Voice cloning for kid-monitoring is comparatively unclaimed territory** — no hackathon or commercial competitor found doing "parent's cloned voice intervenes in a kid-monitoring event." This is a much fresher wedge than fall detection. (Caution found in research: there's active public concern about AI voice-cloning of children as a *child-safety risk*, e.g. [HiWave Blog](https://hiwavemakers.com/blog/ai-voice-cloning-child-safety-parents/) — the reverse of our use case, but it means judges/audience will already have voice-cloning-and-kids top of mind; leading with **explicit consent, opt-in registration, and on-device-only voice-clone storage** in the pitch will read as thoughtful rather than risky.)

**Recommendation:** De-emphasize "fall detection" as the headline; keep it as one supported scenario, but lead the pitch with the **agentic two-way conversation + cross-device orchestration + parent-voice intervention** as the novel core, explicitly naming that we know eldercare-privacy-camera products exist and are going further (conversational response, not just alerting).

---

## 7. Alexa Skills Challenges (Multimodal 2023-24; Arduino Smart Home Challenge)

- **Alexa Skills Challenge: Multimodal** — 999 participants, 350+ skills submitted, $20K winner + $5K each to finalists. Focus: skills going beyond voice-only (screens, multimodal). ([Devpost](https://alexamultimodal.devpost.com/))
- **Alexa and Arduino Smart Home Challenge** — $59K+ in prizes; winner **"Walle"**, a full home-automation control panel with Alexa built in; other notable entries included a sign-language-to-Alexa glove and a robot fish-feeder. ([Amazon Alexa Blog](https://developer.amazon.com/en-US/blogs/alexa/post/bbdf8956-982b-4838-b171-d828e9f8fe05/announcing-the-winners-of-the-alexa-and-arduino-smart-home-challeng))

**Pattern:** cloud-voice-assistant-centric smart home hacks reward *novel input modality* (sign language, multimodal screens) over "yet another light/thermostat control." **Idea:** our "text the system from a meeting, have it speak in your voice to your kid" is exactly this kind of novel-input/novel-output modality twist — lean into it as a demo beat.

---

## 8. Snapdragon Multiverse Hackathon series itself (Princeton Sept 2025, Bangalore, Noida — same competition family as ours)

Directly useful for calibrating what "our own" judges reward.

- **Princeton edition rules** ([official page](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)): 3 tracks — Real-time CV Assistant (object tracking/scene understanding/anomaly detection), Conversational AI Companion (voice/text coaching/tutoring/storytelling), RL Agent Arena. Submission requirements: **GitHub repo with README, open-source license, a Windows executable, and code that prioritizes edge processing.** Two awards: a judged Top Award (scored across 4 categories) and a peer-voted Team's Choice Award.
- **Noida edition winner — "Team Ghost Map"** (led by Deepesh Kakkar, Thapar Institute): in ~30 hours built an **end-to-end edge AI robotics platform** — scan a real environment → build a digital twin → train autonomous navigation in simulation → deploy to a real robot, running entirely on Snapdragon hardware (sim-to-real pipeline). ([Tribune coverage](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/))

**Takeaway:** the winning bar at *this exact hackathon family* is a full **working, deployable, edge-first pipeline with real hardware in the loop** — not a slide-deck concept or a cloud-API wrapper. A packaged Windows .EXE with a real GitHub README is a **hard submission requirement pattern across editions**, matching our judging rubric's Deployment & Accessibility criterion (20 pts) — confirms we must nail an actual installer, not just a working demo on the dev machine.

---

## Overdone vs. fresh — summary

**Overdone (avoid leading with these, or explicitly differentiate):**
- "Camera-free / pose-only / no-video" elder fall detection — Sentinare, EdgeCare.ai, Sync Labs, Veron Care, and a decade of Hackster/Hackaday hobby projects all do this. Alert-only pipelines to a caregiver app are table stakes now, not a wow factor.
- Generic "smart lights react to sensor" loops (Matter posture-lighting, motion-triggered lighting) — clean but expected.
- Single-device "on-device NPU chatbot/assistant" apps (every Korea hackathon winner) — expected baseline for a Snapdragon event now, not differentiating by itself.
- Voice-satellite personality/character skins (HA contest) — charming but a solved, done-many-times pattern; useful as garnish, not core pitch.

**Comparatively fresh / underexploited (lean into these):**
- True **heterogeneous multi-device orchestration** (edge nodes doing perception, hub doing reasoning, phone doing notification/companion app, cloud accelerator for burst inference) — none of the smart-home contests surveyed actually did this; single sensor→app or single PC→NPU app dominates.
- **Two-way agentic conversation as the response**, not just an alert — none of the eldercare privacy-camera competitors talk back or reason about escalation.
- **Consent-based cloned-voice intervention from a trusted person** (parent) — essentially unclaimed in this space; pair with visible, explicit consent/registration UX to defuse the "AI voice cloning of kids is scary" narrative that's currently circulating.
- Explicit, named, per-device **NPU/latency/privacy numbers** in the pitch — this is what got quoted back by judges at the sibling Qualcomm Korea hackathon; treat it as a checklist item, not an afterthought.

---

## Top ideas for QNet Home (ranked)

1. **Reframe the headline pitch away from "fall detection" toward "an agentic home hub that talks back and orchestrates across devices."** Fall/distress detection is a supported scenario, not the wow-factor — the eldercare-privacy-camera market (Sentinare, EdgeCare.ai, Sync Labs, Penn Prize 2025) has already normalized "on-device, no-video, alert caregiver." Differentiate on the two-way conversational response and cross-device orchestration, which none of them have.
2. **Lead with the parent-voice-cloning kid-monitoring angle as the most novel, demo-able differentiator** — no hackathon or commercial competitor found doing this; it's fresh, and the "text from a meeting, speak in your voice to your kid" beat is a strong, novel-modality demo moment in the spirit of what won Alexa's Multimodal Challenge. Explicitly show consent/registration UX on-screen to preempt the "AI cloning kids' voices is dangerous" narrative currently in the press.
3. **Instrument and narrate per-device NPU utilization + latency numbers explicitly in the demo/pitch** (mirrors exactly what Qualcomm Korea hackathon judges quoted as their reason for picking every one of the 5 winners: "processed directly on device's NPU," "no extra cost," "lightning-fast"). Show a number for: Arduino UNO Q pose-estimation inference time, PC SLM/VLM decision latency, TTS latency, end-to-end event-to-response latency.
4. **Borrow the "parallel-repository" family-privacy idea from the Famigo architecture** (IEEE, family voice assistant): separate memory/context per household member (kid profile, elderly-resident profile, parent profile) even though we're not doing cloud RAG — reinforces the "privacy-first, per-person" pitch angle with real architectural teeth.
5. **Make the sense→decide→actuate trigger logic legible and inspectable in the demo** (name the exact heuristic/threshold, e.g., pose-angle + duration for fall, dB + duration for distress cry) — mirrors what won AWS "Reinventing Healthy Spaces" (CO2-ppm-triggered ventilation) and the Matter posture-lighting winner; judges reward "I can see why it decided that," not just "the AI figured it out."
6. **Give the on-device response a light personality/visual layer** (consistent voice/tone, maybe an LED state on the Arduino node showing "listening/thinking/speaking") — cheap production value that repeatedly won HA's community contest (Bender, View Assist, HA-Visual-Voice-Assistant) by making the assistant feel "alive" on camera.
7. **Treat the packaged Windows .EXE + thorough public GitHub README + demo video as first-class deliverables, not afterthoughts** — this is an explicit, recurring submission requirement across Snapdragon Multiverse editions (Princeton rules) and clearly separates memorable entries from forgotten ones (Samsung's SmartThings challenge left almost no public trace a year later, unlike Hackster/HA-contest entries that still have living GitHub repos/threads).
8. **The winning bar at this exact hackathon family is a full working edge-first pipeline with real hardware in the loop, not a concept demo** (cf. Noida's winning sim-to-real robotics pipeline built in ~30 hours). Budget build time to get a genuinely live, on-hardware, end-to-end path working across all 3 device tiers (UNO Q → PC → phone/cloud) even if scoped narrow, rather than a broader but partially-mocked pipeline.

---

## Sources

- [Home Assistant voice contest winners announcement](https://community.home-assistant.io/t/and-the-winners-of-our-voice-assistant-community-contest-are/704882)
- [Home Assistant Voice Assistant Contest kickoff](https://www.home-assistant.io/blog/2024/01/17/voice-assistant-contest/)
- [Wyoming protocol (rhasspy/wyoming-satellite) GitHub](https://github.com/rhasspy/wyoming-satellite)
- [Home Assistant Wyoming integration docs](https://www.home-assistant.io/integrations/wyoming/)
- [Home Assistant Voice Preview Edition coverage — Notebookcheck](https://www.notebookcheck.net/Home-Assistant-launches-new-privacy-first-voice-assistant-hardware.937193.0.html)
- [Nordic "Make it Matter!" contest page — Hackster.io](https://www.hackster.io/contests/makeitmatter)
- [Nordic Semiconductor Make it Matter launch](https://www.nordicsemi.com/Nordic-news/2023/09/Nordic-Semiconductor-and-Hacksterio-launch-Make-it-Matter-design-competition)
- [Meet the Winners of Nordic's Make it Matter Contest — Hackster News](https://www.hackster.io/news/meet-the-winners-of-nordic-semiconductor-s-make-it-matter-contest-9289d00c04d4)
- [Qualcomm Edge AI Developer Hackathon Korea — winners recap](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea)
- [Famigo: A Privacy-Preserving Hybrid Voice Assistant for Multi-User Family Environments — IEEE Xplore](https://ieeexplore.ieee.org/document/11385934/)
- [Samsung SDC24 SmartThings Innovation Challenge](https://blog.smartthings.com/developers/sdc24-smartthings-innovation-challenge-win-a-samsung-frame-tv/)
- [AWS "Reinventing Healthy Spaces" contest — Hackster.io](https://www.hackster.io/contests/Healthy-Spaces-with-AWS)
- [Penn Today — Sync Labs / President's Innovation Prize 2025](https://penntoday.upenn.edu/news/penn-students-develop-ai-driven-solution-transform-senior-care)
- [AltumView Sentinare product site](https://www.altumview.ca/)
- [EdgeCare.ai — Privacy-First Edge AI for Aging in Place](https://www.edgecare.ai/)
- [Hackaday — Elderly Autonomous Fall Detection project](https://hackaday.io/project/26983/logs)
- [Hackster — Fall Detection for the Elderly](https://www.hackster.io/coderscafe/fall-detection-for-the-elderly-698924)
- [HiWave Blog — AI Voice Cloning of Children: The New Child Safety Crisis](https://hiwavemakers.com/blog/ai-voice-cloning-child-safety-parents/)
- [Amazon Alexa Skills Challenge: Multimodal — Devpost](https://alexamultimodal.devpost.com/)
- [Announcing the Winners of the Alexa and Arduino Smart Home Challenge](https://developer.amazon.com/en-US/blogs/alexa/post/bbdf8956-982b-4838-b171-d828e9f8fe05/announcing-the-winners-of-the-alexa-and-arduino-smart-home-challeng)
- [Snapdragon Multiverse Hackathon | Princeton — official rules](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon | Noida](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-noida)
- [Team led by city youth emerges winner at Qualcomm hackathon — The Tribune](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [OOP's 2025 Healthcare AI Hackathon Projects — Out-Of-Pocket](https://www.outofpocket.health/p/oops-2025-healthcare-ai-hackathon-projects)
- [Qualcomm Cloud AI 100 / AIC100 developer overview](https://www.qualcomm.com/developer/blog/2024/01/train-anywhere-infer-qualcomm-cloud-ai-100)
- [Qualcomm Cloud AI SDK — GitHub](https://github.com/quic/cloud-ai-sdk)
- [Arduino UNO Q product page](https://www.arduino.cc/product-uno-q/)
- [Arduino and Qualcomm launch Hackster developer contest 2026 (UNO Q)](https://www.prnewswire.com/apac/news-releases/arduino-and-qualcomm-launch-hacksters-first-developer-contest-of-2026-global-competition-kicks-off-with-300-arduino-uno-q-boards-and-opportunities-to-showcase-edge-ai-innovation-302703213.html)
