# The Android Phone's Role in QNet Home

Research date: **2026-08-03**. Author: research agent. Scope: what the Android device should do, what it should *not* do, and a ~1.5-person-day build plan.

> **Note on method:** the session's WebSearch budget was exhausted before this task started, so everything below is verified by direct WebFetch of primary sources (Android developer docs, Qualcomm `quic/ai-hub-apps`, Maven Central, ntfy docs, GStreamer docs) plus the QAI Hub performance YAMLs already cached in `research/tech/_cache/`. Every number is cited. Nothing here is from memory alone.

---

## 0. TL;DR — the recommendation

**Build one native Kotlin/Compose APK: the "QNet Companion". It plays four roles, in this priority order:**

| # | Role | Why it wins points | Cost |
|---|---|---|---|
| 1 | **Offline-first caregiver console** — persistent LAN socket to the hub, incident notifications with 3 action buttons, event timeline | Proves the "works with the router unplugged" claim. FCM *cannot* do this. Directly scores Technical (latency, no-cloud) + UX | 4.5 h |
| 2 | **Push-to-talk voice link into the room** — talk to Mom through the kitchen speaker from the notification | The single most emotionally strong demo beat. Half-duplex PTT dodges all the hard AEC/WebRTC work | 2.5 h |
| 3 | **Third sensing node — accelerometer fall detection** (phone in pocket / on nightstand) | Best architecture argument in the whole project: *the same semantic-event schema, from a totally different sensor class, on a different OS.* Also answers "what about the bathroom, where you'd never put a camera?" | 1.5 h |
| 4 | **Parent-texts-the-system** — reply directly inside the notification (RemoteInput), hub speaks it in the parent's cloned voice | Free feature: it's ~30 lines on top of role 1. Best "innovation" moment per minute of work | 0.5 h |

Total ≈ 9–10 h of focused work + 2 h for signing/packaging/README/screenshots ≈ **1.5 days for one person.**

**Explicitly do NOT do:** Flutter/React Native/PWA (§2), a phone-side SLM in the main flow (§6.3), full WebRTC for the phone leg (§5), FCM as the primary notification path (§4).

**One optional stretch (2–3 h, only if ahead):** GenieX on-device LLM on the phone (§6.3) purely to get a second NPU-utilization number for the 40-point criterion.

---

## 1. Ground truth on the .APK requirement

From `judging/final-submission-requirements.md`:

- *"For **compute applications only**: A packaged executable file for windows (.EXE) … A packaged windows app (.MSIX) is also acceptable"*
- *"For **mobile applications only**: A packaged executable file for Android (.APK)"*

**Reading:** QNet Home is a *compute* application (the Copilot+ PC is the hub, and the rules also say the app "must be capable of being successfully installed and run on the Copilot+ PC"). So the **.EXE/.MSIX is mandatory; the .APK is not.**

**But ship the APK anyway.** It is cheap, it is the only way the phone counts as "meaningfully used", and it feeds the 20-point Deployment criterion (two installable artifacts, both documented). Just don't let it drag you into positioning the project as a mobile app — the .EXE remains the primary deliverable and the README must lead with it.

Deliver: `QNetCompanion-release.apk`, signed with a checked-in-to-repo *debug-grade* release keystore (document that it is a hackathon keystore), plus `adb install` instructions and a QR-code-to-download option served by the hub.

---

## 2. Framework decision: native Kotlin + Compose. Not close.

Every one of the four roles above touches an Android API that cross-platform frameworks reach only through a platform channel you'd have to write in Kotlin anyway.

| Option | Verdict | Deciding facts |
|---|---|---|
| **Kotlin + Jetpack Compose** | ✅ **Choose this** | Direct access to `SensorManager`, `AudioRecord`/`AudioTrack`, foreground-service types, `RemoteInput`, `CallStyle`, ML Kit, and GenieX (an Android-only Maven artifact). One `assembleRelease` → APK. |
| Flutter | ❌ | `flutter_foreground_task` 10.0.0 does cover the Android 14 FGS types incl. `connectedDevice`, so notifications are workable — but raw 16 kHz PCM capture/playback, the sensor state machine, and GenieX all require platform channels. You end up writing the Kotlin *plus* the Dart. Only justified if you also needed iOS. You don't. |
| React Native | ❌ | Same argument as Flutter, and worse for low-latency binary audio streaming over a socket. |
| **PWA / web app** | ❌ **Fatal, multiple ways** | (a) Web Push on Android Chrome is delivered via FCM → **cloud dependency**, which destroys the router-unplugged demo. (b) No foreground service → no persistent LAN socket while backgrounded. (c) `getUserMedia` requires a **secure context**, so a page served from `http://192.168.x.x` cannot open the mic — this alone kills the two-way audio role. (d) No APK. (e) Android 17 local-network rules apply to WebView too ("WebView traffic inherits host app's permission state"). |
| ntfy self-hosted client (no custom app) | ⚠️ **Keep as a 45-min fallback** | See §4.3. Genuinely capable — priority 5 + up to 3 action buttons — but it can't do audio, sensors, or a timeline. Use as risk mitigation, not the plan. |

**Project settings to pin on day 1:** `minSdk 31`, `compileSdk 36`, **`targetSdk 36`** (see §3.1 — this is not a cosmetic choice), single module, Compose BOM, OkHttp for WebSocket, Kotlin coroutines.

---

## 3. The Android platform gotchas that will eat your afternoon

