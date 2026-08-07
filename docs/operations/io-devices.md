# I/O devices — cameras, mics, speakers, USB ports

*The reference for plugging, moving, and addressing USB devices on the room
nodes — written so nothing here has to be re-discovered (everything below was
learned live, 2026-08-06/07). Symptom-indexed fixes:
[`troubleshooting.md`](troubleshooting.md). Per-board current inventory:
[`devices.md`](devices.md).*

## The one mental model

USB devices are addressed two completely different ways in this system:

| | Cameras | Audio (mic/speaker) |
|---|---|---|
| Address form | `/dev/v4l/by-id/usb-<vendor>...-video-index0` | `usb:N` in the voice app's `qnet-config.json` |
| Derived from | **The device itself** (vendor/model/serial) | **Plug order**: 1-based index over USB devices of that type, in ALSA card order — NOT the ALSA card number |
| Survives a port move? | **Yes** — zero config changes, just restart the service that owns it | **No** — indices can shift on ANY replug; always re-check |
| Survives replacing the device? | No — new device = new by-id path; update unit + config | Maybe — only if the count/order of USB audio devices ends up the same |
| Never use | `/dev/videoN` (renumbering broke a board overnight once) | ALSA card numbers as `usb:N` (crashes the app: `USB speaker index out of range`) |

## Inventory commands (run on the board)

```bash
lsusb                      # what's physically on the bus (hubs show here too)
ls /dev/v4l/by-id/         # camera addresses - the ...-video-index0 entries
arecord -l                 # capture devices, in card order (CAMERA MICS APPEAR HERE TOO)
aplay -l                   # playback devices, in card order
sudo dmesg | tail -20      # what happened at the USB level just now
```

Counting `usb:N` from `arecord -l` / `aplay -l`: ignore non-USB rows
(`monaco-gertrude` is the SoC), then number the USB rows 1, 2, 3… in card
order. Example (kitchen, 2026-08-07): capture shows Camera (card 1) then
JOUNIVO (card 2) → the real mic is `usb:2`; playback shows one USB speaker →
it is `usb:1` **whatever its card number says**.

## Who owns which device (do not double-open)

| Device | Owner | Everyone else |
|---|---|---|
| Kitchen camera | `qnet-vision` | `qnet-look` reads vision's `/dev/shm` frame export; `qnet-stream` serves it; neither opens the camera while vision is healthy |
| Bedroom camera | `qnet-look` (with `--export-every 1`) | `qnet-stream` serves the export |
| Mic + speaker (each board) | the `qnet-voice-node` App Lab app — **exclusively**; a second app opening them makes ours crash at startup | — |

## Procedures

### Move a camera to another port
1. Move the plug. 2. `sudo systemctl restart qnet-vision` (kitchen) or
`qnet-look` (bedroom). 3. Confirm the frame advances:
`ls --full-time /dev/shm/qnet_<room>_frame.jpg` twice, 10 s apart.
No config changes — the by-id path followed the device.

### Replace a camera with a different one
1. `ls /dev/v4l/by-id/` → note the NEW `...-video-index0` path.
2. Put it in the unit (`sudo systemctl edit --full qnet-vision` or edit
   [`infra/systemd/`](../../infra/systemd/) + redeploy) and in
   `config/house.yaml`'s room `source`. 3. `daemon-reload`, restart, confirm
   frames advance.

### Plug in / move / replace audio (mic, speaker, headset, hub)
1. Plug in; wait a few seconds to enumerate (`lsusb` should show it — hubs
   are fine, incl. bus-powered; both our desk devices hang off one hub).
2. `arecord -l` + `aplay -l` → count USB entries per the rule above.
3. Set `microphone_device`/`speaker_device` (`usb:N`) in
   `~/ArduinoApps/qnet-voice-node/qnet-config.json`.
4. `arduino-app-cli app restart user:qnet-voice-node` (~45 s).
5. Verify: `docker logs qnet-voice-node-main-1` → `Connected to IQ9`, no
   `SpeakerConfigError`, no `ASR failed` loop. If ASR fail-loops with the
   runner logging a VAD init error: **full `app stop` then `app start`** —
   a plain restart can reuse the wedged runner
   ([troubleshooting](troubleshooting.md#asr-fail-loop-after-changing-audio-devices-the-runners-vad-wedge-2026-08-07)).
6. Mirror the change into [`config/voice-nodes/`](../../config/voice-nodes/)
   in the repo so the next deploy doesn't undo it.

### A camera (or any USB device) is flaky
Escalate cheapest-first: **different port → different cable → different
device.** The discriminating test for "is it actually the camera", with the
owning service stopped so the device is free:

```bash
timeout 12 gst-launch-1.0 v4l2src device=<by-id path> num-buffers=2 ! fakesink
```

Fails on a free device = the connection/hardware is bad, no software will fix
it. A high `lsusb` device number (e.g. `Device 118`) means the connection has
re-enumerated that many times — it is flapping. Kernel signature of a
connection too poor to use at all: `Found UVC device` then
`No valid video chain found` in dmesg.

### After ANY unplugging session, in one line each
- Cameras: restart the owning service (a process that started while its
  camera was absent stays wedged forever — `active` but zero frames).
- Audio: re-run the `usb:N` count (step 2 above) — indices shift silently;
  the wrong index either listens to the camera's mic or crashes the app.
- Then: `bash scripts/health_check.sh` — and
  [`scripts/bring_up.sh`](../../scripts/bring_up.sh)'s diagnostics stage
  checks the camera/frame/foreign-app traps automatically.

## Current known-good layout (2026-08-07)

| Board | Camera | Mic | Speaker |
|---|---|---|---|
| Kitchen (`ventuno`) | HHWei UVC, by-id path in `qnet-vision.service` | JOUNIVO desk mic via hub — `usb:2` (camera mic is `usb:1`) | GEMBIRD via hub — `usb:1` |
| Bedroom (`ventuno2`) | Logitech BRIO, by-id path in `qnet-look.service` | Plantronics Seri headset — `usb:1` (BRIO mic is `usb:2`) | Plantronics Seri headset — `usb:1` |
