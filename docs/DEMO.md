# QNet Home — demo run of show (no-speech build)

*Ops runbooks: power-on + verification → [`operations/cold-start.md`](operations/cold-start.md) · symptom-indexed fixes → [`operations/troubleshooting.md`](operations/troubleshooting.md).*

*v1.0 — 2026-08-06. Voice-first: the kitchen node hears and speaks (Whisper on
the NPU + TTS, `apps/ventuno-q/qnet-voice-node/`) once Phase D3 of
`docs/voice-integration-plan.md` has passed its in-room gate. The dashboard's
flagged voice-sim composer remains the REHEARSED FALLBACK at every beat — same
wire messages, same routing — so a dead microphone can never kill a beat.
Numbers marked [M] are measured; there are no other numbers.*

---

## 0 · Standing topology (what is running where)

| Where | What | How it runs |
|---|---|---|
| IQ-9075 | Mosquitto broker (11883 tcp / 19001 ws) | systemd `mosquitto` |
| IQ-9075 | Gemma 4 E2B on the Hexagon NPU (GenieX, :18181) | systemd `geniex-serve` |
| IQ-9075 | **The agent** (skills on rails) | systemd `qnet-agent` |
| Ventuno Q | Fall detection on the Hexagon NPU (`node/vision.py`) | systemd `qnet-vision` (T7.1) |
| Ventuno Q | Qwen3-VL "look" service (`node/look.py` + VLM container :9001) | systemd `qnet-look` (T7.1) + Docker |
| Ventuno Q | Camera preview frame server (`node/stream.py`, :8090) | systemd `qnet-stream` (T7.1) |
| Ventuno Q (kitchen) | Voice: Whisper-small ASR on the NPU + TTS, wake-gated (`qnet-voice-node`) | Arduino App Lab app |
| Laptop | Dashboard (QNetHome.exe / MSIX) | Start menu / `dist\QNetHome\QNetHome.exe` |
| Phone | Telegram — trusted-contact messages from t.me/Qnethomebot | nothing to start |

All boards are services: power-cycling them brings everything back with no
keystrokes. The agent survives a dead/slow model by design (§6 rails) — this
was observed live: an LLM timeout mid-incident degraded one comfort sentence
and nothing else (`verify/E2E-no-speech.txt`).

## 1 · Pre-flight (5 minutes, before the audience)

```
[ ] IQ9 up:      ssh iq9  'systemctl is-active mosquitto geniex-serve qnet-agent'      → 3× active
[ ] Right broker: ssh iq9 'journalctl -u qnet-agent --no-pager | grep connected | tail -1'
                 → MUST say 127.0.0.1:11883 (1883 is the teammate stack — verify/INCIDENT-wrong-broker.txt)
[ ] Ventuno up:  ssh ventuno 'systemctl is-active qnet-vision qnet-look qnet-stream'   → 3× active
[ ] Dashboard:   launch QNetHome → ⚙ Settings → hub ws://<IQ9-ip>:19001/mqtt (persisted;
                 re-enter only if the corp DHCP moved the board)
[ ] Typed voice: ⚙ Settings → "Simulated voice input" ON → composer + red SIMULATED VOICE
                 badge appear in Live activity (this is the keyboard-for-microphone stand-in)
[ ] Camera view: ⚙ Settings → Rooms & devices → Kitchen camera preview address
                 http://<Ventuno-ip>:8090/kitchen.jpg → click the Kitchen on the map → LIVE
[ ] Phone:       Telegram open on the t.me/Qnethomebot chat, volume ON
[ ] Camera:      kitchen node camera aimed at the fall area; nothing blocking
[ ] Voice:       kitchen status heartbeat shows state idle (dashboard hover) and a spoken
                 "hey home" test query answers audibly; if not — composer fallback, demo goes on
[ ] Timers:      demo pace is set in the qnet-agent unit (see §5) — decide before starting
```

Fallback rule (from IMPLEMENTATION §3): if anything on a board misbehaves,
`dev/inject.py` and `dev/sim.html` carry the same beats from the laptop — the
injector understudy is always warm.

## 2 · Use case 1 — fall response (the centerpiece)

**Beat 0 — show the room seeing.** Click the Kitchen on the floor plan — the
LIVE local preview is the room's actual camera. Close the modal.

**Beat 1 — the fall.** A person falls in front of the kitchen camera (prop
mattress), or — fallback — play `clips/fall-02-cam0-rgb.mp4` to the camera /
run the vision service with the file source. On the dashboard: the Kitchen
tints, a session opens.
*Say to the audience: raw video never leaves this room over the fabric — the
wire carries one small JSON event. (The LIVE preview is a separate LAN-only
endpoint the household enables; say so if asked.)*

**Beat 2 — the house asks, out loud.** The room speaker says "I saw you fall.
Take a breath — are you okay?" (also in the dashboard feed). The person on the
floor answers BY VOICE from here on; the composer mirrors every step if audio
misbehaves.

**Beat 3 — silence escalates, and the phone rings with a question.** Nobody
answers. On the demo timer scale the escalation arrives in seconds: comfort
line + **the phone buzzes** — 🔴 "Possible fall — Tony, kitchen. Reply OK if
you can check on Tony — otherwise I'll call emergency services in 30 seconds."
Hold the phone up: *the house is asking a person before it calls a dispatcher.*