These are the four things most likely to silently break the demo. Handle them on day 1.

### 3.1 `ACCESS_LOCAL_NETWORK` — the #1 landmine (target SDK 36, not 37)

Android's Local Network Protections became **mandatory in Android 17 (API 37)**:

| Target SDK | Behavior |
|---|---|
| ≤ 36 | "Local network access implicitly granted via `INTERNET` permission (temporary)" |
| ≥ 37 | "Local network blocked by default; must request `ACCESS_LOCAL_NETWORK`" |

Covered operations include *"outgoing TCP connections to local addresses"*, incoming TCP, all UDP unicast/multicast/broadcast, `NsdManager`, and `.local` resolution. **When denied, TCP connections fail as a plain timeout** — no exception, no log, just a hang. That is exactly the bug you don't want to debug at 2 a.m.

Actions:
- **Set `targetSdk 36`.** It costs nothing at a hackathon and removes the whole class of failure.
- Do **not** declare `ACCESS_LOCAL_NETWORK` — the docs explicitly say apps targeting SDK 36 or lower should *not* declare or request it.
- **Add one line to the README** noting that a production release targeting API 37+ would declare `ACCESS_LOCAL_NETWORK` (in the `NEARBY_DEVICES` group) or use the `DiscoveryRequest.FLAG_SHOW_PICKER` system picker path, which grants access without a broad permission. Mentioning this in the docs is exactly the "commercially ready" signal the 15-point criterion rewards.
- Avoid mDNS/`NsdManager` for pairing anyway — use QR pairing (§4.4). Fewer permissions, better demo.

### 3.2 Foreground service type: use `connectedDevice`, never `dataSync`

Android 15 added a hard cap: **`dataSync` and `mediaProcessing` foreground services get 6 hours total per 24-hour period**, tracked per type, shared across all instances, reset only when the user foregrounds the app. On timeout the system calls `Service.onTimeout()` and you must `stopSelf()` within seconds or eat a `RemoteServiceException`.

`connectedDevice` has **no timeout** and is described in the docs as being for *"interactions with external devices that require a Bluetooth, NFC, IR, USB, or network connection"* — a perfect fit for a socket to a home hub.

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE"/>
<uses-permission android:name="android.permission.CHANGE_NETWORK_STATE"/>  <!-- satisfies the prerequisite -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<uses-permission android:name="android.permission.INTERNET"/>

<service android:name=".HubLinkService"
         android:foregroundServiceType="connectedDevice"
         android:exported="false"/>
