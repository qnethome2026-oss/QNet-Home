# QNet Home — Project Brief (Seed Idea)

*Captured 2026-08-03 from team discussion. This is the raw seed — scope may change.*

## Hackathon context
- **Event:** Snapdragon Multiverse (Qualcomm internal hackathon), Aug 3–7, 2026. Submission due **Aug 7, 1:00 PM** via GitHub link + MS Form.
- **Hardware kit per team:** Copilot+ PC (Snapdragon X Series) as central hub, a mobile device, Arduino UNO Q, Qualcomm AI Cloud 100.
- **No tracks** — any use case, but focus is on *how systems work together*, multi-device AI orchestration.
- **Judging (100 pts):**
  - Technical Implementation — **40 pts** (resource utilization, optimization, latency/performance, energy efficiency)
  - Application Use-Case & Innovation — **25 pts** (problem solving, creativity/uniqueness, UX)
  - Deployment & Accessibility — **20 pts** (ease of installation and use)
  - Presentation & Documentation — **15 pts**
- **Submission requirements:** open-source GitHub repo, README (description, team, from-scratch setup, run instructions), OSS license, packaged **.EXE/.MSIX** for the compute app (and .APK if mobile app), must run on the Copilot+ PC as described, commercially-ready quality. Optional but recommended: tests, notes, references, well-commented code.

## Core concept
Privacy-first, multi-device AI system: distributed Snapdragon devices collaborate to **sense, reason, and respond entirely on-device**. Devices exchange **semantic events, not video streams**.

- **Edge nodes:** Arduino UNO Q (2 units) in different rooms with camera, mic, speaker, other sensors. Run GStreamer-based vision pipelines + lightweight models (pose estimation / fall detection, loud-sound detection, more TBD). Publish lightweight events (text, optionally snapshots/audio clips) — never stream video.
- **Hub:** Snapdragon X Elite Copilot+ PC running **OpenClaw** as the local AI orchestrator with a local SLM/VLM (QAI Hub models are a starting point; QUAD framework allows any GGUF model on Qualcomm devices).
- **Hub responsibilities:** interpret context from edge events, assess situation, decide course of action, generate reassuring guidance, on-device TTS out through room speaker, coordinate caregiver notification, call tools (emergency response, live connect with owner, flicker lights to attract attention, STT/TTS two-way conversation — "Are you OK?").

## Use case 1 — Elder fall detection & response
Elderly person living alone falls in the kitchen → nearby devices detect within seconds → local agent assesses → reassuring speech in the room → caregiver notified → no video ever leaves the home.

## Use case 2 — Kid monitoring
Falls, fighting, dangerous play (knives, electricity), scribbling on walls, TV-time enforcement. Twist: system can **mimic the parent's voice** (registered voice, prefer on-device cloning; open to cloud if needed) so intervention comes from a familiar voice, not a machine. Parents could text the system from a meeting and it speaks to the kid in their voice. Also for calming kids down.

## Possibly also
- App or website for managing devices, events, rules, caregivers.
- Team strength: professional Qualcomm multimedia / GStreamer pipeline experience — hackathon effort should go to multi-device orchestration + polished end-to-end experience.

## Positioning (the pitch)
The innovation is NOT the fall detector. It's a **reusable agentic multi-device AI architecture**: sensing, orchestration, and response distributed across heterogeneous Snapdragon devices. Swap the sensing component → new scenario, same architecture. Privacy (semantic events not video), low bandwidth, works with limited connectivity.

## Open questions
- Final scope: which scenarios make the demo? What's the wow factor?
- Voice cloning: on-device feasible? Which model? Consent/registration flow?
- Role of Qualcomm AI Cloud 100 and the mobile device in the architecture (judges want all devices meaningfully used).
- Which models on UNO Q vs X Elite NPU vs AIC100?
- Goal: **WIN** — uniqueness, non-obviousness, breadth of devices/frameworks used.
