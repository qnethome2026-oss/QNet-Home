# QNet Home — demo run of show (no-speech build)

*v0.9 — 2026-08-06. Written for the current state: everything real except audio.
Where a person would SPEAK to the house, the presenter TYPES into the room
simulator (`dev/sim.html`) — same wire messages, same routing, zero mocks
anywhere else. When the speech service lands (T3.1), the sim is replaced by a
microphone and this script does not otherwise change. Numbers marked [M] are
measured; there are no other numbers.*

---

## 0 · Standing topology (what is running where)

| Where | What | How it runs |
|---|---|---|
| IQ-9075 | Mosquitto broker (11883 tcp / 19001 ws) | systemd `mosquitto` |
| IQ-9075 | Gemma 4 E2B on the Hexagon NPU (GenieX, :18181) | systemd `geniex-serve` |
| IQ-9075 | **The agent** (skills on rails) | systemd `qnet-agent` |
| Ventuno Q | Fall detection on the Hexagon NPU (`node/vision.py`) | systemd `qnet-vision` (T7.1) |
| Ventuno Q | Qwen3-VL "look" service (`node/look.py` + VLM container :9001) | systemd `qnet-look` (T7.1) + Docker |
| Laptop | Dashboard (QNetHome.exe / MSIX) | Start menu / `dist\QNetHome\QNetHome.exe` |
| Phone | Telegram — trusted-contact messages from t.me/Qnethomebot | nothing to start |

All boards are services: power-cycling them brings everything back with no
keystrokes. The agent survives a dead/slow model by design (§6 rails) — this
was observed live: an LLM timeout mid-incident degraded one comfort sentence
and nothing else (`verify/E2E-no-speech.txt`).

## 1 · Pre-flight (5 minutes, before the audience)

```
[ ] IQ9 up:      ssh iq9  'systemctl is-active mosquitto geniex-serve qnet-agent'   → 3× active
[ ] Ventuno up:  ssh ventuno 'systemctl is-active qnet-vision qnet-look'            → 2× active
[ ] Dashboard:   launch QNetHome → ⚙ Settings → hub ws://<IQ9-ip>:19001/mqtt (persisted;
                 re-enter only if the corp DHCP moved the board)
[ ] Sim:         open dev/sim.html in a second browser window, same ws URL, pick a room
[ ] Phone:       Telegram open on the t.me/Qnethomebot chat, volume ON
[ ] Camera:      kitchen node camera aimed at the fall area; nothing blocking
[ ] Timers:      demo pace is set in the qnet-agent unit (see §5) — decide before starting
```

Fallback rule (from IMPLEMENTATION §3): if anything on a board misbehaves,
`dev/inject.py` carries the same beats from the laptop — the injector understudy
is always warm.

## 2 · Use case 1 — fall response (the centerpiece)

**Beat 1 — the fall.** A person falls in front of the kitchen camera (prop
mattress), or — fallback — play `clips/fall-02-cam0-rgb.mp4` to the camera /
run the vision service with the file source. On the dashboard: the Kitchen
tints, a session opens.
*Say to the audience: raw video never leaves this room — the wire carries one
small JSON event.*

**Beat 2 — the house asks.** Dashboard feed shows "I saw you fall. Take a
breath — are you okay?" (on the node this will be spoken aloud; today it is
text).

**Beat 3 — silence escalates.** Nobody answers. On the demo timer scale the
escalation arrives in seconds: comfort line + **the phone buzzes** — 🔴
"Possible fall — Margaret, kitchen." Hold the phone up.

**Beat 4 — the call.** Still no answer → "You haven't answered, so I'm calling
emergency services now." + **SIMULATED 911 line on the dashboard (red, marked
SIMULATED)** + second buzz — 📞. The word SIMULATED is in every artifact on
purpose; say so.

**Beat 5 — the responder brief.** In the sim (kitchen), type:
`i'm the first responder, can you tell me what happened?` → the house answers
with a grounded timeline (what it saw, when, what it did). One LLM call over
the session log — nothing pre-scripted.

**Beat 6 — close.** Type `false alarm` (or `a responder is here, thank you`) →
session closes, Kitchen turns green, third buzz — ✅, dashboard Summary card
recaps the incident with SIMULATED preserved.

**Interruption rehearsals (practice both — DESIGN §6):**
- Type `i'm fine` at Beat 2 → the house does NOT cancel; it double-checks
  ("are you hurt anywhere?") — replies route through the pain check.
- Type `false alarm` at Beat 3 → instant cancel + ✅ message. Only explicit
  phrases cancel.

## 3 · Use case 2 — "where's my stuff"

Stage: glasses (or any distinct object) visibly placed in the kitchen camera's
view. Presenter is "in the bedroom" (sim room = bedroom).

1. Type: `hey home, where are my glasses` (wake phrase typed today, spoken later).
2. Narrate while it thinks: every room's node is looking with its OWN camera
   and answering in text — the frame never leaves the node. [M] ~3.4 s warm
   per VLM look on the Ventuno.
3. The answer comes back in the asking room: named location with a nearby
   anchor ("on the counter, next to the kettle") — and, with one node deployed,
   the house honestly says it couldn't check the bedroom.
4. Follow-up beat: type `i still don't see them` within 2 minutes → guide mode,
   positional guidance from the same room's camera. After 2 minutes the memory
   expires and the house asks what to look for — say that aloud if it happens.

## 4 · Reset between runs

```
[ ] Sim: type `false alarm` in any room with an open session (or dashboard takeover → Resolve)
[ ] Dashboard: verify all rooms quiet/green, Summary shows the recap
[ ] Sessions accumulate as files; no cleanup needed between runs
[ ] For a pristine feed: restart the dashboard app (feed re-reads live traffic only)
```

## 5 · Timer pacing (decide before the demo)

Real product timers are 30 s (check) / 15 s (escalate) — honest but slow on
stage. The `qnet-agent` unit can carry `--timer-scale 0.3` (≈9 s / 4.5 s):

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
  [M 15.7–16.2 tok/s], MQTT fabric, Telegram to a real phone, engine rails.
- Simulated: the 911 call (marked SIMULATED in every artifact).
- Typed today, spoken when speech lands: the person's replies + wake phrase.
- Unmeasured: fall-model accuracy (no published numbers; our clip table in
  `measurements.md` is the only evidence — quote it, nothing else).
