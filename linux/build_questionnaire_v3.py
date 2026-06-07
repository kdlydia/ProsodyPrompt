#!/usr/bin/env python3
"""Build questionnaire_2026-06-02 folder.

Creates SpeechPrint TextGrids for:
  - English audio_2026-05-30_19-01-35.wav  (MFA alignment, improved pitch)
  - German: 5 GToBI sentences              (human-annotated words + GToBI Ton tier)
  - Doreco port1286_2017_06_30_Jaklin.wav  (Spanish/Italian Whisper + improved pitch)

Key improvements over v2:
  - Primary pitch tracker: Librosa pYIN (extracted ONCE per file, then reused)
  - Xu(1999) octave correction + triangular smoothing on the full track
  - Speaker-adaptive pitch range (auto-detect from median F0)
  - Better symbolic layer: wider neighbour window, IPA labels always
  - German: Wort + Ton (hand-annotated GToBI) tiers included
"""

from __future__ import annotations

import json
import math
import re
import shutil
import statistics
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent
GTOBI_DIR = BASE / " five GToBI annotated sentences"
ENGLISH_WAV = BASE / "audio_2026-05-30_19-01-35.wav"
DORECO_WAV  = BASE / "doreco_port1286_2017_06_30_Jaklin.wav"

QDATE = "2026-06-02"
OUT_BASE = BASE / "out" / f"questionaire_{QDATE}"

GERMAN_SENTENCES = [
    "eine_gelbe_banane",
    "einige_melonen",
    "er_sang_die_lieder",
    "er_will_die_rosen_haben",
    "ich_wohne_in_bern",
]

ENGLISH_JSON = BASE / "out/english_v2/audio_2026-05-30_19-01-35/audio_2026-05-30_19-01-35.json"
GERMAN_JSON_BASE = BASE / "out/german_gtobi"
DORECO_JSON_IT = BASE / "out/daakie_it_v2/doreco_port1286_2017_06_30_Jaklin/doreco_port1286_2017_06_30_Jaklin.json"
DORECO_JSON_ES = BASE / "out/daakie_es_v2/doreco_port1286_2017_06_30_Jaklin/doreco_port1286_2017_06_30_Jaklin.json"

SILENCE_LABELS = {"", "sp", "sil", "SIL", "<eps>", "<sil>", "spn"}

VOWELS_IPA = {
    "a", "e", "i", "o", "u",
    "æ", "ɑ", "ɒ", "ɐ", "ə", "ɚ", "ɛ", "ɜ", "ɝ", "ɪ", "ɨ",
    "ɔ", "ø", "œ", "ʊ", "ʌ", "y", "ɯ", "ɵ", "ɘ", "ɤ", "ɞ",
    "ã", "ɛ̃", "ɔ̃", "œ̃", "ɑ̃",
    "iː", "uː", "eː", "oː", "aː", "ɑː", "ɔː", "ɛː",
    "eɪ", "oʊ", "aɪ", "aʊ", "ɔɪ",
}

WEAK_RISE_FLOOR_ST   = 0.5
WEAK_FALL_FLOOR_ST   = 0.5
ADAPTIVE_FACTOR      = 0.35
STRONG_FACTOR        = 2.5
HIGH_NBR_ST          = 0.8
LOW_NBR_ST           = 0.8
ACCENT_AMP_DB        = 1.5
ACCENT_F0_ST         = 1.0
VELOCITY_STRONG_ST_S = 6.0
DURATION_ACCENT_FACTOR = 1.25
SPIKE_THRESHOLD_ST   = 10.0


# ─── Utilities ───────────────────────────────────────────────────────────────

def _st(a, b):
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12 * math.log2(b / a)

def _safe_mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else None

def _is_vowel(phone: str) -> bool:
    if not phone:
        return False
    if phone in VOWELS_IPA:
        return True
    if phone in {"w", "j", "ʋ", "ɥ", "h", "ɦ", "l", "r", "ɹ", "ɾ", "ɻ"}:
        return False
    return any(ch in VOWELS_IPA for ch in phone)

def _esc(t) -> str:
    return str(t).replace('"', "'")


# ─── Pitch track (extracted once per file) ────────────────────────────────────

