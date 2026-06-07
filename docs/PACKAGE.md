# SpeechPrint Package & Configuration Guide

Comprehensive reference for dependencies, installation details, corpus configuration, and development.

---

## What Gets Installed

### SpeechPrint Toolchain

- **Core pipeline** - `speechprint_pkg` (Python 3.11 package, steps 1–10)
- **CLI tool** - `speechprint` (annotation, ensemble, NMF extensions)
- **Templates** - Corpus scaffolds for new projects
- **CMake-style discovery** - Automatic environment variable resolution via `speechprint --config`

### Language & Runtime Tools

- **Python 3.11+** - Pipeline runtime
- **Git** - Version control (for AUR / COPR installs)
- **uv** - Optional fast dependency resolver
- **7-Zip / tar** - For model archive extraction

### Audio Processing (Required)

- **ffmpeg 6+** - Resampling, channel conversion, format normalization
  - libavcodec, libavformat, libavutil, libswresample
- **Praat 6.4+** - Phonetic analysis engine
  - Bundled `praat` binary, called by Parselmouth
- **libsndfile 1.2+** - WAV/FLAC/OGG read backend

### Speech Recognition (Required)

- **WhisperX** - Word-level ASR with forced alignment
  - PyTorch 2.1+ (CPU or CUDA build)
  - Faster-Whisper backend
  - `large-v3` default model (~1.5 GB, downloaded on first use)

### Forced Alignment (Required)

- **Montreal Forced Aligner (MFA)** - Phoneme-level alignment
  - Kaldi-based acoustic models
  - Per-language dictionaries (CMU, GlobalPhone, custom)
- **Acoustic models** (per language):
  - `english_mfa`, `german_mfa`, `italian_mfa`, `spanish_mfa`, `french_mfa`, `czech_mfa`
- **Dictionaries** (per language): same suffixes

### Prosody & Acoustics (Required)

- **Parselmouth** - Python bindings to Praat
- **librosa** - Audio feature extraction
- **scipy / numpy** - Numerical backbone
- **pandas** - Tabular output (CSV, JSON)

### Export & Interop (Required)

- **pympi-ling** - ELAN `.eaf` writer
- **textgrid** - Praat `.TextGrid` writer
- **matplotlib** - Spectrograms, F0 contours, formant plots

### Platform-Specific Audio Backends

- **Windows** - WASAPI (built into Windows, no separate install needed)
- **macOS** - Core Audio (system library)
- **Linux** - ALSA / PulseAudio / PipeWire (whichever is present)

**All of these are required.** There are no "optional" dependencies in the SpeechPrint annotation pipeline. Every package listed above is necessary for end-to-end annotation. Extensions (NMF, ensemble exporters) layer on top.

---

## Installation Directory Layouts

### macOS

```
/Library/SpeechPrint/             - SpeechPrint CLI tool and templates
  └── templates/
      ├── corpus.toml
      ├── README.md
      ├── data/.gitkeep
      └── vscode/
/Applications/SpeechPrint.app     - SpeechPrint corpus creator GUI
~/.local/bin/speechprint          - Symlink to CLI tool
~/.zshenv                         - Environment variables (sources Homebrew SpeechPrint env)

# SpeechPrint location (set by Homebrew, varies):
# Usually: /opt/homebrew/opt/speechprint/ (Apple Silicon)
# Or:      /usr/local/opt/speechprint/ (Intel)
# Or:      /Library/SpeechPrint/ (if installed separately)

# MFA cache:
# ~/Documents/MFA/  (Montreal Forced Aligner default)
```

### Windows

```
C:\SpeechPrint\
├── bin\                          - Executables and shims
│   ├── speechprint.exe
│   ├── praat.exe
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   └── ...
├── lib\                          - Python packages
│   ├── speechprint_pkg\
│   ├── whisperx\
│   ├── montreal_forced_aligner\
│   └── parselmouth\
├── share\
│   └── speechprint\
│       ├── templates\
│       └── scripts\
│           ├── install_package.ps1
│           └── packages.psd1
└── mfa\                          - MFA model cache
    ├── pretrained_models\
    │   ├── acoustic\
    │   │   ├── english_mfa.zip
    │   │   ├── italian_mfa.zip
    │   │   └── ...
    │   └── dictionary\
    └── temporary\

C:\Python311\                     - Embedded Python runtime

C:\Program Files\...              - Build tools and audio libraries
├── 7-Zip\                        - Archive extraction
└── ...
```

