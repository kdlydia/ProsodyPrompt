#!/usr/bin/env python3
"""Render one MOV per GToBI sentence: static TextGrid image + embedded audio.

Output: FINAL_QUESTIONNAIRE_2026-06-07/german_gtobi/<sentence>.mov
Each clip shows the full TextGrid (waveform + spectrogram + 6 tiers)
for the duration of the audio, so participants see it while listening.
"""
import re, subprocess, tempfile
from pathlib import Path

import librosa
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

GTOBI_DIR = (Path(__file__).parent.parent /
             "FINAL_QUESTIONNAIRE_2026-06-07" / "german_gtobi")

TIER_BG = {
    "sentence":    "#EEF4FF",
    "words":       "#FFFDE7",
    "translation": "#EEF4FF",
    "syllables":   "#F1F8E9",
    "phones":      "#FFF3E0",
    "prosody":     "#F3E5F5",
}
PROSODY_COLOURS = {
    "*": "#C62828", "‾": "#1565C0", "_": "#6A1B9A",
    "/": "#2E7D32", "\\": "#E65100",
}

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


def render_frame(tg_path, wav_path, title):
    tg     = parse_tg(tg_path)
    xmax   = tg["xmax"]
    tiers  = tg["tiers"]
    nt     = len(tiers)

    y, sr = librosa.load(str(wav_path), sr=None, mono=True)

    heights = [0.8, 1.6] + [0.55] * nt
    fig, axes = plt.subplots(
        2 + nt, 1,
        figsize=(11, sum(heights) * 0.85 + 0.6),
        gridspec_kw={"height_ratios": heights},
        facecolor="white",
    )
    fig.subplots_adjust(left=0.15, right=0.99, top=0.93, bottom=0.05, hspace=0.0)

    # Waveform
    ts = np.linspace(0, xmax, len(y))
    ax = axes[0]
    ax.plot(ts, y, color="#333", linewidth=0.5, rasterized=True)
    ax.set_xlim(0, xmax); ax.set_ylim(-1, 1)
    ax.set_ylabel("wav", fontsize=8, rotation=0, ha="right", va="center", labelpad=38)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
    for sp in ax.spines.values(): sp.set_visible(False)

    # Spectrogram
    ax2 = axes[1]
    S = librosa.amplitude_to_db(
        np.abs(librosa.stft(y, n_fft=512, hop_length=128)), ref=np.max)
    ax2.imshow(S, aspect="auto", origin="lower",
               extent=[0, xmax, 0, sr / 2],
               cmap="inferno", vmin=-60, vmax=0, rasterized=True)
    ax2.set_xlim(0, xmax); ax2.set_ylim(0, 5000)
    ax2.set_ylabel("0–5 kHz", fontsize=7, rotation=0,
                   ha="right", va="center", labelpad=38)
    ax2.set_yticks([0, 2500, 5000])
    ax2.tick_params(labelsize=6, bottom=False, labelbottom=False)
    ax2.spines[["top","right","bottom"]].set_visible(False)

    # Tier rows
    for ti, tier in enumerate(tiers):
        ax  = axes[2 + ti]
        bg  = TIER_BG.get(tier["name"], "#FFFFFF")
        ax.set_facecolor(bg)
        ax.set_xlim(0, xmax); ax.set_ylim(0, 1)
        ax.set_ylabel(tier["name"], fontsize=7.5, rotation=0,
                      ha="right", va="center", labelpad=38)
        ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
        for sp in ax.spines.values(): sp.set_visible(False)

        for iv in tier["intervals"]:
            x0, x1 = float(iv["start"]), float(iv["end"])
            label  = iv.get("text", "")
            if x1 <= x0 + 1e-6: continue
            ax.add_patch(mpatches.Rectangle(
                (x0, 0.04), x1 - x0, 0.92,
                facecolor=bg, edgecolor="#bbb", linewidth=0.5,
            ))
            if label:
                # colour prosody symbols distinctively
                col = "#222"
                if tier["name"] == "prosody":
                    for ch, c in PROSODY_COLOURS.items():
                        if ch in label: col = c; break
                fs = 5 if len(label) > 25 else (6.5 if len(label) > 10 else 8.5)
                ax.text((x0 + x1) / 2, 0.50, label,
                        ha="center", va="center",
                        fontsize=fs, color=col,
                        fontweight="bold" if tier["name"] == "prosody" else "normal",
                        clip_on=True)

    # Time ticks on last axis
    ax_last = axes[-1]
    step = 0.1 if xmax < 2 else 0.5
    ax_last.set_xticks(np.arange(0, xmax + 0.01, step))
    ax_last.tick_params(bottom=True, labelbottom=True, labelsize=7)
    ax_last.set_xlabel("seconds", fontsize=8)

    fig.suptitle(title, fontsize=10, fontweight="bold", y=0.97)
    return fig


def make_video(sentence: str):
    tg_path  = GTOBI_DIR / f"{sentence}.TextGrid"
    wav_path = GTOBI_DIR / f"{sentence}.wav"
    out_path = GTOBI_DIR / f"{sentence}.mov"
    if not tg_path.exists() or not wav_path.exists():
        print(f"  Missing: {sentence}", flush=True); return

    title = sentence.replace("_", " ").title()
    print(f"  {title}…", flush=True)

    fig = render_frame(tg_path, wav_path, title)

    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "frame.png"
        fig.savefig(str(img_path), dpi=120, bbox_inches="tight")
        plt.close(fig)

        # Get audio duration
        y, sr = librosa.load(str(wav_path), sr=None, mono=True)
        dur   = len(y) / sr + 0.3   # tiny tail so last frame isn't cut

        # ffmpeg: loop the image for `dur` seconds, mux with audio → .mov
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-framerate", "1",
            "-i", str(img_path),
            "-i", str(wav_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(dur),
            "-shortest",
            "-movflags", "+faststart",
            str(out_path),
        ], check=True, capture_output=True)

    print(f"    → {out_path.name}  ({dur - 0.3:.2f}s audio)", flush=True)


def main():
    sentences = [
        "eine_gelbe_banane",
        "einige_melonen",
        "er_sang_die_lieder",
        "er_will_die_rosen_haben",
        "ich_wohne_in_bern",
    ]
    print("\nGenerating GToBI video clips…", flush=True)
    for s in sentences:
        make_video(s)
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
