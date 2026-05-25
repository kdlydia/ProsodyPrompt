#!/bin/bash
# SpeechPrint - Dependency installer for Linux
# Installs system packages, Python toolchain (via uv), and MFA acoustic models

set -e

RELEASE_TYPE="${1:-stable}"
LANGUAGES_CSV="${2:-en}"

# ============================================================================
# UTILITIES
# ============================================================================

get_sudo_password() {
    local password=""

    if command -v zenity &>/dev/null; then
        password=$(zenity --password --title="SpeechPrint Installer" \
            --text="SpeechPrint Installer requires administrator privileges.\n\nPlease enter your password:" 2>/dev/null)
    elif command -v kdialog &>/dev/null; then
        password=$(kdialog --title "SpeechPrint Installer" \
            --password "SpeechPrint Installer requires administrator privileges.\n\nPlease enter your password:" 2>/dev/null)
    elif command -v yad &>/dev/null; then
        password=$(yad --title="SpeechPrint Installer" \
            --text="SpeechPrint Installer requires administrator privileges.\n\nPlease enter your password:" \
            --entry --hide-text 2>/dev/null)
    elif command -v python3 &>/dev/null; then
        password=$(python3 -c "
import tkinter as tk
from tkinter import simpledialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
password = simpledialog.askstring('SpeechPrint Installer',
    'SpeechPrint Installer requires administrator privileges.\\n\\nPlease enter your password:',
    show='*')
print(password if password else '')
" 2>/dev/null)
    fi

    if [[ -z "$password" ]]; then
        echo "SpeechPrint Installer requires administrator privileges." >&2
        echo "Please enter your password (typing is hidden):" >&2
        read -rsp "" password
        echo "" >&2
    fi

    echo "$password"
}

run_with_sudo() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        if [[ -z "${SUDO_PASSWORD+x}" ]]; then
            SUDO_PASSWORD=$(get_sudo_password)

            if ! echo "$SUDO_PASSWORD" | sudo -S -v 2>/dev/null; then
                echo "ERROR: Incorrect password. Please run the installer again." >&2
                exit 1
            fi
            export SUDO_PASSWORD
        fi

        echo "$SUDO_PASSWORD" | sudo -S "$@"
    fi
}

show_gui_message() {
    local title="$1"
    local message="$2"

    if command -v zenity &>/dev/null; then
        zenity --info --title="$title" --text="$message" --width=400 2>/dev/null || true
    elif command -v kdialog &>/dev/null; then
        kdialog --title "$title" --msgbox "$message" 2>/dev/null || true
    elif command -v yad &>/dev/null; then
        yad --title="$title" --text="$message" --button="OK" 2>/dev/null || true
    else
        echo ""
        echo "=== $title ==="
        echo "$message"
        echo ""
    fi
}

show_sudo_warning() {
    show_gui_message "SpeechPrint Installer" \
        "Welcome to SpeechPrint Installer!\n\nThis installer will set up the SpeechPrint annotation toolchain.\n\nYou may be asked for your password to install system packages."
}

detect_distro() {
    if command -v pacman &>/dev/null; then
        echo "arch"
    elif command -v dnf &>/dev/null; then
        echo "fedora"
    elif command -v apt-get &>/dev/null; then
        echo "ubuntu"
    elif command -v zypper &>/dev/null; then
        echo "opensuse"
    else
        echo "unknown"
    fi
}

ensure_add_apt_repository() {
    if ! command -v add-apt-repository >/dev/null 2>&1; then
        echo "add-apt-repository not found. Installing software-properties-common..."
        run_with_sudo apt-get update
        run_with_sudo apt-get install -y software-properties-common
    fi
}

# ============================================================================
# PYTHON TOOLCHAIN (uv-based)
# ============================================================================

