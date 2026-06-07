#!/usr/bin/env python3
"""Pitch tracker comparison: Praat (raw) vs Praat (corrected) vs Librosa pyin vs torchcrepe.

Generates 3-5 example plots showing octave errors and corrections.
Saves a comparison table and per-tracker notes to the questionnaire folder.

Usage:
    python pitch_tracker_comparison.py --out OUT_DIR

This script runs on the 5 German GToBI sentences (short, controlled, good for comparison).
"""

from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

VENV_BASE = Path("/home/lydia/School/UPF/testSpeechPrint/SpeechPrint-main/new/linux/.venv")
BASE = Path(__file__).parent
GTOBI_DIR = BASE / " five GToBI annotated sentences"

SENTENCES = [
    "eine_gelbe_banane",
    "einige_melonen",
    "er_sang_die_lieder",
    "er_will_die_rosen_haben",
    "ich_wohne_in_bern",
]

ENGLISH_WAV = BASE / "audio_2026-05-30_19-01-35.wav"
DORECO_WAV  = BASE / "doreco_port1286_2017_06_30_Jaklin.wav"


# ─── Pitch extraction helpers ────────────────────────────────────────────────

def praat_pitch_raw(wav_path: Path, floor=75.0, ceiling=600.0) -> tuple[np.ndarray, np.ndarray]:
    """Extract pitch with default Praat SCC method. Returns (times, f0_hz)."""
    import parselmouth
    snd = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch(pitch_floor=floor, pitch_ceiling=ceiling)
    times = pitch.xs()
    f0 = np.array([pitch.get_value_at_time(t) for t in times])
    f0 = np.where(np.isnan(f0), 0.0, f0)
    return times, f0


def praat_pitch_ac(wav_path: Path, floor=75.0, ceiling=600.0) -> tuple[np.ndarray, np.ndarray]:
    """Praat autocorrelation with octave_jump_cost=0.5 (less octave jumping)."""
    import parselmouth
    snd = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch_ac(
        pitch_floor=floor,
        pitch_ceiling=ceiling,
        octave_jump_cost=0.5,
        very_accurate=True,
    )
    times = pitch.xs()
    f0 = np.array([pitch.get_value_at_time(t) for t in times])
    f0 = np.where(np.isnan(f0), 0.0, f0)
    return times, f0


def praat_pitch_corrected(times: np.ndarray, f0: np.ndarray,
                           spike_thr_st: float = 10.0) -> np.ndarray:
    """Xu (1999) octave-correction applied to a Praat pitch track.

    Steps:
    1. Compute median of voiced frames.
    2. For each frame deviating >spike_thr_st ST from median:
       a. Try f0*2 and f0/2 — pick whichever is closer to the local median.
    3. Recompute median, repeat once.
    4. Triangular smoothing over 3 voiced frames.
    """
    f0c = f0.copy()

    for _pass in range(2):
        voiced_mask = f0c > 30
        voiced_vals = f0c[voiced_mask]
        if len(voiced_vals) < 3:
            break
        med = float(np.median(voiced_vals))

        for i, (t, v) in enumerate(zip(times, f0c)):
            if v < 30:
                continue
            st_dist = 12 * math.log2(v / med) if v > 0 and med > 0 else 0
            if abs(st_dist) > spike_thr_st:
                # Try octave alternatives
                cand_up   = v * 2.0
                cand_down = v / 2.0
                dist_orig = abs(st_dist)
                dist_up   = abs(12 * math.log2(cand_up / med))   if cand_up > 30 and cand_up < 800 else 999
                dist_down = abs(12 * math.log2(cand_down / med)) if cand_down > 30 else 999
                best = min(dist_orig, dist_up, dist_down)
                if best == dist_up:
                    f0c[i] = cand_up
                elif best == dist_down:
                    f0c[i] = cand_down

    # Triangular smoothing
    voiced_idx = np.where(f0c > 30)[0]
    for k in range(1, len(voiced_idx) - 1):
        i0, i1, i2 = voiced_idx[k-1], voiced_idx[k], voiced_idx[k+1]
        if i2 - i0 <= 4:  # only smooth nearby frames
            f0c[i1] = (f0c[i0] + 2 * f0c[i1] + f0c[i2]) / 4.0

    return f0c


def librosa_pyin(wav_path: Path, fmin=65.0, fmax=500.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract pitch via librosa's probabilistic YIN (pYIN). Returns (times, f0, voicing_flag)."""
    import librosa
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr,
        frame_length=2048, hop_length=256,
    )
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=256)
    f0_out = np.where(voiced_flag, f0, 0.0)
    f0_out = np.where(np.isnan(f0_out), 0.0, f0_out)
    return times, f0_out, voiced_flag


