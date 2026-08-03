# QNet Home — Progress Tracker

## Status: PHASE 0 COMPLETE — Scope proposed, awaiting team review (2026-08-03)

## Plan
1. [x] Read judging criteria (`judging/`) — summarized in `docs/BRIEF.md`
2. [x] Research fleet DONE: 16/16 agents, ~60 hackathons + 8 tech deep dives → full reports in `research/` (1.8M tokens of research, several claims verified live on this machine)
3. [x] Synthesized into `docs/SCOPE.md` v1.0 — pitch, per-device architecture, MUST/SHOULD/COULD/WON'T, demo script, day-by-day plan, rubric self-check
4. [ ] Team review → lock scope (TODAY — build days are scarce)
5. [ ] Day-1 actions (see SCOPE.md §7): kit phone getprop, AIC100 endpoint email to organizers, UNO Q bring-up, GenieX spike, Chatterbox Nano RTF measurement, MSIX hello-world spike

## Research fleet layout
Each agent writes a full report to a file and returns a summary.

### Hackathon sweep → `research/hackathons/`
- `edge-ai-qualcomm.md` — Qualcomm/Snapdragon/edge-AI hackathons & winners
- `health-assistive.md` — healthcare/eldercare/accessibility hackathons
- `smart-home-iot.md` — smart home / IoT hackathons
- `agentic-llm.md` — agentic AI / LLM-orchestration hackathons
- `vision-safety.md` — computer vision / safety monitoring hackathons
- `embedded-tinyml.md` — Arduino / tinyML / embedded contests
- `university-major.md` — major university hackathon winners (relevant themes)
- `voice-multimodal.md` — voice AI / multimodal / multi-device hackathons

### Tech deep dives → `research/tech/`
- `qai-hub-models.md` — QAI Hub model catalog mapped to our use cases
- `arduino-uno-q.md` — UNO Q capabilities, App Lab, GStreamer, model deployment
- `openclaw.md` — OpenClaw architecture, skills, local models, Windows-on-ARM
- `x-elite-inference.md` — local LLM/STT/TTS on Snapdragon X, NPU stack, power/latency measurement
- `voice-cloning-tts.md` — on-device voice cloning feasibility
- `aic100-cloud.md` — Qualcomm AI Cloud 100 role
- `mobile-role.md` — Android device role, caregiver app, on-device AI on phone
- `competitors-products.md` — existing products/prior art (fall detection, privacy-first home AI, Frigate/Home Assistant)
- `offline-skill-packs.md` — measured size of authoritative first-aid corpus (2.5 MB text / 1,011 pages); offline knowledge-skill technique + which other domains qualify (added 2026-08-03, post-fleet)

## Decisions log
- 2026-08-03: Project seed captured in `docs/BRIEF.md`. Research fleet launched.
- 2026-08-03: Research complete (16/16 agents) → `docs/SCOPE.md` v1.0.
- 2026-08-03 (team): **Voice cloning = opt-in, child scenario only.** Elder/system flows always use the neutral warm voice. Engine = ElevenLabs standard cloning (cloud OK), with locally cached phrase bank for offline/instant playback; local Chatterbox demoted to stretch. SCOPE.md updated.
- 2026-08-03: `docs/IDEAS.md` created — out-of-the-box idea bank; top adds proposed: Ask-the-House memory, night light-path, smoke-alarm relay, nervous-system UI. Talk button rejected (team). §H interactive showpieces added.
- 2026-08-03 (team feedback): showpieces must connect to the crux (privacy/fabric/agentic response), not be party tricks. Second research fleet launched → `research/wow/` (5 agents: full AI Hub catalog, GGUF exotica, viral demos, maker builds, phone exotica). Next: synthesize crux-connected wow beats into IDEAS.md/SCOPE.md.
- 2026-08-03: **Offline emergency knowledge pack** — verified the "emergency knowledge is tiny" hypothesis by downloading + measuring the authoritative corpus (IFRC 2020, AHA 2020, WTIND: 2.5 MB text total). Shipped `skills/emergency/` (6 skills, 16.4 KB, OpenClaw-SKILL.md-compatible) + `research/tech/offline-skill-packs.md`. Added as SHOULD row in SCOPE §4. **Pending: human review of skill content against cited sources before demo (Day-4 checklist).**

## Key dates
- Aug 7, 1:00 PM — GitHub repo submission deadline (MS Form)