ensure_uv() {
    if command -v uv &>/dev/null; then
        echo "✓ uv already installed: $(uv --version)"
        return 0
    fi

    echo "Installing uv (fast Python package manager)..."
    if command -v curl &>/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &>/dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "ERROR: Need curl or wget to install uv" >&2
        return 1
    fi

    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v uv &>/dev/null; then
        echo "ERROR: uv install failed" >&2
        return 1
    fi
    echo "✓ uv installed: $(uv --version)"
}

install_python_pipeline() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    mkdir -p "$sp_root"

    echo "Setting up SpeechPrint Python environment at $sp_root..."

    cd "$sp_root"

    if [[ ! -d "$sp_root/.venv" ]]; then
        uv venv --python 3.11 "$sp_root/.venv"
    fi

    # shellcheck disable=SC1091
    source "$sp_root/.venv/bin/activate"

    if [[ "$RELEASE_TYPE" == "dev" ]]; then
        SP_REF="main"
    else
        SP_REF="stable"
    fi

    echo "Installing speechprint_pkg (ref=$SP_REF)..."

    # Try git install first; fall back to PyPI if available
    if uv pip install "git+https://github.com/SpeechPrint/SpeechPrint.git@${SP_REF}#subdirectory=speechprint_pkg" 2>/dev/null; then
        echo "✓ Installed speechprint_pkg from git"
    elif uv pip install speechprint 2>/dev/null; then
        echo "✓ Installed speechprint from PyPI"
    else
        echo "⚠ Could not fetch speechprint_pkg — install will continue, but pipeline commands will not work until package is available"
    fi

    echo "Installing audio + ASR dependencies..."
    uv pip install \
        "torch>=2.1" \
        "whisperx" \
        "openai-whisper" \
        "montreal-forced-aligner" \
        "praat-parselmouth" \
        "phonemizer" \
        "librosa" \
        "scipy" \
        "numpy" \
        "pandas" \
        "matplotlib" \
        "pympi-ling" \
        "textgrid" \
        "soundfile" \
        || echo "⚠ Some Python dependencies failed — see uv output above"

    deactivate || true

    # Symlink the speechprint CLI launcher
    mkdir -p "$HOME/.local/bin"
    if [[ -n "${SPEECHPRINT_LAUNCHER_DIR:-}" ]] && [[ -f "$SPEECHPRINT_LAUNCHER_DIR/SpeechPrint" ]]; then
        ln -sf "$SPEECHPRINT_LAUNCHER_DIR/SpeechPrint" "$HOME/.local/bin/speechprint"
        echo "✓ Symlinked speechprint → $SPEECHPRINT_LAUNCHER_DIR/SpeechPrint"
    fi
}

# ============================================================================
# MFA ACOUSTIC MODELS
# ============================================================================

install_mfa_models() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    export MFA_ROOT_DIR="$sp_root/mfa"
    mkdir -p "$MFA_ROOT_DIR"

    # shellcheck disable=SC1091
    source "$sp_root/.venv/bin/activate" 2>/dev/null || true

    if ! command -v mfa &>/dev/null; then
        echo "⚠ mfa command not found — skipping acoustic model download"
        return 0
    fi

    IFS=',' read -ra LANG_ARRAY <<< "$LANGUAGES_CSV"
    for code in "${LANG_ARRAY[@]}"; do
        case "$code" in
            en) model="english_mfa" ;;
            de) model="german_mfa" ;;
            it) model="italian_mfa" ;;
            es) model="spanish_mfa" ;;
            fr) model="french_mfa" ;;
            cs) model="czech_mfa" ;;
            *) model="${code}_mfa" ;;
        esac
        echo "Downloading MFA acoustic + dictionary for $code ($model)..."
        mfa model download acoustic "$model" || echo "  ⚠ acoustic $model failed"
        mfa model download dictionary "$model" || echo "  ⚠ dictionary $model failed"
    done

    deactivate || true
}

# ============================================================================
# ENVIRONMENT EXPORT
# ============================================================================

