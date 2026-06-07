#!/usr/bin/env python3
"""Create questionnaire TextGrid variants for each GToBI German sentence and English.

For each German sentence, produces three versions:
  v_full   — Wort(human) + Ton(GToBI) + words_whisper + syllables_SP + phonemes_SP + prosody_SP
  v_human  — Wort(human) + Ton(GToBI) + syllables from human words + phonemes_HW + f0_HW + prosody_HW
  v_both   — Wort(human) + Ton(GToBI) + words_whisper + syllables_HW + phonemes_HW + f0_HW + prosody_HW

Also produces a similarity report comparing whisper vs human transcription per sentence.

Output: out/questionnaire/
  german_gtobi/
    <sentence>_v_full.TextGrid     (comparison view)
    <sentence>_v_human.TextGrid    (human-anchored prosody — cleanest)
    <sentence>_v_both.TextGrid     (both word tiers + human-anchored prosody)
    SIMILARITY_REPORT.txt
  english/
    audio_2026-05-30_19-01-35.TextGrid  (already good — just copy)
    audio_2026-05-30_19-01-35.wav
"""

from __future__ import annotations
import math, re, statistics, sys
from pathlib import Path

VENV_PYTHON = Path("/home/lydia/School/UPF/testSpeechPrint/SpeechPrint-main/new/linux/.venv/bin/python")

# ── Re-use speechprint_pkg if available ─────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from speechprint_pkg.cli import (
        phonemize_words, syllables_for_word, acoustic_features,
        label_prosody, ESPEAK_LANG,
    )
    SP_AVAILABLE = True
except Exception as e:
    SP_AVAILABLE = False
    print(f"  [warn] speechprint_pkg not importable: {e}")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
GTOBI_DIR  = BASE / " five GToBI annotated sentences"
SP_DIR     = BASE / "out/german_gtobi"
ENGLISH_V2 = BASE / "out/english_v2/audio_2026-05-30_19-01-35"
OUT_BASE   = BASE / "out/questionnaire"

SENTENCES = [
    "eine_gelbe_banane",
    "einige_melonen",
    "er_sang_die_lieder",
    "er_will_die_rosen_haben",
    "ich_wohne_in_bern",
]


# ============================================================================
# TextGrid parser (handles IntervalTier + TextTier)
# ============================================================================

