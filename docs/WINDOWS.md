# SpeechPrint for Windows

Complete guide for installing, using, and troubleshooting SpeechPrint on Windows.

## Installation

### Prerequisites

- Windows 10 or later (64-bit only)
- ~6GB free disk space (models + dependencies)
- Internet connection
- Administrator privileges (for dependency installation)

### Install from Executable

1. **Download** `SpeechPrint-X.X.X.exe` from [Releases](https://github.com/SpeechPrint/SpeechPrint/releases)
2. **Double-click** the `.exe` file
3. **UAC (User Access Control) dialog** appears - click "Yes"
4. **Mode selection dialog** appears:
   - Choose **"Install SpeechPrint"** for fresh installation
   - Choose **"Create Corpus"** if already installed
5. **Follow the step-by-step installer:**
   - **Step 1: System Check** - Verifies 64-bit Windows and admin privileges
   - **Step 2: Download SpeechPrint** - Downloads toolchain from GitHub (~120 MB)
   - **Step 3: Install Dependencies** - Installs Python, ffmpeg, Praat (10-20 min)
   - **Step 4: Acoustic Models** - Downloads MFA models for selected languages
   - **Step 5: Environment Setup** - Configures system environment variables
   - **Step 6: Templates** - Extracts corpus templates
   - **Step 7: Complete** - Shows success summary
6. **Restart your terminal/PowerShell** for environment changes to take effect
7. **Create your first corpus** - Run SpeechPrint again and select "Create Corpus"

### What Gets Installed

- **`C:\SpeechPrint\`** - SpeechPrint toolchain, models, configs
- **`C:\Program Files\`** - Audio tools (ffmpeg, Praat, 7-Zip)
- **`C:\Python311\`** - Embedded Python runtime
- **`C:\SpeechPrint\mfa\`** - Montreal Forced Aligner cache
- **Environment Variables:**
  - `SPEECHPRINT_ROOT` = `C:\SpeechPrint`
  - `MFA_ROOT_DIR` = `C:\SpeechPrint\mfa`
  - `WHISPERX_MODEL` = `large-v3`
  - `PATH` += `C:\SpeechPrint\bin;C:\Python311`

### Post-Installation

**Restart your terminal:**

Close PowerShell/CMD completely and reopen. Environment variables reload automatically.

**Verify installation:**

```powershell
echo $env:SPEECHPRINT_ROOT
# Should output: C:\SpeechPrint

speechprint --version
# Should show SpeechPrint version
```

---

## Creating Corpora

### Using SpeechPrint.exe (GUI)

1. Open `SpeechPrint.exe` (from Start Menu or wherever you saved it)
2. Select **"Create Corpus"** mode
3. Enter **Corpus Name** (e.g., "FieldRecordings_2025")
4. Click **"Browse..."** to select location
5. Choose **default language** (en, de, it, es, fr, cs)
6. Optional: Enable "Enable Auto-ensemble"
7. Click **"Create Corpus"**
8. Success dialog shows your corpus location

**Note:** GUI is the primary corpus creation method on Windows. CLI tool is also installed and works from PowerShell or CMD.

---

## Annotating & Exporting

### Quick Start (Command Line)

```powershell
cd MyCorpus
speechprint annotate data\recording.wav --language en
speechprint ensemble
```

### With Visual Studio Code

1. Open generated corpus folder in VS Code
2. Tasks integration should auto-detect configuration
3. Terminal → Run Task → "Annotate active file"
4. Inspect outputs in `out\<recording>\`

### Command Prompt Alternative

```cmd
cd MyCorpus
speechprint annotate data\recording.wav --language en
speechprint ensemble
```

---

## Environment Variables

After installation, these are set in your system environment:

| Variable             | Value                          | Purpose                       |
| -------------------- | ------------------------------ | ----------------------------- |
| `SPEECHPRINT_ROOT`   | `C:\SpeechPrint`               | Toolchain location            |
| `MFA_ROOT_DIR`       | `C:\SpeechPrint\mfa`           | Montreal Forced Aligner cache |
| `WHISPERX_MODEL`     | `large-v3`                     | Default WhisperX model        |
| `PATH`               | Includes SpeechPrint bin       | CLI tools                     |

**Changes take effect after restarting terminal/PowerShell.**

### Manual Environment Variable Check

```powershell
# PowerShell
echo $env:SPEECHPRINT_ROOT

# Command Prompt
echo %SPEECHPRINT_ROOT%
```

### Setting Custom Paths

If you installed SpeechPrint to a different location, set manually:

```powershell
# PowerShell
$env:SPEECHPRINT_ROOT = "D:\Custom\Path\To\SpeechPrint"
```

```cmd
# Command Prompt
set SPEECHPRINT_ROOT=D:\Custom\Path\To\SpeechPrint
```

---

## Troubleshooting

### Installation Fails with "Administrator privileges required"

**Solution:** Right-click `SpeechPrint.exe` → "Run as administrator"

### Dependency Installation Skips with Warnings

**Cause:** Some packages couldn't be installed

**Solution:**

- Check internet connection (dependencies are downloaded)
- Check installation log: `%LOCALAPPDATA%\speechprint_install.log`
- You can continue - dependencies can be manually installed later if needed

### "speechprint not found" after installation

**Cause:** Terminal wasn't restarted after installation

**Solution:** Close PowerShell/CMD completely and reopen (not just a new tab)

### MFA can't find the acoustic model

**Verify environment is set:**

```powershell
echo $env:MFA_ROOT_DIR
# Should show: C:\SpeechPrint\mfa
```

**If empty, restart your terminal.**

**If still not found, download the model manually:**

```powershell
mfa model download acoustic italian_mfa
mfa model download dictionary italian_mfa
```

### Annotation fails with "missing DLL"

**Cause:** Praat or ffmpeg binaries not on PATH

**Solution:** Run the installer again — repair step copies binaries:

```powershell
SpeechPrint.exe   # then choose "Install SpeechPrint"
```

**If issue persists:**

```powershell
# Manually copy DLLs
copy C:\SpeechPrint\bin\*.dll C:\Windows\System32\
```

### PowerShell execution policy error

**Cause:** PowerShell blocked script execution

**This should be handled automatically by SpeechPrint.** If you see execution policy errors:

```powershell
# Temporarily allow for this session
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# Then re-run the annotation
speechprint annotate data\recording.wav --language en
```

### WhisperX errors about CUDA

**Ensure you have a working PyTorch:**

- Visual Studio 2022 redistributables (latest update)
- NVIDIA driver 535+ (if using GPU)

**Check torch:**

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

If `False` and you have an NVIDIA GPU, reinstall PyTorch with CUDA support from `https://pytorch.org`.

### "SpeechPrint.exe is not recognized"

**Cause:** PATH not updated or terminal wasn't restarted

**Solution:** Restart your terminal, or run SpeechPrint from its full path:

```powershell
C:\Users\YourName\Downloads\SpeechPrint.exe
```

---

## Uninstalling

### Remove Everything

```powershell
# Remove SpeechPrint directory
Remove-Item -Path "C:\SpeechPrint" -Recurse -Force

# Remove from Start Menu (automatic via Windows)
# Open Settings > Apps > Apps & Features, find "SpeechPrint" and uninstall
```

Or use Windows Settings:

1. Settings → Apps → Apps & Features
2. Find "SpeechPrint"
3. Click → "Uninstall"

### Clean Up Environment Variables (Optional)

1. Settings → System → Advanced system settings
2. Environment Variables
3. Under "System variables", find and delete:
   - `SPEECHPRINT_ROOT`
   - `MFA_ROOT_DIR`
   - `WHISPERX_MODEL`
   - Any additions to `PATH` containing SpeechPrint

### Registry Cleanup (if needed)

SpeechPrint doesn't use registry. Safe to delete all folders above.

---

## FAQ

**Q: Can I install SpeechPrint to a different location?**

A: The installer uses `C:\SpeechPrint` by default. To use a different location, set `SPEECHPRINT_ROOT` environment variable after installation (see Environment Variables section).

**Q: Can I have multiple SpeechPrint installations?**

A: Yes, but only one `SPEECHPRINT_ROOT` at a time. Switch between them by changing the environment variable.

**Q: Why does installation take so long?**

A: The installer downloads the SpeechPrint toolchain (~120 MB), the WhisperX `large-v3` model (~1.5 GB on first annotation), and MFA acoustic + dictionary models for each language you select. This depends on your internet speed. 15-40 minutes is normal.

**Q: Can I skip MFA model download?**

A: The installer downloads models for the languages you select. You can add more later with `mfa model download acoustic <name>`. Skipping all models means alignment won't work until you download at least one.

**Q: Does SpeechPrint auto-update?**

A: Not yet. Download the new installer from Releases and run it again. It will update existing installations.

**Q: Is the CLI available on Windows?**

A: Yes. After installation `speechprint` is on your PATH and works from PowerShell or CMD. The GUI (`SpeechPrint.exe`) is for one-shot mode selection; the CLI is for scripting and batch annotation.

**Q: Can I run on AMD GPU or Intel Arc?**

A: WhisperX uses PyTorch; AMD ROCm and Intel XPU support depends on your driver and PyTorch build. CPU mode always works. SpeechPrint detects the available backend automatically.

**Q: How do I use PowerShell vs Command Prompt?**

A: Both work. PowerShell syntax shown uses `$env:` for variables; Command Prompt uses `%variable%`. Choose whichever you prefer.

---

## Links

- **[SpeechPrint Pipeline](https://github.com/SpeechPrint/SpeechPrint)** - Learn the annotation steps
- **[Back to README](../README.md)** - Overview and quick start
