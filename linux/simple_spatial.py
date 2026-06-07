#!/usr/bin/env python3
"""simple_spatial.py — stereo pan demo, arrow keys"""
import numpy as np, soundfile as sf, sounddevice as sd
import threading, sys, tty, termios
from pathlib import Path
from scipy.signal import resample_poly

SR, BLOCK = 48000, 1024
BASE = Path(__file__).parent

SOURCES = [
    (BASE / 'demo_clips/demo_clip_20s.wav',
     -1.0, 'English (starts LEFT)'),
    (BASE / 'doreco_port1286_2017_06_30_Jaklin.wav',
      1.0, 'Daakie  (starts RIGHT)'),
    (BASE / ' five GToBI annotated sentences/eine_gelbe_banane.wav',
      0.3, 'German  (starts CENTRE-RIGHT)'),
]

# ── mutable state — no global assignment bugs ─────────────────────────────────
state = {'angle': 0.0, 'zoom': 0.7}
lock  = threading.Lock()

def load():
    out = []
    for path, base_pan, label in SOURCES:
        if not Path(path).exists():
            print(f'  skip (missing): {Path(path).name}')
            continue
        d, sr = sf.read(str(path))
        if d.ndim > 1: d = d[:, 0]
        if sr != SR:
            d = resample_poly(d.astype(np.float32), SR, sr)
        out.append((d.astype(np.float32), base_pan, label))
        print(f'  {label}: {len(d)/SR:.1f}s  base_pan={base_pan:+.1f}')
    return out

def pan_lr(p):          # p ∈ [-1..1] → (L_gain, R_gain), constant power
    p = np.clip(p, -1.0, 1.0)
    return np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)

sources, offsets = [], []

def cb(outdata, frames, *_):
    L = R = np.zeros(frames, np.float32)
    with lock:
        ang = state['angle']
        zm  = state['zoom']
    for i, (sig, base_pan, _) in enumerate(sources):
        N = len(sig); s = offsets[i] % N; e = s + frames
        chunk = sig[s:e] if e <= N else np.concatenate([sig[s:], sig[:e - N]])
        # shift pan by angle: full 180° rotation moves source fully across
        pan   = np.clip(base_pan + ang / 90.0, -1.0, 1.0)
        gl, gr = pan_lr(pan)
        L += chunk * gl * zm
        R += chunk * gr * zm
        offsets[i] = (s + frames) % N
    outdata[:] = np.stack([np.clip(L, -1, 1),
                            np.clip(R, -1, 1)], axis=1)

def main():
    global sources, offsets
    print('\n=== Spatial Language Demo ===')
    sources = load()
    if not sources:
        print('No audio files found.')
        return
    offsets = [0] * len(sources)

    try:
        stream = sd.OutputStream(device='pulse', samplerate=SR, channels=2,
                                  blocksize=BLOCK, dtype='float32', callback=cb)
        stream.start()
    except Exception as e:
        print(f'Audio error: {e}')
        return

    print()
    print('← →  rotate scene (15° per press)')
    print('↑ ↓  louder / quieter')
    print('q    quit')
    print()
    print('TIP: press → many times — English should move from LEFT to RIGHT')
    print()

    old = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            ch = sys.stdin.read(1)
            if ch == 'q':
                break
            elif ch == '\x1b':
                seq = sys.stdin.read(2)
                with lock:
                    if   seq == '[D':   # left arrow
                        state['angle'] -= 15
                        print(f'  ← scene angle={state["angle"]:+.0f}°  '
                              f'(English pan={np.clip(-1+state["angle"]/90,-1,1):+.2f})', end='\r')
                    elif seq == '[C':   # right arrow
                        state['angle'] += 15
                        print(f'  → scene angle={state["angle"]:+.0f}°  '
                              f'(English pan={np.clip(-1+state["angle"]/90,-1,1):+.2f})', end='\r')
                    elif seq == '[A':   # up
                        state['zoom'] = min(2.0, state['zoom'] + 0.1)
                        print(f'  ↑ vol={state["zoom"]:.1f}', end='\r')
                    elif seq == '[B':   # down
                        state['zoom'] = max(0.0, state['zoom'] - 0.1)
                        print(f'  ↓ vol={state["zoom"]:.1f}', end='\r')
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        stream.stop()
        print('\nStopped.')

if __name__ == '__main__':
    main()
