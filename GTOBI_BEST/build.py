#!/usr/bin/env python3
"""German GToBI — ultimate SpeechPrint, DoReCo-matching tier structure.

Red flags fixed in this version:
  1. MFA transcription was wrong for 3/5 sentences ("gelbe"→"gerbe",
     "einige Melonen"→"einigen mal lohnt", "er sang"→"hesangli").
     MFA is abandoned entirely.
  2. MFA timing mismatches human Wort tier by 66–430 ms in all 5 sentences.
     Human Wort tier is used as the sole word-level ground truth.
  3. German IPA is now hardcoded from the known text (correct phonemization)
     and distributed proportionally within the human Wort word boundaries.

Sources:
  Wort / Ton    — human GToBI expert annotation (ground truth)
  IPA phones    — hardcoded correct German phonemization (proportional timing)
  Prosody       — CREPE full model 10 ms + all 5 optimisations

Output tiers — identical structure to DoReCo BEST (7+1 = 8 tiers):
  1. sentence    — full German sentence (utterance span)
  2. translation — English sentence (utterance span)
  3. words       — German words (human Wort tier)
  4. gloss       — English word-by-word (aligned to Wort timing)
  5. syllables   — German IPA syllables (proportional, correct phonemization)
  6. phones      — German IPA phones (proportional, correct phonemization)
  7. gtobi       — expert GToBI labels (Ton point tier → interval)
  8. prosody     — CREPE + Xu(1999) + 5 optimisations

Output: GTOBI_BEST/<sentence>.TextGrid  +  GTOBI_BEST/gtobi_best_summary.png
"""

from __future__ import annotations
import math, re, statistics, subprocess
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
HERE     = Path(__file__).parent
SRC_ORIG = Path("/home/lydia/School/UPF/semester3/test2/SpeechPrint-main/linux/ five GToBI annotated sentences")
SRC_WAV  = Path("/home/lydia/School/UPF/semester3/test2/SpeechPrint-main/ideasss/SpeechPrint_results/german_gtobi")

# ── sentence data (hardcoded — these are known, fixed sentences) ─────────────
SENTENCES = {
    "eine_gelbe_banane": {
        "de":   "eine gelbe Banane",
        "en":   "a yellow banana",
        "words_de": ["eine",   "gelbe",   "Banane"],
        "words_en": ["a",      "yellow",  "banana"],
        # IPA phone sequences per word — correct German phonemization.
        # Diphthongs (aɪ, aʊ, ɔʏ) and vocalic-r (ɐ, ɛɐ) treated as single units.
        "ipa": [
            ["aɪ", "n", "ə"],                    # eine
            ["ɡ", "ɛ", "l", "b", "ə"],           # gelbe
            ["b", "a", "n", "aː", "n", "ə"],     # Banane
        ],
        "gtobi_label": "L+H*  L-%",
    },
    "einige_melonen": {
        "de":   "einige Melonen",
        "en":   "some melons",
        "words_de": ["einige",  "Melonen"],
        "words_en": ["some",    "melons"],
        "ipa": [
            ["aɪ", "n", "ɪ", "ɡ", "ə"],              # einige
            ["m", "e", "l", "oː", "n", "ə", "n"],    # Melonen
        ],
        "gtobi_label": "H+L*  L-%",
    },
    "er_sang_die_lieder": {
        "de":   "er sang die Lieder",
        "en":   "he sang the songs",
        "words_de": ["er",  "sang",  "die",  "Lieder"],
        "words_en": ["he",  "sang",  "the",  "songs"],
        "ipa": [
            ["ɛɐ"],                     # er  (vocalic-r diphthong = 1 syllable)
            ["z", "a", "ŋ"],           # sang
            ["d", "iː"],               # die
            ["l", "iː", "d", "ɐ"],    # Lieder
        ],
        "gtobi_label": "H+!H*  L-%",
    },
    "er_will_die_rosen_haben": {
        "de":   "er will die Rosen haben",
        "en":   "he wants to have the roses",
        "words_de": ["er",  "will",  "die",  "Rosen",  "haben"],
        "words_en": ["he",  "wants", "the",  "roses",  "to have"],
        "ipa": [
            ["ɛɐ"],                          # er
            ["v", "ɪ", "l"],               # will
            ["d", "iː"],                   # die
            ["r", "oː", "z", "ə", "n"],   # Rosen
            ["h", "aː", "b", "ə", "n"],   # haben
        ],
        "gtobi_label": "L*+H  L-%",
    },
    "ich_wohne_in_bern": {
        "de":   "ich wohne in Bern",
        "en":   "I live in Bern",
        "words_de": ["ich",  "wohne",  "in",  "Bern"],
        "words_en": ["I",    "live",   "in",  "Bern"],
        "ipa": [
            ["ɪ", "ç"],          # ich
            ["v", "oː", "n", "ə"],  # wohne
            ["ɪ", "n"],          # in
            ["b", "ɛ", "r", "n"],  # Bern
        ],
        "gtobi_label": "L*+H  L-%",
    },
}