def parse_textgrid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def _find(pat, start=0):
        for i in range(start, len(lines)):
            m = re.match(pat, lines[i].strip())
            if m: return i, m
        return -1, None

    _, m = _find(r"xmin\s*=\s*([\d.eE+\-]+)"); xmin = float(m.group(1)) if m else 0.0
    _, m = _find(r"xmax\s*=\s*([\d.eE+\-]+)"); xmax = float(m.group(1)) if m else 0.0

    tiers, i = [], 0
    while i < len(lines):
        m = re.match(r"\s*item\s*\[(\d+)\]\s*:", lines[i])
        if not m: i += 1; continue
        tier = {}; i += 1
        while i < len(lines):
            l = lines[i].strip()
            if re.match(r"item\s*\[", l): break
            for pat, key in [(r'class\s*=\s*"(.+)"', "class"),
                             (r'name\s*=\s*"(.*)"',  "name")]:
                mm = re.match(pat, l)
                if mm: tier[key] = mm.group(1)
            if re.match(r"intervals:\s*size\s*=\s*(\d+)", l):
                n = int(re.match(r"intervals:\s*size\s*=\s*(\d+)", l).group(1))
                ivs = []; i += 1
                while i < len(lines) and len(ivs) < n:
                    lx = lines[i].strip()
                    if re.match(r"intervals\s*\[", lx):
                        iv = {}; i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(intervals|points|item)\s*\[", lv): break
                            for rx, fld in [(r"xmin\s*=\s*([\d.eE+\-]+)", "xmin"),
                                           (r"xmax\s*=\s*([\d.eE+\-]+)", "xmax"),
                                           (r'text\s*=\s*"(.*)"',         "text")]:
                                mm2 = re.match(rx, lv)
                                if mm2: iv[fld] = (float(mm2.group(1)) if fld != "text" else mm2.group(1))
                            i += 1
                        ivs.append(iv)
                    else: i += 1
                tier["intervals"] = ivs; continue
            if re.match(r"points:\s*size\s*=\s*(\d+)", l):
                n = int(re.match(r"points:\s*size\s*=\s*(\d+)", l).group(1))
                pts = []; i += 1
                while i < len(lines) and len(pts) < n:
                    lx = lines[i].strip()
                    if re.match(r"points\s*\[", lx):
                        pt = {}; i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(points|item)\s*\[", lv): break
                            mm2 = re.match(r"number\s*=\s*([\d.eE+\-]+)", lv)
                            mk  = re.match(r'mark\s*=\s*"(.*)"', lv)
                            if mm2: pt["number"] = float(mm2.group(1))
                            elif mk: pt["mark"] = mk.group(1)
                            i += 1
                        pts.append(pt)
                    else: i += 1
                tier["points"] = pts; continue
            i += 1
        if "name" in tier: tiers.append(tier)
    return {"xmin": xmin, "xmax": xmax, "tiers": tiers}


def _esc(t) -> str:
    return str(t).replace('"', "'")


def write_textgrid(path: Path, xmax: float, tiers: list) -> None:
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {xmax}", "tiers? <exists>",
             f"size = {len(tiers)}", "item []:"]
    for ti, tier in enumerate(tiers, 1):
        tc = tier.get("class", "IntervalTier")
        lines += [f"    item [{ti}]:", f'        class = "{tc}"',
                  f'        name = "{_esc(tier["name"])}"',
                  f"        xmin = 0", f"        xmax = {xmax}"]
        if tc == "TextTier":
            pts = tier.get("points", [])
            lines.append(f"        points: size = {len(pts)}")
            for ii, pt in enumerate(pts, 1):
                lines += [f"        points [{ii}]:",
                          f"            number = {pt.get('number', 0.0)}",
                          f'            mark = "{_esc(pt.get("mark", ""))}"']
        else:
            ivs = tier.get("intervals", [])
            lines.append(f"        intervals: size = {len(ivs)}")
            for ii, iv in enumerate(ivs, 1):
                lines += [f"        intervals [{ii}]:",
                          f"            xmin = {iv.get('xmin', 0.0)}",
                          f"            xmax = {iv.get('xmax', xmax)}",
                          f'            text = "{_esc(iv.get("text", ""))}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fill_gaps(rows: list[dict], xmax: float) -> list[dict]:
    out, cursor = [], 0.0
    for r in sorted(rows, key=lambda x: x.get("xmin", 0)):
        s, e = float(r.get("xmin", 0)), float(r.get("xmax", 0))
        if s > cursor + 5e-4:
            out.append({"xmin": cursor, "xmax": s, "text": ""})
        out.append(r); cursor = max(cursor, e)
    if cursor < xmax - 5e-4:
        out.append({"xmin": cursor, "xmax": xmax, "text": ""})
    return out


# ============================================================================
# Similarity comparison: whisper words vs human words
# ============================================================================

def word_similarity(human_words: list[str], sp_words: list[str]) -> dict:
    """Very simple similarity: longest common subsequence / max length."""
    h = [w.lower().strip() for w in human_words if w.strip()]
    s = [w.lower().strip() for w in sp_words if w.strip()]
    if not h or not s:
        return {"human": h, "sp": s, "lcs": 0, "pct": 0.0, "verdict": "no data"}

    # LCS length
    m, n = len(h), len(s)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if h[i-1] == s[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    lcs = dp[m][n]
    pct = lcs / max(m, n) * 100

    # Also count fuzzy matches (first 3 chars agree)
    fuzzy = sum(1 for hw in h if any(sw[:3] == hw[:3] and len(hw) >= 3 for sw in s))
    fuzzy_pct = fuzzy / max(m, n) * 100

    verdict = ("VERY SIMILAR" if pct >= 70
               else "SOMEWHAT SIMILAR" if pct >= 40 or fuzzy_pct >= 50
               else "DIFFERENT")
    return {"human": h, "sp": s, "lcs": lcs, "pct": round(pct, 1),
            "fuzzy_pct": round(fuzzy_pct, 1), "verdict": verdict}


# ============================================================================
# Re-run prosody analysis using human word intervals
# ============================================================================

def human_word_intervals(wort_tier: dict) -> list[dict]:
    """Extract non-empty word intervals from the Wort tier."""
    out = []
    for iv in wort_tier.get("intervals", []):
        txt = iv.get("text", "").strip()
        if txt:
            out.append({"start": iv["xmin"], "end": iv["xmax"],
                        "word": txt.lower()})
    return out


def run_prosody_on_words(wav: Path, word_intervals: list[dict],
                         language: str = "de") -> tuple[list, list, list]:
    """Run steps 6-7 of the SP pipeline on given word intervals.
    Returns (syllables, phonemes, []) — syllables have prosody labels attached.
    """
    if not SP_AVAILABLE:
        return [], [], []

    word_strings = [w["word"] for w in word_intervals]
    phones_by_word, _ = phonemize_words(word_strings, language)

    syllables, phonemes = [], []
    syll_idx = phone_idx = 0
    for wi, (w_info, phones) in enumerate(zip(word_intervals, phones_by_word)):
        sylls_for_word, syll_phone_lists = syllables_for_word(
            w_info["word"], phones, w_info["start"], w_info["end"])
        for syl, syl_phones in zip(sylls_for_word, syll_phone_lists):
            syll_idx += 1
            syl_record = {
                "index": syll_idx, "label": syl["label"],
                "word_index": wi + 1,
                "start": syl["start"], "end": syl["end"],
                "mid": (syl["start"] + syl["end"]) / 2,
                "duration_s": syl["end"] - syl["start"],
                "phones": " ".join(syl_phones),
            }
            syllables.append(syl_record)
            if syl_phones:
                syl_dur = syl["end"] - syl["start"]
                per_phone = syl_dur / len(syl_phones)
                for j, ph in enumerate(syl_phones):
                    phone_idx += 1
                    ps = syl["start"] + per_phone * j
                    pe = syl["start"] + per_phone * (j + 1)
                    if j == len(syl_phones) - 1: pe = syl["end"]
                    phonemes.append({
                        "index": phone_idx, "label": ph,
                        "syllable_index": syll_idx, "word_index": wi + 1,
                        "start": ps, "end": pe, "mid": (ps + pe) / 2,
                        "duration_s": pe - ps,
                    })

    acoustic_features(wav, syllables)
    acoustic_features(wav, phonemes)
    label_prosody(syllables)
    return syllables, phonemes, []


# ============================================================================
# Tier builders
# ============================================================================

def tier_from_intervals(name: str, rows: list[dict],
                        text_key: str = "text", xmax: float = None) -> dict:
    ivs = [{"xmin": r.get("xmin", r.get("start", 0)),
             "xmax": r.get("xmax", r.get("end", 0)),
             "text": r.get(text_key, "")} for r in rows]
    if xmax is not None:
        ivs = fill_gaps(ivs, xmax)
    return {"class": "IntervalTier", "name": name, "intervals": ivs}


def syllable_tier(name: str, syllables: list[dict], xmax: float) -> dict:
    rows = [{"xmin": s["start"], "xmax": s["end"], "text": s["label"]}
            for s in syllables]
    return {"class": "IntervalTier", "name": name,
            "intervals": fill_gaps(rows, xmax)}


def phoneme_tier(name: str, phonemes: list[dict], xmax: float) -> dict:
    rows = [{"xmin": p["start"], "xmax": p["end"], "text": p["label"]}
            for p in phonemes]
    return {"class": "IntervalTier", "name": name,
            "intervals": fill_gaps(rows, xmax)}


def f0_tier(name: str, syllables: list[dict], xmax: float) -> dict:
    rows = []
    for s in syllables:
        f0 = s.get("mean_f0_hz")
        rows.append({"xmin": s["start"], "xmax": s["end"],
                     "text": f"{int(round(f0))}" if f0 else ""})
    return {"class": "IntervalTier", "name": name,
            "intervals": fill_gaps(rows, xmax)}


def prosody_tier(name: str, syllables: list[dict], xmax: float) -> dict:
    rows = [{"xmin": s["start"], "xmax": s["end"],
             "text": s.get("symbol_marked", "")} for s in syllables]
    return {"class": "IntervalTier", "name": name,
            "intervals": fill_gaps(rows, xmax)}


# ============================================================================
# Main build
# ============================================================================

def build_german(name: str, report_lines: list[str]) -> None:
    print(f"\n── {name}")

    wav_path   = BASE / " five GToBI annotated sentences" / f"{name}.wav"
    gtobi_path = BASE / " five GToBI annotated sentences" / f"{name}.TextGrid"
    sp_path    = SP_DIR / name / f"{name}.TextGrid"
    out_dir    = OUT_BASE / "german_gtobi"
    out_dir.mkdir(parents=True, exist_ok=True)

    gtobi = parse_textgrid(gtobi_path)
    sp    = parse_textgrid(sp_path)

    xmax = gtobi["xmax"]
    gtobi_by  = {t["name"]: t for t in gtobi["tiers"]}
    sp_by     = {t["name"]: t for t in sp["tiers"]}

    wort_tier = gtobi_by.get("Wort")
    ton_tier  = gtobi_by.get("Ton")

    # ── Similarity report ────────────────────────────────────────────────────
    human_words = [iv["text"] for iv in (wort_tier or {}).get("intervals", [])
                   if iv.get("text", "").strip()]
    sp_words_iv = [iv for iv in sp_by.get("words", {}).get("intervals", [])
                   if iv.get("text", "").strip()]
    sp_words    = [iv["text"] for iv in sp_words_iv]

    sim = word_similarity(human_words, sp_words)
    report_lines.append(f"\n{name}")
    report_lines.append(f"  Human words : {sim['human']}")
    report_lines.append(f"  Whisper words: {sim['sp']}")
    report_lines.append(f"  LCS match   : {sim['lcs']}/{max(len(sim['human']), len(sim['sp']))} "
                        f"= {sim['pct']}%  (fuzzy {sim['fuzzy_pct']}%)")
    report_lines.append(f"  Verdict     : {sim['verdict']}")

    show_whisper = (sim["verdict"] != "DIFFERENT")
    report_lines.append(f"  → Include whisper words tier in v_full/v_both: {show_whisper}")

    # ── Human-anchored prosody analysis ──────────────────────────────────────
    hw_intervals = human_word_intervals(wort_tier) if wort_tier else []
    hw_syllables, hw_phonemes, _ = run_prosody_on_words(wav_path, hw_intervals)

    # ── Version v_human: Wort + Ton + HW syllables/phonemes/f0/prosody ──────
    tiers_v_human = []
    if wort_tier: tiers_v_human.append({**wort_tier, "name": "Wort"})
    if ton_tier:  tiers_v_human.append({**ton_tier,  "name": "Ton"})
    if hw_syllables:
        tiers_v_human.append(syllable_tier("syllables", hw_syllables, xmax))
        tiers_v_human.append(phoneme_tier( "phonemes",  hw_phonemes,  xmax))
        tiers_v_human.append(f0_tier(      "f0_pitch",  hw_syllables, xmax))
        tiers_v_human.append(prosody_tier( "prosody",   hw_syllables, xmax))
    write_textgrid(out_dir / f"{name}_v_human.TextGrid", xmax, tiers_v_human)
    print(f"  v_human ({len(tiers_v_human)} tiers): "
          f"Wort+Ton+HW-syllables/phonemes/f0/prosody")

    # ── Version v_full: Wort + Ton + SP words/syllables/phonemes/prosody ────
    tiers_v_full = []
    if wort_tier: tiers_v_full.append({**wort_tier, "name": "Wort"})
    if ton_tier:  tiers_v_full.append({**ton_tier,  "name": "Ton"})
    for sp_name, out_name in [("words",          "words_SP"),
                               ("syllables",      "syllables_SP"),
                               ("phonemes",       "phonemes_SP"),
                               ("f0_pitch",       "f0_pitch_SP"),
                               ("prosody_labels", "prosody_SP")]:
        if sp_name in sp_by:
            tiers_v_full.append({**sp_by[sp_name], "name": out_name})
    write_textgrid(out_dir / f"{name}_v_full.TextGrid", xmax, tiers_v_full)
    print(f"  v_full  ({len(tiers_v_full)} tiers): Wort+Ton+SP-tiers")

    # ── Version v_both: Wort + Ton + whisper words + HW prosody ─────────────
    tiers_v_both = []
    if wort_tier: tiers_v_both.append({**wort_tier, "name": "Wort"})
    if ton_tier:  tiers_v_both.append({**ton_tier,  "name": "Ton"})
    if show_whisper and "words" in sp_by:
        tiers_v_both.append({**sp_by["words"], "name": "words_SP"})
    if hw_syllables:
        tiers_v_both.append(syllable_tier("syllables", hw_syllables, xmax))
        tiers_v_both.append(phoneme_tier( "phonemes",  hw_phonemes,  xmax))
        tiers_v_both.append(f0_tier(      "f0_pitch",  hw_syllables, xmax))
        tiers_v_both.append(prosody_tier( "prosody",   hw_syllables, xmax))
    write_textgrid(out_dir / f"{name}_v_both.TextGrid", xmax, tiers_v_both)
    print(f"  v_both  ({len(tiers_v_both)} tiers): Wort+Ton+whisper-words+HW-prosody")

    # Copy WAV
    import shutil
    shutil.copy2(wav_path, out_dir / f"{name}.wav")


def build_english() -> None:
    print("\n── English (no human annotation — SP output only)")
    out_dir = OUT_BASE / "english"
    out_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    src_tg  = ENGLISH_V2 / "audio_2026-05-30_19-01-35.TextGrid"
    src_wav = BASE / "audio_2026-05-30_19-01-35.wav"
    shutil.copy2(src_tg,  out_dir / "audio_2026-05-30_19-01-35.TextGrid")
    shutil.copy2(src_wav, out_dir / "audio_2026-05-30_19-01-35.wav")
    print("  Copied: SpeechPrint v2 TextGrid (6 tiers) + WAV")


def main() -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)

    if not SP_AVAILABLE:
        print("ERROR: speechprint_pkg not importable. Run with the testSpeechPrint venv.")
        print(f"  Use: PYTHONPATH=. {VENV_PYTHON} questionnaire_textgrids.py")
        sys.exit(1)

    report_lines = ["WHISPER vs HUMAN ANNOTATION SIMILARITY REPORT",
                    "=" * 50]

    for name in SENTENCES:
        build_german(name, report_lines)

    build_english()

    report_path = OUT_BASE / "german_gtobi" / "SIMILARITY_REPORT.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"\n✓ Similarity report: {report_path}")

    # Print summary
    report_lines.append("\n\nVERSION GUIDE")
    report_lines.append("-" * 40)
    report_lines.append("v_human : BEST for questionnaire — uses hand-annotated word")
    report_lines.append("          boundaries for ALL analysis (syllables/phonemes/prosody).")
    report_lines.append("          Shows GToBI annotation alongside SpeechPrint prosody.")
    report_lines.append("v_full  : Shows full SpeechPrint output (whisper-based) next to")
    report_lines.append("          the GToBI reference. Good for comparing whisper vs human.")
    report_lines.append("v_both  : Best of both: whisper words visible, but prosody/phonemes")
    report_lines.append("          computed from human word boundaries.")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\nDone. Output:")
    for f in sorted(OUT_BASE.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(OUT_BASE)}")


if __name__ == "__main__":
    main()
