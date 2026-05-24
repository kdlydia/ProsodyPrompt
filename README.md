# SpeechPrint

Linguistic annotation toolchain. Drop a WAV in, get a Praat TextGrid out.

## Quick start (Linux)

```bash
cd linux
export SPEECHPRINT_ROOT="$PWD"
uv run python -m lib.main
```

Two buttons: **Install SpeechPrint** (one-time) and **New Project / Corpus**.
After creating a project the workspace opens with Import Audio, Record,
Run Annotation, Open in Praat, Export ZIP.

## Output

Each annotated recording produces a Praat TextGrid with six tiers:

1. `words`
2. `syllables`
3. `phonemes` (IPA)
4. `f0_pitch` (mean Hz per syllable)
5. `prosody_labels` (`/` `\` `–`, strongest accent prefixed with `*`)
6. `warnings_review` (what fell back, if anything — `ok` otherwise)

Plus `words.csv`, `syllables.csv`, `phonemes.csv`, `prosody.csv`,
`<recording>.json`, `warnings.json`, `LOG.txt`.

## Platforms

- **Linux** — primary development and testing target.
- **macOS** and **Windows** — scaffolding included, not yet validated.

## Honesty about the pipeline today

- Word timing: WhisperX `align()` when available; falls back to
  segment-proportional or equal-width and writes a warning.
- Phonemes: phonemizer + espeak-ng. Timing is distributed proportionally
  inside each syllable — **not** MFA-grade phone alignment yet.
- Syllables: proportional to phone count inside word intervals.
- Prosody labels: automatic symbolic estimate; thresholds adaptive
  (≥3 ST and ≥0.75× recording std-dev).

Real MFA integration is the next scientific milestone.

## Docs

- [docs/LINUX.md](docs/LINUX.md)
- [docs/MACOS.md](docs/MACOS.md)
- [docs/WINDOWS.md](docs/WINDOWS.md)
- [docs/DEVELOP.md](docs/DEVELOP.md)

GPL-3.0 — see [LICENSE.txt](LICENSE.txt).
