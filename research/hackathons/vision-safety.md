# CV / Safety-Monitoring Hackathons & Contests — Research (Aug 2024 – Aug 2026)

Research pass for QNet Home (Snapdragon Multiverse Hackathon, Aug 3-7 2026). Goal: mine two years of edge-vision / safety-monitoring hackathons for winning patterns, overdone tropes to avoid, and concrete technical/pitch ideas.

---

## 1. NVIDIA + Hackster "AI Innovation Challenge" / "AI at the Edge Challenge" (Jetson Orin Nano, 2024)

- **What it was:** SparkFun/NVIDIA-sponsored Hackster contest giving out free Jetson Orin Nano dev kits; open "AI at the Edge" category plus a dedicated generative-AI-on-the-edge category.
- **Winners / notable projects:**
  - *Interactive Animatronic GLaDOS* (Generative AI Applications winner) — speech recognition + LLM + TTS + a 6-axis manipulator, fully local conversational character. Relevant pattern: judges reward a **fully local voice+LLM+physical-actuation loop** with personality, not just a detector.
  - *ClearWaters* — underwater image enhancement via a denoising diffusion model on Jetson AGX Orin (Generative AI Models for the Edge winner). Shows judges like **generative models pushed to edge silicon**, not just discriminative CV.
  - *Realtime Language-Segment-Anything on Jetson Orin* — open-vocabulary detection + SAM running in realtime at the edge.
  - *Escalator people tracker* (Open/"AI at the Edge" category) — people-tracking in retail spaces driving live generative graphics; team explicitly noted the **same CV pipeline generalizes to construction/build-site safety** — i.e., judges rewarded architecture reuse across verticals, exactly our "reusable multi-device architecture" pitch.
  - *Cooking meals with a local AI assistant on Jetson AGX Orin* — multimodal multi-agent fully-local conversational assistant with voice, closest analog to our Copilot+ PC agent loop.
- **Takeaway for QNet Home:** A fully-local voice-driven agent with a distinct "character"/persona (GLaDOS) reads as more inventive than a plain detector demo. Also validates the "one CV pipeline, multiple safety verticals" pitch angle we already have (fall detection + kid monitoring).

