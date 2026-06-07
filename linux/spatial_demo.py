#!/usr/bin/env python3
"""
spatial_demo.py — Latent space ambisonics demo
English (front 0°), Daakie (left -90°), German (right +90°)
Head tracking: OSC from phone, or keyboard arrow keys.
Output: AirPods binaural (device 33).

Keyboard: ← → yaw, ↑ ↓ pitch, q quit
OSC (phone GyrOSC/SensorUDP): send to port 9001
  /head yaw pitch      (degrees)
  /gyrosc/gyro x y z   (radians, GyrOSC default)
"""

import scipy.special
if not hasattr(scipy.special, 'sph_harm'):
    scipy.special.sph_harm = scipy.special.sph_harm_y

import numpy as np, soundfile as sf, sounddevice as sd
import threading, sys, tty, termios
from pathlib import Path
from scipy.signal import resample_poly
import spaudiopy.sph as spsph, spaudiopy.io as spio, spaudiopy.decoder as spdec
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

SR       = 48000
BLOCK    = 2048
AIRPODS  = 'pulse'
OSC_PORT = 9001
SH_ORDER = 1

BASE = Path(__file__).parent
SOURCES = [
    (BASE / 'demo_clips/demo_clip_20s.wav',                               0, 0, 'English  (front)'),
    (BASE / 'doreco_port1286_2017_06_30_Jaklin.wav',                    -90, 0, 'Daakie   (left)'),
    (BASE / ' five GToBI annotated sentences/eine_gelbe_banane.wav',     90, 0, 'German   (right)'),
]

_yaw, _pitch, _lock = 0.0, 0.0, threading.Lock()
_sources, _offsets, _hrirs_nm = [], [], None

def get_ori():
    with _lock: return _yaw, _pitch
def set_ori(y, p):
    global _yaw, _pitch
    with _lock: _yaw, _pitch = float(y), float(p)
def d2r(d): return d * np.pi / 180.0

def load_sources():
    enc = []
    for path, azi, ele, label in SOURCES:
        if not Path(path).exists():
            print(f'  skip: {Path(path).name}'); continue
        audio, sr = sf.read(str(path))
        if audio.ndim > 1: audio = audio[:, 0]
        audio = resample_poly(audio.astype(np.float32), SR, sr) if sr != SR else audio.astype(np.float32)
        Y = spsph.sh_matrix(SH_ORDER, np.array([d2r(azi)]),
                             np.array([np.pi/2 - d2r(ele)]), sh_type='real')
        enc.append((audio[:, None] * Y).T)  # (n_sh, N)
        print(f'  {label}: {len(audio)/SR:.1f}s')
    return enc

def audio_cb(outdata, frames, time_info, status):
    n_sh = (SH_ORDER+1)**2
    mix  = np.zeros((n_sh, frames), dtype=np.float32)
    for i, sig in enumerate(_sources):
        N = sig.shape[1]; s = _offsets[i] % N; e = s + frames
        chunk = sig[:, s:e] if e <= N else np.concatenate([sig[:, s:], sig[:, :e-N]], 1)
        mix += chunk; _offsets[i] = (s + frames) % N
    yaw, pitch = get_ori()
    R   = spsph.sh_rotation_matrix(SH_ORDER, d2r(-yaw), d2r(-pitch), 0.0)
    bin_ = spdec.sh2bin(R @ mix, _hrirs_nm)  # (2, ?)
    out  = np.zeros((frames, 2), dtype=np.float32)
    n    = min(bin_.shape[1], frames)
    out[:n, 0] = bin_[0, :n]; out[:n, 1] = bin_[1, :n]
    outdata[:] = out

def main():
    global _sources, _offsets, _hrirs_nm
    print('\n=== Spatial Language Demo ===')
    _sources  = load_sources()
    if not _sources: return
    _offsets  = [0] * len(_sources)
    _hrirs_nm = spdec.magls_bin(spio.load_hrirs(SR, filename='dummy'), SH_ORDER)
    print('HRTFs loaded (dummy — swap for FABIAN/KEMAR .sofa for real quality)')

    disp = Dispatcher()
    disp.map('/head',        lambda a, *args: set_ori(args[0], args[1] if len(args)>1 else 0))
    disp.map('/gyrosc/gyro', lambda a, x, y, z: set_ori(np.degrees(z), np.degrees(x)))
    try:
        threading.Thread(target=ThreadingOSCUDPServer(('0.0.0.0', OSC_PORT), disp).serve_forever, daemon=True).start()
        print(f'OSC: port {OSC_PORT} — GyrOSC: /gyrosc/gyro, custom: /head yaw pitch')
    except Exception as e: print(f'OSC: {e}')

    print('\nEnglish (front) · Daakie (left) · German (right)')
    print('Keys: ←→ yaw  ↑↓ pitch  q quit\n')
    stream = sd.OutputStream(device=AIRPODS, samplerate=SR, channels=2,
                              blocksize=BLOCK, dtype='float32', callback=audio_cb)
    stream.start()
    old = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            ch = sys.stdin.read(1)
            if ch == 'q': break
            elif ch == '\x1b':
                seq = sys.stdin.read(2)
                yaw, pitch = get_ori()
                if   seq=='[D': yaw   -= 15
                elif seq=='[C': yaw   += 15
                elif seq=='[A': pitch += 10
                elif seq=='[B': pitch -= 10
                set_ori(yaw, pitch)
                print(f'  yaw={yaw:+.0f}°  pitch={pitch:+.0f}°', end='\r')
    except KeyboardInterrupt: pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        stream.stop(); print('\nStopped.')

if __name__ == '__main__': main()
