# SpeechPrint: Vision vs Implementation Gap

A comprehensive audit of what's envisioned in the thesis vs what's currently implemented.

---

## ✅ FULLY IMPLEMENTED (Current Pipeline)

### Analysis Direction (One-way: Audio → Annotation)

**Pipeline:** WAV → WhisperX → MFA/hardcoded IPA → {pYIN|CREPE|PESTO|Praat AC|YIN} → TextGrid

**Components:**
- [x] Transcription: WhisperX large-v3 (English, German, multilingual)
- [x] Forced alignment: MFA (English phone-level), WhisperX CTC (other languages), proportional fallback
- [x] Phonemization: espeak-ng with max-onset syllabification
- [x] Pitch extraction: 5 trackers (pYIN, CREPE, PESTO, Praat AC, YIN)
- [x] Algorithmic optimizations (5):
  - MAD-based adaptive thresholds
  - Utterance boundary reset
  - Pitch declination removal
  - Nucleus edge trimming (15%)
  - Octave error correction (Xu 1999)
- [x] Symbolic prosody layer: 7 symbols (/, //, \, \\, ‾, _, *, ?)
- [x] TextGrid output with 7+ tiers (words, phones, syllables, prosody, etc.)
- [x] CSV/JSON export per-word, per-syllable, per-phoneme

**Testing & Evaluation:**
- [x] Pitch tracker comparison (5 methods × 3 corpora)
- [x] GToBI benchmark (German reference sentences)
- [x] English minimal-pairs evaluation
- [x] Endangered language testing (Daakie, Cabécar DoReCo corpora)
- [x] 238 octave errors identified and corrected in Praat AC

**User Interface:**
- [x] Interactive CLI (no GUI yet)
- [x] 4-option main menu
- [x] Question-based workflow
- [x] Tracker comparison mode (multiple prosody tiers)

---

## 🟡 PARTIALLY IMPLEMENTED / SKETCHED

### Batch Processing & CLI Commands (Appendix D)

**Mentioned in thesis:**
```bash
uv run python -m speechprint batch --input-dir ...
uv run python -m speechprint export --textgrid ... --format csv
uv run python -m speechprint evaluate-gtobi --sentences-dir ...
```

**Actual status:**
- [x] Batch processing works via `build_questionnaire_v3.py`, `build_doreco_speechprint.py`, etc.
- [ ] Formal `speechprint` CLI entry points not fully unified
- [x] CSV export implemented in build scripts
- [x] GToBI evaluation available via `build_questionnaire_v3.py`

**Missing:** Clean pip-installable CLI commands. Users must run scripts directly in `linux/` directory.

---

## ❌ ENVISIONED BUT NOT IMPLEMENTED

### 1. Prosody Resynthesis (Chapter 6.1, Figure 6.1)

**Vision:** Close the loop—users can edit prosody symbols in TextGrid and hear the result without re-recording.

**Proposed implementation:**
- TextGrid (edited symbols) → F0 target compiler → Coqui TTS/XTTS → Resynthesized WAV
- Coqui XTTS supports voice cloning from 30s reference + prosodic control
- Map symbolic labels (/, //, \, etc.) to F0 targets at word/syllable boundaries

**Status:** Design concept only. No code written.

**What exists:**
- ✓ TextGrid with editable prosody tier
- ✓ Symbol→F0 mapping logic partially sketched in thesis (lines 146–162)
- ✗ Coqui integration
- ✗ Real-time synthesis on edit
- ✗ Voice cloning workflow

**Effort to implement:** ~1–2 weeks (Coqui API integration + F0 target compiler + validation)

---

### 2. Speech Digital Audio Workstation (Chapter 6.2)

**Vision:** A GUI timeline editor (like music DAW) where users can:
- Click syllables to change prosody symbols
- Drag pitch movement onset/offset
- Toggle accent markers (*)
- Switch between ‾ (high) and _ (low)
- Get **real-time auditory feedback** on each edit

**Proposed architecture:**
- TextGrid as editable timeline representation
- Each syllable interval is a MIDI-like node
- Edits trigger re-synthesis of affected region
- Non-specialist-friendly: operate at symbolic level, not acoustic F0 curves

**Status:** Mockup/design concept only. No UI code.

**What exists:**
- ✓ TextGrid with prosody tier
- ✓ Symbolic representation suitable for this interface
- ✗ GUI framework (GTK4, web-based, or Electron)
- ✗ Timeline rendering
- ✗ Real-time re-synthesis on edit

**Comparison:** Praat allows acoustic F0 manipulation (expert-level). Speech DAW targets linguists and field workers (symbolic level).

**Effort to implement:** ~3–4 weeks
- Web UI (React): ~2 weeks
- Real-time synthesis integration: ~1 week
- User testing & refinement: ~1 week

---

### 3. Automatic Prosody Classification (Chapter 6.3)

**Vision:** Assign utterance-level labels (not per-syllable) to speed up annotation workflows.

**Proposed categories:**
1. **Declarative** - Statement with final fall
2. **Interrogative** - Yes/no question with final rise
3. **Narrow focus** - Single prominent word (contrast/correction)
4. **Continuation** - Non-final phrase (more speech follows)
5. **Exclamation** - Emphatic, high onset + rapid fall

**Training approach:**
- Use GToBI-annotated corpora (boundary tones: H%, L%, H-%, L-%)
- Extract features: mean F0, F0 range, final boundary slope, median amplitude
- Train classifier (SVM, Random Forest, or neural net) on hand-annotated sentences

**Status:** No code written. Design concept only.

**What exists:**
- ✓ Per-syllable prosody labels
- ✓ F0 and amplitude extraction already available
- ✗ Feature engineering for utterance-level classification
- ✗ Labeled training data for these 5 categories
- ✗ Classifier implementation

**Effort to implement:** ~1–2 weeks (once training data is prepared)

---

### 4. Bias & Cross-Lingual Phonological Approximation (Chapter 6.4)

**Vision:** Understand how speech models project their learned phonology onto unsupported languages, creating systematic (not random) error patterns.

**Observation:** When Whisper's Italian model hears Daakie, it returns phonetically plausible Italian word sequences, not noise. This reveals the model's phonological priors.

**Proposed research directions:**
- Map the gap between what a model hears vs what was said
- Compositional space at intersection of speech tech + sound art
- Apply SpeechPrint to cross-lingual inputs to visualize these projections

**Status:** Theoretical framework only. No implementation.

**What exists:**
- ✓ Daakie recordings processed with Italian Whisper (in appendices)
- ✓ Documented in thesis as example of systematic bias
- ✗ Systematic analysis framework
- ✗ Visualization tools
- ✗ Research methodology

**Effort to implement:** Open-ended research (~ongoing, not a shipping feature)

---

## 🎨 PROTOTYPE: Prosody Synthesis Toolkit (Appendix E)

**Status:** Design sketch with example CLI commands. Prototype code mentioned but not complete.

**Proposed tools:**

### `prosody2tract.py`
Convert TextGrid prosody tier → VocalTractLab articulatory synthesis

```bash
python prosody2tract.py recording.TextGrid --f0-floor 85 --f0-ceiling 300
```

**Intended use:** Close loop between symbolic prosody and articulatory synthesis

**Dependencies:**
- TensorTract2 (articulatory forward model)
- VocalTractLab (Windows only, requires license)
- PESTO pitch tracker
- SciPy, SoundFile

**Status:** 
- [x] Described in thesis
- [ ] Code not in repo or incomplete
- ✗ Only works on Windows (VocalTractLab limitation)

---

### `audio2tract.py`
Audio-to-articulatory inversion with parameter manipulation

```bash
python audio2tract.py my_audio.wav -m TCX multiply 1.5 -m f0 set 150
```

**Intended use:** Modify articulation (tongue constriction, F0, pressure) and re-synthesize

**Status:**
- [x] Described in thesis (lines 633–660)
- [ ] Code not in repo
- ✗ Requires TensorTract, Windows/VocalTractLab

---

### `prosody_morph.py`
Blend prosody/articulation between two speakers

```bash
python prosody_morph.py --prima speaker_a.wav --secunda speaker_b.wav --blend 0.5
```

**Status:**
- [x] Described in thesis
- [ ] Code not in repo
- ✗ Research prototype only

---

### Movement Generators
Smooth/stochastic/chaotic parameter trajectories (linear, sigmoid, ease-in-out, Lorenz, Gendy/Xenakis-style stochastic)

**Status:**
- [x] Defined in thesis (Table in Appendix E)
- [ ] Code skeleton exists? (Not verified)
- [ ] Integration with tract-sequence complete? (Unknown)

---

## 📊 Implementation Gap Summary

| Component | Status | Effort | Notes |
|-----------|--------|--------|-------|
| **Analysis pipeline** | ✅ Complete | — | Fully working, reproducible |
| **GToBI evaluation** | ✅ Complete | — | 5 German reference sentences |
| **Pitch tracker comparison** | ✅ Complete | — | All 5 trackers tested |
| **Endangered language** | ✅ Complete | — | Daakie, Cabécar, Kakabe |
| **CLI batch processing** | 🟡 Partial | 1 day | Scripts work; formal CLI entry points missing |
| **Prosody resynthesis** | ❌ Not done | 1–2 weeks | Coqui TTS integration needed |
| **Speech DAW GUI** | ❌ Not done | 3–4 weeks | Timeline editor + real-time synthesis |
| **Prosody classifier** | ❌ Not done | 1–2 weeks | Training data + classifier |
| **Cross-lingual bias analysis** | ❌ Not done | Open-ended | Research framework only |
| **Prosody synthesis toolkit** | ❌ Not done | 2–3 weeks | TensorTract, articulatory models, VocalTractLab (Windows) |
| **Movement generators** | ❌ Not done | 1 week | Stochastic/chaotic trajectory shapes |

---

## 🎯 Priority Order for Future Work

### Immediate (1–2 weeks)
1. **Unified CLI** - Make `prosodyprompt batch`, `prosodyprompt export`, etc. work
2. **Prosody resynthesis** - Add Coqui TTS integration (highest payoff for users)

### Near-term (3–4 weeks)
3. **Speech DAW prototype** - Web UI for interactive editing + real-time synthesis
4. **Prosody classifier** - Utterance-level labels to speed annotation workflows

### Future (Research)
5. **Cross-lingual bias analysis** - Formalize and visualize phonological projection
6. **Articulatory synthesis** - Prosody→articulation→audio loop (Windows/VocalTractLab constraint)

---

## 📝 What the Thesis Promises vs Delivers

**Thesis frame:**
- Positions SpeechPrint as the *analysis* half of a bidirectional loop
- DrawSpeech cited as proof-of-concept for synthesis half
- Speech DAW as natural next step

**Current delivery:**
- ✅ Analysis side: fully functional, reproducible, well-documented
- ⚠️ Synthesis side: design sketches only, no working code
- ⚠️ GUI: interactive CLI only (GTK4 GUI planned but not implemented)

**For thesis submission:**
- Appendices A–C show working analysis results ✓
- Appendix D documents installation ✓
- Appendix E is aspirational ("prototype status", "design concept") ✓ (This is okay — future directions are expected)

**For GitHub release:**
- All analysis code is reproducible ✓
- Build scripts are versioned and documented ✓
- Synthesis toolkit is incomplete (mention in README as "future work") ✓

---

## 🔗 Linkage Between Thesis & Code

**Appendix A (English minimal pairs):**
- ✓ Script: `build_questionnaire_v3.py`
- ✓ Output: `out/questionnaire_v3/questionnaire_v3.TextGrid`
- ✓ Reproducible

**Appendix B (German GToBI):**
- ✓ Script: `build_questionnaire_v3.py` (same)
- ✓ Results: Table 5.6–5.8 in ch5
- ✓ Reproducible

**Appendix C (Daakie, Cabécar):**
- ✓ Scripts: `build_doreco_speechprint.py`, `build_cabeca.py`
- ✓ Outputs: `out/FINAL_doreco_speechprint_pyin.TextGrid`, etc.
- ✓ Reproducible

**Appendix D (Installation):**
- ✓ Reference: `docs/LINUX.md`
- ✓ Updated and working

**Appendix E (Prosody synthesis):**
- ✓ Design documented
- ⚠️ Code mostly missing
- ✗ Not reproducible in current form
- ⚠️ This is fine for a thesis (future work section)

---

## Recommendation for Your Use

**For thesis submission:** Current state is complete. Appendices show what's implemented + what's envisioned. No missing content.

**For GitHub release:** Add a **"Future Directions"** section to README pointing to Chapter 6 and Appendix E. Make clear:
- Analysis pipeline is production-ready
- Synthesis toolkit and Speech DAW are design concepts for future work
- Contributors welcome to implement these

**Example README section:**
```markdown
## Future Directions

See Chapter 6 of the thesis for detailed discussion of:
- Prosody resynthesis (bidirectional loop with Coqui TTS)
- Speech DAW (interactive timeline editor with real-time synthesis)
- Automatic prosody classification (utterance-level labels)
- Cross-lingual phonological approximation

Appendix E outlines a prototype prosody synthesis toolkit 
(articulatory control via TensorTract). This requires Windows/VocalTractLab.
```

