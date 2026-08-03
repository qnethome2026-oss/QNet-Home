# QNet Home — Idea Bank (out-of-the-box extensions & alternatives)

*2026-08-03. Sources: 16 research reports in `research/` + synthesis. Each idea tagged: **[wow]** demo impact, **[effort]** build cost in the 4-day window, **[src]** where it came from. The scope's MUST set is in `docs/SCOPE.md`; this file is the menu for what else the fabric can do — and the ammunition for the "it generalizes" slide.*

---

## A. The sleeper hit: "The home has a memory" (Ask-the-House)

Because every node publishes semantic events, the hub accumulates a **private, searchable timeline of home state** as a side effect of the architecture we're already building. Add embedding search (nomic-embed runs on the NPU at ~ms) over the event log and the resident or caregiver can *ask the house questions*:

- Elder: **"Where did I leave my glasses?"** (object last-seen memory via detection events), "Did I take my pills this morning?", "Did I lock the back door?"
- Caregiver: "How did Mom sleep?" → digest generated locally: "Up twice, kitchen at 2 AM, normal gait."
- Judges: this converts the event bus from plumbing into a *product* — and it's nearly free (the log already exists; RAG over it is a few hours).

**[wow: very high — nobody in the competitive scan has this][effort: 0.5–1 day][src: my synthesis; caregiver-burden metric from health-assistive.md]**
This is my #1 recommendation to add to scope. It's also the perfect answer to "isn't this just fall detection?" — no, it's an ambient semantic layer for the home; falls are one query against it.

## B. Prevention, not just detection (reframes the whole pitch)

1. **Night light-path**: presence event at night → hub lights the path to the bathroom via smart bulb. Falls *prevented*, not detected. Trivial (we already planned smart-light control) and it flips the narrative: "every fall we prevent is worth ten we respond to." **[wow: high][effort: hours][src: my synthesis; ONSCREEN ambient pattern]**
2. **Gait/routine drift analytics**: daily walking-speed and sit-to-stand trends from pose events → weekly local wellness digest; flags decline before the fall happens. SafelyYou/Sensi charge for this; ours is local. **[wow: med-high][effort: 0.5 day for a credible v1 chart][src: competitors-products.md]**
3. **Hazard sweep**: agent notices rug-corner/clutter/poor-lighting patterns in fall-risk zones and suggests fixes in the weekly digest. **[wow: med][effort: low if VLM-on-snapshot reused][src: my synthesis]**

## C. Cheap high-value sensing skills (each ~hours, reuses existing pipeline)

| Idea | Why it's good | Src |
|---|---|---|
| **Smoke/CO-alarm sound relay** | YamNet already classifies alarm sounds; home empty → phone alert. Classic, universally understood, zero new models | tech/qai-hub-models.md |
| **Glass-break + intrusion anomaly** | Shipping UNO Q brick; agent *speaks to the intruder* — routine-aware ("nobody expected home until 6") | arduino-uno-q.md |
| **Bathroom-safe audio-only node mode** | Mic-only profile (thud/help/water-running-forever): answers "where you'd never put a camera" with a *product mode*, not an excuse | my synthesis + mobile-role.md |
| **Appliance/leak listening** | Washer-done beeps, running-water-too-long, fridge-open chime; Sane.AI won an award on leak audio | edge-ai-qualcomm.md |
| **Keyword distress ("help, help")** | Shipping keyword_spotting brick as always-on gate | arduino-uno-q.md |
| **Hand-gesture "I'm OK" 👍** | Shipping brick; no-speech confirm for hard-of-hearing residents | arduino-uno-q.md |
| **Latchkey-kid mode** | Kid-arrived-home confirmation to parent; stranger-at-door escalation; quiet-hours/TV-time | seed idea + my synthesis |
| **Pet skills** | Dog-on-counter, pet distress while away — the "fun generalization" 10-second slide beat | my synthesis |

## D. Response & actuation ideas

