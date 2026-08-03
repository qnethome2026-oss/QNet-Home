"""Minimal torchaudio shim for Windows-on-ARM (no torchaudio win_arm64 wheel exists).
Provides only what chatterbox-tts needs: transforms.Resample + compliance.kaldi.fbank."""
import math, torch, torch.nn as nn
from . import compliance
from . import transforms
__version__ = "0.0.0-qnet-shim"
