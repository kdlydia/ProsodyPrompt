# Build Scripts for Thesis Appendices

These scripts reproduce the results shown in the thesis appendices. All scripts are in `linux/` directory.

## Appendix A: English Minimal-Pair Corpus

**Script:** `build_questionnaire_v3.py`

Generates prosody annotations for the English minimal-pairs corpus (305.5s, 82 sentences).

```bash
cd linux
python build_questionnaire_v3.py
```

**Output:**
- `out/questionnaire_v3/questionnaire_v3.TextGrid` - Main output with prosody tiers
- Tables in Appendix A (minimal-pair examples with F0 values and symbols)
- Test data for GToBI evaluation

**Configuration:**
- Input: `audio_2026-05-30_19-01-35.wav`
- Transcription: WhisperX (large-v3)
- Pitch tracker: Librosa pYIN
- Optimisations: All 5 (MAD threshold, utterance reset, declination, nucleus trimming, octave recovery)

---

## Appendix B: German GToBI Sentences

**Script:** `build_questionnaire_v3.py` (same script, includes GToBI sentences)

Generates the 5 GToBI reference sentences used for evaluation (Section 5.4, Table 5.6–5.8).

```bash
cd linux
python build_questionnaire_v3.py
# Output includes: out/questionnaire_v3/ with GToBI results
```

**Input sentences:**
- "eine gelbe Banane" (a yellow banana)
- "einige Melonen" (some melons)
- "er sang die Lieder" (he sang the songs)
- "er will die Rosen haben" (he wants to have the roses)
- "ich wohne in Bern" (I live in Bern)

**Output in thesis:**
- Table 5.6: Pitch tracker comparison (pYIN, CREPE, Praat AC, YIN, PESTO)
- Section 5.4.2–5.4.4: GToBI benchmark results (v3 baseline, intermediate CREPE, final pYIN+optimisations)

---

## Appendix C: Daakie (DoReCo) Corpus

**Script:** `build_doreco_speechprint.py`

Generates annotations for Daakie endangered language (DoReCo corpus).

```bash
cd linux
python build_doreco_speechprint.py
```

**Output:**
- `out/FINAL_doreco_speechprint_pyin.TextGrid` - Prosody annotations
- Appendix C tables: pitch tracker comparison, language-specific results

**Configuration:**
- Input: Daakie recording with human phone-level annotation (@TA tier)
- Pitch tracker: CREPE (more robust for endangered languages)
- Optimisations: All 5
- No ASR: uses human-annotated phonetic segmentation

**Related:** `build_kakabe.py` - Similar pipeline for Kakabe variant

---

## Appendix C: Cabécar (DoReCo) Corpus

**Script:** `build_cabeca.py`

Generates annotations for Cabécar endangered language (81.8s, 28 utterances, 431 syllables).

```bash
cd linux
python build_cabeca.py
```

**Output:**
- `out/cabeca/cabeca.TextGrid` - Prosody annotations
- Section 5.5.1: Pitch tracker comparison table
- Language-specific prosody distribution (21.0% rising, 18.8% falling)

---

## Evaluation Scripts

**`pitch_tracker_comparison.py`**

Low-level comparison of all 5 pitch trackers (pYIN, CREPE, PESTO, Praat AC, YIN) on the same audio.

```bash
cd linux
python pitch_tracker_comparison.py data/recording.wav
```

Outputs comparison plots and per-frame F0 differences.

**`evaluate_aligners.py`**

Tests forced alignment quality for MFA, Gentle, WhisperX on benchmark sentences.

```bash
cd linux
python evaluate_aligners.py
```

---

## Prosody Synthesis Toolkit (Appendix E)

**Scripts:** `export_to_pink_trombone.py`

Converts ProsodyPrompt TextGrid annotations to Pink Trombone format for articulatory visualization.

```bash
cd linux
python export_to_pink_trombone.py recording.TextGrid
```

**Related future work:**
- `prosody2tract.py` (Appendix E example) - Proposed prosody→vocal-tract control
- `audio2tract.py` (Appendix E) - Inverse: audio→articulation→modification

These are design sketches in the thesis; implementations are TBD.

---

## Running All Builds (Batch)

To regenerate all appendix results:

```bash
cd linux
python build_questionnaire_v3.py    # Appendices A, B
python build_doreco_speechprint.py  # Appendix C (Daakie)
python build_kakabe.py              # Appendix C (Kakabe variant)
python build_cabeca.py              # Appendix C (Cabécar)
```

Expected runtime: ~30–60 minutes depending on GPU availability.

---

## Notes for Reproducibility

1. **GPU optional**: Scripts auto-detect CUDA. Falls back to CPU.
2. **Model downloads**: First run downloads WhisperX, CREPE, MFA models (~2–3 GB).
3. **Audio files**: Included in repo:
   - `audio_2026-05-30_19-01-35.wav` (English, 305.5s)
   - `doreco_port1286_2017_06_30_Jaklin.wav` (Daakie, ~14MB)
   - `doreco_cabeca.wav` (Cabécar, ~14MB)
4. **TextGrid output**: Stored in `linux/out/` with corpus-specific subdirectories.
