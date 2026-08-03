import time, os, numpy as np, soundfile as sf
os.environ.setdefault("OMP_NUM_THREADS","12")
from kokoro_onnx import Kokoro
TEXT="I noticed a fall in the living room. Are you okay? I can call Sarah for you right now."
LONG=("I'm here with you. I've already let Sarah know and she is calling you now. "
      "Try to stay still and breathe slowly. Help is on the way.")
for name,tag in [("models/kokoro/kokoro-v1.0.int8.onnx","int8"),("models/kokoro/kokoro-v1.0.fp32.onnx","fp32")]:
    t0=time.time(); k=Kokoro(name,"models/kokoro/voices-v1.0.bin"); load=time.time()-t0
    print(f"\n=== kokoro {tag}  load={load:.2f}s  file={os.path.getsize(name)/1e6:.0f}MB")
    try:
        so=k.sess.get_providers(); print("   providers:",so)
    except Exception: pass
    for label,txt in [("short",TEXT),("long",LONG)]:
        k.create(txt, voice="af_heart", speed=1.0, lang="en-us")
        ts=[]
        for _ in range(3):
            t0=time.time(); s,sr=k.create(txt, voice="af_heart", speed=1.0, lang="en-us"); ts.append(time.time()-t0)
        dur=len(s)/sr; best=min(ts)
        print(f"   {label}: audio={dur:.2f}s synth={best*1000:.0f}ms RTF={best/dur:.3f} => {dur/best:.2f}x realtime")
        sf.write(f"out/kokoro_{tag}_{label}.wav", s, sr)