**Beat 4 — the contact answers (the new beat: run ONE of the two variants).**

- *Reply-OK variant:* reply `ok` on the phone → the house tells Tony out loud:
  "Good news — Sarah saw my message and is coming to check on you." The
  dashboard shows "Sarah replied: ok" and "Sarah is coming to help" — **and no
  911 call happens.** The phone gets the confirmation back — 🤝 "Got it — I'll
  hold off on emergency services. I'll still call in 3 minutes unless someone
  resolves this." Say the honest part aloud: if Sarah then never shows and
  nobody resolves, the (SIMULATED) call still fires after 3 minutes — an
  acked-then-silence never strands anyone. The reply is matched by the engine's
  rails, not the model.
- *No-reply variant:* ignore the phone → after the 30 s window: "You haven't
  answered, so I'm calling emergency services now." + **SIMULATED 911 line on
  the dashboard (red, marked SIMULATED)** + second buzz — 📞. The word
  SIMULATED is in every artifact on purpose; say so.
- (Judge-proof extra, works from either variant: replying `call 911` on the
  phone places the SIMULATED call immediately.)

**Beat 5 — the responder brief.** Walk in and SAY: "I'm the first responder,
can you tell me what happened?" (fallback: type it in the composer, room
kitchen) → the house answers ALOUD
with a grounded timeline (what it saw, when, what it did). One LLM call over
the session log — nothing pre-scripted.

**Beat 6 — close.** Type `false alarm` (or `a responder is here, thank you`) →
session closes, Kitchen turns green, third buzz — ✅, dashboard Summary card
recaps the incident with SIMULATED preserved.

**Interruption rehearsals (practice both — DESIGN §6):**
- Type `i'm fine` (composer, kitchen) at Beat 2 → the house does NOT cancel; it double-checks
  ("are you hurt anywhere?") — replies route through the pain check.
- Type `false alarm` at Beat 3 → instant cancel + ✅ message. Only explicit
  phrases cancel.

## 3 · Use case 2 — "where's my stuff"

Stage: glasses (or any distinct object) visibly placed in the kitchen camera's
view. Presenter is "in the bedroom" (composer room selector = bedroom).

1. SAY in the kitchen: "hey home, where are my glasses" (fallback: type it in
   the composer). The wake gate on the node strips the phrase; nothing else the
   room says is ever published — say that out loud, it is the privacy story.
2. Narrate while it thinks: every room's node is looking with its OWN camera
   and answering in text — the frame never leaves the node. [M] median 4.1 s
   look→answer round trip on the Ventuno (worst observed 5.4 s).
3. The answer comes back in the asking room: named location with a nearby
   anchor ("on the counter, next to the kettle") — and, with one node deployed,
   the house honestly says it couldn't check the bedroom.
4. Follow-up beat: type `i still don't see them` within 2 minutes → guide mode,
   positional guidance from the same room's camera. After 2 minutes the memory
   expires and the house asks what to look for — say that aloud if it happens.

## 4 · Reset between runs

```
[ ] Composer: type `false alarm` in any room with an open session (or dashboard takeover → Resolve)
[ ] Dashboard: verify all rooms quiet/green, Summary shows the recap
[ ] Sessions accumulate as files; no cleanup needed between runs
[ ] For a pristine feed: restart the dashboard app (feed re-reads live traffic only)
```

## 5 · Timer pacing (decide before the demo)

Real product timers are 30 s (check) / 30 s (escalate — the contact's reply
window) / 180 s (contact-engaged backstop) — honest but slow on stage. The
`qnet-agent` unit can carry `--timer-scale 0.3` (≈9 s / 9 s / 54 s). Note the
Telegram question says "30 seconds" and the confirmation says "3 minutes" —
those are the real product numbers; at demo scale the clock runs faster than
the message claims, which is exactly the "compressed pace" honesty line below:

```
ssh iq9 'sudo systemctl edit qnet-agent'   # override ExecStart with --timer-scale 0.3
```

If asked: say the real numbers and that the demo compresses time; never claim
the compressed pace is the product.

## 6 · If the model dies mid-demo

Nothing to do. The rails fire timers, Telegram, and the SIMULATED call without
the LLM; wording falls back to canned lines (observed live —
`verify/E2E-no-speech.txt`). The `--no-llm` G2 build (`scripts/demo_fallback.sh`)
remains the full fallback demo if the IQ9 itself is lost.

## 7 · What we say is real vs. not (honesty card)

- Real: NPU fall detection [M 34.8 ms/inf], NPU VLM lookups, on-device Gemma
  [M 15.7–16.2 tok/s], MQTT fabric, Telegram to a real phone **in both
  directions** (the question out, the contact's OK / "call 911" back — replies
  matched on engine rails, never by the model), engine rails.
- Simulated: the 911 call (marked SIMULATED in every artifact).
- Spoken live (kitchen): replies, wake queries, responder phrase — all
  wake-gated on the node. Typed composer = rehearsed fallback, clearly badged
  SIMULATED VOICE. Bedroom voice is a stretch goal.
- Unmeasured: fall-model accuracy (no published numbers; our clip table in
  `measurements.md` is the only evidence — quote it, nothing else).
