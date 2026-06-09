# ProsodyPrompt for Linux

Complete guide for installing, using, and troubleshooting ProsodyPrompt on Linux.

## Installation

### Prerequisites

- Linux x86_64 (kernel 5.0+)
- Python 3.11+
- GTK4
- ~5GB free disk space (models + dependencies)
- Internet connection

**Distribution Requirements:**

ProsodyPrompt requires modern Python and audio tooling (Python 3.11, ffmpeg 6+, Praat 6.4+, libsndfile 1.2+). Check your distro:

- **Arch Linux** - Run `pacman -Syu` (always up-to-date)
- **Fedora** - Fedora 43 or later
- **Ubuntu** - Ubuntu 25 or later
- **openSUSE** - Tumbleweed (rolling release, same as Arch)

Advanced users with custom Python builds can use ProsodyPrompt on older distributions.

### Install from Tarball

1. **Download** `ProsodyPrompt-X.X.X-linux.tar.gz` from [Releases](https://github.com/kdlydia/ProsodyPrompt/releases)
2. **Extract to `.local`:**
   ```bash
   tar -xzf ProsodyPrompt-X.X.X-linux.tar.gz -C ~/.local/
   ```
3. **Launch ProsodyPrompt GUI:**
   ```bash
   ~/.local/ProsodyPrompt-X.X.X/ProsodyPrompt
   ```
4. **ProsodyPrompt GUI opens:**
   - Select "Install ProsodyPrompt" mode
   - Follow step-by-step installer
   - May prompt for password (sudo needed for system packages)
5. **When complete**, you can create corpora and annotate recordings

### Installed components

- **`~/.local/ProsodyPrompt-X.X.X/`** - ProsodyPrompt application, CLI tool, templates
- **ProsodyPrompt toolchain** - Via package manager:
  - Arch: `prosodyprompt-bin` from AUR
  - Fedora: `prosodyprompt` from custom COPR
- **`~/.local/bin/prosodyprompt`** - Symlink to CLI tool (added to PATH)
- **`~/.bashrc` or `~/.zshrc`** - Environment variables (PROSODYPROMPT_ROOT, MFA_ROOT_DIR, PATH)

### Post-Installation

**Reload environment variables:**

```bash
# For bash
source ~/.bashrc

# For zsh
source ~/.zshrc
```

Or restart your terminal.

**Verify installation:**

```bash
echo $PROSODYPROMPT_ROOT
# Should output: ~/ProsodyPrompt

prosodyprompt --version
# Should show version number
```

---

## Creating Corpora

### Using ProsodyPrompt GUI

1. Run: `~/.local/ProsodyPrompt-X.X.X/ProsodyPrompt`
2. Select **"Create Corpus"** mode
3. Enter **Corpus Name** (e.g., "FieldRecordings_2025")
4. Click **"Browse..."** to select location
5. Choose **default language** (en, de, it, es, fr, cs)
6. Optional: Enable "Auto-ensemble" or "VS Code configuration"
7. Click **"Create Corpus"**
8. Success shows your corpus location

### Using CLI Tool

```bash
# Basic corpus
prosodyprompt new MyCorpus ~/Corpora/

# With default language preset
prosodyprompt new MyCorpus ~/Corpora/ --language it

# Without VS Code setup
prosodyprompt new MyCorpus ~/Corpora/ --no-vscode
```

---

## Annotating & Exporting

### Quick Start

```bash
cd MyCorpus
speechprint annotate data/recording.wav --language de
speechprint ensemble
ls out/recording/
```

### With VS Code

1. Open corpus folder: `code .`
2. VS Code should auto-detect the SpeechPrint task configuration
3. Terminal → Run Task → "Annotate active file"
4. Inspect outputs in `out/<recording>/`

### Manual Annotation Pipeline

```bash
cd MyCorpus
# Step-by-step rather than the full annotate command
prosodyprompt transcribe data/recording.wav --language en
prosodyprompt align     data/recording.wav --language en
prosodyprompt prosody   data/recording.wav --language en
prosodyprompt export    data/recording.wav --formats textgrid,eaf,csv
```

### Batch corpus

```bash
cd MyCorpus
prosodyprompt corpus data/ --language en
prosodyprompt ensemble
```

---

## Environment Variables

After installation, these are set in your shell config:

| Variable             | Value                                              | Purpose                       |
| -------------------- | -------------------------------------------------- | ----------------------------- |
| `PROSODYPROMPT_ROOT` | `~/ProsodyPrompt` or `/usr/` (if via package manager) | Toolchain location           |
| `MFA_ROOT_DIR`       | `$PROSODYPROMPT_ROOT/mfa`                          | Montreal Forced Aligner cache |
| `WHISPERX_MODEL`     | `large-v3`                                         | Default WhisperX model        |
| `PATH`               | Includes `~/.local/bin`                            | CLI tools                     |

**To apply immediately without restarting:**

```bash
source ~/.bashrc   # or ~/.zshrc
```

---

## Troubleshooting

### "GTK4 not found" during GUI launch

**Fix:**

```bash
# Arch Linux
sudo pacman -S gtk4

# Fedora
sudo dnf install gtk4

# Ubuntu/Debian
sudo apt install libgtk-4-dev

# openSUSE
sudo zypper install gtk4-devel
```

Then run ProsodyPrompt again.

### "prosodyprompt: command not found"

**Cause:** Environment variables not loaded

**Fix:**

```bash
source ~/.bashrc    # or ~/.zshrc
prosodyprompt new MyCorpus
```

Or restart your terminal completely.

### MFA can't find the acoustic model

**Verify environment is set:**

```bash
echo $MFA_ROOT_DIR
# Should show: ~/ProsodyPrompt/mfa or /home/username/ProsodyPrompt/mfa
```

**If empty, reload:**

```bash
source ~/.bashrc    # or ~/.zshrc
```

**If still not found, download the model manually:**

```bash
mfa model download acoustic italian_mfa
mfa model download dictionary italian_mfa
```

### "No suitable asset found" during download

**This shouldn't happen.** ProsodyPrompt automatically detects your distribution and installs dependencies via the appropriate package manager (AUR for Arch, COPR for Fedora).

If you see this error:

1. Verify you're on a supported distribution (Arch or Fedora 43+)
2. Check installation log: `~/.prosodyprompt_install.log`
3. Report as issue on GitHub

### WhisperX fails to load on CPU

**Ensure you have a working ffmpeg and a recent PyTorch:**

```bash
ffmpeg -version    # Should be 6+
python -c "import torch; print(torch.__version__)"  # Should be 2.1+
```

**Reinstall PyTorch (CPU-only build):**

```bash
# Arch Linux
sudo pacman -S python-pytorch

# Fedora
sudo dnf install python3-torch

# Ubuntu/Debian
sudo apt install python3-torch

# openSUSE
sudo zypper install python311-pytorch
```

### Permission denied on ~/.local/bin/speechprint

**Fix permissions:**

```bash
chmod +x ~/.local/bin/prosodyprompt
chmod +x ~/.local/ProsodyPrompt-X.X.X/ProsodyPrompt
```

### Dependency installation asks for password

**This is normal.** Installing system packages requires sudo. Provide your password when prompted.

### "python3 not found" during GUI launch

**Install Python:**

```bash
# Arch Linux
sudo pacman -S python

# Fedora
sudo dnf install python3

# Ubuntu/Debian
sudo apt install python3

# openSUSE
sudo zypper install python3
```

---

## Uninstalling

### Remove Everything

```bash
# Remove ProsodyPrompt installation
rm -rf ~/.local/ProsodyPrompt-*

# Remove CLI symlink
rm ~/.local/bin/prosodyprompt

# Remove MFA cache (large — frees ~3GB)
rm -rf ~/ProsodyPrompt/mfa

# Remove environment setup (optional)
nano ~/.bashrc    # or ~/.zshrc
# Find and delete lines containing PROSODYPROMPT_ROOT, MFA_ROOT_DIR additions
```

### Remove ProsodyPrompt Package

```bash
# Arch Linux
yay -R prosodyprompt-bin

# Fedora
sudo dnf remove prosodyprompt
```

---

## FAQ

**Q: Can I use ProsodyPrompt on Ubuntu 24 / Fedora 42 / older Arch?**

A: ProsodyPrompt requires modern audio tooling:

- **Python 3.11** (modern asyncio + type hints used by the pipeline)
- **ffmpeg 6+** (resampling and channel handling)
- **Praat 6.4+** (Parselmouth compatibility)

Check your distro versions. If you want to use ProsodyPrompt on older systems, you'll need to install newer Python and audio packages yourself (not officially supported).

**Q: Can I use ProsodyPrompt CLI and GUI together?**

A: Yes. Use whichever is more convenient. Both create the same corpus structure.

**Q: Can I annotate with a different WhisperX model?**

A: Yes. Override per call or globally:

```bash
# Per call
prosodyprompt annotate data/recording.wav --language en --whisperx-model medium

# Globally
export WHISPERX_MODEL=medium
prosodyprompt annotate data/recording.wav --language en
```

**Q: How do I switch the default GPU device?**

A: Set the standard CUDA environment variable before running:

```bash
export CUDA_VISIBLE_DEVICES=0
prosodyprompt annotate data/recording.wav --language en
```

If no GPU is detected, SpeechPrint falls back to CPU automatically.

---

## Links

- **[ProsodyPrompt Pipeline](https://github.com/kdlydia/ProsodyPrompt)** - Learn the annotation steps
- **[Back to README](../README.md)** - Overview and quick start