def torchcrepe_pitch(wav_path: Path, fmin=32.7, fmax=1975.5,
                     model="full") -> tuple[np.ndarray, np.ndarray]:
    """Extract pitch via torchcrepe CREPE model. Returns (times, f0_hz)."""
    try:
        import torchcrepe
        import torch
        import torchaudio
    except ImportError as e:
        print(f"  [torchcrepe] not available: {e}")
        return np.array([]), np.array([])

    audio, sr = torchaudio.load(str(wav_path))
    if audio.shape[0] > 1:
        audio = audio.mean(0, keepdim=True)

    # torchcrepe expects 16 kHz
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(sr, 16000)
        audio = resampler(audio)
        sr = 16000

    # crepe hop = 10 ms by default
    hop_length = int(sr * 0.01)

    try:
        frequency, periodicity = torchcrepe.predict(
            audio,
            sr,
            hop_length=hop_length,
            fmin=fmin,
            fmax=fmax,
            model=model,
            batch_size=512,
            device="cpu",
            return_periodicity=True,
        )
        freq_np = frequency.squeeze().numpy()
        period_np = periodicity.squeeze().numpy()
        n = len(freq_np)
        times = np.arange(n) * (hop_length / sr)
        f0 = np.where(period_np > 0.35, freq_np, 0.0)
        return times, f0
    except Exception as e:
        print(f"  [torchcrepe] prediction failed: {e}")
        return np.array([]), np.array([])


# ─── Analysis and comparison ─────────────────────────────────────────────────

def analyze_octave_errors(times_praat: np.ndarray, f0_praat: np.ndarray,
                          times_lib: np.ndarray, f0_lib: np.ndarray,
                          times_crepe: np.ndarray = None, f0_crepe: np.ndarray = None,
                          ) -> dict:
    """Find frames where Praat deviates > 8 ST from librosa pyin (likely octave errors)."""
    results = {
        "praat_voiced": int(np.sum(f0_praat > 30)),
        "librosa_voiced": int(np.sum(f0_lib > 30)),
        "octave_errors_likely": [],
        "praat_median_hz": None,
        "librosa_median_hz": None,
    }

    p_voiced = f0_praat[f0_praat > 30]
    l_voiced = f0_lib[f0_lib > 30]
    if len(p_voiced) >= 2:
        results["praat_median_hz"] = float(np.median(p_voiced))
    if len(l_voiced) >= 2:
        results["librosa_median_hz"] = float(np.median(l_voiced))

    # Cross-compare where both are voiced
    for t_p, f_p in zip(times_praat, f0_praat):
        if f_p < 30:
            continue
        # Find nearest librosa frame
        if len(times_lib) == 0:
            continue
        idx = int(np.argmin(np.abs(times_lib - t_p)))
        f_l = f0_lib[idx]
        if f_l < 30:
            continue
        st_diff = 12 * math.log2(f_p / f_l) if f_p > 0 and f_l > 0 else 0
        if abs(st_diff) > 8:
            results["octave_errors_likely"].append({
                "time_s": round(float(t_p), 3),
                "praat_hz": round(float(f_p), 1),
                "librosa_hz": round(float(f_l), 1),
                "diff_st": round(float(st_diff), 1),
                "direction": "praat_too_high" if st_diff > 0 else "praat_too_low",
            })

    return results


def _octave_error_summary(errors: list[dict]) -> str:
    if not errors:
        return "No octave errors detected"
    high = sum(1 for e in errors if e["direction"] == "praat_too_high")
    low  = sum(1 for e in errors if e["direction"] == "praat_too_low")
    return (f"{len(errors)} probable octave errors "
            f"({high} Praat-too-high, {low} Praat-too-low)")


