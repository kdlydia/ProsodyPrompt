from pathlib import Path
import os
import re, shutil, subprocess, csv


def _find_runner() -> Path:
    """Locate mfa/run_mfa.sh without baking a username into the path.

    Resolution order:
      1. SPEECHPRINT_ROOT env var
      2. Walk up from this file looking for a sibling `mfa/run_mfa.sh`
      3. ~/SpeechPrint/mfa/run_mfa.sh
    """
    candidates = []
    sp_root = os.environ.get("SPEECHPRINT_ROOT")
    if sp_root:
        candidates.append(Path(sp_root).expanduser() / "mfa" / "run_mfa.sh")
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidates.append(parent / "mfa" / "run_mfa.sh")
    candidates.append(Path.home() / "SpeechPrint" / "mfa" / "run_mfa.sh")
    for c in candidates:
        if c.is_file():
            return c
    # Last resort: assume two levels up from this module
    return here.parent.parent / "mfa" / "run_mfa.sh"


RUNNER = _find_runner()
ROOT = RUNNER.parent.parent

ARPABET = {
 "AA":"ɑ","AE":"æ","AH":"ʌ","AO":"ɔ","AW":"aʊ","AY":"aɪ","EH":"ɛ","ER":"ɝ","EY":"eɪ",
 "IH":"ɪ","IY":"i","OW":"oʊ","OY":"ɔɪ","UH":"ʊ","UW":"u","SH":"ʃ","ZH":"ʒ","CH":"tʃ",
 "JH":"dʒ","TH":"θ","DH":"ð","NG":"ŋ","Y":"j"
}
VOWELS = set("ɑæʌɔaɛɝeɪioʊuəɚ")

def norm_text(t):
    t = re.sub(r"[^A-Za-zÀ-ÿ0-9' -]+", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()

def phone_ipa(p):
    p = re.sub(r"\d", "", p.strip()).upper()
    return ARPABET.get(p, p.lower())

def read_tg(path):
    txt = path.read_text(errors="replace")
    tiers = {}
    for block in re.split(r"\n\s*item \[\d+\]:", txt):
        nm = re.search(r'name = "([^"]+)"', block)
        if not nm: continue
        rows = []
        for m in re.finditer(r"xmin = ([0-9.eE+-]+)\s*xmax = ([0-9.eE+-]+)\s*text = \"([^\"]*)\"", block, re.S):
            rows.append({"start":float(m.group(1)), "end":float(m.group(2)), "text":m.group(3)})
        tiers[nm.group(1)] = rows
    return tiers

def is_vowel(ph):
    return any(v in phone_ipa(ph) for v in VOWELS)

def syllabify(phones):
    clean = [p for p in phones if p["text"].strip().lower() not in {"sp","sil","spn","<eps>"}]
    sylls, cur = [], []
    for p in clean:
        cur.append(p)
        if is_vowel(p["text"]):
            sylls.append(cur)
            cur = []
    if cur:
        if sylls: sylls[-1].extend(cur)
        else: sylls.append(cur)
    return [{"start":g[0]["start"], "end":g[-1]["end"], "text":"".join(phone_ipa(x["text"]) for x in g)} for g in sylls if g]

def write_tg(path, dur, tiers):
    order = ["words","phonemes","syllables","accent_target","f0_pitch","prosody_labels","warnings_review"]
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "", "xmin = 0", f"xmax = {dur}", "tiers? <exists>", f"size = {len(order)}", "item []:"]
    for n,tier in enumerate(order,1):
        rows = tiers.get(tier, [])
        lines += [f"    item [{n}]:", '        class = "IntervalTier"', f'        name = "{tier}"', "        xmin = 0", f"        xmax = {dur}", f"        intervals: size = {len(rows)}"]
        for i,r in enumerate(rows,1):
            text = str(r.get("text","")).replace('"', "'")
            lines += [f"        intervals [{i}]:", f"            xmin = {r['start']}", f"            xmax = {r['end']}", f'            text = "{text}"']
    path.write_text("\n".join(lines)+"\n")

def run_precise(wav, transcript, out_root, lang="en"):
    wav = Path(wav).resolve()
    out = Path(out_root) / wav.stem
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wav, out / f"{wav.stem}.wav")

    work = out / "_mfa_work"
    inp = work / "mfa_input"
    alg = work / "mfa_aligned"
    shutil.rmtree(work, ignore_errors=True)
    inp.mkdir(parents=True)

    shutil.copy2(wav, inp / f"{wav.stem}.wav")
    (inp / f"{wav.stem}.lab").write_text(norm_text(transcript) + "\n")

    subprocess.run([str(RUNNER), str(work), lang], check=True)

    tg = next(alg.rglob(f"{wav.stem}.TextGrid"), None)
    if not tg:
        raise RuntimeError("MFA produced no TextGrid")

    raw = read_tg(tg)
    words = raw.get("words") or raw.get("word") or []
    phones_raw = raw.get("phones") or raw.get("phone") or []
    phones = [{"start":p["start"],"end":p["end"],"text":phone_ipa(p["text"])} for p in phones_raw if p["text"].strip()]

    sylls = syllabify(phones_raw)
    dur = max([x["end"] for x in words + phones] or [0])

    star = -1
    if sylls:
        star = max(range(len(sylls)), key=lambda i: sylls[i]["end"] - sylls[i]["start"])
    accent = [{"start":s["start"],"end":s["end"],"text":"*" if i == star else ""} for i,s in enumerate(sylls)]
    prosody = [{"start":s["start"],"end":s["end"],"text":"-"} for s in sylls]

    tiers = {
        "words": words,
        "phonemes": phones,
        "syllables": sylls,
        "accent_target": accent,
        "f0_pitch": [{"start":0,"end":dur,"text":"pending"}],
        "prosody_labels": prosody,
        "warnings_review": [{"start":0,"end":dur,"text":"MFA timing used. Prosody symbols conservative."}],
    }
    write_tg(out / f"{wav.stem}.TextGrid", dur, tiers)

    for name, rows in tiers.items():
        with (out / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["start","end","text"])
            w.writeheader()
            w.writerows(rows)

    print(f"✓ Wrote {out}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--language", default="en")
    ap.add_argument("--output", default="out")
    a = ap.parse_args()
    run_precise(a.wav, a.transcript, a.output, a.language)
