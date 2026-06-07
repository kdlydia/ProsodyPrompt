#!/usr/bin/env python3
"""
webcam_spatial.py — one language at a time, face it to hear it
Sources at -40° 0° +40° — a gentle head turn switches languages completely.
"""
import numpy as np, soundfile as sf, sounddevice as sd
import threading, cv2
from pathlib import Path
from scipy.signal import resample_poly

SR, BLOCK = 48000, 2048
BASE = Path(__file__).parent

# sources at -40°, 0°, +40° — reachable with a normal head turn
SOURCES = [
    (BASE/'doreco_port1286_2017_06_30_Jaklin.wav',                      -40, 'Daakie'),
    (BASE/'demo_clips/demo_clip_20s.wav',                                  0, 'English'),
    (BASE/' five GToBI annotated sentences/eine_gelbe_banane.wav',       +40, 'German'),
]

state = {'yaw': 0.0}
lock  = threading.Lock()
sources, offsets = [], []

def load():
    out = []
    for path, az, label in SOURCES:
        if not Path(path).exists():
            print(f'  MISSING: {path}'); continue
        d, sr = sf.read(str(path))
        if d.ndim > 1: d = d[:,0]
        if sr != SR: d = resample_poly(d.astype(np.float32), SR, sr)
        # normalise loudness
        peak = np.max(np.abs(d)) + 1e-8
        d = d / peak * 0.85
        out.append((d, az, label))
        print(f'  {label} at {az:+d}°')
    return out

def cb(outdata, frames, *_):
    with lock: yaw = state['yaw']
    out = np.zeros(frames, np.float32)

    for i, (sig, src_az, _) in enumerate(sources):
        N = len(sig); s = offsets[i]%N; e = s+frames
        chunk = sig[s:e] if e<=N else np.concatenate([sig[s:],sig[:e-N]])
        offsets[i] = (s+frames)%N

        # hard spotlight: full vol within ±20°, drops to 0 at ±45°
        diff = abs(((yaw - src_az) + 180) % 360 - 180)
        vol  = max(0.0, 1.0 - diff/25.0)   # linear, very steep
        vol  = vol ** 2                     # square for even harder cutoff
        out += chunk * vol

    # stereo: also hard-pan based on head direction for extra cue
    pan   = np.clip(yaw / 60.0, -1.0, 1.0)
    left  = out * np.cos((pan+1)*np.pi/4)
    right = out * np.sin((pan+1)*np.pi/4)
    stereo = np.stack([np.clip(left*2,-1,1), np.clip(right*2,-1,1)], axis=1)
    outdata[:] = stereo

def webcam_thread():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    SMOOTH = 0.3

    while True:
        ok, frame = cap.read()
        if not ok: continue
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(50,50))

        if len(faces):
            x,y,w,h = faces[0]
            fx = (x + w/2) / frame.shape[1]  # 0=left edge 1=right
            # fx=0.5 → centre → yaw=0 (English)
            # fx>0.5 → turned right → yaw>0 → German  
            # fx<0.5 → turned left  → yaw<0 → Daakie
            target = (fx - 0.5) * 100  # ±50° at screen edges

            with lock:
                state['yaw'] += SMOOTH*(target - state['yaw'])
                yaw = state['yaw']

            # show which source is loudest
            best_label, best_vol = 'none', 0
            for _, src_az, lbl in sources:
                diff = abs(((yaw-src_az)+180)%360-180)
                vol  = max(0.0, 1.0-diff/25.0)**2
                if vol > best_vol:
                    best_vol, best_label = vol, lbl

            # bar
            bar_w = 40
            pos   = int(np.clip((fx)*bar_w, 0, bar_w-1))
            bar   = '[' + ' '*pos + '◆' + ' '*(bar_w-1-pos) + ']'
            print(f'  {bar}  yaw={yaw:+5.1f}°  ► {best_label:<10}  vol={best_vol:.2f}   ',
                  end='\r')
        else:
            print('  no face — look at camera                                ', end='\r')
    cap.release()

def main():
    global sources, offsets
    print('\n=== Spatial Demo ===')
    sources = load()
    if not sources: return
    offsets = [0]*len(sources)

    stream = sd.OutputStream(device='pulse', samplerate=SR, channels=2,
                              blocksize=BLOCK, dtype='float32', callback=cb)
    stream.start()
    threading.Thread(target=webcam_thread, daemon=True).start()

    print()
    print('  CENTRE → English   LEFT → Daakie   RIGHT → German')
    print('  Turn your head slowly — language switches at ±40°')
    print('  Press Enter to quit\n')
    try: input()
    except (KeyboardInterrupt, EOFError): pass
    finally: stream.stop(); print('\nStopped.')

if __name__ == '__main__': main()
