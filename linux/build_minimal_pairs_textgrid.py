#!/usr/bin/env python3
"""
Build corrected minimal-pairs TextGrid from prosody_minimal_pairs.tsv.

The auto-generated syllables.csv has prosody errors (e.g., coffee "fi" marked
rising instead of low, kɔ missing * accent, "to" spuriously rising).
The prosody_minimal_pairs.tsv contains human-verified labels.

Uses syllables.csv for timing (authoritative) and overrides prosody labels
with TSV values where a reliable match is found.

Matching strategy (sentence-by-sentence):
  1. For each TSV sentence group, compute word frequencies from the recording
     and pick the RAREST non-trivial word as the search anchor — this avoids
     latching onto high-frequency words like "yesterday" that appear in TSV
     bug rows duplicated from the preceding sentence.
  2. Locate the anchor in the recording (word list) starting from the current
     position pointer (strictly monotone; no backtracking).
  3. Within the sentence region (starting from anchor), match TSV syllables
     sequentially; TSV rows whose word is inconsistent with the sentence text
     are skipped (catches the [3c→4a] duplication bug).
  4. word_ptr is maintained in 0-based list-position units throughout.

Output: out/appendix/minimal_pairs_prosody_corrected.TextGrid + .wav
Tiers:  sentence | words | syllables | f0_vowel | prosody
"""
from __future__ import annotations
import csv
import math
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

BASE     = Path(__file__).parent
OUT_DIR  = BASE / "out/appendix"
SYLS_CSV = BASE / "out/english_v2/audio_2026-05-30_19-01-35/syllables.csv"
WORDS_CSV= BASE / "out/english_v2/audio_2026-05-30_19-01-35/words.csv"
TSV_PATH = OUT_DIR / "prosody_minimal_pairs.tsv"
OUT_TG   = OUT_DIR / "minimal_pairs_prosody_corrected.TextGrid"

COMMON_WORDS = {
    "i", "a", "the", "to", "for", "is", "was", "it", "an", "in",
    "on", "at", "my", "we", "you", "he", "she", "her", "his",
    "as", "or", "and", "not", "so", "do", "did", "has", "no",
    "too", "but", "who", "are", "where", "when", "how", "what",
}

# Spelled-out number / contraction normalisation so that e.g. "30" (recording)
# matches "thirty" (sentence text) and "he's" matches "hes" after punctuation strip.
WORD_NORMALIZE = {
    "30": "thirty", "he's": "hes", "didn't": "didnt",
    "don't": "dont", "you're": "youre", "that's": "thats",
}


# ── I/O helpers ──────────────────────────────────────────────────────────────

def _esc(t: str) -> str:
    return str(t).replace('"', "'")


