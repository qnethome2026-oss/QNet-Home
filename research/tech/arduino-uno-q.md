# Arduino UNO Q — Deep Technical Dive (for QNet Home)

Research date: **2026-08-03**. Sources at bottom. Everything is labelled
**[VERIFIED]** (primary source: Qualcomm data sheet, Arduino docs/pinout PDF, Arduino/Edge
Impulse source code), **[REPORTED]** (third-party blog/review measurement), or
**[ESTIMATE]** (my extrapolation — do not put in the deck without measuring it yourself).

---

## 0. Executive summary — the 8 things that change our design

1. **There is NO NPU and NO compute-DSP on the UNO Q.** The QRB2210 data sheet
   (80-30843-1 Rev AE, 89 pages) contains **zero** occurrences of "Hexagon", "HVX", "NPU",
   "TOPS" or "neural". The only DSP is `LPASS QDSP6 v66` — an *audio + sensor* DSP, and
   Qualcomm's own overview says it is a "dedicated DSP **shared** between Snapdragon sensor
   core and low-power audio subsystem". ML acceleration on UNO Q = **CPU (4×A53 @2.0 GHz) +
   Adreno 702 GPU @845 MHz via OpenCL 2.0**. All "NPU offload" claims in our pitch must be
   attributed to the Snapdragon X Elite Hexagon NPU and/or AIC100 — never to the UNO Q. **[VERIFIED]**
2. **Arduino's own code proves it**: in `arduino/app-bricks-py`, every QNN/NPU-accelerated
   model and every offline speech brick is gated `supported_boards: ["ventunoq"]`. The
   `asr` (Whisper) and `tts` (Piper/MeloTTS) bricks are **Ventuno Q only**. On UNO Q there is
   *no first-party on-device ASR or TTS*. **[VERIFIED]**
3. **But the UNO Q *can* run a local LLM**: App Lab 0.9.0 (2026-07-10) added the "LLM brick
   for UNO Q" — llama.cpp CPU, 4 threads, 16k ctx, default `Qwen3.5-0.8B-Q4_0` (507 MB) or
   `gemma-3-1b-it-Q4_0` (722 MB). The container has `mem_limit: 2500m`, so **the 4 GB variant
   is effectively mandatory** if you want an LLM on the node. **[VERIFIED]**
4. **GStreamer is first-class and Qualcomm-native.** The image ships GStreamer 1.0 +
   plugins-base/good, **libcamera 0.7 + `libcamerasrc`**, and Qualcomm's **`qtiqmmfsrc`**
   plugin. Arduino's `CSICamera` builds literally
   `libcamerasrc camera-name=… ! video/x-raw,width=…,framerate=…/1 ! videoconvert !
   video/x-raw,format=BGR ! appsink drop=true max-buffers=1`. Our team's GStreamer expertise is
   directly on-target — this is our unfair advantage. **[VERIFIED]**
5. **Only one published FPS number exists for UNO Q vision**: **~58 ms/inference ≈ 17 inferences/s**
   for an Edge Impulse **YOLOv5-Pico** model at 640×480 on the UNO Q (Foundries.io, "Elf Detector"
   series). Use that as our anchor. **[REPORTED]**
6. **Edge Impulse has a GPU deployment target for this board**: Studio → Deployment offers
   "Arduino UNO Q" (CPU), "Linux aarch64" (CPU) and **"Linux Arduino UNO Q (GPU)" —
   "GPU-accelerated inference via Adreno 702"**. This is our only legitimate "hardware offload
   on the node" claim, and it's a cheap win for the 40-pt technical criterion. **[VERIFIED]**
7. **Practical I/O is USB-only.** One USB-C port does power + data + DisplayPort. Camera, mic and
   speaker all realistically arrive over a **powered USB-C hub with PD**. The board *does* have
   analog `MIC2_INP/INM/BIAS`, `HPH_L/R`, `LINEOUT_P/M`, `EAR_P/M` and dual 4-lane MIPI-CSI —
   but only on two **60-pin bottom high-density connectors (JMISC / JMEDIA)**, i.e. you need a
   mating carrier board we do not have. **[VERIFIED from official pinout PDF]**
8. **Someone already published "UNO Q senses + Snapdragon X Elite NPU infers"** (Shivay Lamba,
   Arduino Project Hub + Medium, 2026-04-29: Modulino Distance → UNO Q → Windows-ARM64 laptop
   running MobileFaceNet/CavaFace via **ONNX Runtime QNN EP** → Modulino Buzzer). Our
   differentiation must be the *semantic event bus + agentic tool-calling + two-way voice +
   multi-room*, not "UNO Q talks to a Copilot+ PC". **[VERIFIED]**

---

## 1. Hardware

### 1.1 SoC — Qualcomm Dragonwing QRB2210 [VERIFIED, QRB2210 Data Sheet 80-30843-1 Rev AE]

| Block | Spec |
|---|---|
| CPU | 64-bit, **4× Arm Cortex-A53 @ 2.0 GHz**, 512 kB L2 |
| GPU | **Adreno 702 @ 845 MHz**, OpenGL ES 3.1, **Vulkan 1.1, OpenCL 2.0**, 64-bit addressing |
| DSP | **LPASS QDSP6 v66 K**, 512 kB L2 — *audio and sensor processing only*. No cDSP, no HVX, no NPU |
| ISP | **2× ISP (13 MP + 13 MP, or 25 MP) @ 30 fps ZSL**; Spectra 340L; 48 MP nZSL |
| MIPI-CSI | Combination D-PHY 1.2 / C-PHY 1.0, configurable **4/4 or 4/2/1**; D-PHY 2.5 Gbps/lane |
| Video encode | **1080p30 H.264** and **1080p30 HEVC (H.265)**, 8-bit (Venus) |
| Video decode | 1080p30 H.264 / H.265 / VP9 |
| Video concurrency | **1080p30 decode + 720p30 encode** simultaneously |
| HFR capture | 480p120 |
| Display | 1× 4-lane MIPI-DSI D-PHY 1.2 (1.5 Gbps/lane), HD+ 720×1680 @60 Hz, Adreno DPU 920 |
| Memory | Dual-channel LPDDR4X 2×16-bit @1804 MHz (or LPDDR3 1×32-bit @933 MHz) |
| Storage IF | eMMC 5.1 / SD 3.0 |
| Audio | Integrated codec in **PM4125 PMIC**, optional WSA8810 smart amp; SLIMbus + SoundWire (2 Tx / 2 Rx) |
| Audio/voice features | "Support for **two voice activation engines**", "**integrated low-power island for voice activation**", "always-on noise suppression", low-power 7.1 audio |
| Power (CPU rail) | **Dhrystone 1.5 W** on VDD_APC, quad-core @2 GHz, Tj +95 °C; **rock-bottom 10.4 mW** |
| Wireless (SoC ref) | WCN3910/WCN3950 (Arduino uses the **WCBN3536A** module) |

> The "**integrated low-power island for voice activation**" + "two voice activation engines" is a
> genuinely interesting energy-efficiency angle, but it is a *mobile/Android* feature of the
> LPASS island. There is **no evidence it is exposed on Arduino's Debian image** — treat as a
> talking point, not a deliverable, unless we verify it on hardware. **[VERIFIED spec / UNVERIFIED on board]**

### 1.2 Board [VERIFIED]

