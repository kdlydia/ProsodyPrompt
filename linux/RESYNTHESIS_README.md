# Prosody Resynthesis Module

Closes the bidirectional loop: **TextGrid (edited prosody) → F0 targets → Coqui TTS → Resynthesized audio**

**Status:** Chapter 6.1 implementation (design in thesis, now functional code)

**Linux-native:** Coqui TTS, pYIN, CREPE all work on Linux. No Windows dependencies.

---

## Architecture

```
┌─────────────────────────────────────────┐
│      Existing SpeechPrint Pipeline       │
│   WAV → WhisperX → MFA → pYIN/CREPE     │
└─────────────┬───────────────────────────┘
              │
              ▼
         TextGrid
    (prosody tier: /, //, \, etc.)
              │
    ┌─────────┴──────────┐
    │                    │
    ▼                    ▼
┌────────────┐    ┌──────────────┐
│   USER     │    │   PROGRAM    │
│ (Edit tier)│    │ (Algorithms) │
└────────────┘    └──────────────┘
    │                    │
    └─────────┬──────────┘
              │
              ▼
      F0Compiler
   (symbols → F0 targets)
              │
              ▼
      CoquiSynthesizer
   (F0-conditioned TTS)
              │
              ▼
         New WAV
      (with modified prosody)
```

### Components

#### **f0_compiler.py** — Symbol → F0 Logic
Maps prosody symbols to quantitative pitch targets.

**Inputs:**
- Prosody symbols: `/, //, \, \\, ‾, _, *, ?`
- Syllable timing (onset, offset)
- Speaker pitch range (Hz)

**Processing:**
1. Parse symbol components:
   - Height: `‾` (high), `_` (low), or default (mid)
   - Direction: `//` (strongly rising), `/` (weakly rising), etc.
   - Prominence: `*` (accent marker)
   
2. Compute F0 targets:
   - Onset F0 = reference_f0 ± offset_based_on_height
   - Offset F0 = reference_f0 ± shift_based_on_direction
   - Smooth transitions between syllables (max 3 semitones)
   
3. Generate smooth trajectories:
   - Rising: slow onset, fast offset
   - Falling: fast onset, slow offset
   - Level: constant F0

**Output:**
- List of `F0Target(time, hz, is_accent, confidence)` points

#### **textgrid_io.py** — TextGrid Manipulation
Read/write TextGrid files with proper format handling.

**Key methods:**
```python
TextGridReader.read(path)                    # Load TextGrid
TextGridReader.get_prosody_tier(path)        # Extract prosody layer
TextGridWriter.write(path, xmin, xmax, tiers)  # Save TextGrid
TextGridWriter.add_prosody_tier(...)         # Insert new tier
```

#### **coqui_interface.py** — TTS Synthesis
Wrapper around Coqui TTS with voice cloning.

**Features:**
- Voice cloning from reference audio (15-30s recommended)
- Glow-TTS + HiFi-GAN vocoder (native Linux support via ONNX)
- F0 control (optional: PSOLA-based pitch shifting)
- Speed adjustment (time-stretching)

**Usage:**
```python
synth = CoquiSynthesizer(device='cpu')  # or 'cuda'
speaker = synth.clone_voice("reference.wav", "speaker_name")
audio, sr = synth.synthesize(
    text="Mary flew to Milan yesterday",
    speaker_name=speaker,
    f0_targets=[100, 110, 120, ...],  # Optional
    f0_times=[0.0, 0.1, 0.2, ...],
)
synth.save(audio, "output.wav", sr)
```

#### **prosody_editor.py** — Interactive Editing
Foundation for both CLI and web-based Speech DAW.

**Workflow:**
1. Load TextGrid + extract prosody tier
2. Parse into `EditableProsodicSyllable` objects
3. User modifies symbols (interactive or programmatic)
4. Compile to F0 targets
5. Synthesize
6. Export modified TextGrid

