#!/usr/bin/env python3
"""Multi-aligner evaluation pipeline for SpeechPrint.

Runs a WAV file through four alignment backends and produces:
  1. One TextGrid per aligner (words + syllables + phonemes + prosody)
  2. A combined COMPARISON TextGrid with all aligner tiers side by side
  3. An optional merge with a reference human-annotated TextGrid

Backends implemented:
  whisper    — Whisper-only segment timing, words distributed proportionally
  whisperx   — WhisperX CTC forced alignment (word-level precision)
  gentle     — Gentle / Kaldi alignment via Docker (English-optimised)
  mfa        — Montreal Forced Aligner (phone-level output)

Usage:
  python evaluate_aligners.py --wav FILE.wav --language en|it|pt ...
  python evaluate_aligners.py --wav FILE.wav --language it \\
      --reference HUMAN.TextGrid --output out/endangered_language
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import wave
import zipfile
from pathlib import Path
from typing import Optional

# ============================================================================
# CONSTANTS
# ============================================================================

VOWELS_IPA = set(
    "aeiouæɑɒɐəɚɛɜɝɪɨɔøœuʊʌyɯɵɘɤɞɛ̞ɔ̞ɑ̃ɛ̃ɔ̃œ̃ãiɪeɛæaɑɒɔoʊuʌəɝɚy"
)
VOWELS_LATIN = set("aeiouyAEIOUYäöüÄÖÜáéíóúàèìòùÁÉÍÓÚÀÈÌÒÙâêîôûÂÊÎÔÛ")

ESPEAK_LANG = {
    "en": "en-us", "de": "de", "it": "it",
    "es": "es", "fr": "fr-fr", "cs": "cs",
    "pt": "pt", "nl": "nl",
}

# MFA model paths discovered in the repo
MFA_MODELS_DIRS = [
    Path("/home/lydia/School/UPF/thesis260512/tools/mfa_models"),
    Path("/home/lydia/School/UPF/semester3/thesis_foo/thesis260512_2/tools/mfa_models"),
    Path("/home/lydia/School/UPF/thesis_foo/thesis260512_2/tools/mfa_models"),
]
MFA_ACOUSTIC = {
    "en": "english_mfa",
    "it": "italian_cv",
}
MFA_DICT = {
    "en": "english_mfa",
    "it": "italian_cv",
}


# ============================================================================
# UTILITIES
# ============================================================================

def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def _safe_mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else None


def _safe_std(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return statistics.pstdev(xs) if len(xs) >= 2 else 0.0


def _semitone(a, b):
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12 * math.log2(b / a)


def _esc(t):
    return str(t).replace('"', "'")


def find_mfa_model(kind: str, name: str) -> Optional[Path]:
    for base in MFA_MODELS_DIRS:
        p = base / "pretrained_models" / kind / f"{name}.{'dict' if kind == 'dictionary' else 'zip'}"
        if p.exists():
            return p
    return None


# ============================================================================
# STAGE 1: TRANSCRIPTION  (shared across backends)
# ============================================================================

def get_transcript(wav: Path, language: str) -> dict:
    """Run WhisperX transcription. Returns {text, segments, language, source}."""
    try:
        import whisperx
        model = whisperx.load_model("small", device="cpu", compute_type="int8")
        result = model.transcribe(str(wav), language=language)
        segments = result.get("segments", [])
        text = " ".join(seg.get("text", "") for seg in segments).strip()
        text_clean = re.sub(r"[^A-Za-zÀ-ÿ0-9 ']+", " ", text).strip().lower()
        text_clean = re.sub(r"\s+", " ", text_clean)
        if text_clean and segments:
            return {"text": text_clean, "segments": segments,
                    "language": result.get("language", language), "source": "whisperx"}
    except Exception as e:
        print(f"  ! WhisperX unavailable: {e}", flush=True)

    try:
        import whisper
        model = whisper.load_model("small")
        result = model.transcribe(str(wav), language=language)
        segments = result.get("segments", [])
        text_clean = re.sub(r"[^A-Za-zÀ-ÿ0-9 ']+", " ", result.get("text", "")).strip().lower()
        text_clean = re.sub(r"\s+", " ", text_clean)
        return {"text": text_clean, "segments": segments,
                "language": language, "source": "whisper_fallback"}
    except Exception as e:
        print(f"  ! whisper unavailable: {e}", flush=True)

    fallback = re.sub(r"[_\-\d]+", " ", wav.stem).strip().lower()
    return {"text": fallback, "segments": [], "language": language, "source": "filename"}


# ============================================================================
# BACKEND 1: Whisper segment-level (proportional word timing)
# ============================================================================

def align_whisper_segment(transcript: dict) -> tuple[list[dict], str]:
    """Distribute words proportionally within Whisper segments (coarse timing)."""
    segments = transcript.get("segments", [])
    words = []
    for seg in segments:
        s = float(seg.get("start", 0.0) or 0.0)
        e = float(seg.get("end", 0.0) or 0.0)
        tokens = [w for w in (seg.get("text") or "").strip().split() if w]
        if e <= s or not tokens:
            continue
        n = len(tokens)
        span = e - s
        for i, tok in enumerate(tokens):
            clean = re.sub(r"[^a-zà-ÿ0-9']+", "", tok.lower())
            if not clean:
                continue
            words.append({
                "start": s + span * i / n,
                "end": s + span * (i + 1) / n,
                "word": clean,
            })
    source_note = "whisper-segment (proportional word timing within segments)"
    return words, source_note


# ============================================================================
# BACKEND 2: WhisperX CTC word-level alignment
# ============================================================================

def align_whisperx(wav: Path, transcript: dict, language: str) -> tuple[list[dict], str]:
    """WhisperX CTC forced alignment — word-level precision."""
    segments = transcript.get("segments", [])
    try:
        import whisperx
        align_model, metadata = whisperx.load_align_model(language_code=language, device="cpu")
        aligned = whisperx.align(segments, align_model, metadata, str(wav), device="cpu",
                                  return_char_alignments=False)
        words = []
        for seg in aligned.get("segments", []):
            for w in seg.get("words", []):
                start = w.get("start")
                end = w.get("end")
                token = re.sub(r"[^a-zà-ÿ0-9']+", "", (w.get("word") or "").strip().lower())
                if start is None or end is None or not token or end <= start:
                    continue
                words.append({"start": float(start), "end": float(end), "word": token})
        if words:
            return words, "whisperx-ctc (CTC forced alignment, word-level)"
        return [], "whisperx-ctc returned no words"
    except Exception as e:
        return [], f"whisperx-ctc failed: {e}"


# ============================================================================
# BACKEND 3: Gentle (Docker)
# ============================================================================

def align_gentle(wav: Path, transcript: dict, language: str) -> tuple[list[dict], str]:
    """Gentle forced alignment via Docker (english-optimised Kaldi model)."""
    if language not in ("en", "english"):
        return [], f"gentle skipped: only supports English (got '{language}')"

    text = transcript.get("text", "")
    if not text.strip():
        return [], "gentle skipped: empty transcript"

    import uuid as _uuid
    gentle_tmp = Path(f"/tmp/gentle_eval_{_uuid.uuid4().hex[:8]}")
    gentle_tmp.mkdir(parents=True, exist_ok=True)
    try:
        wav_tmp = gentle_tmp / wav.name
        shutil.copy2(wav, wav_tmp)
        txt_tmp = gentle_tmp / "transcript.txt"
        txt_tmp.write_text(text, encoding="utf-8")

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{gentle_tmp}:/data",
            "lowerquality/gentle",
            "python", "/gentle/align.py",
            f"/data/{wav.name}",
            f"/data/transcript.txt",
            "--output", "/data/gentle_out.json",
            "--conservative",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            out_json = gentle_tmp / "gentle_out.json"
            if not out_json.exists():
                return [], f"gentle: no output (stderr: {r.stderr[:200]})"
            result = json.loads(out_json.read_text())
            words = []
            for w in result.get("words", []):
                if w.get("case") != "success":
                    continue
                start = w.get("start")
                end = w.get("end")
                token = re.sub(r"[^a-zà-ÿ0-9']+", "", (w.get("word") or "").lower())
                if start is None or end is None or not token or end <= start:
                    continue
                words.append({"start": float(start), "end": float(end), "word": token})
            source = f"gentle-kaldi (Kaldi acoustic model, {len(words)} words aligned)"
            return words, source
        except subprocess.TimeoutExpired:
            return [], "gentle: timeout after 300s"
        except Exception as e:
            return [], f"gentle: error: {e}"
    finally:
        shutil.rmtree(gentle_tmp, ignore_errors=True)


# ============================================================================
# BACKEND 4: MFA (Montreal Forced Aligner) — phone-level output
# ============================================================================

def align_mfa(wav: Path, transcript: dict, language: str) -> tuple[list[dict], list[dict], str]:
    """MFA forced alignment. Returns (word_intervals, phone_intervals, source_note).

    MFA gives phone-level timing, which is the highest resolution of all backends.
    """
    acoustic_name = MFA_ACOUSTIC.get(language)
    dict_name = MFA_DICT.get(language)
    if not acoustic_name:
        return [], [], f"mfa: no acoustic model configured for language '{language}'"

    acoustic_path = find_mfa_model("acoustic", acoustic_name)
    dict_path = find_mfa_model("dictionary", dict_name or acoustic_name)
    if not acoustic_path:
        return [], [], f"mfa: acoustic model '{acoustic_name}' not found"
    if not dict_path:
        return [], [], f"mfa: dictionary '{dict_name}' not found"

    text = transcript.get("text", "").strip()
    if not text:
        return [], [], "mfa: empty transcript"

    mfa_bin = Path("/home/lydia/miniforge3/envs/speechprint-mfa/bin/mfa")
    if not mfa_bin.exists():
        return [], [], f"mfa: binary not found at {mfa_bin}"

    import uuid
    run_id = uuid.uuid4().hex[:8]
    tmp_base = Path(f"/tmp/mfa_{run_id}")
    tmp_base.mkdir(parents=True, exist_ok=True)
    try:
        # corpus_dir name becomes MFA's internal working dir name — keep it short and unique
        corpus_dir = tmp_base / wav.stem[:16]
        out_dir = tmp_base / "out"
        corpus_dir.mkdir()
        out_dir.mkdir()

        # Copy WAV and write LAB transcript
        shutil.copy2(wav, corpus_dir / wav.name)
        lab_file = corpus_dir / (wav.stem + ".lab")
        lab_file.write_text(text, encoding="utf-8")
        print(f"    MFA corpus: {corpus_dir}, transcript words: {len(text.split())}", flush=True)

        conda_bin = Path("/home/lydia/miniforge3/bin/conda")
        if conda_bin.exists():
            cmd = [
                str(conda_bin), "run", "-n", "speechprint-mfa",
                "mfa", "align",
                str(corpus_dir),
                str(dict_path),
                str(acoustic_path),
                str(out_dir),
                "--clean",
                "--num_jobs", "2",
            ]
        else:
            cmd = [
                str(mfa_bin), "align",
                str(corpus_dir),
                str(dict_path),
                str(acoustic_path),
                str(out_dir),
                "--clean",
                "--num_jobs", "2",
            ]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                               env={**os.environ, "MFA_ROOT_DIR": str(tmp_base / "mfa")})
            tg_files = list(out_dir.rglob("*.TextGrid"))
            if not tg_files:
                # Also check corpus_dir for output (MFA sometimes writes there)
                tg_files = list(corpus_dir.rglob("*.TextGrid"))
            if not tg_files:
                return [], [], f"mfa: no TextGrid output (rc={r.returncode}, stderr={r.stderr[-400:]})"

            tg_content = tg_files[0].read_text(encoding="utf-8")
            word_ivs, phone_ivs = _parse_mfa_textgrid(tg_content)
            src = (f"mfa-{acoustic_name} (phone-level Kaldi+MFA, "
                   f"{len(word_ivs)} words, {len(phone_ivs)} phones)")
            return word_ivs, phone_ivs, src
        except subprocess.TimeoutExpired:
            return [], [], "mfa: timeout after 600s"
        except Exception as e:
            return [], [], f"mfa: error: {e}"
    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)


def _parse_mfa_textgrid(content: str) -> tuple[list[dict], list[dict]]:
    """Parse MFA TextGrid output, returning (word_intervals, phone_intervals)."""
    lines = content.splitlines()
    tiers: dict[str, list] = {}
    current_name = None
    current_ivs: list = []
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        m = re.match(r'name\s*=\s*"(.+)"', l)
        if m:
            if current_name is not None:
                tiers[current_name] = current_ivs
            current_name = m.group(1)
            current_ivs = []
        elif re.match(r"intervals\s*\[\d+\]", l):
            iv = {}
            i += 1
            while i < len(lines):
                lv = lines[i].strip()
                xm = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", lv)
                xM = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", lv)
                tx = re.match(r'text\s*=\s*"(.*)"', lv)
                if xm:
                    iv["xmin"] = float(xm.group(1))
                elif xM:
                    iv["xmax"] = float(xM.group(1))
                elif tx:
                    iv["text"] = tx.group(1)
                if re.match(r"intervals\s*\[", lines[i].strip()) or (
                        re.match(r"(item|points)\s*\[", lines[i].strip())):
                    break
                i += 1
            if iv.get("text", "").strip() and iv.get("text") not in ("", "sp", "SIL", "<eps>"):
                current_ivs.append({
                    "start": iv.get("xmin", 0.0),
                    "end": iv.get("xmax", 0.0),
                    "label": iv.get("text", ""),
                })
            continue
        i += 1
    if current_name:
        tiers[current_name] = current_ivs

    word_ivs = [{"start": iv["start"], "end": iv["end"], "word": iv["label"]}
                for iv in tiers.get("words", [])]
    phone_ivs = [{"start": iv["start"], "end": iv["end"], "label": iv["label"]}
                 for iv in tiers.get("phones", [])]
    return word_ivs, phone_ivs


# ============================================================================
# PHONEMIZATION + SYLLABIFICATION
# ============================================================================

def phonemize_words(words: list[str], language: str) -> list[list[str]]:
    if not words:
        return []
    try:
        from phonemizer import phonemize
        from phonemizer.separator import Separator
        lang = ESPEAK_LANG.get(language, "en-us")
        ipa = phonemize(
            words, language=lang, backend="espeak",
            separator=Separator(phone=" ", word=" | ", syllable=""),
            strip=True, preserve_punctuation=False, with_stress=False, njobs=1,
        )
        if isinstance(ipa, str):
            ipa = [ipa]
        out = []
        for line in ipa:
            phones = [p for p in (line or "").split() if p and p != "|"]
            out.append(phones)
        return out
    except Exception as e:
        print(f"  ! phonemizer: {e}", flush=True)
        return [[] for _ in words]


def split_phones_into_syllables(phones: list[str]) -> list[list[str]]:
    if not phones:
        return []
    is_vowel = [any(ch in VOWELS_IPA for ch in p) for p in phones]
    vowel_idx = [i for i, v in enumerate(is_vowel) if v]
    if not vowel_idx:
        return [phones]
    sylls: list[list[str]] = []
    for k, vi in enumerate(vowel_idx):
        if k == 0:
            onset_start = 0
        else:
            prev_vi = vowel_idx[k - 1]
            gap = vi - prev_vi - 1
            cut = prev_vi + 1 + (gap // 2) if gap > 0 else prev_vi + 1
            onset_start = cut
            if sylls and cut > prev_vi + 1:
                sylls[-1].extend(phones[prev_vi + 1: cut])
        if k == len(vowel_idx) - 1:
            sylls.append(phones[onset_start:])
        else:
            sylls.append(phones[onset_start: vi + 1])
    return sylls


def syllabify_latin(word: str) -> list[str]:
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


def build_syllables_phonemes(word_intervals: list[dict], phones_by_word: list[list[str]],
                              mfa_phone_intervals: list[dict] | None = None
                              ) -> tuple[list[dict], list[dict]]:
    """Build syllable and phoneme interval lists from word intervals + phonemizer output.

    If mfa_phone_intervals is provided (phone-level timing from MFA), the phoneme
    timing is taken directly from MFA rather than proportional distribution.
    Returns (syllables, phonemes).
    """
    syllables: list[dict] = []
    phonemes: list[dict] = []
    syll_idx = 0
    phone_idx = 0

    for wi, (w_info, phones) in enumerate(zip(word_intervals, phones_by_word)):
        w0 = float(w_info["start"])
        w1 = float(w_info["end"])
        word = w_info.get("word", "")

        if phones:
            syll_phone_lists = split_phones_into_syllables(phones)
        else:
            syll_phone_lists = [[]]

        total_phones = sum(len(s) for s in syll_phone_lists) or 1
        # Always label syllables with their IPA phones, never orthographic.
        # The orthographic fallback caused "flew" to appear instead of "fluː"
        # when the syllable count happened to match (feedback: IPA/English mix).
        ortho_sylls = ["".join(p) for p in syll_phone_lists] or [word]

        cursor = w0
        word_dur = w1 - w0
        for si, (label, syl_phones) in enumerate(zip(ortho_sylls, syll_phone_lists)):
            syll_idx += 1
            frac = len(syl_phones) / total_phones
            s0 = cursor
            s1 = cursor + word_dur * frac if si < len(syll_phone_lists) - 1 else w1
            cursor = s1
            syl_record = {
                "index": syll_idx, "label": label, "word_index": wi + 1,
                "start": s0, "end": s1, "mid": (s0 + s1) / 2,
                "duration_s": s1 - s0, "phones": " ".join(syl_phones),
            }
            syllables.append(syl_record)

            if syl_phones:
                syl_dur = s1 - s0
                per_phone = syl_dur / len(syl_phones)
                for j, ph in enumerate(syl_phones):
                    phone_idx += 1
                    ps = s0 + per_phone * j
                    pe = s0 + per_phone * (j + 1) if j < len(syl_phones) - 1 else s1
                    phonemes.append({
                        "index": phone_idx, "label": ph,
                        "syllable_index": syll_idx, "word_index": wi + 1,
                        "start": ps, "end": pe, "mid": (ps + pe) / 2,
                        "duration_s": pe - ps,
                    })

    # If MFA phone intervals are available, replace the phoneme tier timing with MFA's
    if mfa_phone_intervals:
        phonemes = [
            {
                "index": i + 1, "label": iv["label"],
                "syllable_index": 0, "word_index": 0,
                "start": iv["start"], "end": iv["end"],
                "mid": (iv["start"] + iv["end"]) / 2,
                "duration_s": iv["end"] - iv["start"],
            }
            for i, iv in enumerate(mfa_phone_intervals)
        ]

    return syllables, phonemes


# ============================================================================
# ACOUSTIC FEATURES
# ============================================================================

def acoustic_features(wav: Path, intervals: list[dict]) -> None:
    """Add f0, intensity, formants to each interval dict in place."""
    try:
        import parselmouth
    except Exception as e:
        print(f"  ! parselmouth: {e}", flush=True)
        for r in intervals:
            r.update({"mean_f0_hz": None, "min_f0_hz": None, "max_f0_hz": None,
                       "onset_f0_hz": None, "offset_f0_hz": None,
                       "mean_intensity_db": None, "f1_hz": None, "f2_hz": None,
                       "f3_hz": None, "voiced_frames": 0,
                       "f0_10pt": [], "f0_velocity_st_s": None})
        return

    snd = parselmouth.Sound(str(wav))
    try:
        pitch = snd.to_pitch()
    except Exception:
        pitch = None
    try:
        intensity = snd.to_intensity()
    except Exception:
        intensity = None
    try:
        formant = snd.to_formant_burg()
    except Exception:
        formant = None

    for row in intervals:
        s = float(row["start"])
        e = float(row["end"])
        if e <= s:
            row.update({"mean_f0_hz": None, "min_f0_hz": None, "max_f0_hz": None,
                        "onset_f0_hz": None, "offset_f0_hz": None,
                        "mean_intensity_db": None, "voiced_frames": 0,
                        "f0_10pt": [], "f0_velocity_st_s": None,
                        "f1_hz": None, "f2_hz": None, "f3_hz": None})
            continue

        # 10-point time-normalized F0 (inspired by ProsodyPro)
        ts_10 = [s + (e - s) * j / 9 for j in range(10)]
        f0s_10 = []
        intens = []
        for t in ts_10:
            if pitch is not None:
                try:
                    hz = float(pitch.get_value_at_time(t))
                    f0s_10.append(hz if hz and not math.isnan(hz) and hz > 0 else None)
                except Exception:
                    f0s_10.append(None)
            if intensity is not None:
                try:
                    db = float(intensity.get_value(t))
                    if not math.isnan(db):
                        intens.append(db)
                except Exception:
                    pass

        f0s_valid = [x for x in f0s_10 if x is not None]
        row["f0_10pt"] = [round(x, 1) if x else None for x in f0s_10]
        row["mean_f0_hz"] = _safe_mean(f0s_valid)
        row["min_f0_hz"] = min(f0s_valid) if f0s_valid else None
        row["max_f0_hz"] = max(f0s_valid) if f0s_valid else None
        row["onset_f0_hz"] = next((x for x in f0s_10 if x), None)
        row["offset_f0_hz"] = next((x for x in reversed(f0s_10) if x), None)
        row["mean_intensity_db"] = _safe_mean(intens)
        row["voiced_frames"] = len(f0s_valid)

        # F0 velocity (semitones/second) — slope from onset to offset
        onset = row["onset_f0_hz"]
        offset = row["offset_f0_hz"]
        dur = e - s
        if onset and offset and dur > 0:
            mv_st = _semitone(onset, offset)
            row["f0_velocity_st_s"] = (mv_st / dur) if mv_st is not None else None
        else:
            row["f0_velocity_st_s"] = None

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


# ============================================================================
# IMPROVED SYMBOLIC PROSODY LAYER
# (Inspired by ProsodyPro: 10-pt F0, velocity, excursion, boundary detection)
# ============================================================================

F0_RISE_FLOOR_ST = 2.5
F0_FALL_FLOOR_ST = 2.5
F0_STD_FACTOR = 0.70
PAUSE_THRESHOLD_S = 0.25   # silence ≥ 250 ms = potential phrase boundary


def label_prosody_enhanced(syllables: list[dict], word_intervals: list[dict]) -> None:
    """Enhanced symbolic prosody labelling.

    Adds per-syllable:
      symbol          — "/" rising  "\\" falling  "–" level  "?" unknown
      symbol_marked   — above + "*" on the most prominent syllable
      pitch_movement  — "rising" | "falling" | "level" | "unknown"
      pitch_movement_st
      relative_height_st  — semitones relative to speaker mean F0
      excursion_st    — max - min F0 within syllable (in semitones)
      f0_velocity_st_s— rate of F0 change (semitones/second)
      prominence_score
      is_prominent
      stress_class    — "SS1" light | "SS2" medium | "SS3" prominent
      phrase_boundary — True if a pause ≥ PAUSE_THRESHOLD_S follows this syllable
      height_class    — "H" (high), "M" (mid), "L" (low) relative to speaker range
    """
    if not syllables:
        return

    # --- pitch movements ---
    movements: list[Optional[float]] = []
    for syl in syllables:
        mv = _semitone(syl.get("onset_f0_hz"), syl.get("offset_f0_hz"))
        syl["pitch_movement_st"] = mv
        movements.append(mv)

    std_mv = _safe_std(movements)
    rise_threshold = max(F0_RISE_FLOOR_ST, F0_STD_FACTOR * std_mv)
    fall_threshold = -max(F0_FALL_FLOOR_ST, F0_STD_FACTOR * std_mv)

    # --- speaker F0 statistics for relative height ---
    f0_vals = [s.get("mean_f0_hz") for s in syllables if s.get("mean_f0_hz")]
    mean_f0 = _safe_mean(f0_vals)
    std_f0 = _safe_std(f0_vals)
    f0_q1 = sorted(f0_vals)[len(f0_vals) // 4] if len(f0_vals) >= 4 else None
    f0_q3 = sorted(f0_vals)[3 * len(f0_vals) // 4] if len(f0_vals) >= 4 else None

    # --- phrase boundaries from pauses between words ---
    word_ends = {w["end"]: w.get("start", 0.0) for w in word_intervals}
    pause_ends: set[float] = set()
    sorted_words = sorted(word_intervals, key=lambda w: w["start"])
    for i in range(len(sorted_words) - 1):
        gap = sorted_words[i + 1]["start"] - sorted_words[i]["end"]
        if gap >= PAUSE_THRESHOLD_S:
            pause_ends.add(sorted_words[i]["end"])

    for i, syl in enumerate(syllables):
        mv = syl["pitch_movement_st"]

        # Pitch direction symbol
        if mv is None:
            syl["pitch_movement"] = "unknown"
            syl["symbol"] = "?"
        elif mv >= rise_threshold:
            syl["pitch_movement"] = "rising"
            syl["symbol"] = "/"
        elif mv <= fall_threshold:
            syl["pitch_movement"] = "falling"
            syl["symbol"] = "\\"
        else:
            syl["pitch_movement"] = "level"
            syl["symbol"] = "–"

        # F0 excursion within syllable (semitones from min to max)
        excursion = _semitone(syl.get("min_f0_hz"), syl.get("max_f0_hz"))
        syl["excursion_st"] = excursion

        # Relative height (semitones above speaker mean)
        syl["relative_height_st"] = (
            _semitone(mean_f0, syl["mean_f0_hz"]) if (mean_f0 and syl.get("mean_f0_hz")) else None
        )

        # Height class H/M/L (based on speaker F0 quartiles)
        f0 = syl.get("mean_f0_hz")
        if f0 and f0_q3 and f0_q1:
            syl["height_class"] = "H" if f0 >= f0_q3 else ("L" if f0 <= f0_q1 else "M")
        else:
            syl["height_class"] = "?"

        # Phrase boundary (pause after the word containing this syllable)
        syl["phrase_boundary"] = syl.get("end", 0.0) in pause_ends or (
            i + 1 < len(syllables) and
            syllables[i + 1]["start"] - syl["end"] >= PAUSE_THRESHOLD_S
        )

        # Prominence score (F0 height + movement magnitude + intensity)
        height = abs(syl.get("relative_height_st") or 0.0)
        movement = abs(mv or 0.0)
        intensity_score = max(0.0, (syl.get("mean_intensity_db", -50) or -50) + 50.0) / 25.0
        excursion_score = abs(excursion or 0.0) / 4.0  # normalised
        syl["prominence_score"] = height + movement + intensity_score + excursion_score

    # Mark the most prominent syllable
    strongest = max(range(len(syllables)), key=lambda i: syllables[i]["prominence_score"])
    for i, syl in enumerate(syllables):
        syl["is_prominent"] = (i == strongest)
        pb = "%" if syl.get("phrase_boundary") else ""
        if syl["is_prominent"] and syl["symbol"] != "?":
            syl["symbol_marked"] = pb + "*" + syl["symbol"]
        else:
            syl["symbol_marked"] = pb + syl["symbol"]

        score = syl["prominence_score"]
        if syl["is_prominent"]:
            syl["stress_class"] = "SS3"
        elif score > std_mv * 1.5 if std_mv > 0 else score > 1.5:
            syl["stress_class"] = "SS2"
        else:
            syl["stress_class"] = "SS1"


# ============================================================================
# TEXTGRID WRITER
# ============================================================================

def _fill_gaps(rows: list[dict], xmax: float, value_key: str = "value") -> list[dict]:
    out = []
    cursor = 0.0
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


def write_textgrid(path: Path, xmax: float, tiers: list[dict]) -> None:
    """Write a Praat TextGrid. Each tier: {name, rows: [{start, end, value}]}"""
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
                f'            text = "{_esc(row.get("value", ""))}"',
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tiers_from_pipeline(word_intervals, syllables, phonemes, mfa_phones,
                         backend_label: str, xmax: float) -> list[dict]:
    """Build the 6 standard tiers for one backend."""
    tiers = [
        {
            "name": f"{backend_label}_words",
            "rows": [{"start": w["start"], "end": w["end"], "value": w.get("word", "")}
                     for w in word_intervals],
        },
        {
            "name": f"{backend_label}_syllables",
            "rows": [{"start": s["start"], "end": s["end"], "value": s.get("label", "")}
                     for s in syllables],
        },
        {
            "name": f"{backend_label}_phonemes",
            "rows": [{"start": p["start"], "end": p["end"], "value": p.get("label", "")}
                     for p in (mfa_phones if mfa_phones else phonemes)],
        },
        {
            "name": f"{backend_label}_f0_hz",
            "rows": [{"start": s["start"], "end": s["end"],
                      "value": f"{int(round(s['mean_f0_hz']))}" if s.get("mean_f0_hz") else ""}
                     for s in syllables],
        },
        {
            "name": f"{backend_label}_prosody",
            "rows": [{"start": s["start"], "end": s["end"],
                      "value": s.get("symbol_marked", "")}
                     for s in syllables],
        },
        {
            "name": f"{backend_label}_height",
            "rows": [{"start": s["start"], "end": s["end"],
                      "value": s.get("height_class", "")}
                     for s in syllables],
        },
    ]
    return tiers


# ============================================================================
# HUMAN TEXTGRID READER (re-used from merge_textgrids)
# ============================================================================

def parse_textgrid_tiers(path: Path) -> tuple[float, list[dict]]:
    """Return (xmax, list of tier dicts). Each tier: {name, intervals:[{xmin,xmax,text}]}"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    xmax_match = re.search(r"xmax\s*=\s*([\d.]+)\s*\ntiers", text)
    xmax = float(xmax_match.group(1)) if xmax_match else 0.0

    tiers = []
    i = 0
    while i < len(lines):
        if re.match(r"\s*item\s*\[\d+\]\s*:", lines[i]):
            tier: dict = {}
            i += 1
            while i < len(lines):
                l = lines[i].strip()
                if re.match(r"item\s*\[", l):
                    break
                m = re.match(r'class\s*=\s*"(.+)"', l)
                if m:
                    tier["class"] = m.group(1)
                m = re.match(r'name\s*=\s*"(.*)"', l)
                if m:
                    tier["name"] = m.group(1)
                m = re.match(r"intervals:\s*size\s*=\s*(\d+)", l)
                if m:
                    n = int(m.group(1))
                    ivs = []
                    i += 1
                    while i < len(lines) and len(ivs) < n:
                        if re.match(r"\s*intervals\s*\[", lines[i]):
                            iv: dict = {}
                            i += 1
                            while i < len(lines):
                                lv = lines[i].strip()
                                if re.match(r"(intervals|item)\s*\[", lv):
                                    break
                                xm = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", lv)
                                xM = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", lv)
                                tx = re.match(r'text\s*=\s*"(.*)"', lv)
                                if xm:
                                    iv["xmin"] = float(xm.group(1))
                                if xM:
                                    iv["xmax"] = float(xM.group(1))
                                if tx:
                                    iv["text"] = tx.group(1)
                                i += 1
                            ivs.append(iv)
                        else:
                            i += 1
                    tier["intervals"] = ivs
                    continue
                i += 1
            if "name" in tier:
                tiers.append(tier)
            continue
        i += 1

    return xmax, tiers