| | |
|---|---|
| MCU | **STM32U585** (Cortex-M33 @160 MHz, 2 MB flash, 786 kB SRAM, FPU), runs Arduino sketches on **Zephyr** |
| SKUs | **ABX00162**: 2 GB LPDDR4 + 16 GB eMMC — **$44** / €47.60 · **ABX00173**: 4 GB + 32 GB eMMC — **$59** |
| Form factor | UNO, **68.58 × 53.34 mm** |
| I/O | **47 digital I/O**, 6× 14-bit ADC, 2× 12-bit DAC, 6× PWM, 3× USART, 2× UART, 4× I2C (I²C/I³C), 3× SPI, **CAN-FD**, JTAG |
| Expansion | **Qwiic** connector (Modulino), classic UNO shield headers |
| On-board UI | **8×13 blue LED matrix**, 4× (2×) user RGB LEDs, user push-button, power button |
| USB | **1× USB-C**, host/device role switch, power-role switch, **DisplayPort/HDMI-via-dongle video out** |
| Wireless | **Wi-Fi 5 dual-band 2.4/5 GHz + Bluetooth 5.1**, on-board antenna (WCBN3536A) |
| Power | **5 V @ max 3 A via USB-C**, or **VIN 7–24 V DC** |
| Debug | QRB2210 acts as CMSIS-DAP/SWD adapter for the STM32 (`adb shell arduino-debug` + openocd) |
| Launch | Announced 2025-10-07 (same day Qualcomm announced it is **acquiring Arduino**); shipped 2025-10-24. 4 GB SKU available 2026-01-21 |

### 1.3 The bottom connectors, exactly (from the official full-pinout PDF, rev 2026-02-17) [VERIFIED]

Two **60-pin high-density board-to-board connectors** on the underside. These pins **cannot be
used as regular GPIOs** and are **1.8 V logic** (MCU headers are 3.3 V — warning is printed on the pinout).

* **JMEDIA** — MIPI-DSI0 (CLK + L0..L3 diff pairs), **CSI0** 4 lanes (`CSI0_*_LN0..LN3` + CLK),
  **CSI1** 4 lanes, `SOC_CAM_MCLK0/1`, `CCI_I2C_SCL0/SDA0`, `CCI_I2C_SCL1/SDA1`, +3V3, VIN,
  4 SoC GPIOs (`GPIO_20/21/22/23/29/30`).
* **JMISC** — **analog audio from the PMIC**: `MIC2_INP`, `MIC2_INM`, `MIC2_BIAS`,
  `HPH_L`, `HPH_R`, `HPH_REF`, `HS_DET`, `EAR_P_R`, `EAR_M_R`, `LINEOUT_P`, `LINEOUT_M`;
  plus `MCU_OPAMP1_VINP/VINM/VOUT`, `MCU_I2C4_SCL/SDA`, MCU trace/SDMMC pins,
  `SOC_GPIO_98..101`, `SOC_GPIO_*_SE0`, +3V3/+1V8/VBAT/VCOIN/+5V USB.
  Pinout note: *"Analog Audio functionality is provided by the PMIC."*

**Consequence for us:** without a carrier/breakout, **all camera and audio must be USB**.
Budget a **powered USB-C hub with PD** per node (this is the #1 logistics risk; multiple
reviewers report hub incompatibility, see §10).

---

## 2. The NPU question — settled

| Claim | Verdict |
|---|---|
| "UNO Q has an NPU" | **False.** No Hexagon/NPU/HVX/TOPS anywhere in the QRB2210 data sheet. |
| "UNO Q has a Hexagon DSP" | Half-true: `LPASS QDSP6 v66` exists but is the audio/sensor DSP, not a QNN/HTP target. Some third-party spec pages (CNX) loosely list "Hexagon DSP" — do not repeat it. |
| "UNO Q can run QNN / Qualcomm AI Runtime" | **No evidence.** In `app-bricks-py`, `ei-qnn-models-runner` and `llamacpp-npu-runner` containers mount `/dev/fastrpc-cdsp`, `/dev/fastrpc-cdsp-secure`, `/dev/dma_heap/system` and the **`qcs8300` cDSP firmware** — all Ventuno Q (Dragonwing IQ8 / QCS8275-class) paths. |
| "UNO Q can GPU-accelerate ML" | **Yes** — Adreno 702 / OpenCL 2.0; Edge Impulse ships a dedicated **"Linux Arduino UNO Q (GPU)"** deployment target described as "GPU-accelerated inference via Adreno 702". |
| Hardware blocks we *can* legitimately claim as offload | **2× ISP** (debayer/AE/AWB/scaling free of CPU), **Venus H.264/H.265 encoder + decoder** (`/dev/video0` = encoder, `/dev/video1` = decoder), **Adreno 702 GPU**, **STM32U585 MCU** (always-on sensing / real-time actuation). |

### For contrast — Arduino **VENTUNO Q** (do we even have one? probably not)
Announced/pre-release as of mid-2026, **not shipping** while Arduino/Qualcomm upstream the kernel.
Dragonwing **IQ8 (IQ-8275 / QCS8275-class)**, octa-core, **Adreno 623 @877 MHz**,
**Hexagon Tensor NPU 40 INT8 TOPS**, 16 GB LPDDR5, 64 GB eMMC + M.2 NVMe Gen4, Wi-Fi 6, BT 5.3,
2.5 GbE, 160×100×25.8 mm. Pre-release Geekbench 6 ≈ **2100 single / 2700 multi**, and the article
notes that is "roughly 50 % better than Uno Q" multi-core ⇒ **UNO Q ≈ 1800 multi-core GB6 [ESTIMATE
derived from a stated ratio]**. On Ventuno Q, Arduino ships Whisper-Small-quantized ASR,
Piper/MeloTTS, Qwen3-4B / Qwen3-VL-4B / Qwen2.5-VL-7B via **Genie**, QNN-accelerated YOLOX and
face-det-lite, and an NPU-utilisation meter in App Lab. **[REPORTED / VERIFIED from model manifest]**

> **Pitch implication:** we can honestly say "QNet Home's node tier is deliberately built for the
> *cheapest* Dragonwing silicon with no NPU, so it also scales *up* unchanged to Ventuno Q's 40-TOPS
> NPU by swapping a model manifest." That's an architecture-quality point judges like.

---

## 3. Camera support

### 3.1 What Arduino actually supports in software [VERIFIED — `app_peripherals/camera`]
`Camera()` auto-selects one of four backends:

| Backend | Source syntax | Underlying |
|---|---|---|
| `V4LCamera` | `Camera("usb:0")`, `Camera("/dev/video2")` | V4L2 (OpenCV `CAP_V4L2`) — **USB UVC webcams** |
| `CSICamera` | `Camera("csi:0")`, `Camera("csi:CAMERA0")` | GStreamer: **`libcamerasrc`** (mainline `qcom-camss` driver) **or `qtiqmmfsrc camera=N`** (CamX/cam-server) — auto-detected |
| `IPCamera` | `Camera("rtsp://…")`, `Camera("http://…/stream")` | RTSP / HLS / HTTP-MJPEG, auth + auto-reconnect |
| `WebSocketCamera` | `Camera("ws://0.0.0.0:8080")` | **Board hosts a WS server; a phone/PC pushes JPEG/base64 frames** (1 client at a time) |

Notes:
* CSI stack detection: `camss_driver_present()` checks `/sys/bus/platform/drivers/qcom-camss`;
  CamX path needs `cam-server`. Arduino even filters `libgstqtiqmmfsrc` out of the GStreamer
  plugin path on CAMSS hosts because it *aborts at load time* when cam-server is absent —
  i.e. **the shipping image is the mainline CAMSS/libcamera stack**, not CamX. [VERIFIED from code comments]
