#!/usr/bin/env python3
"""Rebuild all four corpora with the optimal tracker + all 5 optimisations.

Tracker choices (matching the two-pipeline thesis conclusion):
  Daakie   → CREPE  (already done in DORECO_BEST — just copied)
  Cabécar  → CREPE  (already done in out/cabeca_best.TextGrid — just copied)
  GToBI    → pYIN   (pYIN scored 3/5 correct vs CREPE 1/5 on short clean sentences)
  English  → pYIN   (clean studio speech; pYIN reliable on non-endangered audio)

5 optimisations applied to all:
  1. MAD-based adaptive threshold
  2. Utterance boundary reset
  3. Pitch declination removal
  4. Nucleus edge trimming (15%)
  5. Octave recovery in spike removal

Outputs written to FINAL_QUESTIONNAIRE_2026-06-07/ (overwrites placeholders).
"""

from __future__ import annotations
import math, re, shutil, statistics
from pathlib import Path

ROOT = Path(__file__).parent.parent
HERE = Path(__file__).parent
Q_OUT = ROOT / "FINAL_QUESTIONNAIRE_2026-06-07"
C_OUT = ROOT / "TRACKER_COMPARISON_2026-06-07"

# ── algorithm constants ───────────────────────────────────────────────────────
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

GERMAN_VOWELS = {
    "a","aː","ɛ","ɛː","e","eː","i","iː","ɪ","o","oː","ɔ","u","uː","ʊ",
    "y","yː","ʏ","ø","øː","œ","ə","ɐ","aɪ","aʊ","ɔʏ","ɛɐ",
}

SENTENCES = {
    "eine_gelbe_banane": {
        "de": "eine gelbe Banane", "en": "a yellow banana",
        "words_de": ["eine","gelbe","Banane"],
        "words_en": ["a","yellow","banana"],
        "ipa": [["aɪ","n","ə"],["ɡ","ɛ","l","b","ə"],["b","a","n","aː","n","ə"]],
    },
    "einige_melonen": {
        "de": "einige Melonen", "en": "some melons",
        "words_de": ["einige","Melonen"],
        "words_en": ["some","melons"],
        "ipa": [["aɪ","n","ɪ","ɡ","ə"],["m","e","l","oː","n","ə","n"]],
    },
    "er_sang_die_lieder": {
        "de": "er sang die Lieder", "en": "he sang the songs",
        "words_de": ["er","sang","die","Lieder"],
        "words_en": ["he","sang","the","songs"],
        "ipa": [["ɛɐ"],["z","a","ŋ"],["d","iː"],["l","iː","d","ɐ"]],
    },
    "er_will_die_rosen_haben": {
        "de": "er will die Rosen haben", "en": "he wants to have the roses",
        "words_de": ["er","will","die","Rosen","haben"],
        "words_en": ["he","wants","the","roses","to have"],
        "ipa": [["ɛɐ"],["v","ɪ","l"],["d","iː"],["r","oː","z","ə","n"],["h","aː","b","ə","n"]],
    },
    "ich_wohne_in_bern": {
        "de": "ich wohne in Bern", "en": "I live in Bern",
        "words_de": ["ich","wohne","in","Bern"],
        "words_en": ["I","live","in","Bern"],
        "ipa": [["ɪ","ç"],["v","oː","n","ə"],["ɪ","n"],["b","ɛ","r","n"]],
    },
}
SENTENCE_ORDER = ["eine_gelbe_banane","einige_melonen","er_sang_die_lieder",
                  "er_will_die_rosen_haben","ich_wohne_in_bern"]


# ── TextGrid I/O ──────────────────────────────────────────────────────────────
def parse_tg(path):
    text = path.read_text(encoding="utf-8")
    xmax = float(re.search(r"xmax = ([\d.]+)", text, re.M).group(1))
    tiers = []
    for block in re.split(r"\n\s*item \[\d+\]:", text)[1:]:
        nm  = re.search(r'name = "([^"]*)"', block)
        cls = re.search(r'class = "([^"]*)"', block)
        if not nm or not cls: continue
        if "Interval" in cls.group(1):
            ivs = []
            for iv in re.split(r"\n\s*intervals \[\d+\]:", block)[1:]:
                a = re.search(r"xmin = ([\d.]+)", iv)
                b = re.search(r"xmax = ([\d.]+)", iv)
                c = re.search(r'text = "([^"]*)"', iv, re.DOTALL)
                if a and b and c:
                    ivs.append({"start":float(a.group(1)),"end":float(b.group(1)),"text":c.group(1)})
            tiers.append({"name":nm.group(1),"class":"interval","intervals":ivs})
        elif "Text" in cls.group(1):
            pts = []
            for pt in re.split(r"\n\s*points \[\d+\]:", block)[1:]:
                n = re.search(r"number = ([\d.]+)", pt)
                m = re.search(r'mark = "([^"]*)"', pt)
                if n and m: pts.append({"time":float(n.group(1)),"mark":m.group(1)})
            tiers.append({"name":nm.group(1),"class":"point","points":pts})
    return {"xmax": xmax, "tiers": tiers}