write_env_setup() {
    local sp_root="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
    local marker="# >>> SpeechPrint <<<"
    local end_marker="# <<< SpeechPrint >>>"
    local rc=""

    if [[ -n "${ZSH_VERSION:-}" ]] || [[ "${SHELL:-}" == *zsh* ]]; then
        rc="$HOME/.zshrc"
    else
        rc="$HOME/.bashrc"
    fi

    [[ ! -f "$rc" ]] && touch "$rc"

    if grep -q "$marker" "$rc"; then
        echo "✓ SpeechPrint environment already set in $rc"
        return 0
    fi

    cat >> "$rc" <<EOF

$marker
export SPEECHPRINT_ROOT="$sp_root"
export MFA_ROOT_DIR="\$SPEECHPRINT_ROOT/mfa"
export WHISPERX_MODEL="\${WHISPERX_MODEL:-large-v3}"
export PATH="\$HOME/.local/bin:\$PATH"
[[ -f "\$SPEECHPRINT_ROOT/.venv/bin/activate" ]] && source "\$SPEECHPRINT_ROOT/.venv/bin/activate"
$end_marker
EOF
    echo "✓ Added SpeechPrint environment block to $rc"
}

# ============================================================================
# PER-DISTRO SYSTEM PACKAGES
# ============================================================================

install_system_arch() {
    show_gui_message "Arch Linux Detected" \
        "Installing SpeechPrint system dependencies for Arch Linux."

    echo "Caching sudo password..."
    run_with_sudo true

    run_with_sudo pacman -Sy --noconfirm --needed \
        python python-pip ffmpeg praat git curl \
        gtk4 python-gobject base-devel \
        espeak-ng alsa-utils \
        || echo "⚠ Some pacman packages failed"
}

install_system_fedora() {
    show_gui_message "Fedora Detected" \
        "Installing SpeechPrint system dependencies for Fedora."

    run_with_sudo dnf install -y \
        python3 python3-pip ffmpeg-free praat git curl \
        gtk4 python3-gobject \
        gcc gcc-c++ make \
        espeak-ng alsa-utils \
        || echo "⚠ Some dnf packages failed"
}

install_system_ubuntu() {
    show_gui_message "Ubuntu / Debian Detected" \
        "Installing SpeechPrint system dependencies for Ubuntu / Debian."

    run_with_sudo apt-get update
    run_with_sudo apt-get install -y \
        python3 python3-pip python3-venv \
        ffmpeg praat git curl \
        libgtk-4-dev python3-gi \
        build-essential \
        espeak-ng alsa-utils \
        || echo "⚠ Some apt packages failed"
}

install_system_opensuse() {
    show_gui_message "openSUSE Detected" \
        "Installing SpeechPrint system dependencies for openSUSE."

    run_with_sudo zypper install -y \
        python311 python311-pip ffmpeg praat git curl \
        gtk4-devel python311-gobject \
        gcc gcc-c++ make \
        espeak-ng alsa-utils \
        || echo "⚠ Some zypper packages failed"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_sudo_warning

DISTRO=$(detect_distro)
echo "Detected distribution: $DISTRO"
echo "Release channel:       $RELEASE_TYPE"
echo "Language modules:      $LANGUAGES_CSV"
echo ""

case "$DISTRO" in
    arch)
        install_system_arch
        ;;
    fedora)
        install_system_fedora
        ;;
    ubuntu)
        install_system_ubuntu
        ;;
    opensuse)
        install_system_opensuse
        ;;
    unknown)
        echo "WARNING: Unknown distribution — skipping system packages."
        echo "You will need to ensure python3.11, ffmpeg, praat, gtk4 are installed manually."
        show_gui_message "Unknown Distribution" \
            "Your distribution is not in the auto-install list.\n\nThe installer will continue with Python-only setup. You will need to install ffmpeg, praat, and python3.11 manually."
        ;;
esac

