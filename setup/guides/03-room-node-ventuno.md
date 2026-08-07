# Guide 3 — A room node (Arduino UNO Q / "Ventuno Q")

**What you're doing:** turning one board into a room that **watches** (fall
detection, if it has a camera), **looks** ("where's my stuff" via its own
VLM), **streams** a LAN-only camera preview to the dashboard, and
**hears/speaks** (wake word, on-NPU Whisper, TTS). Repeat this guide per
room; skip any capability a room doesn't need.

**You need:** an Arduino UNO Q with the vendor Ubuntu 24.04 + App Lab image
(as shipped), on the LAN; a USB UVC camera (for watch/look rooms); a USB
mic + speaker or headset (for voice rooms); the hub from Guide 2 already up,
and its IP (called `<HUB-IP>` below). Board login: user `arduino` (password:
the Arduino image default, or ask your team).

**Deep dives:** VLM → [`../ventuno-vlm/README.md`](../ventuno-vlm/README.md) ·
voice runtime → [`../ventuno-voice/arduino-speech.md`](../ventuno-voice/arduino-speech.md) ·
fall model → [`../../models/fall-detection/README.md`](../../models/fall-detection/README.md).

---

## Step 1 — SSH access

Same recipe as Guide 2 Step 1, with user `arduino`. Add an alias per board —
ours are `ventuno` (kitchen) and `ventuno2` (bedroom):

```
Host ventuno
  HostName <BOARD-IP>
  User arduino
  IdentityFile ~/.ssh/id_ed25519
```

**Verify:** `ssh ventuno 'echo SSH_OK'`.

## Step 2 — Board packages and the node venv

On the board (`ssh ventuno`):

```bash
sudo apt-get install -y qairt-tools qairt-libs qairt-dsp-binaries qairt-headers
python3 -m venv ~/qnet-venv
~/qnet-venv/bin/pip install numpy opencv-python-headless paho-mqtt pyyaml httpx
```

(QAIRT is the Qualcomm NPU runtime — present in the board's own apt repos,
just not preinstalled.)

## Step 3 — Deploy the node code

From the **laptop**, in the repo (uses the SSH alias from Step 1):

```bash
bash scripts/deploy_vision_ventuno.sh ventuno   # camera rooms
bash scripts/deploy_look_ventuno.sh ventuno     # every room that answers "where is my..."
```

Both land the code in `~/qnet-node` on the board.

## Step 4 — Find the camera's stable path

On the board:

```bash
ls /dev/v4l/by-id/
```

Note the `...-video-index0` entry for your camera and use **that** path in
every config and unit below. ⚠️ Never use `/dev/video0`-style paths — USB
re-enumeration silently swaps them (it broke a board once;
[`troubleshooting.md`](../../docs/operations/troubleshooting.md)).

## Step 5 — Fall detection (camera rooms only)

The model is already compiled for this board's NPU and committed to the
repo — nothing to convert.

1. On the board, create the model directory (does not exist by default):
   ```bash
   sudo mkdir -p /data/local/tmp/quad/models && sudo chown -R arduino:arduino /data/local/tmp/quad
   ```
2. From the laptop:
   ```bash
   scp models/fall-detection/best_ventuno_qcs8300.bin ventuno:/data/local/tmp/quad/models/
   ```

## Step 6 — The VLM ("where's my stuff" eyes)

1. From the laptop, ship the compose file:
   ```bash
   scp setup/ventuno-vlm/docker-compose-qcs8300-ubuntu.yaml ventuno:~/
   ```
2. Get the model onto the board at `/home/arduino/models/`. Two ways:
   - **From another QNet board** (fastest, ~2 min on a LAN):
     `rsync -a arduino@<other-board>:/home/arduino/models/ /home/arduino/models/`
   - **First board:** pull `qwen3_vl_4b_instruct` (w4a16, ~4.1 GB) per the
     container's model docs — see [`../ventuno-vlm/README.md`](../ventuno-vlm/README.md).
