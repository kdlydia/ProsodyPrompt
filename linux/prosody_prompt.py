#!/usr/bin/env python3
"""ProsodyPrompt — full loop demo.

  WAV  →  SpeechPrint (pYIN + Xu1999)  →  symbolic prosody tier
       →  PSOLA resynthesis  →  new WAV with transferred prosody

Usage
-----
# Extract prosody from a recording and print the symbolic tier:
python prosody_prompt.py analyse recording.wav

# Transfer the prosody of source.wav onto the phoneme content of target.wav:
python prosody_prompt.py transfer --source source.wav --target target.wav

# Apply a prosody specification string to a WAV file:
# (raises pitch +2ST on accented syllables, lowers non-prominent ones)
python prosody_prompt.py apply recording.wav --spec "*‾// ‾ _ ‾\\\\ *‾/"

The transfer mode is the key demo: same words, different prosody.
Take two recordings of "MARY flew to Milan" and "Mary flew to MILAN",
swap their F0 contours — the semantic focus shifts.
"""

from __future__ import annotations
import math, sys, argparse
from pathlib import Path

# ── check parselmouth ─────────────────────────────────────────────────────────
try:
    import parselmouth
    from parselmouth.praat import call
except ImportError:
    print("parselmouth not found. Install: pip install --break-system-packages parselmouth")
    sys.exit(1)

try:
    import librosa
    import numpy as np
except ImportError:
    print("librosa not found. Install: pip install librosa")
    sys.exit(1)


# ── pYIN + Xu(1999) ───────────────────────────────────────────────────────────
def extract_f0_pyin(wav_path: Path, fmin=65.0, fmax=500.0):
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    scan = y[:int(20 * sr)]
    f0r, vf, _ = librosa.pyin(scan, fmin=65, fmax=500, sr=sr,
                               frame_length=2048, hop_length=256)
    voiced = f0r[vf & ~np.isnan(f0r)] if vf is not None else np.array([])
    if len(voiced) > 10:
        med = float(np.median(voiced))
        fmin = max(50.0, med * 0.5)
        fmax = min(600.0, med * 2.5)

    f0r, vf, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                               frame_length=2048, hop_length=256)
    hop = 256
    times = librosa.frames_to_time(range(len(f0r)), sr=sr, hop_length=hop)
    f0 = np.where(vf & ~np.isnan(f0r), f0r, 0.0)
    return times, f0, y, sr


