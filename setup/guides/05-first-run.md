# Guide 5 — First run of the whole house

**What you're doing:** confirming every device from Guides 1–4 works as one
system, then exercising both capabilities for real.

**You need:** hub up (Guide 2), at least one room node up (Guide 3), the
laptop on the same LAN. Edit the three IPs at the top of
`scripts/health_check.sh` (or export `QNET_IQ9`, `QNET_KITCHEN`,
`QNET_BEDROOM`) to match your boards.

---

## Step 1 — The one-command check

From the repo on the laptop:

```bash
bash scripts/health_check.sh
```

Not green, or the boards were just powered on / reconfigured? One command
(re)starts every service on every device, waits out the slow model loads,
and re-runs this check — IPs are arguments (or edit the top of the script):

```bash
bash scripts/bring_up.sh <HUB-IP> <KITCHEN-IP> <BEDROOM-IP>
```

Its companion doc, [`scripts/bring_up.md`](../../scripts/bring_up.md),
explains every stage and diagnostic — including the two rules for USB
replugging (cameras need no config; audio `usb:N` must be re-checked).

Expected final line: **`ALL GREEN - the house is demo-ready`**. Any red line
names the failing service and the fix; the symptom-indexed deep dive is
[`docs/operations/troubleshooting.md`](../../docs/operations/troubleshooting.md).

## Step 2 — Open the dashboard

Open `dashboard/index.html` in a browser (or the packaged Windows app —
build steps in [`packaging/`](../../packaging/)). In ⚙ Settings set the hub
to `ws://<HUB-IP>:19001/mqtt`. Expected: rooms on the floor plan, a
breathing green dot per live camera; click a room for its preview.

## Step 3 — A fall, end to end

- **Real:** lie down in view of the camera room's camera and stay down —
  detection needs ~2 seconds of continuous view of you on the floor.
- **Injected** (no acrobatics required):
  ```bash
  ssh iq9 "cd qnet-home && PYTHONPATH=. ~/qnet-agent-venv/bin/python dev/inject.py --port 11883 fall --room kitchen"
  ```

Expected sequence: the room asks aloud *"I saw you fall. Take a breath — are
you okay?"* → answer it, or stay silent and watch the ladder: comfort lines,
the Telegram question (Guide 4), the **SIMULATED** emergency call. Speak
*"I'm the first responder — give me a summary of what happened"* for the
spoken handover. End with **"false alarm"** or the dashboard's **Mark
resolved**.

## Step 4 — Find something

Near any voice room, say: **"Hey Home, where are my keys?"** Expected:
every camera room checks with its own VLM (~4–6 s) and the room you asked
from speaks the answer with a landmark — or an honest miss naming what was
actually checked.

## Where to look when something misbehaves

| Symptom in | Look at |
|---|---|
| The engine (no replies, wrong escalation) | `ssh iq9 "journalctl -u qnet-agent -f"` |
| A room's ears/voice | `ssh <board> "docker logs -f qnet-voice-node-main-1"` |
| Fall detection | `ssh <board> "journalctl -u qnet-vision -f"` · live tuner: `dev/vision_tuner.py` |
| The VLM | `ssh <board> "docker logs -f genai-llm-vlm-service"` |
| The wire itself | `.venv/Scripts/python dev/spy.py --broker <HUB-IP> --port 11883` |
| Voice-loop latency | `.venv/Scripts/python dev/voice_bench.py --broker <HUB-IP> --port 11883` |

Everything else: [`docs/operations/troubleshooting.md`](../../docs/operations/troubleshooting.md).

## What you have now

The whole house: falls answered out loud and escalated to real phones,
belongings found by cameras that never share a frame. For the demo script
and timings, see [`docs/DEMO.md`](../../docs/DEMO.md).
