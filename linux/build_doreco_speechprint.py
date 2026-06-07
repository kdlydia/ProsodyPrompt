#!/usr/bin/env python3
"""Build SpeechPrint TextGrid from DoReCo Daakie human-annotated phones.

No ASR. Words and phones come directly from DoReCo wd@TA and ph@TA tiers.
Xu (1999) spike trimming applied before every F0 measurement.

Output tiers (10):
  1. sentence        — utterance-level Daakie orthographic text (tx@TA)
  2. translation     — utterance-level English free translation (ft@TA)
  3. words           — Daakie words (wd@TA, human-annotated)
  4. gloss           — English word glosses (gl@TA, human-annotated)
  5. syllables       — vowel-nucleus syllable spans (from ph@TA)
  6. phones          — SAMPA phonemes (ph@TA, human-annotated)
  7. prosody_crepe   — ProsodyPro analysis using CREPE F0 (Kim et al. 2018, NYU)
  8. prosody_pyin    — ProsodyPro analysis using pYIN F0 (librosa, best baseline)
  9. prosody_yin     — ProsodyPro analysis using YIN F0 (librosa)
 10. prosody_praat   — ProsodyPro analysis using Praat autocorrelation (more errors)

Prosody symbols:
  ‾  high level      _  low level       (‾ = U+203E overline, opposite of _)
  /  weakly rising   // strongly rising
  \\  weakly falling  \\\\ strongly falling
  *  accent (prominent: loud + high relative to neighbours)
  Combinations: ‾// _// ‾\\ _\\ etc.

Also generates a scrolling MP4 video (waveform + spectrogram + all tiers).
"""

from __future__ import annotations

import math
import re
import statistics
import subprocess
import sys
from pathlib import Path


# ============================================================================
# DoReCo Daakie vowel set (SAMPA-based, from ph@TA tier)
# ============================================================================

DAAKIE_VOWELS = {
    "a", "a:", "e:", "E", "E:", "i", "i:", "O", "O:", "o", "u", "u:",
    "{",
}

SKIP_LABELS = {"<p:>", "<<fp>>", "<<fs>>", "<<ui>>", "<<ui>gon>", "****"}

SPIKE_THRESHOLD_ST  = 12.0
WEAK_RISE_FLOOR_ST  = 0.5
WEAK_FALL_FLOOR_ST  = 0.5
ADAPTIVE_FACTOR     = 0.35
STRONG_FACTOR       = 2.5
HIGH_NBR_ST         = 0.8
LOW_NBR_ST          = 0.8
ACCENT_AMP_DB       = 1.5
ACCENT_F0_ST        = 1.0
VELOCITY_STRONG_ST_S = 6.0
DURATION_ACCENT_FACTOR = 1.25

HIGH_LEVEL_SYM = "‾"   # U+203E OVERLINE — opposite of underscore
LOW_LEVEL_SYM  = "_"


# ============================================================================
# TEXTGRID PARSER
# ============================================================================

