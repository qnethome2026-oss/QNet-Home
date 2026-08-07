# `bring_up.sh` — one command to start (or recover) the whole house

Companion doc to [`bring_up.sh`](bring_up.sh) — same name, same folder, they
go together. The script **acts** (restarts every service on every board, in
order, then verifies); this page explains what each stage does, what the
diagnostics mean, and where to go when the script says a problem is one it
cannot fix. Everything here was battle-tested during the 2026-08-07 overnight
recovery.

## Usage

```bash
bash scripts/bring_up.sh                                # IPs from the top of the script
bash scripts/bring_up.sh <HUB-IP> <KITCHEN-IP> <BEDROOM-IP>   # IPs as arguments
QNET_BEDROOM= bash scripts/bring_up.sh                  # empty IP = skip that board
bash scripts/bring_up.sh --dry-run                      # print the plan, touch nothing
```

The three IPs live in a marked block at the top of the script (they move on
DHCP — override by argument or `QNET_IQ9`/`QNET_KITCHEN`/`QNET_BEDROOM` env
vars). SSH goes to `user@IP` directly, so nothing depends on `~/.ssh/config`
aliases. The boards' `sudo` will prompt for their passwords — none are stored
in the repo. Expect **~2 minutes end to end**: the voice apps reload their
speech models (~45 s) and a VLM's first answer after a start takes ~50 s.

## What each stage does

| Stage | Commands | What you get |
|---|---|---|
| 1. Hub (IQ-9075) | restart `mosquitto`, `geniex-serve`, `qnet-agent`; then check the journal | The event fabric, the LLM on `:18181`, the engine — **verified connected to `127.0.0.1:11883`** (anything else means the board's `house.local.yaml` is wrong) |
| 2. Kitchen node | restart `qnet-vision`/`qnet-look`/`qnet-stream`; `docker start` the VLM; `arduino-app-cli app restart` the voice app | Fall detection, "where's my stuff", camera preview, ears + voice |
| 3. Bedroom node | same minus `qnet-vision` (fall detection is kitchen-only by design) | Look + preview + ears + voice |
| 4. Wait | 45 s | Voice apps finish reloading Whisper/TTS models |
| 5. Diagnostics | see below | The failure modes a restart **cannot** fix, named explicitly |
| 6. Verification | runs [`health_check.sh`](health_check.sh) | **`ALL GREEN - the house is demo-ready`** or the exact failing check with its fix |

## The diagnostics stage — what the warnings mean

Each check exists because the failure happened live; each prints its fix.
Full write-ups: [`docs/operations/troubleshooting.md`](../docs/operations/troubleshooting.md).

| Warning | Meaning | Deep dive |
|---|---|---|
| `foreign voice app running` | Another App Lab app owns the mic/speaker, so ours shows `failed` — only one app can hold the audio devices. Park theirs (`app stop`), restart ours. | troubleshooting § *Our voice app "failed"* |
| `no camera device nodes` | `/dev/v4l/by-id/` is empty — the camera is not usable at the USB level. **No software fixes this**: reseat/move the USB connection (see escalation below). | troubleshooting § *Camera vanished* |
| `camera present but frame is stale` | Device nodes exist but the capture process is wedged — typical after a process started while the camera was absent mid-replug. Restart `qnet-vision` (kitchen) / `qnet-look` (bedroom exporter). | troubleshooting § *Camera vanished*, second trap |

## After ANY USB replugging or port change — the two rules

Learned the hard way (2026-08-07, ~03:00), both now in troubleshooting:

1. **Cameras: no config change needed.** `/dev/v4l/by-id/...` paths are
   derived from the device, not the port — just restart `qnet-vision`.
   If capture still dies, escalate cheapest-first: **different port →
   different cable → different camera** (our "dead" camera was a bad
   port/cable path; a port move fixed it outright — verify with the bare
   capture test in troubleshooting before condemning hardware).
2. **Audio: ALWAYS re-check `usb:N`.** The index is **1-based over USB
   devices of that type, in card order — not the ALSA card number** — and
   the order changes on replug: our mic index silently ended up on the
   *camera's* microphone once, and an out-of-range index crashes the app's
   main container outright. Run `arecord -l` / `aplay -l`, count the USB
   entries, fix `qnet-config.json`, restart the voice app, and mirror the
   change to `config/voice-nodes/` in the repo.
   → troubleshooting § *Voice node deaf or mute after replugging USB audio*

## Related pages

- [`docs/operations/io-devices.md`](../docs/operations/io-devices.md) — the full I/O reference: addressing model, inventory commands, move/replace procedures.
- [`health_check.sh`](health_check.sh) — the read-only half; safe any time, even mid-demo.
- [`docs/operations/cold-start.md`](../docs/operations/cold-start.md) — what auto-starts by itself after power-on (usually you need no script at all: plug in, wait ~3 min, run the health check).
- [`docs/operations/rebuild.md`](../docs/operations/rebuild.md) — a board wiped or replaced, from blank image.
- [`docs/operations/troubleshooting.md`](../docs/operations/troubleshooting.md) — every observed failure mode, symptom-indexed.
- [`setup/guides/`](../setup/guides/01-laptop.md) — first-time setup from scratch, laptop → hub → rooms → Telegram → first run.