class PitchTrack:
    """Holds pre-computed pitch + amplitude arrays for a WAV file."""

    def __init__(self, wav_path: Path, floor: float = 75.0, ceiling: float = 500.0):
        self.wav_path = wav_path
        self.floor    = floor
        self.ceiling  = ceiling
        self.times    = np.array([])
        self.f0       = np.array([])   # 0 = unvoiced
        self._amp_snd = None
        self._amp_int = None
        self._loaded  = False
        self._sr      = None

    def load(self) -> None:
        if self._loaded:
            return

        print(f"    Loading pitch track: {self.wav_path.name} "
              f"(floor={self.floor:.0f}, ceiling={self.ceiling:.0f} Hz) …", flush=True)

        # --- Primary: Librosa pYIN ---
        try:
            import librosa
            y, sr = librosa.load(str(self.wav_path), sr=16000, mono=True)
            self._sr = sr
            hop = 256
            f0_full, voiced_flag, _ = librosa.pyin(
                y, fmin=self.floor, fmax=self.ceiling, sr=sr,
                frame_length=2048, hop_length=hop,
            )
            self.times = librosa.frames_to_time(
                np.arange(len(f0_full)), sr=sr, hop_length=hop
            )
            f0_raw = np.where(voiced_flag & ~np.isnan(f0_full), f0_full, 0.0)
            self.f0 = self._correct_octaves(f0_raw)
            print(f"    pYIN: {int(np.sum(self.f0 > 30))} voiced frames, "
                  f"median={np.median(self.f0[self.f0>30]):.1f} Hz", flush=True)
        except Exception as e:
            print(f"    pYIN failed ({e}), falling back to Praat …", flush=True)
            self._load_praat()

        # --- Amplitude: Praat Intensity ---
        try:
            import parselmouth
            snd = parselmouth.Sound(str(self.wav_path))
            self._amp_snd = snd
            self._amp_int = snd.to_intensity()
        except Exception:
            pass

        self._loaded = True

    def _load_praat(self) -> None:
        import parselmouth
        snd = parselmouth.Sound(str(self.wav_path))
        pitch = snd.to_pitch_ac(
            pitch_floor=self.floor,
            pitch_ceiling=self.ceiling,
            octave_jump_cost=0.5,
            very_accurate=True,
        )
        self.times = pitch.xs()
        f0_raw = np.array([
            float(pitch.get_value_at_time(t)) if not math.isnan(float(pitch.get_value_at_time(t) or 0)) else 0.0
            for t in self.times
        ])
        f0_raw = np.where(f0_raw > 30, f0_raw, 0.0)
        self.f0 = self._correct_octaves(f0_raw)
        print(f"    Praat AC: {int(np.sum(self.f0 > 30))} voiced frames", flush=True)
        self._amp_snd = parselmouth.Sound(str(self.wav_path))
        try:
            self._amp_int = self._amp_snd.to_intensity()
        except Exception:
            pass

    def _correct_octaves(self, f0: np.ndarray) -> np.ndarray:
        """Xu (1999) octave spike correction + triangular smoothing."""
        f0c = f0.copy()
        voiced = f0c[f0c > 30]
        if len(voiced) < 3:
            return f0c
        med = float(np.median(voiced))

        for _pass in range(2):
            for i in range(len(f0c)):
                v = f0c[i]
                if v < 30:
                    continue
                st = 12 * math.log2(v / med) if v > 0 and med > 0 else 0
                if abs(st) > SPIKE_THRESHOLD_ST:
                    cand_up   = v * 2.0
                    cand_down = v / 2.0
                    d_up   = abs(12 * math.log2(cand_up / med))   if 30 < cand_up   < 800 else 999
                    d_down = abs(12 * math.log2(cand_down / med)) if cand_down > 30         else 999
                    d_orig = abs(st)
                    if d_up < d_orig and d_up <= SPIKE_THRESHOLD_ST:
                        f0c[i] = cand_up
                    elif d_down < d_orig and d_down <= SPIKE_THRESHOLD_ST:
                        f0c[i] = cand_down
                    else:
                        f0c[i] = 0.0

            # Update median after each pass
            voiced = f0c[f0c > 30]
            if len(voiced) >= 2:
                med = float(np.median(voiced))

        # Triangular smoothing
        voiced_idx = np.where(f0c > 30)[0]
        for k in range(1, len(voiced_idx) - 1):
            i0, i1, i2 = voiced_idx[k-1], voiced_idx[k], voiced_idx[k+1]
            if i2 - i0 <= 5:
                f0c[i1] = (f0c[i0] + 2.0 * f0c[i1] + f0c[i2]) / 4.0

        return f0c

    def get_f0_at(self, t: float) -> float | None:
        """Interpolate F0 at time t. Returns None if unvoiced."""
        if len(self.times) == 0:
            return None
        idx = int(np.argmin(np.abs(self.times - t)))
        v = float(self.f0[idx])
        return v if v > 30 else None

    def get_f0_segment(self, t_start: float, t_end: float, n: int = 10) -> list[float | None]:
        """Get n F0 samples across [t_start, t_end]."""
        if len(self.times) == 0:
            return [None] * n
        ts = [t_start + (t_end - t_start) * j / (n - 1) for j in range(n)]
        return [self.get_f0_at(t) for t in ts]

    def get_amplitude(self, t_start: float, t_end: float, n: int = 10) -> float | None:
        if self._amp_int is None:
            return None
        ts = [t_start + (t_end - t_start) * j / (n - 1) for j in range(n)]
        vals = []
        for t in ts:
            try:
                db = float(self._amp_int.get_value(t))
                if not math.isnan(db):
                    vals.append(db)
            except Exception:
                pass
        return _safe_mean(vals)


