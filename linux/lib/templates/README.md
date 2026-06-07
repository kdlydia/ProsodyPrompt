# @CORPUS_NAME@

A SpeechPrint project / corpus.
Default language for new recordings: **@LANGUAGE@** (can be overridden per file).

## Quick start (GUI)

1. Launch SpeechPrint and choose **Open Existing Project** → this folder.
2. In the workspace:
   - **Import Audio** to copy a WAV (or any audio file — ffmpeg will convert).
   - **● Record** to capture directly from the default microphone.
   - Pick a recording from the list, choose its language, then **Run Annotation**.
   - When the 9-stage progress finishes you can **Open in Praat**, **Open Folder**, or **Export ZIP** to share.

## Quick start (CLI)

```bash
# Annotate one file
speechprint annotate data/<recording>.wav --language @LANGUAGE@

# Annotate everything in data/
speechprint-run data @LANGUAGE@ .

# Aggregate per-recording outputs into corpus-level tables
speechprint ensemble --root .
```

## What gets produced

For each `<recording>.wav` placed in `data/`, the pipeline writes
`out/<recording>/` with:

```
<recording>/
├── <recording>.wav           # copy of the source
├── <recording>.TextGrid      # 6-tier Praat TextGrid
├── <recording>.json          # full machine-readable manifest
├── words.csv                 # word intervals from forced alignment
├── syllables.csv             # syllable intervals + per-syllable f0, intensity, formants
├── phonemes.csv              # IPA phones (proportional within each syllable)
├── prosody.csv               # one-row summary for this recording
├── warnings.json             # what fell back, if anything
├── run_metadata.json
├── LOG.txt                   # stage-by-stage progress log
├── figures/
└── intermediates/
```

### TextGrid tier set

The TextGrid contains exactly six tiers, in this order:

1. **words** — IntervalTier, word-level intervals from forced alignment
2. **syllables** — IntervalTier, orthographic syllable labels
3. **phonemes** — IntervalTier, IPA phones
4. **f0_pitch** — IntervalTier, mean f0 per syllable (Hz, integer)
5. **prosody_labels** — IntervalTier, `/` `\` `–` symbols; the strongest accent is prefixed with `*`
6. **warnings_review** — IntervalTier, a single span describing fallbacks/warnings (or `ok`)

## Corpus configuration

Edit `corpus.toml` to change defaults. Per-recording overrides live in
`[recordings."<file>.wav"]` tables.

## Open in Praat (CLI)

```bash
praat --open out/<recording>/<recording>.wav out/<recording>/<recording>.TextGrid
```

## Troubleshooting

### "WhisperX unavailable" warning

The pipeline falls back to plain `openai-whisper`, then to the filename if no
ASR is available. Re-run the installer or `pip install whisperx` into the
SpeechPrint venv.

### Phoneme tier is empty

`espeak-ng` and `phonemizer` are needed. Re-run the installer (it now
installs both by default), or:

```bash
# On Arch:
sudo pacman -S espeak-ng
# Then in the SpeechPrint venv:
uv pip install phonemizer
```

### Word boundaries look off

The pipeline's best path uses WhisperX's `align()` for phonetic word timing.
Without it, word timing degrades to segment-proportional or equal-width
fallbacks — `warnings.json` and the `warnings_review` tier in the TextGrid
will tell you which path was used.

## Documentation

- [SpeechPrint](https://github.com/SpeechPrint/SpeechPrint)
- [Praat](https://www.fon.hum.uva.nl/praat/)
- [Montreal Forced Aligner](https://montreal-forced-aligner.readthedocs.io/)
- [phonemizer + espeak-ng](https://github.com/bootphon/phonemizer)
