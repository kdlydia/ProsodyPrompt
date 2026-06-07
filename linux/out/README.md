# SpeechPrint Evaluation Output — README

## Overview

This directory contains the output of the SpeechPrint automatic annotation pipeline applied to two recordings:

1. **Endangered language (DoReCo — Roots of Europe Portuguese)** — `doreco_port1286_2017_06_30_Jaklin.wav` — 162.7 s, 44100 Hz mono
2. **English prosody corpus** — `audio_2026-05-30_19-01-35.wav` — 305.5 s, 16000 Hz mono

For each recording, the pipeline was run with **four alignment backends** plus a comparison against the hand-annotated DoReCo TextGrid (endangered language only).

---

## Directory Structure

```
out/
  README.md                          ← this file
  REPORT_endangered_language.md      ← evaluation report (endangered language)
  REPORT_english.md                  ← evaluation report (English prosody corpus)

  endangered_language_eval/
    summary.json                     ← machine-readable run summary
    whisper/
      *_whisper.TextGrid             ← Whisper-only (segment-level alignment)
      *_whisper.json
    whisperx/
      *_whisperx.TextGrid            ← WhisperX CTC (word-level alignment)
      *_whisperx.json
    gentle/                          ← (skipped: Gentle is English-only)
    mfa/                             ← (skipped: see REPORT for explanation)
    *_COMPARISON.TextGrid            ← ALL tiers combined, open this in Praat

  english_eval/
    summary.json
    whisper/
      *_whisper.TextGrid
    whisperx/
      *_whisperx.TextGrid
    gentle/
      *_gentle.TextGrid              ← Gentle Kaldi (448/451 words aligned)
    mfa/
      *_mfa.TextGrid                 ← MFA phone-level (1516 phones)
    *_COMPARISON.TextGrid            ← ALL tiers combined, open this in Praat

  doreco_port1286_2017_06_30_Jaklin/   ← original SpeechPrint run output
    *.TextGrid
    *.csv  (words, syllables, phonemes, prosody)
    *.json

  english/                             ← original SpeechPrint run output (English)
    audio_2026-05-30_19-01-35/
      *.TextGrid, *.csv, *.json
```

---

## How to Open in Praat

1. Open Praat
2. From the menu: **Open → Read from file...**
3. Navigate to the `*_COMPARISON.TextGrid` file
4. Also open the corresponding WAV file (drag and drop, or Open → Read from file)
5. Select both the Sound and the TextGrid in the Objects panel, then click **View & Edit**

**Recommended for comparison:**
- `out/endangered_language_eval/doreco_port1286_2017_06_30_Jaklin_COMPARISON.TextGrid`
- `out/english_eval/audio_2026-05-30_19-01-35_COMPARISON.TextGrid`

---

## Tier Description — All TextGrids

### TextGrid Tier Naming Convention

Every tier name follows the pattern `<source>_<content>`:

| Source prefix | Meaning |
|---------------|---------|
| `h_` | **Human annotation** (DoReCo hand-labelled, reference) |
| `whisper_` | **Whisper** (OpenAI Whisper small, segment-level only) |
| `whisperx_` | **WhisperX CTC** (word-level forced alignment) |
| `gentle_` | **Gentle / Kaldi** (word-level, English only) |
| `mfa_` | **MFA** (Montreal Forced Aligner, phone-level) |
| `sp_` | **SpeechPrint standard output** (single-backend, 6 tiers) |

---

### Human Annotation Tiers (DoReCo — endangered language only)

| Tier | Abbreviation | Content |
|------|-------------|---------|
| `h_tx@TA` | Free text | Full utterance transcription in the original language (orthographic) |
| `h_wd@TA` | Word | Word-level segmentation. Each interval = one word, timed to the audio |
| `h_ph@TA` | Phoneme | Hand-annotated phoneme segments in IPA. **This is the gold standard for phoneme comparison** |
| `h_mb@TA` | Morpheme boundary | Morpheme-level segmentation (sub-word) |
| `h_gl@TA` | Gloss | Interlinear gloss (morpheme-by-morpheme translation) |
| `h_ps@TA` | Part of speech | Grammatical category per morpheme |
| `h_ref@TA` | Reference | Utterance identifier strings (e.g. `0001_doreco_port1286_...`) |
| `h_ft@TA` | Free translation | Full utterance translation into English |

---