def xu1999_trim(vals):
    import statistics
    voiced = [v for v in vals if v and v > 0]
    if len(voiced) < 2:
        return list(vals)
    med = statistics.median(voiced)
    def st(a, b):
        return 12 * math.log2(b/a) if a > 0 and b > 0 else None
    tr = []
    for v in vals:
        if not v or v <= 0:
            tr.append(v); continue
        dev = abs(st(med, v) or 0)
        if dev <= 12:
            tr.append(v)
        else:
            cands = [v*2, v/2]
            best = min(cands, key=lambda c: abs(st(med,c) or float("inf")))
            tr.append(best if abs(st(med,best) or 0) < 12 else None)
    n, sm = len(tr), list(tr)
    for i in range(1, n-1):
        a, b, c = tr[i-1], tr[i], tr[i+1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            sm[i] = (a + 2*b + c) / 4
    return sm


def label_syllable(f0_pts, nbr_f0_mean, rec_std):
    from statistics import median
    voiced = [v for v in f0_pts if v and v > 0]
    if not voiced:
        return "?"
    f0_mean = sum(voiced) / len(voiced)
    onset  = next((v for v in f0_pts if v), None)
    offset = next((v for v in reversed(f0_pts) if v), None)
    wthr = max(0.5, 0.35 * rec_std)
    sthr = max(wthr * 2.5, 2.0)

    mv = 12 * math.log2(offset/onset) if onset and offset and onset > 0 and offset > 0 else None

    if mv is None:
        direction = ""
    elif mv >= wthr:
        direction = "//" if abs(mv) >= sthr else "/"
    elif mv <= -wthr:
        direction = "\\\\" if abs(mv) >= sthr else "\\"
    else:
        direction = ""

    hst = None
    if nbr_f0_mean and f0_mean:
        hst = 12 * math.log2(f0_mean / nbr_f0_mean) if nbr_f0_mean > 0 else None
    is_high = hst is not None and hst >= 0.8
    is_low  = hst is not None and hst <= -0.8

    if direction == "":
        h = "‾" if is_high else ("_" if is_low else ("‾" if f0_mean and nbr_f0_mean else "?"))
    else:
        h = "‾" if is_high else ("_" if is_low else "")

    return h + direction if h else direction


# ── analyse ───────────────────────────────────────────────────────────────────
def analyse(wav_path: Path):
    print(f"\nAnalysing: {wav_path.name}")
    times, f0, y, sr = extract_f0_pyin(wav_path)

    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        print("No voiced frames detected.")
        return

    print(f"  Duration   : {len(y)/sr:.2f}s")
    print(f"  Pitch range: {voiced.min():.0f} Hz - {voiced.max():.0f} Hz")
    print(f"  Median F0  : {float(np.median(voiced)):.1f} Hz")
    print(f"  Voiced     : {len(voiced)} / {len(f0)} frames ({100*len(voiced)/len(f0):.1f}%)")

    # Quick utterance-level prosody sketch (50ms windows)
    window = 0.05
    total = len(y) / sr
    t = 0.0
    symbols = []
    f0_means = []
    import statistics as stats

    windows = []
    while t < total - window:
        idx = np.searchsorted(times, t)
        idx2 = np.searchsorted(times, t + window)
        chunk = [float(v) for v in f0[idx:idx2] if v > 0]
        if chunk:
            windows.append(sum(chunk)/len(chunk))
        else:
            windows.append(None)
        t += window

    voiced_windows = [w for w in windows if w]
    if len(voiced_windows) < 2:
        print("  Not enough voiced windows for prosody analysis.")
        return

    rec_std = stats.stdev(voiced_windows)
    rec_med = stats.median(voiced_windows)

    print(f"\n  Pitch sketch (50ms windows):")
    print(f"  {'Time':>6}  {'F0':>6}  Rel")
    for i, (w, t_) in enumerate(zip(windows, np.arange(0, total-window, window))):
        if w is None:
            print(f"  {t_:6.2f}s  {'   --':>6}")
        else:
            st_from_med = 12 * math.log2(w / rec_med) if rec_med > 0 else 0
            bar = int(st_from_med)
            marker = "▲" if bar > 1 else ("▼" if bar < -1 else "─")
            print(f"  {t_:6.2f}s  {w:6.1f}Hz  {marker}")


# ── transfer ──────────────────────────────────────────────────────────────────
def transfer(source_path: Path, target_path: Path, output_path: Path | None = None):
    """Transfer the F0 contour of source onto the phonemes of target using PSOLA."""
    if output_path is None:
        output_path = target_path.parent / f"{target_path.stem}_prosody_from_{source_path.stem}.wav"

    print(f"\nProsody transfer")
    print(f"  Source (prosody donor) : {source_path.name}")
    print(f"  Target (phoneme donor) : {target_path.name}")
    print(f"  Output                 : {output_path.name}")

    # Load both with parselmouth
    src_snd = parselmouth.Sound(str(source_path))
    tgt_snd = parselmouth.Sound(str(target_path))

    # Extract manipulation objects (PSOLA)
    src_manip = call(src_snd, "To Manipulation", 0.01, 75, 600)
    tgt_manip = call(tgt_snd, "To Manipulation", 0.01, 75, 600)

    # Extract pitch tier from source
    src_pitch_tier = call(src_manip, "Extract pitch tier")

    # Scale source pitch tier to span of target duration
    src_dur = src_snd.duration
    tgt_dur = tgt_snd.duration
    scale = tgt_dur / src_dur

    # Create new pitch tier aligned to target duration
    new_pitch_tier = call("Create PitchTier", "transferred", 0, tgt_dur)

    # Get all points from source pitch tier
    n_points = call(src_pitch_tier, "Get number of points")
    for i in range(1, n_points + 1):
        t = call(src_pitch_tier, "Get time from index", i)
        f = call(src_pitch_tier, "Get value at index", i)
        new_t = t * scale
        if 0 <= new_t <= tgt_dur:
            call(new_pitch_tier, "Add point", new_t, f)

    # Replace target's pitch tier with scaled source pitch tier
    call([tgt_manip, new_pitch_tier], "Replace pitch tier")

    # Resynthesize
    result = call(tgt_manip, "Get resynthesis (overlap-add)")
    result.save(str(output_path), "WAV")
    print(f"  Written: {output_path}")
    return output_path


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="ProsodyPrompt — analyse and transfer prosody between recordings."
    )
    sub = parser.add_subparsers(dest="command")

    p_analyse = sub.add_parser("analyse", help="Extract and display prosody from a WAV")
    p_analyse.add_argument("wav", type=Path)

    p_transfer = sub.add_parser("transfer",
        help="Transfer prosody (F0) of source onto phoneme content of target")
    p_transfer.add_argument("--source", type=Path, required=True,
                            help="WAV file to take prosody FROM")
    p_transfer.add_argument("--target", type=Path, required=True,
                            help="WAV file to keep phonemes FROM")
    p_transfer.add_argument("--output", type=Path, default=None)

    args = parser.parse_args()

    if args.command == "analyse":
        analyse(args.wav)
    elif args.command == "transfer":
        out = transfer(args.source, args.target, args.output)
        print(f"\nDone. Open in Praat or play with:")
        print(f"  aplay {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
