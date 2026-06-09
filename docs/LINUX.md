# ProsodyPrompt for Linux

Complete guide for installing, using, and troubleshooting ProsodyPrompt on Linux.

## Installation

### Prerequisites

- Linux x86_64 (kernel 5.0+)
- Python 3.11+
- Git
- ffmpeg 6+
- ~5GB free disk space (for models and dependencies)
- Internet connection

**Distribution Requirements:**

ProsodyPrompt requires modern Python and audio tooling. Check your distro:

- **Arch Linux** - Run `pacman -Syu` (always up-to-date)
- **Fedora** - Fedora 43 or later
- **Ubuntu** - Ubuntu 25 or later
- **openSUSE** - Tumbleweed (rolling release, same as Arch)

Advanced users with custom Python builds can use ProsodyPrompt on older distributions.

### Quick Start (Development Installation)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kdlydia/ProsodyPrompt
   cd ProsodyPrompt
   ```

2. **Create virtual environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Run ProsodyPrompt:**
   ```bash
   cd linux
   python run.py
   ```

The interactive CLI opens immediately. No GUI, no config files. It asks questions and shows numbered options — choose language, tracker, annotation source — then runs the pipeline.

### Installation Troubleshooting

#### "command not found: python3.11"

Use your distribution's Python:

```bash
# Check available Python version
python3 --version

# Arch Linux (install if needed)
sudo pacman -S python

# Fedora 43+
sudo dnf install python3

# Ubuntu 25+
sudo apt install python3

# openSUSE Tumbleweed
sudo zypper install python3
```

#### "ffmpeg not found"

Install ffmpeg for your distribution:

```bash
# Arch Linux
sudo pacman -S ffmpeg

# Fedora
sudo dnf install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# openSUSE
sudo zypper install ffmpeg
```

#### "pip install" fails on PyTorch

PyTorch can be finicky. Use CPU-only to start:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install torchaudio
pip install torchcrepe
```

If you have a GPU (CUDA 12.x):

```bash
pip install torch torchcrepe torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### "No module named parselmouth"

Parselmouth requires Praat to be installed on your system:

```bash
# Arch Linux
sudo pacman -S praat

# Fedora
sudo dnf install praat

# Ubuntu/Debian
sudo apt install praat

# openSUSE
sudo zypper install praat

# Then reinstall parselmouth
pip install --force-reinstall --no-cache-dir parselmouth
```

---

## Quick Usage

### Basic Annotation (from audio file only)

```bash
cd linux
python run.py
# Choose: 1) Annotate a recording
# Follow prompts for language and pitch tracker
```

### With Existing TextGrid (DoReCo, ELAN)

```bash
cd linux
python run.py
# Choose: 1) Annotate a recording
# When asked "Do you have a human-annotated TextGrid?", answer yes
# Point to your .TextGrid file
```

---

## Environment Variables

After installation, you may want to set these for batch processing:

```bash
export PROSODYPROMPT_ROOT=~/ProsodyPrompt
export WHISPERX_MODEL=large-v3
export CUDA_VISIBLE_DEVICES=0  # if you have a GPU
```

Add to `~/.bashrc` or `~/.zshrc` if you want them persistent:

```bash
echo 'export PROSODYPROMPT_ROOT=~/ProsodyPrompt' >> ~/.bashrc
source ~/.bashrc
```

---

## Troubleshooting

### "GTK4 not found" during GUI launch

Install GTK4 development files:

```bash
# Arch Linux
sudo pacman -S gtk4

# Fedora
sudo dnf install gtk4-devel

# Ubuntu/Debian
sudo apt install libgtk-4-dev

# openSUSE
sudo zypper install gtk4-devel
```

### "WhisperX fails to load on CPU"

Ensure you have recent PyTorch and ffmpeg:

```bash
ffmpeg -version    # Should be 6+
python -c "import torch; print(torch.__version__)"  # Should be 2.1+
```

Reinstall with explicit versions:

```bash
pip install --force-reinstall --no-cache-dir torch==2.1.2 torchaudio==2.1.2
```

### "MFA model not found"

If Montreal Forced Aligner can't find acoustic models:

```bash
# Download manually
mfa model download acoustic english_us_arpa

# Or set explicit path
export MFA_ROOT_DIR=$PROSODYPROMPT_ROOT/mfa
```

### "CREPE fails on GPU" (CUDA out of memory)

Fall back to pYIN or use CPU:

```bash
# In run.py, choose pYIN instead of CREPE
# Or disable GPU:
export CUDA_VISIBLE_DEVICES=
```

### "Permission denied" running scripts

Make sure scripts are executable:

```bash
chmod +x linux/run.py
```

---

## Uninstalling

### Remove Development Installation

```bash
# Remove directory
rm -rf ~/ProsodyPrompt

# Remove virtual environment
rm -rf ~/ProsodyPrompt/venv
```

### Clear Cache and Models

```bash
# Remove MFA models (large — frees ~3GB)
rm -rf ~/.local/share/mfa

# Remove Whisper cache
rm -rf ~/.cache/huggingface
```

---

## Development Notes

### Running Build Scripts

For generating thesis appendices or test corpora:

```bash
cd linux
python build_questionnaire_v3.py   # English minimal pairs
python build_doreco_speechprint.py # Daakie (DoReCo) corpus
python build_cabeca.py             # Cabécar (DoReCo) corpus
```

### Testing on Different Linux Distributions

Test environment matrix (Arch, Fedora 43+, Ubuntu 25+, openSUSE Tumbleweed):

```bash
# In each container/VM:
git clone https://github.com/kdlydia/ProsodyPrompt
cd ProsodyPrompt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd linux && python run.py
```

---

## FAQ

**Q: Can I use ProsodyPrompt on Ubuntu 24 / Fedora 42 / older Arch?**

A: ProsodyPrompt requires:
- Python 3.11+ (async, type hints)
- ffmpeg 6+ (resampling, channel handling)
- Praat 6.4+ (Parselmouth compatibility)

Older distributions may have outdated packages. You can install newer Python manually, but it's not officially supported.

**Q: Can I use a GPU?**

A: Yes. CREPE and WhisperX will auto-detect CUDA (12.x). For older CUDA versions, install PyTorch explicitly:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**Q: How do I run batch processing?**

A: Use the main `run.py` with option 2 (Batch annotate), or modify `build_questionnaire_v3.py` for your corpus.

**Q: Where are output files?**

A: In `linux/out/` directory structure: `out/recording_name/recording.TextGrid` and per-word/per-syllable CSV exports.

---

## Links

- **[ProsodyPrompt GitHub](https://github.com/kdlydia/ProsodyPrompt)** - Source code
- **[Back to README](../README.md)** - Overview and quick start