* `WebSocketCamera` + `RemoteSensor` (WS telemetry server, JSON/CSV/binary) are **built-in
  multi-device plumbing** — an Android phone can be a camera or a sensor for the node with zero
  custom protocol work. Directly relevant to the "multi-device orchestration" theme.

### 3.2 `/dev/video*` map on UNO Q with one USB webcam [VERIFIED — Edge Impulse reference doc]

| Node | What it is |
|---|---|
| `/dev/video0` | **Qualcomm Venus video ENCODER** (not a camera!) |
| `/dev/video1` | **Qualcomm Venus video DECODER** (not a camera!) |
| `/dev/video2` | USB camera RGB main stream (e.g. Logitech BRIO) |
| `/dev/video3` | camera metadata |
| `/dev/video4` | IR stream (if the webcam has one, e.g. BRIO) |
| `/dev/video5` | IR metadata |

Gotchas: the `video_objectdetection` brick defaults to `VIDEO_DEVICE=/dev/video1` (!) — override it.
Always filter card names containing `venus`/`encoder`/`decoder`. Force `MJPG` FourCC for
1280×720 to avoid raw-YUYV USB bandwidth limits. **An IR-capable webcam (Logitech BRIO) is a
sneaky low-light win for elderly night-time monitoring.**

### 3.3 MIPI CSI in practice
Electrically supported (2 ports × 4 lanes on JMEDIA, dual ISP, 13 MP+13 MP @30 fps) and
software-supported (`libcamerasrc` via CAMSS). **Practically unusable for us**: needs a mating
60-pin carrier + a libcamera-supported sensor tuning file. **Use USB UVC.** [VERIFIED]

---

## 4. Audio: microphone capture and speech output

### 4.1 What exists [VERIFIED]

* **On-board analog audio** (`MIC2_INP/INM/BIAS` differential electret mic + bias, `HPH_L/R`,
  `LINEOUT_P/M`, `EAR_P/M`) — **PMIC PM4125 codec, JMISC 60-pin connector only**.
* **`Microphone` peripheral** (`app_peripherals/microphone`): ALSA (`pyalsaaudio`), defaults
  **16 kHz, mono, S16_LE, periodsize 1024**; device selector is an int index that
  "gives priority to **USB microphones** then **jack** microphones", or an explicit ALSA name, or
  `Microphone.USB_MIC_x` / `Microphone.JACK_MIC_x`, **or a `ws://` address so a remote client
  streams PCM in**.
* **`Speaker` peripheral**: ALSA out, default 16 kHz mono S16_LE, `Speaker.USB_SPEAKER_1/2`,
  `Speaker.JACK_SPEAKER_1`, tunable `periodsize` (docs suggest `periodsize=480` = 30 ms blocks
  @16 kHz for interactive/real-time synthesis) and `queue_maxsize` (5–20 blocks for low latency).
* Container image installs `alsa-utils`, `libportaudiocpp0`, **`pipewire-alsa`**, `pyaudio`.
* Brick prerequisites literally say: *"USB-C Hub with external power supply (5V, 3A)"*,
  *"USB audio device (USB speaker or USB-C → 3.5 mm adapter)"*, *"Microphones included in USB
  cameras/webcams are generally supported"*.

### 4.2 Speech OUTPUT on UNO Q — the honest answer
* The first-party **`tts` brick is `supported_boards: ["ventunoq"]`** and needs the
  `arduino:genie_audio` service + QNN. **Not available on UNO Q.** [VERIFIED]
