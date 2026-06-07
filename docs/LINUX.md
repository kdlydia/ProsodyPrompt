# SpeechPrint for Linux

Complete guide for installing, using, and troubleshooting SpeechPrint on Linux.

## Installation

### Prerequisites

- Linux x86_64 (kernel 5.0+)
- Python 3.11+
- GTK4
- ~5GB free disk space (models + dependencies)
- Internet connection

**Distribution Requirements:**

SpeechPrint requires modern Python and audio tooling (Python 3.11, ffmpeg 6+, Praat 6.4+, libsndfile 1.2+). Check your distro:

- **Arch Linux** - Run `pacman -Syu` (always up-to-date)
- **Fedora** - Fedora 43 or later
- **Ubuntu** - Ubuntu 25 or later
- **openSUSE** - Tumbleweed (rolling release, same as Arch)

Advanced users with custom Python builds can use SpeechPrint on older distributions.

### Install from Tarball

1. **Download** `SpeechPrint-X.X.X-linux.tar.gz` from [Releases](https://github.com/SpeechPrint/SpeechPrint/releases)
2. **Extract to `.local`:**
   ```bash
   tar -xzf SpeechPrint-X.X.X-linux.tar.gz -C ~/.local/
   ```
3. **Launch SpeechPrint GUI:**
   ```bash
   ~/.local/SpeechPrint-X.X.X/SpeechPrint
   ```
4. **SpeechPrint GUI opens:**
   - Select "Install SpeechPrint" mode
   - Follow step-by-step installer
   - May prompt for password (sudo needed for system packages)
5. **When complete**, you can create corpora and annotate recordings

### Installed components

- **`~/.local/SpeechPrint-X.X.X/`** - SpeechPrint application, CLI tool, templates
- **SpeechPrint toolchain** - Via package manager:
  - Arch: `speechprint-bin` from AUR
  - Fedora: `speechprint` from custom COPR
- **`~/.local/bin/speechprint`** - Symlink to CLI tool (added to PATH)
- **`~/.bashrc` or `~/.zshrc`** - Environment variables (SPEECHPRINT_ROOT, MFA_ROOT_DIR, PATH)

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
echo $SPEECHPRINT_ROOT
# Should output: ~/SpeechPrint

speechprint --version
# Should show version number
```

---

## Creating Corpora

### Using SpeechPrint GUI

1. Run: `~/.local/SpeechPrint-X.X.X/SpeechPrint`
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
speechprint new MyCorpus ~/Corpora/

# With default language preset
speechprint new MyCorpus ~/Corpora/ --language it

# Without VS Code setup
speechprint new MyCorpus ~/Corpora/ --no-vscode
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
speechprint transcribe data/recording.wav --language en
speechprint align     data/recording.wav --language en
speechprint prosody   data/recording.wav --language en
speechprint export    data/recording.wav --formats textgrid,eaf,csv
```

### Batch corpus

```bash
cd MyCorpus
speechprint corpus data/ --language en
speechprint ensemble
```

---

## Environment Variables

After installation, these are set in your shell config:

| Variable             | Value                                              | Purpose                       |
| -------------------- | -------------------------------------------------- | ----------------------------- |
| `SPEECHPRINT_ROOT`   | `~/SpeechPrint` or `/usr/` (if via package manager) | Toolchain location           |
| `MFA_ROOT_DIR`       | `$SPEECHPRINT_ROOT/mfa`                            | Montreal Forced Aligner cache |
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

Then run SpeechPrint again.

### "speechprint: command not found"

**Cause:** Environment variables not loaded

**Fix:**

```bash
source ~/.bashrc    # or ~/.zshrc
speechprint new MyCorpus
```

Or restart your terminal completely.

### MFA can't find the acoustic model

**Verify environment is set:**

```bash
echo $MFA_ROOT_DIR
# Should show: ~/SpeechPrint/mfa or /home/username/SpeechPrint/mfa
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

**This shouldn't happen.** SpeechPrint automatically detects your distribution and installs dependencies via the appropriate package manager (AUR for Arch, COPR for Fedora).

If you see this error:

1. Verify you're on a supported distribution (Arch or Fedora 43+)
2. Check installation log: `~/.speechprint_install.log`
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
chmod +x ~/.local/bin/speechprint
chmod +x ~/.local/SpeechPrint-X.X.X/SpeechPrint
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
# Remove SpeechPrint installation
rm -rf ~/.local/SpeechPrint-*

# Remove CLI symlink
rm ~/.local/bin/speechprint

# Remove MFA cache (large — frees ~3GB)
rm -rf ~/SpeechPrint/mfa

# Remove environment setup (optional)
nano ~/.bashrc    # or ~/.zshrc
# Find and delete lines containing SPEECHPRINT_ROOT, MFA_ROOT_DIR additions
```

### Remove SpeechPrint Package

```bash
# Arch Linux
yay -R speechprint-bin

# Fedora
sudo dnf remove speechprint
```

---

## FAQ

**Q: Can I use SpeechPrint on Ubuntu 24 / Fedora 42 / older Arch?**

A: SpeechPrint requires modern audio tooling:

- **Python 3.11** (modern asyncio + type hints used by the pipeline)
- **ffmpeg 6+** (resampling and channel handling)
- **Praat 6.4+** (Parselmouth compatibility)

Check your distro versions. If you want to use SpeechPrint on older systems, you'll need to install newer Python and audio packages yourself (not officially supported).

**Q: Can I use SpeechPrint CLI and GUI together?**

A: Yes. Use whichever is more convenient. Both create the same corpus structure.

**Q: Can I annotate with a different WhisperX model?**

A: Yes. Override per call or globally:

```bash
# Per call
speechprint annotate data/recording.wav --language en --whisperx-model medium

# Globally
export WHISPERX_MODEL=medium
speechprint annotate data/recording.wav --language en
```

**Q: How do I switch the default GPU device?**

A: Set the standard CUDA environment variable before running:

```bash
export CUDA_VISIBLE_DEVICES=0
speechprint annotate data/recording.wav --language en
```

If no GPU is detected, SpeechPrint falls back to CPU automatically.

---

## Links

- **[SpeechPrint Pipeline](https://github.com/SpeechPrint/SpeechPrint)** - Learn the annotation steps
- **[Back to README](../README.md)** - Overview and quick start
