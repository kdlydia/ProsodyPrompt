#!/usr/bin/env python3
"""DoReCo Daakie — best-quality SpeechPrint.

F0 tracker : CREPE full model (Kim et al. 2018, NYU), 10 ms hop, batch_size=128
             + Xu (1999) spike trimming + ProsodyPro-style relative labelling
Tier source : all human-annotated from DoReCo (no ASR, no computed words/syllables)

Output: DORECO_BEST/doreco_best.TextGrid  +  DORECO_BEST/doreco_best.mp4
"""

from __future__ import annotations

import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
HERE    = Path(__file__).parent
SRC_DIR = HERE.parent / "linux"
TG_IN   = SRC_DIR / "doreco_port1286_2017_06_30_Jaklin.TextGrid"
WAV_IN  = SRC_DIR / "doreco_port1286_2017_06_30_Jaklin.wav"
TG_OUT  = HERE / "doreco_best.TextGrid"
VID_OUT = HERE / "doreco_best.mp4"

# ── constants ─────────────────────────────────────────────────────────────────
DAAKIE_VOWELS = {"a","a:","e:","E","E:","i","i:","O","O:","o","u","u:","{"}
SKIP_LABELS   = {"<p:>","<<fp>>","<<fs>>","<<ui>>","<<ui>gon>","****"}

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

HIGH_SYM = "‾"   # U+203E overline  (opposite of underscore)
LOW_SYM  = "_"


