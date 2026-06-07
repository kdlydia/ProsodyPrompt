#!/usr/bin/env python3
"""Create two final output folders from existing best TextGrids.

FINAL_QUESTIONNAIRE_2026-06-07/   — 6 consistent tiers, best prosody only
  sentence | words | translation | syllables | phones | prosody
  (translation empty for English; sentence auto-derived from words for English)

TRACKER_COMPARISON_2026-06-07/    — all 5 tracker tiers side-by-side
  sentence | words | translation | syllables | phones |
  prosody_crepe | prosody_pyin | prosody_yin | prosody_praat | prosody_pesto

Sources used:
  Daakie  : DORECO_BEST/doreco_best.TextGrid     (CREPE + 5 opt)
  Cabécar : out/cabeca_best.TextGrid              (CREPE + 5 opt, from build_cabeca.py)
            out/cabeca_comparison.TextGrid         (all trackers)
  GToBI   : GTOBI_BEST/<sentence>.TextGrid        (CREPE + 5 opt, gtobi tier dropped)
  English : out/questionaire_2026-06-02/english/audio_*.TextGrid  (pYIN best)

Run build_cabeca.py first if cabeca outputs don't exist yet.
"""

from __future__ import annotations
import re, shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
HERE = Path(__file__).parent

Q_OUT = ROOT / "FINAL_QUESTIONNAIRE_2026-06-07"
C_OUT = ROOT / "TRACKER_COMPARISON_2026-06-07"