def make_pitch_track(wav_path: Path) -> PitchTrack:
    """Create and load a PitchTrack with auto-detected speaker range."""
    # Quick scan to estimate speaker's median F0 range
    floor, ceiling = 75.0, 500.0
    try:
        import librosa
        y, sr = librosa.load(str(wav_path), sr=16000, mono=True, duration=20.0)
        f0_scan, voiced_scan, _ = librosa.pyin(
            y, fmin=65.0, fmax=500.0, sr=sr,
            frame_length=2048, hop_length=1024,
        )
        voiced_scan_vals = f0_scan[voiced_scan & ~np.isnan(f0_scan)]
        if len(voiced_scan_vals) >= 5:
            med = float(np.median(voiced_scan_vals))
            floor   = max(50.0,  med * 0.5)
            ceiling = min(600.0, med * 2.5)
    except Exception:
        pass

    pt = PitchTrack(wav_path, floor, ceiling)
    pt.load()
    return pt


# ─── Measure vowel nucleus ─────────────────────────────────────────────────────

def measure_vowel(pt: PitchTrack, nuc_start: float, nuc_end: float) -> dict:
    """Measure F0 and amplitude at vowel nucleus using pre-loaded PitchTrack."""
    dur = nuc_end - nuc_start
    if dur <= 0.005:
        return {"f0_onset": None, "f0_mid": None, "f0_offset": None,
                "f0_mean": None, "amplitude_db": None, "voiced": False,
                "velocity_st_s": None}

    n = 10
    f0_pts = pt.get_f0_segment(nuc_start, nuc_end, n)
    amp = pt.get_amplitude(nuc_start, nuc_end, n)

    voiced = [v for v in f0_pts if v is not None]
    f0_onset  = next((v for v in f0_pts if v), None)
    f0_offset = next((v for v in reversed(f0_pts) if v), None)

    mid_idx = n // 2
    f0_mid = None
    for delta in range(n // 2 + 1):
        for idx in (mid_idx - delta, mid_idx + delta):
            if 0 <= idx < n and f0_pts[idx] is not None:
                f0_mid = f0_pts[idx]
                break
        if f0_mid:
            break

    f0_mean = _safe_mean(voiced)
    velocity = None
    if f0_onset and f0_offset and dur > 0:
        mv = _st(f0_onset, f0_offset)
        if mv is not None:
            velocity = mv / dur

    return {
        "f0_onset": f0_onset, "f0_mid": f0_mid, "f0_offset": f0_offset,
        "f0_mean": f0_mean, "amplitude_db": amp,
        "voiced": len(voiced) / n > 0.3,
        "velocity_st_s": velocity,
    }


# ─── Syllabification ──────────────────────────────────────────────────────────

def find_vowel_nucleus(phones: list[str], syl_start: float, syl_end: float,
                       mfa_ivs: list[dict] | None = None) -> tuple[float, float]:
    vowel_idx = [i for i, p in enumerate(phones) if _is_vowel(p)]
    if not vowel_idx:
        return syl_start, syl_end
    if mfa_ivs:
        syl_mfa = [iv for iv in mfa_ivs
                   if iv["start"] >= syl_start - 1e-4 and iv["end"] <= syl_end + 1e-4
                   and iv["label"] not in SILENCE_LABELS]
        if syl_mfa:
            vowel_mfa = [iv for iv in syl_mfa if _is_vowel(iv["label"])]
            if vowel_mfa:
                return float(vowel_mfa[0]["start"]), float(vowel_mfa[-1]["end"])
    total = len(phones)
    syl_dur = syl_end - syl_start
    nuc_start = syl_start + syl_dur * vowel_idx[0] / total
    nuc_end   = syl_start + syl_dur * (vowel_idx[-1] + 1) / total
    return nuc_start, nuc_end


def phones_to_syllables(phones: list[str], word_start: float, word_end: float,
                        mfa_ivs: list[dict] | None = None) -> list[dict]:
    if not phones:
        return []
    vowel_idx = [i for i, p in enumerate(phones) if _is_vowel(p)]
    if not vowel_idx:
        v_s, v_e = find_vowel_nucleus(phones, word_start, word_end, mfa_ivs)
        return [{"label": "".join(phones), "start": word_start, "end": word_end,
                 "phones": phones, "vowel_start": v_s, "vowel_end": v_e}]

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
            boundaries.append((onset_start, len(phones)))
        else:
            boundaries.append((onset_start, vi + 1))

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


# ─── Improved symbolic prosody ────────────────────────────────────────────────

def label_prosody_v3(syllables: list[dict]) -> None:
    """Improved prosody labelling (v3).

    Key improvements over v2:
    - Neighbour window ±2 (wider context)
    - Recording-level median F0 as secondary height reference
    - Accent also fires when louder AND (longer OR any height advantage)
    - Strong rise/fall: either very large magnitude OR (magnitude + velocity)
    - All unvoiced syllables get '?' unless neighbours are both voiced
    """
    n = len(syllables)
    if n == 0:
        return

    for syl in syllables:
        mv  = _st(syl.get("f0_onset"), syl.get("f0_offset"))
        syl["_mv"]  = mv
        syl["_vel"] = syl.get("velocity_st_s")

    mvs_valid = [abs(syl["_mv"]) for syl in syllables if syl["_mv"] is not None]
    if len(mvs_valid) >= 2:
        rec_std = statistics.stdev(mvs_valid)
    else:
        rec_std = 2.0

    weak_thr   = max(WEAK_RISE_FLOOR_ST, ADAPTIVE_FACTOR * rec_std)
    strong_thr = max(weak_thr * STRONG_FACTOR, 2.5)

    all_f0_means = [s.get("f0_mean") for s in syllables if s.get("f0_mean")]
    rec_median_f0 = statistics.median(all_f0_means) if all_f0_means else None

    for i, syl in enumerate(syllables):
        mv      = syl["_mv"]
        vel     = syl["_vel"]
        f0_mean = syl.get("f0_mean")
        amp     = syl.get("amplitude_db")

        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in range(max(0, i-2), min(n, i+3)):
            if j == i:
                continue
            v = syllables[j].get("f0_mean")
            a = syllables[j].get("amplitude_db")
            d = syllables[j]["end"] - syllables[j]["start"]
            if v: nbr_f0.append(v)
            if a: nbr_amp.append(a)
            nbr_dur.append(d)

        nbr_mean_f0  = _safe_mean(nbr_f0)
        nbr_mean_amp = _safe_mean(nbr_amp)
        nbr_mean_dur = _safe_mean(nbr_dur) if nbr_dur else None
        syl_dur = syl["end"] - syl["start"]
        is_long = (nbr_mean_dur is not None and syl_dur >= DURATION_ACCENT_FACTOR * nbr_mean_dur)

        height_st = _st(nbr_mean_f0, f0_mean) if (nbr_mean_f0 and f0_mean) else None
        height_vs_rec = _st(rec_median_f0, f0_mean) if (rec_median_f0 and f0_mean) else None

        is_high = ((height_st is not None and height_st >= HIGH_NBR_ST) or
                   (height_vs_rec is not None and height_vs_rec >= HIGH_NBR_ST * 1.5))
        is_low  = ((height_st is not None and height_st <= -LOW_NBR_ST) and
                   (height_vs_rec is None or height_vs_rec <= 0))

        amp_above = (amp - nbr_mean_amp) if (amp is not None and nbr_mean_amp is not None) else None
        is_loud   = amp_above is not None and amp_above >= ACCENT_AMP_DB

        mag_strong = abs(mv) >= strong_thr if mv is not None else False
        vel_strong = abs(vel) >= VELOCITY_STRONG_ST_S if vel is not None else False

        if mv is None:
            direction = ""
        elif mv >= weak_thr:
            direction = "//" if (mag_strong and vel_strong) or abs(mv) >= strong_thr * 1.5 else "/"
        elif mv <= -weak_thr:
            direction = "\\\\" if (mag_strong and vel_strong) or abs(mv) >= strong_thr * 1.5 else "\\"
        else:
            direction = ""

        if direction == "":
            height_sym = "-" if is_high else ("_" if is_low else ("-" if f0_mean and nbr_mean_f0 else "?"))
        else:
            height_sym = "-" if is_high else ("_" if is_low else "")

        is_accent = is_loud and (
            (height_st is not None and height_st >= ACCENT_F0_ST)
            or is_long
            or (height_vs_rec is not None and height_vs_rec >= ACCENT_F0_ST)
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
            symbol = "?" if not f0_mean else "-"

        syl["symbol"]    = symbol
        syl["is_accent"] = is_accent


# ─── Build prosody tiers from pre-loaded pitch track ─────────────────────────

def build_prosody_tiers(pt: PitchTrack, words: list[dict], phones_per_word: list[list],
                         mfa_phones: list[dict] | None = None
                         ) -> tuple[list, list, list, list]:
    all_syllables = []
    syllable_rows = []
    f0_rows       = []

    for wi, (w, phones) in enumerate(zip(words, phones_per_word)):
        sylls = phones_to_syllables(phones, w["start"], w["end"], mfa_phones)
        for syl in sylls:
            m = measure_vowel(pt, syl["vowel_start"], syl["vowel_end"])
            syl.update(m)
            syl["word_idx"] = wi
            all_syllables.append(syl)
            syllable_rows.append({"start": syl["start"], "end": syl["end"],
                                   "value": syl["label"]})

    label_prosody_v3(all_syllables)

    for syl in all_syllables:
        f0_label = ""
        if syl.get("f0_onset"):
            on  = int(round(syl["f0_onset"]))
            off = int(round(syl["f0_offset"])) if syl.get("f0_offset") else "?"
            amp = f"{round(syl['amplitude_db'], 1)}dB" if syl.get("amplitude_db") else "?"
            f0_label = f"{on}|{off}Hz  {amp}"
        f0_rows.append({"start": syl["start"], "end": syl["end"], "value": f0_label})

    prosody_rows = [
        {"start": syl["start"], "end": syl["end"], "value": syl.get("symbol", "?")}
        for syl in all_syllables
    ]

    return syllable_rows, f0_rows, prosody_rows, all_syllables


# ─── Phonemizer helper ────────────────────────────────────────────────────────

ESPEAK_LANG = {"en": "en-us", "de": "de", "it": "it", "es": "es", "pt": "pt"}

def phonemize_words_list(word_strings: list[str], lang: str) -> list[list[str]]:
    try:
        from phonemizer import phonemize
        from phonemizer.separator import Separator
        ipa_raw = phonemize(
            word_strings, language=ESPEAK_LANG.get(lang, "en-us"), backend="espeak",
            separator=Separator(phone=" ", word=" | ", syllable=""),
            strip=True, preserve_punctuation=False, with_stress=False, njobs=1,
        )
        if isinstance(ipa_raw, str):
            ipa_raw = [ipa_raw]
        return [[p for p in (line or "").split() if p and p != "|"] for line in ipa_raw]
    except Exception as e:
        print(f"    phonemizer failed: {e}", flush=True)
        return [[] for _ in word_strings]


# ─── TextGrid I/O ─────────────────────────────────────────────────────────────

def parse_textgrid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def _find(pat, start=0):
        for i in range(start, len(lines)):
            m = re.match(pat, lines[i].strip())
            if m:
                return i, m
        return -1, None

    _, m = _find(r"xmin\s*=\s*([\d.eE+\-]+)"); xmin = float(m.group(1)) if m else 0.0
    _, m = _find(r"xmax\s*=\s*([\d.eE+\-]+)"); xmax = float(m.group(1)) if m else 0.0

    tiers, i = [], 0
    while i < len(lines):
        m = re.match(r"\s*item\s*\[(\d+)\]\s*:", lines[i])
        if not m:
            i += 1
            continue
        tier = {}
        i += 1
        while i < len(lines):
            l = lines[i].strip()
            if re.match(r"item\s*\[", l):
                break
            for pat, key in [(r'class\s*=\s*"(.+)"', "class"),
                             (r'name\s*=\s*"(.*)"',  "name")]:
                mm = re.match(pat, l)
                if mm:
                    tier[key] = mm.group(1)
            if re.match(r"intervals:\s*size\s*=\s*(\d+)", l):
                n_iv = int(re.match(r"intervals:\s*size\s*=\s*(\d+)", l).group(1))
                ivs = []
                i += 1
                while i < len(lines) and len(ivs) < n_iv:
                    lx = lines[i].strip()
                    if re.match(r"intervals\s*\[", lx):
                        iv = {}
                        i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(intervals|points|item)\s*\[", lv):
                                break
                            for rx, fld in [(r"xmin\s*=\s*([\d.eE+\-]+)", "xmin"),
                                            (r"xmax\s*=\s*([\d.eE+\-]+)", "xmax"),
                                            (r'text\s*=\s*"(.*)"', "text")]:
                                mm2 = re.match(rx, lv)
                                if mm2:
                                    iv[fld] = float(mm2.group(1)) if fld != "text" else mm2.group(1)
                            i += 1
                        ivs.append(iv)
                    else:
                        i += 1
                tier["intervals"] = ivs
                continue
            if re.match(r"points:\s*size\s*=\s*(\d+)", l):
                n_pts = int(re.match(r"points:\s*size\s*=\s*(\d+)", l).group(1))
                pts = []
                i += 1
                while i < len(lines) and len(pts) < n_pts:
                    lx = lines[i].strip()
                    if re.match(r"points\s*\[", lx):
                        pt_ = {}
                        i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(points|item)\s*\[", lv):
                                break
                            mm2 = re.match(r"number\s*=\s*([\d.eE+\-]+)", lv)
                            mk  = re.match(r'mark\s*=\s*"(.*)"', lv)
                            if mm2: pt_["number"] = float(mm2.group(1))
                            elif mk: pt_["mark"] = mk.group(1)
                            i += 1
                        pts.append(pt_)
                    else:
                        i += 1
                tier["points"] = pts
                continue
            i += 1
        if "name" in tier:
            tiers.append(tier)
    return {"xmin": xmin, "xmax": xmax, "tiers": tiers}


def _fill_gaps(rows: list[dict], xmax: float) -> list[dict]:
    out = []
    cursor = 0.0
    for r in sorted(rows, key=lambda x: x.get("start", x.get("xmin", 0))):
        s = float(r.get("start", r.get("xmin", 0)))
        e = float(r.get("end",   r.get("xmax", 0)))
        if s > cursor + 5e-4:
            out.append({"start": cursor, "end": s, "value": ""})
        out.append({"start": s, "end": e, "value": r.get("value", r.get("text", ""))})
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
        tc = tier.get("class", "IntervalTier")
        lines += [
            f"    item [{ti}]:",
            f'        class = "{tc}"',
            f'        name = "{_esc(tier["name"])}"',
            "        xmin = 0",
            f"        xmax = {xmax}",
        ]
        if tc == "TextTier":
            pts = tier.get("points", [])
            lines.append(f"        points: size = {len(pts)}")
            for ii, pt in enumerate(pts, 1):
                lines += [
                    f"        points [{ii}]:",
                    f"            number = {pt.get('number', 0.0)}",
                    f'            mark = "{_esc(pt.get("mark", ""))}"',
                ]
        else:
            rows = _fill_gaps(tier.get("rows", tier.get("intervals", [])), xmax)
            lines.append(f"        intervals: size = {len(rows)}")
            for ii, row in enumerate(rows, 1):
                lines += [
                    f"        intervals [{ii}]:",
                    f"            xmin = {row['start']}",
                    f"            xmax = {row['end']}",
                    f'            text = "{_esc(row["value"])}"',
                ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─── Build English ────────────────────────────────────────────────────────────

def build_english(out_dir: Path) -> None:
    print("\n── English (audio_2026-05-30_19-01-35.wav)", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not ENGLISH_JSON.exists():
        print(f"  SKIP: JSON not found", flush=True)
        shutil.copy2(ENGLISH_WAV, out_dir / ENGLISH_WAV.name)
        return

    data = json.loads(ENGLISH_JSON.read_text(encoding="utf-8"))
    words = data["words"]
    mfa_phones = data.get("mfa_phones", [])
    duration = float(data.get("duration_s", max(w["end"] for w in words) + 0.1))

    word_strings = [w["word"] for w in words]
    phones_per_word = phonemize_words_list(word_strings, "en")

    word_rows = []
    prev_end = 0.0
    for w in words:
        gap = w["start"] - prev_end
        if gap > 0.04:
            word_rows.append({"start": prev_end, "end": w["start"],
                               "value": f"<sil {gap:.2f}s>"})
        word_rows.append({"start": w["start"], "end": w["end"], "value": w["word"]})
        prev_end = w["end"]

    phone_rows = (
        [{"start": p["start"], "end": p["end"], "value": p["label"]}
         for p in mfa_phones if p.get("label", "") not in SILENCE_LABELS]
        if mfa_phones else
        [{"start": p["start"], "end": p["end"], "value": p["label"]}
         for p in data.get("phonemes", []) if p.get("label", "") not in SILENCE_LABELS]
    )

    pt = make_pitch_track(ENGLISH_WAV)
    syl_rows, f0_rows, pro_rows, syls = build_prosody_tiers(
        pt, words, phones_per_word, mfa_phones or None
    )

    tiers = [
        {"name": "words",    "rows": word_rows},
        {"name": "phonemes", "rows": phone_rows},
        {"name": "syllables","rows": syl_rows},
        {"name": "f0_vowel", "rows": f0_rows},
        {"name": "prosody",  "rows": pro_rows},
    ]

    out_tg = out_dir / f"{ENGLISH_WAV.stem}.TextGrid"
    write_textgrid(out_tg, duration, tiers)
    shutil.copy2(ENGLISH_WAV, out_dir / ENGLISH_WAV.name)

    accented = [s for s in syls if s.get("is_accent")]
    print(f"  Syllables: {len(syl_rows)}, accented (*): {len(accented)}", flush=True)
    for s in accented[:8]:
        on  = int(s['f0_onset'])  if s.get('f0_onset')  else "?"
        off = int(s['f0_offset']) if s.get('f0_offset') else "?"
        print(f"    [{s['label']}] {s['symbol']}  F0:{on}→{off}Hz  "
              f"amp:{round(s.get('amplitude_db') or 0, 1)}dB", flush=True)
    print(f"  TextGrid: {out_tg}", flush=True)


# ─── Build German GToBI ───────────────────────────────────────────────────────

def build_german_sentence(name: str, out_dir: Path) -> None:
    print(f"\n── German: {name}", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_path   = GTOBI_DIR / f"{name}.wav"
    gtobi_path = GTOBI_DIR / f"{name}.TextGrid"
    if not gtobi_path.exists():
        print(f"  SKIP: GToBI not found", flush=True)
        return

    gtobi    = parse_textgrid(gtobi_path)
    gtobi_by = {t["name"]: t for t in gtobi["tiers"]}
    wort_tier = gtobi_by.get("Wort")
    ton_tier  = gtobi_by.get("Ton")
    xmax = gtobi["xmax"]

    word_intervals = [
        {"start": iv["xmin"], "end": iv["xmax"], "word": iv["text"].lower()}
        for iv in (wort_tier or {}).get("intervals", [])
        if iv.get("text", "").strip()
    ]
    if not word_intervals:
        print("  SKIP: no words in Wort tier", flush=True)
        return

    word_strings    = [w["word"] for w in word_intervals]
    phones_per_word = phonemize_words_list(word_strings, "de")

    pt = make_pitch_track(wav_path)
    syl_rows, f0_rows, pro_rows, syls = build_prosody_tiers(
        pt, word_intervals, phones_per_word
    )

    phone_rows = []
    for wi, (w, phones) in enumerate(zip(word_intervals, phones_per_word)):
        if not phones:
            continue
        dur = w["end"] - w["start"]
        per_ph = dur / len(phones)
        for j, ph in enumerate(phones):
            ps = w["start"] + per_ph * j
            pe = w["start"] + per_ph * (j + 1)
            if j == len(phones) - 1:
                pe = w["end"]
            phone_rows.append({"start": ps, "end": pe, "value": ph})

    # Wort rows from GToBI (include empty intervals for proper coverage)
    wort_rows = [{"start": iv["xmin"], "end": iv["xmax"], "value": iv.get("text", "")}
                 for iv in (wort_tier or {}).get("intervals", [])]

    tiers = []
    if wort_tier:
        tiers.append({"name": "Wort", "rows": wort_rows})
    if ton_tier:
        tiers.append({"name": "Ton", "class": "TextTier", "points": ton_tier.get("points", [])})
    tiers += [
        {"name": "syllables", "rows": syl_rows},
        {"name": "phonemes",  "rows": phone_rows},
        {"name": "f0_vowel",  "rows": f0_rows},
        {"name": "prosody",   "rows": pro_rows},
    ]

    out_tg = out_dir / f"{name}.TextGrid"
    write_textgrid(out_tg, xmax, tiers)
    shutil.copy2(wav_path, out_dir / f"{name}.wav")

    tons = [(pt_["number"], pt_["mark"]) for pt_ in (ton_tier or {}).get("points", [])]
    print(f"  GToBI tones: {tons}", flush=True)
    accented = [s for s in syls if s.get("is_accent")]
    print(f"  Syllables: {len(syl_rows)}, accented: {len(accented)}", flush=True)
    for s in accented[:4]:
        on  = int(s['f0_onset'])  if s.get('f0_onset')  else "?"
        off = int(s['f0_offset']) if s.get('f0_offset') else "?"
        print(f"    [{s['label']}] {s['symbol']}  F0:{on}→{off}Hz", flush=True)
    print(f"  TextGrid: {out_tg}", flush=True)


# ─── Build Doreco ─────────────────────────────────────────────────────────────

def build_doreco(out_dir: Path) -> None:
    print("\n── Doreco port1286 (Daakie)", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = DORECO_JSON_IT if DORECO_JSON_IT.exists() else DORECO_JSON_ES
    if not json_path.exists():
        print(f"  SKIP: no JSON found", flush=True)
        return

    lang = "it" if DORECO_JSON_IT.exists() else "es"
    print(f"  Using {lang} Whisper alignment", flush=True)

    data     = json.loads(json_path.read_text(encoding="utf-8"))
    words    = data["words"]
    duration = float(data.get("duration_s", max(w["end"] for w in words) + 0.1))

    word_strings    = [w["word"] for w in words]
    phones_per_word = phonemize_words_list(word_strings, lang)

    word_rows = []
    prev_end = 0.0
    for w in words:
        gap = w["start"] - prev_end
        if gap > 0.04:
            word_rows.append({"start": prev_end, "end": w["start"],
                               "value": f"<sil {gap:.2f}s>"})
        word_rows.append({"start": w["start"], "end": w["end"], "value": w["word"]})
        prev_end = w["end"]

    pt = make_pitch_track(DORECO_WAV)
    syl_rows, f0_rows, pro_rows, syls = build_prosody_tiers(pt, words, phones_per_word)

    phone_rows = []
    for wi, (w, phones) in enumerate(zip(words, phones_per_word)):
        if not phones:
            continue
        dur = w["end"] - w["start"]
        per_ph = dur / len(phones)
        for j, ph in enumerate(phones):
            ps = w["start"] + per_ph * j
            pe = w["start"] + per_ph * (j + 1)
            if j == len(phones) - 1:
                pe = w["end"]
            phone_rows.append({"start": ps, "end": pe, "value": ph})

    tiers = [
        {"name": "words",     "rows": word_rows},
        {"name": "phonemes",  "rows": phone_rows},
        {"name": "syllables", "rows": syl_rows},
        {"name": "f0_vowel",  "rows": f0_rows},
        {"name": "prosody",   "rows": pro_rows},
    ]

    name   = DORECO_WAV.stem
    out_tg = out_dir / f"{name}.TextGrid"
    write_textgrid(out_tg, duration, tiers)
    shutil.copy2(DORECO_WAV, out_dir / DORECO_WAV.name)

    accented = [s for s in syls if s.get("is_accent")]
    print(f"  Syllables: {len(syl_rows)}, accented: {len(accented)}", flush=True)
    print(f"  TextGrid: {out_tg}", flush=True)


# ─── Write README ─────────────────────────────────────────────────────────────

def write_readme(out_base: Path) -> None:
    text = f"""QUESTIONNAIRE OUTPUT — {QDATE}
{"=" * 50}

This folder contains SpeechPrint v3 TextGrids for:

  english/
    audio_2026-05-30_19-01-35.TextGrid  — English minimal pairs recording
    audio_2026-05-30_19-01-35.wav

  german_gtobi/
    eine_gelbe_banane.TextGrid          — Tiers: Wort (human) + Ton (GToBI annotation)
    einige_melonen.TextGrid             —        + syllables (IPA) + phonemes (IPA)
    er_sang_die_lieder.TextGrid         —        + f0_vowel (onset|offset Hz  amp dB)
    er_will_die_rosen_haben.TextGrid    —        + prosody (/ \\ * - _ symbols)
    ich_wohne_in_bern.TextGrid

  doreco/
    doreco_port1286_2017_06_30_Jaklin.TextGrid
    doreco_port1286_2017_06_30_Jaklin.wav

PITCH TRACKING (v3 improvements over v2):
  PRIMARY  : Librosa pYIN — probabilistic YIN, returns voiced/unvoiced confidence,
             more robust against octave errors than Praat SCC
  FALLBACK : Praat to_pitch_ac() with octave_jump_cost=0.5
  CORRECTION: Xu (1999) / ProsodyPro octave-spike removal:
             - median of voiced frames computed
             - frames >10 ST from median: try F0/2 and F0*2
             - keep whichever is closest to median
             - triangular smoothing (1:2:1) over 3 consecutive voiced frames
  RANGE    : speaker-adaptive floor/ceiling from 20-second scan (pYIN)

PROSODY SYMBOLS (v3):
  /    rising intra-syllable pitch (onset→offset > threshold)
  //   strongly rising (very large excursion)
  \\   falling
  \\\\  strongly falling
  -    high level relative to neighbours
  _    low level relative to neighbours
  *    prominent accent (louder AND higher/longer)
  ?    unvoiced (no pitch data)
  Combinations: */ *\\ *- *_ */ *// etc.

SYMBOLIC LAYER (v3 improvements):
  - Neighbour window: ±2 syllables (was ±1)
  - Recording-level median F0 as secondary height reference
  - Accent fires when louder AND (higher OR longer) — catches "flew"-type accents
  - Strong rise/fall: requires both large magnitude AND high velocity
  - All syllable labels are IPA (no orthographic fallback)
"""
    (out_base / "README.txt").write_text(text, encoding="utf-8")
    print(f"\n  README: {out_base / 'README.txt'}", flush=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\nSpeechPrint questionnaire builder v3 — {QDATE}", flush=True)
    print(f"Output: {OUT_BASE}\n", flush=True)

    OUT_BASE.mkdir(parents=True, exist_ok=True)

    # English
    try:
        build_english(OUT_BASE / "english")
    except Exception as e:
        print(f"  ERROR (English): {e}", flush=True)
        import traceback; traceback.print_exc()

    # German GToBI sentences
    gde_dir = OUT_BASE / "german_gtobi"
    for name in GERMAN_SENTENCES:
        try:
            build_german_sentence(name, gde_dir)
        except Exception as e:
            print(f"  ERROR ({name}): {e}", flush=True)
            import traceback; traceback.print_exc()

    # Doreco
    try:
        build_doreco(OUT_BASE / "doreco")
    except Exception as e:
        print(f"  ERROR (Doreco): {e}", flush=True)
        import traceback; traceback.print_exc()

    write_readme(OUT_BASE)

    print(f"\n{'='*50}", flush=True)
    print(f"Done. Files in: {OUT_BASE}", flush=True)
    for f in sorted(OUT_BASE.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(OUT_BASE)}", flush=True)


if __name__ == "__main__":
    main()