* So on UNO Q you have three options:
  1. **(Recommended) Synthesize on the Copilot+ PC (Hexagon NPU), stream PCM to the node.**
     `Speaker` accepts raw bytes; or `Microphone(device="ws://…")`'s mirror-image pattern.
     Best latency, best quality, and it's *where our voice-cloning model lives anyway*.
     Also gives us a real NPU-offload number to quote.
  2. **Piper TTS on the A53s inside a custom brick** (Piper is CPU-only ONNX, `piper-tts_en`
     voice is only 79 MB in Arduino's own manifest). Plausible but **[ESTIMATE]**: expect
     ~0.6–1.5× real-time for a low-quality voice on 4×A53@2 GHz — measure before promising.
  3. **`espeak-ng`** — instant, tiny, robotic. Good as a fallback/failsafe voice ("system is
     offline") but not for the emotional-reassurance UX.
* **`sound_generator` brick** exists on UNO Q (tones/alarms/musical elements) plus
  `wave_generator` — free non-speech audio feedback (chime before speaking, alarm escalation).

### 4.3 Speech INPUT on UNO Q
* Local **`asr` brick (Whisper-small w8a16) is Ventuno-Q-only.** [VERIFIED]
* On UNO Q you get **`cloud_asr`** (streaming cloud STT, needs API key) — *kills our
  privacy pitch*, avoid.
* **`keyword_spotting` brick works on UNO Q** (Edge Impulse `.eim`, OOTB "Hey Arduino!" model,
  13 MB, `confidence` + `debounce_sec` params, USB mic required). Use this as the **wake-word
  gate on the node**, then stream 16 kHz PCM to the PC for full ASR. Two-tier ASR = a real
  architecture point (bandwidth + privacy + energy).
* Mic quality: expect a USB webcam array mic to be adequate for wake-word at 2–3 m, marginal for
  far-field conversational ASR. **Buy/borrow one USB conference mic (e.g. a small speakerphone
  with AEC) per node** — it also solves the speaker problem in one device and gives you
  acoustic echo cancellation, which you will need for barge-in during two-way conversation. **[ESTIMATE/advice]**

---

## 5. Software stack

### 5.1 OS & tooling [VERIFIED]
* **Debian-based Linux** on the QRB2210 (upstream-oriented; mainline `qcom-camss`, libcamera 0.7).
  Zephyr on the STM32U585 — the `arduino_uno_q` board is **upstream in mainline Zephyr**
  (`boards/arduino/uno_q`, noted in Zephyr 4.3 release notes); Zephyr-supported peripherals:
  `adc, dac, pwm, i2c, spi, dma, counter, rtc, watchdog, nvs, display, arduino_i2c, arduino_spi`
  (**no MDF/ADF PDM-mic driver — don't plan on MCU digital-mic sound-activity-detect**).
* Access: **USB (adb)**, **SSH** (`ssh arduino@<board>.local`), **App Lab web IDE on port 7000**,
  `arduino-app-cli` on-device.
* **Docker is core to the design** — every AI brick is a container from `ghcr.io/arduino/app-bricks/*`.
  Containers are Python **3.13**-slim based; `arduino_app_bricks` requires Python ≥3.13.
* Filesystem: `/home/arduino/ArduinoApps/<app>/`, `/home/arduino/.arduino-bricks/`,
  `/home/arduino/.arduino-bricks/ei-models/`, `/var/lib/arduino-app-cli/models/{edge-impulse,llamacpp}`.
  **`/home/arduino` is only ~3.6 GB** — plan model sizes and `docker system prune -a` /
  `arduino-app-cli system cleanup`.
* App Lab desktop client: **Windows 10+ (64-bit)**, macOS 11+, Ubuntu 22.04+, Debian Trixie.
  ⚠️ *Windows-on-ARM (arm64) is not called out anywhere* — **verify App Lab runs on the
  Snapdragon X Elite host on day 1**; fallback is SSH + `arduino-app-cli` (fully headless-capable).

### 5.2 App Lab release timeline [VERIFIED — GitHub releases]
`0.3.2` 2025-12-19 · `0.4.0` 2026-02-06 · `0.5.0` 2026-02-28 · `0.6.0` 2026-04-10
(Sound Generator, Telegram Bot, Cloud ASR bricks) · `0.7.0` 2026-04-29 (**Custom Bricks**) ·
`0.8.0` 2026-05-25 · **`0.9.0` 2026-07-10** (**LLM brick for UNO Q**; Ventuno Q ASR/TTS/LLM/VLM/
gesture; NPU-usage meter for Ventuno Q; multi-panel editor; WebUI auto-generation).

### 5.3 App structure, Bridge, and Custom Bricks [VERIFIED]
```
<app>/
  app.yaml           # name, icon, description, ports: [...], bricks: [...]
  python/main.py     # runs on Linux MPU; App.run() MUST be last
  sketch/sketch.ino  # runs on STM32/Zephyr
  sketch/sketch.yaml # platform: arduino:zephyr + libraries WITH versions "(x.y.z)"
  bricks/<my-brick>/ # custom brick: brick_config.yaml + brick_compose.yaml + Dockerfile + __init__.py
  models/ assets/
```
* **Bridge** = MessagePack-RPC over an internal UART (Serial1, 115200) with a `Arduino-Router`
  service on the MPU (star topology). Python: `@bridge.on_call`, `@bridge.on_notify`,
  `bridge.call(...)`, `bridge.notify(...)`. Arduino: `Bridge.provide()`, **`Bridge.provide_safe()`
  for GPIO**, `Bridge.call().result(x)`, `Bridge.notify()`. `notify()` is fire-and-forget (faster).
  **No published latency figure** — measure it; it's a nice number to put on a slide. **[VERIFIED / number missing]**
* **Custom Bricks (0.7+)** are the key extensibility hook: a brick can be *Python-only* or
  *Python + Docker container*, declared in a local `bricks/` folder and auto-deployed by App Lab.
  **This is how we ship our own GStreamer pipeline, our own MQTT/event publisher, our own
  Piper TTS, or an MCP server, without fighting the framework.**
* Constraint: **only ONE app runs per board at a time**; sketch compile at launch takes up to a minute.

### 5.4 CLI cheat-sheet [VERIFIED]
```bash
arduino-app-cli app new "my-app"
arduino-app-cli app start user:my-app        # or examples:blink, or full path
arduino-app-cli app stop <path> ; app list ; app logs <path> --all
arduino-app-cli brick list ; brick details arduino:<name>
arduino-app-cli system update | set-name "kitchen-node" | network enable|disable | cleanup
```

---

## 6. Complete Brick inventory, and which board each runs on

Source: `arduino/app-bricks-py` `src/arduino/app_bricks/*/brick_config.yaml` + `models/models-list.yaml`. **[VERIFIED]**

| Brick | Category | UNO Q? | Backend / default model |
|---|---|---|---|
| `object_detection` / `video_objectdetection` | vision | ✅ | Edge Impulse `.eim` in `ei-models-runner` container. UNO Q → **YOLOX-Nano 416×416** (CPU); Ventuno → YOLOX-Nano-QNN |
| `image_classification` / `video_imageclassification` | vision | ✅ | EI; **MobileNetV2** (27 MB), **person-classification (WakeVision) 224×224** (14 MB) |
| `visual_anomaly_detection` | vision | ✅ | EI; concrete-crack 160×160 (Ventuno gets 512×512 QNN) |
| face detection | vision | ✅ | EI-wrapped **Qualcomm AI Hub `face_det_lite`**, **320×240 on UNO Q** vs **640×480 QNN on Ventuno** — a clean illustration of the NPU gap |
| `audio_classification` | audio | ✅ | EI; OOTB **"glass-breaking" classifier** (Background / Glass_Breaking), 13 MB |
| `keyword_spotting` | audio | ✅ | EI; OOTB **"Hey Arduino!"** (background/hey_arduino/other), 13 MB, USB mic |
| `sound_generator`, `wave_generator` | audio | ✅ | pure-Python synthesis → `Speaker` |
| `motion_detection` | sensor | ✅ | EI accel model (idle/snake/updown/wave) |
| `vibration_anomaly_detection` | sensor | ✅ | EI fan-anomaly |
| `llm` | ai | ✅ **(0.9.0+)** | **llama.cpp CPU**: `Qwen3.5-0.8B-Q4_0` (507 MB) default on UNO Q; `gemma-3-1b-it-Q4_0` (722 MB) also allowed. Ventuno → Genie `qwen3_4b_instruct_2507`. LangChain-wrapped: `chat()`, `chat_stream()`, `with_memory()`, `system_prompt`, `temperature`, **`tools=`** |
| `cloud_llm` | text | ✅ | LangChain + API key (e.g. `google:gemini-2.5-flash`) |
| **`mcp_client`** | ai | ✅ | Aggregates HTTP **MCP** servers → LangChain tools → hand straight to `llm`/`cloud_llm` via `tools=`. Can **bundle an MCP server as a custom-brick container** (FastMCP or Docker MCP Gateway) |
| `mqtt` | IoT | ✅ (code) | paho-mqtt ≥2.1.0 publish/subscribe. **`brick_config.yaml` has `disabled: true`** → hidden in the UI; use `pip install arduino_app_bricks[mqtt]` or paho directly |
| `web_ui` | UI | ✅ | FastAPI + socket.io + uvicorn, serves `assets/`, port 7000 |
| `streamlit_ui` | UI | ✅ | Streamlit |
| `dbstorage_sqlstore` / `dbstorage_tsstore` | storage | ✅ | SQLite / InfluxDB |
| `telegram_bot` | IoT | ✅ | python-telegram-bot ≥21.1 — **a zero-effort "text the system from a meeting" channel for our kid-monitoring use case** |
| `arduino_cloud`, `weather_forecast`, `air_quality_monitoring`, `mood_detector` (nltk), `camera_code_detection` (zbar) | misc | ✅ | |
| **`asr`** (Whisper-small w8a16) | audio | ❌ **ventunoq only** | `requires_services: [arduino:genie_audio]`, `qnn`. 23+ languages, VAD hangover param |
| **`tts`** (Piper EN/DE/IT, MeloTTS EN/ES/ZH) | audio | ❌ **ventunoq only** | streaming PCM, `speak()`, `synthesize_wav()`, `cancel()`, sentence-chunking ≤1024 chars |
| `cloud_asr` | audio | ✅ | cloud STT with API key (privacy-hostile) |
| **`vlm`** (Qwen3-VL-4B) | ai | ❌ **ventunoq only** | Genie |
| **`gesture_recognition`** (MediaPipe hand, 21 landmarks, 6 gestures) | vision | ❌ **ventunoq only** | **LiteRT (`ai-edge-litert`) + QNN delegate**, mounts `/dev/fastrpc-cdsp*` |

Also worth stealing from: **`hand-gestures`** EI object-detection model (five/good/neut/peace) **does**
run on UNO Q via the plain `object_detection` brick — a cheap "child waves for help" / "thumbs-up
I'm OK" gesture confirm channel that avoids ASR entirely.

### 6.1 Example apps shipped (`arduino/app-bricks-examples`) [VERIFIED]
* `core-and-foundational/`: 01-led-blink … **06-camera-basics**, **07-microphone-basics**,
  08-web-ui-basics, **09-computer-vision**.
* `inspirational/common/`: **audio-classification**, **keyword-spotting**, anomaly-detection,
  object-detection, **video-generic-object-detection**, **mobile-video-generic-object-detection**
  (phone camera → board over WebSocket), video-person-classification, image-classification,
  chatbot-cloud-llm, bedtime-story-teller, telegram-bot, code-detector, music-composer,
  theremin, home-climate-monitoring-and-storage, air-quality-monitoring, system-resources-logger, …
* `inspirational/platform_unoq/`: **edge-ai-assistant** (local `llm` + `web_ui` chatbot),
  **video-face-detection**, color-your-leds, unoq-pin-toggle.
* `inspirational/platform_ventunoq/`: edge-**speech**-assistant, edge-**dictation**-assistant,
  gesture-booth, smart-mirror — i.e. **all the voice demos are on the board we don't have.**

---

## 7. GStreamer on UNO Q — our home turf

**What's on the image / in the brick containers** [VERIFIED — `containers/python-base/Dockerfile`]:
`libgstreamer1.0-0`, `libgstreamer-plugins-base1.0-0` (Qualcomm-patched .deb),
`gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-base-apps`, **`gstreamer1.0-libcamera`**,
**`libcamera0.7` + IPA**, **`qtiqmmfsrc` .deb**, `gir1.2-gstreamer-1.0` + PyGObject (so
`Gst.parse_launch` from Python works), OpenCV built **with the GStreamer backend**
(`cv2.CAP_GSTREAMER`). Note: `libgstvpx.so`, `libvpx9`, `libx265-215` are deliberately **removed**,
and `libegl-mesa0`/`mesa-libgallium`/`libllvm19` are **purged inside the container** (so no Mesa
OpenCL in-container — GPU inference needs the vendor stack / host paths; **verify**).

Real pipelines Arduino ships:
```bash
# CSICamera (CAMSS path)
libcamerasrc camera-name=<name> ! video/x-raw,width=W,height=H,framerate=F/1 \
  ! videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=1
# CSICamera (CamX path)  -> source element is: qtiqmmfsrc camera=<id>
# aihub runner default    -> v4l2src device=/dev/video0 ! videoconvert ! videoscale
#                            ! video/x-raw,format=RGB,width=W,height=H
#                            ! queue max-size-buffers=1 leaky=downstream ! appsink name=appsink
# ei-models-runner (video_objectdetection brick):
#   --gst-source "tcpserversrc host=0.0.0.0 port=5050 ! jpegdec"  --preview-original-resolution
```
⚠️ **Performance smell we can exploit**: the stock `video_objectdetection` brick has Python capture
the frame, **JPEG-encode it, push over TCP:5050 to the container, which `jpegdec`s it again**.
That's two codec passes + a socket hop per frame, on 4 A53s. **Writing our own custom brick with a
single GStreamer pipeline (`v4l2src ! jpegdec/videoconvert ! tee ! appsink`) is a legitimate,
easily-measured optimisation** — "we removed a redundant JPEG encode/decode round-trip and cut
per-frame CPU by X %" is exactly the kind of concrete number the 40-pt criterion rewards.

**Optional accelerator — `edgeimpulse/gst-plugins-edgeimpulse`** (Rust): elements
`edgeimpulsevideoinfer`, **`edgeimpulseaudioinfer`**, `edgeimpulseoverlay`,
**`edgeimpulsecontinueif`** (drop/pass on `detection_count >= 1`, `anomaly_score > 0.5`, with
severity `rules`), **`edgeimpulsecrop`** (1→N per-detection crops), `edgeimpulseocr`,
`edgeimpulsesink` (upload to EI ingestion). Emits `edge-impulse-inference-result` bus messages and
`VideoRegionOfInterestMeta` (interoperable with **Qualcomm IM SDK `qtioverlay`**).
This gives us **declarative two-stage cascaded inference inside one pipeline** — exactly the
"cheap gate → expensive model on crops only" pattern we want. Caveat: **no binary releases; build
from source** (Rust/gst-plugin). Time-box it; have the Python fallback ready. **[VERIFIED]**

---

## 8. Realistic on-device perception for QNet Home

### 8.1 Numbers we actually have

| Workload | Measurement | Source | Status |
|---|---|---|---|
| YOLOv5-**Pico** (EI), 640×480 capture, UNO Q CPU | **~58 ms/inference ≈ 17 inferences/s** | Foundries.io "Elf Detector" pt.4 | **[REPORTED]** |
| face-det-lite (Qualcomm AI Hub) UNO Q vs Ventuno | **320×240** (UNO Q) vs **640×480 + QNN** (Ventuno) — same 17 MB model | Arduino model manifest | **[VERIFIED]** |
| YOLOX-Nano 416×416 (stock OOTB detector) | **no published number**; ~2–4× the MACs of YOLOv5-Pico ⇒ **~150–300 ms ⇒ 3–7 fps** | — | **[ESTIMATE — measure]** |
| FOMO (MobileNetV2 0.35, 96×96/160×160) | **no published number**; typical A53-class ⇒ **10–30 ms ⇒ 30+ fps** | — | **[ESTIMATE — measure]** |
| MoveNet-Lightning INT8 192×192 / BlazePose-lite, CPU | **no published number**; ⇒ **~70–140 ms ⇒ 7–14 fps** | — | **[ESTIMATE — measure]** |
| Adreno 702 GPU delegate speed-up vs 4×A53 | EI ships a UNO Q **(GPU)** target; typical conv-net gain **1.5–3×**, with fixed per-inference overhead that can *hurt* tiny models | — | **[ESTIMATE — measure both]** |
| `Qwen3.5-0.8B-Q4_0` on 4×A53 @2 GHz, llama.cpp Q4_0 | **no published number**; ⇒ **~4–8 tok/s decode**, prompt-processing several hundred ms/100 tok | — | **[ESTIMATE — measure]** |
| Whole-CPU power at load | CPU rail Dhrystone **1.5 W**; board total with Wi-Fi + USB webcam ⇒ **~3–6 W** | QRB2210 DS + inference | **[VERIFIED / ESTIMATE]** |

**Nobody has published UNO Q power, thermal, or Geekbench numbers.** That is an *opportunity*: bring a
USB-C power meter to the hackathon and be the first to show measured **mJ per inference** and
**mJ per event** on this board. Judges score "energy efficiency" explicitly, and a measured
number from a device nobody has measured is memorable.

### 8.2 Recommended fall-detection stack — **do NOT do pose estimation as the primary detector**

Full-frame pose estimation on 4×A53 with no NPU will land at single-digit-to-low-teens FPS, eat
the whole CPU (starving the LLM/audio/web-UI containers on a 2 GB board), and is the thing most
likely to blow up on demo day. Use a **three-stage cascade** instead — this is *also* the better
architecture story:

**Stage 0 — MCU always-on gate (STM32U585 / Zephyr, ~mW).**
Analog mic module (MAX9814/MAX4466) → `A0` (14-bit ADC is Zephyr-supported on `arduino_uno_q`) →
compute a 20–50 ms RMS envelope + a short-window peak/median ratio on the M33 → on threshold,
`Bridge.notify("loud_event", dbfs)` to Python. Optionally a PIR or a Modulino Distance (VL53L4CD)
on Qwiic as a "someone is in the room" gate. **This is the energy-efficiency headline: the A53
vision pipeline stays idle/at 2 fps until the MCU says something happened.** Measure the delta in
watts with and without — that's your slide.

**Stage 1 — cheap continuous vision gate on the A53s (target ≥15 fps).**
FOMO or `person-classification` (224×224, 14 MB) or a small person-only detector, at 320×240,
`queue max-size-buffers=1 leaky=downstream`. Track person bbox centroid + **aspect ratio (w/h)**
+ vertical position over a 2–3 s ring buffer.
**Fall heuristic that actually works and is defensible:** `w/h` flips from <0.6 (standing) to >1.2
(prone) within <1.5 s **AND** centroid drops >25 % of frame height **AND** the bbox is then
static for >5 s. Combine with the Stage-0 acoustic impact for a joint confidence.

**Stage 2 — burst confirmation, only on a Stage-1 candidate.**
Two mutually-exclusive designs; pick one and say why:
* **(2a) Keep video on the node — privacy-max.** Run the *expensive* model (MoveNet-Lightning /
  BlazePose, or the 416×416 detector, ideally via the EI **GPU** target) for a **3-second burst
  only**, on cropped ROI (`edgeimpulsecrop`). Publish only `{event: fall_suspected, conf: 0.87,
  keypoints: [...], room: "bedroom"}`. Nothing but JSON ever leaves the node. Burst-compute means
  the *average* cost is ~Stage-1 cost, and you can quote both peak and average.
* **(2b) Escalate skeleton/blurred crop to the Copilot+ PC VLM.** Send **pose keypoints only**
  (or a heavily blurred/edge-only 128×128 crop) over the event bus; the PC VLM/SLM adjudicates.
  Preserves "no video leaves the room" *if* you only ship keypoints. This is where the PC's
  Hexagon NPU earns its 40-pt keep.

**Optional hardware ace (if procurable):** a **Seeed MR60FDA2 60 GHz mmWave fall-detection module**
(3×3×3 m coverage, 120° H / 100° V FOV, mount 2.2–3.0 m, static human presence to 6 m,
**UART @115200**, 0.5 W standby / 1.4 W active, `Seeed-mmWave-library`). Camera-free fall detection
that works **in the dark and in a bathroom** — the single strongest answer to "but a camera in a
bedroom is creepy". Sensor-fuse it with vision. Only viable if we can get one in <2 days. **[VERIFIED product]**

### 8.3 Loud-sound / acoustic event detection — very doable
1. **`audio_classification` brick works on UNO Q today**, with a shipped **glass-breaking**
   classifier. Immediate demo value ("the system heard glass break in the kitchen").
2. **Train our own Edge Impulse audio classifier in an afternoon**: classes like
   `background / thud-impact / shout-scream / glass / TV-speech / crying`. EI audio models
   (MFE/MFCC + small 1-D CNN) are cheap enough to run continuously alongside vision. Deploy as
   `.eim` into `/home/arduino/.arduino-bricks/ei-models/`, set `EI_AUDIO_CLASSIFICATION_MODEL`.
   **Remember `chmod +x` the `.eim`** — it's an executable, not a data file.
3. Layer a **dB-SPL/A-weighted level** metric under it (pure DSP, ~free) so the semantic event
   carries `{class, confidence, peak_dbfs, duration_ms}` — richer events make the agent smarter.
4. `keyword_spotting` in parallel for the wake word / "help" / "I'm OK".
5. **All three can be one GStreamer audio pipeline** with a `tee`:
   `alsasrc ! audioconvert ! audioresample ! audio/x-raw,format=S16LE,channels=1,rate=16000 ! tee`
   → level/RMS branch, → `edgeimpulseaudioinfer` (classifier) branch, → KWS branch,
   → optional `appsink` for PCM upload to the PC ASR. **One capture, four consumers, zero extra
   copies** — a textbook GStreamer flex.

### 8.4 What we can claim, honestly, on a slide

| Claim | Basis |
|---|---|
| "Two heterogeneous Snapdragon tiers: Dragonwing QRB2210 edge nodes (no NPU) + Snapdragon X Elite Hexagon NPU hub" | ✅ accurate and *more* interesting than pretending the node has an NPU |
| "Node-side perception at ≥15 fps for the always-on gate, with a burst-mode confirmation model" | ✅ if we measure it (FOMO/person-cls at 320×240) |
| "GPU-offloaded inference on Adreno 702 via Edge Impulse's UNO Q (GPU) target — X ms vs Y ms on CPU" | ✅ measurable in ~1 hour; strongest single technical bullet available on this board |
| "Hardware ISP + Venus H.264 encoder used for the on-device-only ring buffer; CPU never touches encode" | ✅ 1080p30 H.264 + H.265 encode is in the data sheet |
| "MCU-gated always-on sensing: A53 cluster idles until the Cortex-M33 fires; measured N mW → M W transition" | ✅ measurable, and it's the energy-efficiency answer |
| "Only semantic JSON events cross the network — measured B bytes/event vs ~C Mbps for a video stream" | ✅ trivially measurable, extremely quotable (e.g. ~200 B/event vs 2 Mbps) |
| "UNO Q has an NPU / N TOPS" | ❌ **never say this** |
| "On-device Whisper / on-device neural TTS on the UNO Q" | ❌ not with first-party bricks; only via our own container, and unmeasured |

---

## 9. Networking, orchestration, sensors, power

* **Wi-Fi 5 dual-band + BT 5.1**; `nmcli` for provisioning; mDNS (`<boardname>.local`);
  network enable/disable via `arduino-app-cli system network`. **[VERIFIED]**
* **MQTT**: `paho-mqtt ≥2.1.0` available (brick present but `disabled: true` in the UI). Run the
  broker on the Copilot+ PC (Mosquitto) and have nodes publish `qnet/<room>/event`. **[VERIFIED]**
* **MCP**: `mcp_client` brick turns MCP servers into LangChain tools and feeds them to the local
  `llm`. Symmetrically, we can ship a **FastMCP server as a custom brick container on each node**
  so the PC-side agent (OpenClaw) discovers `node.speak()`, `node.arm()`, `node.snapshot_pose()`
  as tools. **This is the cleanest way to make "multi-device orchestration" literal and legible
  to judges.** **[VERIFIED]**
* **WebSocket built-ins**: `WebSocketCamera` (phone → node frames), `Microphone(device="ws://…")`
  (remote PCM in), `RemoteSensor` (JSON/CSV/binary telemetry in). Free multi-device plumbing. **[VERIFIED]**
* **Qwiic / Modulino catalogue** (I²C): Thermo (HS3003), **Distance (VL53L4CD ToF)**, Movement
  (IMU), **Light (ambient/colour/proximity/IR)**, Buttons, Knob, Joystick, **Pixels (8× RGB)**,
  **Buzzer**, **Vibro**, Motors, Latch Relay, LED Matrix, **Hub (8 extra I²C addresses)**,
  Extender (long-distance I²C). **No mmWave / PIR / VOC Modulino exists** — those must be
  third-party Qwiic/Grove/UART modules. **[VERIFIED]**
* **Power**: USB-C 5 V @ ≤3 A, or **VIN 7–24 V**. QRB2210 CPU rail Dhrystone **1.5 W**,
  rock-bottom **10.4 mW**. Whole-board figures are unpublished — **measure with a USB-C meter**.
  Note "operates at reduced performance via standard laptop USB" (i.e. a 500 mA/900 mA port
  will throttle you) → **always use the PD hub / powered supply for demos**. **[VERIFIED + REPORTED]**

---

## 10. Known pain points (from people who actually used it)

* **2 GB is genuinely tight**: "with 2GB RAM running Docker containers, AI models, a web server,
  and your application code, things can get slow" (Tech Explorations). The llama.cpp container
  alone declares `mem_limit: 2500m`. **Use the 4 GB SKU for any node that runs an LLM.** **[REPORTED]**
* **`/home/arduino` ≈ 3.6 GB.** Docker images + `.eim` models + GGUF fill it fast. Use
  `opencv-python-headless`, `pip --no-cache-dir`, `docker system prune -a`, and put venvs on `/opt`. **[VERIFIED]**
* **USB-C hub compatibility is flaky** and OS-dependent (worked on macOS, failed on Linux Mint for
  one reviewer). App Lab on Linux has a known board-selection bug with a forum workaround.
  **Bring 2–3 different PD hubs.** **[REPORTED]**
* Serial output from the sketch **does not appear in App Lab's serial monitor over Wi-Fi**. **[REPORTED]**
* App Lab stability: reviewers report crashes/quirks. Have the `arduino-app-cli` + SSH path
  rehearsed as the demo-day fallback. **[REPORTED]**
* `video_objectdetection` brick's `VIDEO_DEVICE` default is `/dev/video1` = the **Venus decoder**.
  Override to `/dev/video2`. **[VERIFIED]**
* Edge Impulse `.eim` files **must be `chmod +x`**. **[VERIFIED]**
* `edge_impulse_linux` python SDK needs `six`/`pyaudio` mocks in some app layouts; pin
  `edge-impulse-linux==1.2.2`. **[VERIFIED]**

---

## 11. Community / prior art since launch (competitive intel)

| Project | What it is | Why it matters to us |
|---|---|---|
| **Shivay Lamba — "AI Guard"** (Arduino Project Hub + Medium, **2026-04-29**) | Modulino **Distance** proximity gate → UNO Q → **Windows-ARM64 laptop NPU** running MobileFaceNet(128-d)/CavaFace(512-d) via **ONNX Runtime QNN EP** → Modulino **Buzzer**. Comms via **RouterBridge with serial fallback**. Face DB = compressed NumPy, cosine match. | **Closest prior art to our seed idea.** "UNO Q senses, Copilot+ PC NPU infers" is already published. We must lead with the *agentic, multi-room, semantic-event, voice-identity* layer — not the topology. Also: it's a good reference for the ONNX-RT-QNN-EP recipe on our hub. |
| **Foundries.io — "Elf Detector" series (pt.4)** | YOLOv5-Pico via **Edge Impulse Linux SDK `.eim`**, USB cam `/dev/video0` @640×480, OpenCV, Flask MJPEG + SSE, Docker. **~58 ms/inference, ~17 fps**; renders decoupled from inference with "sticky" boxes. | **Our only hard FPS datapoint**, plus the exact "decouple render from inference" trick we should copy. |
| **Tech Explorations** — hands-on + "Person Detector: Bridge, Bricks and Real-Time AI" | MobileNet person classification via `video_imageclassification`, `confidence=0.5`, `debounce=0.5 s`, Bridge → LED matrix. Documents Bridge API and the pain points above. | Best free write-up of Bridge patterns and gotchas. |
| **CircuitDigest** — UNO Q getting-started + face detection | USB webcam + Windows App Lab + Type-C hub; face detector example, confidence slider, "Run at startup". | Confirms the practical USB-hub workflow; no perf numbers. |
| **Edge Impulse repos** | `example-rock-paper-scissors-Arduino-UNO-Q`, `unoq-braccio-sketchbot`, `example-lidar-mapper-edge-impulse`, `ei-unoq-custom-sensor` (ADC custom sensor), `example-arduino-app-lab-accelerometer-data-collection`, `agent-tools/skills/build-arduino-uno-q-app-lab` (a **1181-line UNO Q + App Lab reference** — read it), `gst-plugins-edgeimpulse`. | The `agent-tools` REFERENCE.md is the single densest UNO Q engineering doc in existence. |
| **CNX Software** | Acquisition + UNO Q intro (2025-10-07), 4 GB SKU (2026-01-21), **UNO Q Arcade bundle** (2026-07-22, Qwiic-daisy-chained Modulinos, ~$90). | Board is being pushed as a consumer-ish kit; "arcade bundle" shows Qwiic chaining is a supported pattern. |
| **Arduino VENTUNO Q** (pre-release, mid-2026) | IQ8, 40 TOPS NPU, 16 GB, Wi-Fi 6, 2.5 GbE. Not shipping; kernel patches in flight. | Useful "our architecture scales to this" slide; do **not** assume we'll have one. |

**Notably absent from all prior art:** multi-node/multi-room semantic event buses, pose-based fall
detection on UNO Q, on-device TTS on UNO Q, voice-identity/cloned-voice intervention, and any
agentic tool-calling loop spanning node + PC. **That's our whitespace.**

---

## 12. Concrete recommendations for QNet Home

1. **Insist on 4 GB (ABX00173) nodes.** 2 GB will not hold Docker + vision + audio + web UI + any LLM.
2. **Nodes are sensors, not brains.** No LLM/VLM/ASR/TTS on the UNO Q. Node = GStreamer perception
   + rule/heuristic fusion + `Speaker` playback sink + MCP tool surface. Brain = Copilot+ PC
   (Hexagon NPU) with OpenClaw. That's honest, and it's the architecture judges will respect.
3. **Ship two custom bricks of our own** (both trivially demoable):
   * `qnet-sensor` — one GStreamer pipeline: `v4l2src` + `alsasrc`, `tee`, EI video + audio
     inference, RMS/level, ring-buffer to Venus H.264 (local only), publishes JSON events.
   * `qnet-agentnode` — FastMCP server exposing `speak(pcm|text)`, `get_state()`,
     `snapshot_pose()`, `set_light()`, `arm/disarm()`; plus an MQTT publisher.
4. **Do the Adreno 702 GPU A/B early (hour 3).** Deploy the same EI model as
   "Arduino UNO Q" (CPU) and "Linux Arduino UNO Q (GPU)" and record ms/inference + CPU%. One
   number, huge credibility, and it's the only NPU-adjacent claim the board supports.
5. **Do the MCU-gate energy A/B (hour 6).** USB-C power meter: idle, Stage-1 gate only, full burst.
   Report **mW and mJ/event**. Nobody has published this for UNO Q.
6. **Use `keyword_spotting` on-node + PC-side ASR.** Wake-word ("Hey QNet" / "help") stays local;
   only post-wake 16 kHz PCM crosses the wire; PC does Whisper on the NPU. Two-tier ASR is a
   crisp bandwidth/privacy/energy story.
7. **Speech output = PC synthesizes (cloned voice on NPU) → stream PCM → node `Speaker`.**
   Set `periodsize=480` (30 ms @16 kHz) and `queue_maxsize≈10` for barge-in-capable latency.
   Keep `espeak-ng` on the node as the offline failsafe voice.
8. **Get a USB conference speakerphone per node** (mic + speaker + AEC in one USB device). It
   solves far-field capture, playback, and echo cancellation, and halves your USB port count.
9. **Steal the `mobile-video-generic-object-detection` + `RemoteSensor` pattern** to make the
   Android phone a first-class node (extra camera / caregiver's live-connect endpoint) with
   zero protocol work — cheap way to make the "multi-device" claim four devices deep.
10. **Add `telegram_bot`** for the "parent texts the system from a meeting" flow — it's a shipped
    brick, ~20 lines, and it demos beautifully.
11. **Differentiate hard from the AI-Guard prior art**: multi-room, semantic-event bus with
    measured byte counts, agentic tool-calling with a real tool list, two-way conversation with
    barge-in, consented voice identity, and graceful degradation when the hub is offline
    (node-local rules still fire + espeak). Say out loud that "UNO Q + Copilot+ PC" alone is
    already public — then show what we added.

## 13. First-two-hours verification checklist (things I could not confirm remotely)

- [ ] Does **App Lab run natively on Windows-on-ARM** (Snapdragon X Elite)? If not: SSH + `arduino-app-cli`.
- [ ] `cat /etc/os-release`, `uname -a` — Debian release + kernel version (unpublished anywhere).
- [ ] `gst-inspect-1.0 | wc -l`; is `libcamerasrc` present? `qtiqmmfsrc`? `v4l2h264enc`/`v4l2h265enc` (Venus via V4L2 M2M)?
- [ ] `clinfo` — is **OpenCL** actually available on the host (Adreno vendor driver vs Freedreno/Mesa)?
- [ ] Which `/dev/video*` is the USB cam; does `MJPG` 1280×720 negotiate?
- [ ] `aplay -l` / `arecord -l` — is the **jack** codec (PMIC) exposed as an ALSA card even without a carrier?
- [ ] Measure: FOMO@320×240 fps, person-cls@224 fps, YOLOX-Nano@416 fps, CPU vs GPU `.eim`.
- [ ] Measure: `Qwen3.5-0.8B-Q4_0` tok/s (if we use the node LLM at all).
- [ ] Measure: Bridge `notify()` and `call()` round-trip latency (M33 ↔ A53).
- [ ] Measure: board power at idle / gate / burst with a USB-C meter.
- [ ] Thermals: does it throttle in a closed enclosure at sustained 4-core load? (no data exists)

---

## Sources

**Primary — Qualcomm**
- QRB2210 Data Sheet, 80-30843-1 Rev AE (89 pp): https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7554/QRB2210.pdf · https://docs.qualcomm.com/doc/80-30843-1/80-30843-1.pdf
- QRB2210 product page: https://www.qualcomm.com/internet-of-things/products/q2-series/qrb2210
- Dragonwing QRB2210 Product Brief 87-61720-1 Rev D: https://docs.qualcomm.com/doc/87-61720-1/87-61720-1_REV_D_Qualcomm_Dragonwing_QRB2210_Processor_Product_Brief.pdf
- Robotics RB1 platform (same SoC): https://www.thundercomm.com/product/qualcomm-robotics-rb1-platform/
- Qualcomm Neural Processing / QAIRT SDK overview: https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-10/SNPE_general_overview.html

**Primary — Arduino**
- UNO Q hardware docs: https://docs.arduino.cc/hardware/uno-q/
- UNO Q product page: https://www.arduino.cc/product-uno-q/ · Store: https://store-usa.arduino.cc/products/uno-q
- **Full pinout PDF (rev 2026-02-17, JMISC/JMEDIA pin lists)**: https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf
- Datasheet PDF: https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf
- App Lab docs: https://docs.arduino.cc/software/app-lab/ · Bricks: https://docs.arduino.cc/software/app-lab/bricks/about-bricks · https://docs.arduino.cc/software/app-lab/bricks/use-bricks/
- App Lab 0.6 blog: https://blog.arduino.cc/2026/04/06/arduino-app-lab-0-6-more-control-more-bricks-faster-ai/
- App Lab 0.7 (Custom Bricks) blog: https://blog.arduino.cc/2026/04/29/arduino-app-lab-0-7-custom-bricks-are-here/
- App Lab releases (0.9.0, 2026-07-10): https://github.com/arduino/arduino-app-lab/releases/tag/al-0.9.0 · repo: https://github.com/arduino/arduino-app-lab
- **`arduino/app-bricks-py`** (brick configs, `models/models-list.yaml`, container Dockerfiles, camera/mic/speaker peripherals): https://github.com/arduino/app-bricks-py
- **`arduino/app-bricks-examples`**: https://github.com/arduino/app-bricks-examples
- `arduino/arduino-app-cli`: https://github.com/arduino/arduino-app-cli
- VENTUNO Q: https://www.arduino.cc/product-ventuno-q
- Modulino catalogue: https://store.arduino.cc/collections/modulino
- Zephyr upstream board support: https://github.com/zephyrproject-rtos/zephyr/tree/main/boards/arduino/uno_q

**Edge Impulse**
- Run Arduino App Lab: https://docs.edgeimpulse.com/hardware/deployments/run-arduino-app-lab
- UNO Q board page (Adreno 702, GPU accel, GStreamer dependency): https://docs.edgeimpulse.com/hardware/boards/arduino-uno-q
- **`agent-tools` UNO Q + App Lab reference (1181 lines)**: https://github.com/edgeimpulse/agent-tools/blob/main/skills/build-arduino-uno-q-app-lab/references/REFERENCE.md
- **GStreamer plugins**: https://github.com/edgeimpulse/gst-plugins-edgeimpulse · docs: https://edgeimpulse.github.io/gst-plugins-edgeimpulse/
- Examples: https://github.com/edgeimpulse/example-rock-paper-scissors-Arduino-UNO-Q · https://github.com/edgeimpulse/unoq-braccio-sketchbot · https://github.com/edgeimpulse/ei-unoq-custom-sensor · https://github.com/edgeimpulse/mwc-workshop-uno-q-updater
- QNN hardware acceleration: https://github.com/edgeimpulse/qnn-hardware-acceleration

**Third-party measurements & write-ups**
- Foundries.io, Elf Detector pt.4 — **17 fps / 58 ms YOLOv5-Pico**: https://www.foundries.io/insights/blog/elf-detector-real-time-object-detection/
- Tech Explorations hands-on: https://techexplorations.com/blog/arduino/arduino-uno-q-hands-on-with-arduinos-dual-brain-ai-board/
- Tech Explorations Person Detector / Bridge: https://techexplorations.com/blog/arduino/arduino-uno-q-person-detector-bridge-bricks-and-real-time-ai/
- CircuitDigest getting-started + face detection: https://circuitdigest.com/tutorial/getting-started-with-arduino-uno-q-beginners-guide · https://circuitdigest.blogspot.com/2026/04/arduino-uno-q-face-detection-project.html
- LinuxGizmos spec write-up: https://linuxgizmos.com/arduino-uno-q-combines-qualcomm-dragonwing-qrb2210-and-stm32-mcu/
- CNX Software: acquisition + launch https://www.cnx-software.com/2025/10/07/qualcomm-acquires-arduino-introduces-arduino-uno-q-dual-brain-sbc/ · 4 GB SKU https://www.cnx-software.com/2026/01/21/arduino-uno-q-4gb-board-with-4gb-ram-32gb-storage-available-59/ · Arcade bundle https://www.cnx-software.com/2026/07/22/arduino-uno-q-arcade-bundle-lets-you-build-a-custom-retro-gaming-console/
- SBCwiki, Ventuno Q first look + Geekbench: https://sbcwiki.com/news/articles/arduino-ventuno-q-first-look-ew26/
- Supekkupuru UNO Q spec review: https://supekkupuru.page/en/blog/2025/12/arduino-uno-q
- Hackster, Running ML/AI on Arduino UNO Q: https://www.hackster.io/vsupacha/running-ml-ai-on-arduino-uno-q-59ff07 *(403 to automated fetch; open in a browser)*
- **Prior art — Shivay Lamba AI Guard**: https://projecthub.arduino.cc/shivaylamba/ai-guard-demo-with-arduino-uno-q-modulino-sensors-and-local-npu-face-recognition-dcfcfe · https://shivaylamba.medium.com/building-a-local-ai-face-recognition-demo-with-arduino-uno-q-modulino-and-a-laptop-npu-b2a5f9ed8a3f · https://github.com/shivaylamba/cavaface-detection-arduino-unoq-npu
- Chips and Cheese on Hexagon DSP/NPU lineage: https://chipsandcheese.com/p/qualcomms-hexagon-dsp-and-now-npu

**Optional sensor**
- Seeed MR60FDA2 60 GHz mmWave fall detection: https://wiki.seeedstudio.com/getting_started_with_mr60fda2_mmwave_kit/ · library https://github.com/Love4yzp/Seeed-mmWave-library