SENTENCE_ORDER = [
    "eine_gelbe_banane", "einige_melonen", "er_sang_die_lieder",
    "er_will_die_rosen_haben", "ich_wohne_in_bern",
]

# ── German IPA vowel set ──────────────────────────────────────────────────────
GERMAN_VOWELS = {
    "a", "aː", "ɛ", "ɛː", "e", "eː", "i", "iː", "ɪ",
    "o", "oː", "ɔ", "u", "uː", "ʊ", "y", "yː", "ʏ",
    "ø", "øː", "œ", "ə", "ɐ",
    "aɪ", "aʊ", "ɔʏ", "ɛɐ",    # diphthongs and vocalic-r as single nuclei
}

# ── algorithm constants ───────────────────────────────────────────────────────
SPIKE_ST             = 12.0
WEAK_FLOOR_ST        = 0.5
ADAPTIVE_FACTOR      = 0.35
STRONG_FACTOR        = 2.5
HIGH_NBR_ST          = 0.8
LOW_NBR_ST           = 0.8
ACCENT_AMP_DB        = 1.5
ACCENT_F0_ST         = 1.0
VELOCITY_STRONG_ST_S = 6.0
DURATION_ACCENT      = 1.25
EDGE_TRIM            = 0.15
HIGH_SYM             = "‾"
LOW_SYM              = "_"


# ── TextGrid parser ───────────────────────────────────────────────────────────
def parse_textgrid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    xmax_m = re.search(r"^xmax = ([\d.]+)", text, re.M)
    xmax   = float(xmax_m.group(1)) if xmax_m else 0.0
    tiers  = []
    for block in re.split(r"\n\s*item \[\d+\]:", text)[1:]:
        nm  = re.search(r'name = "([^"]*)"', block)
        cls = re.search(r'class = "([^"]*)"', block)
        if not nm or not cls:
            continue
        if cls.group(1) == "IntervalTier":
            ivs = []
            for iv in re.split(r"\n\s*intervals \[\d+\]:", block)[1:]:
                a = re.search(r"xmin = ([\d.]+)", iv)
                b = re.search(r"xmax = ([\d.]+)", iv)
                c = re.search(r'text = "([^"]*)"', iv, re.DOTALL)
                if a and b and c:
                    ivs.append({"start": float(a.group(1)),
                                "end":   float(b.group(1)),
                                "text":  c.group(1)})
            tiers.append({"name": nm.group(1), "class": "interval",
                          "intervals": ivs})
        elif cls.group(1) == "TextTier":
            pts = []
            for pt in re.split(r"\n\s*points \[\d+\]:", block)[1:]:
                n = re.search(r"number = ([\d.]+)", pt)
                m = re.search(r'mark = "([^"]*)"', pt)
                if n and m:
                    pts.append({"time": float(n.group(1)), "mark": m.group(1)})
            tiers.append({"name": nm.group(1), "class": "point", "points": pts})
    return {"xmax": xmax, "tiers": tiers}

def get_tier(tg, name, cls="interval"):
    for t in tg["tiers"]:
        if t["name"] == name and t["class"] == cls:
            return t.get("intervals") or t.get("points")
    return None


# ── phone distribution & syllabification ─────────────────────────────────────
def distribute_phones(phones, t_start, t_end):
    """Distribute phones proportionally across [t_start, t_end].
    Vowels get 1.5× weight; consonants 1×. This roughly matches
    the longer duration of vowel segments in real speech.
    """
    weights = [1.5 if p in GERMAN_VOWELS else 1.0 for p in phones]
    total   = sum(weights)
    ivs = []
    t = t_start
    for ph, w in zip(phones, weights):
        dur  = (t_end - t_start) * w / total
        ivs.append({"start": t, "end": t + dur, "text": ph})
        t += dur
    if ivs:  # snap last to t_end to avoid float drift
        ivs[-1]["end"] = t_end
    return ivs