### Linux

```
~/.local/SpeechPrint-X.X.X/       - SpeechPrint application
├── lib/
│   ├── main.py
│   ├── cli.py
│   ├── config.py
│   ├── modes/
│   ├── ui/
│   └── templates -> ../templates
├── scripts/
│   ├── create_corpus.sh
│   ├── install_deps.sh
│   └── build_distribution.sh
├── SpeechPrint                   - Launcher script
└── speechprint-config.json

~/.local/bin/speechprint          - Symlink to SpeechPrint launcher

~/SpeechPrint/                    - SpeechPrint toolchain (or via package manager)
├── bin/
├── lib/
│   └── speechprint_pkg/
├── share/
│   └── speechprint/
│       └── templates/
└── mfa/                          - MFA model cache
    ├── pretrained_models/
    └── temporary/

# OR installed via package manager:
# Arch: /usr/lib, /usr/share (from speechprint-bin AUR)
# Fedora: /usr/lib64, /usr/share (from speechprint COPR)
```

---

## Environment Variables

SpeechPrint automatically sets these during installation:

| Variable             | Value                                  | Purpose                                 |
| -------------------- | -------------------------------------- | --------------------------------------- |
| `SPEECHPRINT_ROOT`   | Installation directory (see layouts)   | Toolchain root for discovery            |
| `MFA_ROOT_DIR`       | `$SPEECHPRINT_ROOT/mfa`                | Montreal Forced Aligner cache location  |
| `WHISPERX_MODEL`     | `large-v3`                             | Default WhisperX model size             |
| `PATH`               | Includes SpeechPrint `bin/` directory  | CLI tools and audio executables         |
| `PYTHONPATH`         | Includes `$SPEECHPRINT_ROOT/lib`       | Pipeline package import path            |

**To reload after installation (without restarting):**

```bash
# macOS/Linux
source ~/.zshenv
# or
source ~/.bashrc

# Windows
# Close and reopen PowerShell/CMD
```

---

## Generated Corpus Structure

Users receive this structure when creating a new corpus:

```
MyCorpus/
├── corpus.toml                   # Corpus-wide configuration
├── README.md                     # Corpus documentation
├── .gitignore                    # Version control exclusions
├── .vscode/                      # VS Code configuration (optional)
│   ├── settings.json             # Python language server and formatting
│   ├── tasks.json                # Tasks (Annotate, Ensemble, Export)
│   └── launch.json               # Debug launch configurations
├── data/                         # Drop your WAV files here
│   └── .gitkeep
└── out/                          # Annotation outputs (auto-populated)
    └── .gitkeep
```

### Key Files to Edit

- **`corpus.toml`** — Define corpus defaults:
  - Default language (`en`, `de`, `it`, `es`, `fr`, `cs`, ...)
  - Speaker sex default (`M`, `F`, `U`)
  - Pitch floor / ceiling (override per-recording in filenames)
  - Output formats (`textgrid`, `eaf`, `csv`, `json`)

- **`data/`** — Drop WAV files here. Naming convention:
  - `<speaker>_<style>_<id>.wav` → metadata parsed automatically
  - Example: `S01_read_001.wav` → speaker=S01, style=read, id=001

- **`.vscode/settings.json`** — Adjust IDE behavior:
  - Python interpreter selection
  - Code formatting rules
  - Task discovery

---

## Configuring corpus.toml

The generated `corpus.toml` is designed to "just work" but is fully customizable.

### Setting Default Language

```toml
[defaults]
language = "it"          # en, de, it, es, fr, cs
speaker_sex = "U"        # M, F, U (unknown)
```

### Per-Recording Overrides

Recordings inherit corpus defaults; override per file via filename or front-matter:

```toml
[recordings."S01_read_001.wav"]
language = "de"
speaker_sex = "F"
pitch_floor = 75
pitch_ceiling = 500
```

### Enabling Auto-Ensemble

If you created the corpus without auto-ensemble, enable it manually:

```toml
[pipeline]
auto_ensemble = true     # Run `speechprint ensemble` after every annotate
```

