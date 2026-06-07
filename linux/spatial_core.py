"""Shared spatial audio engine used by webcam_spatial.py and airpods_spatial.py"""
import numpy as np, soundfile as sf, sounddevice as sd
import threading
from pathlib import Path
from scipy.signal import resample_poly, butter, lfilter

SR, BLOCK = 48000, 1024
BASE = Path(__file__).parent

SOURCES = [
    (BASE/'demo_clips/demo_clip_20s.wav',     -1.0, 'English'),
    (BASE/'doreco_port1286_2017_06_30_Jaklin.wav', 1.0, 'Daakie'),
    (BASE/' five GToBI annotated sentences/eine_gelbe_banane.wav', 0.3, 'German'),
]

state  = {'angle': 0.0, 'zoom': 0.8}
lock   = threading.Lock()
sources, offsets = [], []

# low-pass filter for "behind" sources — muffled, clearly different timbre
_b, _a = butter(2, 800/(SR/2), btype='low')
_zi    = {}  # filter states per source

def load():
    global sources, offsets, _zi
    out = []
    for path, base_pan, label in SOURCES:
        if not Path(path).exists():
            print(f'  skip: {Path(path).name}'); continue
        d, sr = sf.read(str(path))
        if d.ndim > 1: d = d[:,0]
        if sr != SR: d = resample_poly(d.astype(np.float32), SR, sr)
        out.append((d.astype(np.float32), base_pan, label))
        print(f'  {label}: {len(d)/SR:.0f}s')
    sources = out
    offsets = [0]*len(out)
    _zi     = {i: np.zeros((max(len(_a),len(_b))-1,)) for i in range(len(out))}

def cb(outdata, frames, *_):
    L = R = np.zeros(frames, np.float32)
    with lock:
        ang = state['angle']
        zm  = state['zoom']

    for i, (sig, base_pan, _) in enumerate(sources):
        N = len(sig); s = offsets[i]%N; e = s+frames
        chunk = sig[s:e] if e<=N else np.concatenate([sig[s:],sig[:e-N]])
        offsets[i] = (s+frames)%N

        # how far is this source from straight ahead (0=front, 1=behind)
        pan_pos   = np.clip(base_pan + ang/40.0, -1.0, 1.0)   # -1=left +1=right
        front_amt = 1.0 - abs(pan_pos)   # 1=in front, 0=hard left/right
        behind    = max(0.0, -front_amt + 0.3)   # only sources near behind

        # apply LPF for distant/behind sources
        if behind > 0.05:
            filtered, _zi[i] = lfilter(_b, _a, chunk, zi=_zi[i])
            chunk = chunk*(1-behind) + filtered*behind

        # volume: loudest when straight ahead, quieter at sides
        vol = (0.4 + 0.6*front_amt) * zm

        # stereo pan (constant power)
        p  = pan_pos
        gl = np.cos((p+1)*np.pi/4)
        gr = np.sin((p+1)*np.pi/4)
        L += chunk * gl * vol
        R += chunk * gr * vol

    outdata[:] = np.stack([np.clip(L,-1,1), np.clip(R,-1,1)], axis=1)

def start_stream():
    stream = sd.OutputStream(device='pulse', samplerate=SR, channels=2,
                              blocksize=BLOCK, dtype='float32', callback=cb)
    stream.start()
    return stream