```

`connectedDevice` requires **at least one** of: `CHANGE_NETWORK_STATE` / `CHANGE_WIFI_STATE` / `CHANGE_WIFI_MULTICAST_STATE` / `NFC` / `TRANSMIT_IR` in the manifest, **or** runtime `BLUETOOTH_*`/`UWB_RANGING`, **or** a `UsbManager.requestPermission()` call. `CHANGE_NETWORK_STATE` is manifest-only — no runtime prompt. Easiest possible path.

For the fall-detection sensor service, `health` is the semantically correct type (also untimed) and requires either `HIGH_SAMPLING_RATE_SENSORS` in the manifest or runtime `ACTIVITY_RECOGNITION`. Simplest: run sensors inside the *same* `connectedDevice` service and skip the second service entirely.

### 3.3 Full-screen-intent alerts need a setup-wizard step

Android 14 restricted `USE_FULL_SCREEN_INTENT`: *"apps that are allowed to use this permission are limited to those that provide calling and alarms only. The Google Play Store revokes default `USE_FULL_SCREEN_INTENT` permissions for any apps that don't fit this profile"* (deadline May 31, 2024). It stays enabled for apps installed before the user's Android 14 update, and users can toggle it.

For a sideloaded hackathon APK you must assume it is **not** granted. Handle it properly — this is a 15-minute job that reads as polish:

1. Call `NotificationManager.canUseFullScreenIntent()`.
2. If false, in onboarding show "Allow full-screen emergency alerts" and launch `Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT`.
3. Fall back to `IMPORTANCE_HIGH` channel + `setCategory(CATEGORY_ALARM)` heads-up notification, which works regardless.

A fall-alarm app is arguably an "alarm app", so this is a defensible use — say so in the README.

### 3.4 Doze / OEM battery killers

- Request `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` in onboarding (and document it).
- 30-second application-level heartbeat over the WebSocket, with exponential-backoff reconnect (OkHttp does not auto-reconnect; HiveMQ's MQTT client does).
- Document a "set Battery → Unrestricted" step: Samsung/Xiaomi ROMs kill sockets aggressively and this *will* bite you if you leave the phone idle for 30 minutes before the judging slot.

### 3.5 Also on the day-1 checklist

- `POST_NOTIFICATIONS` is a runtime permission on Android 13+ and **applies to the foreground-service notification too**. Request it in the first-run flow before starting the service.
- **First 30 minutes with the actual kit phone**, run:
  ```
  adb shell getprop ro.soc.model
  adb shell getprop ro.product.model
  adb shell getprop ro.build.version.sdk
  adb shell pm list packages | findstr "com.google.android.gms"
  ```
  The last one matters enormously: **if the kit phone is a Qualcomm QRD/reference device without Google Play Services, FCM is impossible** — which turns the local-first design from "nice differentiator" into "the only thing that works". Either way you win, but you need to know before you plan.

---

## 4. Transport + offline-first notifications

### 4.1 Recommended: one WebSocket from the phone to the hub, JSON semantic events

```
UNO Q node ──MQTT/JSON──┐
UNO Q node ──MQTT/JSON──┤──► Hub (X Elite): event bus + agent ──WebSocket/JSON──► Phone
Phone (accel node) ─────┘                                     ◄──binary PCM frames──
```

Why a plain WebSocket to the hub rather than having the phone join the MQTT broker directly:

- **The .EXE stays self-contained.** No Mosquitto install for the judge. (Mosquitto's Windows build is x64 — it would run under emulation on X Elite, which is a smell in a talk about resource utilization.) A WebSocket server inside your hub process is native ARM64 and zero-install. Direct feed into the 20-point Deployment criterion.
- Same socket carries events *and* the binary audio frames (§5) — one connection, one auth token, one reconnect path.
- If the UNO Q nodes already speak MQTT, the hub bridges MQTT ↔ WebSocket. That bridge is 20 lines and is *itself* a good slide: "the hub is the semantic-event broker; every device speaks the schema it's best at."

If you'd rather have the phone speak MQTT for architectural purity, use **HiveMQ MQTT Client `com.hivemq:hivemq-mqtt-client:1.3.17`** (Apache 2.0, MQTT 5 + 3.1.1, WebSocket transport, *"automatic and configurable reconnect handling and message redelivery"*, *"automatic and configurable resubscribe if the session expired"*). **Do not use `eclipse-paho/paho.mqtt.android`** — latest release is 1.1.1, MQTT 3.1.1 only, docs still reference Android SDK 24, no statements about Android 12+/14+ compatibility, and it requires you to also pull in the separate `mqttv3` dependency.

### 4.2 Why FCM cannot be the primary path

FCM requires internet, full stop. It also requires Play Services (see §3.5). And ntfy's own docs describe FCM's timing bluntly: messages *"may arrive with a significant delay (sometimes many minutes, or even hours later)"*. For a fall alert that is disqualifying.

**Design it as: LAN WebSocket primary, FCM as an optional "caregiver is away from home" tier.** If time is short, ship LAN-only and say so proudly — "no cloud in the loop, by design" is a stronger story than a half-working FCM path. Add one honest sentence in the README about the away-from-home tier as future work.

### 4.3 ntfy self-hosted — keep as the 45-minute fallback

If the custom APK is running late, self-hosted ntfy gets you actionable alerts with **zero mobile code**:

- Self-hosted servers use **instant delivery** (a persistent foreground-service connection), *"even when your phone is in doze mode"*, bypassing Firebase entirely. F-Droid builds have no Firebase at all and always use instant delivery.
- `X-Priority: 5` = *"really long vibration bursts, default notification sound with a pop-over notification"*.
- Up to **3 action buttons** per notification. The `http` action is the one you want — it POSTs straight to a hub REST endpoint:
  ```
  X-Actions: http, Acknowledge, http://hub.lan:8080/ack/42, method=POST;
             view, Open live audio, http://hub.lan:8080/listen/42;
             http, Escalate, http://hub.lan:8080/escalate/42, method=POST
  ```
- Server: `ntfy serve`, no cloud dependency, default port 80.
- **Caveat for our hub:** ntfy v2.26.3 (2026-07-20) ships `ntfy_2.26.3_windows_amd64.zip` — **Windows ARM64 is not a published asset.** It will run under x64 emulation on X Elite, or you can `GOOS=windows GOARCH=arm64 go build` from source. Linux arm64 `.deb` *is* published, so a third option is running ntfy on an Arduino UNO Q. All three are slightly awkward — which is another reason to prefer your own WebSocket in the hub.

### 4.4 Pairing: QR code, ~15 minutes, disproportionate payoff

Hub displays a QR containing `qnet://pair?ws=ws://192.168.1.42:8765&token=<random>`. Phone scans with CameraX + ML Kit Barcode Scanning (bundled model = fully offline). Done.

This beats mDNS on every axis: no `NsdManager`, no multicast, no local-network permission questions, and it demos in four seconds. It also gives you the token-based auth story for free ("the phone is cryptographically paired to this home, nothing is discoverable on the network").

---

## 5. Live two-way audio into the home: choose push-to-talk, not WebRTC

### The options, ranked for a 4-day build

