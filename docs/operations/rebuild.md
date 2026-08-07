# Rebuild a device from scratch

*Back to the [docs index](../README.md). This is the **from-a-blank-board**
path. If the boards already exist and you just powered them off, you want
[`cold-start.md`](cold-start.md) instead — everything auto-starts and one
command verifies it.*

Each section is ordered so that every step can be verified before the next.
Credentials are not in this repo: SSH aliases (`iq9`, `ventuno`, `ventuno2`)
live in `~/.ssh/config`, secrets in each board's gitignored
`config/house.local.yaml` (see [`devices.md`](devices.md)).

## IQ-9075 — the brain

*Outcome: the hub — LLM endpoint on `:18181`, broker on `11883`/`19001`, and
the agent connected to both.*

1. **LLM**: follow [`setup/iq9-gemma-geniex/README.md`](../../setup/iq9-gemma-geniex/README.md)
   (GenieX + Gemma 4 E2B + the `geniex-serve` unit). Verify with the tests in
   that folder. *Board gotcha: never `apt --fix-broken install` here — use
   `apt-get download <pkg> && sudo dpkg -i`.*
2. **Broker**: install mosquitto (same download+dpkg route), then copy
   [`infra/mosquitto.conf`](../../infra/mosquitto.conf) to
   `/etc/mosquitto/conf.d/qnet.conf`, `sudo systemctl enable --now mosquitto`.
   Verify: `ss -tlnp | grep -E '11883|19001'` shows both listeners.
3. **Agent code**: ship the repo tree to `~/qnet-home` —
   `git archive main --prefix=qnet-home/ | ssh iq9 'tar -x -C ~'` (or clone).
4. **Agent venv**: `python3 -m venv ~/qnet-agent-venv && ~/qnet-agent-venv/bin/pip install aiomqtt httpx pyyaml openai`.
5. **Secrets + board config**: create `~/qnet-home/config/house.local.yaml` with
   the Telegram bot token, the contact chat ids, and — critically —
   `mqtt: {host: 127.0.0.1, port: 11883}`. **Never copy the laptop's copy**
   (`verify/INCIDENT-wrong-broker.txt`).
6. **Unit**: `sudo cp infra/systemd/qnet-agent.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now qnet-agent`.
   Verify: `journalctl -u qnet-agent | grep connected` says `127.0.0.1:11883`.

## Ventuno Q — a room node

*Outcome: a room that watches (fall detection where there's a camera), looks
("where's my stuff" via its own VLM), streams a LAN preview, and hears/speaks
— all auto-starting on boot.*

Steps 1–4 apply to every room; 5 is kitchen-only; 6–7 are per-capability.

1. **QAIRT** (not preinstalled on this image):
   `sudo apt-get install -y qairt-tools qairt-libs qairt-dsp-binaries qairt-headers`.
2. **Node venv**: `python3 -m venv ~/qnet-venv && ~/qnet-venv/bin/pip install numpy opencv-python-headless paho-mqtt pyyaml httpx`.
3. **Node code**: from the laptop run
   [`scripts/deploy_vision_ventuno.sh`](../../scripts/deploy_vision_ventuno.sh)
   and/or [`scripts/deploy_look_ventuno.sh`](../../scripts/deploy_look_ventuno.sh)
   → `~/qnet-node`.
4. **Camera path**: always address the camera by its stable id
   (`ls /dev/v4l/by-id/`), never `/dev/videoN` — USB re-enumeration silently
   broke a board once ([`troubleshooting.md`](troubleshooting.md)).
5. **Fall detection (kitchen only)**: compile/copy the QNN context binary per
   [`models/fall-detection/README.md`](../../models/fall-detection/README.md)
   into `/data/local/tmp/quad/models/` (create it and `chown arduino:arduino`
   — it does not exist by default). Verify with a single `qnn-net-run`.
6. **VLM (every room that answers "where is my…")**: follow
   [`setup/ventuno-vlm/README.md`](../../setup/ventuno-vlm/README.md) — compose
   file + model directory (rsync board-to-board beats re-downloading), then
   `docker compose up -d`. Verify `/v1/models` lists `qwen3_vl_4b_instruct`.
   **Set `restart: unless-stopped`** or the room comes back blind after a
   reboot.
7. **Voice (every room that hears/speaks)**: the board's built-in
   `whisper-small-quantized` ASR model works with no download — for the float
   `whisper-small` upgrade, register the Whisper QNN artifacts with
   [`scripts/install_whisper_voice_ai_model.sh`](../../scripts/install_whisper_voice_ai_model.sh)
   (rsync them from another board's
   `/var/lib/arduino-app-cli/models/audio-analytics/asr/`, or use a Qualcomm
   Voice AI artifact — details in the runbook below), deploy the app with
   [`scripts/deploy_voice_node.sh`](../../scripts/deploy_voice_node.sh), write
   `~/ArduinoApps/qnet-voice-node/qnet-config.json` from the matching file in
   [`config/voice-nodes/`](../../config/voice-nodes/) (set `room_id`,
   `iq9_host`, `mqtt_port: 11883`, and the mic/speaker `usb:N` from
   `arecord -l` / `aplay -l`), then
   `arduino-app-cli app start user:qnet-voice-node`. Background:
   [`setup/ventuno-voice/arduino-speech.md`](../../setup/ventuno-voice/arduino-speech.md).
8. **Units**: copy the relevant files from
   [`infra/systemd/`](../../infra/systemd/) — `qnet-vision` (kitchen),
   `qnet-look`/`qnet-stream` (both, bedroom variants have `-bedroom` names),
   and `qnet-voice-app` (both) — then `daemon-reload` and `enable --now` each.
   Edit `--room` and `--broker` to match the board.

## Laptop — dashboard, harness, packaging

*Outcome: the test suite green, the dashboard opening, and (optionally) the
installable Windows app.*

```
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" numpy pillow
.venv/Scripts/python -m pytest -q          # the hermetic suite
```

Dashboard: open `dashboard/index.html` (broker default is already the IQ9).
Windows app: `packaging/build.ps1` then `packaging/make_msix.ps1`
(cert trust steps in `packaging/SIGNING.md`).

## Finally

```
bash scripts/health_check.sh      # all green = the rebuild is complete
```
