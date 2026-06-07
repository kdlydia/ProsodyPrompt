#!/usr/bin/env python3
"""Build the definitive SpeechPrint TextGrid from the best available aligner.

English  → MFA (phone-level Kaldi) for words and phoneme timing
Endangered language → WhisperX CTC (only viable cross-language aligner)

Output tiers (5):
  1. words       — word labels; silence gaps labelled <sil N.NNs>
  2. phonemes    — IPA phones at their best-aligner timing
  3. syllables   — syllable spans with vowel nucleus markers
  4. f0_vowel    — F0_onset|F0_mid|F0_off Hz  Amp dB  (vowel nucleus measurements)
  5. prosody     — / \\ // \\\\ – _ * symbols relative to neighbour syllables

Prosody symbols (relative to ±1 syllable neighbours):
  /    rising pitch (onset→offset > +1.5 st)
  //   strongly rising    (> +4 st or velocity > 8 st/s)
  \\   falling            (< -1.5 st)
  \\\\  strongly falling   (< -4 st or velocity > 8 st/s)
  –    high relative to neighbours (mean F0 > nbr mean + 1 st)
  _    low relative to neighbours  (mean F0 < nbr mean - 1 st)
  *    prominent accent (amplitude AND F0 height stand out locally)
  Combinations: *– */ *\\ *// etc. — prominent + direction
  Silence is explicit in the words tier; phoneme/syllable tiers have empty silences.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Optional


# ============================================================================
# IPA vowel set for nucleus detection
# ============================================================================

# Strict IPA vowel characters only — no consonants (j w h r l) that appear in diphthong strings
VOWELS_IPA = {
    # Cardinal monophthongs
    "a", "e", "i", "o", "u",
    # IPA vowel symbols
    "æ", "ɑ", "ɒ", "ɐ", "ə", "ɚ", "ɛ", "ɜ", "ɝ", "ɪ", "ɨ",
    "ɔ", "ø", "œ", "ʊ", "ʌ", "y", "ɯ", "ɵ", "ɘ", "ɤ", "ɞ",
    # Nasal vowels
    "ã", "ɛ̃", "ɔ̃", "œ̃", "ɑ̃",
    # Common transcription shortcuts used by espeak/MFA
    "iː", "uː", "eː", "oː", "aː", "ɑː", "ɔː", "ɛː",
    # Diphthong base vowels (without glide)
    "eɪ", "oʊ", "aɪ", "aʊ", "ɔɪ",
}
SILENCE_LABELS = {"", "sp", "sil", "SIL", "<eps>", "<sil>", "spn"}
# Recording-adaptive thresholds (see label_prosody_relative for usage)
# Global FLOORS — the computed threshold can never go below these.
WEAK_RISE_FLOOR_ST  = 0.5
WEAK_FALL_FLOOR_ST  = 0.5
# Adaptive factor: threshold = max(floor, FACTOR × std_dev_of_recording_movements)
ADAPTIVE_FACTOR     = 0.35
# Strong movement = 2.5× the adaptive weak threshold
STRONG_FACTOR       = 2.5
HIGH_NBR_ST = 0.8
LOW_NBR_ST  = 0.8
ACCENT_AMP_DB = 1.5
ACCENT_F0_ST  = 1.0
VELOCITY_STRONG_ST_S = 6.0
# Duration accent cue: a syllable ≥25% longer than its neighbours counts as "long"
DURATION_ACCENT_FACTOR = 1.25
# Xu (1999) / ProsodyPro trimming: max semitone distance from vowel-nucleus median
# before a pitch sample is treated as an octave spike.
SPIKE_THRESHOLD_ST = 12.0


# ============================================================================
# UTILITIES
# ============================================================================

def trim_f0_xu1999(f0_vals: list) -> list:
    """Remove octave-error spikes and apply triangular smoothing.

    Implements the Xu (1999) trimming algorithm used in ProsodyPro:
    1. Compute the median F0 across all voiced samples in the vowel nucleus.
       Median is robust to a minority of octave-doubled outliers.
    2. Remove any sample that deviates >SPIKE_THRESHOLD_ST semitones from
       that median (octave spikes typically land ~12–30 ST away).
    3. Apply one pass of triangular smoothing (weights 1:2:1) over three
       consecutive voiced points to reduce measurement jitter.
    """
    import statistics as _st_mod
    voiced = [v for v in f0_vals if v is not None]
    if len(voiced) < 2:
        return list(f0_vals)
    f0_median = _st_mod.median(voiced)
    trimmed = [
        v if (v is None or abs(_st(f0_median, v) or 0) <= SPIKE_THRESHOLD_ST) else None
        for v in f0_vals
    ]
    n = len(trimmed)
    smooth = list(trimmed)
    for i in range(1, n - 1):
        if all(trimmed[j] is not None for j in (i - 1, i, i + 1)):
            smooth[i] = (trimmed[i - 1] + 2.0 * trimmed[i] + trimmed[i + 1]) / 4.0
    return smooth


def _safe_mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else None

def _st(a, b):
    """Semitones from a to b (positive = rising)."""
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12 * math.log2(b / a)

def _is_vowel(phone: str) -> bool:
    """Check if a phone string represents a vowel."""
    if not phone:
        return False
    # Check the full phone string first (handles long symbols like iː, eɪ)
    if phone in VOWELS_IPA:
        return True
    # Reject known consonant glides even if they contain vowel characters
    if phone in {"w", "j", "ʋ", "ɥ", "h", "ɦ", "l", "r", "ɹ", "ɾ", "ɻ"}:
        return False
    # Check individual characters — catches single vowel symbols
    return any(ch in VOWELS_IPA for ch in phone)

def _esc(t) -> str:
    return str(t).replace('"', "'")


# ============================================================================
# LOAD BACKEND DATA
# ============================================================================

def load_backend_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================================
# VOWEL NUCLEUS EXTRACTION
# ============================================================================

def find_vowel_nucleus(phones_in_syllable: list[str],
                       syl_start: float, syl_end: float,
                       mfa_phone_intervals: list[dict] | None = None) -> tuple[float, float]:
    """Return (nucleus_start, nucleus_end) for the vowel nucleus of a syllable.

    If mfa_phone_intervals is provided, uses actual MFA phone timings.
    Otherwise estimates proportionally within [syl_start, syl_end].

    Returns (syl_start, syl_end) if no vowel found (fallback to whole syllable).
    """
    if not phones_in_syllable:
        return syl_start, syl_end

    # Identify vowel phones by index in the syllable phone list
    vowel_indices = [i for i, p in enumerate(phones_in_syllable) if _is_vowel(p)]
    if not vowel_indices:
        return syl_start, syl_end  # all consonants — measure whole span

    # If MFA phone intervals are available, match them by position
    if mfa_phone_intervals:
        # Find the sub-list of MFA intervals that fall within [syl_start, syl_end]
        syl_phones_mfa = [iv for iv in mfa_phone_intervals
                          if iv["start"] >= syl_start - 1e-4 and iv["end"] <= syl_end + 1e-4
                          and iv["label"] not in SILENCE_LABELS]
        if syl_phones_mfa:
            vowel_mfa = [iv for iv in syl_phones_mfa if _is_vowel(iv["label"])]
            if vowel_mfa:
                return float(vowel_mfa[0]["start"]), float(vowel_mfa[-1]["end"])

    # Proportional estimate within syllable
    total = len(phones_in_syllable)
    syl_dur = syl_end - syl_start
    v_start_idx = vowel_indices[0]
    v_end_idx = vowel_indices[-1]
    nuc_start = syl_start + syl_dur * v_start_idx / total
    nuc_end = syl_start + syl_dur * (v_end_idx + 1) / total
    return nuc_start, nuc_end


# ============================================================================
# F0 MEASUREMENT AT VOWEL NUCLEUS
# ============================================================================

def measure_vowel_f0(snd, pitch, intensity, nuc_start: float, nuc_end: float,
                     n_points: int = 10) -> dict:
    """Measure F0 and amplitude at onset, midpoint, and offset of the vowel nucleus.

    Returns dict with:
      f0_onset, f0_mid, f0_offset  — Hz (or None if unvoiced)
      f0_mean, f0_min, f0_max      — Hz over n_points
      amplitude_db                 — mean intensity dB
      f0_10pt                      — list of 10 F0 values (for velocity)
      voiced                       — True if >30% voiced frames
    """
    dur = nuc_end - nuc_start
    if dur <= 0.005:  # < 5 ms — too short to measure reliably
        return {"f0_onset": None, "f0_mid": None, "f0_offset": None,
                "f0_mean": None, "f0_min": None, "f0_max": None,
                "amplitude_db": None, "f0_10pt": [], "voiced": False,
                "velocity_st_s": None, "excursion_st": None}

    # 10 evenly-spaced points across nucleus (ProsodyPro-style time-normalisation)
    ts = [nuc_start + dur * j / (n_points - 1) for j in range(n_points)]

    f0_vals_raw = []
    intens_vals = []
    for t in ts:
        f0 = None
        try:
            hz = float(pitch.get_value_at_time(t))
            if hz and not math.isnan(hz) and hz > 30:
                f0 = hz
        except Exception:
            pass
        f0_vals_raw.append(f0)

        try:
            db = float(intensity.get_value(t))
            if not math.isnan(db):
                intens_vals.append(db)
        except Exception:
            pass

    # ProsodyPro-inspired trimming: remove octave spikes, then smooth
    f0_vals = trim_f0_xu1999(f0_vals_raw)

    voiced_vals = [v for v in f0_vals if v is not None]
    voiced = len(voiced_vals) / n_points > 0.3

    # Onset = first voiced value, mid = middle, offset = last voiced
    f0_onset = next((v for v in f0_vals if v), None)
    f0_offset = next((v for v in reversed(f0_vals) if v), None)
    # Mid = voiced value closest to 50%
    mid_idx = n_points // 2
    f0_mid = None
    for delta in range(n_points // 2 + 1):
        for idx in (mid_idx - delta, mid_idx + delta):
            if 0 <= idx < n_points and f0_vals[idx] is not None:
                f0_mid = f0_vals[idx]
                break
        if f0_mid is not None:
            break

    f0_mean = _safe_mean(voiced_vals)
    f0_min = min(voiced_vals) if voiced_vals else None
    f0_max = max(voiced_vals) if voiced_vals else None

    # Velocity = semitones per second from onset to offset
    velocity = None
    if f0_onset and f0_offset and dur > 0:
        mv = _st(f0_onset, f0_offset)
        if mv is not None:
            velocity = mv / dur

    excursion = _st(f0_min, f0_max) if f0_min and f0_max else None

    return {
        "f0_onset": f0_onset, "f0_mid": f0_mid, "f0_offset": f0_offset,
        "f0_mean": f0_mean, "f0_min": f0_min, "f0_max": f0_max,
        "amplitude_db": _safe_mean(intens_vals),
        "f0_10pt": f0_vals,
        "voiced": voiced,
        "velocity_st_s": velocity,
        "excursion_st": excursion,
    }


def f0_label(m: dict) -> str:
    """Build the F0 measurement tier label: 'onset|offset Hz  Amp dB'

    Format requested by evaluator: F0 at beginning and end of vowel + amplitude.
    """
    def hz(v): return f"{int(round(v))}" if v else "?"
    amp = f"{round(m['amplitude_db'], 1)}dB" if m["amplitude_db"] else "?"
    return f"{hz(m['f0_onset'])}|{hz(m['f0_offset'])}Hz  {amp}"


# ============================================================================
# PROSODY LABELS (relative to neighbours)
# ============================================================================

def label_prosody_relative(syllables: list[dict]) -> None:
    """Add prosody symbols relative to ±1 neighbour syllables.

    Uses recording-level normalisation: the weak rise/fall threshold is set
    to max(FLOOR, ADAPTIVE_FACTOR × std_dev_of_all_pitch_movements_in_this_recording).
    This makes the labeller sensitive to the actual pitch range of the speaker
    rather than a fixed semitone floor — following the recommendation from
    evaluation feedback (Prof. Krifka, 30 May 2026): compressed conversational
    speech has a narrow pitch range; a fixed 1.5 ST floor suppresses most labels.
    """
    import statistics as _stats

    n = len(syllables)
    if n == 0:
        return

    # First pass: compute movements for all syllables
    for syl in syllables:
        mv = _st(syl.get("f0_onset"), syl.get("f0_offset"))
        vel = syl.get("velocity_st_s")
        syl["_mv"] = mv
        syl["_vel"] = vel

    # Recording-level adaptive thresholds
    mvs_valid = [abs(syl["_mv"]) for syl in syllables if syl["_mv"] is not None]
    if len(mvs_valid) >= 2:
        rec_std = _stats.stdev(mvs_valid)
    else:
        rec_std = 2.0  # fallback if too few voiced syllables
    weak_thr   = max(WEAK_RISE_FLOOR_ST,  ADAPTIVE_FACTOR * rec_std)
    strong_thr = max(weak_thr * STRONG_FACTOR, 2.0)

    for i, syl in enumerate(syllables):
        mv = syl["_mv"]
        vel = syl["_vel"]
        f0_mean = syl.get("f0_mean")
        amp = syl.get("amplitude_db")

        # ---- neighbour mean F0, amplitude, and duration ----
        nbr_f0 = []
        nbr_amp = []
        nbr_dur = []
        for j in (i - 1, i + 1):
            if 0 <= j < n:
                v = syllables[j].get("f0_mean")
                a = syllables[j].get("amplitude_db")
                d = syllables[j]["end"] - syllables[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)

        nbr_mean_f0 = _safe_mean(nbr_f0)
        nbr_mean_amp = _safe_mean(nbr_amp)
        # Duration prominence: syllable is "long" when ≥DURATION_ACCENT_FACTOR × neighbour mean
        syl_dur = syl["end"] - syl["start"]
        nbr_mean_dur = _safe_mean(nbr_dur) if nbr_dur else None
        is_long = (nbr_mean_dur is not None and syl_dur >= DURATION_ACCENT_FACTOR * nbr_mean_dur)

        # ---- height relative to neighbours ----
        height_st = _st(nbr_mean_f0, f0_mean) if (nbr_mean_f0 and f0_mean) else None
        is_high = height_st is not None and height_st >= HIGH_NBR_ST
        is_low = height_st is not None and height_st <= -LOW_NBR_ST

        # ---- amplitude prominence relative to neighbours ----
        amp_above = (amp - nbr_mean_amp) if (amp and nbr_mean_amp) else None
        is_loud = amp_above is not None and amp_above >= ACCENT_AMP_DB

        # ---- pitch direction (intra-syllable movement) ----
        strong = (abs(mv) >= strong_thr if mv else False) or \
                 (abs(vel) >= VELOCITY_STRONG_ST_S if vel else False)

        if mv is None:
            direction = ""  # unvoiced/unknown
        elif mv >= weak_thr:
            direction = "//" if strong else "/"
        elif mv <= -weak_thr:
            direction = "\\\\" if strong else "\\"
        else:
            direction = ""  # level — height takes over

        # ---- height symbol (used when direction is level or absent) ----
        if direction == "":
            if is_high:
                height_sym = "-"   # high level (use - for ASCII; render as – in docs)
            elif is_low:
                height_sym = "_"
            else:
                height_sym = "-" if (f0_mean and nbr_mean_f0) else "?"
        else:
            # When direction is present, height adds extra context
            if is_high:
                height_sym = "-"
            elif is_low:
                height_sym = "_"
            else:
                height_sym = ""

        # ---- accent (*) ----
        # Classic cue: louder AND higher than neighbours.
        # Duration cue: also trigger * when syllable is distinctly longer AND
        # louder, even if the F0 height difference is marginal — this catches
        # focus accents where the pitch peak rides the amplitude shift rather
        # than a clear height step (feedback: "flew" missed because dB alone
        # wasn't enough but duration + amplitude together signal the accent).
        is_accent = (
            (is_loud and height_st is not None and height_st >= ACCENT_F0_ST)
            or (is_long and is_loud and is_high)
        )

        # ---- assemble symbol ----
        # Format: [*][height][direction]
        # Examples: */  *\  *-  _\  -/  //  \\
        symbol = ""
        if is_accent:
            symbol += "*"
        if height_sym and direction:
            symbol += height_sym + direction    # e.g. -/ or _\
        elif height_sym:
            symbol += height_sym               # e.g. - or _
        elif direction:
            symbol += direction                # e.g. / or //

        if not symbol:
            symbol = "?" if not f0_mean else "-"

        syl["symbol"] = symbol
        syl["is_accent"] = is_accent


# ============================================================================
# SYLLABIFICATION from phones (with vowel-nucleus annotation)
# ============================================================================

def group_phones_into_syllables(phones: list[str], word_start: float, word_end: float,
                                  mfa_ivs: list[dict] | None = None) -> list[dict]:
    """Group phones into syllables. Returns list of {label, start, end, phones, vowel_start, vowel_end}."""
    if not phones:
        return []

    # Find vowel positions → syllable nuclei
    is_vowel = [_is_vowel(p) for p in phones]
    vowel_idx = [i for i, v in enumerate(is_vowel) if v]
    if not vowel_idx:
        # All consonants — one syllable covering the whole word
        v_start, v_end = find_vowel_nucleus(phones, word_start, word_end, mfa_ivs)
        return [{"label": "".join(phones), "start": word_start, "end": word_end,
                 "phones": phones, "vowel_start": v_start, "vowel_end": v_end}]

    # Build syllable spans using maximum-onset principle
    boundaries = []  # (phone_idx_start, phone_idx_end_exclusive) for each syllable
    for k, vi in enumerate(vowel_idx):
        if k == 0:
            onset_start = 0
        else:
            prev_vi = vowel_idx[k - 1]
            gap = vi - prev_vi - 1
            # Max-onset: split consonant cluster, give first half to coda, rest to onset
            cut = prev_vi + 1 + (gap // 2) if gap > 0 else prev_vi + 1
            # Close previous syllable up to cut, start new from cut
            if boundaries:
                prev = boundaries[-1]
                boundaries[-1] = (prev[0], cut)
            onset_start = cut
        if k == len(vowel_idx) - 1:
            boundaries.append((onset_start, len(phones)))
        else:
            boundaries.append((onset_start, vi + 1))

    # Now build timing for each syllable
    total_phones = len(phones)
    word_dur = word_end - word_start
    syllables = []
    for bi, (ps, pe) in enumerate(boundaries):
        syl_phones = phones[ps:pe]
        s0 = word_start + word_dur * ps / total_phones
        s1 = word_start + word_dur * pe / total_phones
        if bi == len(boundaries) - 1:
            s1 = word_end
        label = "".join(syl_phones)
        v_start, v_end = find_vowel_nucleus(syl_phones, s0, s1, mfa_ivs)
        syllables.append({
            "label": label, "start": s0, "end": s1,
            "phones": syl_phones,
            "vowel_start": v_start, "vowel_end": v_end,
        })
    return syllables


# ============================================================================
# TEXTGRID WRITER
# ============================================================================

def _fill_gaps(rows: list[dict], xmax: float) -> list[dict]:
    out = []
    cursor = 0.0
    for r in rows:
        s = float(r["start"])
        e = float(r["end"])
        if s > cursor + 5e-4:
            out.append({"start": cursor, "end": s, "value": ""})
        out.append({"start": s, "end": e, "value": r.get("value", "")})
        cursor = max(cursor, e)
    if cursor < xmax - 5e-4:
        out.append({"start": cursor, "end": xmax, "value": ""})
    return out


def write_textgrid(path: Path, xmax: float, tiers: list[dict]) -> None:
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {xmax}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for ti, tier in enumerate(tiers, 1):
        rows = _fill_gaps(tier["rows"], xmax)
        lines += [
            f"    item [{ti}]:",
            '        class = "IntervalTier"',
            f'        name = "{_esc(tier["name"])}"',
            "        xmin = 0",
            f"        xmax = {xmax}",
            f"        intervals: size = {len(rows)}",
        ]
        for ii, row in enumerate(rows, 1):
            lines += [
                f"        intervals [{ii}]:",
                f"            xmin = {row['start']}",
                f"            xmax = {row['end']}",
                f'            text = "{_esc(row["value"])}"',
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================================
# MAIN BUILD
# ============================================================================

def build(json_path: Path, wav_path: Path, output_path: Path,
          backend_label: str, has_mfa_phones: bool = False):

    print(f"\nBuilding final TextGrid: {backend_label}", flush=True)
    data = load_backend_json(json_path)

    words = data["words"]       # [{start, end, word}]
    phones_by_word = data["phonemes"]   # [{start, end, label}] proportional phones
    mfa_phones = data.get("mfa_phones", [])  # [{start, end, label}] MFA phones if available

    duration = float(data.get("duration_s",
                     max((w["end"] for w in words), default=0.0) + 0.1
                     if words else 10.0))

    # Read the JSON's duration from the WAV if not present
    if duration <= 0:
        import wave
        with wave.open(str(wav_path)) as wf:
            duration = wf.getnframes() / wf.getframerate()

    # Load acoustics — use to_pitch_ac with higher octave_jump_cost (0.5 vs
    # default 0.35) to discourage Praat from jumping an octave on noisy frames;
    # residual spikes are cleaned by trim_f0_xu1999 below.
    try:
        import parselmouth
        snd = parselmouth.Sound(str(wav_path))
        pitch_obj = snd.to_pitch_ac(
            pitch_floor=75.0,
            pitch_ceiling=600.0,
            octave_jump_cost=0.5,
        )
        intens_obj = snd.to_intensity()
    except Exception as e:
        print(f"  ! Parselmouth failed: {e}", flush=True)
        snd = pitch_obj = intens_obj = None

    # Phonemize words to get IPA
    word_strings = [w["word"] for w in words]
    lang = data.get("language", "en")

    try:
        from phonemizer import phonemize
        from phonemizer.separator import Separator
        from evaluate_aligners import ESPEAK_LANG
        espeak_lang = ESPEAK_LANG.get(lang, "en-us")
        ipa_raw = phonemize(
            word_strings, language=espeak_lang, backend="espeak",
            separator=Separator(phone=" ", word=" | ", syllable=""),
            strip=True, preserve_punctuation=False, with_stress=False, njobs=1,
        )
        if isinstance(ipa_raw, str):
            ipa_raw = [ipa_raw]
        phones_per_word = [[p for p in (line or "").split() if p and p != "|"]
                           for line in ipa_raw]
    except Exception as e:
        print(f"  ! phonemizer: {e}", flush=True)
        phones_per_word = [[] for _ in words]

    # ---- Build word tier (with silence labels) ----
    word_rows = []
    prev_end = 0.0
    for w in words:
        gap = w["start"] - prev_end
        if gap > 0.04:   # > 40 ms gap → mark as silence
            word_rows.append({
                "start": prev_end, "end": w["start"],
                "value": f"<sil {gap:.2f}s>"
            })
        word_rows.append({"start": w["start"], "end": w["end"], "value": w["word"]})
        prev_end = w["end"]

    # ---- Build phoneme tier (prefer MFA phones, else proportional) ----
    if has_mfa_phones and mfa_phones:
        phone_rows = [{"start": p["start"], "end": p["end"], "value": p["label"]}
                      for p in mfa_phones if p["label"] not in SILENCE_LABELS]
    else:
        phone_rows = [{"start": p["start"], "end": p["end"], "value": p["label"]}
                      for p in phones_by_word if p.get("label", "") not in SILENCE_LABELS]

    # ---- Build syllables and measure F0 at vowel nucleus ----
    syllable_rows = []
    f0_rows = []
    prosody_rows = []
    all_syllables = []

    mfa_iv_list = mfa_phones if has_mfa_phones and mfa_phones else None

    for wi, (w, phones) in enumerate(zip(words, phones_per_word)):
        sylls = group_phones_into_syllables(phones, w["start"], w["end"], mfa_iv_list)
        for syl in sylls:
            # Measure F0 at vowel nucleus
            meas = {}
            if pitch_obj and intens_obj:
                meas = measure_vowel_f0(snd, pitch_obj, intens_obj,
                                        syl["vowel_start"], syl["vowel_end"])
            syl.update(meas)
            syl["word_idx"] = wi
            all_syllables.append(syl)
            syllable_rows.append({"start": syl["start"], "end": syl["end"],
                                   "value": syl["label"]})

    # Compute prosody relative to neighbours
    label_prosody_relative(all_syllables)

    for syl in all_syllables:
        f0_rows.append({"start": syl["start"], "end": syl["end"],
                        "value": f0_label(syl) if syl.get("f0_onset") else ""})
        prosody_rows.append({"start": syl["start"], "end": syl["end"],
                              "value": syl.get("symbol", "?")})

    # ---- Write TextGrid ----
    tiers = [
        {"name": "words",    "rows": word_rows},
        {"name": "phonemes", "rows": phone_rows},
        {"name": "syllables","rows": syllable_rows},
        {"name": "f0_vowel", "rows": f0_rows},
        {"name": "prosody",  "rows": prosody_rows},
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_textgrid(output_path, duration, tiers)

    print(f"  Words:    {len(word_rows)} intervals", flush=True)
    print(f"  Phonemes: {len(phone_rows)} intervals {'(MFA phone-level)' if has_mfa_phones and mfa_phones else '(proportional)'}", flush=True)
    print(f"  Syllables:{len(syllable_rows)} intervals", flush=True)
    print(f"  F0 meas:  {sum(1 for r in f0_rows if r['value'])} voiced syllables", flush=True)
    print(f"  Written:  {output_path}", flush=True)

    # Print a sample of the prosody output
    accented = [s for s in all_syllables if s.get("is_accent")]
    print(f"  Accented syllables (*): {len(accented)}", flush=True)
    for s in accented[:5]:
        print(f"    [{s['label']}] {s['symbol']}  F0: {s.get('f0_onset') and int(s['f0_onset'])}→"
              f"{s.get('f0_offset') and int(s['f0_offset'])} Hz", flush=True)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    p = argparse.ArgumentParser(description="Build final SpeechPrint TextGrid")
    p.add_argument("--json", required=True, help="Backend JSON (from evaluate_aligners.py)")
    p.add_argument("--wav", required=True, help="WAV file")
    p.add_argument("--output", required=True, help="Output TextGrid path")
    p.add_argument("--backend", required=True, help="Backend label (mfa / whisperx)")
    p.add_argument("--mfa-phones", action="store_true", help="JSON contains mfa_phones")
    args = p.parse_args()

    build(
        json_path=Path(args.json),
        wav_path=Path(args.wav),
        output_path=Path(args.output),
        backend_label=args.backend,
        has_mfa_phones=args.mfa_phones,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