Source: [AI Innovation Challenge Roundup — SparkFun](https://news.sparkfun.com/10569), [AI at the Edge Challenge — Hackster.io](https://www.hackster.io/contests/NVIDIA)

---

## 2. Hailo Hackathon (annual internal + community, 2023/24/25 editions)

- **Format:** ~60 Hailo employees, 24-hour internal hackathon, built on Raspberry Pi 5 + Hailo AI HAT+ (Hailo-8, 26 TOPS) or Hailo-8L (13 TOPS). Projects are open-sourced afterward in `hailo-ai/hailo-rpi5-examples` and `hailo-ai/hailo-CLIP` community-projects folders on GitHub.
- **Notable projects (2024-2025):**
  - **B-AIby Monitor** — baby monitor combining cry-sound classification with activity tracking; Telegram-bot alerts + web dashboard. Technically thin (README has no explicit privacy statement, no on-device guarantee), which is exactly the **generic "baby monitor" trope we must not repeat verbatim** — it's overdone and this entry didn't differentiate technically.
  - **HailoGames ("Salted Fish")** — real-time "Red Light, Green Light" game using pose estimation on Hailo-8; good demo of turning pose estimation into an interactive, judge-engaging live demo rather than a passive dashboard.
  - **NavigAItor** — GPS/gyro-free autonomous navigation using visual landmarks only.
  - **Community fall-detection project** (Pi 5 + Hailo-8L, via Elektor writeup) — YOLOv8 pose model on Hailo-8L at **30 FPS**, using 17 keypoints grouped into head/shoulder/hip/knee/ankle bands; fall flagged only if (a) ≥2 keypoint groups collapse into the same ~30px vertical band AND (b) bounding-box aspect ratio flips (height ≤ width). On trigger it saves **one snapshot + metadata only** (no continuous video) and pushes a Twilio SMS/WhatsApp alert. This is a clean, cheap **dual-condition heuristic to suppress false positives** without a heavier temporal model — directly reusable logic for our own fall-detection node.
- **Overdone-ness warning:** Baby monitors and generic "fall detector on a Pi" are extremely common submissions in this ecosystem — the bar for winning is doing something *with* the detection (an agentic response, a game, a persona), not just detecting it.

Sources: [Hailo Hackathon 2025 blog](https://hailo.ai/blog/hailo-hackathon-2024-2025-pushing-the-limits-of-ai-innovation-on-raspberry-pi/), [B-AIby Monitor README](https://github.com/hailo-ai/hailo-CLIP/blob/main/community_projects/baiby_monitor/README.md), [Pi-5+Hailo8L fall detection — Elektor](https://www.elektormagazine.com/labs/pi-5hailo8l-ai-powered-fall-identification-recording-project)

---

## 3. Seeed Studio Vision Challenge (2024, Grove Vision AI Module V2 + XIAO ESP32C3)

- **Format:** 3-month challenge, 100 Grove Vision AI V2 kits distributed, 60+ submissions.
- **Winners / highlights:**
  - *Watching Washers* — monitors washing-machine state via the on-module vision sensor (tiny, single-purpose edge inference, no cloud).
  - *Flame-Free Farm* — fire-prevention + goat counting on a farm; combines a safety trigger with an unrelated utility count, showing judges reward **multi-purpose sensing from one node**.
  - *Step Guard 3.0* — AI-based step/fall-adjacent detection using the Grove Vision AI V2 module.
  - *Eletect* — safety + wildlife/animal-preservation detection.
- **Pattern:** All of these run detection entirely on a sub-$30 vision module (on-sensor NPU), sending only small structured outputs upstream — validates our "publish semantic events only, not video" architecture as a known, judge-approved pattern at the smallest edge tier.

Source: [Seeed Vision Challenge winners](https://www.seeedstudio.com/blog/2024/07/15/vision-challenge-winners-and-projects/) (search cache; live page returned 403 on direct fetch)

---

## 4. OpenCV AI Competition / Spatial AI Contest lineage (2023 edition, sponsored by Intel)

- **Format:** Global competition (177 submissions, 1500+ developers in the 2023 edition) built around OAK-D depth+AI cameras; descends from the original 2020-2022 "OpenCV Spatial AI Contest" (sponsored by Intel and Microsoft Azure, 50 finalist teams) which required replicating a manufacturing/safety solution on an OAK-D-Lite camera.
- **Notable winner:** *FREISA* (Four-legged Robot Ensuring Intelligent Sprinkler Automation, Team B-AROL-O) — an on-device depth-AI robot for autonomous irrigation.
- **Relevance:** This lineage established **depth-sensing + on-device inference (no cloud round-trip)** as a winning combo years before it became mainstream — an early signal that "runs entirely at the edge, low latency" beats cloud-dependent entries in these juried contests, which lines up with our AIC100/PC/edge-node split (do the semantic reasoning locally, don't ship frames).

Sources: [OpenCV AI Competition 2023 wrap — Voxel51](https://voxel51.com/blog/opencv-ai-competition-2023), [OpenCV Spatial AI Contest — Kickstarter update](https://www.kickstarter.com/projects/opencv/opencv-ai-kit/posts/2899951)

---

## 5. NVIDIA AI City Challenge (CVPR/ICCV workshop competition, 2024 = 8th edition, 2025 = 9th edition)

This is a research-grade leaderboard competition (not a weekend hackathon) but it's the most rigorous public benchmark for exactly our sensing domain, and top solutions are published papers — extremely citable ammunition for our "technical implementation" score.

- **2024 (8th) track winners:**
  - **Track 1 (multi-camera people tracking):** Team79 SJTU-LENOVO — geometric consistency + state-aware re-ID correction across camera views. Directly relevant if we ever coordinate the two UNO Q nodes' fields of view.
  - **Track 2 (traffic-safety description/analysis):** Team208 AliOpenTrek — efficient fine-tuning of a **vision-language model** to narrate "what happened" in a safety-relevant scene. This is structurally identical to what our Copilot+ PC SLM/VLM does when interpreting a semantic event ("fall detected, elderly person, near kitchen") — validates VLM-as-narrator as a competition-winning technique, not just a hackathon toy.
  - **Track 3 (naturalistic driving action recognition):** Team155 TeleAI — "augmented self-mask attention transformer" for identifying anomalous behavior from video, i.e., action recognition beyond simple pose thresholds.
  - **Track 4 (fisheye camera object detection):** Team9 VNPT AI — heavy data augmentation + ensembling to handle lens distortion; less relevant to us.
  - **Track 5 (PPE/helmet-violation detection):** Team99 UIT — Co-DETR + minority-class enhancement (helmet violations are a rare class, needed oversampling/class-balancing tricks).
- **2025 (9th) track:** Added an optional **Jetson-hardware track** — teams submit TensorRT-optimized Docker containers benchmarked on a real AGX Orin 64GB, scored by harmonic mean of F1 and normalized FPS. This validates **judges explicitly rewarding measured edge-latency/FPS numbers**, not just accuracy — matches this hackathon's Technical Implementation criterion (latency/performance, NPU offload, measured numbers).
- **Overdone-ness note:** Plain PPE/helmet detection (Track 5-style) is heavily saturated in both this competition and countless independent hackathons (see §6). If we ever touch a "wearing helmet/vest" feature, treat it as a footnote, not a headline.

Source: [2024 AI City Challenge Winners](https://www.aicitychallenge.org/2024-challenge-winners/), [The 9th AI City Challenge (2025), ICCV workshop paper](https://openaccess.thecvf.com/content/ICCV2025W/AICity/papers/Tang_The_9th_AI_City_Challenge_ICCVW_2025_paper.pdf)

---

## 6. PPE / workplace danger-zone detection (broad hackathon + open-source trend, 2024-2025)

- This is the single **most overdone** category in the entire domain. Examples found: Venture Base Hackathon 2025 YOLOv8+OpenCV PPE compliance project (96% mAP@50 claimed); the open-source `Construction-Hazard-Detection` GitHub project (YOLO for helmet/vest detection + HDBSCAN-clustered danger zones from cone coordinates + proximity-to-machinery alerts); dozens of "YOLOv8/v10/v11 PPE detection" student papers and Devpost entries.
- **Technical pattern worth stealing (not the PPE part):** the "virtual fence" technique — an enhanced YOLOv7 + pose-estimation model creates a **dynamic hazard-zone polygon** around a detected opening/machine, then checks worker joint positions against that polygon; one construction-safety paper reports 80.6% AP / 86.5% F1 for near-miss alerting this way. This generalizes nicely to "kid too close to the stove/stairs" zone logic for the kid-monitoring use case, but frame it as **zone-aware pose reasoning**, not "PPE detection" — the latter phrase alone will read as generic/overdone to judges who've seen it a hundred times.

Sources: [Construction-Hazard-Detection — GitHub](https://github.com/yihong1120/Construction-Hazard-Detection), [Frontiers: near-miss detection benchmarking YOLOv8-v12](https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2026.1827664/full), [ScienceDirect: floor-opening fall prevention via quadrilateral detection + pose](https://www.sciencedirect.com/science/article/abs/pii/S0926580524002723)

---

## 7. HackTX 2024 — "Angel's Protection" (UT Dallas team)

- **What it did:** Privacy-first person-locator that answers natural-language queries ("find the person in a red jacket with a backpack") using **YOLOv11 detection + a segmentation model that extracts clothing attributes (color, sleeve length) instead of running facial recognition**, stored in a searchable attribute database, with Llama 3.2 refining query matches. Built on Intel AI Developer Cloud.
- **Why it won:** Took 3 first-place category awards ("Best Use of Intel AI," "Best Use of GenAI w/ InterSystems IRIS Vector Search," "Best Ground-Up Model") — roughly $12.4k in prizes. Judges explicitly rewarded the **privacy-by-architecture decision** (no biometric identity, only appearance descriptors) as the differentiator over a "just run face-rec" baseline.
- **Direct lesson for QNet Home:** We already plan "publish only semantic events, no video" — Angel's Protection is proof that a **named, explicit non-biometric design choice** (we never do face ID; we describe scenes/skeletons, never identities) is a strong, judge-legible privacy story, and we should say it exactly that plainly in our pitch rather than leaving it implicit.

Source: [UT Dallas CS news — Angel's Protection at HackTX 2024](https://cs.utdallas.edu/33262/ut-dallas-team-triumphs-at-hacktx-2024-with-angels-protection)

---

## 8. tinyML Vision Challenge ("Eyes on Edge", Hackster) & Seeed 2023 tinyML Challenge

- **Eyes on Edge (tinyML Foundation, via Hackster):** contest specifically for low-power ML vision on microcontrollers; direct submissions page was inaccessible (403) but contest scope was person-detection / vision-on-a-budget style entries — same "Wake Vision" person-detection dataset lineage the Edge AI Foundation is still running "Challenge EDGE" contests on today.
- **Seeed 2023 tinyML Challenge:** 91 participants, 20+ countries, 14 teams, 44 submissions across weather-station / crop-disease / wildlife-monitoring problem statements — not safety-specific, but establishes that **judges in this tier reward extremely tight power/compute budgets** (microcontroller-class inference) as a first-class differentiator, something we can point to for the Arduino UNO Q side of our stack (Linux+MCU) if we push any inference down to the MCU tier, not just the Linux side.

Sources: [Eyes on Edge: tinyML Vision Challenge — Hackster](https://www.hackster.io/contests/tinyml-vision), [Highlights and Winners of the 2023 tinyML Challenge — Seeed](https://www.seeedstudio.com/blog/2023/12/01/highlights-and-winners-of-the-2023-tinyml-challenge/), [Challenge EDGE: Wake Vision Data Challenge — Edge AI Foundation](https://www.edgeaifoundation.org/posts/challenge-edge-wake-vision-data-challenge-now-open)

---

## 9. Qualcomm's own hackathon lineage (context for judging our exact event)

- **Windows on Snapdragon AI Hackathon (Devpost):** 1st place *AudioNova*, 2nd *Snapdragon AI: Multilingual Translator*, 3rd *Civil Dialog* — none of the top-3 were vision/safety projects; judging language explicitly cited "best use of Qualcomm AI Hub models" as a scored dimension, meaning **using Qualcomm AI Hub's pre-optimized/quantized model zoo for the target NPU is itself a judging signal**, not just a convenience — worth explicitly citing which AI Hub models (if any) we deploy on the Snapdragon X Elite NPU.
- **Snapdragon Multiverse Hackathon @ Princeton (Sept 2025):** structurally the same event lineage as ours — three tracks (Real-time CV Assistant, Conversational AI Companion, RL Agent Arena), Copilot+ PC as "control surface," teams bring their own Snapdragon devices/microcontrollers, GitHub submission with runnable executable required, judged on 4 unnamed categories plus a peer "Team's Choice" award. No public winner writeup was found (likely too recent/unlisted), but the **track structure confirms our "CV Assistant + Conversational Companion" combo is exactly the archetype this hackathon series rewards** — QNet Home already straddles both tracks by design.

Sources: [Windows on Snapdragon AI Hackathon — winners announcement](https://wos-ai.devpost.com/updates/34096-and-the-winners-are), [Snapdragon Multiverse Hackathon @ Princeton](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)

---

## 10. Event-based / privacy-preserving sensing research signal (not a hackathon, but a differentiator we can cite)

- Recent (2025-26) academic work on **event-based cameras for human detection/urban monitoring** (E-CHUM) and general "event-encoding for privacy-friendly always-on sensing" argues that encoding motion as sparse events *before* any frame-level representation is formed is a stronger privacy claim than "we don't upload the video" (which is still recoverable/inspectable on-device). We are not proposing event-camera hardware, but we can borrow the **vocabulary** — describe our edge nodes as emitting "sparse semantic events" analogous to event-camera output, reinforcing the privacy pitch with a technically literate framing that judges with CV backgrounds will recognize.

Source: [Event-Based Machine Vision for Edge AI Computing, Sensors 2026](https://doi.org/10.3390/s26030935), [E-CHUM: Event-based Cameras for Human Detection and Urban Monitoring](https://arxiv.org/pdf/2512.11076)

---

## What's overdone (avoid leading with these)

1. **Plain PPE/helmet/vest detection** — saturated across AI City Challenge Track 5, countless Devpost/student hackathons, and dozens of open-source repos. Fine as a minor feature, bad as a headline.
2. **Generic "fall detector on a Pi/Jetson with pose estimation"** — this exact combo (YOLOv8-pose + keypoint-band heuristic) is now a well-worn hackathon/community pattern (Hailo community project, multiple Hackster/Jetson entries). If we lead with "we detect falls," judges will have seen it. We must lead with the **agentic response + multi-device orchestration + voice/persona layer**, using fall detection only as the trigger example.
3. **Generic baby/child monitor (cry detection + camera)** — B-AIby Monitor and many commercial products already do this with no privacy architecture to speak of; a plain baby monitor reads as a solved, low-differentiation problem.
4. **Face-recognition-based person ID** — Angel's Protection's win explicitly rewarded *avoiding* this; using facial recognition would be both a privacy red flag and a differentiation loss versus a project judges already funded for NOT doing it.

## Where winners actually differentiated

- **Doing something with the detection**, not just detecting: GLaDOS (persona+voice), HailoGames (turned pose estimation into a live interactive game), Angel's Protection (natural-language query interface over privacy-safe attributes), AliOpenTrek's VLM narration (turns raw detections into a human-readable safety narrative — closest analog to our SLM/VLM event interpretation step).
- **Explicit, named privacy architecture** beats "we're privacy-conscious" as a slogan: HackTX judges rewarded the specific mechanism (clothing attributes, not face ID); we should equally name our mechanism ("semantic events only, zero video/audio frames leave the room node, skeleton keypoints discarded after inference").
- **Measured on-device performance numbers** are explicitly judged, not decorative: AI City Challenge's 2025 Jetson track scores FPS + accuracy harmonic mean; OpenCV's lineage rewarded on-device (no cloud round-trip) latency. We should report our own actual measured latency/FPS/NPU-utilization numbers for each stage of the pipeline (UNO Q pose inference → event publish → PC SLM/VLM reasoning → TTS response) rather than only architecture diagrams.
- **Reused pipeline across verticals**: the Jetson "escalator people tracker" team called out that their retail-tracking CV pipeline also applies to construction-site safety — a direct precedent for pitching QNet Home's *single reusable event-orchestration architecture* powering both elder-fall-response and kid-monitoring as one product line, not two demos bolted together.

---

## Top ideas for QNet Home from this domain (ranked)

1. **Name the privacy mechanism explicitly and specifically**, the way Angel's Protection did ("no facial recognition, no clothing-attribute database — we discard raw video/audio at the edge node after producing pose keypoints/audio-class events; only structured JSON events leave the room"). Say this in the first 30 seconds of the pitch, not as a footnote.
2. **Report real measured numbers** (fall-detection FPS on the UNO Q, end-to-end event→TTS-response latency, NPU utilization on the Copilot+ PC for the SLM/VLM) — AI City Challenge's Jetson track and the OpenCV Spatial AI lineage both show judges explicitly score this, and it directly hits the 40-pt Technical Implementation criterion.
3. **Don't lead with fall detection as the novelty** — it is the most-repeated demo in this entire research pull (Hailo community, Jetson forums, multiple hackathons). Lead with the **agentic, multi-device, voice-persona response loop**; use fall detection only as one illustrative trigger among several (loud sound, prolonged stillness, kid danger-zone entry).
4. **Steal the dual-condition false-positive heuristic** from the Hailo community fall-detection project (keypoint vertical-collapse AND bbox aspect-ratio flip) as a cheap, explainable, low-compute gate before escalating to the heavier SLM/VLM reasoning stage — cite it as a deliberate two-stage (cheap heuristic → expensive semantic reasoning) design for efficiency, which also strengthens the Technical Implementation score.
5. **Borrow the VLM-as-narrator pattern** from AI City Challenge Track 2's winning team (AliOpenTrek): explicitly demo the moment where the local SLM/VLM turns "pose collapse + no motion for 8s, kitchen node" into an actual spoken sentence — that translation step is what judges in the top adjacent competition literally awarded first place for.
6. **Turn the pose/event pipeline into a second, visibly "fun" demo mode** the way HailoGames did with Red-Light-Green-Light — e.g., a lightweight party-trick mode where the same skeleton pipeline judges a kid's "freeze!" game — costs almost nothing to add, but gives judges an interactive, memorable moment beyond the somber elder-care narrative and shows pipeline reuse live on stage.
7. **Frame the reusable architecture pitch using the "one pipeline, many verticals" line** used by the Jetson escalator-tracking team (retail tracking → construction safety) — say outright: "the same event-orchestration substrate that powers fall response also powers kid-safety and could power pet-monitoring or workplace safety tomorrow with zero architecture change, only new event types."
8. **Explicitly cite use of Qualcomm AI Hub models** on the Snapdragon NPU if we do — the Windows-on-Snapdragon hackathon's own judging criteria named "best use of Qualcomm AI Hub models" as a scored line item, so make sure whichever ASR/TTS/VLM/pose model we deploy is called out by name and tied to Hub/QNN, not left implicit.
9. **Avoid PPE/helmet detection and plain baby-monitor framing entirely** — both are the two most saturated tropes found across this research (AI City Track 5, Hailo community, countless Devpost entries); if either sneaks into a demo, relabel/reframe it (e.g., "danger-zone pose reasoning," not "PPE detection").
10. **Use event-camera-style vocabulary** ("sparse semantic events," not "we don't stream video") to signal CV literacy to judges who have seen actual event-camera privacy research — a small rhetorical upgrade over the more common "we anonymize the video" framing which sounds like an afterthought rather than an architectural choice.

---

## Sources

- [AI at the Edge Challenge — Hackster.io](https://www.hackster.io/contests/NVIDIA)
- [AI Innovation Challenge — Hackster.io](https://www.hackster.io/contests/SparkFun-NVIDIA-AI-Innovation-Challenge)
- [AI Innovation Challenge Roundup — SparkFun News](https://news.sparkfun.com/10569)
- [Hailo Hackathon 2025: Edge AI Innovative Ideas on Raspberry Pi](https://hailo.ai/blog/hailo-hackathon-2024-2025-pushing-the-limits-of-ai-innovation-on-raspberry-pi/)
- [B-AIby Monitor project README (Hailo community)](https://github.com/hailo-ai/hailo-CLIP/blob/main/community_projects/baiby_monitor/README.md)
- [HailoGames "Salted Fish" pose-estimation game (Hailo community)](https://github.com/hailo-ai/hailo-rpi5-examples/blob/main/community_projects/sailted_fish/README.md)
- [Pi-5+Hailo8L AI-powered Fall Identification & Recording project — Elektor Magazine](https://www.elektormagazine.com/labs/pi-5hailo8l-ai-powered-fall-identification-recording-project)
- [Announcing Winners & Cool Projects of Seeed Studio Vision Challenge](https://www.seeedstudio.com/blog/2024/07/15/vision-challenge-winners-and-projects/)
- [OpenCV AI Competition 2023 wrap-up — Voxel51 blog](https://voxel51.com/blog/opencv-ai-competition-2023)
- [OpenCV Spatial AI Competition — Phase 1 Winners (Kickstarter update)](https://www.kickstarter.com/projects/opencv/opencv-ai-kit/posts/2899951)
- [2024 AI City Challenge Winners — aicitychallenge.org](https://www.aicitychallenge.org/2024-challenge-winners/)
- [The 9th AI City Challenge (ICCV 2025 Workshop paper, incl. Jetson track)](https://openaccess.thecvf.com/content/ICCV2025W/AICity/papers/Tang_The_9th_AI_City_Challenge_ICCVW_2025_paper.pdf)
- [The 8th AI City Challenge (CVPR 2024 Workshop paper)](https://openaccess.thecvf.com/content/CVPR2024W/AICity/papers/Wang_The_8th_AI_City_Challenge_CVPRW_2024_paper.pdf)
- [Construction-Hazard-Detection — GitHub](https://github.com/yihong1120/Construction-Hazard-Detection)
- [Benchmarking YOLOv8-YOLOv12 for near-miss detection in construction safety — Frontiers 2026](https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2026.1827664/full)
- [Preventing falls from floor openings using quadrilateral detection and pose-estimation — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0926580524002723)
- [UT Dallas Team Triumphs at HackTX 2024 With Angel's Protection](https://cs.utdallas.edu/33262/ut-dallas-team-triumphs-at-hacktx-2024-with-angels-protection)
- [Eyes on Edge: tinyML Vision Challenge — Hackster.io](https://www.hackster.io/contests/tinyml-vision)
- [Highlights and Winners of the 2023 tinyML Challenge — Seeed Studio](https://www.seeedstudio.com/blog/2023/12/01/highlights-and-winners-of-the-2023-tinyml-challenge/)
- [Challenge EDGE: Wake Vision Data Challenge — Edge AI Foundation](https://www.edgeaifoundation.org/posts/challenge-edge-wake-vision-data-challenge-now-open)
- [Edge Impulse Hackathon 2025: And the Winners Are...](https://www.edgeimpulse.com/blog/edge-impulse-contest-2025-winners/)
- [Windows on Snapdragon AI Hackathon — winners announcement (Devpost)](https://wos-ai.devpost.com/updates/34096-and-the-winners-are)
- [Snapdragon Multiverse Hackathon @ Princeton — Qualcomm Developer](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Event-Based Machine Vision for Edge AI Computing — Sensors 2026](https://doi.org/10.3390/s26030935)
- [E-CHUM: Event-based Cameras for Human Detection and Urban Monitoring](https://arxiv.org/pdf/2512.11076)
