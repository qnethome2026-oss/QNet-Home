import time, numpy as np, torch, soundfile as sf, librosa
torch.set_num_threads(12)
# --- fix the float64 leak: librosa.resample falls back to scipy (float64) without soxr ---
_orig = librosa.resample
def resample32(y, **kw):
    return np.ascontiguousarray(_orig(y, **kw)).astype(np.float32)
librosa.resample = resample32
_origload = librosa.load
def load32(*a, **k):
    y, sr = _origload(*a, **k); return y.astype(np.float32), sr
librosa.load = load32

from chatterbox.tts_turbo import ChatterboxTurboTTS
TEXT = "Hey buddy, that's too rough. Please stop and come sit with me for a minute."
t0=time.time(); m=ChatterboxTurboTTS.from_pretrained(device="cpu")
print(f"TURBO(350M) load={time.time()-t0:.1f}s sr={m.sr}")
for tag in ["warm","run1","run2"]:
    t0=time.time(); wav = m.generate(TEXT, audio_prompt_path="out/ref_voice.wav"); gen=time.time()-t0
    a = wav.squeeze(0).detach().cpu().numpy()
    dur=len(a)/m.sr
    print(f"  [turbo_{tag}] audio={dur:.2f}s gen={gen:.2f}s RTF={gen/dur:.3f} -> {dur/gen:.2f}x realtime")
    sf.write(f"out/chatterbox_turbo_{tag}.wav", a, m.sr)
