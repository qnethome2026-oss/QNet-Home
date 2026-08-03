# Major Hackathon Winner Research — Home Safety / Elder Care / Multi-Device / Voice AI (Aug 2024 – Aug 2026)

Research pass for QNet Home (Snapdragon Multiverse Hackathon, Aug 3-7 2026). Goal: mine grand-prize/top winners from major collegiate + Devpost hackathons for themes, demo tricks, and pitch structures relevant to a multi-device home-safety AI, and flag overdone patterns to avoid.

---

## 0. CRITICAL FINDING: Qualcomm already runs a "Snapdragon Multiverse Hackathon" series — this is our own event's sibling/precedent

Before the university hackathons, the single most decision-relevant discovery: **Qualcomm has been running a recurring "Snapdragon Multiverse Hackathon" at multiple sites** (Princeton, MIT CSAIL, Bangalore, Jalandhar/Noida — May–July 2026 and Sept 2025), and a near-identical **"Qualcomm Multiverse" track** appeared inside **DiamondHacks 2026** (San Diego, ACM UCSD/MLH). This is effectively the template our own internal hackathon was cloned from, so its rubric language and winning pattern are the single best predictor of what "our" judges want.

- **DiamondHacks 2026 – Qualcomm Multiverse track** ($2,000 cash + Meta Quest 3 512GB): explicitly asks teams to use "AI PCs, mobile devices, cloud services, and microcontrollers" including **Arduino UNO Q and/or Rubik Pi**, and to "design applications that go beyond a single device—distributing perception, intelligence, and interaction across platforms powered by Snapdragon," emphasizing **privacy-first, low-latency, and energy-efficient** solutions. [devpost](https://diamondhacks-2026.devpost.com/)
- **Snapdragon Multiverse Hackathon — Princeton** (Sept 27-28, 2025): teams got a Copilot+ PC as "control surface" plus other Snapdragon devices/microcontrollers. Three tracks: **Real-time CV Assistant** (on-device CV: object tracking, anomaly detection, gesture recognition), **Conversational AI Companion** (voice/text AI for coaching/tutoring/storytelling), **RL Agent Arena**. Judging gave a **Top Award** (judges, 4 evaluation categories) and a separate **Team's Choice Award** (peer vote). [qualcomm.com](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- **Snapdragon Multiverse Hackathon — Noida** (Qualcomm India campus, 2026): winning team **"Ghost Map"** (Deepesh Kakkar, Thapar University + 4 teammates) built **"Dragverse"** — phone captures a 3D scan of a real environment → digital twin simulation → trains a robot-control policy via RL in-sim → deploys the trained model to a **physical robot**. Prize: Snapdragon X2 Elite Copilot+ PCs each + Qualcomm DevRel support + featured blog/livestream. [Tribune India](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- Bangalore edition ran July 11-12, 2026 at the Qualcomm Bengaluru campus (same "distributed cross-device AI application network" framing); no public winner writeup found.

**Why this matters for us:** the winning "Dragverse" pattern is exactly "capture on one device → heavy compute on another → act in the physical world on a third," narrated as a literal live pipeline. That is precisely QNet Home's architecture (Arduino UNO Q edge sensing → Copilot+ PC agent reasoning → speaker/lights/notification action). We should make the **cross-device handoff itself the visual centerpiece of the demo** — e.g., point at the Arduino node, then cut to the PC lighting up and speaking, then cut to a phone notification — because that is verifiably what this judging culture rewards.

---

## 1. TreeHacks (Stanford) — 2024 & 2025

**TreeHacks 2025 Grand Prize ($11,000): HawkWatch.** [Devpost](https://devpost.com/software/hawkwatch) · [YouTube](https://www.youtube.com/watch?v=h2G_Z_NtcXk) · [Stanford Daily](https://stanforddaily.com/2025/02/18/treehacks-awards-200000-in-prizes-to-students-from-around-the-world/)
- What it did: turns any camera into a smart security system. Sends audio, video, and TensorFlow.js body-pose data to **Google Gemini VLM** for real-time multimodal threat detection (assault, shoplifting, medical emergencies like fainting/choking); emails/phones alerts to security staff; dashboard shows multiple live streams plus a chat "assistant bot" that answers "what should I do in this situation?" using the live event context.
- Stack: Next.js/TS/Tailwind, Supabase, Gemini VLM, TensorFlow.js pose, Resend (notifications), WebSockets, OpenAI for the assistant bot.
- Why it won: built a *fully functional* multi-modal (audio+video+pose) surveillance pipeline in 36 hours with a genuinely usable human-in-the-loop dashboard — technical completeness + an actionable "now what do I do" layer, not just detection.
- **Ideas for QNet Home:** (1) An in-agent chat/assistant surface that lets a caregiver ask "what happened / what should I do" using the same event context the agent already has — this is nearly a freebie on top of our OpenClaw agent and demonstrably wins judges. (2) Multimodal fusion (sound + pose) is what separated HawkWatch from generic camera demos — we already do this, emphasize it. (3) **Overdone warning:** "camera + VLM + alert" security-monitoring demos are common (see also PennApps' Watchful.AI below) — we must lead with "no video ever leaves the edge device, only semantic events" as the explicit differentiator, since HawkWatch (and most competitors) stream raw video/frames to a cloud VLM, which is exactly the privacy weakness we avoid.

**TreeHacks 2024 Moonshot Grand Prize ($10,000 + Japan trip): Team Baymax.** [Stanford Daily](https://stanforddaily.com/2024/02/27/treehacks-2024/)
- A mobility-assistance project for people with mobility limitations (accessibility/assistive-tech framing won the top "moonshot" award, not a security/monitoring pitch).
- **Idea:** Judges at TreeHacks have twice rewarded assistive/dignity-preserving tech for a vulnerable population over pure surveillance-security tech — reinforces leaning into the "dignity and reassurance" framing (a voice that says "are you okay?" rather than a camera that just alerts) rather than a pure detection/monitoring pitch.

## 2. HackMIT — 2024 & 2025

**HackMIT 2025 Founders Lab Grand Prize: Yeigo** — an AR mobility aid for people who use walkers, giving real-time guidance on height/posture adjustments. [LinkedIn/RealityHack ecosystem](https://www.realityhackatmit.com/2025-founderslab)
- Continues the "assistive tech for mobility-limited users" pattern seen at TreeHacks 2024's Baymax — a second data point that accessibility-for-aging/mobility-impaired users is a proven grand-prize category, independent of pure security framing.
- Also in the HackMIT 2025 gallery (not confirmed as a track winner): **BAImax**, "personal AI health assistant to make elderly care more accessible and effective" — shows elder-care AI companions are an increasingly common submission category, i.e. we should expect other teams at *our* hackathon to attempt something similar; we need a sharper wedge than "AI + elderly."

## 3. Cal Hacks (UC Berkeley) — 11.0 (2024) & 12.0 (2025)

**Cal Hacks 12.0 Grand Prize (1st/695 projects): FaceTimeOS.** [Dylan Lu's writeup](https://blog.dylanlu.com/cal-hacks-12/) · GitHub `ThePickleGawd/FaceTimeOS`
- What it did: lets you **FaceTime call your own Mac** and give it voice commands; a computer-use agent (built on Simular's **Agent S**) executes tasks (find files, debug code) while you watch/talk through the call. Speech via Fetch.ai + Fish Audio; UI via an open-source Cluely-style overlay.
- **Demo trick (very relevant):** the author explicitly says he *removed click functionality entirely* before the demo and forced the agent to keyboard-only actions, purely to make the live demo bulletproof — "judges primarily evaluate what they see," so he optimized visual polish and reliability over technical completeness.
- Why it won: reused an existing capability (computer-use agents aren't new) but wrapped it in a **familiar consumer interface** (a normal FaceTime call) as the interaction surface — novelty came from the vehicle, not the underlying tech.
- **Ideas for QNet Home:** (1) This is the closest precedent to our "parent texts the system from a meeting and it speaks in their cloned voice" trick — a familiar communication channel (phone call/text) becoming the trigger for an agent acting in the physical world is a proven grand-prize-winning demo pattern. We should stage this exact moment live for judges: a teammate texts from their phone mid-pitch, and the room speaker immediately responds in their cloned voice. (2) Deliberately hard-code a narrow, reliable path for the live demo (e.g., pre-agreed phrases/scenario) rather than trying to prove full robustness on stage — reduces demo-day risk without lying about capability, since the underlying system genuinely works.

**Cal Hacks 11.0 Grand Prize (2024): Duet.** [Stanford Daily](https://stanforddaily.com/2024/11/20/stanford-students-win-cal-hacks/)
- EEG headset (Emotiv) → classifies emotional/brain state → ML generates adaptive music that shifts with the wearer's emotional state in real time.
- **Idea:** judges rewarded turning a raw biosignal into a legible *emotional* narrative in real time. QNet Home's pipeline (pose/audio event → agent interprets *emotional/situational state* → reassuring voice response) follows the same "sensor → felt meaning → adaptive output" arc; make the emotional interpretation step visible/legible to judges (e.g., show the agent's reasoning trace: "detected: fall + prolonged stillness + no response → escalating tone").

## 4. LA Hacks 2025

**2nd place: Lumos.** [Devpost](https://devpost.com/software/lumos-f8h0mn)
- AI-powered smart glasses (Snap Spectacles) for **Alzheimer's patients**: on-device face recognition overlays names/relationships as subtle AR cues; autonomous agents (Fetch.ai, Dain, Gemini 2.5) handle contextual reminders and safety monitoring; daily journaling prompts.
- **Idea + overdone warning:** This is the second data point (with MHacks below) that "AI/AR glasses for dementia/memory-recall" is becoming a recognizable subgenre at hackathons — if we ever considered a wearable angle for elder care, avoid it; our **ambient, ceiling/room-mounted edge-node** approach (no wearable required, nothing to forget to put on, works even during a fall when a wearable might be knocked off or the person can't operate it) is a genuine differentiator worth stating explicitly against this pattern.

## 5. Hack the North (Waterloo) 2024

**Winning project (hardware/domain track): SecureStep.** [Mappedin blog](https://www.mappedin.com/resources/blog/hack-the-north-2024/) · related `devpost.com/software/smartcane`
- A smart walking cane for seniors in care homes: ESP8266 + MPU6050 accelerometer/gyro detects falls, publishes the wearer's exact indoor geolocation onto a facility floor plan via the **Mappedin SDK**, and routes caregivers to the fastest indoor path to the person.
- **Idea:** fall *detection* alone is now table-stakes/overdone (see also HawkWatch's "medical emergency" detection, TreeHacks' Baymax, and the general "fall detection" genre across nearly every hardware hackathon). SecureStep won specifically because it added **actionable indoor routing for the responder**, not just an alert. QNet Home should consider a lightweight equivalent — e.g., the agent's caregiver notification includes which room/edge-node triggered the event and a suggested fastest path/room label — cheap to add, and it's a proven differentiator from a plain "fall detected!" push notification.

## 6. PennApps XXV (2024, UPenn)

- **Watchful.AI**: "AI agent providing 24/7 student protection against school shootings" — a continuous on-device monitoring agent framed explicitly as *protection*, not surveillance. [PennApps XXV gallery]
- No project in the visible gallery directly matched elder-care/fall-detection/voice-companion themes as strongly as other schools' events that year — PennApps XXV's healthtech/safety representation was thin, suggesting home-safety/elder-care is *not* saturated at every hackathon, just at the ones that explicitly lean healthtech (TreeHacks, HackMIT, LA Hacks, DeltaHacks).
- **Idea:** the "24/7 AI agent, framed as protector not spy" language pattern (used for school safety) is directly reusable copy for our elder/kid-monitoring pitch — lean on "protector," "companion," "guardian" framing over "surveillance/monitoring" framing in our own pitch script, since judges respond well to the protective framing and it also defuses the privacy-creepiness objection before it's raised.

## 7. DeltaHacks XI (McMaster, Jan 2025)

- **Pickle – Emergency Response**: an **offline-capable** disaster-safety communication platform that works "amidst disaster ... without ... internet connection." [DeltaHacks XI gallery]
- **FitBud**: wearable-band rehab tracking with real-time movement feedback synced across multiple devices.
- **Idea:** Pickle's core pitch hook — resilience with **no dependency on internet/cloud** during the exact moment it matters most (a disaster/emergency) — is a strong echo of QNet Home's "privacy-first, on-device, semantic-events-only" architecture. We should explicitly claim the same resilience benefit: our system keeps working for detection + local TTS/voice response even if home internet or cloud connectivity drops, because the fall-detection/pose pipeline and local SLM/VLM run on-device; only optional caregiver notification needs connectivity. This is a legitimate, judge-relevant "why does distributing across devices matter, not just where compute happens" argument for the 40-pt technical category.

## 8. HackHarvard 2024 & 2025

- **HackHarvard 2024 "Overall Best Hack": Sustain-ify** (Amrita Vishwa Vidyapeetham team) — AI app guiding sustainable living/waste-repurposing/eco shopping; first Indian-university team to win the all-track grand prize since 2015. [Amrita press release](https://www.amrita.edu/news/amrita-students-win-grand-prize-in-a-world-renowned-hackathon-at-harvard/)
- Not thematically relevant to home safety, but notable as a reminder that **overall grand prizes often go to a clean, well-scoped single-pitch app** rather than the most technically ambitious project — reinforces that presentation clarity (15 pts in our rubric) and a crisp single-sentence pitch matter as much as raw technical scope.
- HackHarvard 2025 ("Compile the Decade," Oct 3-5, 2025) winner list not found in this pass (results not indexed at research time); no blocker to our conclusions.

## 9. MHacks 2025 (Michigan) & general devpost sweep

- Multiple projects in the MHacks 2025 gallery target **dementia/Alzheimer's name-recall via Snap Spectacles/AR**, plus a **Medicare Connect** app (appointment simplification, medical-report interpretation, medication reminders) — confirms elder-tech-via-wearable-AR is now a repeated pattern across at least 3 different hackathons in this research window (LA Hacks, MHacks, and Snap's own hackathon showcase program). **Overdone: avoid AR/wearable-glasses elder tech**; QNet Home's ambient/no-wearable angle is a clean point of contrast to state explicitly in the pitch.
- **VoiceCare** (submitted to an "AI Partner Catalyst" hackathon; win status unconfirmed): voice-first AI companion for elderly living independently — proactively calls for medication reminders/companionship, analyzes speech for distress, SMS-alerts family. Stack: Flutter, **Gemini 2.0 (Vertex AI)**, **ElevenLabs** (TTS/STT), Flask, **Twilio** SMS, Firebase. [Devpost](https://devpost.com/software/voicecare-hvlta9)
  - **Idea:** this is close to the *response* half of QNet Home already — validates the tool-calling pattern (LLM decides → SMS/call family → TTS conversation) as a proven, judge-legible architecture. But VoiceCare is a **phone-app-only** concept with no distributed sensing; our differentiation is that detection happens on a separate physical edge device with zero video ever leaving it, and the PC-hosted agent is the one orchestrating across devices — make sure the pitch draws this contrast directly ("apps like this exist, but they can't see a fall happen — they wait for you to already be able to press a button or speak").

---

## Cross-cutting "overdone, avoid or must differentiate" list

| Pattern | Seen in | How to avoid looking generic |
|---|---|---|
| Camera + cloud VLM → alert (raw video/frames sent off-device) | HawkWatch (TreeHacks '25), many generic "smart security camera" Devpost entries | State explicitly: **no video/audio ever leaves the edge node** — only semantic JSON events cross the network. Quantify the bytes/sec of an event (~KB) vs. a video stream (~Mbps) as a concrete technical-slide number. |
| Fall detection alone (wearable cane/tag/app), generic "fall detected!" alert | SecureStep (Hack the North '24), TreeHacks' Baymax, countless health-hackathon entries | Add actionable context (which room/node, situational reasoning, a live two-way voice check before escalating) — SecureStep won specifically by adding indoor routing, not raw detection. |
| AR/wearable glasses for dementia/memory-recall | Lumos (LA Hacks '25), multiple MHacks '25 projects, Snap hackathon showcase | Emphasize QNet Home requires **nothing worn** — works during exactly the moment (a fall) when a wearable might be knocked loose or the person can't operate a device. |
| Phone-app AI companion + SMS alert for elderly (single device, no real-world sensing) | VoiceCare | Contrast: apps wait for the user to act; QNet Home senses the event autonomously via distributed edge nodes. |
| Computer-use agent triggered by a normal phone call/text (novel *interface*, not novel *tech*) | FaceTimeOS (Cal Hacks 12.0 grand prize) | Not overdone for us — but borrow the **demo trick**, not avoid it: reuse a familiar channel (text message) as the on-stage trigger for the cloned-voice intervention. |

## Notable pattern NOT found anywhere in this research: voice-cloning of a trusted family member for intervention

Across TreeHacks, HackMIT, Cal Hacks, LA Hacks, Hack the North, PennApps, DeltaHacks, HackHarvard, and MHacks (Aug 2024–Aug 2026), **no winning or gallery project found used consent-registered voice cloning of a parent/caregiver as the intervention voice.** This is a genuine white-space differentiator for the kid-monitoring use case. The one risk: voice cloning is a widely-publicized **vishing/scam-call vector** (fake "grandchild in trouble" calls, etc.), so judges may reflexively raise the deepfake-trust concern. Because no competitor project in this research addresses that concern, being the team that **proactively names it and shows the consent/registration/local-storage safeguard on a slide** is a low-cost way to convert a potential objection into a point of Innovation-category credibility ("we thought about the misuse case explicitly").

---

## Ranked "Top ideas for QNet Home" from this domain research

1. **Make the cross-device handoff the visual centerpiece of the live demo**, not an implementation detail — Qualcomm's own "Snapdragon Multiverse Hackathon" series' winning project (Dragverse, phone→PC-sim→physical robot) suggests judges in this exact program reward *visibly* watching a pipeline cross device boundaries. Stage the demo as: point at Arduino UNO Q node → cut to PC lighting up + agent speaking → cut to phone notification, narrated live.
2. **Borrow FaceTimeOS's demo trick for our "parent's cloned voice" feature**: have a teammate actually text/call in from their phone mid-pitch and have the room speaker respond instantly in their cloned voice. A familiar-channel trigger for an agent action was literally the Cal Hacks 12.0 grand-prize-winning demo mechanic — and pre-script/pre-narrow this exact path for on-stage reliability (per Dylan Lu's explicit "removed click functionality" reliability trick).
3. **Lead the pitch with "no video/audio ever leaves the edge device — only semantic events"** as the headline technical/privacy differentiator against the dominant "camera + cloud VLM" pattern (HawkWatch and the broader genre). Put a concrete number on it (event payload size vs. equivalent video bitrate) to hit the Technical Implementation rubric's "measured numbers matter."
4. **Explicitly disclaim the AR/wearable elder-tech genre** (Lumos, MHacks Snap-Spectacles projects) by stating QNet Home requires nothing worn — differentiates from a now-recognizable subgenre and directly answers "why not just a wearable?"
5. **Add lightweight caregiver-routing context** (which room/node triggered, suggested nearest-person path) the way SecureStep's Mappedin integration did — cheap addition, proven differentiator from generic "fall detected" alerts.
6. **Preempt the voice-clone-scam objection on a slide**: state the consent-registration + local-only storage of the voice model explicitly. No competitor project found addresses this, so naming it first is a credibility/innovation point, not just a defensive move.
7. **Surface the agent's reasoning trace live** (à la HawkWatch's contextual assistant bot and Duet's biosignal→emotion narrative) — show judges the OpenClaw agent's interpretation ("detected: fall + 12s stillness + no verbal response → escalating") rather than a black-box alert; judges have rewarded this "explainable decision" layer twice in this research (HawkWatch, Duet).
8. **Claim offline/degraded-network resilience** as a technical strength, echoing DeltaHacks' Pickle: because detection + local TTS/voice conversation run on-device, the core safety loop keeps working even if home internet drops — only the optional caregiver SMS/cloud escalation needs connectivity. This is a legitimate answer to "why distribute intelligence across devices instead of just using the cloud."
9. **Keep the pitch script crisp and single-sentence** (HackHarvard 2024's Sustain-ify won "Overall Best Hack" on a clean, well-scoped pitch, not the most technically sprawling project) — don't let two use-cases (elder fall + kid monitoring) dilute the one-line hook; pick one as primary and the other as "and it generalizes to..." in ~10 seconds.

---

## Sources

- [HawkWatch — Devpost](https://devpost.com/software/hawkwatch)
- [HawkWatch demo — YouTube](https://www.youtube.com/watch?v=h2G_Z_NtcXk)
- [TreeHacks 2025 — Stanford Daily, $200k awarded](https://stanforddaily.com/2025/02/18/treehacks-awards-200000-in-prizes-to-students-from-around-the-world/)
- [TreeHacks 2024 — Stanford Daily, "Innovation and empathy win"](https://stanforddaily.com/2024/02/27/treehacks-2024/)
- [TreeHacks 2025 project gallery](https://treehacks-2025.devpost.com/project-gallery)
- [Samarth Shiramshetty / TreeHacks 2025 coverage](https://americansouthasiannetwork.com/south-asian-spotlight/samarth-shiramshetty-wins-grand-prize-at-standford-treehacks-2025/)
- [HackMIT 2025 Founders Lab — Yeigo winner](https://www.realityhackatmit.com/2025-founderslab)
- [HackMIT 2025 project gallery (Plume)](https://plume.hackmit.org/gallery?hackathon_id=hack-2025&page=1)
- [Cal Hacks 12.0 — FaceTimeOS writeup, Dylan Lu's Dev Blog](https://blog.dylanlu.com/cal-hacks-12/)
- [Cal Hacks 12.0 — Devpost](https://cal-hacks-12-0.devpost.com/)
- [Cal Hacks 11.0 — Duet, Stanford Daily](https://stanforddaily.com/2024/11/20/stanford-students-win-cal-hacks/)
- [Lumos — Devpost](https://devpost.com/software/lumos-f8h0mn)
- [LA Hacks 2025 project gallery](https://la-hacks-2025.devpost.com/project-gallery)
- [Hack the North 2024 — SecureStep, Mappedin blog](https://www.mappedin.com/resources/blog/hack-the-north-2024/)
- [SmartCane — Devpost](https://devpost.com/software/smartcane)
- [PennApps XXV project gallery](https://pennapps-xxv.devpost.com/project-gallery)
- [DeltaHacks XI project gallery](https://deltahacks-xi.devpost.com/project-gallery)
- [HackHarvard 2024 — Amrita Vishwa Vidyapeetham press release, Sustain-ify](https://www.amrita.edu/news/amrita-students-win-grand-prize-in-a-world-renowned-hackathon-at-harvard/)
- [HackHarvard 2024 — Devpost](https://hackharvard-2024.devpost.com/)
- [MHacks 2025 project gallery](https://mhacks-2025.devpost.com/project-gallery)
- [VoiceCare — Devpost](https://devpost.com/software/voicecare-hvlta9)
- [DiamondHacks 2026 — Devpost (Qualcomm Multiverse track)](https://diamondhacks-2026.devpost.com/)
- [Snapdragon Multiverse Hackathon — Princeton, Qualcomm](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon — Bangalore, Qualcomm](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)
- [Snapdragon Multiverse Hackathon — MIT CSAIL listing](https://www.csail.mit.edu/event/snapdragon-multiverse-hackathon)
- [Team Ghost Map / Dragverse — Tribune India](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [Qualcomm India opens registrations for Snapdragon Multiverse Hackathon — Bharat Mirror](https://english.bharatmirror.com/qualcomm-india-opens-registrations-for-snapdragon-multiverse-hackathon-to-build-multi-device-ai-solutions/)