| Approach | Effort | Verdict |
|---|---|---|
| **Half-duplex push-to-talk: 16 kHz mono PCM16 over the existing WebSocket** | **~2.5 h** | ✅ **Do this.** |
| Opus via `MediaCodec` over the same socket | +1 h | Opus *encoding* is supported from **Android 10+**. Drops 256 kbps → ~24 kbps. Unnecessary on LAN; nice one-liner for the bandwidth slide if you have spare time. |
| GStreamer `webrtcsink`/`webrtcsrc` + `gst-webrtc-signalling-server` | ~1 day | ⚠️ **Great for the hub ↔ UNO Q leg** (your team's home turf; the rswebrtc plugin ships a signalling server and supports WHIP/LiveKit/Janus/AWS-KVS signallers, and pairs `webrtcsink` + `webrtcsrc` for bidirectional media). **Not worth it for the phone leg.** |
| Browser-based WebRTC client on the phone | trap | ❌ `getUserMedia` needs a secure context. `http://192.168.x.x` is not one. You'd need a real TLS cert on a LAN IP — a rabbit hole. |
| Self-hosted LiveKit | ~4 h + server | ⚠️ `livekit-server --dev` (devkey/secret) with `--bind 0.0.0.0` works on LAN and Windows is supported. But it's a whole extra server to install, which taxes the .EXE story. Only if you decide full-duplex is essential. |

### Why push-to-talk is the *right* answer, not just the cheap one

1. **It eliminates acoustic echo cancellation**, which is the genuinely hard part of full-duplex audio in a room with a loud speaker and an open mic. AEC across a 3-device relay chain is a day-destroyer.
2. **The UX is better for the actual use case.** "Hold to talk to Mom" is a walkie-talkie — instantly legible to a judge, no "can you hear me? — you're breaking up" failure mode on stage.
3. It reuses the existing socket, token, and reconnect logic. Zero new infrastructure.

### Concrete implementation

**Phone → room (talk):**
- `AudioRecord` with `MediaRecorder.AudioSource.VOICE_COMMUNICATION` (this is the source that engages the hardware AEC/NS block), 16 kHz, mono, `ENCODING_PCM_16BIT`.
- 20 ms frames = 320 samples = **640 bytes**; send as WebSocket *binary* frames with a 4-byte header (`streamId`, `seq`). 32 KB/s.
- Hub receives → relays to the target UNO Q node → GStreamer `appsrc ! audioconvert ! audioresample ! autoaudiosink` (or straight to ALSA).

**Room → phone (listen):**
- UNO Q mic → hub → same socket → `AudioTrack` with `AudioAttributes.USAGE_VOICE_COMMUNICATION`, ~60 ms jitter buffer.

**Latency budget:** 20 ms frame + 60 ms jitter + ~5 ms LAN + hub relay + node playback ≈ **150–250 ms one-way**. Instrument it and put the number on screen (§8) — echo a sequence number back through the loop and show measured round-trip.

**Entry point:** the "Listen"/"Talk" action button on the incident notification opens straight into the PTT screen. If you want the premium version, try `NotificationCompat.CallStyle.forIncomingCall(...)` (API 31+) so a fall alert arrives looking like an incoming call with Answer/Decline. Budget **30 minutes max** for that experiment — CallStyle wants to be tied to an ongoing call and may need FGS type `phoneCall`/`MANAGE_OWN_CALLS` to render correctly; if it fights you, fall back to `IMPORTANCE_HIGH` + `CATEGORY_ALARM` + three plain actions, which looks fine.

**"Call 911" button:** use `Intent.ACTION_DIAL` with a pre-filled number, **not `ACTION_CALL`**. No `CALL_PHONE` permission needed, the user confirms the dial, and it's the responsible design. **For the demo, wire it to a teammate's number, and say on stage that you did** — judges notice that kind of care.

---

## 6. Should the phone also be a sensing / inference node?

### 6.1 ✅ YES — accelerometer fall detection. This is the best 1.5 hours in the whole mobile scope.

The strategic value is not the detector. It's that **a second, completely different sensor class, on a different OS, publishes the identical semantic event onto the same bus** — which is the literal thesis of the project ("swap the sensing component → new scenario, same architecture"). And it answers the question a smart judge *will* ask: *"cameras in every room? what about the bathroom?"* Answer: the bathroom doesn't get a camera, it gets the phone in the person's pocket, and the hub can't tell the difference because the event schema is the same.

Sensors are all available with `_WAKE_UP` variants that function while the device sleeps, plus batching support:
`TYPE_ACCELEROMETER`, `TYPE_LINEAR_ACCELERATION`, `TYPE_GRAVITY`, `TYPE_SIGNIFICANT_MOTION`, `TYPE_ROTATION_VECTOR`, `TYPE_STEP_DETECTOR`.

**State machine (classic free-fall → impact → posture → inactivity; tune the constants on your own bodies):**

| Stage | Condition |
|---|---|
| 1. Free-fall | `|a| < 3 m/s²` sustained ≥ 80 ms (`TYPE_ACCELEROMETER` @ 50 Hz) |
| 2. Impact | `|a| > 25 m/s²` (≈2.5 g) within 800 ms of stage 1 |
| 3. Posture change | `TYPE_GRAVITY` / `TYPE_ROTATION_VECTOR` shows vertical → horizontal |
| 4. Inactivity | `| |a| − 9.81 | < 1.5 m/s²` for ≥ 8 s |
| → | Publish `{"type":"fall_suspected","source":"phone.accel","confidence":0.x,"ts":...}` |

**Include the 10-second cancel countdown** on the phone ("Are you OK? — I'm fine") before escalating. This is what Apple Watch and Pixel do, it's the honest answer to false positives, and it demonstrates product maturity for ~20 lines of code. Use `TYPE_SIGNIFICANT_MOTION` as a cheap on-body gate so a phone sitting on a table doesn't trigger.

Use `TYPE_ACCELEROMETER` at `SENSOR_DELAY_GAME` (~50 Hz) — that's plenty, and low power. Report the measured CPU cost; it should be fractions of a percent, which is itself a good energy-efficiency data point.

### 6.2 ⚠️ MAYBE — phone as bedside voice terminal (on-device STT)

If you want the phone to *listen*, you have two nearly-free options and one expensive one:

| Path | Facts | Verdict |
|---|---|---|
| **ML Kit GenAI Speech Recognition** | **Alpha API** (*"no SLA or deprecation policy… changes may be made that break backward compatibility"*). Basic mode: **API 31+**, 15 languages incl. en-US. Streaming from mic or file; file input must be *"raw, headerless 16-bit PCM"*, mono, 16 kHz, fed at real-time rate (~32 KB/s — note this is exactly our PTT format). Advanced high-accuracy mode is **Pixel 10 only** right now. | Cheapest. Alpha status is a demo risk. |
| `SpeechRecognizer.createOnDeviceSpeechRecognizer()` | On-device, offline, API 31+; check availability with `checkRecognitionSupport()`. Depends on an installed language pack. | Safe, boring, free. |
| whisper.cpp Android example | Repo recommends **tiny or base only** on phones; models go in `assets/models`; build depends on the whole whisper.cpp tree; no NPU/GPU acceleration and no streaming in the sample. | ❌ Not worth it — you already have Whisper on the hub NPU. |

**Recommendation: mark this COULD, not SHOULD.** The UNO Q room node already provides the mic. Phone-side STT duplicates capability without strengthening the multi-device story. The one scenario where it *is* worth it: if you want the caregiver to *dictate* the message to be spoken in their cloned voice ("hold to dictate") instead of typing it. That's a 45-minute add on top of PTT and it's a nicer demo than typing. Use `createOnDeviceSpeechRecognizer`, not the alpha API.

### 6.3 ❌ NO (as a main-flow component) — phone-side SLM. But there's a smart 2-hour version.

**The good news: the friction collapsed.** There are now two phone-LLM paths in `quic/ai-hub-apps` (latest release **v0.33.0, 2026-07-21**):

- **`apps/chatapp_android`** — Genie C++ APIs from the QAIRT SDK. Requires a QAIRT SDK install, Docker or Gradle build, model export from AI Hub, `tokenizer.json` sourced from HuggingFace, and hand-copying `.bin` context binaries into `src/main/assets/models/llm/`. Wants Android 15+ and Snapdragon 8 Gen 3 or newer (tested on 8 Elite), and a *"newer meta-build"* for LLM execution. **Half a day, minimum. Skip.**
- **`apps/geniex_chat_android` — GenieX. This is the one.** *"Runs LLMs and VLMs on the Snapdragon NPU, GPU, or CPU through a single pluggable runtime."* The Android binding is a **single Maven Central dependency, `com.qualcomm.qti:geniex-android` (latest 0.3.16)**; the app *"downloads the model you select at runtime from an in-app catalog"* and — the key sentence — ***"no model export or asset copying is required to build and run it."*** Build = open in Android Studio (2024.3.1+), Gradle sync, build APK. NPU on Snapdragon 8 Elite / 8 Elite Gen 5, GPU on Adreno, CPU on arm64-v8a.

Also handy: `pip install qai-hub-apps` then
```
qai-hub-apps list
qai-hub-apps fetch geniex_chat_android --output-dir ~
qai-hub-apps fetch chatapp_android --model <model_id> --chipset qualcomm-snapdragon-8-elite --output-dir ~
```
(v0.33.0 added `--device` as an alternative to `--chipset`.) That gets you a ready-to-build project in minutes.

**Phone-side numbers you can actually quote** (from `research/tech/_cache/`, QAI Hub measured, QAIRT 2.45.0):

| Model / precision | Device | Runtime | tok/s | prefill tok/s | TTFT (min) |
|---|---|---|---|---|---|
| Qwen3-0.6B **w4a16** | Snapdragon 8 Elite QRD | `geniex_qairt` **NPU** | **106.6** | 6490 | **19.7 ms** |
| Qwen3-0.6B w4a16 | 8 Elite Gen 5 QRD | `geniex_qairt` NPU | **119.8** | 8806 | 14.5 ms |
| Qwen3-1.7B w4a16 | 8 Elite QRD | `geniex_qairt` NPU | **53.9** | 1025 | **31.2 ms** |
| Qwen3-1.7B w4a16 | 8 Elite Gen 5 QRD | `geniex_qairt` NPU | 62.0 | 1250 | 25.6 ms |
| Qwen3-1.7B q4_0 | 8 Elite QRD | `geniex_llamacpp` NPU (ctx 4096) | 21.2 | 663 | 193 ms |
| Qwen3-1.7B q4_0 | 8 Elite QRD | `geniex_llamacpp` **CPU** (ctx 4096) | 13.3 | 127 | 1006 ms |
| Llama-3.2-3B w4a16 | 8 Elite QRD | `geniex_qairt` NPU | 30.0 | 1635 | 78.3 ms |

Two things jump out and both are usable on a slide: **w4a16 via QAIRT is ~2.5× faster than q4_0 via llama.cpp on the same NPU** (53.9 vs 21.2 tok/s), and **NPU beats CPU by ~4× on tok/s and ~30× on prefill** (663 vs 127 tok/s prefill). That is a ready-made "right model on the right silicon" argument.

**Verdict: don't put reasoning on the phone in the main flow.** It duplicates the hub's job and muddies the story ("who's the brain?"). Judges reward a *clear* division of labour.

**The smart 2-hour version, if you're ahead:** use GenieX with Qwen3-0.6B w4a16 for exactly one job — **rewriting the caregiver's terse text on-device before it leaves the phone.** Parent types "tell him to stop jumping on the couch"; the phone's NPU turns it into a calm, first-person, age-appropriate line; that goes to the hub, which speaks it in the parent's cloned voice. This:
- gives you a **second NPU-utilization + tok/s number** on a second device for the 40-point criterion,
- keeps the raw text on the phone (privacy story stays intact),
- and at 106 tok/s with 19.7 ms TTFT it is genuinely instant.

Mark it **SHOULD-if-time**, cut without regret.

### 6.4 ❌ NO — phone as a camera node

Do not put a camera on the phone. Even though QAI Hub numbers make it trivially capable (MediaPipe-Pose w8a8 on Galaxy S25 NPU: pose_detector **0.188 ms**, pose_landmark **0.194 ms**, ~9 MB peak; YOLOv11-Pose w8a8_mixed_int16 qnn_dlc **1.74 ms**), it (a) duplicates the UNO Q's role, (b) contradicts "the phone is the *caregiver's remote* / the person's *wearable*", and (c) invites the "so it *is* a camera system" question your whole privacy pitch exists to avoid.

For reference if you ever need phone-side audio/vision: YamNet w8a8 qnn_dlc on S25 NPU **0.095 ms** (~28 MB); Whisper-Tiny NPU encoder **15.25 ms** / decoder **1.57 ms**; Whisper-Base **26.0 / 2.84 ms**; Whisper-Small **70.1 / 8.37 ms**; Zipformer streaming ASR encoder **5.42 ms**. There is also a `voice_ai` runtime appearing alongside `qnn_context_binary` in the AI Hub metrics for Whisper/MeloTTS/Piper — worth a 10-minute poke since it may be a packaged on-device speech pipeline, but it is not documented on the public AI Hub docs pages I could reach, so don't plan around it.

---

## 7. The parent-texts-the-system flow (do this — it's nearly free)

The whole feature lives inside the notification. From the Android docs: `RemoteInput` (API 24+) lets the user type directly into a notification action.

```kotlin
val remoteInput = RemoteInput.Builder("key_reply")
    .setLabel("Say something to Aarav…")
    .build()

val replyAction = NotificationCompat.Action.Builder(
        R.drawable.ic_reply, "Speak to room", replyPendingIntent /* FLAG_MUTABLE */)
    .addRemoteInput(remoteInput)
    .build()
```
Retrieve with `RemoteInput.getResultsFromIntent(intent)?.getCharSequence("key_reply")`, handle in a `BroadcastReceiver`, push over the WebSocket, then **update the same notification ID** to "Spoken in your voice in the Living Room ✓". That closing acknowledgement is what makes it feel like a product.

**Two implementation notes from the docs:** use a **different request code per conversation** in the `PendingIntent` (*"to prevent users from replying to the wrong conversation"*), and handle actions in a `BroadcastReceiver` so you don't have to open the app.

**Make the hub earn its keep here.** Don't relay the text verbatim to TTS — that's a speaking tube, not an agent. The hub's SLM should:
1. rewrite terse parent-speak into a calm, age-appropriate, first-person line,
2. pick the target room from current occupancy (it already knows, from the events),
3. choose the parent's cloned voice,
4. optionally follow up ("did he stop?") from the next few seconds of events, and report back.

That is the difference between a feature and the "agentic multi-device architecture" you're pitching. Use `NotificationCompat.MessagingStyle` for the thread so the notification itself reads as a conversation with the house.

---

## 8. Metrics to instrument on the phone (this is where the 40 points live)

Build a **Diagnostics** tab in the app. It is maybe 90 minutes of Compose and it is the single highest-scoring-per-hour thing on the mobile side, because the rubric literally says *"resource utilization, optimization, latency and performance, and energy efficiency"*.

Show, live:

| Metric | How | Why it scores |
|---|---|---|
| Event → notification-posted latency | hub timestamp in the JSON vs `System.currentTimeMillis()` at post; NTP-sync or measure RTT/2 | Expect **< 50 ms on Wi-Fi**. A hard number beats an adjective. |
| Bytes per semantic event vs. equivalent video | count actual socket bytes; compare against e.g. 2 Mbps ×2 cameras | The killer privacy+efficiency stat: **~300 bytes/event vs ~500 KB/s per camera** — quote the ratio. |
| PTT round-trip audio latency | echo a sequence number through hub → node → back | Proves the real-time claim on stage. |
| Uplink bitrate during PTT | 640 B / 20 ms = **32 KB/s** (or ~24 kbps with Opus) | Shows you thought about the audio codec. |
| Phone battery drain over the demo window | `BatteryManager.BATTERY_PROPERTY_CURRENT_NOW`, and `adb shell dumpsys batterystats` for the writeup | Energy efficiency is an explicit sub-criterion and almost nobody instruments it. |
| Accelerometer node CPU % + sample rate | `/proc/self/stat` delta, or Android Studio profiler screenshot in the README | "A 24/7 fall sensor for <1% of one core." |
| Connection state + reconnect count | service state | Feeds the resilience demo. |
| *(if GenieX ships)* tok/s, TTFT, compute unit | GenieX API | Second NPU on a second device. |

**The demo beat to rehearse:** unplug the router. The phone's notification still lands, the timeline still updates, PTT still works, and the Diagnostics tab shows `WAN: down / Hub link: 12 ms`. Then say the sentence: *"nothing in this demo has touched the internet."* That one moment pays for the entire local-first architecture.

---

## 9. Traps to avoid (summary)

1. **`targetSdk 37`** → LAN sockets silently time out (§3.1). Use 36.
2. **`dataSync` foreground service** → dies after 6 h/24 h on Android 15+ (§3.2). Use `connectedDevice`.
3. **Assuming full-screen intents work** → they don't on a sideloaded APK targeting 14+ (§3.3). Add the onboarding grant step.
4. **A PWA for the phone role** → no background socket, no `getUserMedia` on `http://LAN-IP`, no APK (§2).
5. **FCM as the primary path** → breaks the router-unplug demo, may not even exist on a QRD device (§4.2, §3.5).
6. **WebRTC on the phone leg** → signalling + TLS + AEC rabbit hole. PTT instead (§5).
7. **`ACTION_CALL` for the 911 button** → needs a permission and can actually dial emergency services during a rehearsal. Use `ACTION_DIAL` with a teammate's number (§5).
8. **`paho.mqtt.android`** → stale (1.1.1, MQTT 3.1.1, SDK 24-era). Use HiveMQ 1.3.17 if you go MQTT (§4.1).
9. **A phone camera node** → duplicates the UNO Q and undermines the privacy pitch (§6.4).
10. **Forgetting `POST_NOTIFICATIONS`** → your foreground service notification silently doesn't show on Android 13+ (§3.5).

---

## 10. The 1.5-day build plan (12 focused hours, one person)

| Hours | Task | Done when |
|---|---|---|
| 0.0–0.5 | Device recon (`getprop`, Play Services check, Android version). Create project: Kotlin, Compose, minSdk 31, targetSdk 36. Agree the JSON event schema with the hub owner **in writing**. | `adb install` of a hello-world APK works |
| 0.5–3.0 | `HubLinkService` (`connectedDevice` FGS) + OkHttp WebSocket + heartbeat + backoff reconnect. QR pairing (CameraX + ML Kit Barcode). Permission onboarding (`POST_NOTIFICATIONS`, battery optimization, full-screen intent). | Scan QR → persistent "QNet Home connected" notification |
| 3.0–5.0 | Incident notification: `IMPORTANCE_HIGH` channel, `CATEGORY_ALARM`, full-screen intent w/ fallback, 3 actions (Acknowledge / Listen / Dial). `RemoteInput` reply → hub. Compose timeline screen (`LazyColumn`, backfilled from hub history). | Inject a fake fall event on the hub → phone buzzes, all 4 interactions work |
| 5.0–7.5 | Push-to-talk: `AudioRecord`(VOICE_COMMUNICATION, 16 kHz mono) → 20 ms binary frames → hub → UNO Q; return path via `AudioTrack`. On-screen latency readout. | Hold button on phone, voice comes out of the room speaker, and back |
| 7.5–9.0 | Accelerometer fall node: sensor state machine, on-body gate, 10 s "I'm fine" countdown, publish `fall_suspected` with the same schema as the UNO Q nodes. | Drop the phone onto a cushion → hub agent reacts identically to a camera-detected fall |
| 9.0–10.0 | Diagnostics screen (§8) with the latency / bytes / battery / CPU counters. | Numbers visible and believable on stage |
| 10.0–11.0 | Release signing, `assembleRelease`, APK in repo + hub-served download QR, README section w/ screenshots, one smoke test. | A teammate installs from the README alone, without asking you anything |
| 11.0–12.0 | Buffer. In order of value: ntfy fallback wiring → dictate-instead-of-type (`createOnDeviceSpeechRecognizer`) → `CallStyle` notification experiment. | — |
| *+2–3 h stretch* | GenieX (`com.qualcomm.qti:geniex-android:0.3.16`) Qwen3-0.6B w4a16 on-device rewrite of the caregiver's message, with tok/s + TTFT shown in Diagnostics. | A second NPU number on a second device |

---

## 11. Open questions for the team

1. **What is the actual kit phone?** Everything in §6.3 assumes Snapdragon 8 Elite-class for GenieX NPU support (docs list 8 Elite / 8 Elite Gen 5 for NPU). Check `ro.soc.model` first thing. If it's older than 8 Gen 3, drop the phone-LLM stretch entirely.
2. **Does it have Google Play Services?** Determines whether FCM is even an option and how hard you lean on "local-only by design" (§3.5).
3. **Do the UNO Q nodes speak MQTT or something else?** Decides whether the hub needs the MQTT↔WebSocket bridge (§4.1). Lock the event schema on day 1 — it's the interface between three people's work.
4. **Which device owns the room speaker** — UNO Q or hub? Changes the audio relay topology in §5 (though not the phone-side code).
5. **`voice_ai` runtime**: it shows up in the cached AI Hub metrics for Whisper/MeloTTS/Piper but isn't in the public AI Hub docs. Worth a 10-minute look by whoever owns the hub STT/TTS work; do not plan around it.

---

## Sources

**Android platform (all fetched 2026-08-03)**
- [Foreground service timeouts](https://developer.android.com/develop/background-work/services/fgs/timeout) — Android 15 `dataSync`/`mediaProcessing` 6 h per 24 h; `connectedDevice` untimed
- [Foreground service types and prerequisites](https://developer.android.com/develop/background-work/services/fgs/service-types) — `connectedDevice`, `health`, `specialUse`, `remoteMessaging` permission requirements
- [Android 14 behavior changes](https://developer.android.com/about/versions/14/behavior-changes-14) — `USE_FULL_SCREEN_INTENT` restricted to calling/alarm apps; mandatory FGS types
- [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16) — Local Network Protections opt-in phase, `NEARBY_WIFI_DEVICES` interim
- [Android 17 behavior changes](https://developer.android.com/about/versions/17/behavior-changes-17) — API 37, `ACCESS_LOCAL_NETWORK` mandatory, background audio hardening
- [Local network access permission](https://developer.android.com/privacy-and-security/local-network-permission) — target-SDK table, failure modes (TCP timeout / UDP `EPERM`), `FLAG_SHOW_PICKER` alternative
- [Create a notification](https://developer.android.com/develop/ui/views/notifications/build-notification) — `addAction` (max 3), `RemoteInput` direct reply, `MessagingStyle`, channels, `POST_NOTIFICATIONS`
- [Time-sensitive notifications](https://developer.android.com/develop/ui/views/notifications/time-sensitive) — `USE_FULL_SCREEN_INTENT` manifest usage
- [Sensor reference](https://developer.android.com/reference/android/hardware/Sensor) — accelerometer / gravity / linear-acceleration / significant-motion and `_WAKE_UP` variants
- [Supported media formats](https://developer.android.com/media/platform/supported-formats) — Opus **encoder** support from Android 10; AAC-LC and AMR-WB all versions
- [ML Kit GenAI — Speech Recognition](https://developers.google.com/ml-kit/genai/speech-recognition/android) — **alpha**, basic mode API 31+, 15 languages, 16 kHz mono headerless PCM, advanced mode Pixel 10 only
- [ML Kit GenAI overview](https://developer.android.com/ai/gemini-nano) — AICore, Prompt / Summarize / Rewrite / Proofread / Image-description / Speech APIs
- [SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer) — `createOnDeviceSpeechRecognizer`, `checkRecognitionSupport`, `EXTRA_PREFER_OFFLINE`

**Qualcomm**
- [quic/ai-hub-apps](https://github.com/quic/ai-hub-apps) — app table, BSD-3, Android 11+/API 30+, NPU on 8 Gen 2+; latest release **v0.33.0, 2026-07-21**
- [chatapp_android README](https://raw.githubusercontent.com/quic/ai-hub-apps/main/apps/chatapp_android/README.md) — Genie/QAIRT, Docker build, manual model export, Snapdragon 8 Gen 3+
- [geniex_chat_android README](https://raw.githubusercontent.com/quic/ai-hub-apps/main/apps/geniex_chat_android/README.md) — GenieX pluggable NPU/GPU/CPU runtime, in-app model catalog, *"no model export or asset copying is required"*
- [qai-hub-apps CLI README](https://raw.githubusercontent.com/quic/ai-hub-apps/main/cli/README.md) — `list` / `info` / `fetch --model --chipset --device --output-dir`
- [com.qualcomm.qti:geniex-android on Maven Central](https://central.sonatype.com/artifact/com.qualcomm.qti/geniex-android/versions) — latest **0.3.16**
- [quic/ai-hub-models](https://github.com/quic/ai-hub-models) — 200+ models; QAIRT / LiteRT / ONNX Runtime
- [AI Hub docs](https://workbench.aihub.qualcomm.com/docs/) — supported target runtimes
- Local cache: `research/tech/_cache/*.yaml` — measured per-device metrics (QAIRT 2.45.0) for Snapdragon 8 Elite QRD, 8 Elite Gen 5 QRD, Galaxy S25/S26, X Elite CRD

**Transport / notifications / media**
- [ntfy — subscribe from phone](https://docs.ntfy.sh/subscribe/phone/) — instant delivery vs FCM, F-Droid Firebase-free variant, doze behavior
- [ntfy — publishing](https://docs.ntfy.sh/publish/) — priority 1–5, up to 3 action buttons (`view`/`http`/`broadcast`/`copy`) with syntax, click actions, attachments
- [ntfy — install](https://docs.ntfy.sh/install/) — `ntfy serve`, no cloud dependency, platform support
- [ntfy releases](https://github.com/binwiederhier/ntfy/releases) — v2.26.3 (2026-07-20); Windows asset is **amd64 only**; linux arm64 available
- [eclipse-paho/paho.mqtt.android](https://github.com/eclipse-paho/paho.mqtt.android) — 1.1.1, MQTT 3.1.1, SDK-24-era docs
- [hivemq/hivemq-mqtt-client](https://github.com/hivemq/hivemq-mqtt-client) — 1.3.17, MQTT 5 + 3.1.1, WebSocket, auto-reconnect/resubscribe, Apache 2.0
- [GStreamer rswebrtc plugin](https://gstreamer.freedesktop.org/documentation/rswebrtc/index.html) — `webrtcsink`/`webrtcsrc`, bundled `gst-webrtc-signalling-server`, WHIP/LiveKit/Janus/AWS-KVS signallers
- [LiveKit self-hosting locally](https://docs.livekit.io/home/self-hosting/local/) — `livekit-server --dev`, `--bind 0.0.0.0`, port 7880, Windows supported
- [flutter_foreground_task](https://pub.dev/packages/flutter_foreground_task) — v10.0.0, all Android 14 FGS types, Android 15 `dataSync` 6 h caveat
- [whisper.cpp Android example](https://github.com/ggml-org/whisper.cpp/tree/master/examples/whisper.android) — tiny/base recommended, no documented NPU/GPU path
- [llama.cpp OpenCL/Adreno backend](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md) — Adreno 750/810/830/840, X1-85, X2-90; NDK 26.3; `-DGGML_OPENCL=ON`