# ── TextGrid parser ───────────────────────────────────────────────────────────
def parse_textgrid(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    xmax = float(re.search(r"^xmax = ([\d.]+)", text, re.M).group(1))
    tiers = []
    for block in re.split(r"\n\s*item \[\d+\]:", text)[1:]:
        nm = re.search(r'name = "([^"]*)"', block)
        if not nm:
            continue
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
        if t["name"] == name:
            return t["intervals"]
    return None


# ── maths helpers ─────────────────────────────────────────────────────────────
def _st(a, b):
    if not a or not b or a <= 0 or b <= 0:
        return None
    return 12.0 * math.log2(b / a)

def _mean(xs):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else None

def trim_xu1999(vals):
    """Xu (1999) spike removal with octave recovery.

    Before dropping an outlier frame, try its octave alternatives (×2, ÷2).
    If one of those is within SPIKE_ST of the median, use it instead of None.
    This recovers data points rather than discarding them.
    """
    voiced = [v for v in vals if v and v > 0]
    if len(voiced) < 2:
        return list(vals)
    med = statistics.median(voiced)
    tr = []
    for v in vals:
        if not v or v <= 0:
            tr.append(v)
            continue
        dev = abs(_st(med, v) or 0)
        if dev <= SPIKE_ST:
            tr.append(v)
        else:
            # octave recovery: try ×2 and ÷2
            cands = [v * 2, v / 2]
            best  = min(cands, key=lambda c: abs(_st(med, c) or float("inf")))
            tr.append(best if abs(_st(med, best) or 0) < SPIKE_ST else None)
    n = len(tr)
    sm = list(tr)
    for i in range(1, n - 1):
        a, b, c = tr[i-1], tr[i], tr[i+1]
        if a and b and c and a > 0 and b > 0 and c > 0:
            sm[i] = (a + 2*b + c) / 4
    return sm


# ── CREPE (torchcrepe, full model, 10 ms hop) ─────────────────────────────────
def run_crepe(wav_path: Path, fmin=65.0, fmax=500.0):
    import numpy as np, librosa, torch, torchcrepe

    print("  Loading audio + running CREPE (full, 10 ms hop)…", flush=True)
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    y16   = librosa.resample(y, orig_sr=sr, target_sr=16000)
    sr16  = 16000
    hop   = 160    # 10 ms at 16 kHz

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

    print(f"  CREPE: {int(np.sum(f0 > 30))} voiced frames  sr={sr16}  hop={hop}",
          flush=True)
    return times, f0, rms, y, sr


# ── nucleus measurement ───────────────────────────────────────────────────────
EDGE_TRIM = 0.15  # fraction to discard from each end of nucleus window

def measure(times, f0, rms, t0, t1, n=10):
    """Measure F0 and amplitude in a vowel nucleus window.

    Edge trimming: the outer EDGE_TRIM fraction at each end is skipped before
    sampling. Consonant-to-vowel and vowel-to-consonant transitions contaminate
    the first and last ~10-15 ms of the window; trimming them gives cleaner
    onset and offset estimates.
    """
    import numpy as np
    dur = t1 - t0
    if dur < 0.010:
        return {"f0_onset": None, "f0_offset": None, "f0_mean": None,
                "amplitude_db": None, "voiced": False, "velocity_st_s": None}
    # Trim edges; fall back to full window if nucleus is very short
    margin = EDGE_TRIM * dur
    t0s = t0 + margin
    t1s = t1 - margin
    if t1s - t0s < 0.010:
        t0s, t1s = t0, t1
    ts = [t0s + (t1s - t0s) * j / (n - 1) for j in range(n)]
    raw, rv = [], []
    for t in ts:
        idx = min(int(np.searchsorted(times, t)), len(f0) - 1)
        v = float(f0[idx])
        raw.append(v if v > 30 else None)
        rv.append(float(rms[idx]))
    pts    = trim_xu1999(raw)
    voiced = [v for v in pts if v and v > 0]
    ok     = len(voiced) / n > 0.3
    onset  = next((v for v in pts if v), None)
    offset = next((v for v in reversed(pts) if v), None)
    mid    = None
    for d in range(n // 2 + 1):
        for i in (n // 2 - d, n // 2 + d):
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


# ── syllabification ───────────────────────────────────────────────────────────
def syllabify(phone_ivs):
    phones = [iv["text"] for iv in phone_ivs]
    n = len(phones)
    if not n: return []
    vids = [i for i, p in enumerate(phones) if p in DAAKIE_VOWELS]
    if not vids:
        s, e = phone_ivs[0]["start"], phone_ivs[-1]["end"]
        return [{"start": s, "end": e, "label": "".join(phones),
                 "v0": s, "v1": e}]
    bounds = []
    for k, vi in enumerate(vids):
        onset = 0 if k == 0 else (
            vids[k-1] + 1 + (vi - vids[k-1] - 1) // 2)
        if bounds and k > 0:
            bounds[-1] = (bounds[-1][0], onset)
        bounds.append((onset, n if k == len(vids)-1 else vi + 1))
    out = []
    for ps, pe in bounds:
        ivs = phone_ivs[ps:pe]
        s, e = ivs[0]["start"], ivs[-1]["end"]
        vi  = [iv for iv in ivs if iv["text"] in DAAKIE_VOWELS]
        out.append({"start": s, "end": e,
                    "label": "".join(phones[ps:pe]),
                    "v0": vi[0]["start"] if vi else s,
                    "v1": vi[-1]["end"]  if vi else e})
    return out


# ── prosody labelling ─────────────────────────────────────────────────────────
def label_prosody(syls, utt_breaks=None):
    """Label prosody with four algorithmic improvements over the baseline:

    1. MAD threshold  — replaces std for adaptive thresholds. Std is pulled by
       extreme outlier movements; MAD (× 1.4826 for Gaussian equivalence) is the
       robust alternative taught in robust statistics courses. Effect: fewer
       syllables classified as 'strong' when a handful of very fast movements
       inflate the variance.

    2. Utterance boundary reset — neighbours across an utterance boundary are
       excluded from the height and amplitude comparisons. The last syllable of
       an utterance is systematically low (final lowering); comparing it to the
       first syllable of the next utterance (which resets high) produces false
       height contrasts.

    3. Declination removal — within each utterance, a linear regression is fit
       to the sequence of f0_mean values as a function of time. The slope is
       subtracted before the height comparison. This removes the natural
       downward drift of F0 over an utterance (declination), which otherwise
       systematically inflates the 'falling' label count.

    4. Nucleus edge trimming — already applied in measure(); noted here for
       completeness: the outer 15% of the nucleus window is discarded before
       sampling, reducing consonant-transition contamination at onset/offset.
    """
    n = len(syls)
    if not n:
        return

    # ── Assign utterance index ────────────────────────────────────────────────
    breaks = sorted(utt_breaks) if utt_breaks else []
    utt_of = []
    for s in syls:
        utt_of.append(sum(1 for b in breaks if s["start"] >= b))

    # ── Pitch movements ───────────────────────────────────────────────────────
    for s in syls:
        s["_mv"] = _st(s.get("f0_onset"), s.get("f0_offset"))

    # ── MAD-based adaptive threshold (improvement 1) ──────────────────────────
    mvs = [abs(s["_mv"]) for s in syls if s["_mv"] is not None]
    if len(mvs) >= 4:
        med_mv = statistics.median(mvs)
        mad    = statistics.median([abs(x - med_mv) for x in mvs])
        std    = 1.4826 * mad if mad > 0 else 2.0   # normalised MAD ≈ σ
    elif len(mvs) >= 2:
        std = statistics.stdev(mvs)
    else:
        std = 2.0
    wthr = max(WEAK_FLOOR_ST, ADAPTIVE_FACTOR * std)
    sthr = max(wthr * STRONG_FACTOR, 2.0)

    # ── Declination removal per utterance (improvement 3) ────────────────────
    utts = {}
    for i, ui in enumerate(utt_of):
        utts.setdefault(ui, []).append(i)

    f0_det = {}   # detrended f0_mean, keyed by syllable index
    for ui, idxs in utts.items():
        voiced = [(syls[j]["start"], syls[j]["f0_mean"])
                  for j in idxs if syls[j].get("f0_mean")]
        if len(voiced) >= 3:
            ts  = [p[0] for p in voiced]
            fs  = [p[1] for p in voiced]
            t_c = sum(ts) / len(ts)
            f_c = sum(fs) / len(fs)
            num = sum((t - t_c) * (f - f_c) for t, f in zip(ts, fs))
            den = sum((t - t_c) ** 2 for t in ts)
            slope = num / den if den > 0 else 0.0
            for j in idxs:
                fm = syls[j].get("f0_mean")
                # subtract trend; keep mean level (add f_c back)
                f0_det[j] = (fm - slope * (syls[j]["start"] - t_c)) if fm else None
        else:
            for j in idxs:
                f0_det[j] = syls[j].get("f0_mean")

    # ── Per-syllable labelling ────────────────────────────────────────────────
    for i, s in enumerate(syls):
        mv  = s["_mv"]
        vel = s.get("velocity_st_s")
        f0m = f0_det.get(i)          # detrended
        amp = s.get("amplitude_db")

        nbr_f0, nbr_amp, nbr_dur = [], [], []
        for j in (i - 1, i + 1):
            if 0 <= j < n and utt_of[j] == utt_of[i]:   # same utterance only
                v = f0_det.get(j)
                a = syls[j].get("amplitude_db")
                d = syls[j]["end"] - syls[j]["start"]
                if v: nbr_f0.append(v)
                if a: nbr_amp.append(a)
                nbr_dur.append(d)

        nf0  = _mean(nbr_f0)
        namp = _mean(nbr_amp)
        ndur = _mean(nbr_dur) if nbr_dur else None
        dur  = s["end"] - s["start"]

        is_long = ndur and dur >= DURATION_ACCENT * ndur
        hst     = _st(nf0, f0m) if (nf0 and f0m) else None
        is_high = hst is not None and hst >=  HIGH_NBR_ST
        is_low  = hst is not None and hst <= -LOW_NBR_ST
        above   = (amp - namp) if (amp and namp) else None
        is_loud = above is not None and above >= ACCENT_AMP_DB
        strong  = (abs(mv) >= sthr if mv else False) or \
                  (abs(vel) >= VELOCITY_STRONG_ST_S if vel else False)

        if mv is None:      direction = ""
        elif mv >=  wthr:   direction = "//" if strong else "/"
        elif mv <= -wthr:   direction = "\\\\" if strong else "\\"
        else:               direction = ""

        if direction == "":
            h = HIGH_SYM if is_high else (LOW_SYM if is_low else
                (HIGH_SYM if (f0m and nf0) else "?"))
        else:
            h = HIGH_SYM if is_high else (LOW_SYM if is_low else "")

        accent = ((is_loud and hst is not None and hst >= ACCENT_F0_ST)
                  or (is_long and is_loud and is_high))

        sym = ("*" if accent else "") + (h + direction if h else direction) or \
              ("?" if not f0m else HIGH_SYM)
        s["symbol"] = sym
        s["accent"] = accent


# ── TextGrid writer ───────────────────────────────────────────────────────────
def fill(rows, xmax):
    out, cur = [], 0.0
    for r in sorted(rows, key=lambda x: x["start"]):
        s, e = float(r["start"]), float(r["end"])
        if s > cur + 5e-4:
            out.append({"start": cur, "end": s, "value": ""})
        out.append({"start": s, "end": e, "value": r.get("value","")})
        cur = max(cur, e)
    if cur < xmax - 5e-4:
        out.append({"start": cur, "end": xmax, "value": ""})
    return out

def write_tg(path, xmax, tiers):
    def q(t): return str(t).replace('"',"'")
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


# ── video ─────────────────────────────────────────────────────────────────────
def make_video(tg_path, wav_path, out_path, win=5.0, step=1.0, fps=4):
    import numpy as np, librosa, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt, matplotlib.patches as mp

    print("\n  Generating video…", flush=True)
    y, sr   = librosa.load(str(wav_path), sr=None, mono=True)
    total   = len(y) / sr
    tg      = parse_textgrid(tg_path)
    tiers   = tg["tiers"]
    nt      = len(tiers)

    BG = {"sentence":"#EEF4FF","translation":"#EEF4FF",
          "words":"#FFFDE7","gloss":"#FFFDE7",
          "syllables":"#F1F8E9","phones":"#FFF3E0","prosody":"#F3E5F5"}

    frames_dir = out_path.parent / "_frames"
    frames_dir.mkdir(exist_ok=True)
    heights = [0.7, 1.4] + [0.52] * nt
    fig_h   = sum(heights) * 0.88 + 0.5
    paths, t, fi, tot = [], 0.0, 0, int(total/step)+1

    while True:
        te  = min(t + win, total)
        fig, axes = plt.subplots(2+nt, 1, figsize=(14, fig_h),
                                 gridspec_kw={"height_ratios": heights},
                                 facecolor="white")
        fig.subplots_adjust(left=0.13, right=0.99, top=0.95, bottom=0.04, hspace=0)

        seg = y[max(0,int(t*sr)):min(len(y),int(te*sr))]
        ts  = np.linspace(t, te, len(seg))
        axes[0].plot(ts, seg, color="#333", lw=0.3, rasterized=True)
        axes[0].set_xlim(t, te); axes[0].set_ylim(-1,1)
        axes[0].set_ylabel("wav", fontsize=7, rotation=0, ha="right", va="center", labelpad=32)
        axes[0].tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
        for sp in axes[0].spines.values(): sp.set_visible(False)

        ax2 = axes[1]
        if len(seg) > 512:
            S = librosa.amplitude_to_db(
                np.abs(librosa.stft(seg, n_fft=512, hop_length=128)), ref=np.max)
            ax2.imshow(S, aspect="auto", origin="lower",
                       extent=[t,te,0,sr/2], cmap="Greys", vmin=-60, vmax=0, rasterized=True)
        ax2.set_xlim(t,te); ax2.set_ylim(0,5000)
        ax2.set_ylabel("0–5 kHz", fontsize=7, rotation=0, ha="right", va="center", labelpad=32)
        ax2.set_yticks([0,2500,5000]); ax2.tick_params(labelsize=6, bottom=False, labelbottom=False)
        ax2.spines[["top","right","bottom"]].set_visible(False)

        for ti, tier in enumerate(tiers):
            ax = axes[2+ti]
            ax.set_xlim(t,te); ax.set_ylim(0,1)
            bg = BG.get(tier["name"], "#FFF")
            ax.set_facecolor(bg)
            ax.set_ylabel(tier["name"], fontsize=6.5, rotation=0,
                          ha="right", va="center", labelpad=32)
            ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
            for sp in ax.spines.values(): sp.set_visible(False)
            for iv in tier["intervals"]:
                x0 = max(iv["start"],t); x1 = min(iv["end"],te)
                if x1 <= x0+1e-6: continue
                label = iv.get("text","")
                ax.add_patch(mp.Rectangle((x0,.05),x1-x0,.90,
                             facecolor=bg, edgecolor="#999", lw=0.4))
                if label:
                    fs = 5 if len(label)>30 else (6 if len(label)>12 else 7)
                    ax.text((x0+x1)/2,.5,label,ha="center",va="center",
                            fontsize=fs, clip_on=True)

        ax_last = axes[-1]
        ts_step = 0.5 if win<=6 else 1.0
        ax_last.set_xticks(np.arange(np.ceil(t/ts_step)*ts_step, te+.01, ts_step))
        ax_last.tick_params(bottom=True, labelbottom=True, labelsize=6)
        ax_last.set_xlabel("s", fontsize=7)
        fig.suptitle(f"DoReCo Daakie — CREPE Best  [{t:.2f}–{te:.2f} s]  "
                     f"({fi+1}/{tot})", fontsize=8, fontweight="bold", y=.98)

        fp = frames_dir / f"f{fi:05d}.png"
        fig.savefig(str(fp), dpi=100, bbox_inches="tight")
        plt.close(fig)
        paths.append(fp)
        if fi % 20 == 0: print(f"  frame {fi+1}/{tot}  t={t:.1f}s", flush=True)
        if te >= total: break
        t += step; fi += 1

    print(f"  {len(paths)} frames rendered.", flush=True)
    lst = frames_dir/"frames.txt"
    with open(str(lst),"w") as f:
        for p in paths: f.write(f"file '{p.name}'\nduration {1/fps}\n")
        if paths: f.write(f"file '{paths[-1].name}'\n")
    try:
        subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),
                        "-vf",f"scale=trunc(iw/2)*2:trunc(ih/2)*2,fps={fps}",
                        "-c:v","libx264","-pix_fmt","yuv420p","-crf","20",
                        str(out_path)],
                       check=True, cwd=str(frames_dir), capture_output=True)
        print(f"  Video: {out_path}", flush=True)
    except FileNotFoundError:
        print(f"  ffmpeg not found — frames in {frames_dir}", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"  ffmpeg error: {e.stderr.decode()}", flush=True)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nDoReCo BEST (CREPE full, 10 ms): {TG_IN.name}", flush=True)

    tg   = parse_textgrid(TG_IN)
    xmax = tg["xmax"]

    wd = get_tier(tg, "wd@TA")
    ph = get_tier(tg, "ph@TA")
    tx = get_tier(tg, "tx@TA")
    ft = get_tier(tg, "ft@TA")
    gl = get_tier(tg, "gl@TA")
    if wd is None or ph is None:
        sys.exit("ERROR: wd@TA or ph@TA missing")

    def utt(tier):
        return [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                for iv in (tier or [])
                if iv["text"] and iv["text"] not in SKIP_LABELS]

    sentence_rows    = utt(tx)
    translation_rows = utt(ft)

    word_rows, real_words = [], []
    for iv in wd:
        if iv["text"] in SKIP_LABELS or not iv["text"]:
            gap = iv["end"] - iv["start"]
            if gap >= 0.04:
                word_rows.append({"start": iv["start"], "end": iv["end"],
                                  "value": f"<sil {gap:.2f}s>"})
        else:
            word_rows.append({"start": iv["start"], "end": iv["end"],
                              "value": iv["text"]})
            real_words.append(iv)

    gloss_rows = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in (gl or [])
                  if iv["text"] and iv["text"] not in SKIP_LABELS]

    phone_rows = [{"start": iv["start"], "end": iv["end"], "value": iv["text"]}
                  for iv in ph
                  if iv["text"] and iv["text"] not in SKIP_LABELS]

    # syllabify (human phone alignments)
    syl_rows, syl_tmpls = [], []
    for wiv in real_words:
        wp = [iv for iv in ph
              if iv["start"] >= wiv["start"]-1e-4
              and iv["end"]  <= wiv["end"]+1e-4
              and iv["text"] and iv["text"] not in SKIP_LABELS]
        if not wp: continue
        for s in syllabify(wp):
            syl_rows.append({"start": s["start"], "end": s["end"], "value": s["label"]})
            syl_tmpls.append(s)

    # CREPE
    times, f0, rms, _y, _sr = run_crepe(WAV_IN)

    # Utterance boundaries: end time of each tx@TA interval
    # (used to prevent cross-utterance neighbour comparisons)
    utt_breaks = [iv["end"] for iv in (tx or [])
                  if iv["text"] and iv["text"] not in SKIP_LABELS]

    # measure + label
    syls = []
    for tmpl in syl_tmpls:
        s = dict(tmpl)
        s.update(measure(times, f0, rms, tmpl["v0"], tmpl["v1"]))
        syls.append(s)
    label_prosody(syls, utt_breaks=utt_breaks)

    prosody_rows = [{"start": s["start"], "end": s["end"],
                     "value": s.get("symbol","?")} for s in syls]

    tiers = [
        {"name": "sentence",    "rows": sentence_rows},
        {"name": "translation", "rows": translation_rows},
        {"name": "words",       "rows": word_rows},
        {"name": "gloss",       "rows": gloss_rows},
        {"name": "syllables",   "rows": syl_rows},
        {"name": "phones",      "rows": phone_rows},
        {"name": "prosody",     "rows": prosody_rows},
    ]
    HERE.mkdir(parents=True, exist_ok=True)
    write_tg(TG_OUT, xmax, tiers)

    accented = [s for s in syls if s.get("accent")]
    print(f"  Syllables: {len(syls)}  voiced: {sum(1 for s in syls if s.get('f0_onset'))}"
          f"  accented: {len(accented)}", flush=True)

    make_video(TG_OUT, WAV_IN, VID_OUT)

    # open in Praat
    for bin in ("praat","praat6"):
        try:
            subprocess.Popen([bin,"--open", str(WAV_IN.resolve()),
                                             str(TG_OUT.resolve())])
            print("  Praat opened.", flush=True)
            break
        except FileNotFoundError:
            continue


if __name__ == "__main__":
    main()
