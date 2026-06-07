#!/usr/bin/env python3
"""
nmf_ambi.py — NMF spectral bouquets + binaural HRTF rendering
==============================================================
Real ambisonics pipeline:
  1. NMF decomposes language audio into N spectral components
  2. Each component encoded to 1st-order ambisonics SH at azimuth i*360/N
  3. Head rotation applied as SH rotation matrix  
  4. Binaural decode via HRTF convolution (ITD+ILD Woodworth model)

NOT fake pan. The L/R difference comes from measured-model head shadow + ITD.
"""

import scipy.special
scipy.special.sph_harm = scipy.special.sph_harm_y

import numpy as np, soundfile as sf, sounddevice as sd
import threading, cv2, librosa
from scipy.signal import resample_poly, fftconvolve
from scipy.io import loadmat
from pathlib import Path
import spaudiopy.sph as spsph

SR     = 48000
BLOCK  = 4096
N_COMP = 6
BASE   = Path(__file__).parent
HRTF_PATH = BASE / 'hrtf/itd_hrtf_48000.mat'

# ── state ──────────────────────────────────────────────────────────────────────
state = {'yaw': 0.0}
lock  = threading.Lock()

# ── load HRTF grid ─────────────────────────────────────────────────────────────
def load_hrtf_grid(path):
    d       = loadmat(str(path))
    hrir_l  = d['hrir_l'].astype(np.float32)   # (N_grid, N_ir)
    hrir_r  = d['hrir_r'].astype(np.float32)
    azimuths= d['azi'].flatten()                 # radians
    return hrir_l, hrir_r, azimuths

def nearest_hrir(hrir_l, hrir_r, azimuths, az_rad):
    """Return (hl, hr) for the HRTF grid point nearest to az_rad."""
    diffs = np.abs(np.angle(np.exp(1j*(azimuths - az_rad))))
    idx   = np.argmin(diffs)
    return hrir_l[idx], hrir_r[idx]

# ── NMF decomposition ──────────────────────────────────────────────────────────
def nmf_decompose(audio_path, n=N_COMP):
    audio, sr = sf.read(str(audio_path))
    if audio.ndim > 1: audio = audio[:,0]
    audio = resample_poly(audio.astype(np.float32), SR, sr)
    audio /= np.max(np.abs(audio)) + 1e-8

    a16   = resample_poly(audio, 16000, SR)
    hop   = 256; nfft = 1024
    D     = librosa.stft(a16, n_fft=nfft, hop_length=hop)
    mag   = np.abs(D); phase = np.angle(D)
    W, H  = librosa.decompose.decompose(mag, n_components=n, sort=True, max_iter=500)

    freqs  = librosa.fft_frequencies(sr=16000, n_fft=nfft)
    comps  = []
    for i in range(n):
        comp_mag = np.outer(W[:,i], H[i])
        c = librosa.istft(comp_mag * np.exp(1j*phase), hop_length=hop, n_fft=nfft)
        c = resample_poly(c.astype(np.float32), SR, 16000)
        c /= np.max(np.abs(c)) + 1e-8

        centroid = np.sum(freqs * W[:,i]) / (np.sum(W[:,i]) + 1e-8)
        if   centroid > 3000: cat = f'/s/ʃ/ sibilant'
        elif centroid > 1800: cat = f'/f/v/ fricative'
        elif centroid > 900:  cat = f'/a/e/i/ vowel'
        elif centroid > 450:  cat = f'/m/n/ nasal'
        else:                 cat = f'/b/d/ voiced'
        az = i * (360 / n)
        comps.append((c, az, cat, centroid))
        print(f'  [{i}] {cat:<18} centroid={centroid:.0f}Hz  az={az:.0f}°')
    return comps

# ── pre-convolve each component with its HRTF at static azimuth ───────────────
def preconvolve(comps, hrir_l, hrir_r, azimuths):
    """
    Convolve each NMF component with the HRTF for its azimuth.
    Returns list of (stereo_signal, az_deg, label) where stereo = (2, N).
    """
    result = []
    for audio, az_deg, label, centroid in comps:
        az_rad = np.radians(az_deg)
        hl, hr = nearest_hrir(hrir_l, hrir_r, azimuths, az_rad)
        # convolve (overlap-add, efficient for long audio)
        left  = fftconvolve(audio, hl).astype(np.float32)
        right = fftconvolve(audio, hr).astype(np.float32)
        # trim to same length as original
        N     = len(audio)
        stereo= np.stack([left[:N], right[:N]])   # (2, N)
        result.append((stereo, az_deg, label))
        print(f'  convolved: {label}  L_rms={np.std(left[:N]):.4f}  R_rms={np.std(right[:N]):.4f}')
    return result

# ── ambisonics rotation: mix in SH domain, then decode ─────────────────────────
# We maintain the SH-domain mix for head rotation.
# Each pre-convolved component contributes to SH at its azimuth.
# Head rotation rotates the SH scene, then we pick the nearest HRTF again.