def get_tier(tg, name, cls="interval"):
    for t in tg["tiers"]:
        if t["name"] == name and t.get("class") == cls:
            return t.get("intervals") or t.get("points")
    return None

def get_tier_any(tg, *names):
    for name in names:
        for t in tg["tiers"]:
            if t["name"] == name:
                return t.get("intervals") or t.get("points")
    return None

def fill(rows, xmax):
    out, cur = [], 0.0
    for r in sorted(rows, key=lambda x: x["start"]):
        s, e = float(r["start"]), float(r["end"])
        if s > cur + 5e-4: out.append({"start":cur,"end":s,"value":""})
        out.append({"start":s,"end":e,"value":r.get("value","")})
        cur = max(cur, e)
    if cur < xmax - 5e-4: out.append({"start":cur,"end":xmax,"value":""})
    return out

def write_tg(path, xmax, tiers):
    def q(t): return str(t).replace('"',"'")
    lines = ['File type = "ooTextFile"','Object class = "TextGrid"',"",
             "xmin = 0",f"xmax = {xmax}","tiers? <exists>",
             f"size = {len(tiers)}","item []:"]
    for ti, tier in enumerate(tiers, 1):
        rows = fill(tier["rows"], xmax)
        lines += [f"    item [{ti}]:",'        class = "IntervalTier"',
                  f'        name = "{q(tier["name"])}"',"        xmin = 0",
                  f"        xmax = {xmax}",f"        intervals: size = {len(rows)}"]
        for ii, r in enumerate(rows, 1):
            lines += [f"        intervals [{ii}]:",
                      f"            xmin = {r['start']}",
                      f"            xmax = {r['end']}",
                      f'            text = "{q(r["value"])}"']
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"    written: {path.name}", flush=True)


# ── maths ─────────────────────────────────────────────────────────────────────
def _st(a, b):
    if not a or not b or a <= 0 or b <= 0: return None
    return 12.0 * math.log2(b / a)

def _mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs)/len(xs) if xs else None

def trim_xu(vals):
    voiced = [v for v in vals if v and v > 0]
    if len(voiced) < 2: return list(vals)
    med = statistics.median(voiced)
    tr = []
    for v in vals:
        if not v or v <= 0: tr.append(v); continue
        if abs(_st(med,v) or 0) <= SPIKE_ST:
            tr.append(v)
        else:
            cands = [v*2, v/2]
            best = min(cands, key=lambda c: abs(_st(med,c) or float("inf")))
            tr.append(best if abs(_st(med,best) or 0) < SPIKE_ST else None)
    n, sm = len(tr), list(tr)
    for i in range(1, n-1):
        a, b, c = tr[i-1], tr[i], tr[i+1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            sm[i] = (a + 2*b + c) / 4
    return sm


# ── pYIN tracker ──────────────────────────────────────────────────────────────
def run_pyin(y, sr, fmin=65.0, fmax=500.0):
    import numpy as np, librosa
    hop = 256
    f0r, vf, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                               frame_length=2048, hop_length=hop)
    times = librosa.frames_to_time(range(len(f0r)), sr=sr, hop_length=hop)
    f0 = np.where(vf & ~np.isnan(f0r), f0r, 0.0)
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    rms = librosa.util.fix_length(rms, size=len(f0))
    print(f"    pYIN: {int(np.sum(f0>30))} voiced frames", flush=True)
    return times, f0, rms


