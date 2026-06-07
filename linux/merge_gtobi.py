#!/usr/bin/env python3
"""Merge original GToBI TextGrid (Wort + Ton tiers) with SpeechPrint output.

Output tier order (for Praat readability):
  1. Wort          — original word boundaries (IntervalTier from GToBI)
  2. Ton           — GToBI tone annotations    (TextTier/PointTier from GToBI)
  3. sp_words      — SpeechPrint WhisperX words
  4. sp_syllables  — SpeechPrint syllables with IPA-derived labels
  5. sp_phonemes   — SpeechPrint IPA phones
  6. sp_f0_pitch   — SpeechPrint mean F0 per syllable (Hz)
  7. sp_prosody    — SpeechPrint prosody symbols (/ // \\ \\\\ -- *)

Usage:
    python merge_gtobi.py --gtobi <gtobi.TextGrid> --sp <sp_output.TextGrid> \
                          --output <merged.TextGrid>

Or batch mode (no args): processes all five GToBI sentences automatically.
"""

import argparse
import re
import sys
from pathlib import Path


# ============================================================================
# TextGrid parser — handles both IntervalTier and TextTier
# ============================================================================

def parse_textgrid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def _find(pattern, start=0):
        for i in range(start, len(lines)):
            m = re.match(pattern, lines[i].strip())
            if m:
                return i, m
        return -1, None

    _, m = _find(r"xmin\s*=\s*([\d.eE+\-]+)")
    xmin = float(m.group(1)) if m else 0.0
    _, m = _find(r"xmax\s*=\s*([\d.eE+\-]+)")
    xmax = float(m.group(1)) if m else 0.0

    tiers = []
    i = 0
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

            cm = re.match(r'class\s*=\s*"(.+)"', l)
            nm = re.match(r'name\s*=\s*"(.*)"', l)
            xi = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", l)
            xa = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", l)

            if cm:
                tier["class"] = cm.group(1)
            elif nm:
                tier["name"] = nm.group(1)
            elif xi and "xmin" not in tier:
                tier["xmin"] = float(xi.group(1))
            elif xa and "xmax" not in tier:
                tier["xmax"] = float(xa.group(1))

            # IntervalTier
            im = re.match(r"intervals:\s*size\s*=\s*(\d+)", l)
            if im:
                n = int(im.group(1))
                intervals = []
                i += 1
                while i < len(lines) and len(intervals) < n:
                    lx = lines[i].strip()
                    if re.match(r"intervals\s*\[", lx):
                        iv = {}
                        i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(intervals|points|item)\s*\[", lv):
                                break
                            xm2 = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", lv)
                            xM2 = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", lv)
                            tx  = re.match(r'text\s*=\s*"(.*)"', lv)
                            if xm2: iv["xmin"] = float(xm2.group(1))
                            elif xM2: iv["xmax"] = float(xM2.group(1))
                            elif tx: iv["text"] = tx.group(1)
                            i += 1
                        intervals.append(iv)
                    else:
                        i += 1
                tier["intervals"] = intervals
                continue

            # TextTier (PointTier)
            pm = re.match(r"points:\s*size\s*=\s*(\d+)", l)
            if pm:
                n = int(pm.group(1))
                points = []
                i += 1
                while i < len(lines) and len(points) < n:
                    lx = lines[i].strip()
                    if re.match(r"points\s*\[", lx):
                        pt = {}
                        i += 1
                        while i < len(lines):
                            lv = lines[i].strip()
                            if re.match(r"(points|item)\s*\[", lv):
                                break
                            nm2  = re.match(r"number\s*=\s*([\d.eE+\-]+)", lv)
                            mk   = re.match(r'mark\s*=\s*"(.*)"', lv)
                            if nm2: pt["number"] = float(nm2.group(1))
                            elif mk: pt["mark"] = mk.group(1)
                            i += 1
                        points.append(pt)
                    else:
                        i += 1
                tier["points"] = points
                continue

            i += 1

        if "name" in tier:
            tiers.append(tier)

    return {"xmin": xmin, "xmax": xmax, "tiers": tiers}


# ============================================================================
# TextGrid writer — handles both IntervalTier and TextTier
# ============================================================================

def _esc(t) -> str:
    return str(t).replace('"', "'")


def write_textgrid(path: Path, xmin: float, xmax: float, tiers: list) -> None:
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        f"xmin = {xmin}",
        f"xmax = {xmax}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for ti, tier in enumerate(tiers, 1):
        tier_class = tier.get("class", "IntervalTier")
        lines += [
            f"    item [{ti}]:",
            f'        class = "{tier_class}"',
            f'        name = "{_esc(tier["name"])}"',
            f"        xmin = {xmin}",
            f"        xmax = {xmax}",
        ]

        if tier_class == "TextTier":
            points = tier.get("points", [])
            lines.append(f"        points: size = {len(points)}")
            for ii, pt in enumerate(points, 1):
                lines += [
                    f"        points [{ii}]:",
                    f"            number = {pt.get('number', 0.0)}",
                    f'            mark = "{_esc(pt.get("mark", ""))}"',
                ]
        else:
            intervals = tier.get("intervals", [])
            lines.append(f"        intervals: size = {len(intervals)}")
            for ii, iv in enumerate(intervals, 1):
                lines += [
                    f"        intervals [{ii}]:",
                    f"            xmin = {iv.get('xmin', 0.0)}",
                    f"            xmax = {iv.get('xmax', xmax)}",
                    f'            text = "{_esc(iv.get("text", ""))}"',
                ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================================
# Merge logic
# ============================================================================

def merge(gtobi_path: Path, sp_path: Path, output_path: Path) -> None:
    print(f"\nMerging: {gtobi_path.name} + {sp_path.parent.name}")

    gtobi = parse_textgrid(gtobi_path)
    sp    = parse_textgrid(sp_path)

    # Use GToBI duration as xmax (it is the ground-truth recording span)
    xmax = gtobi["xmax"]

    gtobi_by_name = {t["name"]: t for t in gtobi["tiers"]}
    sp_by_name    = {t["name"]: t for t in sp["tiers"]}

    merged = []

    # 1. Original GToBI word tier (IntervalTier)
    if "Wort" in gtobi_by_name:
        t = dict(gtobi_by_name["Wort"])
        t["name"] = "Wort"
        merged.append(t)

    # 2. Original GToBI tone tier (TextTier / PointTier)
    if "Ton" in gtobi_by_name:
        t = dict(gtobi_by_name["Ton"])
        t["name"] = "Ton"
        merged.append(t)

    # 3-7. SpeechPrint tiers
    for sp_name, out_name in [
        ("words",          "sp_words"),
        ("syllables",      "sp_syllables"),
        ("phonemes",       "sp_phonemes"),
        ("f0_pitch",       "sp_f0_pitch"),
        ("prosody_labels", "sp_prosody"),
    ]:
        if sp_name in sp_by_name:
            t = dict(sp_by_name[sp_name])
            t["name"] = out_name
            merged.append(t)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_textgrid(output_path, 0.0, xmax, merged)

    print(f"  Tiers merged ({len(merged)}):")
    for t in merged:
        tier_class = t.get("class", "IntervalTier")
        if tier_class == "TextTier":
            n = len(t.get("points", []))
            print(f"    {t['name']:25s}  {n} points  (TextTier)")
        else:
            n = len(t.get("intervals", []))
            print(f"    {t['name']:25s}  {n} intervals")
    print(f"  Written: {output_path}")


# ============================================================================
# Entry point
# ============================================================================

GTOBI_DIR = Path(__file__).parent / " five GToBI annotated sentences"
SP_DIR    = Path(__file__).parent / "out/german_gtobi"
OUT_DIR   = Path(__file__).parent / "out/german_gtobi_merged"

SENTENCES = [
    "eine_gelbe_banane",
    "einige_melonen",
    "er_sang_die_lieder",
    "er_will_die_rosen_haben",
    "ich_wohne_in_bern",
]


def main():
    parser = argparse.ArgumentParser(description="Merge GToBI + SpeechPrint TextGrids")
    parser.add_argument("--gtobi",   help="Path to original GToBI TextGrid")
    parser.add_argument("--sp",      help="Path to SpeechPrint TextGrid")
    parser.add_argument("--output",  help="Output path")
    args = parser.parse_args()

    if args.gtobi and args.sp and args.output:
        merge(Path(args.gtobi), Path(args.sp), Path(args.output))
        return

    # Batch mode: all five sentences
    print(f"Batch mode — merging all {len(SENTENCES)} GToBI sentences")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in SENTENCES:
        gtobi = GTOBI_DIR / f"{name}.TextGrid"
        sp    = SP_DIR / name / f"{name}.TextGrid"
        out   = OUT_DIR / f"{name}_MERGED.TextGrid"
        if not gtobi.exists():
            print(f"  SKIP (no GToBI TextGrid): {gtobi}")
            continue
        if not sp.exists():
            print(f"  SKIP (no SP TextGrid): {sp}")
            continue
        merge(gtobi, sp, out)

    print(f"\nDone. Merged TextGrids in: {OUT_DIR}")


if __name__ == "__main__":
    main()
