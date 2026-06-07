#!/usr/bin/env python3
"""Create a single Praat TextGrid for class presentation containing both
the old (v1) and new (v2) prosody annotation tiers side by side.

Usage:
    python build_class_comparison.py

The output goes to:
    out/class_demo/english_v1_vs_v2.TextGrid   ← open this in Praat
    out/class_demo/audio_2026-05-30_19-01-35.wav  ← copy of the recording

Tiers in the output (top to bottom):
    sentence       — sentence IDs and text (from corrected TextGrid)
    words          — word boundaries from MFA
    phonemes       — IPA phones from MFA
    syllables_v2   — NEW: IPA syllable labels (always IPA, no ortho mix)
    f0_vowel_v2    — NEW: F0 onset|offset Hz + amplitude at vowel nucleus
                         with Xu (1999) spike trimming
    prosody_v2     — NEW: / \\ – _ * symbols + duration accent cue
    syllables_v1   — OLD: syllable labels (may mix IPA and orthographic)
    f0_vowel_v1    — OLD: F0 onset|mid|offset Hz + amplitude
    prosody_v1     — OLD: / \\ – _ * symbols (no duration cue)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).parent
WAV  = BASE / "audio_2026-05-30_19-01-35.wav"

# Old (v1) results — the corrected TextGrid that was shown in the thesis
OLD_TG = BASE / "out/appendix/minimal_pairs_prosody_corrected.TextGrid"

# MFA JSON — input to the new pipeline
MFA_JSON = BASE / "out/english_eval/mfa/audio_2026-05-30_19-01-35_mfa.json"

OUT_DIR = BASE / "out/class_demo"
OUT_TG  = OUT_DIR / "english_v1_vs_v2.TextGrid"


# ---------------------------------------------------------------------------
# TextGrid I/O
# ---------------------------------------------------------------------------

def _esc(t) -> str:
    return str(t).replace('"', "'")


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
    print(f"  Written: {path}")


def parse_textgrid(path: Path) -> tuple[float, dict[str, list]]:
    """Parse a TextGrid and return (xmax, {tier_name: [{start,end,value}]})."""
    text = path.read_text(encoding="utf-8")
    xmax_m = re.search(r"xmax\s*=\s*([\d.]+)\s*\ntiers", text)
    xmax = float(xmax_m.group(1)) if xmax_m else 0.0

    tiers: dict[str, list] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"\s*item\s*\[\d+\]\s*:", lines[i]):
            name = None
            intervals: list = []
            i += 1
            while i < len(lines):
                l = lines[i].strip()
                if re.match(r"item\s*\[", l):
                    break
                m = re.match(r'name\s*=\s*"(.*)"', l)
                if m:
                    name = m.group(1)
                if re.match(r"intervals\s*\[", l):
                    iv: dict = {}
                    i += 1
                    while i < len(lines):
                        lv = lines[i].strip()
                        xm = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", lv)
                        xM = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", lv)
                        tx = re.match(r'text\s*=\s*"(.*)"', lv)
                        if xm: iv["start"] = float(xm.group(1))
                        if xM: iv["end"] = float(xM.group(1))
                        if tx: iv["value"] = tx.group(1)
                        if re.match(r"(intervals|item)\s*\[", lv):
                            break
                        i += 1
                    intervals.append({"start": iv.get("start", 0.0),
                                      "end": iv.get("end", 0.0),
                                      "value": iv.get("value", "")})
                    continue
                i += 1
            if name:
                tiers[name] = [r for r in intervals if r["value"]]
            continue
        i += 1
    return xmax, tiers


# ---------------------------------------------------------------------------
# New pipeline (v2) — calls build_final_textgrid.build()
# ---------------------------------------------------------------------------

def run_new_pipeline(json_path: Path, wav_path: Path) -> dict[str, list]:
    """Run the v2 pipeline and return {tier_name: [{start,end,value}]} tiers."""
    import tempfile
    tmp = Path(tempfile.mktemp(suffix=".TextGrid"))
    try:
        # Import the updated build_final_textgrid module
        sys.path.insert(0, str(BASE))
        import build_final_textgrid as bft
        bft.build(
            json_path=json_path,
            wav_path=wav_path,
            output_path=tmp,
            backend_label="mfa",
            has_mfa_phones=True,
        )
        _, tiers = parse_textgrid(tmp)
        return tiers
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not OLD_TG.exists():
        print(f"ERROR: old TextGrid not found at {OLD_TG}", file=sys.stderr)
        print("  Run build_minimal_pairs_textgrid.py first.", file=sys.stderr)
        return 1
    if not MFA_JSON.exists():
        print(f"ERROR: MFA JSON not found at {MFA_JSON}", file=sys.stderr)
        print("  Run evaluate_aligners.py first.", file=sys.stderr)
        return 1
    if not WAV.exists():
        print(f"WARNING: WAV not found at {WAV}", file=sys.stderr)

    print("Parsing old (v1) TextGrid …")
    xmax, old_tiers = parse_textgrid(OLD_TG)
    print(f"  Tiers: {list(old_tiers.keys())}  xmax={xmax:.2f}s")

    print("Running new (v2) pipeline …")
    new_tiers = run_new_pipeline(MFA_JSON, WAV)
    print(f"  Tiers: {list(new_tiers.keys())}")
    if new_tiers:
        v2_xmax = max(
            (r["end"] for rows in new_tiers.values() for r in rows),
            default=xmax,
        )
        xmax = max(xmax, v2_xmax)

    # Build merged tier list
    tiers = []
    for name in ("sentence", "words"):
        rows = old_tiers.get(name, [])
        if rows:
            tiers.append({"name": name, "rows": rows})

    # Phonemes from new pipeline (MFA phone-level, IPA)
    for name in ("phonemes",):
        rows = new_tiers.get(name, [])
        if rows:
            tiers.append({"name": name, "rows": rows})

    # New tiers
    for v2_name, tier_name in (
        ("syllables", "syllables_v2"),
        ("f0_vowel",  "f0_vowel_v2"),
        ("prosody",   "prosody_v2"),
    ):
        rows = new_tiers.get(v2_name, [])
        tiers.append({"name": tier_name, "rows": rows})

    # Old tiers
    for v1_name, tier_name in (
        ("syllables", "syllables_v1"),
        ("f0_vowel",  "f0_vowel_v1"),
        ("prosody",   "prosody_v1"),
    ):
        rows = old_tiers.get(v1_name, [])
        tiers.append({"name": tier_name, "rows": rows})

    print(f"Writing comparison TextGrid ({len(tiers)} tiers) …")
    write_textgrid(OUT_TG, xmax, tiers)

    # Copy WAV
    if WAV.exists():
        dst = OUT_DIR / WAV.name
        shutil.copy2(WAV, dst)
        print(f"  Copied WAV: {dst}")

    print(f"\nDone. Open in Praat:")
    print(f"  TextGrid: {OUT_TG}")
    print(f"  WAV:      {OUT_DIR / WAV.name if WAV.exists() else '(not found)'}")
    print(f"\nTier guide:")
    print(f"  sentence    — sentence labels (IDs from minimal-pairs corpus)")
    print(f"  words       — word boundaries (MFA forced alignment)")
    print(f"  phonemes    — IPA phones (MFA phone-level)")
    print(f"  syllables_v2 — NEW: IPA syllable nuclei, no orthographic mix")
    print(f"  f0_vowel_v2  — NEW: F0 onset|offset Hz + dB  (Xu 1999 trimmed)")
    print(f"  prosody_v2   — NEW: / \\ – _ * with duration accent cue")
    print(f"  syllables_v1 — OLD: syllable labels (may contain English ortho)")
    print(f"  f0_vowel_v1  — OLD: F0 onset|mid|offset Hz + dB (no trimming)")
    print(f"  prosody_v1   — OLD: / \\ – _ * (no duration cue)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
