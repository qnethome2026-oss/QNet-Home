# Guide 1 — The laptop (toolchain, tests, and a no-hardware demo)

**What you're doing:** getting the repo running on your computer — the test
suite proves the code works before you touch any board, and an optional
15-minute demo runs the entire product loop with zero hardware.

**You need:** any computer with Python 3.12+, Git, and a web browser.
Windows on ARM64 is what we run; Linux/macOS work the same (swap
`.venv/Scripts/` for `.venv/bin/` in every command).

---

## Step 1 — Clone and install

```bash
git clone <this-repo-url> QNet-Home
cd QNet-Home
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # Linux/macOS: .venv/bin/pip
```

## Step 2 — Prove the code

```bash
.venv/Scripts/python -m pytest -q
```

Expected: **200+ passed** (a handful "deselected" is normal — those need live
hardware). If this is green, every engine behavior in the docs is verified on
your machine.

## Step 3 (optional) — The whole product with no boards

1. **Terminal A** — start a local MQTT broker:
   ```bash
   .venv/Scripts/python dev/broker.py
   ```
   Leave it running. It listens on `1883` (MQTT) and `9001` (WebSocket).
2. **Terminal B** — run the scripted fall demo end to end:
   ```bash
   bash scripts/demo_fallback.sh
   ```
   Expected: it injects a fall, walks the whole escalation ladder in ~5
   seconds (timers scaled down), and prints **PASS**.
3. **See it:** open `dashboard/index.html` in your browser. Click ⚙ Settings
   and set the hub URL to `ws://127.0.0.1:9001/mqtt`. The floor plan goes
   live against your local broker.
4. **Drive it yourself:**
   - Inject a fall: `.venv/Scripts/python dev/inject.py fall --room kitchen`
     (the default port `1883` is your local broker) and watch the dashboard
     narrate the escalation.
   - Or open `dev/sim.html` — a room simulator that types what a person
     would have said, routed exactly like real speech.

## What you have now

The code proven on your machine, and a feel for the product loop. Next:
[Guide 2 — the hub](02-hub-iq9075.md).