Then re-run any annotation:

```bash
speechprint annotate data/recording.wav --language en
# → out/recording/ AND updated ensemble files in out/ensemble/
```

### Linking Additional Extensions

Example: Enable NMF spectral bouquet extraction on the whole corpus:

```toml
[extensions.nmf]
enabled = true
n_components = 5
fragment_duration = 4.0
```

Example: Custom dictionary path for MFA:

```toml
[mfa]
dictionary = "/path/to/custom.dict"
acoustic_model = "italian_mfa"
```

### Setting Output Formats

```toml
[export]
formats = ["textgrid", "eaf", "csv", "json"]
include_figures = true
include_intermediates = false
```

### Changing Output Directory

By default, annotations go to `out/<recording_name>/`.

To customize:

```toml
[paths]
output_dir = "annotations"    # Relative to corpus root
data_dir = "wavs"             # Relative to corpus root
```

### Advanced: Custom WhisperX Model

To use a smaller / faster model per corpus:

```toml
[whisperx]
model = "medium"              # tiny, base, small, medium, large-v2, large-v3
device = "cuda"               # cpu, cuda, mps
compute_type = "float16"      # float16, int8, float32
```

Then re-annotate:

```bash
speechprint annotate data/recording.wav --language en
```

---

## Annotating Recordings

### Command Line (All Platforms)

```bash
# Full pipeline (steps 1-10)
speechprint annotate data/recording.wav --language de

# Interactive — prompts for language at runtime
speechprint linguist data/recording.wav

# Run ensemble aggregation after manual verification
speechprint ensemble

# Inspect a single recording's outputs
ls out/recording/
```

### Using VS Code

1. **Open corpus folder** — `code .`
2. **Tasks extension** — Should auto-detect tasks.json
3. **Run annotation task** — Terminal → Run Task → "Annotate active file"
4. **Open Praat** — Press F5 with a `.TextGrid` selected
5. **View output** — Inspect `out/<recording>/` directory

### Using JetBrains / PyCharm

1. **Open folder** — File → Open → Select corpus directory
2. **Mark as Python project** — Set interpreter to `$SPEECHPRINT_ROOT/bin/python3`
3. **Run config** — Add new "shell script" → `speechprint annotate ...`
4. **Debug** — Set breakpoints in `speechprint_pkg/pipeline/`

### Using a script

```bash
# Annotate every WAV in data/ matching a pattern
for wav in data/*.wav; do
    speechprint annotate "$wav" --language it
done
speechprint ensemble
```

### Using Make (Unix-like)

```makefile
WAVS := $(wildcard data/*.wav)
ANN  := $(patsubst data/%.wav,out/%/recording.TextGrid,$(WAVS))

all: $(ANN) out/ensemble/mean_f0.csv

out/%/recording.TextGrid: data/%.wav
	speechprint annotate $< --language it

out/ensemble/mean_f0.csv: $(ANN)
	speechprint ensemble
```

---

## Cross-Platform Annotation Behavior

The pipeline handles platform differences automatically:

### macOS & Linux

- **Audio backend** - Core Audio / ALSA selected at runtime
- **MFA cache** - `~/Documents/MFA/` (macOS), `~/SpeechPrint/mfa/` (Linux)
- **No additional setup** - No need to set `PYTHONPATH` manually if `speechprint --config` resolves

Example of what's automatic:

```python
# In speechprint_pkg/pipeline/step2_audio.py
if sys.platform == "darwin":
    backend = "coreaudio"
elif sys.platform == "linux":
    backend = "alsa"
elif sys.platform == "win32":
    backend = "wasapi"
```

### Windows

- **Path handling** - Backslash / forward slash normalized at CLI boundary
- **Flat structure** - Praat, ffmpeg, and Python in `C:\SpeechPrint\bin\`
- **Portable distribution** - Zip the install folder and run on another machine (no installer needed)

Example of what's automatic:

```python
if sys.platform == "win32":
    praat_path = Path(os.environ["SPEECHPRINT_ROOT"]) / "bin" / "praat.exe"
else:
    praat_path = shutil.which("praat") or "/usr/bin/praat"