**Key methods:**
```python
editor = ProsodyEditor("recording.TextGrid", "audio.wav")
editor.modify_symbol(0, "//")          # Change symbol
editor.modify_height(0, "high")        # Change height
editor.modify_accent(0, add=True)      # Toggle accent
targets = editor.compile_to_f0_targets()
editor.export_to_textgrid("output.TextGrid")
```

#### **utils.py** — Helpers
Utility functions:
- Semitone/Hz conversions
- F0 extraction (pYIN, CREPE, autocorrelation)
- Speaker pitch range auto-detection
- Symbol validation/parsing

---

## Usage

### Quick Start (CLI)

```bash
# Basic: interactive editing
python resynthesis_cli.py my_recording.TextGrid --audio my_recording.wav

# Batch: synthesize with modified prosody
python resynthesis_cli.py my_recording.TextGrid \
    --audio my_recording.wav \
    --mode batch \
    --output out/
```

### Interactive Commands

```
list                           Show all syllables with symbols
edit 0 //                      Change syllable 0 to "strongly rising"
accent 5                       Add accent to syllable 5
height 3 high                  Make syllable 3 "high"
direction 2 falling            Make syllable 2 "falling"
synthesize                     Full synthesis with all edits
export output.TextGrid         Save modified TextGrid
reset                          Undo all changes
quit                           Exit
```

### Python API

```python
from prosody_resynthesis import ProsodyEditor, CoquiSynthesizer
from prosody_resynthesis.f0_compiler import F0Compiler

# 1. Load and edit
editor = ProsodyEditor("recording.TextGrid", "recording.wav")
editor.modify_symbol(0, "//")  # First syllable: strongly rising
editor.modify_accent(5, add=True)

# 2. Compile to F0
targets = editor.compile_to_f0_targets(f0_floor=75, f0_ceiling=300)

# 3. Synthesize
synth = CoquiSynthesizer()
synth.clone_voice("recording.wav", "speaker")
audio, sr = synth.synthesize("Mary flew to Milan", speaker_name="speaker", f0_targets=...)

# 4. Export
editor.export_to_textgrid("output.TextGrid")
synth.save(audio, "resynthesized.wav", sr)
```

---

## Architecture: Modularity & Extension

### For Speech DAW (Web UI)

`prosody_editor.py` is designed to be the backend for an interactive timeline editor:

```python
# Backend API (Flask/FastAPI)
@app.post("/edit")
def edit_syllable(syllable_id: int, symbol: str):
    editor.modify_symbol(syllable_id, symbol)
    return editor.summary()

@app.post("/preview")
def preview_syllable(syllable_id: int):
    # Re-synthesize just this region
    targets = editor.compile_to_f0_targets()
    return synth.synthesize(...)
```

### For Other Tools

- **Prosody Classifier (Chapter 6.3):** Use compiled F0 targets as features
- **Cross-lingual Analysis:** Apply resynthesis to mis-transcribed audio
- **Articulatory Synthesis:** Replace `CoquiSynthesizer` with articulatory model

Each module is standalone and pluggable.

---

## Pitch Range Auto-Detection

If no `--f0-floor` / `--f0-ceiling` specified, system auto-detects from audio:

```python
from prosody_resynthesis.utils import detect_speaker_pitch_range

audio, sr = sf.read("recording.wav")
f0_floor, f0_ceiling = detect_speaker_pitch_range(audio, sr)
# e.g., (75.2, 298.4) for typical adult speaker
```

Uses F0 quartiles (Q1, Q3) with 10% safety margin.

---

## F0 Compiler: Parametric Model Details

### Symbol Components

| Component | Options | Effect |
|-----------|---------|--------|
| Height | `‾` (high), `_` (low), none (mid) | Onset F0 ± ~25% of range |
| Direction | `//` (strong ↑), `/` (weak ↑), `\\` (weak ↓), `\\\\` (strong ↓), none (→) | Offset F0 shift ±5 or ±2 semitones |
| Accent | `*` | Boost onset F0 by ~15% |
| Voicing | `?` | Confidence = 0.0 (for synthesis routing) |

### F0 Computation

