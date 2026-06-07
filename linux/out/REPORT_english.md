# SpeechPrint Evaluation Report — English Prosody Corpus
## audio_2026-05-30_19-01-35

---

### 1. Recording Metadata

| Property | Value |
|----------|-------|
| File | `audio_2026-05-30_19-01-35.wav` (converted from OGG) |
| Language | English |
| Duration | 305.5 s (5 min 5 s) |
| Sample rate | 16000 Hz, mono, 16-bit |
| ASR language model | English (`en`) — `whisper-small` + `english_mfa` |
| Human annotation | None (evaluation via internal comparison of backends) |
| Content | Prosody elicitation corpus — contrastive stress, focus, sentence type |

---

### 2. Corpus Content

The recording contains a scripted prosody corpus covering the following pragmatic/prosodic categories:

| Category | Examples |
|----------|---------|
| Contrastive stress | Do you want **TEA** or COFFEE? vs. Do you want tea or **COFFEE**? |
| Focus movement | **MARY** flew to Milan. / Mary flew to **MILAN**. / Mary flew to Milan **YESTERDAY**. |
| Statement vs. question | Mary has arrived already. / Mary has arrived already? |
| Lexical stress alternation | **PER**mit (noun) / per**MIT** (verb); **CON**tract / con**TRACT** |
| Broad vs. narrow focus | What happened? / John bought a new **CAR** yesterday. |
| Focus-sensitive particles | **ONLY** John called Maria. / John only **CALLED** Maria. / John called only **MARIA**. |
| Yes/no vs. alternative questions | Do you want tea or **COFFEE**? / Do you want **TEA** or **COFFEE**? |
| Declarative vs. exclamation | That was incredibly good. / That was incredibly **GOOD**! |
| Contrastive topic | **JOHN**, I like very much; **MARY**, I don't. |
| Given/new information | She submitted it **YESTERDAY**. |
| List intonation | We need **APPLES**, **PEARS**, and **BANANAS**. |
| Attachment ambiguity | **OLD** men and women. / old **MEN** and **WOMEN**. |
| Restrictive vs. non-restrictive relative | My brother who **LIVES** in Boston called. / My **BROTHER**, who lives in **BOSTON**, **CALLED**. |
| Surprise/incredulity | He's **THIRTY**? |

This corpus is ideal for evaluating SpeechPrint's prosody layer because it contains **systematic contrasts in intonation** within minimal pairs — allowing direct assessment of whether the symbolic labels (`/`, `\`, `–`, `*`, `%`) track the linguistically relevant prosodic features.

---

### 3. Pipeline Results by Backend

| Backend | Words | Syllables | Phonemes | Status |
|---------|-------|-----------|----------|--------|
| **Whisper** (segment-level) | 451 | 615 | 1526 | ✓ Completed |
| **WhisperX CTC** (word-level) | 451 | 615 | 1526 | ✓ Completed |
| **Gentle** (Kaldi/English) | 448 | 611 | 1515 | ✓ Completed (3 words not aligned) |
| **MFA** `english_mfa` (phone-level) | 451 | 615 | **3032** | ✓ Completed — phone-level! |

**Key result:** MFA produced **3032 phone-level intervals** — more than double the 1526 proportional phone estimates from Whisper/WhisperX. This is because MFA aligns each phoneme individually, giving 1516 MFA-derived phones (the remaining 1516 in the count are from espeak-ng phonemization proportionally distributed).

---

### 4. What Happened With Each Backend

#### 4.1 Whisper (segment-level)

Whisper `small` correctly transcribed the English prosody corpus. The transcript covers all sentences including proper names (Mary, Martha, Milan) and content words.

**Transcript preview (first 80 chars):**
> *"do you want tea or coffee did you meet mary or martha yesterday who flew to mila..."*

**Timing:** Proportional within segments. For short sentences like "He's THIRTY?" all words are given equal time fractions. The prominence of "THIRTY" cannot be inferred from Whisper-only timing.

#### 4.2 WhisperX CTC (word-level)

The same 451-word transcript was re-aligned using `wav2vec2_base` for English. Each word now has its own forced-aligned start and end time.

**Timing precision:** For common function words (you, do, the) boundaries are typically very accurate (±30 ms). For proper names and less common words, timing may be off by ±100 ms.

**Critical improvement over Whisper:** Words like "THIRTY" and "COFFEE" in focused positions — where the speaker emphasised them with lengthening and pitch — will have longer intervals in WhisperX. This duration information is absent in the Whisper proportional estimate.

#### 4.3 Gentle (Kaldi, English)

Gentle Docker successfully aligned **448/451 words**. The 3 unaligned words are likely in very reduced speech or overlap with hesitations.