def fill_gaps(rows: list[dict], xmax: float) -> list[dict]:
    out, cur = [], 0.0
    for r in sorted(rows, key=lambda x: x["xmin"]):
        s, e = float(r["xmin"]), float(r["xmax"])
        if s > cur + 5e-4:
            out.append({"xmin": cur, "xmax": s, "text": ""})
        out.append(r)
        cur = max(cur, e)
    if cur < xmax - 5e-4:
        out.append({"xmin": cur, "xmax": xmax, "text": ""})
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
        ivs = tier["intervals"]
        lines += [
            f"    item [{ti}]:",
            '        class = "IntervalTier"',
            f'        name = "{_esc(tier["name"])}"',
            "        xmin = 0",
            f"        xmax = {xmax}",
            f"        intervals: size = {len(ivs)}",
        ]
        for ii, iv in enumerate(ivs, 1):
            lines += [
                f"        intervals [{ii}]:",
                f"            xmin = {iv['xmin']}",
                f"            xmax = {iv['xmax']}",
                f'            text = "{_esc(iv.get("text", ""))}"',
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written: {path}")


# ── data loading ─────────────────────────────────────────────────────────────

def load_words(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            w = r["word"].lower().strip()
            rows.append({
                "index":  int(r["index"]),
                "word":   w,
                "wnorm":  WORD_NORMALIZE.get(w, re.sub(r"[^a-z]", "", w)),
                "start":  float(r["start"]),
                "end":    float(r["end"]),
            })
    return rows


def load_syllables(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            def _f(c):
                try: return float(r[c]) if r.get(c) else None
                except: return None
            rows.append({
                "index":    int(r["index"]),
                "label":    r["label"].strip(),
                "word_idx": int(r["word_index"]),
                "start":    float(r["start"]),
                "end":      float(r["end"]),
                "onset_f0": _f("onset_f0_hz"),
                "mean_f0":  _f("mean_f0_hz"),
                "off_f0":   _f("offset_f0_hz"),
                "amp_db":   _f("mean_intensity_db"),
                "symbol":   r.get("symbol_marked", r.get("symbol", "?")).strip(),
            })
    return rows


def load_tsv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sid  = r.get("sentence_id", "").strip()
            sent = r.get("sentence",    "").strip()
            syl  = r.get("syllable",    "").strip()
            word = r.get("word",        "").strip().lower()
            f0v  = r.get("f0_vowel",    "").strip()
            pros = r.get("prosody",     "").strip()
            if not sid:
                continue
            rows.append({"sentence_id": sid, "sentence": sent,
                         "syllable": syl, "word": word,
                         "wnorm": WORD_NORMALIZE.get(word, re.sub(r"[^a-z]", "", word)),
                         "f0_vowel": f0v, "prosody": pros})
    return rows


# ── sentence word set (normalised) ───────────────────────────────────────────

def sentence_word_set(sentence_text: str) -> set[str]:
    """Normalised word tokens from sentence text (strips annotations, punctuation)."""
    text = re.sub(r"\[.*?\]", "", sentence_text)   # remove [contrastive] etc.
    text = re.sub(r"[^a-zA-Z0-9 ]", "", text).lower()  # keep alphanumeric
    tokens = set(text.split())
    # Also add WORD_NORMALIZE mappings in both directions
    extra = set()
    for t in tokens:
        extra.add(WORD_NORMALIZE.get(t, t))
    # e.g. "thirty" → also accept "30"
    for k, v in WORD_NORMALIZE.items():
        if v in tokens:
            extra.add(k)
    return tokens | extra


def is_consistent(wnorm: str, sw: set[str]) -> bool:
    return not wnorm or wnorm in sw


# ── F0 label ─────────────────────────────────────────────────────────────────

def build_f0_label(syl: dict) -> str:
    def hz(v): return f"{int(round(v))}" if v and not math.isnan(v) else "?"
    def db(v): return f"{round(v,1)}dB"   if v and not math.isnan(v) else "?"
    return (f"{hz(syl.get('onset_f0'))}|{hz(syl.get('mean_f0'))}"
            f"|{hz(syl.get('off_f0'))}Hz  {db(syl.get('amp_db'))}")


# ── core matching ─────────────────────────────────────────────────────────────

def match_tsv(tsv_rows: list[dict],
              syllables: list[dict],
              words: list[dict]) -> None:
    """
    Annotate syllables in-place with TSV labels (tsv_sid, tsv_pros, tsv_f0).
    """
    # ── lookups ──────────────────────────────────────────────────────────────
    word_freq: Counter = Counter(w["wnorm"] for w in words)
    word_lpos: dict[int, int] = {w["index"]: i for i, w in enumerate(words)}
    widx_to_lpos: dict[int, int] = word_lpos  # word index (1-based) → list pos (0-based)

    for s in syllables:
        w = words[widx_to_lpos.get(s["word_idx"], 0)]
        s["word_text"]  = w["word"]
        s["word_wnorm"] = w["wnorm"]

    # initialise annotation fields
    for s in syllables:
        s.update({"tsv_sid": "", "tsv_sent": "", "tsv_pros": "", "tsv_f0": ""})

    # ── group TSV by sentence_id ──────────────────────────────────────────────
    groups: OrderedDict[str, dict] = OrderedDict()
    for row in tsv_rows:
        sid = row["sentence_id"]
        if sid not in groups:
            groups[sid] = {"sentence": row["sentence"], "rows": []}
        groups[sid]["rows"].append(row)

    # ── word-pos lookup for syllable positions ────────────────────────────────
    word_to_sylpos: dict[int, list[int]] = defaultdict(list)
    for pos, s in enumerate(syllables):
        word_to_sylpos[s["word_idx"]].append(pos)

    # ── process each sentence ─────────────────────────────────────────────────
    syl_ptr  = 0   # 0-based position in syllables list
    word_ptr = 0   # 0-based position in words list (strictly increasing)

    for sid, grp in groups.items():
        sentence_text = grp["sentence"]
        sw = sentence_word_set(sentence_text)

        # Clean rows: word consistent with sentence text
        clean_rows = [r for r in grp["rows"] if is_consistent(r["wnorm"], sw)]

        if not clean_rows:
            continue

        # Rarest anchor word (non-common, non-short, lowest freq in recording)
        # Use words from the sentence TEXT (not TSV rows, to avoid bug rows)
        sent_non_common = [
            t for t in sentence_word_set(sentence_text)
            if t and t not in COMMON_WORDS and len(t) > 2
        ]
        # Also include from clean_rows in case sentence text parsing differs
        tsv_non_common = [
            r["wnorm"] for r in clean_rows
            if r["wnorm"] and r["wnorm"] not in COMMON_WORDS and len(r["wnorm"]) > 2
        ]
        candidates = sent_non_common + tsv_non_common
        if not candidates:
            candidates = [r["wnorm"] for r in clean_rows if r["wnorm"]]

        anchor = min(candidates, key=lambda w: word_freq.get(w, 999)) if candidates else None
        if anchor is None:
            continue

        # Locate anchor in words list from current word_ptr
        MAX_SCAN = 400
        anchor_lpos = None
        for i in range(word_ptr, min(word_ptr + MAX_SCAN, len(words))):
            if words[i]["wnorm"] == anchor:
                anchor_lpos = i
                break

        if anchor_lpos is None:
            continue

        # Set syl_ptr to first syllable of the word at anchor_lpos
        w_idx = words[anchor_lpos]["index"]
        syl_positions = word_to_sylpos.get(w_idx, [])
        if syl_positions:
            anchor_syl_pos = min(syl_positions)
            # Look slightly before anchor for first word of sentence
            first_wnorm = next((r["wnorm"] for r in clean_rows if r["wnorm"]), None)
            if first_wnorm and first_wnorm != anchor:
                for back in range(max(word_ptr, anchor_lpos - 25), anchor_lpos):
                    if words[back]["wnorm"] == first_wnorm:
                        first_w_idx = words[back]["index"]
                        first_syl_pos = min(word_to_sylpos.get(first_w_idx, [anchor_syl_pos]))
                        # Only use if it doesn't go backwards in time
                        if first_syl_pos >= syl_ptr:
                            anchor_lpos  = back
                            anchor_syl_pos = first_syl_pos
                        break
            syl_ptr  = max(syl_ptr,  anchor_syl_pos)
            word_ptr = max(word_ptr, anchor_lpos)

        # Match clean rows to syllables sequentially from syl_ptr
        LOOKAHEAD = 25
        for row in clean_rows:
            tw = row["wnorm"]
            if not tw:
                continue

            found = None
            for ahead in range(LOOKAHEAD):
                pos = syl_ptr + ahead
                if pos >= len(syllables):
                    break
                if syllables[pos]["word_wnorm"] == tw:
                    found = pos
                    break

            if found is not None:
                s = syllables[found]
                s["tsv_sid"]  = sid
                s["tsv_sent"] = sentence_text
                s["tsv_pros"] = row["prosody"]
                s["tsv_f0"]   = row["f0_vowel"]
                syl_ptr  = found + 1
                # advance word_ptr (convert word_idx 1-based → list pos 0-based)
                wlpos = widx_to_lpos.get(s["word_idx"])
                if wlpos is not None:
                    word_ptr = max(word_ptr, wlpos + 1)


# ── sentence tier ─────────────────────────────────────────────────────────────

def build_sentence_tier(syllables: list[dict], xmax: float) -> list[dict]:
    runs, cur_sid = [], None
    cur_s = cur_e = 0.0
    cur_text = ""
    for s in syllables:
        sid = s["tsv_sid"]
        if sid != cur_sid:
            if cur_sid is not None:
                runs.append((cur_s, cur_e, cur_sid, cur_text))
            cur_sid, cur_text = sid, s["tsv_sent"]
            cur_s = s["start"]
        cur_e = s["end"]
    if cur_sid is not None:
        runs.append((cur_s, cur_e, cur_sid, cur_text))

    ivs = []
    for (s, e, sid, text) in runs:
        label = f"{sid} [{text}]" if sid and text else (sid or "")
        ivs.append({"xmin": s, "xmax": e, "text": label})
    return fill_gaps(ivs, xmax)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading ...")
    words     = load_words(WORDS_CSV)
    syllables = load_syllables(SYLS_CSV)
    tsv_rows  = load_tsv(TSV_PATH)
    print(f"  {len(words)} words  {len(syllables)} syllables  {len(tsv_rows)} TSV rows")

    xmax = syllables[-1]["end"] + 0.05 if syllables else 10.0

    print("Matching TSV sentences → syllables ...")
    match_tsv(tsv_rows, syllables, words)

    n_matched = sum(1 for s in syllables if s["tsv_sid"])
    print(f"  Matched: {n_matched}/{len(syllables)} syllables")

    # ── tiers ──────────────────────────────────────────────────────────────
    sent_ivs = build_sentence_tier(syllables, xmax)

    word_rows = []
    prev = 0.0
    for w in words:
        if w["start"] > prev + 0.04:
            word_rows.append({"xmin": prev, "xmax": w["start"], "text": ""})
        word_rows.append({"xmin": w["start"], "xmax": w["end"], "text": w["word"]})
        prev = w["end"]
    if prev < xmax - 5e-4:
        word_rows.append({"xmin": prev, "xmax": xmax, "text": ""})

    syl_ivs = fill_gaps(
        [{"xmin": s["start"], "xmax": s["end"], "text": s["label"]}
         for s in syllables], xmax)

    f0_ivs = fill_gaps(
        [{"xmin": s["start"], "xmax": s["end"],
          "text": (s["tsv_f0"] if s["tsv_f0"] and s["tsv_f0"] != "?"
                   else build_f0_label(s))}
         for s in syllables], xmax)

    n_tsv = 0
    pros_rows = []
    for s in syllables:
        if s["tsv_pros"]:
            label = s["tsv_pros"]
            n_tsv += 1
        else:
            label = s["symbol"]
        pros_rows.append({"xmin": s["start"], "xmax": s["end"], "text": label})
    pros_ivs = fill_gaps(pros_rows, xmax)
    print(f"  Prosody: {n_tsv} from TSV  {len(syllables)-n_tsv} from auto-label")

    # ── spot checks ────────────────────────────────────────────────────────
    print("\n[1a] First 7 syllables (expect kɔ→*-\\\\ fi→_):")
    for s in syllables[:7]:
        src = "TSV" if s["tsv_pros"] else "auto"
        pros = s["tsv_pros"] or s["symbol"]
        print(f"  [{s['tsv_sid']:4s}] {s['label']:8s} {s['word_text']:10s}  {pros:8s} ({src})")

    print("\n['to' syllables in sentences 2a-2h (expect -):]")
    for s in syllables:
        if s["word_text"] == "to" and 15 < s["start"] < 45:
            src = "TSV" if s["tsv_pros"] else "auto"
            pros = s["tsv_pros"] or s["symbol"]
            print(f"  [{s['tsv_sid']:4s}] {s['label']:8s} t={s['start']:.1f}  {pros:8s} ({src})")

    print("\n[Per-sentence match summary]")
    from collections import Counter as C
    sid_count = C(s["tsv_sid"] for s in syllables if s["tsv_sid"])
    for sid, n in sorted(sid_count.items()):
        print(f"  {sid:5s}: {n} syllables")

    # ── write ──────────────────────────────────────────────────────────────
    tiers = [
        {"name": "sentence",  "intervals": sent_ivs},
        {"name": "words",     "intervals": word_rows},
        {"name": "syllables", "intervals": syl_ivs},
        {"name": "f0_vowel",  "intervals": f0_ivs},
        {"name": "prosody",   "intervals": pros_ivs},
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_textgrid(OUT_TG, xmax, tiers)

    import shutil
    for src in [
        BASE / "audio_2026-05-30_19-01-35.wav",
        BASE / "out/english_v2/audio_2026-05-30_19-01-35/audio_2026-05-30_19-01-35.wav",
    ]:
        if src.exists():
            dst = OUT_DIR / "minimal_pairs_prosody_corrected.wav"
            shutil.copy2(src, dst)
            print(f"  Copied WAV: {dst}")
            break

    print("\nDone.")


if __name__ == "__main__":
    main()
