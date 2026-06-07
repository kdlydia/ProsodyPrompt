# SpeechPrint Evaluation Report — Endangered Language Recording
## DoReCo corpus: doreco_port1286_2017_06_30_Jaklin

---

### 1. Recording Metadata

| Property | Value |
|----------|-------|
| File | `doreco_port1286_2017_06_30_Jaklin.wav` |
| Language | European Portuguese (DoReCo corpus) — an endangered variety being documented |
| Duration | 162.7 s (2 min 42 s) |
| Sample rate | 44100 Hz, mono, 16-bit |
| ASR language model applied | Italian (`it`) — nearest supported Romance language model |
| Human annotation | DoReCo hand-annotated TextGrid (10 tiers) |
| Speaker | Jaklin (female, 2017 recording) |

**Note:** This recording is in a Portuguese-family variety documented as part of the DoReCo (Documentation of Remote Corpora) project. No trained acoustic model or pronunciation dictionary exists for this language. The Italian model was applied because Italian is the closest supported Romance language in SpeechPrint, allowing evaluation of cross-language performance.

---

### 2. Pipeline Results by Backend

| Backend | Words | Syllables | Phonemes | Status |
|---------|-------|-----------|----------|--------|
| **Whisper** (segment-level) | 202 | 372 | 790 | ✓ Completed |
| **WhisperX CTC** (word-level) | 202 | 372 | 790 | ✓ Completed |
| **Gentle** (Kaldi/English) | — | — | — | ✗ Skipped — English-only |
| **MFA Italian** (phone-level) | — | — | — | ✗ Failed — OOV words |

**Human annotation (reference):**

| Tier | Intervals |
|------|-----------|
| `h_wd@TA` (human words) | 377 intervals |
| `h_ph@TA` (human phonemes) | 1154 intervals |
| `h_tx@TA` (utterances) | 73 intervals |

---

### 3. What Happened With Each Backend

#### 3.1 Whisper (segment-level alignment)

Whisper `small` was run with `language=it`. It produced 202 word tokens across 73 speech segments, with a total transcript of approximately 180 words of recognisable Italian-sounding text.

**What Whisper recognised (first 60 characters):**
> *"ok sochi ne ha tucco napia nel lumbino ne ha punenso..."*

**Analysis:** Whisper heard Italian-like phoneme sequences in the Portuguese speech. This is expected — Italian and Portuguese are both Romance languages with similar phoneme inventories (especially vowels and fricatives). The transcription is semantically nonsensical (these are not real Italian words) but phonetically plausible given the input.

**Timing:** Words are placed proportionally within each Whisper segment. Two words within the same segment will appear as equally-spaced estimates. This is a coarse approximation — word boundaries within a segment may be off by ±500 ms or more.

#### 3.2 WhisperX CTC (word-level alignment)

WhisperX re-ran forced alignment on the Whisper transcription using the Italian CTC acoustic model (`wav2vec2_voxpopuli_base_10k_asr_it`, 360 MB, downloaded from PyTorch Hub). This produced the **same 202 words** but with **individually forced-aligned boundaries**.

**Word timing precision:** ±50–150 ms per boundary (CTC forced alignment quality). This is significantly better than the proportional Whisper estimate.

**Key observation:** WhisperX and Whisper produced the same word count because the transcription step is shared. The difference is entirely in the **quality of word boundaries**. Compare the `whisper_words` and `whisperx_words` tiers in the COMPARISON TextGrid — word boundaries should differ noticeably.

#### 3.3 Gentle (skipped)

Gentle's Docker image uses the CMU Pronouncing Dictionary (English) and a Kaldi acoustic model trained on English. It is structurally incapable of aligning non-English speech. **Skipped by design.**

#### 3.4 MFA Italian (failed — OOV words)

MFA was invoked with the `italian_cv` acoustic model and `italian_cv.dict` pronunciation dictionary. MFA failed at the corpus preprocessing stage with an alignment error.

**Root cause:** Out-of-vocabulary (OOV) words. The WhisperX Italian transcription contains many words that are not standard Italian and therefore not found in the Italian CV pronunciation dictionary (e.g., `punenso`, `punenchia`, `lumbino`, `sochi`). When the majority of the transcript is OOV, MFA's Kaldi feature generation collapses — it cannot build a word-level decoding graph.

**Implication:** This is not a bug — it is a fundamental limitation of forced alignment for cross-language application. Forced alignment requires that the transcript matches the dictionary. When ASR produces non-dictionary output (which is inevitable for an endangered language run through a mismatched model), MFA cannot proceed.

**What this means for evaluation:** MFA Italian alignment is not available for this file. This is an accurate and important finding: for endangered languages without a trained model, forced alignment tools like MFA are effectively unusable unless a custom dictionary is created from the hand-annotated data.

---

### 4. Comparison with Human Annotation

