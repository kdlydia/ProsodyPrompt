**A linguistic prosody annotation environment and field-research toolkit.**  
Drop a WAV in, get a Praat TextGrid out — with symbolic prosody, multi-tracker F0 comparison, and pathways to articulatory synthesis.

> ⚠️ **For Linux machines only.** macOS and Windows ports are planned. See platform status below.

---

```
┌─────────────────────────────────────────────────────┐
│  Navigate to the SpeechPrint GitHub page:           │
│  https://github.com/speechprint/SpeechPrint         │
└─────────────────────────────────────────────────────┘
```

---

## What SpeechPrint is

SpeechPrint is a Swiss army knife for anyone who needs to go from raw audio to structured prosodic annotation — without knowing how to get WhisperX to work, without a phonetics lab, and without specialist software beyond Praat.

It is designed for two kinds of users:

**Field linguists and language documenters** who need fast, reproducible prosodic pre-annotation for under-resourced or endangered languages. No ASR model exists for your language? SpeechPrint can work from your own human-annotated TextGrid tiers and apply the acoustic analysis automatically.

**Computational researchers and students** who want to compare pitch tracking algorithms, evaluate forced alignment quality, or produce symbolic prosody layers for corpora quickly.

The longer dream — and where this is heading — is a system in which prosody is not just analysed but *authored*: a combined text editor and speech DAW where you draw an intonation contour, hum a prosodic pattern, or sketch source-target articulatory trajectories, and the system generates speech accordingly. People write scripts but need actors to figure out how to say them. Why not encode that in the script.

---

## Quick start

```bash
git clone https://github.com/speechprint/SpeechPrint
cd SpeechPrint/linux
python run.py
```

That's it. The interactive CLI opens immediately — no GUI, no configuration files to edit. It works like `pacman`: asks questions, shows numbered options, lets you toggle trackers on and off, then runs the pipeline.

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

```
┌─────────────────────────────────────────────────────────────┐
│  Annotation source                                          │
│                                                             │
│  ○  I have a human-annotated TextGrid (DoReCo / fieldwork)  │
│     → words, phones, and timing come from your file.        │
│     → Only acoustic measurement and prosody labelling       │
│        are applied automatically.                           │
│                                                             │
│  ○  I have audio only — run full automatic pipeline         │
│     → Transcription → alignment → phonemization             │
│        → acoustic measurement → prosody labels              │
│                                                             │
│                              [ Next → ]                     │
└─────────────────────────────────────────────────────────────┘
```

**Human-annotated path** (DoReCo, ELAN export, manually corrected TextGrid):  
Tier names are mapped automatically. DoReCo uses `@TA` or `@6` suffixes; SpeechPrint detects both. Words, phones, and utterance boundaries are read directly, and only the F0 extraction and prosody labelling steps run automatically. This is the recommended path for endangered and under-resourced languages.

**Automatic path** (audio only):  
Full nine-stage pipeline: transcription → forced alignment → phonemization → syllabification → F0 extraction → prosody labelling.

---

## Step 1 — Language selection

```
┌─────────────────────────────────────────────────────────────┐
│  Language                                                   │
│                                                             │
│  Common languages (ASR + forced alignment available)        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  English (en)  German (de)  Spanish (es)             │   │
│  │  French (fr)   Italian (it) Japanese (ja)  ...       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ○  My language is not listed above                         │
│     Language ISO code (optional): [      ]                  │
│                                                             │
│     ☐  Find a phonologically similar supported language     │
│        (uses IPA consonant/vowel inventory overlap)         │
│        Suggested: Italian for Romance; Japanese for         │
│        mora-timed languages; etc.                           │
│                                                             │
│     Note: ASR output will be phonetically plausible but     │
│     lexically incorrect. Prosody labels remain acoustically │
│     valid regardless of transcription quality.              │
│                                                             │
│                              [ Next → ]                     │
└─────────────────────────────────────────────────────────────┘
```

When no model exists for your language, SpeechPrint ranks available ASR languages by phonological distance — measured by consonant inventory overlap and vowel system similarity from PHOIBLE/WALS data. A Chibchan language will be offered Quechua or a similar inventory before it is offered English.

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

```
┌─────────────────────────────────────────────────────────────┐
│  Pitch tracker                                              │
│                                                             │
│  ☑  pYIN (recommended for clean speech)                     │
│  ☑  CREPE (recommended for field/archival)                  │
│  ☑  PESTO                                                   │
│  ☑  Praat AC + Xu(1999)                                     │
│  ☐  YIN (not recommended for prosody)                       │
│                                                             │
│  ☑  Generate comparison TextGrid                            │
│     (one prosody_* tier per tracker)                        │
│                                                             │
│                              [ Run → ]                      │
└─────────────────────────────────────────────────────────────┘
```

The comparison TextGrid lets you open the same recording in Praat and inspect all five prosody tiers simultaneously — choose whichever matches your perception of the intonation.

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
