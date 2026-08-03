import time, torch, soundfile as sf, numpy as np
torch.set_num_threads(12)
TEXT = "Hey buddy, that's too rough. Please stop and come sit with me for a minute."
def bench(label, model, **kw):
    t0=time.time(); wav = model.generate(TEXT, **kw); gen=time.time()-t0
    a = wav.squeeze(0).detach().cpu().numpy() if hasattr(wav,'squeeze') else np.asarray(wav)
    dur=len(a)/model.sr
    print(f"  [{label}] audio={dur:.2f}s  gen={gen:.2f}s  RTF={gen/dur:.3f}  {dur/gen:.2f}x realtime")
    sf.write(f"out/chatterbox_{label}.wav", a, model.sr)
    return gen,dur
try:
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    t0=time.time(); m=ChatterboxTurboTTS.from_pretrained(device="cpu"); print(f"TURBO(350M) load={time.time()-t0:.1f}s sr={m.sr}")
    bench("turbo_warm", m, audio_prompt_path="out/ref_voice.wav")
    bench("turbo_run1", m, audio_prompt_path="out/ref_voice.wav")
    bench("turbo_run2", m, audio_prompt_path="out/ref_voice.wav")
except Exception as e:
    import traceback; print("TURBO FAILED:", type(e).__name__, e); traceback.print_exc()
try:
    from chatterbox.tts import ChatterboxTTS
    t0=time.time(); m=ChatterboxTTS.from_pretrained(device="cpu"); print(f"BASE(500M) load={time.time()-t0:.1f}s sr={m.sr}")
    bench("base_warm", m, audio_prompt_path="out/ref_voice.wav")
    bench("base_run1", m, audio_prompt_path="out/ref_voice.wav")
except Exception as e:
    import traceback; print("BASE FAILED:", type(e).__name__, e); traceback.print_exc()