```

### Model Discovery (All Platforms)

SpeechPrint searches for MFA models in this order:

1. `MFA_ROOT_DIR` environment variable (highest priority, set by SpeechPrint)
2. Standard installation paths:
   - macOS: `~/Documents/MFA/`, `/Library/SpeechPrint/mfa/`
   - Linux: `~/SpeechPrint/mfa/`, `/usr/share/speechprint/mfa/`
   - Windows: `C:\SpeechPrint\mfa\`
3. If not found → pipeline error with helpful message and `mfa model download` suggestion

---

## Troubleshooting Pipeline Errors

### "MFA acoustic model not found" Error

**Cause:** Pipeline can't locate the MFA model for the requested language

**Check environment:**

```bash
# macOS/Linux
echo $MFA_ROOT_DIR

# Windows
echo %MFA_ROOT_DIR%
```

**If empty, reload environment:**

```bash
# macOS/Linux
source ~/.zshenv    # or ~/.bashrc
speechprint annotate ...

# Windows
# Close and reopen PowerShell/CMD completely
```

**If still missing, download the model:**

```bash
mfa model download acoustic italian_mfa
mfa model download dictionary italian_mfa
speechprint annotate data/recording.wav --language it
```

**Or pass the path directly:**

```bash
speechprint annotate data/recording.wav --language it \
    --mfa-acoustic /path/to/italian_mfa.zip \
    --mfa-dictionary /path/to/italian_mfa.dict
```

### Python Version Mismatch

**Error:** "ModuleNotFoundError: No module named 'speechprint_pkg'"

**Cause:** Python version doesn't have SpeechPrint in its `sys.path`

**Fix:** Use the bundled interpreter:

```bash
# macOS
$(brew --prefix speechprint)/bin/python3 -m speechprint_pkg.cli annotate ...

# Linux
~/SpeechPrint/bin/python3 -m speechprint_pkg.cli annotate ...

# Windows
C:\SpeechPrint\bin\python.exe -m speechprint_pkg.cli annotate ...
```

Or ensure `speechprint` CLI is on `PATH` and run it directly.

### Annotation Errors with WhisperX

**Error:** "torch.cuda.OutOfMemoryError"

**Cause:** WhisperX `large-v3` needs ~6 GB VRAM in float16

**Solution:** Use a smaller model or CPU:

```bash
# Smaller model
speechprint annotate data/recording.wav --language en --whisperx-model medium

# CPU
export CUDA_VISIBLE_DEVICES=""
speechprint annotate data/recording.wav --language en
```

---

## Contributing to SpeechPrint

Contributions welcome! See [DEVELOP.md](DEVELOP.md) for:

- Building SpeechPrint from source
- Testing on your platform
- CI/CD integration details
- Pull request guidelines
- Code style for Swift/C#/Python/Bash

---

## Key Learnings from SpeechPrint Development

1. **All dependencies are required** — There is no "optional" in the annotation pipeline. Every package listed is necessary for steps 1–10 to function.

2. **Explicit user consent** — The installer shows every step and lets users see what's happening. No background magic. Mode dialog → release dialog → step-by-step install with logs.

3. **Environment variables matter** — SpeechPrint carefully sets `SPEECHPRINT_ROOT`, `MFA_ROOT_DIR`, `WHISPERX_MODEL`, and `PATH` so the pipeline finds models automatically.

4. **Platform-specific audio backends** — Windows uses WASAPI, macOS uses Core Audio, Linux picks ALSA/PulseAudio/PipeWire. The pipeline detects which is available.

5. **MFA cache discovery is critical** — `MFA_ROOT_DIR` provides automatic model resolution. Users shouldn't have to manually hunt for acoustic models.

6. **Testing on clean systems** — Always verify installers on fresh machines without Python / Praat / ffmpeg pre-installed.

---

## Links

- **[macOS Installation Guide](MACOS.md)** — Complete setup walkthrough
- **[Windows Installation Guide](WINDOWS.md)** — Step-by-step instructions
- **[Linux Installation Guide](LINUX.md)** — Distribution support and setup
- **[Development Guide](DEVELOP.md)** — Contributing to SpeechPrint
- **[Main README](README.md)** — Quick start and overview
- **[SpeechPrint Pipeline](https://github.com/SpeechPrint/SpeechPrint)** — Learn the annotation steps and architecture
