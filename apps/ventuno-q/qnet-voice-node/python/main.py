# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""QNet combined ASR/TTS/MQTT application for Arduino VENTUNO Q."""

from __future__ import annotations

import atexit
import logging

from arduino.app_bricks.asr import AutomaticSpeechRecognition
from arduino.app_bricks.tts import TextToSpeech
from arduino.app_bricks.web_ui import WebUI
from arduino.app_peripherals.microphone import Microphone
from arduino.app_peripherals.speaker import Speaker
from arduino.app_utils import App

from config import VoiceNodeConfig
from mqtt_transport import MQTTTransport
from speech_backend import ArduinoSpeechBackend
from voice_controller import VoiceController


logging.basicConfig(level=logging.INFO)

config = VoiceNodeConfig.from_env()
microphone = Microphone(device=config.microphone_device)
asr = AutomaticSpeechRecognition(mic=microphone)
# App CLI provisions the default supported model, while this public attribute
# selects any compatible model discovered by the audio-analytics runner. This
# keeps model choice in node configuration and lets float Small/Medium use the
# same ASR/TTS/MQTT application.
asr.model = config.asr_model
asr.language = config.language

# Explicit selection avoids silently using a wrong playback endpoint. For the
# current demo, set QNET_SPEAKER_DEVICE=usb:1 after attaching a USB speaker.
speaker = Speaker(
    device=config.speaker_device,
    sample_rate=Speaker.RATE_44K,
    shared=True,
)
tts = TextToSpeech(speaker=speaker)
ui = WebUI()
transport = MQTTTransport(config)
speech = ArduinoSpeechBackend(asr, tts)
controller = VoiceController(speech=speech, transport=transport, config=config)
transport.set_say_handler(controller.on_tts_command)
transport.set_session_handler(controller.on_session_event)
# The 5 s status heartbeat (B3c) reports the controller's live voice state.
transport.set_state_provider(controller.voice_state)

# B1/R5: the snapshot deliberately carries no raw transcript - this page is
# unauthenticated on the LAN, so only post-gate published text is exposed.
ui.expose_api("GET", "/api/status", controller.status_snapshot)

# On the current Ventuno Q App runtime, user_loop may begin before the audio
# bricks' automatic lifecycle has opened their devices. Start these two bricks
# explicitly so the microphone and speaker are ready before the first ASR turn.
microphone.start()
atexit.register(microphone.stop)
App.start_brick(asr)
App.start_brick(tts)
transport.start()
atexit.register(transport.close)

App.run(user_loop=controller.run_once)