# ── TextGrid I/O ──────────────────────────────────────────────────────────────
def parse_tg(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    xmax = float(re.search(r"xmax = ([\d.]+)", text, re.M).group(1))
    tiers = []
    for block in re.split(r"\n\s*item \[\d+\]:", text)[1:]:
        nm = re.search(r'name = "([^"]*)"', block)
        if not nm: continue
        ivs = []
        for iv in re.split(r"\n\s*intervals \[\d+\]:", block)[1:]:
            a = re.search(r"xmin = ([\d.]+)", iv)
            b = re.search(r"xmax = ([\d.]+)", iv)
            c = re.search(r'text = "([^"]*)"', iv, re.DOTALL)
            if a and b and c:
                ivs.append({"start": float(a.group(1)),
                             "end":   float(b.group(1)),
                             "text":  c.group(1)})
        tiers.append({"name": nm.group(1), "intervals": ivs})
    return {"xmax": xmax, "tiers": tiers}

def get_tier(tg: dict, *names: str) -> list | None:
    """Return first tier that matches any of the given names."""
    for name in names:
        for t in tg["tiers"]:
            if t["name"] == name:
                return t["intervals"]
    return None

def fill(rows: list, xmax: float) -> list:
    out, cur = [], 0.0
    for r in sorted(rows, key=lambda x: x["start"]):
        s, e = float(r["start"]), float(r["end"])
        if s > cur + 5e-4:
            out.append({"start": cur, "end": s, "value": ""})
        out.append({"start": s, "end": e, "value": r.get("value", "")})
        cur = max(cur, e)
    if cur < xmax - 5e-4:
        out.append({"start": cur, "end": xmax, "value": ""})
    return out

def write_tg(path: Path, xmax: float, tiers: list) -> None:
    def q(t): return str(t).replace('"', "'")
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {xmax}", "tiers? <exists>",
             f"size = {len(tiers)}", "item []:"]
    for ti, tier in enumerate(tiers, 1):
        rows = fill(tier["rows"], xmax)
        lines += [f"    item [{ti}]:", '        class = "IntervalTier"',
                  f'        name = "{q(tier["name"])}"',
                  "        xmin = 0", f"        xmax = {xmax}",
                  f"        intervals: size = {len(rows)}"]
        for ii, r in enumerate(rows, 1):
            lines += [f"        intervals [{ii}]:",
                      f"            xmin = {r['start']}",
                      f"            xmax = {r['end']}",
                      f'            text = "{q(r["value"])}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  → {path.name}", flush=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def rows_from_tier(tier_ivs: list | None, *, value_key="text") -> list:
    if tier_ivs is None: return []
    return [{"start": iv["start"], "end": iv["end"], "value": iv[value_key]}
            for iv in tier_ivs]

def empty_tier(xmax: float) -> list:
    """Single empty interval covering the full file."""
    return [{"start": 0.0, "end": xmax, "value": ""}]

def sentences_from_words(word_ivs: list, xmax: float,
                          gap_threshold: float = 0.35) -> list:
    """Group words into sentence intervals using silence gaps."""
    words = [iv for iv in word_ivs if iv["text"] and not iv["text"].startswith("<sil")]
    if not words: return []
    sentences, group = [], [words[0]]
    for w in words[1:]:
        if w["start"] - group[-1]["end"] >= gap_threshold:
            sentences.append(group)
            group = [w]
        else:
            group.append(w)
    if group: sentences.append(group)
    return [{"start": g[0]["start"], "end": g[-1]["end"],
             "value": " ".join(w["text"] for w in g)}
            for g in sentences]


# ── corpus processors ─────────────────────────────────────────────────────────
def process_daakie(q_dir: Path, c_dir: Path):
    print("\nDaakie…", flush=True)
    best_tg_path = ROOT / "DORECO_BEST" / "doreco_best.TextGrid"
    cmp_tg_path  = HERE / "out" / "FINAL_doreco_speechprint_pyin.TextGrid"
    wav_src      = HERE / "doreco_port1286_2017_06_30_Jaklin.wav"

    # ── questionnaire ─────────────────────────────────────────────────────────
    tg   = parse_tg(best_tg_path)
    xmax = tg["xmax"]
    tiers_q = [
        {"name": "sentence",    "rows": rows_from_tier(get_tier(tg, "sentence"))},
        {"name": "words",       "rows": rows_from_tier(get_tier(tg, "words"))},
        {"name": "translation", "rows": rows_from_tier(get_tier(tg, "translation"))},
        {"name": "syllables",   "rows": rows_from_tier(get_tier(tg, "syllables"))},
        {"name": "phones",      "rows": rows_from_tier(get_tier(tg, "phones"))},
        {"name": "prosody",     "rows": rows_from_tier(get_tier(tg, "prosody"))},
    ]
    out = q_dir / "daakie"; out.mkdir(parents=True, exist_ok=True)
    write_tg(out / "daakie.TextGrid", xmax, tiers_q)
    shutil.copy(wav_src, out / wav_src.name)

    # ── comparison ────────────────────────────────────────────────────────────
    if cmp_tg_path.exists():
        tg2   = parse_tg(cmp_tg_path)
        xmax2 = tg2["xmax"]
        base = [
            {"name": "sentence",    "rows": rows_from_tier(get_tier(tg2, "sentence"))},
            {"name": "words",       "rows": rows_from_tier(get_tier(tg2, "words"))},
            {"name": "translation", "rows": rows_from_tier(get_tier(tg2, "translation"))},
            {"name": "syllables",   "rows": rows_from_tier(get_tier(tg2, "syllables"))},
            {"name": "phones",      "rows": rows_from_tier(get_tier(tg2, "phones"))},
        ]
        tracker_tiers = []
        for name in ("prosody_crepe","prosody_pyin","prosody_yin","prosody_praat"):
            ivs = get_tier(tg2, name)
            if ivs: tracker_tiers.append({"name": name, "rows": rows_from_tier(ivs)})
        # add PESTO placeholder if missing
        if not any(t["name"] == "prosody_pesto" for t in tracker_tiers):
            tracker_tiers.append({"name": "prosody_pesto", "rows": empty_tier(xmax2)})
        out2 = c_dir / "daakie"; out2.mkdir(parents=True, exist_ok=True)
        write_tg(out2 / "daakie_comparison.TextGrid", xmax2, base + tracker_tiers)
        shutil.copy(wav_src, out2 / wav_src.name)
    else:
        print(f"  (comparison TG not found — run build_doreco_speechprint.py first)", flush=True)


def process_cabeca(q_dir: Path, c_dir: Path):
    print("\nCabécar…", flush=True)
    best_tg_path = HERE / "out" / "cabeca_best.TextGrid"
    cmp_tg_path  = HERE / "out" / "cabeca_comparison.TextGrid"
    wav_src      = HERE / "doreco_cabeca.wav"

    if not best_tg_path.exists():
        print("  (cabeca_best.TextGrid not found — run build_cabeca.py first)", flush=True)
        return

    # ── questionnaire ─────────────────────────────────────────────────────────
    tg   = parse_tg(best_tg_path)
    xmax = tg["xmax"]
    tiers_q = [
        {"name": "sentence",    "rows": rows_from_tier(get_tier(tg, "sentence"))},
        {"name": "words",       "rows": rows_from_tier(get_tier(tg, "words"))},
        {"name": "translation", "rows": rows_from_tier(get_tier(tg, "translation"))},
        {"name": "syllables",   "rows": rows_from_tier(get_tier(tg, "syllables"))},
        {"name": "phones",      "rows": rows_from_tier(get_tier(tg, "phones"))},
        {"name": "prosody",     "rows": rows_from_tier(get_tier(tg, "prosody"))},
    ]
    out = q_dir / "cabeca"; out.mkdir(parents=True, exist_ok=True)
    write_tg(out / "cabeca.TextGrid", xmax, tiers_q)
    shutil.copy(wav_src, out / wav_src.name)

    # ── comparison ────────────────────────────────────────────────────────────
    if cmp_tg_path.exists():
        tg2   = parse_tg(cmp_tg_path)
        xmax2 = tg2["xmax"]
        base = [
            {"name": "sentence",    "rows": rows_from_tier(get_tier(tg2, "sentence"))},
            {"name": "words",       "rows": rows_from_tier(get_tier(tg2, "words"))},
            {"name": "translation", "rows": rows_from_tier(get_tier(tg2, "translation"))},
            {"name": "syllables",   "rows": rows_from_tier(get_tier(tg2, "syllables"))},
            {"name": "phones",      "rows": rows_from_tier(get_tier(tg2, "phones"))},
        ]
        tracker_tiers = [
            {"name": n, "rows": rows_from_tier(get_tier(tg2, n))}
            for n in ("prosody_crepe","prosody_pyin","prosody_yin",
                      "prosody_praat","prosody_pesto")
            if get_tier(tg2, n)
        ]
        out2 = c_dir / "cabeca"; out2.mkdir(parents=True, exist_ok=True)
        write_tg(out2 / "cabeca_comparison.TextGrid", xmax2, base + tracker_tiers)
        shutil.copy(wav_src, out2 / wav_src.name)


def process_gtobi(q_dir: Path, c_dir: Path):
    print("\nGerman GToBI…", flush=True)
    sentences = [
        "eine_gelbe_banane",
        "einige_melonen",
        "er_sang_die_lieder",
        "er_will_die_rosen_haben",
        "ich_wohne_in_bern",
    ]
    wav_src_dir = ROOT / "ideasss" / "SpeechPrint_results" / "german_gtobi"
    best_dir    = ROOT / "GTOBI_BEST"

    for s in sentences:
        best_path = best_dir / f"{s}.TextGrid"
        wav_src   = wav_src_dir / f"{s}.wav"
        if not best_path.exists():
            print(f"  (missing: {best_path.name})", flush=True); continue

        tg   = parse_tg(best_path)
        xmax = tg["xmax"]

        # ── questionnaire — drop gtobi tier ───────────────────────────────────
        tiers_q = [
            {"name": "sentence",    "rows": rows_from_tier(get_tier(tg, "sentence"))},
            {"name": "words",       "rows": rows_from_tier(get_tier(tg, "words"))},
            {"name": "translation", "rows": rows_from_tier(get_tier(tg, "translation"))},
            {"name": "syllables",   "rows": rows_from_tier(get_tier(tg, "syllables"))},
            {"name": "phones",      "rows": rows_from_tier(get_tier(tg, "phones"))},
            {"name": "prosody",     "rows": rows_from_tier(get_tier(tg, "prosody"))},
        ]
        out = q_dir / "german_gtobi"; out.mkdir(parents=True, exist_ok=True)
        write_tg(out / f"{s}.TextGrid", xmax, tiers_q)
        if wav_src.exists(): shutil.copy(wav_src, out / wav_src.name)

        # ── comparison — CREPE only for now; placeholders for others ──────────
        tiers_c = [
            {"name": "sentence",    "rows": rows_from_tier(get_tier(tg, "sentence"))},
            {"name": "words",       "rows": rows_from_tier(get_tier(tg, "words"))},
            {"name": "translation", "rows": rows_from_tier(get_tier(tg, "translation"))},
            {"name": "syllables",   "rows": rows_from_tier(get_tier(tg, "syllables"))},
            {"name": "phones",      "rows": rows_from_tier(get_tier(tg, "phones"))},
            {"name": "prosody_crepe","rows": rows_from_tier(get_tier(tg, "prosody"))},
            {"name": "prosody_pyin", "rows": empty_tier(xmax)},
            {"name": "prosody_yin",  "rows": empty_tier(xmax)},
            {"name": "prosody_praat","rows": empty_tier(xmax)},
            {"name": "prosody_pesto","rows": empty_tier(xmax)},
        ]
        out2 = c_dir / "german_gtobi"; out2.mkdir(parents=True, exist_ok=True)
        write_tg(out2 / f"{s}_comparison.TextGrid", xmax, tiers_c)
        if wav_src.exists(): shutil.copy(wav_src, out2 / wav_src.name)


def process_english(q_dir: Path, c_dir: Path):
    print("\nEnglish…", flush=True)
    # Best existing English: questionaire_2026-06-02 (pYIN + Xu1999)
    best_path = HERE / "out" / "questionaire_2026-06-02" / "english" / \
                "audio_2026-05-30_19-01-35.TextGrid"
    wav_src   = HERE / "audio_2026-05-30_19-01-35.wav"

    if not best_path.exists():
        print("  (English best TG not found)", flush=True); return

    tg   = parse_tg(best_path)
    xmax = tg["xmax"]

    word_ivs  = get_tier(tg, "words")
    syl_ivs   = get_tier(tg, "syllables")
    phone_ivs = get_tier(tg, "phonemes", "phones")
    pros_ivs  = get_tier(tg, "prosody", "prosody_labels")

    # build sentence tier from word groupings (silence gaps ≥ 0.35 s)
    sentence_rows = sentences_from_words(word_ivs or [], xmax)

    # ── questionnaire ─────────────────────────────────────────────────────────
    tiers_q = [
        {"name": "sentence",    "rows": sentence_rows},
        {"name": "words",       "rows": rows_from_tier(word_ivs)},
        {"name": "translation", "rows": empty_tier(xmax)},   # English = no translation
        {"name": "syllables",   "rows": rows_from_tier(syl_ivs)},
        {"name": "phones",      "rows": rows_from_tier(phone_ivs)},
        {"name": "prosody",     "rows": rows_from_tier(pros_ivs)},
    ]
    out = q_dir / "english"; out.mkdir(parents=True, exist_ok=True)
    write_tg(out / "english.TextGrid", xmax, tiers_q)
    if wav_src.exists(): shutil.copy(wav_src, out / "audio_original.wav")

    # ── comparison — pYIN as primary; placeholders for others ────────────────
    tiers_c = [
        {"name": "sentence",     "rows": sentence_rows},
        {"name": "words",        "rows": rows_from_tier(word_ivs)},
        {"name": "translation",  "rows": empty_tier(xmax)},
        {"name": "syllables",    "rows": rows_from_tier(syl_ivs)},
        {"name": "phones",       "rows": rows_from_tier(phone_ivs)},
        {"name": "prosody_crepe","rows": empty_tier(xmax)},
        {"name": "prosody_pyin", "rows": rows_from_tier(pros_ivs)},
        {"name": "prosody_yin",  "rows": empty_tier(xmax)},
        {"name": "prosody_praat","rows": empty_tier(xmax)},
        {"name": "prosody_pesto","rows": empty_tier(xmax)},
    ]
    out2 = c_dir / "english"; out2.mkdir(parents=True, exist_ok=True)
    write_tg(out2 / "english_comparison.TextGrid", xmax, tiers_c)
    if wav_src.exists(): shutil.copy(wav_src, out2 / "audio_original.wav")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nBuilding final folders…", flush=True)
    print(f"  Questionnaire → {Q_OUT}", flush=True)
    print(f"  Comparison    → {C_OUT}", flush=True)

    Q_OUT.mkdir(parents=True, exist_ok=True)
    C_OUT.mkdir(parents=True, exist_ok=True)

    process_daakie(Q_OUT, C_OUT)
    process_cabeca(Q_OUT, C_OUT)
    process_gtobi(Q_OUT, C_OUT)
    process_english(Q_OUT, C_OUT)

    print("\nDone.", flush=True)
    print(f"\nQuestionnaire folder contents:", flush=True)
    for f in sorted(Q_OUT.rglob("*")):
        if f.is_file(): print(f"  {f.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
