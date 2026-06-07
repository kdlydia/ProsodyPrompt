#!/usr/bin/env python3
"""DoReCo Cabécar — SpeechPrint with all 5 trackers + best single-tracker output.

Tier source : human-annotated DoReCo tiers (suffix @6, not @TA)
Trackers    : CREPE · pYIN · YIN · Praat · PESTO
Best output : CREPE full model + Xu(1999) + 5 optimisations

Outputs
  out/cabeca_comparison.TextGrid  — all 5 prosody tiers (for tracker comparison)
  out/cabeca_best.TextGrid        — single CREPE best (for questionnaire)
"""

from __future__ import annotations
import math, re, statistics, subprocess, sys
from pathlib import Path

HERE    = Path(__file__).parent
TG_IN   = HERE / "doreco_cabeca.TextGrid"
WAV_IN  = HERE / "doreco_cabeca.wav"
CMP_OUT = HERE / "out" / "cabeca_comparison.TextGrid"
BEST_OUT= HERE / "out" / "cabeca_best.TextGrid"

# Cabécar vowel set (SAMPA from ph@6 tier)
CABECA_VOWELS = {"a", "a~", "E", "E~", "I", "I~", "O", "O~", "U", "i", "u", "u~"}
SKIP = {"<p:>", "****", "<<fp>>", "<<fs>>", "<<ui>>"}
def _skip(t): return not t or any(t.startswith(s.rstrip(">")) for s in SKIP) or t in SKIP

SPIKE_ST   = 12.0
WEAK_FLOOR = 0.5
ALPHA      = 0.35
STRONG_F   = 2.5
HIGH_ST    = 0.8
LOW_ST     = 0.8
AMP_DB     = 1.5
F0_ST      = 1.0
VEL_ST_S   = 6.0
DUR_F      = 1.25
EDGE_TRIM  = 0.15
HIGH_SYM   = "‾"
LOW_SYM    = "_"


# ── TextGrid parser ───────────────────────────────────────────────────────────
def parse_tg(path):
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

def get_tier(tg, name):
    for t in tg["tiers"]:
        if t["name"] == name: return t["intervals"]
    return None


# ── maths ─────────────────────────────────────────────────────────────────────
def _st(a, b):
    if not a or not b or a <= 0 or b <= 0: return None
    return 12.0 * math.log2(b / a)

def _mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else None

