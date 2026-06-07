# SpeechPrint for macOS

Complete guide for installing, using, and troubleshooting SpeechPrint on macOS.

## Installation

### Prerequisites

- macOS 14.0 (Sonoma) or later
- ~5GB free disk space (models + dependencies)
- Internet connection
- Administrator access (for Homebrew)

### Install from DMG

1. **Download** `SpeechPrint-macos.dmg` from [Releases](https://github.com/SpeechPrint/SpeechPrint/releases)
2. **Open** the DMG and double-click **SpeechPrint.app**
3. **If "unverified developer" warning appears:**
   - Close the warning
   - Go to **System Settings → Privacy & Security**
   - Scroll down to find **SpeechPrint**
   - Click **"Open Anyway"**
   - Double-click SpeechPrint.app again
4. Choose **"Install SpeechPrint"**
5. Select a release channel (Stable recommended)
6. If Homebrew is not installed, enter your password when prompted
7. Wait for installation to complete — progress is shown in the app
8. Restart your terminal when done

### What Gets Installed

- **Homebrew** - manages the SpeechPrint toolchain installation
- **SpeechPrint toolchain** - installed via `brew install speechprint/speechprint/speechprint`
- **`~/.local/bin/speechprint`** - CLI corpus creator and annotator
- **`$ZDOTDIR/.zshenv`** - updated to source SpeechPrint environment and extend `PATH`

### Post-Installation

**Reload environment variables:**

```bash
source $ZDOTDIR/.zshenv
```

Or simply restart your terminal.

**Verify installation:**

```bash
speechprint --version
```

---

## Creating Corpora

### Using SpeechPrint.app (GUI)

1. Open **SpeechPrint.app** (from the DMG, or move it to `/Applications` first)
2. Choose **"Create New Corpus"**
3. Enter a **Corpus Name** (e.g., "FieldRecordings_2025")
4. Click **"Browse..."** to select a location
5. Choose **default language** (en, de, it, es, fr, cs)
6. Optional: Enable **"Auto-ensemble"**
7. Click **"Create Corpus"**

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
```

### With VS Code

1. Open corpus folder: `code .`
2. VS Code should auto-detect the SpeechPrint task configuration
3. Terminal → Run Task → "Annotate active file"
4. Open the resulting `out/<recording>/recording.TextGrid` in Praat

---

## Environment Variables

After installation, these are added to `$ZDOTDIR/.zshenv`:

```zsh
source "<homebrew-prefix>/env.sh"
export PATH="$HOME/.local/bin:$PATH"
```

The `env.sh` sourced from the Homebrew prefix sets any variables the toolchain requires (e.g. `SPEECHPRINT_ROOT`, `MFA_ROOT_DIR`, `WHISPERX_MODEL`).

**To apply immediately without restarting:**

```bash
source $ZDOTDIR/.zshenv
```

---

## Troubleshooting

### "speechprint: command not found"

**Cause:** Environment variables not loaded yet.

**Fix:**

```bash
source $ZDOTDIR/.zshenv
```

Or restart your terminal.

### "SpeechPrint.app won't open" or "damaged application"

**Fix:**

```bash
xattr -rd com.apple.quarantine /path/to/SpeechPrint.app
```

Then try opening again.

### MFA can't find the acoustic model

**Verify environment is set:**

```bash
echo $MFA_ROOT_DIR
```

**If empty, reload:**

```bash
source $ZDOTDIR/.zshenv
```

### WhisperX fails to load on Apple Silicon

**Ensure you have a recent PyTorch with MPS support:**

```bash
python -c "import torch; print(torch.backends.mps.is_available())"
# Should print: True
```

**If too old, update via Homebrew:**

```bash
brew install python@3.11
pip3.11 install --upgrade torch
```

### Homebrew password prompt during install

**This is normal.** Homebrew needs admin privileges to set up its directory structure on a fresh install. Your password is not stored.

---

## Uninstalling

```bash
# Remove SpeechPrint toolchain
brew uninstall speechprint
brew autoremove

# Remove CLI tool
rm ~/.local/bin/speechprint

# Remove MFA cache (large — frees ~3GB)
rm -rf ~/SpeechPrint/mfa

# Remove environment config (optional)
# Edit $ZDOTDIR/.zshenv and delete the SpeechPrint lines
```

---

## FAQ

**Q: Why does installation take a while?**

A: Homebrew is downloading and building the SpeechPrint toolchain and its dependencies (ffmpeg, Praat, WhisperX, MFA, Parselmouth, etc.). If these are already cached on your machine, it's much faster.

**Q: Can I use SpeechPrint.app and the CLI together?**

A: Yes. Both create the same corpus structure - use whichever suits your workflow.

**Q: Do I need to keep SpeechPrint.app after installing?**

A: Only if you want to create new corpora via the GUI. The CLI (`speechprint`) works independently once installed.

---

## Links

- **[SpeechPrint Pipeline](https://github.com/SpeechPrint/SpeechPrint)** - Learn the annotation steps
- **[Back to README](../README.md)** - Overview and quick start
