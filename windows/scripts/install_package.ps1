# SpeechPrint - Windows dependency installer
# Installs Python 3.11, ffmpeg, Praat, and the SpeechPrint Python pipeline (+ MFA models)

param(
    [string]$Release = "stable",
    [string]$Languages = "en"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [warn] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [err] $msg" -ForegroundColor Red }

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

$SP_ROOT = "C:\SpeechPrint"
$MFA_ROOT = Join-Path $SP_ROOT "mfa"
$PY_ROOT = "C:\Python311"

Write-Host ""
Write-Host "SpeechPrint Windows installer"
Write-Host "============================="
Write-Host "  Release channel : $Release"
Write-Host "  Languages       : $Languages"
Write-Host "  SPEECHPRINT_ROOT: $SP_ROOT"
Write-Host ""

# ----------------------------------------------------------------------------
# 1. Check admin
# ----------------------------------------------------------------------------

Write-Step "Checking admin privileges..."
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Must run as Administrator"
    exit 1
}
Write-OK "Running as administrator"

# ----------------------------------------------------------------------------
# 2. Ensure folders
# ----------------------------------------------------------------------------

Write-Step "Creating install directories..."
New-Item -ItemType Directory -Force -Path $SP_ROOT  | Out-Null
New-Item -ItemType Directory -Force -Path "$SP_ROOT\bin" | Out-Null
New-Item -ItemType Directory -Force -Path "$SP_ROOT\lib" | Out-Null
New-Item -ItemType Directory -Force -Path "$SP_ROOT\share\speechprint\templates" | Out-Null
New-Item -ItemType Directory -Force -Path $MFA_ROOT | Out-Null
Write-OK "Folders ready"

# ----------------------------------------------------------------------------
# 3. Install Python via winget (or via embedded installer fallback)
# ----------------------------------------------------------------------------