def trim_xu(vals):
    voiced = [v for v in vals if v and v > 0]
    if len(voiced) < 2: return list(vals)
    med = statistics.median(voiced)
    tr = []
    for v in vals:
        if not v or v <= 0: tr.append(v); continue
        dev = abs(_st(med, v) or 0)
        if dev <= SPIKE_ST:
            tr.append(v)
        else:
            cands = [v * 2, v / 2]
            best = min(cands, key=lambda c: abs(_st(med, c) or float("inf")))
            tr.append(best if abs(_st(med, best) or 0) < SPIKE_ST else None)
    n = len(tr); sm = list(tr)
    for i in range(1, n - 1):
        a, b, c = tr[i-1], tr[i], tr[i+1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            sm[i] = (a + 2*b + c) / 4
    return sm


# ── F0 trackers ───────────────────────────────────────────────────────────────
def track_pyin(y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa
    hop = 256
    f0r, vf, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, frame_length=2048, hop_length=hop)
    times = librosa.frames_to_time(range(len(f0r)), sr=sr, hop_length=hop)
    f0 = np.where(vf & ~np.isnan(f0r), f0r, 0.0)
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    pYIN:  {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr

def track_yin(y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa
    hop = 256
    f0r = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=hop)
    times = librosa.frames_to_time(range(len(f0r)), sr=sr, hop_length=hop)
    f0 = np.where((f0r >= fmin) & (f0r <= fmax), f0r, 0.0)
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    YIN:   {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr

def track_praat(wav_path, y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa, parselmouth
    hop = 256
    times = librosa.frames_to_time(range(int(len(y)/hop)+1), sr=sr, hop_length=hop)
    snd = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch(time_step=hop/sr, pitch_floor=fmin, pitch_ceiling=fmax)
    f0 = np.array([(v if v and not math.isnan(v) else 0.0)
                   for v in (pitch.get_value_at_time(t) for t in times)])
    f0 = np.nan_to_num(f0, nan=0.0)
    f0 = np.where((f0 >= fmin) & (f0 <= fmax), f0, 0.0)
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    Praat: {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr

def track_crepe(y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa, torch, torchcrepe
    y16  = librosa.resample(y, orig_sr=sr, target_sr=16000)
    sr16, hop = 16000, 160
    freq, conf = torchcrepe.predict(
        torch.tensor(y16[None], dtype=torch.float32), sr16,
        hop_length=hop, fmin=fmin, fmax=fmax,
        model="full", decoder=torchcrepe.decode.viterbi,
        return_periodicity=True, batch_size=128, device="cpu",
    )
    freq = freq.squeeze().numpy(); conf = conf.squeeze().numpy()
    times = librosa.frames_to_time(range(len(freq)), sr=sr16, hop_length=hop)
    f0 = np.where((conf > 0.5) & (freq >= fmin) & (freq <= fmax), freq, 0.0)
    rms = librosa.feature.rms(y=y16, hop_length=hop)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    CREPE: {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr16

def track_pesto(y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa, torch, pesto
    y16 = librosa.resample(y, orig_sr=sr, target_sr=16000) if sr != 16000 else y.copy()
    sr16, hop = 16000, 160
    x = torch.from_numpy(y16.astype(np.float32)).unsqueeze(0)
    timestamps, freqs, _, periodicity = pesto.predict(x, sr16, step_size=10.0)
    times = timestamps.numpy()
    freqs = freqs.squeeze().numpy()
    per   = periodicity.squeeze().numpy()
    f0 = np.where((per > 0.5) & (freqs >= fmin) & (freqs <= fmax), freqs, 0.0)
    rms = librosa.feature.rms(y=y16, hop_length=hop)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    PESTO: {int(np.sum(f0 > 30))} voiced frames", flush=True)
    return times, f0, rms, sr16


# ── nucleus measurement ───────────────────────────────────────────────────────
def measure(times, f0, rms, t0, t1, n=10):
    import numpy as np
    dur = t1 - t0
    empty = {"f0_onset": None, "f0_offset": None, "f0_mean": None,
             "amplitude_db": None, "voiced": False, "velocity_st_s": None}
    if dur < 0.010: return empty
    margin = EDGE_TRIM * dur
    t0s, t1s = t0 + margin, t1 - margin
    if t1s - t0s < 0.010: t0s, t1s = t0, t1
    ts = [t0s + (t1s - t0s) * j / (n - 1) for j in range(n)]
    raw, rv = [], []
    for t in ts:
        idx = min(int(np.searchsorted(times, t)), len(f0) - 1)
        v = float(f0[idx])
        raw.append(v if v > 30 else None)
        rv.append(float(rms[idx]))
    pts    = trim_xu(raw)
    voiced = [v for v in pts if v and v > 0]
    ok     = len(voiced) / n > 0.3
    onset  = next((v for v in pts if v), None)
    offset = next((v for v in reversed(pts) if v), None)
    f0m    = _mean(voiced)
    rmsm   = _mean(rv)
    amp    = (20 * math.log10(rmsm + 1e-10) + 120) if rmsm else None
    vel    = None
    if onset and offset and dur > 0:
        mv = _st(onset, offset)
        if mv is not None: vel = mv / dur
    return {"f0_onset": onset, "f0_offset": offset, "f0_mean": f0m,
            "amplitude_db": amp, "voiced": ok, "velocity_st_s": vel}


# ── syllabification ───────────────────────────────────────────────────────────
def syllabify(phone_ivs, vowels):
    phones = [iv["text"] for iv in phone_ivs]
    n = len(phones)
    if not n: return []
    vids = [i for i, p in enumerate(phones) if p in vowels]
    if not vids:
        s, e = phone_ivs[0]["start"], phone_ivs[-1]["end"]
        return [{"start": s, "end": e, "label": "".join(phones), "v0": s, "v1": e}]
    bounds = []
    for k, vi in enumerate(vids):
        onset = 0 if k == 0 else vids[k-1] + 1 + (vi - vids[k-1] - 1) // 2
        if bounds and k > 0: bounds[-1] = (bounds[-1][0], onset)
        bounds.append((onset, n if k == len(vids) - 1 else vi + 1))
    out = []
    for ps, pe in bounds:
        ivs = phone_ivs[ps:pe]
        s, e = ivs[0]["start"], ivs[-1]["end"]
        vi = [iv for iv in ivs if iv["text"] in vowels]
        out.append({"start": s, "end": e, "label": "".join(phones[ps:pe]),
                    "v0": vi[0]["start"] if vi else s,
                    "v1": vi[-1]["end"]  if vi else e})
    return out


# ── prosody labelling (all 5 optimisations) ───────────────────────────────────
def label_prosody(syls, utt_breaks=None):
    n = len(syls)
    if not n: return
    breaks = sorted(utt_breaks or [])
    utt_of = [sum(1 for b in breaks if s["start"] >= b) for s in syls]

    for s in syls:
        s["_mv"] = _st(s.get("f0_onset"), s.get("f0_offset"))

    mvs = [abs(s["_mv"]) for s in syls if s["_mv"] is not None]
    if len(mvs) >= 4:
        med_mv = statistics.median(mvs)
        mad    = statistics.median([abs(x - med_mv) for x in mvs])
        std    = 1.4826 * mad if mad > 0 else 2.0
    elif len(mvs) >= 2:
        std = statistics.stdev(mvs)
    else:
        std = 2.0
    wthr = max(WEAK_FLOOR, ALPHA * std)
    sthr = max(wthr * STRONG_F, 2.0)

    utts = {}
    for i, ui in enumerate(utt_of): utts.setdefault(ui, []).append(i)

    f0_det = {}
    for ui, idxs in utts.items():
        voiced = [(syls[j]["start"], syls[j]["f0_mean"])
                  for j in idxs if syls[j].get("f0_mean")]
        if len(voiced) >= 3:
            ts = [p[0] for p in voiced]; fs = [p[1] for p in voiced]
            tc = sum(ts)/len(ts); fc = sum(fs)/len(fs)
            num = sum((t-tc)*(f-fc) for t,f in zip(ts,fs))
            den = sum((t-tc)**2 for t in ts)
            slope = num/den if den > 0 else 0.0
            for j in idxs:
                fm = syls[j].get("f0_mean")
                f0_det[j] = (fm - slope*(syls[j]["start"]-tc)) if fm else None
        else:
            for j in idxs: f0_det[j] = syls[j].get("f0_mean")

    for i, s in enumerate(syls):
        mv  = s["_mv"]
        vel = s.get("velocity_st_s")
        f0m = f0_det.get(i)
        amp = s.get("amplitude_db")
        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in (i-1, i+1):
            if 0 <= j < n and utt_of[j] == utt_of[i]:
                v = f0_det.get(j); a = syls[j].get("amplitude_db")
                d = syls[j]["end"] - syls[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)
        nf0  = _mean(nbr_f0); namp = _mean(nbr_amp)
        ndur = _mean(nbr_dur) if nbr_dur else None
        dur  = s["end"] - s["start"]
        is_long = ndur and dur >= DUR_F * ndur
        hst     = _st(nf0, f0m) if (nf0 and f0m) else None
        is_high = hst is not None and hst >=  HIGH_ST
        is_low  = hst is not None and hst <= -LOW_ST
        above   = (amp - namp) if (amp and namp) else None
        is_loud = above is not None and above >= AMP_DB
        strong  = (abs(mv) >= sthr if mv else False) or \
                  (abs(vel) >= VEL_ST_S if vel else False)

        if mv is None:    direction = ""
        elif mv >=  wthr: direction = "//" if strong else "/"
        elif mv <= -wthr: direction = "\\\\" if strong else "\\"
        else:             direction = ""

        h = (HIGH_SYM if is_high else (LOW_SYM if is_low else
             (HIGH_SYM if (f0m and nf0) else "?"))) if direction == "" else \
            (HIGH_SYM if is_high else (LOW_SYM if is_low else ""))

        accent = ((is_loud and hst is not None and hst >= F0_ST)
                  or (is_long and is_loud and is_high))
        sym = ("*" if accent else "") + (h + direction if h else direction) or \
              ("?" if not f0m else HIGH_SYM)
        s["symbol"] = sym; s["accent"] = accent


# ── TextGrid writer ───────────────────────────────────────────────────────────
def fill(rows, xmax):
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

def write_tg(path, xmax, tiers):
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
    print(f"  Written: {path}", flush=True)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nCabécar SpeechPrint: {TG_IN.name}", flush=True)

    tg   = parse_tg(TG_IN)
    xmax = tg["xmax"]

    tx = get_tier(tg, "tx@6")
    ft = get_tier(tg, "ft@6")
    wd = get_tier(tg, "wd@6")
    gl = get_tier(tg, "gl@6")
    ph = get_tier(tg, "ph@6")
    if wd is None or ph is None:
        sys.exit("ERROR: wd@6 or ph@6 missing from TextGrid")

    def utt(tier):
        return [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                for iv in (tier or []) if iv["text"] and not _skip(iv["text"])]

    sentence_rows    = utt(tx)
    translation_rows = utt(ft)

    word_rows, real_words = [], []
    for iv in wd:
        if _skip(iv["text"]):
            gap = iv["end"] - iv["start"]
            if gap >= 0.04:
                word_rows.append({"start": iv["start"], "end": iv["end"],
                                  "value": f"<sil {gap:.2f}s>"})
        else:
            word_rows.append({"start": iv["start"], "end": iv["end"],
                              "value": iv["text"]})
            real_words.append(iv)

    gloss_rows = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in (gl or []) if iv["text"] and not _skip(iv["text"])]

    phone_rows = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in ph if iv["text"] and not _skip(iv["text"])]

    syl_rows, syl_tmpls = [], []
    for wiv in real_words:
        wp = [iv for iv in ph
              if iv["start"] >= wiv["start"] - 1e-4
              and iv["end"]  <= wiv["end"]   + 1e-4
              and iv["text"] and not _skip(iv["text"])]
        if not wp: continue
        for s in syllabify(wp, CABECA_VOWELS):
            syl_rows.append({"start": s["start"], "end": s["end"], "value": s["label"]})
            syl_tmpls.append(s)

    utt_breaks = [iv["end"] for iv in (tx or [])
                  if iv["text"] and not _skip(iv["text"])]

    # ── load audio ────────────────────────────────────────────────────────────
    print("  Loading audio…", flush=True)
    import librosa
    y, sr = librosa.load(str(WAV_IN), sr=None, mono=True)

    # ── auto pitch range from speaker ────────────────────────────────────────
    scan = y[:int(20 * sr)]
    _, vf, _ = librosa.pyin(scan, fmin=65, fmax=500, sr=sr,
                             frame_length=2048, hop_length=256)
    import numpy as np
    f0_scan, _, _ = librosa.pyin(scan, fmin=65, fmax=500, sr=sr,
                                  frame_length=2048, hop_length=256)
    voiced_scan = f0_scan[vf & ~np.isnan(f0_scan)] if vf is not None else np.array([])
    if len(voiced_scan) > 10:
        med = float(np.median(voiced_scan))
        fmin_use = max(50.0, med * 0.5)
        fmax_use = min(600.0, med * 2.5)
    else:
        fmin_use, fmax_use = 65.0, 500.0
    print(f"  Pitch range: {fmin_use:.0f}–{fmax_use:.0f} Hz", flush=True)

    # ── run all trackers ──────────────────────────────────────────────────────
    print("  Running F0 trackers:", flush=True)
    results = {}

    print("  → pYIN…", flush=True)
    results["pyin"] = track_pyin(y, sr, fmin_use, fmax_use)

    print("  → YIN…", flush=True)
    results["yin"] = track_yin(y, sr, fmin_use, fmax_use)

    print("  → Praat…", flush=True)
    try:    results["praat"] = track_praat(WAV_IN, y, sr, fmin_use, fmax_use)
    except Exception as e: print(f"    Praat failed: {e}"); results["praat"] = None

    print("  → CREPE (slow)…", flush=True)
    try:    results["crepe"] = track_crepe(y, sr, fmin_use, fmax_use)
    except Exception as e: print(f"    CREPE failed: {e}"); results["crepe"] = None

    print("  → PESTO…", flush=True)
    try:    results["pesto"] = track_pesto(y, sr, fmin_use, fmax_use)
    except Exception as e: print(f"    PESTO failed: {e}"); results["pesto"] = None

    # ── build prosody tier for each tracker ───────────────────────────────────
    def prosody_tier(result):
        if result is None:
            return [{"start": s["start"], "end": s["end"], "value": ""} for s in syl_tmpls]
        times, f0, rms, _ = result
        syls = []
        for tmpl in syl_tmpls:
            s = dict(tmpl)
            s.update(measure(times, f0, rms, tmpl["v0"], tmpl["v1"]))
            syls.append(s)
        label_prosody(syls, utt_breaks=utt_breaks)
        return [{"start": s["start"], "end": s["end"], "value": s.get("symbol", "?")}
                for s in syls]

    p_crepe = prosody_tier(results["crepe"])
    p_pyin  = prosody_tier(results["pyin"])
    p_yin   = prosody_tier(results["yin"])
    p_praat = prosody_tier(results["praat"])
    p_pesto = prosody_tier(results["pesto"])

    common_rows = [
        {"name": "sentence",     "rows": sentence_rows},
        {"name": "words",        "rows": word_rows},
        {"name": "translation",  "rows": translation_rows},
        {"name": "syllables",    "rows": syl_rows},
        {"name": "phones",       "rows": phone_rows},
    ]

    # ── comparison TextGrid (all 5 trackers) ──────────────────────────────────
    CMP_OUT.parent.mkdir(parents=True, exist_ok=True)
    write_tg(CMP_OUT, xmax, common_rows + [
        {"name": "prosody_crepe", "rows": p_crepe},
        {"name": "prosody_pyin",  "rows": p_pyin},
        {"name": "prosody_yin",   "rows": p_yin},
        {"name": "prosody_praat", "rows": p_praat},
        {"name": "prosody_pesto", "rows": p_pesto},
    ])

    # ── best TextGrid (CREPE only, 6 tiers) ───────────────────────────────────
    write_tg(BEST_OUT, xmax, common_rows + [
        {"name": "prosody", "rows": p_crepe},
    ])

    print(f"\n  Words: {len(real_words)}  Syllables: {len(syl_tmpls)}", flush=True)
    print(f"  Utterance breaks: {len(utt_breaks)}", flush=True)


if __name__ == "__main__":
    main()