1. **Nearest-helper routing**: alert says which room + who else is home + suggested route (SecureStep won with this addition). **[effort: low]**
2. **TV as the response surface** (ONSCREEN pattern): cast the "Are you OK?" card to the room's TV. **[effort: med — only if time]**
3. **ggwave acoustic handshake**: nodes exchange a chirp-encoded event when Wi-Fi is down — an audible, memorable offline-mesh beat (GibberLink won a global hackathon on this trick). **[wow: high theater][effort: 0.5 day][src: voice-multimodal.md]**
4. **Drill mode**: replay AIC100-generated synthetic scenarios as injected events — "fire drill for the AI" — doubles as our test harness demoed live. **[effort: free — it's the eval rig with a UI toggle]**

*(Dropped: elder talk button — team decision 2026-08-03.)*

## H. Interactive in-room showpieces — "ask it, and it reliably does something cool"

The trick for live-demo reliability: build the showpiece on the SAME person-tracking/occupancy core the safety features already need, so the cool moment exercises zero extra ML. Ranked:

1. **Follow-me voice (the architecture hero).** Start a conversation with the house in room A, walk to room B mid-sentence — the voice *hands off to room B's speaker* and continues, because occupancy tracking already knows where you are. One judge instruction: "keep talking to it and walk." Nothing demonstrates "multiple devices acting as one system" better, and it's just an audio-routing switch on top of the core pipeline. **[wow: killer][reliability: high — occupancy is the core pipeline][effort: ~0.5 day]**
2. **"House, close your eyes." (the trust hero.)** Voice command → node audibly confirms ("Privacy mode. Camera off in the kitchen."), LED goes red, the V4L2 stream provably stops (HUD shows the pipeline halted, packet monitor flatlines). "Open your eyes" resumes. An off-switch you can *talk to* — judges can command it themselves, it cannot fail (it's stopping a process, not running a model), and it converts the privacy claim into a physical, inspectable behavior. **[wow: high][reliability: near-perfect][effort: hours]**
3. **"House, where are my glasses?" (the memory hero, staged spatially.)** The answer comes *from the room where they were last seen* — the far node's speaker says "They're in here — on the kitchen counter" and pulses its light. Ask-the-House (§A) with a multi-room theatrical payoff. Stage-proof it by walking the glasses past that node during setup. **[wow: high][reliability: high if pre-staged][effort: rides on §A]**
4. **"House, find me." (hide-and-seek.)** Judge walks anywhere; the house announces in real time which room they're in ("Living room… now hallway… now kitchen"). Pure occupancy readout — the most failure-proof interactive beat available. Kid-mode variant: freeze-game/Simon-says using the same skeleton (HailoGames pattern). **[wow: med-high][reliability: near-perfect][effort: hours]**
5. **"House, count my squats." (the physical one.)** Judge does 5 squats; the room counts each rep aloud and scores form. Keypoint rep-counting is trivial and robust; ties directly to the elder mobility/gait story ("the same skill tracks Mom's sit-to-stand trend"). Judges doing something physical with the system is the most memorable 20 seconds you can buy. **[wow: high][reliability: high — rep counting is easy mode][effort: ~0.5 day]**
6. **"House, status report." (roll-call.)** Each room's node answers in sequence from its own speaker: "Kitchen — clear. Living room — one person, seated." The house audibly *is* a distributed system for 10 seconds. Reads current state only → cannot hallucinate, cannot fail. **[wow: med][reliability: perfect][effort: hours]**
7. **"House, remember this." (teach-by-showing — the boldest one.)** Hold an object up to a node: "these are Dad's keys — tell me if they're still here when I leave." CLIP embedding captured on the spot (21.5 ms on NPU per the QAI Hub report); later the house recognizes that specific object with no retraining. Live-teaching the home new semantics is genuinely novel; slightly riskier to demo than 1–6, so rehearse with high-contrast objects. **[wow: killer if it lands][reliability: medium][effort: ~1 day]**

## E. Alternative headline framings (same fabric, if we wanted to pivot)

1. **Care mesh across homes**: your hub subscribes to semantic events from a parent's house across town — video never leaves either home, only events cross the WAN. "The sandwich generation's dashboard." Strong story, adds WAN plumbing risk. **[pivot cost: +1 day]**
2. **Accessibility home for deaf/HoH**: every sound in the house becomes a visual/haptic event (doorbell, alarm, crying baby, name being called). Accessibility framing repeatedly wins both technical + impact awards. **[pivot cost: reframe only — the stack is identical]**
3. **Post-surgery recovery ("home step-down unit")**: discharge patients monitored for falls/immobility/med adherence for 2 weeks — insurance/hospital angle. **[pivot cost: framing only]**
4. **Independent-living facility mode**: multi-resident B2B — contrast with SafelyYou (they retain video; we never form it). **[pivot cost: framing only]**

## F. Demo-spectacle wildcards

- **Live "home nervous system" visualization** as the hub UI centerpiece: floor plan with events rippling through it, agent reasoning streamed alongside. Makes the invisible architecture visible — this IS the multi-device story on one screen. **[recommend: yes, this should be the main UI]**
- **Freeze-game / Simon-says fun mode** reusing the skeleton pipeline (HailoGames pattern) — 20 seconds of levity after the somber elder beat.
- **Judge-as-user moments**: judge types the hazard word ("scissors"), judge presses PTT, judge runs `qnet verify`. Every judge-touches-it moment is worth a slide.

## G. Explicitly rejected (and why)

- **Emotion recognition on video** — creepy + EU AI Act risk; prosody-on-voice during an active check-in is the defensible version.
- **Face recognition for identity** — biometric compliance burden; HackTX winner Angel's Protection won by *naming* its avoidance (clothing attributes). We do the same with track-IDs.
- **Wearables** — kit doesn't include one; and "ambient = works when the wearable is on the nightstand" is our talking point *against* Apple Watch.
- **Full smart-home control platform** (lights/thermostat/etc. as a feature checklist) — Home Assistant exists; we'd look like a worse HA instead of a new category.

---

## Recommendation: what actually enters the build

Adopt now (cheap, compounding): **Ask-the-House memory (A)**, **night light-path (B1)**, **smoke-alarm relay (C1)**, **nervous-system UI (F1)**, and from §H: **follow-me voice (H1)** + **"close your eyes" (H2)** as the interactive demo beats, with **"find me" (H4)** as the zero-risk warm-up.
Hold for the "generalizes" slide (build only if ahead): squat counter (H5), teach-by-showing (H7), bathroom audio-mode, latchkey mode, drill-mode UI, ggwave, freeze-game.
Framings to steal for the pitch regardless: prevention-not-detection, caregiver-burden reduction ("1 digest, not 40 alerts"), accessibility angle.