echo ""
echo "=== Python compatibility ==="
PYVER=
echo "Detected Python: "
if [[ "" > "3.12" ]]; then
  echo "⚠ MFA/kalpy may not work on Python . WhisperX and prosody modules can still work."
fi
echo
echo "=== Python toolchain (uv) ==="
ensure_uv || { echo "✗ uv setup failed"; exit 1; }
install_python_pipeline

echo ""
echo
echo "=== Forced aligners (multi-backend) ==="
# Each aligner is opt-in via env var. Defaults: MFA on, Gentle on (Docker-mode
# is fast to set up if Docker is available; otherwise skipped), CrisperWhisper
# on (pip-only, light to install).
INSTALL_MFA="${SPEECHPRINT_INSTALL_MFA:-1}"
INSTALL_GENTLE="${SPEECHPRINT_INSTALL_GENTLE:-1}"
INSTALL_CRISPER="${SPEECHPRINT_INSTALL_CRISPERWHISPER:-1}"

SP_ROOT_DIR="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$INSTALL_MFA" = "1" ]; then
    echo "--- MFA (Montreal Forced Aligner) via miniforge/mamba ---"
    if [ -x "$SCRIPT_DIR/setup_mfa_mamba.sh" ]; then
        SPEECHPRINT_ROOT="$SP_ROOT_DIR" bash "$SCRIPT_DIR/setup_mfa_mamba.sh" "$LANGUAGES_CSV" \
            || echo "⚠ MFA setup failed — continuing without it"
    else
        echo "⚠ setup_mfa_mamba.sh not found at $SCRIPT_DIR — skipping"
    fi
else
    echo "Skipping MFA install (SPEECHPRINT_INSTALL_MFA=0)"
fi

if [ "$INSTALL_GENTLE" = "1" ]; then
    echo ""
    echo "--- Gentle (Kaldi-based, HTTP API) ---"
    if [ -x "$SCRIPT_DIR/setup_gentle.sh" ]; then
        SPEECHPRINT_ROOT="$SP_ROOT_DIR" bash "$SCRIPT_DIR/setup_gentle.sh" auto \
            || echo "⚠ Gentle setup failed — continuing without it"
    else
        echo "⚠ setup_gentle.sh not found — skipping"
    fi
else
    echo "Skipping Gentle install (SPEECHPRINT_INSTALL_GENTLE=0)"
fi

if [ "$INSTALL_CRISPER" = "1" ]; then
    echo ""
    echo "--- CrisperWhisper (HuggingFace model) ---"
    if [ -x "$SCRIPT_DIR/setup_crisperwhisper.sh" ]; then
        SPEECHPRINT_ROOT="$SP_ROOT_DIR" bash "$SCRIPT_DIR/setup_crisperwhisper.sh" \
            || echo "⚠ CrisperWhisper setup failed — continuing without it"
    else
        echo "⚠ setup_crisperwhisper.sh not found — skipping"
    fi
else
    echo "Skipping CrisperWhisper install (SPEECHPRINT_INSTALL_CRISPERWHISPER=0)"
fi

echo ""
echo "--- Aligner availability check ---"
if [ -x "$SP_ROOT_DIR/.venv/bin/python" ]; then
    "$SP_ROOT_DIR/.venv/bin/python" -m speechprint_pkg.cli aligners 2>/dev/null || \
        echo "  (aligners status will be available after first launch)"
fi

echo "=== Shell environment ==="
write_env_setup

echo ""
echo "✓ SpeechPrint installation complete"
show_gui_message "Installation Complete" \
    "SpeechPrint installation complete! 🎉\n\nNext steps:\n1. Restart your terminal or run: source ~/.bashrc (or ~/.zshrc)\n2. Create a corpus: speechprint new MyCorpus ~/Corpora/\n3. Annotate: speechprint annotate data/recording.wav --language en"

unset SUDO_PASSWORD
exit 0