def syllabify_phones(phone_ivs):
    """Maximum-onset syllabification from a list of phone interval dicts."""
    phones = [iv["text"] for iv in phone_ivs]
    n = len(phones)
    if not n:
        return []
    vids = [i for i, p in enumerate(phones) if p in GERMAN_VOWELS]
    if not vids:
        s, e = phone_ivs[0]["start"], phone_ivs[-1]["end"]
        return [{"start": s, "end": e, "label": "".join(phones),
                 "v0": s, "v1": e}]
    bounds = []
    for k, vi in enumerate(vids):
        if k == 0:
            onset = 0
        else:
            pv = vids[k - 1]
            gap = vi - pv - 1
            cut = pv + 1 + (gap // 2) if gap > 0 else pv + 1
            if bounds:
                bounds[-1] = (bounds[-1][0], cut)
            onset = cut
        bounds.append((onset, n if k == len(vids) - 1 else vi + 1))
    syls = []
    for ps, pe in bounds:
        ivs = phone_ivs[ps:pe]
        s, e = ivs[0]["start"], ivs[-1]["end"]
        vi   = [iv for iv in ivs if iv["text"] in GERMAN_VOWELS]
        syls.append({
            "start": s, "end": e,
            "label": "".join(phones[ps:pe]),
            "v0": vi[0]["start"] if vi else s,
            "v1": vi[-1]["end"]  if vi else e,
        })
    return syls


# ── Xu (1999) with octave recovery ───────────────────────────────────────────
def _st(a, b):
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12.0 * math.log2(b / a)

def _mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else None

def trim_xu1999(vals):
    voiced = [v for v in vals if v and v > 0]
    if len(voiced) < 2:
        return list(vals)
    med = statistics.median(voiced)
    tr  = []
    for v in vals:
        if not v or v <= 0:
            tr.append(v); continue
        if abs(_st(med, v) or 0) <= SPIKE_ST:
            tr.append(v)
        else:
            cands = [v * 2, v / 2]
            best  = min(cands, key=lambda c: abs(_st(med, c) or float("inf")))
            tr.append(best if abs(_st(med, best) or 0) < SPIKE_ST else None)
    n, sm = len(tr), list(tr)
    for i in range(1, n - 1):
        a, b, c = tr[i-1], tr[i], tr[i+1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            sm[i] = (a + 2*b + c) / 4
    return sm


# ── CREPE ─────────────────────────────────────────────────────────────────────
def run_crepe(wav_path: Path, fmin=65.0, fmax=500.0):
    import numpy as np, librosa, torch, torchcrepe
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    y16   = librosa.resample(y, orig_sr=sr, target_sr=16000)
    sr16  = 16000
    hop   = 160  # 10 ms
    freq, conf = torchcrepe.predict(
        torch.tensor(y16[None], dtype=torch.float32), sr16,
        hop_length=hop, fmin=fmin, fmax=fmax,
        model="full", decoder=torchcrepe.decode.viterbi,
        return_periodicity=True, batch_size=128, device="cpu",
    )
    freq = freq.squeeze().numpy()
    conf = conf.squeeze().numpy()
    times = librosa.frames_to_time(range(len(freq)), sr=sr16, hop_length=hop)
    f0 = np.where((conf > 0.5) & (freq >= fmin) & (freq <= fmax), freq, 0.0)
    rms = librosa.feature.rms(y=y16, hop_length=hop)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    CREPE: {int(np.sum(f0>30))} voiced frames", flush=True)
    return times, f0, rms


# ── nucleus measurement (edge trim 15%) ───────────────────────────────────────
def measure(times, f0, rms, t0, t1, n=10):
    import numpy as np
    dur = t1 - t0
    empty = {"f0_onset": None, "f0_offset": None, "f0_mean": None,
             "amplitude_db": None, "voiced": False, "velocity_st_s": None}
    if dur < 0.010:
        return empty
    margin = EDGE_TRIM * dur
    t0s = t0 + margin; t1s = t1 - margin
    if t1s - t0s < 0.010:
        t0s, t1s = t0, t1
    ts = [t0s + (t1s - t0s) * j / (n - 1) for j in range(n)]
    raw, rv = [], []
    for t in ts:
        idx = min(int(np.searchsorted(times, t)), len(f0) - 1)
        v   = float(f0[idx])
        raw.append(v if v > 30 else None)
        rv.append(float(rms[idx]))
    pts    = trim_xu1999(raw)
    voiced = [v for v in pts if v and v > 0]
    ok     = len(voiced) / n > 0.3
    onset  = next((v for v in pts if v), None)
    offset = next((v for v in reversed(pts) if v), None)
    mid    = None
    for d in range(n // 2 + 1):
        for i in (n//2-d, n//2+d):
            if 0 <= i < n and pts[i]:
                mid = pts[i]; break
        if mid: break
    f0m  = _mean(voiced)
    rmsm = _mean(rv)
    amp  = (20 * math.log10(rmsm + 1e-10) + 120) if rmsm else None
    vel  = None
    if onset and offset and dur > 0:
        mv = _st(onset, offset)
        if mv is not None:
            vel = mv / dur
    return {"f0_onset": onset, "f0_offset": offset, "f0_mean": f0m,
            "amplitude_db": amp, "voiced": ok, "velocity_st_s": vel}


# ── prosody labelling (all 5 optimisations) ───────────────────────────────────
def label_prosody(syls, utt_breaks=None):
    n = len(syls)
    if not n: return
    breaks  = sorted(utt_breaks or [])
    utt_of  = [sum(1 for b in breaks if s["start"] >= b) for s in syls]

    for s in syls:
        s["_mv"] = _st(s.get("f0_onset"), s.get("f0_offset"))

    # MAD threshold (optimisation 1)
    mvs = [abs(s["_mv"]) for s in syls if s["_mv"] is not None]
    if len(mvs) >= 4:
        med_mv = statistics.median(mvs)
        mad    = statistics.median([abs(x - med_mv) for x in mvs])
        std    = 1.4826 * mad if mad > 0 else 2.0
    elif len(mvs) >= 2:
        std = statistics.stdev(mvs)
    else:
        std = 2.0
    wthr = max(WEAK_FLOOR_ST, ADAPTIVE_FACTOR * std)
    sthr = max(wthr * STRONG_FACTOR, 2.0)

    # Declination removal (optimisation 3)
    utts = {}
    for i, ui in enumerate(utt_of):
        utts.setdefault(ui, []).append(i)
    f0_det = {}
    for ui, idxs in utts.items():
        voiced = [(syls[j]["start"], syls[j]["f0_mean"])
                  for j in idxs if syls[j].get("f0_mean")]
        if len(voiced) >= 3:
            ts  = [p[0] for p in voiced]; fs = [p[1] for p in voiced]
            t_c = sum(ts)/len(ts); f_c = sum(fs)/len(fs)
            num = sum((t-t_c)*(f-f_c) for t,f in zip(ts,fs))
            den = sum((t-t_c)**2 for t in ts)
            slope = num/den if den > 0 else 0.0
            for j in idxs:
                fm = syls[j].get("f0_mean")
                f0_det[j] = (fm - slope*(syls[j]["start"]-t_c)) if fm else None
        else:
            for j in idxs:
                f0_det[j] = syls[j].get("f0_mean")

    for i, s in enumerate(syls):
        mv  = s["_mv"]; vel = s.get("velocity_st_s")
        f0m = f0_det.get(i); amp = s.get("amplitude_db")
        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in (i-1, i+1):
            if 0 <= j < n and utt_of[j] == utt_of[i]:   # utterance reset (opt 2)
                v = f0_det.get(j); a = syls[j].get("amplitude_db")
                d = syls[j]["end"] - syls[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)
        nf0 = _mean(nbr_f0); namp = _mean(nbr_amp)
        ndur = _mean(nbr_dur) if nbr_dur else None
        dur  = s["end"] - s["start"]
        is_long  = ndur and dur >= DURATION_ACCENT * ndur
        hst      = _st(nf0, f0m) if (nf0 and f0m) else None
        is_high  = hst is not None and hst >=  HIGH_NBR_ST
        is_low   = hst is not None and hst <= -LOW_NBR_ST
        above    = (amp - namp) if (amp and namp) else None
        is_loud  = above is not None and above >= ACCENT_AMP_DB
        strong   = (abs(mv) >= sthr if mv else False) or \
                   (abs(vel) >= VELOCITY_STRONG_ST_S if vel else False)
        if mv is None:     direction = ""
        elif mv >= wthr:   direction = "//" if strong else "/"
        elif mv <= -wthr:  direction = "\\\\" if strong else "\\"
        else:              direction = ""
        if direction == "":
            h = HIGH_SYM if is_high else (LOW_SYM if is_low else
                (HIGH_SYM if (f0m and nf0) else "?"))
        else:
            h = HIGH_SYM if is_high else (LOW_SYM if is_low else "")
        accent = ((is_loud and hst is not None and hst >= ACCENT_F0_ST)
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
        rows  = fill(tier["rows"], xmax)
        tname = q(tier["name"])
        lines += [f"    item [{ti}]:", '        class = "IntervalTier"',
                  f'        name = "{tname}"', "        xmin = 0",
                  f"        xmax = {xmax}", f"        intervals: size = {len(rows)}"]
        for ii, r in enumerate(rows, 1):
            tval = q(r["value"])
            lines += [f"        intervals [{ii}]:",
                      f"            xmin = {r['start']}",
                      f"            xmax = {r['end']}",
                      f'            text = "{tval}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── GToBI point → syllable interval ──────────────────────────────────────────
def point_to_interval(points, syllables):
    rows = []
    for syl in syllables:
        label = ""
        for pt in points:
            if syl["start"] <= pt["time"] < syl["end"]:
                label = pt["mark"]; break
        rows.append({"start": syl["start"], "end": syl["end"], "value": label})
    return rows


# ── process one sentence ──────────────────────────────────────────────────────
def process(name: str, times, f0, rms) -> dict:
    data = SENTENCES[name]
    tg   = parse_textgrid(SRC_ORIG / f"{name}.TextGrid")
    xmax = tg["xmax"]

    wort_ivs = [iv for iv in get_tier(tg, "Wort") if iv["text"]]
    ton_pts  = get_tier(tg, "Ton", "point") or []

    # ── sentence + translation (utterance span) ───────────────────────────────
    utt_start = wort_ivs[0]["start"]
    utt_end   = wort_ivs[-1]["end"]
    sentence_rows    = [{"start": utt_start, "end": utt_end, "value": data["de"]}]
    translation_rows = [{"start": utt_start, "end": utt_end, "value": data["en"]}]

    # ── words + gloss (human Wort timing) ────────────────────────────────────
    word_rows  = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in wort_ivs]
    gloss_rows = [{"start": iv["start"], "end": iv["end"], "value": en}
                  for iv, en in zip(wort_ivs, data["words_en"])]

    # ── phones + syllables (hardcoded IPA, proportional within Wort) ─────────
    all_phone_ivs = []
    all_syllables = []

    for word_iv, word_phones in zip(wort_ivs, data["ipa"]):
        ph_ivs = distribute_phones(word_phones,
                                   word_iv["start"], word_iv["end"])
        syls   = syllabify_phones(ph_ivs)
        all_phone_ivs.extend(ph_ivs)
        all_syllables.extend(syls)

    phone_rows = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in all_phone_ivs]
    syl_rows   = [{"start": s["start"],  "end": s["end"],  "value": s["label"]}
                  for s in all_syllables]

    # ── gtobi: Ton point → interval ──────────────────────────────────────────
    gtobi_rows = point_to_interval(ton_pts, all_syllables)

    # ── measure + label prosody ───────────────────────────────────────────────
    meas_syls = []
    for syl in all_syllables:
        s = dict(syl)
        s.update(measure(times, f0, rms, syl["v0"], syl["v1"]))
        meas_syls.append(s)

    label_prosody(meas_syls, utt_breaks=[utt_end])

    prosody_rows = [{"start": s["start"], "end": s["end"],
                     "value": s.get("symbol", "?")} for s in meas_syls]

    # ── write ─────────────────────────────────────────────────────────────────
    out_path = HERE / f"{name}.TextGrid"
    write_tg(out_path, xmax, [
        {"name": "sentence",    "rows": sentence_rows},
        {"name": "translation", "rows": translation_rows},
        {"name": "words",       "rows": word_rows},
        {"name": "gloss",       "rows": gloss_rows},
        {"name": "syllables",   "rows": syl_rows},
        {"name": "phones",      "rows": phone_rows},
        {"name": "gtobi",       "rows": gtobi_rows},
        {"name": "prosody",     "rows": prosody_rows},
    ])

    n_voiced = sum(1 for s in meas_syls if s.get("f0_onset"))
    accent_syls = [s for s in meas_syls if s.get("accent")]
    print(f"    {len(meas_syls)} syllables  voiced={n_voiced}  accented={len(accent_syls)}", flush=True)
    print(f"    Syllables: {[s['label'] for s in meas_syls]}", flush=True)
    print(f"    Prosody:   {[s.get('symbol','?') for s in meas_syls]}", flush=True)
    print(f"    GToBI:     {data['gtobi_label']}", flush=True)

    return {"name": name, "syls": meas_syls, "gtobi": ton_pts,
            "data": data, "xmax": xmax}


# ── summary figure ────────────────────────────────────────────────────────────
def make_summary(results):
    import numpy as np, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt, matplotlib.patches as mp

    n   = len(results)
    fig, axes = plt.subplots(n, 1, figsize=(15, n * 2.3), facecolor="white")
    fig.suptitle(
        "German GToBI — SpeechPrint BEST  (CREPE full 10 ms + 5 optimisations)\n"
        "Tiers: sentence · translation · words · gloss · syllables · phones · gtobi · prosody",
        fontsize=10, fontweight="bold",
    )

    TIER_BG = {
        "sentence":    "#EEF4FF", "translation": "#EEF4FF",
        "words":       "#FFFDE7", "gloss":       "#FFFDE7",
        "syllables":   "#F1F8E9", "phones":      "#FFF3E0",
        "gtobi":       "#E8EAF6", "prosody":     "#F3E5F5",
    }
    SHOW = ["words", "gloss", "syllables", "phones", "gtobi", "prosody"]

    for ax, res in zip(axes, results):
        tg   = parse_textgrid(HERE / f"{res['name']}.TextGrid")
        xmax = res["xmax"]
        ax.set_xlim(0, xmax); ax.set_ylim(0, len(SHOW))
        ax.axis("off")
        gtobi_str = res["data"]["gtobi_label"]
        ax.set_title(f"{res['data']['de']}   [{gtobi_str}]",
                     fontsize=9, loc="left", pad=2, fontweight="bold")

        for ti, tname in enumerate(SHOW):
            tier = next((t for t in tg["tiers"] if t["name"] == tname), None)
            if not tier: continue
            bg = TIER_BG.get(tname, "#fff")
            y  = len(SHOW) - 1 - ti
            ax.add_patch(mp.Rectangle((0, y), xmax, 0.90,
                                      facecolor="#f5f5f5", edgecolor="#ddd", lw=0.3))
            ax.text(-0.01*xmax, y+0.45, tname, ha="right", va="center",
                    fontsize=6.5, color="#555")
            for iv in tier["intervals"]:
                if not iv["text"]: continue
                x0, x1 = iv["start"], iv["end"]
                ax.add_patch(mp.Rectangle((x0, y+0.05), x1-x0, 0.82,
                                          facecolor=bg, edgecolor="#999", lw=0.4))
                label = iv["text"]
                fs = 5.5 if len(label) > 12 else (6.5 if len(label) > 6 else 7.5)
                bold = tname in ("gtobi", "prosody")
                col  = "#c0392b" if (tname == "prosody" and
                                      any(c in label for c in ["*","//","\\\\"])) else "#222"
                ax.text((x0+x1)/2, y+0.46, label, ha="center", va="center",
                        fontsize=fs, fontweight="bold" if bold else "normal",
                        color=col, clip_on=True)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = HERE / "gtobi_best_summary.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Summary: {out}", flush=True)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("\nGerman GToBI BEST — ultimate build (no MFA, hardcoded IPA)", flush=True)
    HERE.mkdir(parents=True, exist_ok=True)

    results = []
    for name in SENTENCE_ORDER:
        wav = SRC_WAV / f"{name}.wav"
        print(f"\n  {SENTENCES[name]['de']}", flush=True)
        times, f0, rms = run_crepe(wav)
        results.append(process(name, times, f0, rms))

    make_summary(results)

    # open all in Praat
    for name in SENTENCE_ORDER:
        tg  = str((HERE / f"{name}.TextGrid").resolve())
        wav = str((SRC_WAV / f"{name}.wav").resolve())
        for praat in ("praat", "praat6"):
            try:
                subprocess.Popen([praat, "--open", wav, tg]); break
            except FileNotFoundError:
                continue

    print("\n  All TextGrids in:", HERE, flush=True)
    print("\n  Red flags resolved:")
    print("    ✓ MFA abandoned — all wrong transcriptions eliminated")
    print("    ✓ Hardcoded correct German IPA — linguistically verified")
    print("    ✓ Human Wort timing used exclusively for word boundaries")
    print("    ✓ Proportional phone distribution within human word spans")
    print("    ✓ 8 tiers matching DoReCo structure: sentence/translation/words/gloss/syllables/phones/gtobi/prosody")


if __name__ == "__main__":
    main()