3. On the board, start it:
   ```bash
   GENAI_MODEL_DIR=/home/arduino/models docker compose -f ~/docker-compose-qcs8300-ubuntu.yaml up -d
   ```

**Verify:** `curl -m 120 http://127.0.0.1:9001/v1/models` lists the model.
The first query after a start can be slow or empty — retry once (model load
≈ 50 s).

## Step 7 — Voice (rooms that hear and speak)

1. From the laptop, deploy the app:
   ```bash
   bash scripts/deploy_voice_node.sh <BOARD-IP>
   ```
2. On the board, find the mic and speaker indices:
   ```bash
   arecord -l    # microphone cards
   aplay -l      # speaker cards
   ```
   ⚠️ `usb:N` is **NOT the ALSA card number** — it is a **1-based index over
   the USB devices of that type**, in card order (learned from the brick's
   own error: `USB speaker index 3 out of range. Available: 1-1`). Count only
   the USB entries in each list: one USB speaker → it is `usb:1`, whatever
   its card number. For the microphone, a camera's built-in mic counts too —
   if the camera is the first USB capture device, your real mic is `usb:2`.
3. On the board, create `~/ArduinoApps/qnet-voice-node/qnet-config.json`
   (start from [`config/voice-nodes/`](../../config/voice-nodes/) — the
   kitchen and bedroom files are our real, working examples):
   ```json
   {
     "device_id": "kitchen-voice-01",
     "room_id": "kitchen",
     "groups": [],
     "iq9_host": "<HUB-IP>",
     "mqtt_port": 11883,
     "mqtt_username": null,
     "mqtt_password": null,
     "microphone_device": "usb:2",
     "speaker_device": "usb:1",
     "asr_model": "whisper-small-quantized",
     "language": "en",
     "idle_listen_timeout_seconds": 30,
     "session_listen_timeout_seconds": 15,
     "transcript_window_seconds": 10,
     "post_tts_guard_ms": 500,
     "tts_queue_size": 20,
     "responder_phrase": "I am the first responder"
   }
   ```
   Field notes: `room_id` must match a room in `config/house.yaml`;
   `asr_model: whisper-small-quantized` is **built into the board** and works
   with no download (we run the float `whisper-small` — an optional upgrade
   installed with `scripts/install_whisper_voice_ai_model.sh`, see the
   [voice runbook](../ventuno-voice/arduino-speech.md)).
4. On the board, start the app (first start provisions models, ~1–2 min):
   ```bash
   arduino-app-cli app start user:qnet-voice-node
   ```

**Verify:** `docker logs qnet-voice-node-main-1 2>&1 | grep Connected` shows
`Connected to IQ9; subscribed to qnet/<room>/say and qnet/session/+`.

## Step 8 — Make it all survive reboots (systemd)

From the laptop, copy the units this room needs, then install each on the
board. Kitchen-style camera room:

```bash
scp infra/systemd/qnet-vision.service infra/systemd/qnet-look.service infra/systemd/qnet-stream.service infra/systemd/qnet-voice-app.service ventuno:/tmp/
ssh ventuno "sudo cp /tmp/qnet-*.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now qnet-vision qnet-look qnet-stream qnet-voice-app"
```

⚠️ **Before enabling, edit each unit's `ExecStart`** on the board
(`sudo nano /etc/systemd/system/qnet-*.service`): set `--room` to this room,
`--broker` to `<HUB-IP>`, and `--source` to the Step 4 camera path. A room
without a camera skips `qnet-vision`; a second camera room uses the
`-bedroom` unit variants (they install under the same names — their headers
explain).

## Verify the whole room

From the laptop:

```bash
.venv/Scripts/python dev/spy.py --broker <HUB-IP> --port 11883 -t 'qnet/#'
```

Within ~5 s you should see `qnet/<room>/status` heartbeats. Say the wake
phrase — *"Hey Home, where are my keys?"* — and watch the `ask` appear.

## What you have now

A room that watches, looks, streams, hears, and speaks — and comes back by
itself after a power cycle. Repeat for the next room, or go to
[Guide 4 — Telegram](04-telegram.md).
