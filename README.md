# ProsodyPrompt

Linguistic prosody annotation environment and field-research toolkit.
Drop a WAV in, get a Praat TextGrid out.

Linux only for now. macOS and Windows planned.

Source: https://github.com/kdlydia/SpeechPrint

---

SpeechPrint is for anyone who needs to go from raw audio to structured prosodic annotation without a phonetics lab. It runs a pipeline from transcription through forced alignment to symbolic prosody labels, outputs a Praat TextGrid, and lets you compare five pitch trackers side by side so you can decide which one looks right for your recording.

It works for two kinds of material: recordings where you have a human-annotated TextGrid already (DoReCo fieldwork corpora, ELAN exports) and recordings where you have audio only and need everything done automatically.

The longer direction is a system where prosody is not just analysed but authored — a combined text editor and speech DAW where you draw an intonation contour or sketch a prosodic pattern and the system generates speech accordingly. People write scripts but need actors to figure out how to say them. The idea is to encode that in the script itself. DrawSpeech (Chen et al., 2025) showed this is tractable: users draw rough pitch sketches per word and a diffusion model recovers the full contour. SpeechPrint's symbolic tier is the analysis side of that loop; the synthesis side is where this is heading.

---

## Quick start

```bash
git clone https://github.com/kdlydia/SpeechPrint
cd SpeechPrint/linux
python run.py
```

The interactive CLI opens immediately. No GUI, no config files. It asks questions and shows numbered options — choose language, tracker, annotation source — then runs the pipeline.

```
════════════════════════════════════════════════════════
  SpeechPrint  v0.3
════════════════════════════════════════════════════════

  Linguistic prosody annotation environment
  For Linux machines only.
  https://github.com/speechprint/SpeechPrint

Main menu
────────────────────────────────────────────────────────

  1)  Annotate a recording
  2)  Batch annotate a folder
  3)  Check / install dependencies
  4)  Open output folder in file manager
  q)  Quit

  >
```

On first run, choose **3** to check and install missing dependencies automatically.

> A GTK4 GUI is planned for a later release. The interactive CLI covers all functionality.

---

## Step 0 — Do you have a human-annotated TextGrid?

SpeechPrint asks this at launch. Your answer determines the entire pipeline.

The CLI asks three questions before running.

**1. Do you have a human-annotated TextGrid?**
If yes, point it at your file. DoReCo's `@TA` and `@6` tier suffixes are detected automatically; words, phones, and utterance boundaries come from your annotation, and only the F0 extraction and prosody labelling run automatically. This is the recommended path for endangered and under-resourced languages.
If no, the full nine-stage pipeline runs from transcription to prosody labels.

**2. Language.**
For common languages (English, German, Spanish, French, Italian, and others) SpeechPrint uses WhisperX large-v3 for transcription and MFA for phone-level alignment on English. For endangered or under-resourced languages, it can suggest the phonologically closest supported model using consonant and vowel inventory overlap from PHOIBLE data. ASR output on an unsupported language will be phonetically plausible but lexically incorrect; the prosody labels are acoustically valid regardless of transcription quality.

---

## Step 2 — Pitch tracker selection

SpeechPrint supports five pitch trackers. You can run one or all in parallel; the comparison TextGrid shows every track as a separate prosody tier so you can visually choose which works best for your recording.

| Tracker | Type | Best for | Notes |
|---------|------|----------|-------|
| **pYIN** (librosa) | Signal-processing | Clean studio speech, fast CPU | Best for common languages; reliable V/UV detection |
| **CREPE** (torchcrepe) | Deep learning | Archival / field recordings | Most robust on irregular phonation; slower |
| **PESTO** | Self-supervised | Novel phonation types | Trained on singing; different error profile |
| **Praat AC + Xu(1999)** | Signal-processing | Reference / comparison | Good fallback; known octave-error risk |
| **YIN** (librosa) | Signal-processing | Speed only | No V/UV detector — unreliable for prosody |

**3. Pitch tracker.**
Toggle any combination. Enabling comparison mode writes a separate `prosody_*` tier for each tracker so you can open the same recording in Praat and compare them directly — choose whichever matches your perception of the intonation.

---

## Pipeline

### Automatic path (nine stages)

```
WAV
 │
 ├─ Stage 1: Load audio (sample rate, duration, channel count)
 ├─ Stage 2: Transcribe (WhisperX large-v3 → word sequence + segment timing)
 ├─ Stage 3: Prepare transcript (clean punctuation, label silences)
 ├─ Stage 4: Forced alignment
 │           English → MFA phone-level
 │           Other   → WhisperX CTC word-level
 │           Fallback → proportional distribution
 ├─ Stage 5: F0 + intensity extraction (pYIN / CREPE / PESTO / Praat)
 │           Speaker pitch range auto-detected from first 20 s
 │           Xu(1999) spike removal + octave recovery applied
 ├─ Stage 6: Phonemization (espeak-ng → IPA; max-onset syllabification)
 ├─ Stage 7: Symbolic prosody labelling
 │           MAD-based adaptive thresholds
 │           Utterance boundary reset (no cross-utterance neighbours)
 │           Pitch declination removal (linear regression per utterance)
 │           Nucleus edge trimming (15% from each end)
 ├─ Stage 8: Write TextGrid (Praat-format, contiguous intervals)
 └─ Stage 9: Export CSV + JSON (per-word, per-syllable, per-phoneme)
```

### Human-annotation path

```
WAV + existing TextGrid
 │
 ├─ Read tier mapping (@TA / @6 / custom)
 ├─ Syllabify from ph@* tier (max-onset, language vowel inventory)
 ├─ Stage 5: F0 + intensity (CREPE recommended for endangered languages)
 │           All five algorithmic optimisations applied
 └─ Stage 8–9: Write output TextGrid + CSV
```

---

## Output

### TextGrid tiers

| Tier | Source | Content |
|------|--------|---------|
| `sentence` | ASR / human tx@* | Utterance-level text |
| `words` | ASR / human wd@* | Word intervals; silences as `<sil N.NNs>` |
| `translation` | human ft@* | English translation (endangered language recordings) |
| `syllables` | computed | IPA syllable labels |
| `phones` | MFA / espeak-ng / human ph@* | Phone-level intervals |
| `prosody` | computed | Symbolic labels (best tracker) |
| `prosody_pyin` | pYIN | pYIN prosody tier (comparison mode) |
| `prosody_crepe` | CREPE | CREPE prosody tier |
| `prosody_pesto` | PESTO | PESTO prosody tier |
| `prosody_praat` | Praat AC | Praat prosody tier |

### Prosody symbols

| Symbol | Meaning |
|--------|---------|
| `/` | Weakly rising pitch within syllable |
| `//` | Strongly rising (> 2.5 × adaptive threshold) |
| `\` | Weakly falling |
| `\\` | Strongly falling |
| `‾` | High level (above neighbouring syllables, U+203E) |
| `_` | Low level (below neighbouring syllables) |
| `*` | Prominent accent (louder + higher or longer than neighbours) |
| `?` | Unvoiced or insufficient F0 data |

Symbols combine: `*‾//` = accented, high, strongly rising. `_\\` = low, strongly falling.

### Export structure

```
recording_name/
├── recording.wav
├── recording.TextGrid          ← main output (open in Praat)