Write-Step "Installing Python 3.11..."
$pythonExe = "$PY_ROOT\python.exe"
if (Test-Path $pythonExe) {
    Write-OK "Python already present at $PY_ROOT"
} else {
    try {
        winget install --silent --accept-source-agreements --accept-package-agreements --id Python.Python.3.11 `
            --location $PY_ROOT 2>&1 | Out-Host
        Write-OK "Python 3.11 installed"
    } catch {
        Write-Warn "winget failed: $_"
        Write-Warn "You may need to install Python 3.11 manually from https://www.python.org/downloads/"
    }
}

# ----------------------------------------------------------------------------
# 4. Install audio tools via winget
# ----------------------------------------------------------------------------

Write-Step "Installing ffmpeg..."
try {
    winget install --silent --accept-source-agreements --accept-package-agreements --id Gyan.FFmpeg 2>&1 | Out-Host
    Write-OK "ffmpeg installed"
} catch { Write-Warn "ffmpeg via winget failed: $_" }

Write-Step "Installing Praat..."
try {
    winget install --silent --accept-source-agreements --accept-package-agreements --id Praat.Praat 2>&1 | Out-Host
    Write-OK "Praat installed"
} catch { Write-Warn "Praat via winget failed: $_" }

Write-Step "Installing Git..."
try {
    winget install --silent --accept-source-agreements --accept-package-agreements --id Git.Git 2>&1 | Out-Host
    Write-OK "Git installed"
} catch { Write-Warn "Git via winget failed: $_" }

# ----------------------------------------------------------------------------
# 5. Install uv (Python dep manager)
# ----------------------------------------------------------------------------

Write-Step "Installing uv (fast Python package manager)..."
try {
    Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" | Invoke-Expression
    Write-OK "uv installed"
} catch {
    Write-Warn "uv install failed: $_  — falling back to pip"
}

# ----------------------------------------------------------------------------
# 6. SpeechPrint Python pipeline + venv
# ----------------------------------------------------------------------------

Write-Step "Creating SpeechPrint venv at $SP_ROOT\.venv ..."
$uv = (Get-Command uv -ErrorAction SilentlyContinue)
if ($uv) {
    uv venv --python 3.11 "$SP_ROOT\.venv"
} else {
    & $pythonExe -m venv "$SP_ROOT\.venv"
}

$VENV_PIP    = "$SP_ROOT\.venv\Scripts\pip.exe"
$VENV_PY     = "$SP_ROOT\.venv\Scripts\python.exe"
$VENV_SP_CLI = "$SP_ROOT\.venv\Scripts\speechprint.exe"

Write-Step "Installing speechprint_pkg + dependencies..."
$ref = if ($Release -eq "dev") { "main" } else { "stable" }
try {
    if ($uv) {
        uv pip install --python "$VENV_PY" "git+https://github.com/SpeechPrint/SpeechPrint.git@${ref}#subdirectory=speechprint_pkg"
    } else {
        & $VENV_PIP install "git+https://github.com/SpeechPrint/SpeechPrint.git@${ref}#subdirectory=speechprint_pkg"
    }
    Write-OK "speechprint_pkg installed"
} catch {
    Write-Warn "speechprint_pkg install failed — pipeline commands will not work until this is fixed"
}

try {
    if ($uv) {
        uv pip install --python "$VENV_PY" torch whisperx montreal-forced-aligner praat-parselmouth librosa scipy numpy pandas matplotlib pympi-ling textgrid soundfile
    } else {
        & $VENV_PIP install torch whisperx montreal-forced-aligner praat-parselmouth librosa scipy numpy pandas matplotlib pympi-ling textgrid soundfile
    }
    Write-OK "Python dependencies installed"
} catch {
    Write-Warn "Some Python dependencies failed: $_"
}

# ----------------------------------------------------------------------------
# 7. MFA acoustic models
# ----------------------------------------------------------------------------

Write-Step "Downloading MFA acoustic models for: $Languages"
$env:MFA_ROOT_DIR = $MFA_ROOT
$langArray = $Languages -split ","
foreach ($code in $langArray) {
    $code = $code.Trim()
    $model = switch ($code) {
        "en" { "english_mfa" }
        "de" { "german_mfa" }
        "it" { "italian_mfa" }
        "es" { "spanish_mfa" }
        "fr" { "french_mfa" }
        "cs" { "czech_mfa" }
        default { "${code}_mfa" }
    }
    Write-Host "  Downloading $code → $model"
    try {
        & $VENV_PY -m montreal_forced_aligner.command_line.mfa model download acoustic $model 2>&1 | Out-Host
        & $VENV_PY -m montreal_forced_aligner.command_line.mfa model download dictionary $model 2>&1 | Out-Host
        Write-OK "$code acoustic + dictionary downloaded"
    } catch {
        Write-Warn "$code model download failed: $_"
    }
}

# ----------------------------------------------------------------------------
# 8. Templates
# ----------------------------------------------------------------------------

Write-Step "Installing corpus templates..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcTemplates = Join-Path $scriptDir "templates"
if (Test-Path $srcTemplates) {
    Copy-Item -Recurse -Force "$srcTemplates\*" "$SP_ROOT\share\speechprint\templates\"
    Write-OK "Templates installed to $SP_ROOT\share\speechprint\templates"
} else {
    Write-Warn "Templates not found in script directory; skipping"
}

# ----------------------------------------------------------------------------
# 9. CLI shim — make `speechprint` available globally
# ----------------------------------------------------------------------------

Write-Step "Creating speechprint.cmd shim in $SP_ROOT\bin ..."
@"
@echo off
set SPEECHPRINT_ROOT=$SP_ROOT
set MFA_ROOT_DIR=$MFA_ROOT
set WHISPERX_MODEL=large-v3
set SPEECHPRINT_TEMPLATE_DIR=$SP_ROOT\share\speechprint\templates
"$VENV_PY" -m speechprint_pkg.cli %*
"@ | Set-Content -Path "$SP_ROOT\bin\speechprint.cmd" -Encoding ASCII
Write-OK "Created $SP_ROOT\bin\speechprint.cmd"

# ----------------------------------------------------------------------------
# 10. Environment variables (machine-wide)
# ----------------------------------------------------------------------------

Write-Step "Setting environment variables (machine scope)..."
[Environment]::SetEnvironmentVariable("SPEECHPRINT_ROOT", $SP_ROOT, "Machine")
[Environment]::SetEnvironmentVariable("MFA_ROOT_DIR", $MFA_ROOT, "Machine")
[Environment]::SetEnvironmentVariable("WHISPERX_MODEL", "large-v3", "Machine")

$path = [Environment]::GetEnvironmentVariable("Path", "Machine")
$spBin = "$SP_ROOT\bin"
if ($path -notlike "*$spBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$path;$spBin", "Machine")
    Write-OK "Added $spBin to PATH"
} else {
    Write-OK "$spBin already on PATH"
}

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "  SpeechPrint installation done"  -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Close and reopen PowerShell/CMD"
Write-Host "  2. speechprint new MyCorpus C:\Corpora\"
Write-Host "  3. speechprint annotate data\recording.wav --language $($langArray[0])"
Write-Host ""

exit 0