# ── nucleus measurement ───────────────────────────────────────────────────────
def measure(times, f0, rms, t0, t1, n=10):
    import numpy as np
    dur = t1 - t0
    empty = {"f0_onset":None,"f0_offset":None,"f0_mean":None,
             "amplitude_db":None,"voiced":False,"velocity_st_s":None}
    if dur < 0.010: return empty
    margin = EDGE_TRIM * dur
    t0s, t1s = t0 + margin, t1 - margin
    if t1s - t0s < 0.010: t0s, t1s = t0, t1
    ts = [t0s + (t1s-t0s)*j/(n-1) for j in range(n)]
    raw, rv = [], []
    for t in ts:
        idx = min(int(np.searchsorted(times, t)), len(f0)-1)
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
    amp    = (20*math.log10(rmsm+1e-10)+120) if rmsm else None
    vel    = None
    if onset and offset and dur > 0:
        mv = _st(onset, offset)
        if mv is not None: vel = mv / dur
    return {"f0_onset":onset,"f0_offset":offset,"f0_mean":f0m,
            "amplitude_db":amp,"voiced":ok,"velocity_st_s":vel}


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
        mad    = statistics.median([abs(x-med_mv) for x in mvs])
        std    = 1.4826*mad if mad > 0 else 2.0
    elif len(mvs) >= 2:
        std = statistics.stdev(mvs)
    else:
        std = 2.0
    wthr = max(WEAK_FLOOR, ALPHA*std)
    sthr = max(wthr*STRONG_F, 2.0)
    utts = {}
    for i, ui in enumerate(utt_of): utts.setdefault(ui,[]).append(i)
    f0_det = {}
    for ui, idxs in utts.items():
        voiced = [(syls[j]["start"],syls[j]["f0_mean"])
                  for j in idxs if syls[j].get("f0_mean")]
        if len(voiced) >= 3:
            ts=[p[0] for p in voiced]; fs=[p[1] for p in voiced]
            tc=sum(ts)/len(ts); fc=sum(fs)/len(fs)
            num=sum((t-tc)*(f-fc) for t,f in zip(ts,fs))
            den=sum((t-tc)**2 for t in ts)
            slope=num/den if den > 0 else 0.0
            for j in idxs:
                fm=syls[j].get("f0_mean")
                f0_det[j]=(fm-slope*(syls[j]["start"]-tc)) if fm else None
        else:
            for j in idxs: f0_det[j]=syls[j].get("f0_mean")
    for i, s in enumerate(syls):
        mv=s["_mv"]; vel=s.get("velocity_st_s")
        f0m=f0_det.get(i); amp=s.get("amplitude_db")
        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in (i-1, i+1):
            if 0 <= j < n and utt_of[j] == utt_of[i]:
                v=f0_det.get(j); a=syls[j].get("amplitude_db")
                d=syls[j]["end"]-syls[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)
        nf0=_mean(nbr_f0); namp=_mean(nbr_amp)
        ndur=_mean(nbr_dur) if nbr_dur else None
        dur=s["end"]-s["start"]
        is_long  = ndur and dur >= DUR_F*ndur
        hst      = _st(nf0,f0m) if (nf0 and f0m) else None
        is_high  = hst is not None and hst >=  HIGH_ST
        is_low   = hst is not None and hst <= -LOW_ST
        above    = (amp-namp) if (amp and namp) else None
        is_loud  = above is not None and above >= AMP_DB
        strong   = (abs(mv) >= sthr if mv else False) or \
                   (abs(vel) >= VEL_ST_S if vel else False)
        if mv is None:    direction=""
        elif mv >=  wthr: direction="//" if strong else "/"
        elif mv <= -wthr: direction="\\\\" if strong else "\\"
        else:             direction=""
        if direction == "":
            h=HIGH_SYM if is_high else (LOW_SYM if is_low else
              (HIGH_SYM if (f0m and nf0) else "?"))
        else:
            h=HIGH_SYM if is_high else (LOW_SYM if is_low else "")
        accent=((is_loud and hst is not None and hst >= F0_ST)
                or (is_long and is_loud and is_high))
        sym=("*" if accent else "")+(h+direction if h else direction) or \
            ("?" if not f0m else HIGH_SYM)
        s["symbol"]=sym; s["accent"]=accent


# ── GToBI helpers ─────────────────────────────────────────────────────────────
def distribute_phones(phones, t0, t1):
    weights = [1.5 if p in GERMAN_VOWELS else 1.0 for p in phones]
    total = sum(weights)
    ivs, t = [], t0
    for ph, w in zip(phones, weights):
        dur = (t1-t0)*w/total
        ivs.append({"start":t,"end":t+dur,"text":ph})
        t += dur
    if ivs: ivs[-1]["end"] = t1
    return ivs