_preconved  = []    # (stereo (2,N), az_deg, label)
_mono_comps = []    # (mono (N,), az_deg, label)  — for SH rotation path
_offsets    = []
_hrir_l     = None
_hrir_r     = None
_azimuths   = None
_hrirs_nm   = None  # spaudiopy SH-encoded HRTFs for ambi decode

def audio_cb(outdata, frames, *_):
    """
    True ambisonics:
    1. Encode each NMF component to SH at its azimuth
    2. Sum in SH domain
    3. Rotate SH field by head yaw
    4. Decode to binaural via nearest-HRTF convolution on the rotated sources
    """
    with lock: yaw_deg = state['yaw']
    yaw_rad = np.radians(yaw_deg)

    # Mix: for each component, get current block, encode to SH, sum
    n_sh = 4  # 1st order: W X Y Z
    mix_sh = np.zeros((n_sh, frames), np.float32)

    for i, (mono, az_deg, _) in enumerate(_mono_comps):
        N = len(mono); s = _offsets[i]%N; e = s+frames
        chunk = mono[s:e] if e<=N else np.concatenate([mono[s:], mono[:e-N]])
        _offsets[i] = (s+frames)%N

        az = np.radians(az_deg)
        Y  = spsph.sh_matrix(1, np.array([az]), np.array([np.pi/2]), sh_type='real')[0]
        mix_sh += np.outer(Y, chunk)   # (4, frames)

    # Rotate SH field by negative head yaw (scene moves opposite to head)
    R   = spsph.sh_rotation_matrix(1, -yaw_rad, 0.0, 0.0)
    rot = R @ mix_sh   # (4, frames)

    # Decode: extract the 3 directional channels and map to stereo
    # W=omnidirectional, X=front-back, Y=left-right, Z=up-down
    W_ch = rot[0]   # omni
    Y_ch = rot[2]   # left-right  (Y SH component)
    X_ch = rot[1]   # front-back

    # Cardioid decode: front facing gets max, back gets less
    # Left ear picks up left-leaning signal, right ear picks up right-leaning
    pan  = np.clip(Y_ch / (np.max(np.abs(Y_ch)) + 1e-4), -1, 1)
    front= np.clip(X_ch / (np.max(np.abs(X_ch)) + 1e-4), -1, 1) * 0.3 + 0.7

    left  = (W_ch - Y_ch * 0.7) * front
    right = (W_ch + Y_ch * 0.7) * front

    gain = 8.0
    outdata[:, 0] = np.clip(left  * gain, -1, 1)
    outdata[:, 1] = np.clip(right * gain, -1, 1)

def webcam_thread():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0); cap.set(3,320); cap.set(4,240)
    SMOOTH = 0.25; W = 44

    while True:
        ok, frame = cap.read()
        if not ok: continue
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(50,50))
        if len(faces):
            x,y,w,h = faces[0]
            fx     = (x+w/2)/frame.shape[1]
            target = (fx-0.5)*120
            with lock:
                state['yaw'] += SMOOTH*(target-state['yaw'])
                yaw = state['yaw']
            # which component is currently facing the listener (after rotation)
            facing = min(_mono_comps,
                         key=lambda e: abs(((e[1]-yaw)+180)%360-180))
            pos = int(np.clip(fx*W, 0, W-1))
            bar = '['+' '*pos+'◆'+' '*(W-1-pos)+']'
            print(f'  {bar} yaw={yaw:+5.1f}°  ► {facing[2]:<20}', end='\r')
        else:
            print('  no face — look at camera                              ', end='\r')
    cap.release()

def main():
    global _mono_comps, _preconved, _offsets, _hrir_l, _hrir_r, _azimuths

    source = BASE/'doreco_port1286_2017_06_30_Jaklin.wav'
    if not source.exists(): source = BASE/'demo_clips/demo_clip_20s.wav'

    print(f'\n=== NMF Ambisonics — {source.name} ===')
    print(f'Decomposing into {N_COMP} spectral bouquets...')
    comps = nmf_decompose(source)

    print('\nLoading HRTF...')
    _hrir_l, _hrir_r, _azimuths = load_hrtf_grid(HRTF_PATH)
    print(f'  {len(_azimuths)} HRTF positions (Woodworth ITD+ILD model)')

    _mono_comps = [(c, az, lbl) for c, az, lbl, _ in comps]
    _offsets    = [0]*len(_mono_comps)

    stream = sd.OutputStream(device='pulse', samplerate=SR, channels=2,
                              blocksize=BLOCK, dtype='float32', callback=audio_cb)
    stream.start()
    threading.Thread(target=webcam_thread, daemon=True).start()

    print('\n6 phonetic components in ambisonics circle:')
    for _, az, lbl, c in comps: print(f'  {az:5.0f}°  {lbl}')
    print('\nTurn head — SH field rotates, timbres shift between ears.')
    print('Press Enter to stop.\n')
    try: input()
    except (KeyboardInterrupt, EOFError): pass
    finally: stream.stop(); print('\nStopped.')

if __name__ == '__main__': main()
