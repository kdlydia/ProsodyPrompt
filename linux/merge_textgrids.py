#!/usr/bin/env python3
"""Merge human DoReCo TextGrid with SpeechPrint output into a single comparison TextGrid.

Tier order in output (for Praat readability):
  Human tiers (prefixed h_): tx@TA, wd@TA, ph@TA, mb@TA, gl@TA, ps@TA, ref@TA, ft@TA
  SpeechPrint tiers (prefixed sp_): words, syllables, phonemes, f0_pitch, prosody_labels
"""

import re
import sys
from pathlib import Path


def parse_textgrid(path: Path) -> dict:
    """Parse a Praat TextGrid into a dict with keys:
        xmin, xmax, tiers: list of {name, class, xmin, xmax, intervals: [{xmin, xmax, text}]}
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def find(pattern, start=0):
        for i in range(start, len(lines)):
            m = re.match(pattern, lines[i].strip())
            if m:
                return i, m
        return -1, None

    _, m = find(r"xmin\s*=\s*([\d.]+)")
    xmin = float(m.group(1)) if m else 0.0
    _, m = find(r"xmax\s*=\s*([\d.]+)")
    xmax = float(m.group(1)) if m else 0.0

    tiers = []
    i = 0
    while i < len(lines):
        m = re.match(r"\s*item\s*\[(\d+)\]\s*:", lines[i])
        if m:
            tier = {}
            i += 1
            while i < len(lines):
                l = lines[i].strip()
                if re.match(r"item\s*\[", l):
                    break
                if re.match(r'class\s*=\s*"(.+)"', l):
                    tier["class"] = re.match(r'class\s*=\s*"(.+)"', l).group(1)
                elif re.match(r'name\s*=\s*"(.*)"', l):
                    tier["name"] = re.match(r'name\s*=\s*"(.*)"', l).group(1)
                elif re.match(r"xmin\s*=\s*([\d.]+)", l):
                    tier["xmin"] = float(re.match(r"xmin\s*=\s*([\d.]+)", l).group(1))
                elif re.match(r"xmax\s*=\s*([\d.]+)", l):
                    tier["xmax"] = float(re.match(r"xmax\s*=\s*([\d.]+)", l).group(1))
                elif re.match(r"intervals:\s*size\s*=\s*(\d+)", l):
                    n = int(re.match(r"intervals:\s*size\s*=\s*(\d+)", l).group(1))
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
                                xm = re.match(r"xmin\s*=\s*([\d.eE+\-]+)", lv)
                                xM = re.match(r"xmax\s*=\s*([\d.eE+\-]+)", lv)
                                tx = re.match(r'text\s*=\s*"(.*)"', lv)
                                if xm: iv["xmin"] = float(xm.group(1))
                                elif xM: iv["xmax"] = float(xM.group(1))
                                elif tx: iv["text"] = tx.group(1)
                                i += 1
                            intervals.append(iv)
                        else:
                            i += 1
                    tier["intervals"] = intervals
                    continue
                i += 1
            if "name" in tier:
                tiers.append(tier)
            continue
        i += 1

    return {"xmin": xmin, "xmax": xmax, "tiers": tiers}


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
        intervals = tier.get("intervals", [])
        lines += [
            f"    item [{ti}]:",
            f'        class = "IntervalTier"',
            f'        name = "{tier["name"]}"',
            f"        xmin = {xmin}",
            f"        xmax = {xmax}",
            f"        intervals: size = {len(intervals)}",
        ]
        for ii, iv in enumerate(intervals, 1):
            lines += [
                f"        intervals [{ii}]:",
                f"            xmin = {iv.get('xmin', 0.0)}",
                f"            xmax = {iv.get('xmax', xmax)}",
                f'            text = "{str(iv.get("text", "")).replace(chr(34), chr(39))}"',
            ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    base = Path(__file__).parent
    human_tg = base / "doreco_port1286_2017_06_30_Jaklin.TextGrid"
    sp_tg = base / "out/doreco_port1286_2017_06_30_Jaklin/doreco_port1286_2017_06_30_Jaklin.TextGrid"
    out_tg = base / "out/doreco_port1286_2017_06_30_Jaklin_COMPARISON.TextGrid"

    print(f"Reading human TextGrid: {human_tg}")
    human = parse_textgrid(human_tg)
    print(f"  {len(human['tiers'])} tiers, duration={human['xmax']}s")

    print(f"Reading SpeechPrint TextGrid: {sp_tg}")
    sp = parse_textgrid(sp_tg)
    print(f"  {len(sp['tiers'])} tiers, duration={sp['xmax']}s")

    # Use the human recording duration as the reference xmax
    xmax = human["xmax"]

    # Human tiers to include, in display order
    human_include = ["tx@TA", "wd@TA", "ph@TA", "mb@TA", "gl@TA", "ps@TA", "ref@TA", "ft@TA"]
    # SpeechPrint tiers to include (skip warnings_review)
    sp_include = ["words", "syllables", "phonemes", "f0_pitch", "prosody_labels"]

    human_by_name = {t["name"]: t for t in human["tiers"]}
    sp_by_name = {t["name"]: t for t in sp["tiers"]}

    merged_tiers = []

    for name in human_include:
        if name in human_by_name:
            tier = dict(human_by_name[name])
            tier["name"] = "h_" + name
            merged_tiers.append(tier)

    for name in sp_include:
        if name in sp_by_name:
            tier = dict(sp_by_name[name])
            tier["name"] = "sp_" + name
            merged_tiers.append(tier)

    print(f"\nMerged tiers ({len(merged_tiers)}):")
    for t in merged_tiers:
        n_iv = len(t.get("intervals", []))
        print(f"  {t['name']:30s}  {n_iv} intervals")

    out_tg.parent.mkdir(parents=True, exist_ok=True)
    write_textgrid(out_tg, 0.0, xmax, merged_tiers)
    print(f"\n✓ Written: {out_tg}")


if __name__ == "__main__":
    main()