def syllabify_phones(phone_ivs, vowels):
    phones = [iv["text"] for iv in phone_ivs]
    n = len(phones)
    if not n: return []
    vids = [i for i,p in enumerate(phones) if p in vowels]
    if not vids:
        s, e = phone_ivs[0]["start"], phone_ivs[-1]["end"]
        return [{"start":s,"end":e,"label":"".join(phones),"v0":s,"v1":e}]
    bounds = []
    for k, vi in enumerate(vids):
        onset = 0 if k == 0 else vids[k-1]+1+(vi-vids[k-1]-1)//2
        if bounds and k > 0: bounds[-1]=(bounds[-1][0],onset)
        bounds.append((onset, n if k==len(vids)-1 else vi+1))
    out = []
    for ps, pe in bounds:
        ivs=phone_ivs[ps:pe]; s,e=ivs[0]["start"],ivs[-1]["end"]
        vi=[iv for iv in ivs if iv["text"] in vowels]
        out.append({"start":s,"end":e,"label":"".join(phones[ps:pe]),
                    "v0":vi[0]["start"] if vi else s,
                    "v1":vi[-1]["end"]  if vi else e})
    return out


# ── sentence-level grouping (for English utterance breaks) ───────────────────
def sentences_from_words(word_ivs, gap=0.35):
    words = [iv for iv in word_ivs if iv["text"] and not iv["text"].startswith("<sil")]
    if not words: return []
    groups, grp = [], [words[0]]
    for w in words[1:]:
        if w["start"] - grp[-1]["end"] >= gap:
            groups.append(grp); grp = [w]
        else:
            grp.append(w)
    if grp: groups.append(grp)
    return [{"start":g[0]["start"],"end":g[-1]["end"],
             "text":" ".join(w["text"] for w in g)} for g in groups]


# ── questionnaire row helper ──────────────────────────────────────────────────
def rows(ivs): return [{"start":iv["start"],"end":iv["end"],"value":iv.get("text",iv.get("value",""))} for iv in (ivs or [])]
def empty(xmax): return [{"start":0.0,"end":xmax,"value":""}]


