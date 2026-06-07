"""SpeechPrint analysis pipeline.

Pipeline stages (see annotate() for the staged-progress log):
    1. Load audio
    2. Transcribe with Whisper / WhisperX
    3. Prepare transcript for alignment
    4. Force-align words to audio (WhisperX align if available)
    5. Extract pitch, intensity, formants (Parselmouth)
    6. Build IPA / phone layer (phonemizer/espeak)
    7. Build symbolic prosody layer (adaptive thresholds)
    8. Write Praat TextGrid (6 tiers)
    9. Export CSVs (words, syllables, phonemes, prosody)

Tier set produced (per CLAUDE.md, in this order):
    1. words              — IntervalTier, word-level
    2. syllables          — IntervalTier, syllable-level
    3. phonemes           — IntervalTier, IPA phones
    4. f0_pitch           — IntervalTier, mean f0 per syllable in Hz
    5. prosody_labels     — IntervalTier, / \\ – per syllable, * on strongest
    6. warnings_review    — IntervalTier, single warning span if anything fell back
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import statistics
import sys
import wave
import zipfile
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# CONSTANTS
# ============================================================================

# Stage names — match the user-facing progress display
STAGES = [
    "Loading audio",
    "Transcribing speech with Whisper",
    "Preparing transcript for alignment",
    "Running forced alignment",
    "Extracting pitch, intensity, and formants",
    "Creating IPA / phone layer",
    "Creating symbolic prosody layer",
    "Writing Praat TextGrid",
    "Exporting CSV / ZIP",
]

# Adaptive prosody thresholds (recording-normalised).
# Weak rise/fall: movement > max(FLOOR, FACTOR × std_dev_of_recording)
# Strong rise/fall: movement > STRONG_FACTOR × weak_threshold → // or \\
F0_RISE_FLOOR_ST  = 0.5   # floor for weak / label (was 3.0 — too insensitive)
F0_FALL_FLOOR_ST  = 0.5   # floor for weak \ label
F0_STD_FACTOR     = 0.35  # adaptive factor (was 0.75)
F0_STRONG_FACTOR  = 2.5   # strong threshold = STRONG_FACTOR × weak threshold → // \\
F0_VELOCITY_STRONG_ST_S = 6.0  # ST/s — also triggers // or \\ regardless of amplitude

# Vowel sets used for syllabification proxies when no MFA model is available.
VOWELS_LATIN = set("aeiouyAEIOUYäöüÄÖÜáéíóúàèìòùÁÉÍÓÚÀÈÌÒÙâêîôûÂÊÎÔÛ")
VOWELS_IPA = set(
    "aeiouæɑɒɐəɚɛɜɝɪɨɔøœuʊʌyɯɵɘɤɞɛ̞ɔ̞ɑ̃ɛ̃ɔ̃œ̃ã"
    "iɪeɛæaɑɒɔoʊuʌəɝɚy"
)


# ============================================================================
# UTILITIES
# ============================================================================


def _stage(num: int, message: Optional[str] = None, log_file: Optional[Path] = None) -> None:
    """Print a numbered stage marker for the GUI's staged-progress display."""
    if num <= 0 or num > len(STAGES):
        return
    name = STAGES[num - 1]
    line = f"[{num}/{len(STAGES)}] {name}"
    if message:
        line += f" — {message}"
    print(line, flush=True)
    if log_file is not None:
        try:
            with log_file.open("a") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


def _safe_mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else None