def parse_textgrid(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    xmax_m = re.search(r"^xmax = ([\d.]+)", content, re.MULTILINE)
    xmax = float(xmax_m.group(1)) if xmax_m else 0.0

    tiers = []
    for block in re.split(r"\n\s*item \[\d+\]:", content)[1:]:
        name_m = re.search(r'name = "([^"]*)"', block)
        if not name_m:
            continue
        intervals = []
        for iv in re.split(r"\n\s*intervals \[\d+\]:", block)[1:]:
            xmin_m = re.search(r"xmin = ([\d.]+)", iv)
            xmax_m2 = re.search(r"xmax = ([\d.]+)", iv)
            text_m  = re.search(r'text = "([^"]*)"', iv, re.DOTALL)
            if xmin_m and xmax_m2 and text_m:
                intervals.append({
                    "start": float(xmin_m.group(1)),
                    "end":   float(xmax_m2.group(1)),
                    "text":  text_m.group(1),
                })
        tiers.append({"name": name_m.group(1), "intervals": intervals})
    return {"xmax": xmax, "tiers": tiers}


def get_tier(tg: dict, name: str) -> list[dict] | None:
    for t in tg["tiers"]:
        if t["name"] == name:
            return t["intervals"]
    return None


# ============================================================================
# UTILITIES
# ============================================================================

def _st(a, b) -> float | None:
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12.0 * math.log2(b / a)


def _safe_mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else None


def trim_f0_xu1999(f0_vals: list) -> list:
    """Xu (1999) / ProsodyPro: median-based spike removal + triangular smoothing."""
    voiced = [v for v in f0_vals if v is not None and v > 0]
    if len(voiced) < 2:
        return list(f0_vals)
    med = statistics.median(voiced)
    trimmed = [
        v if (v is None or v <= 0 or abs(_st(med, v) or 0) <= SPIKE_THRESHOLD_ST)
        else None
        for v in f0_vals
    ]
    n = len(trimmed)
    smooth = list(trimmed)
    for i in range(1, n - 1):
        a, b, c = trimmed[i - 1], trimmed[i], trimmed[i + 1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            smooth[i] = (a + 2.0 * b + c) / 4.0
    return smooth


# ============================================================================
# F0 TRACKERS  — each returns (times_array, f0_array, rms_array, sr)
# ============================================================================

def track_pyin(y, sr, fmin=65.0, fmax=500.0):
    """pYIN — probabilistic YIN, best librosa tracker."""
    import numpy as np
    import librosa

    hop = 256
    f0_raw, voiced_flag, _ = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr, frame_length=2048, hop_length=hop,
    )
    times = librosa.frames_to_time(range(len(f0_raw)), sr=sr, hop_length=hop)
    f0 = np.where(voiced_flag & ~np.isnan(f0_raw), f0_raw, 0.0)

    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))

    print(f"    pYIN:  {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr


def track_yin(y, sr, fmin=65.0, fmax=500.0):
    """YIN — deterministic, faster, more octave errors than pYIN."""
    import numpy as np
    import librosa

    hop = 256
    f0_raw = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop)
    times  = librosa.frames_to_time(range(len(f0_raw)), sr=sr, hop_length=hop)
    f0 = np.where((f0_raw >= fmin) & (f0_raw <= fmax), f0_raw, 0.0)

    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))

    print(f"    YIN:   {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr


def track_crepe(y, sr, fmin=65.0, fmax=500.0):
    """CREPE — deep CNN pitch tracker (Kim et al. 2018, NYU ITP).
    Uses torchcrepe (PyTorch port, "full" model). Resamples to 16 kHz.
    batch_size=256 keeps memory manageable on CPU.
    Downloads model weights (~84 MB) on first run.
    """
    import numpy as np
    import librosa
    import torch
    import torchcrepe

    y16  = librosa.resample(y, orig_sr=sr, target_sr=16000)
    sr16 = 16000
    hop_samples = 320   # 20 ms at 16 kHz

    audio_t = torch.tensor(y16[None], dtype=torch.float32)
    freq_c, conf_c = torchcrepe.predict(
        audio_t, sr16,
        hop_length=hop_samples,
        fmin=fmin, fmax=fmax,
        model="full",
        decoder=torchcrepe.decode.viterbi,
        return_periodicity=True,
        batch_size=256,
        device="cpu",
    )
    freq_c = freq_c.squeeze().numpy()
    conf_c = conf_c.squeeze().numpy()
    times  = librosa.frames_to_time(range(len(freq_c)), sr=sr16, hop_length=hop_samples)

    f0 = np.where(
        (conf_c > 0.5) & (freq_c >= fmin) & (freq_c <= fmax),
        freq_c, 0.0,
    )
    rms16 = librosa.feature.rms(y=y16, hop_length=hop_samples)[0]
    rms16 = librosa.util.fix_length(rms16, size=len(f0))

    print(f"    CREPE: {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms16, sr16


def track_praat(wav_path: Path, y, sr, fmin=65.0, fmax=500.0):
    """Praat autocorrelation via parselmouth — reference with known octave errors."""
    import numpy as np
    import librosa
    import parselmouth

    hop = 256
    hop_s = hop / sr
    times = librosa.frames_to_time(
        range(int(len(y) / hop) + 1), sr=sr, hop_length=hop
    )

    snd   = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch(
        time_step=hop_s, pitch_floor=fmin, pitch_ceiling=fmax
    )

    f0 = np.array([
        (v if v is not None and not math.isnan(v) else 0.0)
        for v in (pitch.get_value_at_time(t) for t in times)
    ])
    f0 = np.nan_to_num(f0, nan=0.0)
    f0 = np.where((f0 >= fmin) & (f0 <= fmax), f0, 0.0)

    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))

    print(f"    Praat: {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr


# ============================================================================
# NUCLEUS MEASUREMENT
# ============================================================================

def measure_nucleus(times, f0, rms, t_start: float, t_end: float,
                    n_points: int = 10) -> dict:
    import numpy as np

    dur = t_end - t_start
    empty = {
        "f0_onset": None, "f0_mid": None, "f0_offset": None,
        "f0_mean": None, "amplitude_db": None, "voiced": False,
        "velocity_st_s": None,
    }
    if dur < 0.010:
        return empty

    ts = [t_start + dur * j / (n_points - 1) for j in range(n_points)]
    f0_raw_pts, rms_pts = [], []
    for t in ts:
        idx = int(np.searchsorted(times, t))
        idx = min(idx, len(f0) - 1)
        val = float(f0[idx])
        f0_raw_pts.append(val if val > 30 else None)
        rms_pts.append(float(rms[idx]))

    f0_pts = trim_f0_xu1999(f0_raw_pts)
    voiced_vals = [v for v in f0_pts if v is not None and v > 0]
    voiced = len(voiced_vals) / n_points > 0.3

    f0_onset  = next((v for v in f0_pts if v), None)
    f0_offset = next((v for v in reversed(f0_pts) if v), None)
    mid_idx = n_points // 2
    f0_mid = None
    for delta in range(n_points // 2 + 1):
        for idx in (mid_idx - delta, mid_idx + delta):
            if 0 <= idx < n_points and f0_pts[idx]:
                f0_mid = f0_pts[idx]
                break
        if f0_mid:
            break

    f0_mean  = _safe_mean(voiced_vals)
    rms_mean = _safe_mean(rms_pts)
    amp_db   = (20.0 * math.log10(rms_mean + 1e-10) + 120.0) if rms_mean else None

    velocity = None
    if f0_onset and f0_offset and dur > 0:
        mv = _st(f0_onset, f0_offset)
        if mv is not None:
            velocity = mv / dur

    return {
        "f0_onset": f0_onset, "f0_mid": f0_mid, "f0_offset": f0_offset,
        "f0_mean": f0_mean, "amplitude_db": amp_db,
        "voiced": voiced, "velocity_st_s": velocity,
    }


# ============================================================================
# SYLLABIFICATION
# ============================================================================

def is_vowel(phone: str) -> bool:
    return phone in DAAKIE_VOWELS


def syllabify_phones(phone_ivs: list[dict]) -> list[dict]:
    phones = [iv["text"] for iv in phone_ivs]
    n = len(phones)
    if n == 0:
        return []

    vowel_idx = [i for i, p in enumerate(phones) if is_vowel(p)]
    if not vowel_idx:
        label = "".join(phones)
        start, end = phone_ivs[0]["start"], phone_ivs[-1]["end"]
        return [{"start": start, "end": end, "label": label,
                 "vowel_start": start, "vowel_end": end, "phones": phones}]

    boundaries = []
    for k, vi in enumerate(vowel_idx):
        if k == 0:
            onset_start = 0
        else:
            prev_vi = vowel_idx[k - 1]
            gap = vi - prev_vi - 1
            cut = prev_vi + 1 + (gap // 2) if gap > 0 else prev_vi + 1
            if boundaries:
                prev = boundaries[-1]
                boundaries[-1] = (prev[0], cut)
            onset_start = cut
        if k == len(vowel_idx) - 1:
            boundaries.append((onset_start, n))
        else:
            boundaries.append((onset_start, vi + 1))

    syllables = []
    for ps, pe in boundaries:
        syl_ivs = phone_ivs[ps:pe]
        start, end = syl_ivs[0]["start"], syl_ivs[-1]["end"]
        label = "".join(phones[ps:pe])
        v_ivs = [iv for iv in syl_ivs if is_vowel(iv["text"])]
        vowel_start = v_ivs[0]["start"] if v_ivs else start
        vowel_end   = v_ivs[-1]["end"]  if v_ivs else end
        syllables.append({
            "start": start, "end": end, "label": label,
            "vowel_start": vowel_start, "vowel_end": vowel_end,
            "phones": phones[ps:pe],
        })
    return syllables


# ============================================================================
# PROSODY LABELLING
# ============================================================================

def label_prosody_relative(syllables: list[dict]) -> None:
    n = len(syllables)
    if n == 0:
        return

    for syl in syllables:
        mv = _st(syl.get("f0_onset"), syl.get("f0_offset"))
        syl["_mv"]  = mv
        syl["_vel"] = syl.get("velocity_st_s")

    mvs = [abs(syl["_mv"]) for syl in syllables if syl["_mv"] is not None]
    rec_std    = statistics.stdev(mvs) if len(mvs) >= 2 else 2.0
    weak_thr   = max(WEAK_RISE_FLOOR_ST, ADAPTIVE_FACTOR * rec_std)
    strong_thr = max(weak_thr * STRONG_FACTOR, 2.0)

    for i, syl in enumerate(syllables):
        mv      = syl["_mv"]
        vel     = syl["_vel"]
        f0_mean = syl.get("f0_mean")
        amp     = syl.get("amplitude_db")

        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in (i - 1, i + 1):
            if 0 <= j < n:
                v = syllables[j].get("f0_mean")
                a = syllables[j].get("amplitude_db")
                d = syllables[j]["end"] - syllables[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)

        nbr_mean_f0  = _safe_mean(nbr_f0)
        nbr_mean_amp = _safe_mean(nbr_amp)
        nbr_mean_dur = _safe_mean(nbr_dur) if nbr_dur else None
        syl_dur      = syl["end"] - syl["start"]
        is_long = nbr_mean_dur is not None and syl_dur >= DURATION_ACCENT_FACTOR * nbr_mean_dur

        height_st = _st(nbr_mean_f0, f0_mean) if (nbr_mean_f0 and f0_mean) else None
        is_high = height_st is not None and height_st >= HIGH_NBR_ST
        is_low  = height_st is not None and height_st <= -LOW_NBR_ST

        amp_above = (amp - nbr_mean_amp) if (amp and nbr_mean_amp) else None
        is_loud   = amp_above is not None and amp_above >= ACCENT_AMP_DB

        strong = (abs(mv) >= strong_thr if mv else False) or \
                 (abs(vel) >= VELOCITY_STRONG_ST_S if vel else False)

        if mv is None:
            direction = ""
        elif mv >= weak_thr:
            direction = "//" if strong else "/"
        elif mv <= -weak_thr:
            direction = "\\\\" if strong else "\\"
        else:
            direction = ""

        # ‾ = high level (U+203E overline), _ = low level
        if direction == "":
            height_sym = HIGH_LEVEL_SYM if is_high else (
                LOW_LEVEL_SYM if is_low else (
                    HIGH_LEVEL_SYM if (f0_mean and nbr_mean_f0) else "?"
                )
            )
        else:
            height_sym = HIGH_LEVEL_SYM if is_high else (LOW_LEVEL_SYM if is_low else "")

        is_accent = (
            (is_loud and height_st is not None and height_st >= ACCENT_F0_ST)
            or (is_long and is_loud and is_high)
        )

        symbol = ""
        if is_accent:
            symbol += "*"
        if height_sym and direction:
            symbol += height_sym + direction
        elif height_sym:
            symbol += height_sym
        elif direction:
            symbol += direction
        if not symbol:
            symbol = "?" if not f0_mean else HIGH_LEVEL_SYM

        syl["symbol"]    = symbol
        syl["is_accent"] = is_accent


# ============================================================================
# TEXTGRID WRITER
# ============================================================================

def _fill_gaps(rows: list[dict], xmax: float) -> list[dict]:
    out = []
    cursor = 0.0
    for r in sorted(rows, key=lambda x: x["start"]):
        s, e = float(r["start"]), float(r["end"])
        if s > cursor + 5e-4:
            out.append({"start": cursor, "end": s, "value": ""})
        out.append({"start": s, "end": e, "value": r.get("value", "")})
        cursor = max(cursor, e)
    if cursor < xmax - 5e-4:
        out.append({"start": cursor, "end": xmax, "value": ""})
    return out


def write_textgrid(path: Path, xmax: float, tiers: list[dict]) -> None:
    def esc(t): return str(t).replace('"', "'")
    lines = [
        'File type = "ooTextFile"', 'Object class = "TextGrid"', "",
        "xmin = 0", f"xmax = {xmax}", "tiers? <exists>",
        f"size = {len(tiers)}", "item []:",
    ]
    for ti, tier in enumerate(tiers, 1):
        rows = _fill_gaps(tier["rows"], xmax)
        lines += [
            f"    item [{ti}]:", '        class = "IntervalTier"',
            f'        name = "{esc(tier["name"])}"',
            "        xmin = 0", f"        xmax = {xmax}",
            f"        intervals: size = {len(rows)}",
        ]
        for ii, row in enumerate(rows, 1):
            lines += [
                f"        intervals [{ii}]:",
                f"            xmin = {row['start']}",
                f"            xmax = {row['end']}",
                f'            text = "{esc(row["value"])}"',
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written: {path}", flush=True)


# ============================================================================
# MAIN BUILD
# ============================================================================

def build(tg_path: Path, wav_path: Path, output_path: Path):
    print(f"\nDoReCo SpeechPrint: {tg_path.name}", flush=True)

    tg = parse_textgrid(tg_path)
    xmax = tg["xmax"]

    wd_tier = get_tier(tg, "wd@TA")
    ph_tier = get_tier(tg, "ph@TA")
    tx_tier = get_tier(tg, "tx@TA")
    ft_tier = get_tier(tg, "ft@TA")
    gl_tier = get_tier(tg, "gl@TA")
    if wd_tier is None or ph_tier is None:
        sys.exit("ERROR: wd@TA or ph@TA not found in TextGrid")

    # ---- Utterance-level pass-through tiers ----
    def _utt_rows(tier):
        if tier is None:
            return []
        return [
            {"start": iv["start"], "end": iv["end"], "value": iv["text"]}
            for iv in tier if iv["text"] and iv["text"] not in SKIP_LABELS
        ]

    sentence_rows    = _utt_rows(tx_tier)
    translation_rows = _utt_rows(ft_tier)

    # ---- Word tier ----
    word_rows, real_words = [], []
    for iv in wd_tier:
        text = iv["text"]
        if text in SKIP_LABELS or text == "":
            gap = iv["end"] - iv["start"]
            if gap >= 0.04:
                word_rows.append({"start": iv["start"], "end": iv["end"],
                                  "value": f"<sil {gap:.2f}s>"})
        else:
            word_rows.append({"start": iv["start"], "end": iv["end"], "value": text})
            real_words.append(iv)

    # ---- Gloss tier (English word glosses, same timing as wd@TA) ----
    gloss_rows = [
        {"start": iv["start"], "end": iv["end"], "value": iv["text"]}
        for iv in (gl_tier or [])
        if iv["text"] and iv["text"] not in SKIP_LABELS
    ]

    # ---- Phone tier (SAMPA, human-annotated, pass-through) ----
    phone_rows = [
        {"start": iv["start"], "end": iv["end"], "value": iv["text"]}
        for iv in ph_tier
        if iv["text"] not in SKIP_LABELS and iv["text"] != ""
    ]

    # ---- Syllabify from ph@TA (once, tracker-independent) ----
    syllable_rows = []
    syl_templates = []   # [{start,end,vowel_start,vowel_end,label}] no F0

    for word_iv in real_words:
        w_start, w_end = word_iv["start"], word_iv["end"]
        word_phones = [
            iv for iv in ph_tier
            if iv["start"] >= w_start - 1e-4
            and iv["end"]   <= w_end   + 1e-4
            and iv["text"] not in SKIP_LABELS
            and iv["text"] != ""
        ]
        if not word_phones:
            continue
        for syl in syllabify_phones(word_phones):
            syllable_rows.append({"start": syl["start"], "end": syl["end"],
                                  "value": syl["label"]})
            syl_templates.append({
                "start":       syl["start"],
                "end":         syl["end"],
                "vowel_start": syl["vowel_start"],
                "vowel_end":   syl["vowel_end"],
                "label":       syl["label"],
            })

    # ---- Load audio once ----
    print("  Loading audio...", flush=True)
    import librosa
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)

    # ---- Run all F0 trackers ----
    print("  Running F0 trackers:", flush=True)
    trackers = {}

    print("  → CREPE (neural network)...", flush=True)
    try:
        trackers["crepe"] = track_crepe(y, sr)
    except Exception as e:
        print(f"    CREPE failed: {e}", flush=True)
        trackers["crepe"] = None

    print("  → pYIN (probabilistic YIN)...", flush=True)
    trackers["pyin"] = track_pyin(y, sr)

    print("  → YIN (deterministic)...", flush=True)
    trackers["yin"] = track_yin(y, sr)

    print("  → Praat (autocorrelation)...", flush=True)
    try:
        trackers["praat"] = track_praat(wav_path, y, sr)
    except Exception as e:
        print(f"    Praat failed: {e}", flush=True)
        trackers["praat"] = None

    # ---- For each tracker: measure nuclei → label prosody → build tier ----
    def prosody_tier(tracker_result) -> list[dict]:
        if tracker_result is None:
            return [{"start": s["start"], "end": s["end"], "value": ""}
                    for s in syl_templates]
        times, f0, rms, _ = tracker_result
        syls = []
        for tmpl in syl_templates:
            syl = dict(tmpl)
            syl.update(measure_nucleus(times, f0, rms,
                                       tmpl["vowel_start"], tmpl["vowel_end"]))
            syls.append(syl)
        label_prosody_relative(syls)
        return [{"start": s["start"], "end": s["end"],
                 "value": s.get("symbol", "?")} for s in syls]

    prosody_crepe = prosody_tier(trackers["crepe"])
    prosody_pyin  = prosody_tier(trackers["pyin"])
    prosody_yin   = prosody_tier(trackers["yin"])
    prosody_praat = prosody_tier(trackers["praat"])

    # ---- Write TextGrid ----
    tiers = [
        {"name": "sentence",       "rows": sentence_rows},
        {"name": "translation",    "rows": translation_rows},
        {"name": "words",          "rows": word_rows},
        {"name": "gloss",          "rows": gloss_rows},
        {"name": "syllables",      "rows": syllable_rows},
        {"name": "phones",         "rows": phone_rows},
        {"name": "prosody_crepe",  "rows": prosody_crepe},
        {"name": "prosody_pyin",   "rows": prosody_pyin},
        {"name": "prosody_yin",    "rows": prosody_yin},
        {"name": "prosody_praat",  "rows": prosody_praat},
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_textgrid(output_path, xmax, tiers)

    print(f"  Utterances: {len(sentence_rows)}", flush=True)
    print(f"  Words:      {len(real_words)}", flush=True)
    print(f"  Phones:     {len(phone_rows)}", flush=True)
    print(f"  Syllables:  {len(syl_templates)}", flush=True)


# ============================================================================
# VIDEO GENERATOR
# ============================================================================

def generate_video(tg_path: Path, wav_path: Path, output_path: Path,
                   win: float = 5.0, step: float = 1.0, fps: int = 4) -> None:
    """Render a scrolling MP4 of the SpeechPrint TextGrid.

    Each frame shows a `win`-second window advancing by `step` seconds.
    At fps=4 and step=1.0 the video runs at 4× real time.
    Requires: matplotlib, librosa, numpy, ffmpeg on PATH.
    """
    import numpy as np
    import librosa
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    print("\n  Generating video...", flush=True)

    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    total_dur = len(y) / sr

    tg    = parse_textgrid(tg_path)
    tiers = tg["tiers"]
    n_tiers = len(tiers)

    TIER_BG = {
        "sentence":      "#EEF4FF",
        "translation":   "#EEF4FF",
        "words":         "#FFFDE7",
        "gloss":         "#FFFDE7",
        "syllables":     "#F1F8E9",
        "phones":        "#FFF3E0",
        "prosody_crepe": "#F9EBF8",
        "prosody_pyin":  "#F3E5F5",
        "prosody_yin":   "#EDE7F6",
        "prosody_praat": "#E8EAF6",
    }

    frames_dir = output_path.parent / "_video_frames"
    frames_dir.mkdir(exist_ok=True)

    heights = [0.7, 1.4] + [0.50] * n_tiers
    fig_h   = sum(heights) * 0.90 + 0.5

    frame_paths = []
    t = 0.0
    frame_idx = 0
    total_frames = int(total_dur / step) + 1

    while True:
        t_end = min(t + win, total_dur)

        fig, axes = plt.subplots(
            2 + n_tiers, 1, figsize=(14, fig_h),
            gridspec_kw={"height_ratios": heights},
            facecolor="white",
        )
        fig.subplots_adjust(left=0.13, right=0.99, top=0.95, bottom=0.04, hspace=0.0)

        # Waveform
        s0  = max(0, int(t * sr))
        s1  = min(len(y), int(t_end * sr))
        seg = y[s0:s1]
        ts  = np.linspace(t, t_end, len(seg))
        ax  = axes[0]
        ax.plot(ts, seg, color="#333", linewidth=0.3, rasterized=True)
        ax.set_xlim(t, t_end); ax.set_ylim(-1, 1)
        ax.set_ylabel("wav", fontsize=7, rotation=0, ha="right", va="center", labelpad=32)
        ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
        for sp in ax.spines.values(): sp.set_visible(False)

        # Spectrogram
        ax2 = axes[1]
        if len(seg) > 512:
            S = librosa.amplitude_to_db(
                np.abs(librosa.stft(seg, n_fft=512, hop_length=128)), ref=np.max
            )
            ax2.imshow(S, aspect="auto", origin="lower",
                       extent=[t, t_end, 0, sr / 2],
                       cmap="Greys", vmin=-60, vmax=0, rasterized=True)
        ax2.set_xlim(t, t_end); ax2.set_ylim(0, 5000)
        ax2.set_ylabel("0–5 kHz", fontsize=7, rotation=0, ha="right", va="center", labelpad=32)
        ax2.set_yticks([0, 2500, 5000]); ax2.tick_params(labelsize=6, bottom=False, labelbottom=False)
        ax2.spines[["top", "right", "bottom"]].set_visible(False)

        # Tiers
        for ti, tier in enumerate(tiers):
            ax = axes[2 + ti]
            ax.set_xlim(t, t_end); ax.set_ylim(0, 1)
            bg = TIER_BG.get(tier["name"], "#FFFFFF")
            ax.set_facecolor(bg)
            ax.set_ylabel(tier["name"], fontsize=6.5, rotation=0,
                          ha="right", va="center", labelpad=32)
            ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for sp in ax.spines.values(): sp.set_visible(False)

            for iv in tier["intervals"]:
                x0 = max(iv["start"], t)
                x1 = min(iv["end"], t_end)
                if x1 <= x0 + 1e-6:
                    continue
                label = iv.get("text", "")
                ax.add_patch(mpatches.Rectangle(
                    (x0, 0.05), x1 - x0, 0.90,
                    facecolor=bg, edgecolor="#999", linewidth=0.4,
                ))
                if label:
                    fs = 5 if len(label) > 30 else (6 if len(label) > 12 else 7)
                    ax.text((x0 + x1) / 2, 0.50, label,
                            ha="center", va="center", fontsize=fs, clip_on=True)

        # Time axis
        ax_last = axes[-1]
        tick_step = 0.5 if win <= 6 else 1.0
        xticks = np.arange(np.ceil(t / tick_step) * tick_step, t_end + 0.01, tick_step)
        ax_last.set_xticks(xticks)
        ax_last.tick_params(bottom=True, labelbottom=True, labelsize=6)
        ax_last.set_xlabel("s", fontsize=7)

        fig.suptitle(
            f"DoReCo Daakie — SpeechPrint  [{t:.2f}–{t_end:.2f} s]  "
            f"(frame {frame_idx+1}/{total_frames})",
            fontsize=8, fontweight="bold", y=0.98,
        )

        fp = frames_dir / f"frame_{frame_idx:05d}.png"
        fig.savefig(str(fp), dpi=100, bbox_inches="tight")
        plt.close(fig)
        frame_paths.append(fp)

        if frame_idx % 20 == 0:
            print(f"  Frame {frame_idx+1}/{total_frames}  t={t:.1f}s", flush=True)

        if t_end >= total_dur:
            break
        t += step
        frame_idx += 1

    print(f"  {len(frame_paths)} frames rendered.", flush=True)

    list_file = frames_dir / "frames.txt"
    frame_dur = 1.0 / fps
    with open(str(list_file), "w") as f:
        for fp in frame_paths:
            f.write(f"file '{fp.name}'\nduration {frame_dur}\n")
        if frame_paths:
            f.write(f"file '{frame_paths[-1].name}'\n")

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_file),
             "-vf", f"scale=trunc(iw/2)*2:trunc(ih/2)*2,fps={fps}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
             str(output_path)],
            check=True, cwd=str(frames_dir), capture_output=True,
        )
        print(f"  Video written: {output_path}", flush=True)
    except FileNotFoundError:
        print(f"  ffmpeg not found — PNG frames in: {frames_dir}", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"  ffmpeg error:\n{e.stderr.decode()}", flush=True)


# ============================================================================
# PRAAT OPENER
# ============================================================================

def open_in_praat(tg_path: Path, wav_path: Path):
    """Open WAV and TextGrid in Praat's GUI object window."""
    wav_abs = str(wav_path.resolve())
    tg_abs  = str(tg_path.resolve())
    for praat_bin in ("praat", "praat6"):
        try:
            subprocess.Popen([praat_bin, "--open", wav_abs, tg_abs])
            print(f"  Praat opened — select both objects and click 'View & Edit'", flush=True)
            return
        except FileNotFoundError:
            continue
    print("  Praat not found — open manually:", flush=True)
    print(f"    WAV:      {wav_abs}", flush=True)
    print(f"    TextGrid: {tg_abs}", flush=True)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    base     = Path(__file__).parent
    tg_path  = base / "doreco_port1286_2017_06_30_Jaklin.TextGrid"
    wav_path = base / "doreco_port1286_2017_06_30_Jaklin.wav"
    out_path = base / "out" / "FINAL_doreco_speechprint_pyin.TextGrid"
    vid_path = base / "out" / "FINAL_doreco_speechprint_pyin.mp4"

    build(tg_path, wav_path, out_path)
    generate_video(out_path, wav_path, vid_path)
    open_in_praat(out_path, wav_path)