# ══════════════════════════════════════════════════════════════════════════════
# 1. GToBI — pYIN + 5 opt
# ══════════════════════════════════════════════════════════════════════════════
def build_gtobi_pyin():
    import librosa
    SRC_TG  = HERE / " five GToBI annotated sentences"
    SRC_WAV = ROOT / "ideasss" / "SpeechPrint_results" / "german_gtobi"
    OUT_DIR = HERE / "out" / "gtobi_pyin"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nGToBI — pYIN + 5 opt", flush=True)
    for name in SENTENCE_ORDER:
        print(f"  {name}", flush=True)
        wav_path = SRC_WAV / f"{name}.wav"
        tg_src   = SRC_TG  / f"{name}.TextGrid"

        y, sr = librosa.load(str(wav_path), sr=None, mono=True)
        # auto pitch range
        import numpy as np
        f0r, vf, _ = librosa.pyin(y, fmin=65, fmax=500, sr=sr,
                                   frame_length=2048, hop_length=256)
        voiced_hz = f0r[vf & ~np.isnan(f0r)] if vf is not None else np.array([])
        if len(voiced_hz) > 3:
            med = float(np.median(voiced_hz))
            fmin_u = max(50.0, med*0.5); fmax_u = min(600.0, med*2.5)
        else:
            fmin_u, fmax_u = 65.0, 500.0
        times, f0, rms = run_pyin(y, sr, fmin_u, fmax_u)

        tg   = parse_tg(tg_src)
        xmax = tg["xmax"]
        data = SENTENCES[name]

        wort = [iv for iv in (get_tier(tg,"Wort") or []) if iv["text"]]
        ton  = get_tier(tg,"Ton","point") or []

        utt_s, utt_e = wort[0]["start"], wort[-1]["end"]
        sentence_rows    = [{"start":utt_s,"end":utt_e,"value":data["de"]}]
        translation_rows = [{"start":utt_s,"end":utt_e,"value":data["en"]}]
        word_rows        = [{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in wort]

        all_phones, all_syls = [], []
        for word_iv, phones in zip(wort, data["ipa"]):
            ph_ivs = distribute_phones(phones, word_iv["start"], word_iv["end"])
            syls   = syllabify_phones(ph_ivs, GERMAN_VOWELS)
            all_phones.extend(ph_ivs); all_syls.extend(syls)

        phone_rows = [{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in all_phones]
        syl_rows   = [{"start":s["start"], "end":s["end"], "value":s["label"]}  for s in all_syls]

        # gtobi points → intervals
        gtobi_rows = []
        for syl in all_syls:
            label = next((pt["mark"] for pt in ton
                          if syl["start"] <= pt["time"] < syl["end"]), "")
            gtobi_rows.append({"start":syl["start"],"end":syl["end"],"value":label})

        meas = []
        for syl in all_syls:
            s = dict(syl)
            s.update(measure(times, f0, rms, syl["v0"], syl["v1"]))
            meas.append(s)
        label_prosody(meas, utt_breaks=[utt_e])

        pros_rows = [{"start":s["start"],"end":s["end"],"value":s.get("symbol","?")} for s in meas]

        # 8-tier full version (for GTOBI_BEST equivalent)
        write_tg(OUT_DIR / f"{name}.TextGrid", xmax, [
            {"name":"sentence",    "rows":sentence_rows},
            {"name":"translation", "rows":translation_rows},
            {"name":"words",       "rows":word_rows},
            {"name":"syllables",   "rows":syl_rows},
            {"name":"phones",      "rows":phone_rows},
            {"name":"gtobi",       "rows":gtobi_rows},
            {"name":"prosody",     "rows":pros_rows},
        ])

        # 6-tier questionnaire version (no gtobi)
        write_tg(OUT_DIR / f"{name}_questionnaire.TextGrid", xmax, [
            {"name":"sentence",    "rows":sentence_rows},
            {"name":"words",       "rows":word_rows},
            {"name":"translation", "rows":translation_rows},
            {"name":"syllables",   "rows":syl_rows},
            {"name":"phones",      "rows":phone_rows},
            {"name":"prosody",     "rows":pros_rows},
        ])


# ══════════════════════════════════════════════════════════════════════════════
# 2. English — pYIN + 5 opt (uses existing word/syllable/phone timing)
# ══════════════════════════════════════════════════════════════════════════════
def build_english_pyin():
    import librosa, numpy as np
    src_tg  = HERE / "out" / "questionaire_2026-06-02" / "english" / \
              "audio_2026-05-30_19-01-35.TextGrid"
    wav_path = HERE / "audio_2026-05-30_19-01-35.wav"
    out_path = HERE / "out" / "english_pyin_opt.TextGrid"

    print("\nEnglish — pYIN + 5 opt", flush=True)
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)

    # auto pitch range
    scan = y[:int(20*sr)]
    f0r, vf, _ = librosa.pyin(scan, fmin=65, fmax=500, sr=sr,
                               frame_length=2048, hop_length=256)
    voiced_hz = f0r[vf & ~np.isnan(f0r)] if vf is not None else np.array([])
    if len(voiced_hz) > 10:
        med = float(np.median(voiced_hz))
        fmin_u = max(50.0, med*0.5); fmax_u = min(600.0, med*2.5)
    else:
        fmin_u, fmax_u = 65.0, 400.0
    print(f"  Pitch range: {fmin_u:.0f}–{fmax_u:.0f} Hz", flush=True)

    times, f0, rms = run_pyin(y, sr, fmin_u, fmax_u)

    tg   = parse_tg(src_tg)
    xmax = tg["xmax"]

    word_ivs  = get_tier_any(tg, "words") or []
    syl_ivs   = get_tier_any(tg, "syllables") or []
    phone_ivs = get_tier_any(tg, "phonemes", "phones") or []

    # sentence tier from word groupings
    sent_groups = sentences_from_words(word_ivs)
    sentence_rows = [{"start":g["start"],"end":g["end"],"value":g["text"]} for g in sent_groups]
    utt_breaks    = [g["end"] for g in sent_groups]

    # measure each syllable (use syllable span as nucleus; edge trim handles consonants)
    syls = []
    for iv in syl_ivs:
        if not iv["text"] or iv["text"].startswith("<"): continue
        s = {"start":iv["start"],"end":iv["end"],"label":iv["text"],
             "v0":iv["start"],"v1":iv["end"]}
        s.update(measure(times, f0, rms, iv["start"], iv["end"]))
        syls.append(s)

    label_prosody(syls, utt_breaks=utt_breaks)
    pros_rows = [{"start":s["start"],"end":s["end"],"value":s.get("symbol","?")} for s in syls]

    write_tg(out_path, xmax, [
        {"name":"sentence",    "rows":sentence_rows},
        {"name":"words",       "rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in word_ivs]},
        {"name":"translation", "rows":empty(xmax)},
        {"name":"syllables",   "rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in syl_ivs]},
        {"name":"phones",      "rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in phone_ivs]},
        {"name":"prosody",     "rows":pros_rows},
    ])
    print(f"  Syllables labelled: {len(syls)}  Utterances: {len(sent_groups)}", flush=True)
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# 3. Update FINAL_QUESTIONNAIRE folder
# ══════════════════════════════════════════════════════════════════════════════
def update_questionnaire():
    print("\nUpdating FINAL_QUESTIONNAIRE_2026-06-07…", flush=True)

    # GToBI — copy pYIN questionnaire TGs + regenerate videos
    gtobi_src = HERE / "out" / "gtobi_pyin"
    gtobi_out = Q_OUT / "german_gtobi"
    gtobi_out.mkdir(parents=True, exist_ok=True)
    for name in SENTENCE_ORDER:
        src = gtobi_src / f"{name}_questionnaire.TextGrid"
        if src.exists():
            shutil.copy(src, gtobi_out / f"{name}.TextGrid")
            print(f"  GToBI: {name}.TextGrid", flush=True)

    # English
    eng_src = HERE / "out" / "english_pyin_opt.TextGrid"
    eng_out = Q_OUT / "english"
    eng_out.mkdir(parents=True, exist_ok=True)
    if eng_src.exists():
        shutil.copy(eng_src, eng_out / "english.TextGrid")
        print(f"  English: english.TextGrid", flush=True)

    # Cabécar (already built)
    cab_src  = HERE / "out" / "cabeca_best.TextGrid"
    cab_wav  = HERE / "doreco_cabeca.wav"
    cab_out  = Q_OUT / "cabeca"
    cab_out.mkdir(parents=True, exist_ok=True)
    if cab_src.exists():
        shutil.copy(cab_src, cab_out / "cabeca.TextGrid")
        if cab_wav.exists(): shutil.copy(cab_wav, cab_out / cab_wav.name)
        print(f"  Cabécar: cabeca.TextGrid", flush=True)

    # Daakie (already best)
    daakie_src = ROOT / "DORECO_BEST" / "doreco_best.TextGrid"
    daakie_wav = HERE / "doreco_port1286_2017_06_30_Jaklin.wav"
    daakie_out = Q_OUT / "daakie"
    daakie_out.mkdir(parents=True, exist_ok=True)
    if daakie_src.exists():
        shutil.copy(daakie_src, daakie_out / "daakie.TextGrid")
        if daakie_wav.exists(): shutil.copy(daakie_wav, daakie_out / daakie_wav.name)
        print(f"  Daakie: daakie.TextGrid", flush=True)

    # Update comparison folder with new GToBI pYIN prosody
    gtobi_cmp = C_OUT / "german_gtobi"
    gtobi_cmp.mkdir(parents=True, exist_ok=True)
    gtobi_src_dir = HERE / "out" / "gtobi_pyin"
    for name in SENTENCE_ORDER:
        full_src = gtobi_src_dir / f"{name}.TextGrid"
        if not full_src.exists(): continue
        tg   = parse_tg(full_src)
        xmax = tg["xmax"]
        base = [{"name":t["name"],"rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in t["intervals"]]}
                for t in tg["tiers"] if t["name"] in ("sentence","words","translation","syllables","phones")]
        gtobi_tier = next((t for t in tg["tiers"] if t["name"]=="gtobi"), None)
        pros_tier  = next((t for t in tg["tiers"] if t["name"]=="prosody"), None)
        tracker_tiers = [
            {"name":"prosody_crepe","rows":empty(xmax)},
            {"name":"prosody_pyin", "rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in pros_tier["intervals"]] if pros_tier else empty(xmax)},
            {"name":"prosody_yin",  "rows":empty(xmax)},
            {"name":"prosody_praat","rows":empty(xmax)},
            {"name":"prosody_pesto","rows":empty(xmax)},
        ]
        if gtobi_tier:
            base.append({"name":"gtobi","rows":[{"start":iv["start"],"end":iv["end"],"value":iv["text"]} for iv in gtobi_tier["intervals"]]})
        write_tg(gtobi_cmp / f"{name}_comparison.TextGrid", xmax, base + tracker_tiers)

    print("\nAll done.", flush=True)


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    build_gtobi_pyin()
    build_english_pyin()
    update_questionnaire()