### SpeechPrint Automatic Tiers (per backend)

Each backend produces **6 tiers** in the COMPARISON TextGrid:

#### 1. `<backend>_words` — Word segmentation

- **Content:** One labelled interval per word recognised by the ASR model. Empty intervals are silences.
- **Timing source:** Depends on backend (see below).
- **IPA:** No — orthographic output from the ASR model.
- **Compare with:** `h_wd@TA` (human word tier).

#### 2. `<backend>_syllables` — Syllable segmentation

- **Content:** Orthographic syllable labels (e.g., `cof` `fee`, `yes` `ter` `day`). Derived from a maximum-onset principle applied to the IPA phonemes.
- **Timing:** Proportional to phone count within each word's timed span.
- **Why this approach:** True syllable-level timing requires MFA phone output or manual annotation. The proportional method is the best available approximation when only word-level timing exists.
- **IPA phones:** Each interval carries an attribute listing its component phones (visible in JSON; displayed as syllable label in the TextGrid).

#### 3. `<backend>_phonemes` — Phoneme (phone) segmentation in IPA

- **Content:** IPA phone symbol per interval, generated by **espeak-ng** (via `phonemizer`).
  - Language code used: `en-us` for English, `it` for Italian
- **Timing:** Proportional to phone count within each syllable span — **except for `mfa_phonemes`**, which uses MFA's phone-level Kaldi timing (most accurate).
- **Symbol set:** IPA, e.g. `t`, `iː`, `f`, `k`, `æ`, `f`, `iː` for "coffee".
- **Compare with:** `h_ph@TA` (human phoneme tier). Note: `h_ph@TA` uses the actual endangered language's phoneme inventory; `sp_phonemes` uses Italian IPA (cross-language mismatch is intentional for evaluation).

#### 4. `<backend>_f0_hz` — F0 pitch per syllable (Hz)