def _safe_std(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(xs) < 2:
        return 0.0
    return statistics.pstdev(xs)


def _semitone(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12 * math.log2(b / a)


def wav_info(path: Path) -> dict:
    """Return basic WAV header info for the manifest."""
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return {
            "sample_rate": rate,
            "channels": w.getnchannels(),
            "sample_width": w.getsampwidth(),
            "frames": frames,
            "duration_seconds": frames / rate if rate else 0,
        }


# ============================================================================
# STAGE 2: TRANSCRIBE  (WhisperX)
# ============================================================================


def transcribe(path: Path, language: str = "en") -> dict:
    """Run WhisperX (or whisper) transcription. Returns dict with:

        text     — full string, no punctuation, lowercased
        segments — list of {start, end, text, words?}  (WhisperX format)
        source   — "whisperx" | "whisper" | "filename"
    """
    # Try WhisperX first (gives us word-level timestamps in stage 4)
    try:
        import os, whisperx
        # Point to locally cached large-v3 model (avoids download)
        _hf_cache = "/home/lydia/School/UPF/thesis260512/tools/hf_cache"
        if os.path.isdir(_hf_cache):
            os.environ["HF_HOME"] = _hf_cache
        # vad_options: lower onset/offset so speech start is detected earlier
        # (fixes the "eine" onset-too-late bug on short recordings)
        model = whisperx.load_model(
            "large-v3", device="cpu", compute_type="int8",
            language=language,
            vad_options={"vad_onset": 0.3, "vad_offset": 0.2},
        )
        result = model.transcribe(str(path), language=language, batch_size=4)
        segments = result.get("segments", [])
        text = " ".join(seg.get("text", "") for seg in segments).strip()
        text_clean = re.sub(r"[^A-Za-zÀ-ÿ0-9 ']+", " ", text).strip().lower()
        text_clean = re.sub(r"\s+", " ", text_clean)
        if text_clean and segments:
            return {
                "text": text_clean,
                "segments": segments,
                "language": result.get("language", language),
                "source": "whisperx",
            }
    except Exception as e:
        print(f"  ! WhisperX unavailable, trying openai-whisper: {e}", flush=True)

    # Fall back to plain whisper
    try:
        import whisper
        model = whisper.load_model("large")
        result = model.transcribe(str(path), language=language)
        segments = result.get("segments", [])
        text = result.get("text", "").strip()
        text_clean = re.sub(r"[^A-Za-zÀ-ÿ0-9 ']+", " ", text).strip().lower()
        text_clean = re.sub(r"\s+", " ", text_clean)
        if text_clean:
            return {
                "text": text_clean,
                "segments": segments,
                "language": result.get("language", language),
                "source": "whisper",
            }
    except Exception as e:
        print(f"  ! whisper unavailable, falling back to filename: {e}", flush=True)

    # Last resort: use filename
    fallback = re.sub(r"[_\-\d]+", " ", path.stem).strip().lower()
    return {
        "text": fallback or path.stem,
        "segments": [],
        "language": language,
        "source": "filename",
    }


# ============================================================================
# STAGES 3 + 4: PREPARE TRANSCRIPT, FORCED-ALIGN
# ============================================================================


def align_words(
    path: Path,
    transcript: dict,
    language: str = "en",
) -> tuple[list[dict], list[str]]:
    """Run forced alignment. Returns (word_intervals, warnings).

    word_intervals is a list of {start, end, word} dicts.
    Falls back to equal-width division of speech span if alignment unavailable.
    """
    warnings: list[str] = []
    segments = transcript.get("segments", [])

    # Path A: WhisperX has an align step that returns word-level timing
    try:
        import whisperx
        import torch

        align_model, metadata = whisperx.load_align_model(
            language_code=language,
            device="cpu",
        )
        aligned = whisperx.align(
            segments,
            align_model,
            metadata,
            str(path),
            device="cpu",
            return_char_alignments=False,
        )
        words = []
        for seg in aligned.get("segments", []):
            for w in seg.get("words", []):
                start = w.get("start")
                end = w.get("end")
                token = (w.get("word") or "").strip().lower()
                token = re.sub(r"[^a-zà-ÿ0-9']+", "", token)
                if start is None or end is None or not token:
                    continue
                if end <= start:
                    continue
                words.append({"start": float(start), "end": float(end), "word": token})
        if words:
            return words, warnings
        warnings.append("WhisperX align returned no words; falling back")
    except Exception as e:
        warnings.append(f"WhisperX align unavailable: {e}")

    # Path B: derive timing from raw whisper segments + word-level proportional split
    text_words = [w for w in transcript.get("text", "").split() if w]
    if not text_words:
        warnings.append("No transcript words to align")
        return [], warnings

    # Sum the per-segment spans, then distribute words proportionally
    spans = []
    for seg in segments:
        s = float(seg.get("start", 0.0) or 0.0)
        e = float(seg.get("end", 0.0) or 0.0)
        if e > s:
            spans.append((s, e, (seg.get("text") or "").strip().split()))
    if spans:
        words = []
        for s, e, seg_tokens in spans:
            n = max(1, len(seg_tokens))
            span = e - s
            for i, tok in enumerate(seg_tokens):
                t0 = s + span * i / n
                t1 = s + span * (i + 1) / n
                clean = re.sub(r"[^a-zà-ÿ0-9']+", "", tok.lower())
                if not clean:
                    continue
                words.append({"start": t0, "end": t1, "word": clean})
        if words:
            warnings.append("Word timing estimated from segment splits, not phonetic alignment")
            return words, warnings

    # Path C: equal division of whole speech span (worst case)
    info = wav_info(path)
    dur = info["duration_seconds"]
    # Try to find a usable speech span from any segments
    starts = [float(s.get("start", 0.0) or 0.0) for s in segments]
    ends = [float(s.get("end", 0.0) or 0.0) for s in segments]
    speech_start = min(starts) if starts else 0.0
    speech_end = max(ends) if ends else dur
    if speech_end <= speech_start:
        speech_start, speech_end = 0.0, dur
    n = len(text_words)
    span = speech_end - speech_start
    words = [
        {
            "start": speech_start + span * i / n,
            "end": speech_start + span * (i + 1) / n,
            "word": w,
        }
        for i, w in enumerate(text_words)
    ]
    warnings.append("Word timing is equal-width fallback (no aligner available)")
    return words, warnings


# ============================================================================
# STAGE 6: PHONEMES via espeak-ng / phonemizer
# ============================================================================


# espeak language codes used by phonemizer
ESPEAK_LANG = {
    "en": "en-us",
    "de": "de",
    "it": "it",
    "es": "es",
    "fr": "fr-fr",
    "cs": "cs",
}


def phonemize_words(words: list[str], language: str) -> tuple[list[list[str]], Optional[str]]:
    """Return per-word lists of IPA phones. Second value is an error message if any."""
    if not words:
        return [], None
    try:
        from phonemizer import phonemize
        from phonemizer.separator import Separator
    except Exception as e:
        return [[] for _ in words], f"phonemizer not installed: {e}"

    lang = ESPEAK_LANG.get(language, "en-us")
    try:
        ipa = phonemize(
            words,
            language=lang,
            backend="espeak",
            separator=Separator(phone=" ", word=" | ", syllable=""),
            strip=True,
            preserve_punctuation=False,
            with_stress=False,
            njobs=1,
        )
    except Exception as e:
        return [[] for _ in words], f"phonemize failed: {e}"

    out: list[list[str]] = []
    if isinstance(ipa, str):
        ipa = [ipa]
    for line in ipa:
        phones = [p for p in (line or "").split() if p and p != "|"]
        out.append(phones)
    return out, None


def split_phones_into_syllables(phones: list[str]) -> list[list[str]]:
    """Group a flat list of phones into syllables. One vowel = one syllable nucleus.

    Onset consonants attach to the following vowel; coda consonants stay with the
    preceding vowel. This is the "maximal onset" heuristic — good enough for a
    proxy when MFA isn't available.
    """
    if not phones:
        return []
    # Find vowel positions
    is_vowel = [any(ch in VOWELS_IPA for ch in p) for p in phones]
    vowel_idx = [i for i, v in enumerate(is_vowel) if v]
    if not vowel_idx:
        return [phones]  # all consonants — treat as one chunk

    sylls: list[list[str]] = []
    for k, vi in enumerate(vowel_idx):
        # Onset: consonants from end of previous nucleus span up to this vowel
        if k == 0:
            onset_start = 0
        else:
            prev_vi = vowel_idx[k - 1]
            gap = vi - prev_vi - 1
            # Split consonant cluster: leave one consonant as coda of prev syllable
            # and give the rest as onset of this syllable (max-onset principle).
            cut = prev_vi + 1 + (gap // 2) if gap > 0 else prev_vi + 1
            onset_start = cut
            # Append coda to previous syllable
            if sylls and cut > prev_vi + 1:
                sylls[-1].extend(phones[prev_vi + 1: cut])

        # Coda for last vowel = everything after it
        if k == len(vowel_idx) - 1:
            sylls.append(phones[onset_start:])
        else:
            sylls.append(phones[onset_start: vi + 1])
    return sylls


def syllabify_word_proxy(word: str, n_phones_hint: int = 0) -> list[str]:
    """Latin-letter fallback when phonemes aren't available."""
    if not word:
        return []
    chunks: list[str] = []
    cur = ""
    for i, ch in enumerate(word):
        cur += ch
        nxt = word[i + 1] if i + 1 < len(word) else ""
        if ch in VOWELS_LATIN and nxt and nxt not in VOWELS_LATIN:
            if len(cur) > 1:
                chunks.append(cur)
                cur = ""
    if cur:
        if chunks:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks or [word]


def syllables_for_word(
    word: str,
    word_phones: list[str],
    word_start: float,
    word_end: float,
) -> tuple[list[dict], list[list[str]]]:
    """Build syllable intervals + their phone lists for a single word.

    Returns (syllable_dicts, syll_phone_lists).
    Syllable timing within the word is proportional to phone count.
    """
    if word_phones:
        syll_phone_lists = split_phones_into_syllables(word_phones)
        # Distribute syllable spans proportionally to phone count
        total_phones = sum(len(s) for s in syll_phone_lists)
        if total_phones == 0:
            syll_phone_lists = [word_phones]
            total_phones = len(word_phones)
        spans = []
        cursor = word_start
        word_dur = word_end - word_start
        for syll_phones in syll_phone_lists:
            frac = len(syll_phones) / total_phones
            s_end = cursor + word_dur * frac
            spans.append((cursor, s_end))
            cursor = s_end
        # Final adjustment to land exactly on word_end
        if spans:
            spans[-1] = (spans[-1][0], word_end)

        # Generate orthographic syllable labels by re-syllabifying the word.
        ortho_sylls = syllabify_word_proxy(word)
        if len(ortho_sylls) != len(syll_phone_lists):
            # Mismatch — fall back to phone-count labels
            ortho_sylls = [
                "".join(p) for p in syll_phone_lists
            ]

        out = []
        for label, (s0, s1), syll_phones in zip(ortho_sylls, spans, syll_phone_lists):
            out.append({
                "label": label,
                "start": s0,
                "end": s1,
                "phones": list(syll_phones),
            })
        return out, syll_phone_lists

    # No phones available — proxy by orthography, equal split within word.
    ortho_sylls = syllabify_word_proxy(word)
    n = len(ortho_sylls)
    word_dur = word_end - word_start
    out = []
    for i, label in enumerate(ortho_sylls):
        s0 = word_start + word_dur * i / n
        s1 = word_start + word_dur * (i + 1) / n
        out.append({"label": label, "start": s0, "end": s1, "phones": []})
    return out, [[] for _ in ortho_sylls]


# ============================================================================
# STAGE 5: ACOUSTIC FEATURES  (Parselmouth)
# ============================================================================


def acoustic_features(path: Path, intervals: list[dict]) -> tuple[list[dict], list[str]]:
    """Add f0, intensity, formants to each interval dict. Returns (rows, warnings).

    Each input interval must have {start, end}. We mutate in place and also
    return the list for convenience.
    """
    warnings: list[str] = []
    try:
        import parselmouth
    except Exception as e:
        warnings.append(f"parselmouth unavailable: {e}")
        for r in intervals:
            r.update({
                "mean_f0_hz": None, "min_f0_hz": None, "max_f0_hz": None,
                "onset_f0_hz": None, "offset_f0_hz": None,
                "mean_intensity_db": None,
                "f1_hz": None, "f2_hz": None, "f3_hz": None,
                "voiced_frames": 0,
            })
        return intervals, warnings

    snd = parselmouth.Sound(str(path))
    try:
        pitch = snd.to_pitch()
    except Exception as e:
        warnings.append(f"pitch extraction failed: {e}")
        pitch = None
    try:
        intensity = snd.to_intensity()
    except Exception as e:
        warnings.append(f"intensity extraction failed: {e}")
        intensity = None
    try:
        formant = snd.to_formant_burg()
    except Exception as e:
        warnings.append(f"formant extraction failed: {e}")
        formant = None

    for row in intervals:
        s = float(row["start"])
        e = float(row["end"])
        if e <= s:
            row.update({
                "mean_f0_hz": None, "min_f0_hz": None, "max_f0_hz": None,
                "onset_f0_hz": None, "offset_f0_hz": None,
                "mean_intensity_db": None,
                "f1_hz": None, "f2_hz": None, "f3_hz": None,
                "voiced_frames": 0,
            })
            continue
        ts = [s + (e - s) * j / 9 for j in range(10)]
        f0s, intens = [], []
        for t in ts:
            if pitch is not None:
                try:
                    hz = float(pitch.get_value_at_time(t))
                    if hz and not math.isnan(hz) and hz > 0:
                        f0s.append(hz)
                except Exception:
                    pass
            if intensity is not None:
                try:
                    db = float(intensity.get_value(t))
                    if not math.isnan(db):
                        intens.append(db)
                except Exception:
                    pass

        row["mean_f0_hz"] = _safe_mean(f0s)
        row["min_f0_hz"] = min(f0s) if f0s else None
        row["max_f0_hz"] = max(f0s) if f0s else None
        row["onset_f0_hz"] = f0s[0] if f0s else None
        row["offset_f0_hz"] = f0s[-1] if f0s else None
        row["mean_intensity_db"] = _safe_mean(intens)
        row["voiced_frames"] = len(f0s)

        mid = (s + e) / 2
        f1 = f2 = f3 = None
        if formant is not None:
            for fi, key in [(1, "f1"), (2, "f2"), (3, "f3")]:
                try:
                    v = float(formant.get_value_at_time(fi, mid))
                    if not math.isnan(v):
                        if key == "f1": f1 = v
                        elif key == "f2": f2 = v
                        else: f3 = v
                except Exception:
                    pass
        row["f1_hz"], row["f2_hz"], row["f3_hz"] = f1, f2, f3

    return intervals, warnings


# ============================================================================
# STAGE 7: SYMBOLIC PROSODY LABELS  (adaptive thresholds)
# ============================================================================


def label_prosody(syllables: list[dict]) -> None:
    """Mutate syllables to add symbolic prosody labels in place.

    Adds:
        pitch_movement_st  — semitones from onset to offset f0
        pitch_movement     — "rising" / "falling" / "level" / "unknown"
        symbol             — "/" / "\\" / "–" / "?"
        relative_height_st — semitones above mean of all syllables
        prominence_score   — composite score used for ranking
        is_prominent       — True for the strongest accent (gets "*")
    """
    if not syllables:
        return

    # First pass: pitch movement per syllable
    movements: list[Optional[float]] = []
    for syl in syllables:
        mv = _semitone(syl.get("onset_f0_hz"), syl.get("offset_f0_hz"))
        movements.append(mv)
        syl["pitch_movement_st"] = mv

    # Adaptive thresholds (recording-normalised).
    std_mv = _safe_std(movements)
    weak_rise  = max(F0_RISE_FLOOR_ST, F0_STD_FACTOR * std_mv)
    weak_fall  = -max(F0_FALL_FLOOR_ST, F0_STD_FACTOR * std_mv)
    strong_thr = max(weak_rise * F0_STRONG_FACTOR, 2.0)  # absolute floor for //

    # Mean f0 for relative_height_st
    f0_values = [s.get("mean_f0_hz") for s in syllables if s.get("mean_f0_hz")]
    mean_f0 = _safe_mean(f0_values) if f0_values else None

    for syl in syllables:
        mv = syl["pitch_movement_st"]
        vel = None  # velocity not tracked in cli path; reserved for future use

        if mv is None:
            syl["pitch_movement"] = "unknown"
            syl["symbol"] = "?"
        elif mv >= strong_thr:
            syl["pitch_movement"] = "rising"
            syl["symbol"] = "//"
        elif mv >= weak_rise:
            syl["pitch_movement"] = "rising"
            syl["symbol"] = "/"
        elif mv <= -strong_thr:
            syl["pitch_movement"] = "falling"
            syl["symbol"] = "\\\\"
        elif mv <= weak_fall:
            syl["pitch_movement"] = "falling"
            syl["symbol"] = "\\"
        else:
            syl["pitch_movement"] = "level"
            syl["symbol"] = "–"

        syl["relative_height_st"] = (
            _semitone(mean_f0, syl["mean_f0_hz"]) if (mean_f0 and syl.get("mean_f0_hz")) else None
        )

        # Composite prominence — used both to mark the strongest accent
        # and to set stress_class for downstream tools.
        height = abs(syl.get("relative_height_st") or 0.0)
        movement = abs(mv or 0.0)
        intensity_score = 0.0
        if syl.get("mean_intensity_db") is not None:
            intensity_score = max(0.0, (syl["mean_intensity_db"] + 50.0) / 25.0)
        syl["prominence_score"] = height + movement + intensity_score

    # Mark strongest accent with *
    strongest_idx = max(range(len(syllables)), key=lambda i: syllables[i]["prominence_score"])
    for i, syl in enumerate(syllables):
        syl["is_prominent"] = (i == strongest_idx)
        if syl["is_prominent"] and syl["symbol"] != "?":
            syl["symbol_marked"] = "*" + syl["symbol"]
        else:
            syl["symbol_marked"] = syl["symbol"]

        # stress_class for ProsodyPro/ProsoBox compatibility
        score = syl["prominence_score"]
        if syl["is_prominent"]:
            syl["stress_class"] = "SS3"
        elif score > std_mv * 1.5 if std_mv > 0 else score > 1.5:
            syl["stress_class"] = "SS2"
        else:
            syl["stress_class"] = "SS1"


# ============================================================================
# STAGE 8: WRITE TEXTGRID  (6 tiers only)
# ============================================================================


def _esc(text: Any) -> str:
    return str(text).replace('"', "'")


def write_textgrid(
    path: Path,
    duration: float,
    words: list[dict],
    syllables: list[dict],
    phonemes: list[dict],
    warnings_text: str,
) -> None:
    """Write a 6-tier TextGrid per CLAUDE.md spec.

    Tiers (in order):
        1. words            — IntervalTier
        2. syllables        — IntervalTier
        3. phonemes         — IntervalTier
        4. f0_pitch         — IntervalTier (mean f0 per syllable in Hz, integer)
        5. prosody_labels   — IntervalTier (/ \\ – with * on strongest)
        6. warnings_review  — IntervalTier (one span, content = warnings_text)
    """
    def fill_gaps(rows: list[dict], xmin: float, xmax: float, value_key: str = "value") -> list[dict]:
        """Insert empty intervals so the tier covers [xmin, xmax] contiguously."""
        out = []
        cursor = xmin
        for r in rows:
            s = float(r["start"])
            e = float(r["end"])
            if s > cursor + 1e-6:
                out.append({"start": cursor, "end": s, value_key: ""})
            out.append({"start": s, "end": e, value_key: r.get(value_key, "")})
            cursor = e
        if cursor < xmax - 1e-6:
            out.append({"start": cursor, "end": xmax, value_key: ""})
        return out

    word_rows = [
        {"start": w["start"], "end": w["end"], "value": w.get("word", "")}
        for w in words
    ]
    syll_rows = [
        {"start": s["start"], "end": s["end"], "value": s.get("label", "")}
        for s in syllables
    ]
    phone_rows = [
        {"start": p["start"], "end": p["end"], "value": p.get("label", "")}
        for p in phonemes
    ]
    f0_rows = [
        {
            "start": s["start"],
            "end": s["end"],
            "value": (f"{int(round(s['mean_f0_hz']))}" if s.get("mean_f0_hz") else ""),
        }
        for s in syllables
    ]
    prosody_rows = [
        {"start": s["start"], "end": s["end"], "value": s.get("symbol_marked", "")}
        for s in syllables
    ]
    warn_rows = [{"start": 0.0, "end": duration, "value": warnings_text}]

    tiers = [
        ("words", word_rows),
        ("syllables", syll_rows),
        ("phonemes", phone_rows),
        ("f0_pitch", f0_rows),
        ("prosody_labels", prosody_rows),
        ("warnings_review", warn_rows),
    ]

    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {duration}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]

    for ti, (name, rows) in enumerate(tiers, 1):
        filled = fill_gaps(rows, 0.0, duration)
        lines.extend([
            f"    item [{ti}]:",
            '        class = "IntervalTier"',
            f'        name = "{name}"',
            "        xmin = 0",
            f"        xmax = {duration}",
            f"        intervals: size = {len(filled)}",
        ])
        for i, row in enumerate(filled, 1):
            lines.extend([
                f"        intervals [{i}]:",
                f"            xmin = {row['start']}",
                f"            xmax = {row['end']}",
                f'            text = "{_esc(row["value"])}"',
            ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================================
# STAGE 9: CSV EXPORTS
# ============================================================================


WORDS_CSV_FIELDS = ["file", "language", "index", "word", "start", "end", "duration_s"]
SYLLABLES_CSV_FIELDS = [
    "file", "language", "index", "label", "word_index", "start", "end", "mid",
    "duration_s", "mean_f0_hz", "min_f0_hz", "max_f0_hz", "onset_f0_hz",
    "offset_f0_hz", "pitch_movement_st", "pitch_movement", "symbol",
    "symbol_marked", "mean_intensity_db", "relative_height_st",
    "prominence_score", "stress_class", "is_prominent", "voiced_frames",
    "f1_hz", "f2_hz", "f3_hz", "phones",
]
PHONEMES_CSV_FIELDS = [
    "file", "language", "index", "label", "syllable_index", "word_index",
    "start", "end", "mid", "duration_s",
    "mean_f0_hz", "mean_intensity_db", "voiced_frames",
    "f1_hz", "f2_hz", "f3_hz",
]
PROSODY_CSV_FIELDS = [
    "file", "language", "duration_s", "n_words", "n_syllables", "n_phonemes",
    "mean_f0_hz", "min_f0_hz", "max_f0_hz", "f0_std_st",
    "mean_intensity_db",
    "prominent_count", "rising_count", "falling_count", "level_count",
    "alignment_source",
]


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ============================================================================
# MAIN ANNOTATE
# ============================================================================


def annotate(args) -> int:
    wav = Path(args.wav).resolve()
    if not wav.exists():
        print(f"ERROR: {wav} not found", file=sys.stderr)
        return 1

    name = wav.stem
    out = Path(args.output) / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    (out / "intermediates").mkdir(exist_ok=True)
    log_file = out / "LOG.txt"
    log_file.write_text(f"# SpeechPrint annotation log for {wav.name}\n")

    warnings: list[str] = []

    # 1. Load audio --------------------------------------------------------
    _stage(1, str(wav), log_file)
    info = wav_info(wav)
    duration = info["duration_seconds"]

    # 2. Transcribe --------------------------------------------------------
    _stage(2, f"language={args.language}", log_file)
    transcript = transcribe(wav, args.language)
    if transcript["source"] == "filename":
        warnings.append("Transcript source: filename (Whisper unavailable)")

    # 3. Prepare transcript -----------------------------------------------
    _stage(3, transcript["text"][:60] + ("…" if len(transcript["text"]) > 60 else ""), log_file)

    # 4. Forced alignment -------------------------------------------------
    _stage(4, log_file=log_file)
    word_intervals, align_warns = align_words(wav, transcript, args.language)
    warnings.extend(align_warns)

    # 5. Acoustic features for words (we'll compute on syllables later) ---
    _stage(5, log_file=log_file)
    # We'll attach acoustic features to syllables, not words.

    # 6. Phones -----------------------------------------------------------
    _stage(6, log_file=log_file)
    word_strings = [w["word"] for w in word_intervals]
    phones_by_word, phone_err = phonemize_words(word_strings, args.language)
    if phone_err:
        warnings.append(phone_err)

    # Build syllables (per word) + per-phone intervals
    syllables: list[dict] = []
    phonemes: list[dict] = []
    syll_idx = 0
    phone_idx = 0
    for wi, (w_info, phones) in enumerate(zip(word_intervals, phones_by_word)):
        sylls_for_word, syll_phone_lists = syllables_for_word(
            w_info["word"], phones, w_info["start"], w_info["end"]
        )

        for syl, syl_phones in zip(sylls_for_word, syll_phone_lists):
            syll_idx += 1
            syl_record = {
                "index": syll_idx,
                "label": syl["label"],
                "word_index": wi + 1,
                "start": syl["start"],
                "end": syl["end"],
                "mid": (syl["start"] + syl["end"]) / 2,
                "duration_s": syl["end"] - syl["start"],
                "phones": " ".join(syl_phones),
            }
            syllables.append(syl_record)

            # Distribute phones within the syllable, proportionally to phone count
            if syl_phones:
                syl_dur = syl["end"] - syl["start"]
                per_phone = syl_dur / len(syl_phones)
                for j, ph in enumerate(syl_phones):
                    phone_idx += 1
                    ps = syl["start"] + per_phone * j
                    pe = syl["start"] + per_phone * (j + 1)
                    if j == len(syl_phones) - 1:
                        pe = syl["end"]
                    phonemes.append({
                        "index": phone_idx,
                        "label": ph,
                        "syllable_index": syll_idx,
                        "word_index": wi + 1,
                        "start": ps,
                        "end": pe,
                        "mid": (ps + pe) / 2,
                        "duration_s": pe - ps,
                    })

    # Acoustic features on syllables AND phonemes
    acoustic_features(wav, syllables)
    acoustic_features(wav, phonemes)

    # 7. Symbolic prosody labels (adaptive thresholds) --------------------
    _stage(7, log_file=log_file)
    label_prosody(syllables)

    # 8. TextGrid ---------------------------------------------------------
    _stage(8, log_file=log_file)
    warn_text = "; ".join(warnings) if warnings else "ok"
    shutil.copy2(wav, out / f"{name}.wav")
    write_textgrid(
        out / f"{name}.TextGrid",
        duration,
        word_intervals,
        syllables,
        phonemes,
        warn_text,
    )

    # 9. CSV exports ------------------------------------------------------
    _stage(9, log_file=log_file)
    words_rows = [
        {
            "file": wav.name, "language": args.language,
            "index": i + 1, "word": w["word"],
            "start": w["start"], "end": w["end"],
            "duration_s": w["end"] - w["start"],
        }
        for i, w in enumerate(word_intervals)
    ]
    syll_rows = [
        {"file": wav.name, "language": args.language, **s} for s in syllables
    ]
    phone_rows = [
        {"file": wav.name, "language": args.language, **p} for p in phonemes
    ]

    _write_csv(out / "words.csv", WORDS_CSV_FIELDS, words_rows)
    _write_csv(out / "syllables.csv", SYLLABLES_CSV_FIELDS, syll_rows)
    _write_csv(out / "phonemes.csv", PHONEMES_CSV_FIELDS, phone_rows)

    # Recording-level prosody summary
    f0s = [s["mean_f0_hz"] for s in syllables if s.get("mean_f0_hz")]
    intens = [s["mean_intensity_db"] for s in syllables if s.get("mean_intensity_db")]
    movements_st = [s["pitch_movement_st"] for s in syllables if s.get("pitch_movement_st") is not None]
    prosody_summary = [{
        "file": wav.name, "language": args.language,
        "duration_s": duration,
        "n_words": len(word_intervals),
        "n_syllables": len(syllables),
        "n_phonemes": len(phonemes),
        "mean_f0_hz": _safe_mean(f0s),
        "min_f0_hz": min(f0s) if f0s else None,
        "max_f0_hz": max(f0s) if f0s else None,
        "f0_std_st": _safe_std(movements_st),
        "mean_intensity_db": _safe_mean(intens),
        "prominent_count": sum(1 for s in syllables if s.get("is_prominent")),
        "rising_count": sum(1 for s in syllables if s.get("pitch_movement") == "rising"),
        "falling_count": sum(1 for s in syllables if s.get("pitch_movement") == "falling"),
        "level_count": sum(1 for s in syllables if s.get("pitch_movement") == "level"),
        "alignment_source": transcript["source"],
    }]
    _write_csv(out / "prosody.csv", PROSODY_CSV_FIELDS, prosody_summary)

    # JSON manifest + metadata
    manifest = {
        "file": wav.name,
        "language": args.language,
        "transcript": transcript["text"],
        "transcript_source": transcript["source"],
        "wav_info": info,
        "warnings": warnings,
        "words": word_intervals,
        "syllables": syllables,
        "phonemes": phonemes,
        "prosody_summary": prosody_summary[0],
        "tier_set": ["words", "syllables", "phonemes", "f0_pitch", "prosody_labels", "warnings_review"],
    }
    (out / f"{name}.json").write_text(json.dumps(manifest, indent=2, default=str))

    (out / "warnings.json").write_text(json.dumps(warnings, indent=2))
    (out / "run_metadata.json").write_text(json.dumps({
        "backend": "speechprint_pipeline",
        "version": "0.4.0",
        "tiers": ["words", "syllables", "phonemes", "f0_pitch", "prosody_labels", "warnings_review"],
        "stages": STAGES,
        "alignment_source": transcript["source"],
    }, indent=2))

    with log_file.open("a") as fh:
        fh.write(f"\n✓ Wrote {out}\n")

    print(f"✓ Wrote {out}", flush=True)

    # Optional: bundle a ZIP if requested
    if getattr(args, "zip", False):
        zip_path = out.parent / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in out.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(out.parent))
        print(f"✓ Wrote {zip_path}", flush=True)

    return 0


# ============================================================================
# ENSEMBLE / EXPORT-ZIP / OTHER COMMANDS
# ============================================================================


def ensemble(args) -> int:
    """Aggregate per-recording outputs into corpus-level tables."""
    root = Path(args.root)
    out_dir = root / "out"
    if not out_dir.exists():
        print("No out/ directory found", file=sys.stderr)
        return 1

    syll_files = sorted(out_dir.glob("*/syllables.csv"))
    phone_files = sorted(out_dir.glob("*/phonemes.csv"))
    prosody_files = sorted(out_dir.glob("*/prosody.csv"))

    def merge(files: list[Path], dest: Path) -> int:
        rows = []
        fields: list[str] = []
        for f in files:
            with f.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not fields and reader.fieldnames:
                    fields = list(reader.fieldnames)
                for row in reader:
                    rows.append(row)
        if not rows:
            return 0
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    n_syll = merge(syll_files, root / "syllables_all.csv")
    n_phone = merge(phone_files, root / "phonemes_all.csv")
    n_prosody = merge(prosody_files, root / "prosody_all.csv")

    print(f"✓ Ensemble: {n_syll} syllable rows, {n_phone} phone rows, {n_prosody} prosody rows", flush=True)
    return 0


def export_zip(args) -> int:
    """Zip up an annotation output folder."""
    src = Path(args.path).resolve()
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1
    if src.is_file():
        src = src.parent
    zip_path = src.parent / f"{src.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src.parent))
    print(f"✓ Wrote {zip_path}", flush=True)
    return 0


def transcribe_cmd(args) -> int:
    wav = Path(args.wav).resolve()
    t = transcribe(wav, args.language)
    print(json.dumps(t, indent=2, default=str))
    return 0


# ============================================================================
# CLI ENTRY
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="speechprint",
        description="SpeechPrint linguistic annotation pipeline",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("annotate", help="Annotate a single WAV file (full pipeline)")
    a.add_argument("wav")
    a.add_argument("--language", "--lang", default="en")
    a.add_argument("--output", default="out")
    a.add_argument("--zip", action="store_true", help="Also produce a zipped result folder")
    a.set_defaults(func=annotate)

    e = sub.add_parser("ensemble", help="Aggregate per-recording outputs")
    e.add_argument("--root", default=".")
    e.set_defaults(func=ensemble)

    z = sub.add_parser("export-zip", help="Zip an annotation output folder for sharing")
    z.add_argument("path")
    z.set_defaults(func=export_zip)

    t = sub.add_parser("transcribe", help="Print Whisper transcription only (JSON)")
    t.add_argument("wav")
    t.add_argument("--language", "--lang", default="en")
    t.set_defaults(func=transcribe_cmd)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