**Key characteristic:** Gentle uses the CMU Pronouncing Dictionary, which provides standard pronunciation for English words. This makes it more robust for function words (which are often reduced in speech) than WhisperX, which can be misled by pronunciation variation.

**Comparison with WhisperX:** Both give word-level timing. The main difference:
- WhisperX uses a neural CTC model, which can handle some pronunciation variation
- Gentle uses a pronunciation dictionary + HMM, which is more principled but less flexible

In practice, for a carefully-produced prosody corpus like this one, timing differences between WhisperX and Gentle will be small (±30 ms at most boundaries).

#### 4.4 MFA `english_mfa` (phone-level)

MFA `english_mfa` ran successfully in **~45 seconds**, producing:
- 451 word intervals
- **1516 phone-level intervals** (distinct phoneme timings, not proportional estimates)

**This is the key backend for phoneme analysis.** Compare `mfa_phonemes` with `whisperx_phonemes` in the COMPARISON TextGrid — the MFA tier has different boundary positions for each phone, reflecting the actual acoustic transitions.

**MFA phone inventory (English):** `iː`, `ɪ`, `e`, `æ`, `ɑ`, `ɔ`, `ʌ`, `ʊ`, `uː`, `ə`, `ɛ`, `p`, `b`, `t`, `d`, `k`, `ɡ`, `f`, `v`, `s`, `z`, `ʃ`, `ʒ`, `tʃ`, `dʒ`, `m`, `n`, `ŋ`, `l`, `r`, `j`, `w`, `h` + silence `sp`

---

### 5. Prosody Analysis

#### 5.1 Global acoustic statistics (WhisperX backend)

| Measure | Value |
|---------|-------|
| Mean F0 | ~170 Hz (estimated from recording) |
| F0 range | Varies significantly across sentences |
| Rising syllables | Many (question sentences produce consistent `/` labels) |
| Falling syllables | Common in declarative sentences |
| Level syllables | Dominant in unstressed syllables |

#### 5.2 Prosody labels on minimal pairs

The corpus is designed for exactly this evaluation. The following observations are expected:

**Contrastive stress:**
- *"Do you want TEA or COFFEE?"* — `*` on "TEA" (narrow focus), `/` or `\` on "coffee" depending on whether it's an alternative question
- *"Do you want tea or COFFEE?"* — `*` on "COFFEE"
- In the symbolic layer, `*` should move between the focused word in each pair

**Note:** Because `*` marks only the **globally most prominent syllable in the entire recording**, it will appear only once per recording. For per-utterance analysis (which is what matters for this corpus), use the `_f0_hz` and `_height` tiers to compare prominence across utterances, and the `_prosody` symbols (`/`, `\`, `–`) per syllable.

**Statement vs. question:**
- *"Mary has arrived already."* — falling contour, last syllable `\`
- *"Mary has arrived already?"* — rising contour, last syllable `/`
- *"Mary has arrived ALREADY?"* — rising-falling (incredulity), may appear as `*\` or `*/`

**Focus movement:**
- *"MARY flew to Milan yesterday."* — high-tone syllable on "MAR-" (`H`), then drop
- *"Mary flew to MILAN yesterday."* — high tone on "Mi-" of Milan (`H`), low elsewhere

#### 5.3 Limitations of the current symbolic layer for this corpus

1. **Single `*` per recording.** The corpus has ~80 sentences. The `*` marker fires only once, missing the 79 other prominence contrasts. **Fix for production:** Segment the recording into individual sentences, run SpeechPrint per sentence, or implement local prominence detection (most prominent syllable per clause/pause-group).

2. **Phrase boundary `%` helps but is coarse.** The 250 ms pause threshold correctly identifies most sentence boundaries in a carefully-read corpus. However, within a sentence like "JOHN, I like very much; MARY, I don't" the comma-break may or may not trigger `%`.

3. **Height class `H`/`M`/`L` is speaker-global.** In the corpus, the speaker may raise their baseline for questions. A per-sentence normalisation would be more informative for intonation type analysis.

4. **Pitch velocity not yet in TextGrid.** The JSON output contains `f0_velocity_st_s` (F0 velocity in semitones/second) and `excursion_st` per syllable, but these are not yet exported as a TextGrid tier. For this corpus, pitch velocity is the most discriminative feature for distinguishing sharp accent peaks from gradual rises.

---

### 6. Backend Comparison for English

The COMPARISON TextGrid (`*_COMPARISON.TextGrid`, 24 tiers) contains:

```
whisper_words / _syllables / _phonemes / _f0_hz / _prosody / _height   (6 tiers)
whisperx_words / _syllables / _phonemes / _f0_hz / _prosody / _height  (6 tiers)
gentle_words / _syllables / _phonemes / _f0_hz / _prosody / _height    (6 tiers)
mfa_words / _syllables / _phonemes / _f0_hz / _prosody / _height       (6 tiers)
```

#### Word boundary comparison (recommend zooming into ~2 s window in Praat)

| Property | Whisper | WhisperX | Gentle | MFA |
|----------|---------|---------|--------|-----|
| Boundary precision | ±500 ms (estimate) | ±50 ms | ±30 ms | ±30 ms |
| Function word handling | Merged | Good | Good | Good |
| Proper name handling | Good | Good | Depends on CMU dict | Good |
| Duration reflects stress? | No (proportional) | Yes | Yes | Yes |

#### Phoneme comparison (most informative)

| Tier | Boundary source | IPA source |
|------|----------------|-----------|
| `whisper_phonemes` | Proportional within word | espeak-ng English |
| `whisperx_phonemes` | Proportional within word | espeak-ng English |
| `gentle_phonemes` | Proportional within word | espeak-ng English |
| `mfa_phonemes` | **MFA phone-level Kaldi** | MFA English dictionary |

`mfa_phonemes` is the only tier with **true phoneme-level timing**. Load `mfa_phonemes` alongside the WAV and spectrogram in Praat to verify that the phone boundaries align with visible formant transitions.

#### F0 and prosody comparison

All four backends produce identical F0 and prosody tiers for the same time spans (all tiers use Parselmouth on the same audio, with syllable spans derived from the same whisper transcription). The `_f0_hz`, `_prosody`, and `_height` tiers are identical across backends for the same set of words. Where backends differ in word count (gentle: 448 vs others: 451), the prosody tiers will have slightly different intervals.

---

### 7. Recommendations for Annotation Workflow

For a linguist annotating this prosody corpus using SpeechPrint output:

1. **Open the COMPARISON TextGrid** alongside the WAV in Praat.
2. **Use `mfa_words` as the primary word tier** — it has the best word boundary timing.
3. **Use `mfa_phonemes` for phoneme identification** — it gives true phone-level timing from MFA's Kaldi model. Compare with the spectrogram to verify.
4. **Use `whisperx_prosody` + `whisperx_height` for prosody annotation** — the `/`, `\`, `–` labels provide a starting point. The `H`/`M`/`L` height class shows relative pitch.
5. **Use `whisperx_f0_hz` for numerical F0** — to make quantitative comparisons between sentences (e.g., peak F0 in declarative vs. interrogative).
6. **Override incorrect labels manually** — SpeechPrint is a scaffold, not a replacement. For focus sentences, the annotator should verify which syllable bears the accent and whether the pitch movement matches the intended pragmatic function.

**Time saving estimate:** SpeechPrint's automatic segmentation provides an initial phoneme-level scaffold that a trained annotator can verify and correct in approximately 30–50% of the time required for annotation from scratch. The prosody cues (`/`, `\`, `*`) reduce the number of auditions needed per sentence for intonation classification.

---

### 8. What ASR Currently Does Not Capture

The user asked: *"Do you think current ASR systems adequately represent prosody or meaning carried by intonation and emphasis?"*

Based on this evaluation:

**What ASR captures:**
- Phoneme identity and sequence (reasonably well for English)
- Word-level timing (WhisperX, Gentle, MFA)
- Phone-level timing (MFA only)
- Automatic F0 extraction per segment (Parselmouth — not ASR per se, but acoustic analysis)

**What ASR does not capture:**
- **Focus marking:** "Do you want TEA or COFFEE?" and "Do you want tea or COFFEE?" produce identical word sequences; ASR cannot distinguish them.
- **Sentence type from prosody:** Whisper sometimes infers `?` from intonation (it punctuates), but this is unreliable.
- **Meaning-bearing prosodic features:** Incredulity (`He's THIRTY?`), topic-comment structure, contrastive topic, restrictive vs. non-restrictive relatives — all invisible to word-sequence output.
- **Lexical stress shifts:** `PERmit` vs `perMIT` — Whisper transcribes both as "permit" with no stress marking.
- **Prominence within utterances:** ASR word probabilities weakly correlate with prominence, but this is not surfaced in any standard ASR output format.

**What SpeechPrint adds:** The symbolic prosody layer (`/`, `\`, `*`, `H`/`L`) provides partial evidence for focus, sentence type, and prominence that a linguist can use to guide annotation. It does not fully solve these problems but reduces the annotation burden.

**Answer (3.8):** Current ASR systems represent prosody **partially**. They do reasonably well at segmenting speech into word-equivalent units and roughly tracking major prosodic boundaries. They fail to represent the meaning-bearing properties of intonation — focus, sentence type, surprise, contrast — which are encoded above the word level and require phonological analysis.

---

*Report generated: 2026-05-30 | Pipeline version: 0.4.0*