- **Content:** Mean fundamental frequency (F0) over each syllable span, rounded to the nearest Hz. Empty if the syllable is unvoiced.
- **Source:** Parselmouth (Python interface to Praat's pitch tracker, autocorrelation method).
- **Computation:** 10 evenly-spaced sample points per syllable (inspired by ProsodyPro's time-normalised F0), mean taken over voiced frames.
- **Use:** Provides absolute F0 values for comparison with human-perceived pitch. Use alongside `_prosody` for direction.

#### 5. `<backend>_prosody` — Symbolic prosody labels

- **Content:** One symbol per syllable, indicating pitch movement direction and prominence.

| Symbol | Meaning | Condition |
|--------|---------|-----------|
| `/` | Rising pitch | F0 onset→offset movement ≥ threshold (adaptive, based on std dev of all movements in recording) |
| `\` | Falling pitch | F0 onset→offset movement ≤ −threshold |
| `–` | Level pitch | Movement within threshold |
| `?` | Unknown | Syllable is unvoiced or no F0 detected |
| `*` prefix | Prominent syllable | The single syllable with the highest composite prominence score (F0 height + movement + intensity + excursion) |
| `%` prefix | Phrase boundary | A pause of ≥ 250 ms follows this syllable's word |

**Composite prominence score** (per syllable):
```
score = |relative_height_st| + |pitch_movement_st| + intensity_score + excursion_score
```
Where `relative_height_st` is semitones above/below the speaker's mean F0.

**Threshold derivation** (adaptive, per recording):
```
threshold = max(floor=2.5 st,  0.70 × std_dev_of_all_movements)
```
This prevents over-labelling in monotone speech and under-labelling in expressive speech.

**Compared to the original SpeechPrint description:**
- SpeechPrint originally used `_` for low pitch — this implementation uses `H`, `M`, `L` height classes (see tier 6) to separate height from direction.
- `*` marks the single most prominent syllable globally; in the original description it marks "syllables with greater amplitude than neighbours". The current implementation uses a composite acoustic score which is more robust.

#### 6. `<backend>_height` — F0 height class per syllable

- **Content:** `H` (high), `M` (mid), or `L` (low) — derived from the speaker's F0 quartiles.
  - `H` = mean F0 ≥ 75th percentile of all syllables
  - `L` = mean F0 ≤ 25th percentile of all syllables
  - `M` = everything else
- **Use:** Supports ToBI-style high-tone / low-tone distinction. Together with `_prosody`, allows notation of `H*`, `L*`, `!H*` etc. (manually annotated from these cues).

---

### The Four Alignment Backends — What Each Does

#### 1. Whisper (segment-level)
- **ASR model:** OpenAI Whisper `small` — transcription only
- **Word timing:** Each word is placed proportionally within its segment's time span. Segments are typically 2–10 seconds of speech. Word boundaries are **estimates**, not forced-aligned.
- **Phone timing:** Proportional within words.
- **Accuracy:** Lowest temporal precision. Useful as a baseline or when no alignment model is available.
- **Key limitation:** Two words that differ in timing may appear at identical positions if they are in the same segment.

#### 2. WhisperX (CTC word-level)
- **ASR model:** WhisperX = Whisper `small` transcription + CTC forced alignment using a separate acoustic model (`wav2vec2_voxpopuli_base_10k_asr_<lang>`)
- **Word timing:** CTC forced alignment — each word token is matched to audio frames using dynamic programming. Precision is typically ±50 ms at word boundaries.
- **Phone timing:** Proportional within words (CTC gives word-level, not phone-level).
- **Accuracy:** Word-level alignment, good for English and Italian. Better than plain Whisper.
- **Key difference from Whisper:** WhisperX re-runs forced alignment on the word tokens, so boundary precision is much better than the proportional estimate.

#### 3. Gentle (Kaldi-based)
- **ASR model:** Gentle uses the Kaldi speech recognition toolkit with a pre-trained English acoustic model and the CMU Pronouncing Dictionary.
- **Word timing:** Kaldi forced alignment — aligns a known transcript to audio using HMM-based acoustic models. Typical precision: ±20–50 ms.
- **Phone timing:** Proportional within words (Gentle returns word-level output in its JSON API).
- **Language support:** English only. Gentle's dictionary and acoustic model are English-specific.
- **Availability:** Requires Docker (`lowerquality/gentle`). Skipped for non-English audio.
- **Aligned words:** 448/451 (3 words returned "not found" — these appear near very quiet or fast speech).

#### 4. MFA — Montreal Forced Aligner (phone-level)
- **ASR model:** MFA uses pre-trained Kaldi acoustic models per language (`english_mfa` for English, `italian_cv` for Italian) plus a pronunciation dictionary.
- **Word timing:** Kaldi forced alignment — same precision as Gentle, ±20–50 ms.
- **Phone timing:** MFA is unique in providing **phone-level timing** — each phoneme gets its own start/end time. This is the highest temporal resolution of all four backends.
- **Language support:** English and Italian available (pre-trained models found in `thesis260512/tools/mfa_models`).
- **Key advantage:** The `mfa_phonemes` tier reflects MFA's own phone-level boundaries, not the proportional estimate used by other backends. Compare `mfa_phonemes` with `h_ph@TA` (human phonemes) for the most meaningful evaluation.
- **Note on endangered language:** MFA failed for the endangered language file when using the Italian model. Reason: the WhisperX Italian-model transcription produced many words that are not in the Italian pronunciation dictionary (OOV — out of vocabulary), causing MFA's feature generation to fail. This is an important finding about the limitations of cross-language forced alignment.

---

## Recommendation: Which Backend for Which Purpose?

| Use case | Recommended backend | Reason |
|----------|-------------------|--------|
| English research, word-level timing | **WhisperX** or **MFA** | WhisperX is fast; MFA is more accurate but needs dictionary |
| English research, phone-level timing | **MFA** | Only backend with true phone-level output |
| English prosody annotation support | **MFA** + prosody tiers | Most accurate timing for F0 extraction per phoneme |
| Endangered / low-resource language | **WhisperX** with nearest-language model | MFA and Gentle require a dictionary; WhisperX CTC works cross-lingually |
| Quick overview / demo | **Whisper** | Fastest, no alignment model needed |

### Why Not Average Alignments?

The user asked about using an **average** of all aligners' output for syllables and phonemes. This is **not recommended** for the following reasons:

1. **Different aligners agree on segments but not boundaries.** The word "yesterday" might span 0.80–1.20 s in WhisperX and 0.82–1.18 s in MFA. Averaging gives 0.81–1.19 s, which is not more accurate — it introduces a false precision.

2. **Averaging fails for qualitatively different outputs.** MFA gives phone-level timing; others give word-level. There is no principled way to average a 10-phone sequence with a 1-word estimate.

3. **The best approach depends on the task.** For phoneme comparison: use MFA. For quick word-level: use WhisperX. For endangered language: use WhisperX with the closest available language model.

**Recommendation:** Use **WhisperX** as the default for all languages. Use **MFA** additionally for English and other languages where a trained acoustic model and dictionary exist. Report both with their known limitations.

---

## Symbolic Prosody Layer — Design Rationale

The prosody annotation in SpeechPrint is designed to give linguists information that supports, but does not replace, theory-guided transcription. Inspired by **ProsodyPro** (Xu, 2005) and the **ToBI** system:

### What SpeechPrint provides vs. what ProsodyPro provides

| Feature | SpeechPrint | ProsodyPro |
|---------|-------------|-----------|
| Pitch direction | `/` `\` `–` per syllable | F0 contour (10 pts/interval) + velocity |
| Pitch height | `H`/`M`/`L` classes | Mean/max/min F0 in Hz; relative to speaker |
| Prominence | `*` on strongest syllable | Prominence score per interval |
| Phrase boundaries | `%` based on pause | Manual segmentation required |
| F0 excursion | Computed, in JSON | Excursion size in semitones |
| Intensity | Used in prominence score | Time-normalised intensity (10 pts) |

ProsodyPro provides **more raw data** (continuous F0 contour, velocity profile) but requires **Praat scripting skill and manual annotation** of intervals. SpeechPrint provides **ready-to-read symbolic labels** that a non-expert can use directly in Praat.

### Symbol interpretation guide

```
*\     = The most prominent syllable in this recording, with falling pitch
         → likely a nuclear accent (ToBI: H* or L+H* depending on height)

%/     = Phrase-boundary syllable (pause follows) with rising pitch
         → likely a phrase-medial rise or continuation rise (ToBI: H-)

–      = Level pitch, unremarkable prominence
         → likely non-accented (ToBI: unaccented syllable)

H      = F0 in upper quartile of speaker's range
L      = F0 in lower quartile
M      = F0 mid-range
```

### Known limitations

- Prominence is marked **only on the globally strongest syllable** per recording. For recordings with multiple sentences (like the English prosody corpus), this will mark the single loudest/highest syllable in the entire 5-minute file rather than per-utterance accents. For per-utterance analysis, segment the file first.
- The F0 tracker (Parselmouth autocorrelation) can fail in noisy or breathy segments, leading to `?` labels.
- Syllabification is heuristic (maximum-onset principle on IPA phones). It may differ from language-specific syllabification rules.
- Phase `%` boundary detection uses a fixed 250 ms pause threshold — may miss very short pauses or flag non-boundary silences in quiet speech.

---

## How to Run the Pipeline

### Standard SpeechPrint (single backend, GUI or CLI)

```bash
# From linux/ directory, with the testSpeechPrint venv
VENV=/home/lydia/School/UPF/testSpeechPrint/SpeechPrint-main/linux/.venv
PYTHONPATH=. "$VENV/bin/python" -m speechprint_pkg.cli annotate \
    doreco_port1286_2017_06_30_Jaklin.wav --language it --output out/
```

### Multi-aligner evaluation (all backends)

```bash
VENV=/home/lydia/School/UPF/testSpeechPrint/SpeechPrint-main/linux/.venv
"$VENV/bin/python" evaluate_aligners.py \
    --wav audio_2026-05-30_19-01-35.wav \
    --language en \
    --output out/english_eval \
    --backends whisper whisperx gentle mfa
```

### Merge with human annotation

```bash
"$VENV/bin/python" evaluate_aligners.py \
    --wav doreco_port1286_2017_06_30_Jaklin.wav \
    --language it \
    --reference doreco_port1286_2017_06_30_Jaklin.TextGrid \
    --output out/endangered_language_eval
```

### Dependencies

| Tool | Version | Location |
|------|---------|---------|
| Python | 3.13 | `/home/lydia/School/UPF/testSpeechPrint/SpeechPrint-main/linux/.venv` |
| WhisperX | 3.8.5 | same venv |
| OpenAI Whisper | 20231117 | same venv |
| Parselmouth | latest | same venv |
| phonemizer / espeak-ng | latest | same venv |
| MFA 3.3.9 | — | conda env `speechprint-mfa` |
| Gentle | Docker `lowerquality/gentle:latest` | Docker |

---

*Generated: 2026-05-30 by SpeechPrint evaluation pipeline v0.4.0*
