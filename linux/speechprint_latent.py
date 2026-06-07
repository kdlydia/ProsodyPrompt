#!/usr/bin/env python3
"""
speechprint_latent.py
Extension of SpeechPrint: bridge symbolic prosody tier → EnCodec latent space.

What this tests:
  EnCodec (Meta) encodes audio into Residual Vector Quantization (RVQ) codes.
  The codes are stacked: codebook 0 = coarse/speaker/timbre,
  codebooks 1-3 = prosody/rhythm/melody, codebooks 4-7 = fine texture/noise.
  SpeechPrint's / \ * labels describe the same layer as codebooks 1-3.
  So: swapping those middle codebooks between two languages = prosody transfer.

Run:
  python speechprint_latent.py

Output:
  prosody_swap_eng_daakie.wav   — English content + Daakie prosody pattern
  prosody_swap_daakie_eng.wav   — Daakie content + English prosody pattern
  latent_codes_comparison.png   — heatmap of codebook codes across languages
"""

import torch
import torchaudio
import numpy as np
from pathlib import Path

BASE  = Path(__file__).parent
AUDIO = {
    "english": BASE / "audio_2026-05-30_19-01-35.wav",
    "daakie":  BASE / "doreco_port1286_2017_06_30_Jaklin.wav",
    "german_banana":  BASE / "five GToBI annotated sentences/eine_gelbe_banane.wav",
    "german_melonen": BASE / "five GToBI annotated sentences/einige_melonen.wav",
}
MAX_SEC = 10   # trim to this many seconds to keep things fast


# ── 1. Load EnCodec ──────────────────────────────────────────────────────────

def load_model():
    from encodec import EncodecModel
    from encodec.utils import convert_audio as _convert
    model = EncodecModel.encodec_model_24khz()
    model.set_target_bandwidth(6.0)   # 8 codebooks at 24 kHz
    model.eval()
    print(f"EnCodec loaded: {model.sample_rate} Hz, "
          f"{model.quantizer.n_q} codebooks, bandwidth=6 kbps")
    return model, _convert


# ── 2. Encode one audio file → RVQ codes ────────────────────────────────────

def encode(model, convert, path, max_sec=MAX_SEC):
    import soundfile as sf
    data, sr = sf.read(path, dtype='float32', always_2d=True)
    data = data.T  # (channels, samples)
    wav = torch.tensor(data)
    wav = wav[:, : int(sr * max_sec)]
    wav = convert(wav, sr, model.sample_rate, model.channels)
    with torch.no_grad():
        frames = model.encode(wav.unsqueeze(0))
    codes = torch.cat([c for c, _ in frames], dim=-1)   # [1, n_q, T]
    return codes, wav


# ── 3. Decode codes → audio ──────────────────────────────────────────────────

def decode(model, codes):
    with torch.no_grad():
        wav = model.decode([(codes, None)])
    return wav.squeeze(0)

def save_wav(tensor, path, sr=24000):
    import soundfile as sf
    data = tensor.cpu().numpy()
    if data.ndim == 2:
        data = data.T          # (samples, channels)
    elif data.ndim == 1:
        data = data[:, None]
    sf.write(str(path), data, sr)


# ── 4. Prosody swap (the key operation) ──────────────────────────────────────

def swap_prosody(codes_A, codes_B, prosody_books=(1, 2, 3)):
    """
    Keep codes_A's speaker/timbre (book 0) and fine detail (books 4-7).
    Replace prosody/rhythm books (1-3) with those from codes_B.
    Time-resamples codes_B to match codes_A's length if needed.
    """
    mixed = codes_A.clone()
    T_A   = codes_A.shape[-1]
    T_B   = codes_B.shape[-1]
    for b in prosody_books:
        src = codes_B[:, b, :].float().unsqueeze(1)       # [1, 1, T_B]
        if T_A != T_B:
            import torch.nn.functional as F
            src = F.interpolate(src, size=T_A, mode='nearest')
        mixed[:, b, :] = src.squeeze(1).long()
    return mixed


# ── 5. Visualise codebook heatmaps ───────────────────────────────────────────

def plot_codes(codes_dict, out_path="latent_codes_comparison.png"):
    try:
        import matplotlib.pyplot as plt
        n = len(codes_dict)
        fig, axes = plt.subplots(1, n, figsize=(6 * n, 4))
        if n == 1:
            axes = [axes]
        for ax, (name, codes) in zip(axes, codes_dict.items()):
            data = codes[0].numpy().astype(float)   # [n_q, T]
            im = ax.imshow(data, aspect='auto', origin='lower',
                           cmap='viridis', interpolation='nearest')
            ax.set_title(f"{name}\n({data.shape[1]} frames, {data.shape[0]} codebooks)")
            ax.set_xlabel("time frames")
            ax.set_ylabel("codebook index")
            plt.colorbar(im, ax=ax)
        # shade the prosody codebooks
        for ax in axes:
            ax.axhspan(0.5, 3.5, alpha=0.15, color='red',
                       label='prosody books 1-3')
            ax.legend(fontsize=8)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120)
        print(f"  Heatmap saved: {out_path}")
    except ImportError:
        print("  (matplotlib not available — skipping heatmap)")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("SpeechPrint × EnCodec latent space test")
    print("=" * 60)

    model, convert = load_model()

    # --- encode all available files
    codes = {}
    for name, path in AUDIO.items():
        if path.exists():
            print(f"\nEncoding: {name}")
            c, _ = encode(model, convert, str(path))
            codes[name] = c
            print(f"  codes shape: {c.shape}  "
                  f"(n_codebooks={c.shape[1]}, T={c.shape[2]} frames)")
        else:
            print(f"  skip (not found): {path.name}")

    if not codes:
        print("No audio files found — check paths.")
        raise SystemExit(1)

    # --- cross-lingual prosody swaps
    pairs = [
        ("english", "daakie",         "prosody_swap_eng_content_daakie_prosody.wav"),
        ("daakie",  "english",         "prosody_swap_daakie_content_eng_prosody.wav"),
        ("german_banana", "english",   "prosody_swap_german_content_eng_prosody.wav"),
    ]
    print("\n--- Cross-lingual prosody swaps ---")
    for src, prosody_src, fname in pairs:
        if src in codes and prosody_src in codes:
            mixed   = swap_prosody(codes[src], codes[prosody_src],
                                   prosody_books=(1, 2, 3))
            wav_out = decode(model, mixed)
            out     = BASE / fname
            save_wav(wav_out, out)
            print(f"  {src} content + {prosody_src} prosody → {fname}")

    # --- visualise codebook heatmaps
    print("\n--- Codebook heatmaps ---")
    plot_codes({k: v for k, v in codes.items()
                if k in ("english", "daakie")},
               out_path=str(BASE / "latent_codes_comparison.png"))

    print("\nDone.")
    print("\nWhat to listen for:")
    print("  eng_content_daakie_prosody: English words, does the rhythm/melody")
    print("    feel different — more like the Daakie recording?")
    print("  If yes: codebooks 1-3 carry cross-lingual prosodic character.")
    print("  If no:  try prosody_books=(2, 3) or (1, 2) to isolate the layer.")
    print("\nThis is the engineering proof-of-concept for the latent space idea.")