def plot_comparison(name: str, wav_path: Path, out_dir: Path,
                    times_praat_raw: np.ndarray, f0_praat_raw: np.ndarray,
                    times_praat_cor: np.ndarray, f0_praat_cor: np.ndarray,
                    times_lib: np.ndarray, f0_lib: np.ndarray,
                    times_crepe: np.ndarray = None, f0_crepe: np.ndarray = None,
                    errors: dict = None) -> None:
    """Save a 4-panel (or 3-panel) comparison plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    panels = 4 if (times_crepe is not None and len(times_crepe) > 0) else 3
    fig, axes = plt.subplots(panels, 1, figsize=(14, panels * 2.5), sharex=True)
    fig.suptitle(f"Pitch tracker comparison: {name}", fontsize=13, fontweight="bold")

    def _plot_f0(ax, times, f0, label, color, ymin=50, ymax=600):
        voiced_mask = f0 > 30
        if voiced_mask.any():
            ax.scatter(times[voiced_mask], f0[voiced_mask], s=2, color=color, label=label)
        ax.set_ylim(ymin, ymax)
        ax.set_ylabel("F0 (Hz)")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=100, color="gray", lw=0.5, ls="--", alpha=0.5)
        ax.axhline(y=200, color="gray", lw=0.5, ls="--", alpha=0.5)
        ax.axhline(y=400, color="gray", lw=0.5, ls="--", alpha=0.5)

    _plot_f0(axes[0], times_praat_raw, f0_praat_raw, "Praat SCC (raw)", "steelblue")
    _plot_f0(axes[1], times_praat_cor, f0_praat_cor, "Praat AC + Xu(1999) correction", "darkorange")
    _plot_f0(axes[2], times_lib, f0_lib, "Librosa pYIN", "green")
    if panels == 4:
        _plot_f0(axes[3], times_crepe, f0_crepe, "torchcrepe (CREPE)", "purple")

    # Annotate octave errors on raw panel
    if errors and errors.get("octave_errors_likely"):
        for err in errors["octave_errors_likely"][:10]:
            axes[0].axvline(x=err["time_s"], color="red", lw=0.8, alpha=0.5)

    axes[-1].set_xlabel("Time (s)")
    plt.tight_layout()
    out_path = out_dir / f"{name}_pitch_comparison.png"
    plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")


# ─── Main ────────────────────────────────────────────────────────────────────

def run_comparison(wav_path: Path, name: str, out_dir: Path) -> dict:
    print(f"\n── Analyzing: {name}")
    row = {"name": name}

    # Praat raw
    try:
        t_pr, f0_pr = praat_pitch_raw(wav_path)
        voiced_pr = f0_pr[f0_pr > 30]
        row["praat_raw_voiced"] = len(voiced_pr)
        row["praat_raw_median_hz"] = round(float(np.median(voiced_pr)), 1) if len(voiced_pr) else None
        row["praat_raw_min_hz"]    = round(float(np.min(voiced_pr)), 1)    if len(voiced_pr) else None
        row["praat_raw_max_hz"]    = round(float(np.max(voiced_pr)), 1)    if len(voiced_pr) else None
        print(f"  Praat raw: {len(voiced_pr)} voiced frames, "
              f"median={row['praat_raw_median_hz']}Hz, "
              f"range=[{row['praat_raw_min_hz']}, {row['praat_raw_max_hz']}]Hz")
    except Exception as e:
        print(f"  Praat raw failed: {e}")
        t_pr, f0_pr = np.array([]), np.array([])

    # Praat AC (better params)
    try:
        t_pac, f0_pac = praat_pitch_ac(wav_path)
        # Apply Xu (1999) octave correction
        f0_pac_cor = praat_pitch_corrected(t_pac, f0_pac)
        voiced_pac = f0_pac[f0_pac > 30]
        voiced_cor = f0_pac_cor[f0_pac_cor > 30]
        row["praat_ac_voiced"]  = len(voiced_pac)
        row["praat_cor_voiced"] = len(voiced_cor)
        row["praat_cor_median_hz"] = round(float(np.median(voiced_cor)), 1) if len(voiced_cor) else None
        print(f"  Praat AC: {len(voiced_pac)} voiced, corrected: {len(voiced_cor)} "
              f"median={row['praat_cor_median_hz']}Hz")
    except Exception as e:
        print(f"  Praat AC failed: {e}")
        t_pac, f0_pac, f0_pac_cor = t_pr, f0_pr, f0_pr

    # Librosa pyin
    try:
        t_lib, f0_lib, voiced_lib = librosa_pyin(wav_path)
        voiced_lib_vals = f0_lib[f0_lib > 30]
        row["librosa_voiced"]     = int(np.sum(f0_lib > 30))
        row["librosa_median_hz"]  = round(float(np.median(voiced_lib_vals)), 1) if len(voiced_lib_vals) else None
        row["librosa_min_hz"]     = round(float(np.min(voiced_lib_vals)), 1)    if len(voiced_lib_vals) else None
        row["librosa_max_hz"]     = round(float(np.max(voiced_lib_vals)), 1)    if len(voiced_lib_vals) else None
        print(f"  Librosa pYIN: {row['librosa_voiced']} voiced, "
              f"median={row['librosa_median_hz']}Hz, "
              f"range=[{row['librosa_min_hz']}, {row['librosa_max_hz']}]Hz")
    except Exception as e:
        print(f"  Librosa failed: {e}")
        t_lib, f0_lib = np.array([]), np.array([])

    # CREPE via torchcrepe
    try:
        t_crepe, f0_crepe = torchcrepe_pitch(wav_path)
        voiced_crepe = f0_crepe[f0_crepe > 30] if len(f0_crepe) else np.array([])
        row["crepe_voiced"]    = len(voiced_crepe)
        row["crepe_median_hz"] = round(float(np.median(voiced_crepe)), 1) if len(voiced_crepe) else None
        row["crepe_min_hz"]    = round(float(np.min(voiced_crepe)), 1)    if len(voiced_crepe) else None
        row["crepe_max_hz"]    = round(float(np.max(voiced_crepe)), 1)    if len(voiced_crepe) else None
        print(f"  torchcrepe: {row['crepe_voiced']} voiced, "
              f"median={row['crepe_median_hz']}Hz, "
              f"range=[{row['crepe_min_hz']}, {row['crepe_max_hz']}]Hz")
    except Exception as e:
        print(f"  torchcrepe failed: {e}")
        t_crepe, f0_crepe = np.array([]), np.array([])

    # Cross-compare for octave errors
    errors = {}
    if len(t_pr) > 0 and len(t_lib) > 0:
        errors = analyze_octave_errors(t_pr, f0_pr, t_lib, f0_lib, t_crepe, f0_crepe)
        row["octave_errors_n"] = len(errors.get("octave_errors_likely", []))
        row["octave_error_summary"] = _octave_error_summary(errors.get("octave_errors_likely", []))
        print(f"  Octave errors (Praat vs Librosa): {row['octave_error_summary']}")

    # Plot
    if len(t_pr) > 0:
        plot_comparison(
            name, wav_path, out_dir,
            t_pr, f0_pr,
            t_pac, f0_pac_cor,
            t_lib, f0_lib,
            t_crepe if len(t_crepe) > 0 else None,
            f0_crepe if len(f0_crepe) > 0 else None,
            errors,
        )

    row["errors"] = errors
    return row


def write_comparison_report(rows: list[dict], out_dir: Path) -> None:
    """Write a text report comparing the trackers."""
    lines = [
        "PITCH TRACKER COMPARISON REPORT",
        "=" * 60,
        "",
        "Files analyzed: German GToBI sentences + English + Doreco",
        "Trackers: Praat SCC (raw), Praat AC + Xu(1999), Librosa pYIN, torchcrepe",
        "",
        "NOTES ON EACH TRACKER:",
        "-" * 40,
        "",
        "1. Praat SCC (raw):",
        "   - Default Praat pitch.  Susceptible to octave jumps (picks octave",
        "     harmonic instead of F0 when formants interfere).  Known to occasionally",
        "     double or halve the F0 estimate, especially at voicing boundaries.",
        "   - Range: 75–600 Hz (the default Praat range).  Too wide for a single",
        "     speaker → allows implausible values.",
        "",
        "2. Praat AC + Xu (1999) octave correction:",
        "   - Uses to_pitch_ac() with octave_jump_cost=0.5 (double the default",
        "     penalty, so Praat will avoid jumping an octave unless forced to).",
        "   - Post-hoc correction: median across voiced frames is computed; any",
        "     frame deviating >10 ST is tested with F0/2 and F0×2 — whichever",
        "     is closer to the median replaces the outlier.",
        "   - Followed by triangular smoothing (1:2:1 over 3 voiced frames).",
        "   - This mirrors the ProsodyPro approach recommended by Xu (1999).",
        "",
        "3. Librosa pYIN (probabilistic YIN):",
        "   - State-of-the-art monophonic F0 tracker.  Returns voiced/unvoiced",
        "     probability so unvoiced frames are cleanly masked.",
        "   - Less susceptible to octave errors than Praat SCC because it uses",
        "     a statistical model of F0 continuity.",
        "   - Handles whispery or breathy voice better than Praat.",
        "   - Small hop (10 ms) gives fine time resolution.",
        "",
        "4. torchcrepe (CREPE — Convolutional REpresentation for Pitch Estimation):",
        "   - Deep CNN trained on large corpora (NYU MARL, ICASSP 2018).",
        "   - Operates directly on waveform, not spectrum → avoids harmonic confusion.",
        "   - Best overall accuracy on speech and singing, outperforms pYIN/SWIPE",
        "     on challenging material (breathy, creaky, noisy speech).",
        "   - Requires 16 kHz input; uses ~100 ms context.",
        "   - Periodicity threshold 0.35 used here for voicing decision.",
        "",
        "RECOMMENDATION:",
        "   For SpeechPrint, use Librosa pYIN as the primary pitch tracker",
        "   (robust, no heavy model download needed) with Xu(1999) post-correction",
        "   as a safety net. torchcrepe gives the best accuracy but requires GPU",
        "   for production use.",
        "",
        "COMPARISON TABLE:",
        "-" * 60,
    ]

    headers = ["File", "Praat_med(Hz)", "Praat+Xu_med(Hz)", "Lib_med(Hz)",
               "CREPE_med(Hz)", "Octave_errors"]
    col_w = [28, 14, 16, 12, 13, 40]
    hdr = "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for row in rows:
        cols = [
            row.get("name", "?")[:col_w[0]],
            str(row.get("praat_raw_median_hz", "?"))[:col_w[1]],
            str(row.get("praat_cor_median_hz", "?"))[:col_w[2]],
            str(row.get("librosa_median_hz", "?"))[:col_w[3]],
            str(row.get("crepe_median_hz", "?"))[:col_w[4]],
            row.get("octave_error_summary", "?")[:col_w[5]],
        ]
        lines.append("  ".join(c.ljust(w) for c, w in zip(cols, col_w)))

    lines += ["", "OCTAVE ERROR EXAMPLES (top 3 per file):"]
    for row in rows:
        errs = row.get("errors", {}).get("octave_errors_likely", [])
        if not errs:
            continue
        lines.append(f"\n  {row['name']}:")
        for err in errs[:3]:
            lines.append(
                f"    t={err['time_s']:.3f}s  Praat={err['praat_hz']}Hz  "
                f"Librosa={err['librosa_hz']}Hz  diff={err['diff_st']:+.1f}ST  "
                f"({err['direction']})"
            )

    lines += ["", "END OF REPORT"]
    report_path = out_dir / "PITCH_TRACKER_COMPARISON.txt"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nComparison report: {report_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="Output directory")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else BASE / "out" / "pitch_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    # (name, wav_path, max_dur_seconds or None)
    # Short German sentences run in full; long English/Doreco use a 30s excerpt
    targets = [
        (GTOBI_DIR / "eine_gelbe_banane.wav",      "eine_gelbe_banane",  None),
        (GTOBI_DIR / "einige_melonen.wav",           "einige_melonen",     None),
        (GTOBI_DIR / "er_sang_die_lieder.wav",       "er_sang_die_lieder", None),
        (GTOBI_DIR / "er_will_die_rosen_haben.wav",  "er_will_die_rosen",  None),
        (GTOBI_DIR / "ich_wohne_in_bern.wav",        "ich_wohne_in_bern",  None),
    ]
    if ENGLISH_WAV.exists():
        targets.append((ENGLISH_WAV, "audio_english_30s", 30.0))
    if DORECO_WAV.exists():
        targets.append((DORECO_WAV, "doreco_port1286_30s", 30.0))

    for wav_path, name, max_dur in targets:
        if not wav_path.exists():
            print(f"  SKIP (not found): {wav_path}")
            continue
        try:
            # Trim long files to max_dur seconds for comparison
            analysis_wav = wav_path
            if max_dur is not None:
                import soundfile as sf
                import tempfile, os
                data, sr = sf.read(str(wav_path), dtype="float32")
                n_frames = int(sr * max_dur)
                if len(data) > n_frames:
                    print(f"  (Using first {max_dur}s excerpt of {wav_path.name})")
                    analysis_wav = Path(tempfile.mktemp(suffix=".wav"))
                    sf.write(str(analysis_wav), data[:n_frames], sr)

            row = run_comparison(analysis_wav, name, out_dir)
            rows.append(row)

            if analysis_wav != wav_path and analysis_wav.exists():
                analysis_wav.unlink()
        except Exception as e:
            import traceback
            print(f"  ERROR on {name}: {e}")
            traceback.print_exc()

    # Save JSON with all analysis
    json_path = out_dir / "pitch_comparison_data.json"
    json_path.write_text(
        json.dumps(
            [{k: v for k, v in r.items() if k != "errors"} for r in rows],
            indent=2, default=str
        ),
        encoding="utf-8"
    )

    write_comparison_report(rows, out_dir)
    print(f"\nAll outputs in: {out_dir}")


if __name__ == "__main__":
    main()