def human_tiers_as_speechprint_format(human_tiers: list[dict],
                                      include: list[str], prefix: str = "h_") -> list[dict]:
    by_name = {t["name"]: t for t in human_tiers}
    out = []
    for name in include:
        if name not in by_name:
            continue
        tier = by_name[name]
        rows = [{"start": iv.get("xmin", 0.0), "end": iv.get("xmax", 0.0),
                 "value": iv.get("text", "")}
                for iv in tier.get("intervals", [])]
        out.append({"name": prefix + name, "rows": rows})
    return out


# ============================================================================
# MAIN PIPELINE PER BACKEND
# ============================================================================

def run_backend(backend: str, wav: Path, transcript: dict, language: str,
                out_dir: Path, mfa_results: tuple | None = None) -> dict:
    """Run one alignment backend and write its TextGrid. Returns info dict."""
    print(f"\n  [{backend.upper()}]", flush=True)
    duration = wav_duration(wav)
    out_dir.mkdir(parents=True, exist_ok=True)

    mfa_phones = []
    word_intervals = []
    source_note = ""

    if backend == "whisper":
        word_intervals, source_note = align_whisper_segment(transcript)
    elif backend == "whisperx":
        word_intervals, source_note = align_whisperx(wav, transcript, language)
    elif backend == "gentle":
        word_intervals, source_note = align_gentle(wav, transcript, language)
    elif backend == "mfa":
        if mfa_results:
            word_intervals, mfa_phones, source_note = mfa_results
        else:
            word_intervals, mfa_phones, source_note = align_mfa(wav, transcript, language)
    else:
        return {"backend": backend, "error": f"unknown backend '{backend}'"}

    print(f"    Words: {len(word_intervals)}, source: {source_note}", flush=True)

    if not word_intervals:
        print(f"    ! No words — skipping prosody/phoneme stages", flush=True)
        return {"backend": backend, "words": 0, "source": source_note, "error": "no words"}

    # Phonemize
    word_strings = [w["word"] for w in word_intervals]
    phones_by_word = phonemize_words(word_strings, language)

    # Build syllables and phonemes
    syllables, phonemes = build_syllables_phonemes(word_intervals, phones_by_word,
                                                    mfa_phones if backend == "mfa" else None)

    # Acoustic features on syllables
    print(f"    Extracting acoustics for {len(syllables)} syllables...", flush=True)
    acoustic_features(wav, syllables)

    # Enhanced symbolic prosody
    label_prosody_enhanced(syllables, word_intervals)

    # Write per-backend TextGrid
    tiers = tiers_from_pipeline(word_intervals, syllables, phonemes, mfa_phones,
                                 backend, duration)
    tg_path = out_dir / f"{wav.stem}_{backend}.TextGrid"
    write_textgrid(tg_path, duration, tiers)
    print(f"    TextGrid: {tg_path}", flush=True)

    # Write JSON
    json_path = out_dir / f"{wav.stem}_{backend}.json"
    json_path.write_text(json.dumps({
        "backend": backend, "language": language,
        "source_note": source_note,
        "n_words": len(word_intervals), "n_syllables": len(syllables),
        "n_phonemes": len(phonemes) + len(mfa_phones),
        "words": word_intervals, "syllables": syllables, "phonemes": phonemes,
        "mfa_phones": mfa_phones,
    }, indent=2, default=str))

    return {
        "backend": backend,
        "source": source_note,
        "words": len(word_intervals),
        "syllables": len(syllables),
        "phonemes": len(phonemes) + len(mfa_phones),
        "tiers": tiers,
        "tg_path": str(tg_path),
    }


