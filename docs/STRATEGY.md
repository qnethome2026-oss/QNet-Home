# QNet Home — Winning Strategy (Rubric-Driven)

*Draft v0.1 — 2026-08-03, before research results. Will be revised into SCOPE.md once the research fleet reports.*

## The one-sentence thesis
Judges reward **how systems work together**. Our scope must make the *orchestration* the hero — every device in the kit doing something only it can do, exchanging semantic events, with measurable on-device performance.

## Bucket 1: Technical Implementation — 40 pts (the game)
Criteria: resource utilization, optimization, latency & performance, energy efficiency.

What this means concretely:
- **Show the NPU doing the work.** LLM/STT on the X Elite Hexagon NPU (not CPU llama.cpp) if at all feasible. Live NPU-utilization graph during the demo.
- **Measure everything.** A built-in metrics panel: detection→speech latency (target: quote a number like "<3s end-to-end"), tokens/sec, per-stage timing, bandwidth used (bytes of semantic events vs. what a video stream would have been — a killer privacy+efficiency stat), watts if measurable.
- **Right model on the right silicon.** UNO Q: lightweight pose/audio models. X Elite: SLM reasoning + STT/TTS on NPU. Phone: on-device notification/live-connect (+ maybe a third sensing modality). AIC100: a legitimate cloud tier that doesn't break the privacy story. Use ALL FOUR kit devices meaningfully.
- **Degrade gracefully.** Demo: unplug the router → system still detects, still speaks, still alerts on LAN. Judges love resilience and it proves the on-device claim.

## Bucket 2: Use-Case & Innovation — 25 pts
- Fall detection alone is overdone (hypothesis; research will confirm). The novelty must be: (a) agentic multi-step response, not a trigger→alert pipe; (b) two-way voice conversation with the person on the floor; (c) semantic-events-not-video privacy architecture; (d) familiar-voice (parent voice clone) intervention; (e) plug-in scenario architecture (swap the sensing skill → new use case, live in the demo).
- UX matters here too: the caregiver phone experience and the in-room voice experience must feel humane, not alarm-system-like.

## Bucket 3: Deployment & Accessibility — 20 pts
Frequently thrown away by hackathon teams — 20 free points for discipline:
- **.EXE/.MSIX required** for the compute app. Decide packaging path EARLY (day 2, not day 5). If hub is Python/Node, pick a packager that works on ARM64 Windows and test it mid-week.
- One-command / installer-driven setup. UNO Q nodes flashable from a script or documented step-by-step with screenshots.
- A setup wizard in the hub app (discover nodes, name rooms, register caregiver phone, record consent-based voice sample) doubles as the Deployment story AND demo content.

## Bucket 4: Presentation & Docs — 15 pts
- README written for a stranger: description, team, from-scratch setup, run instructions, license, tests, references, commented code (all explicitly listed in the rubric).
- Demo script rehearsed: 1 live fall (mannequin/team member), 1 second-scenario, 1 resilience moment (router unplug), metrics panel visible throughout.
- Architecture diagram that makes the multi-device story legible in 5 seconds.

## Risk register (pre-research)
| Risk | Mitigation |
|---|---|
| OpenClaw doesn't run well on Windows-on-ARM | Fallback: lean custom agent loop (Python + local SLM tool-calling); research agent is evaluating |
| UNO Q too weak for real-time pose estimation | Fallback: lower FPS + motion-gated inference; or detection on-device + snapshot-to-hub VLM confirm |
| Voice cloning on-device too slow/painful on ARM64 | Fallback tiers: pre-generated phrase bank in cloned voice → cloud clone (ElevenLabs) → warm generic TTS |
| .EXE packaging on ARM64 fails late | Spike packaging by day 2 |
| Demo false positives / missed falls live | Rehearsed choreography + confidence thresholds tuned on our own bodies + a replay mode ("event injection") as backup |
| 4 days, 3-5 people | Scope must be cuttable in layers; define MUST/SHOULD/COULD in SCOPE.md |

## Open until research lands
- What won the external Snapdragon Multiverse (predecessor event) — pattern-match the judges.
- Exact model choices (QAI Hub catalog per device).
- OpenClaw go/no-go.
- Voice cloning primary/fallback.
- AIC100 role.
- Which second scenario (kids? or something less obvious) and which extra sensing modalities are cheap wins (loud-sound classification, "calling for help" keyword spotting, stove-left-on, wandering-at-night...).