```
onset_f0 = reference_f0 × (1 + height_offset) × (1 + accent_boost)
offset_f0 = reference_f0 × 2^(direction_shift_semitones / 12)

Smooth transition (max 3 ST jump between syllables)
Trajectory shape based on direction (rising/falling/level)
```

---

## Dependencies

**Core:**
- `numpy`, `scipy` (math)
- `textgrid` (if needed; custom parser used here)
- `soundfile`, `sounddevice` (audio I/O)

**For Synthesis:**
- `TTS` (pip install TTS) — Coqui framework
- `torch`, `torchaudio` (inference)

**Optional (for F0 extraction):**
- `librosa` (pYIN, autocorrelation)
- `torchcrepe` (CREPE pitch tracker)

**Optional (for pitch shifting):**
- `pyrubberband` (full PSOLA support; currently fallback to librosa)

---

## Examples

### Example 1: Simple Resynthesis

```python
from prosody_resynthesis import ProsodyEditor, CoquiSynthesizer

# Load and modify
editor = ProsodyEditor("english_minimal_pairs.TextGrid", "english.wav")

# Make focus shift: accent moves from "MARY" to "MILAN"
editor.modify_symbol(0, "/")      # "MARY": weakly rising
editor.modify_symbol(8, "*//")    # "MILAN": accented, strongly rising

# Compile and synthesize
targets = editor.compile_to_f0_targets()
synth = CoquiSynthesizer()
synth.clone_voice("english.wav", "speaker")
audio, sr = synth.synthesize(
    "Mary flew to Milan yesterday",
    speaker_name="speaker",
    f0_targets=[t.f0 for t in targets],
)

# Export
editor.export_to_textgrid("modified.TextGrid")
synth.save(audio, "resynthesized.wav", sr)
```

### Example 2: Batch Processing

```python
import glob
from prosody_resynthesis import ProsodyEditor

for tg_path in glob.glob("corpora/*.TextGrid"):
    editor = ProsodyEditor(tg_path)
    
    # Apply systematic change (e.g., raise all accents)
    for syl in editor.syllables:
        if '*' in syl.current_symbol:
            editor.modify_height(syl.index, 'high')
    
    # Export
    output = f"modified/{Path(tg_path).name}"
    editor.export_to_textgrid(output)
```

---

## Testing

```bash
cd linux
python -m pytest test_resynthesis.py -v
```

Test coverage:
- F0 compiler: symbol parsing, pitch computation, transitions
- TextGrid I/O: read, write, tier manipulation
- Editor: load, modify, export
- Utils: conversions, F0 extraction, pitch range detection

---

## Performance

| Component | Speed | Notes |
|-----------|-------|-------|
| Symbol compilation (100 syllables) | <100ms | Pure Python, vectorized |
| F0 extraction (5s audio) | ~1-2s (pYIN CPU) | Depends on audio length |
| Voice cloning (15s ref) | ~30s (first time, CPU) | Speaker embedding cached |
| Synthesis (15s) | ~10-20s (CPU) | Glow-TTS + vocoder |
| TextGrid I/O | <10ms | Regex-based parsing |

Total workflow: ~60s for 15s audio on CPU (one-time setup + synthesis).

---

## Future Extensions

1. **Speech DAW (Web UI)** — React timeline editor + WebSocket synthesis
2. **Real-time Preview** — Synthesize on each edit (currently per-utterance)
3. **Pitch Shift PSOLA** — Full Pitch Synchronous Overlap Add (currently basic)
4. **Multi-speaker** — Blend between cloned voices
5. **Articulatory Control** — Replace Coqui with VocalTractLab (Linux-compatible fork TBD)
6. **Prosody Classifier** — Auto-label from F0 targets (Chapter 6.3)

---

## References

- **Thesis Chapter 6.1:** Prosody Resynthesis design, DrawSpeech integration
- **Coqui TTS:** https://github.com/coqui-ai/TTS
- **pYIN:** Librosa implementation of Probabilistic YIN F0 estimation
- **Glow-TTS:** Mockingjay et al., "Glow-TTS: A Generative Flow for Text-to-Speech..."