# ============================================================================
# BUILD COMBINED COMPARISON TEXTGRID
# ============================================================================

def build_comparison_textgrid(
    wav_stem: str,
    duration: float,
    backend_results: list[dict],
    human_tg_path: Optional[Path],
    out_path: Path,
):
    """Merge all backend tiers (+ optional human annotation) into one TextGrid."""
    all_tiers = []

    # Human annotation first (reference)
    if human_tg_path and human_tg_path.exists():
        _, human_tiers = parse_textgrid_tiers(human_tg_path)
        human_include = ["tx@TA", "wd@TA", "ph@TA", "mb@TA", "gl@TA",
                         "ps@TA", "ref@TA", "ft@TA"]
        all_tiers.extend(human_tiers_as_speechprint_format(human_tiers, human_include))
        print(f"  + {len(all_tiers)} human tiers from {human_tg_path.name}", flush=True)

    # Each backend's tiers
    for res in backend_results:
        if "error" in res or "tiers" not in res:
            continue
        for tier in res["tiers"]:
            all_tiers.append(tier)

    write_textgrid(out_path, duration, all_tiers)
    print(f"  Comparison TextGrid ({len(all_tiers)} tiers): {out_path}", flush=True)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multi-aligner evaluation pipeline")
    parser.add_argument("--wav", required=True, help="WAV file to process")
    parser.add_argument("--language", "--lang", required=True, help="Language code (en, it, pt...)")
    parser.add_argument("--reference", help="Human-annotated TextGrid for comparison")
    parser.add_argument("--output", default="out/eval", help="Output directory")
    parser.add_argument("--backends", nargs="+",
                        default=["whisper", "whisperx", "gentle", "mfa"],
                        help="Which backends to run")
    args = parser.parse_args()

    wav = Path(args.wav).resolve()
    if not wav.exists():
        print(f"ERROR: {wav} not found", file=sys.stderr)
        return 1

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = wav_duration(wav)
    print(f"\n=== SpeechPrint Multi-Aligner Evaluation ===")
    print(f"WAV:      {wav.name} ({duration:.1f}s)")
    print(f"Language: {args.language}")
    print(f"Output:   {out_dir}")
    print(f"Backends: {args.backends}")

    # Step 1: Transcription (shared)
    print(f"\n[1/2] Transcribing ({args.language})...", flush=True)
    transcript = get_transcript(wav, args.language)
    print(f"  Source: {transcript['source']}")
    print(f"  Text: {transcript['text'][:80]}...", flush=True)

    # Pre-run MFA once (expensive)
    mfa_results = None
    if "mfa" in args.backends:
        print(f"\n[pre] Running MFA (phone-level alignment)...", flush=True)
        mfa_results = align_mfa(wav, transcript, args.language)
        print(f"  {mfa_results[2]}", flush=True)

    # Step 2: Each backend
    print(f"\n[2/2] Running alignment backends...", flush=True)
    backend_results = []
    for backend in args.backends:
        res = run_backend(
            backend=backend,
            wav=wav,
            transcript=transcript,
            language=args.language,
            out_dir=out_dir / backend,
            mfa_results=mfa_results if backend == "mfa" else None,
        )
        backend_results.append(res)

    # Step 3: Combined comparison TextGrid
    print(f"\n[3/3] Building comparison TextGrid...", flush=True)
    ref_path = Path(args.reference) if args.reference else None
    comp_path = out_dir / f"{wav.stem}_COMPARISON.TextGrid"
    build_comparison_textgrid(wav.stem, duration, backend_results, ref_path, comp_path)

    # Step 4: Summary JSON
    summary = {
        "wav": wav.name,
        "language": args.language,
        "duration_s": duration,
        "transcript_source": transcript["source"],
        "transcript_preview": transcript["text"][:200],
        "backends": [
            {k: v for k, v in r.items() if k not in ("tiers",)}
            for r in backend_results
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(f"\n✓ Done. Outputs in: {out_dir}")
    for res in backend_results:
        n_w = res.get("words", 0)
        n_s = res.get("syllables", 0)
        n_p = res.get("phonemes", 0)
        err = f" [ERROR: {res.get('error')}]" if "error" in res else ""
        print(f"  {res['backend']:10s}  {n_w:3d} words  {n_s:3d} sylls  {n_p:4d} phones{err}")
    print(f"  COMPARISON TextGrid: {comp_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