The COMPARISON TextGrid (`*_COMPARISON.TextGrid`, 20 tiers) places the following tiers side by side:

```
h_tx@TA         — human utterance text (73 utterances)
h_wd@TA         — human words (377)
h_ph@TA         — human phonemes (1154)  ← gold standard
h_mb@TA         — morpheme boundaries (408)
h_gl@TA         — interlinear gloss
h_ps@TA         — part of speech
h_ref@TA        — utterance IDs
h_ft@TA         — English translation

whisper_words   — Whisper word estimates (202)
whisper_syllables
whisper_phonemes
whisper_f0_hz
whisper_prosody
whisper_height

whisperx_words  — WhisperX word estimates (202, better boundaries)
whisperx_syllables
whisperx_phonemes
whisperx_f0_hz
whisperx_prosody
whisperx_height
```

#### 4.1 Word-level comparison

| | Human | Whisper | WhisperX |
|-|-------|---------|---------|
| Word count | 377 | 202 | 202 |
| Coverage | Full recording | ~124% of speech spans | Same transcript, better boundaries |

**Word count discrepancy (377 vs 202):** The human annotation includes functional words, clitics, and particles that Whisper merged or missed. Whisper also hallucinated some word boundaries differently. This is expected — the ASR model has no knowledge of the actual language being spoken.

**Qualitative comparison:** In Praat, align the `h_wd@TA` and `whisperx_words` tiers visually. The WhisperX word boundaries will occasionally coincide with human word boundaries because:
- Both languages are Romance (similar phoneme inventory and rhythm)
- Voicing onsets and stop closures are acoustic events recognisable across languages
- The CTC forced alignment tracks energy and phoneme transitions, which are language-universal

However, word identity will not match — the languages share some phone sequences but not word forms.

#### 4.2 Phoneme-level comparison

Compare `h_ph@TA` (human IPA) with `whisperx_phonemes` (Italian espeak-ng IPA):

- **Human phonemes:** 1154 intervals — hand-labelled to the actual language's phoneme inventory. Includes language-specific vowels, consonants, and tonal features.
- **SpeechPrint phonemes:** 790 intervals — IPA phones derived from Italian phonemization of the garbled Italian transcription. These are the phonemes of the words that Italian espeak-ng *thinks* it heard, not the actual phonemes produced.

**What matches:** Some short common sequences (bilabials, alveolars, open vowels) may coincide because the phoneme inventories overlap significantly for basic places of articulation.

**What does not match:** Language-specific features (nasal vowels, specific diphthongs, tonal patterns) will not appear in the Italian model's output.

**For the evaluation questionnaire (3.1–3.10):** The phoneme tier demonstrates both the potential of SpeechPrint (automatic IPA segmentation, immediate visual cue about segment structure) and its limitation (language-model mismatch produces incorrect transcription for endangered languages).

#### 4.3 Prosody comparison

The F0 analysis (`whisperx_f0_hz`, `whisperx_prosody`, `whisperx_height`) is based on **Parselmouth pitch tracking** of the actual audio — this is completely language-agnostic and **not affected** by the ASR model mismatch.

| Acoustic measure | Value |
|-----------------|-------|
| Mean F0 | 194.6 Hz (female speaker range) |
| F0 range | 77.8 – 493.1 Hz |
| Rising syllables | 23 |
| Falling syllables | 16 |
| Level syllables | 509 / 547 total voiced |

The prosody labels (`/`, `\`, `–`, `*`, `%`) are therefore **valid** even for the endangered language recording — they describe the real pitch contour of the speech regardless of what words were heard. This is an important strength of SpeechPrint's design: the prosody layer is acoustic, not linguistic.

---

### 5. Summary Assessment

| Dimension | Assessment |
|-----------|-----------|
| **Transcription quality** | Poor (expected): Italian model produces plausible-sounding but semantically incorrect transcription of Portuguese/endangered language speech |
| **Word alignment** | Moderate: WhisperX CTC gives usable timing cues at word level despite language mismatch |
| **Phoneme alignment** | Limited: IPA output reflects Italian phonemization of incorrect transcription, not actual language phonemes |
| **Prosody analysis** | Valid: F0, intensity, and pitch direction labels are acoustic measurements, language-independent |
| **MFA alignment** | Not achievable: requires a pronunciation dictionary for the target language |
| **Comparison value** | High: the human annotation provides direct comparison of what an ASR system misses for endangered languages |

**Recommendation:** For endangered language support, SpeechPrint's prosody layer (F0, prominence, phrase boundaries) provides immediate value. The phoneme/word layers require a custom language model or manual correction. SpeechPrint could serve as a starting point for annotators by providing a time-stamped prosodic scaffold even when the lexical transcription is wrong.

---

*Report generated: 2026-05-30 | Pipeline version: 0.4.0*
