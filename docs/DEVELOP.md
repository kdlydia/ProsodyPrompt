# SpeechPrint Development Guide

For developers contributing to SpeechPrint itself.

---

## Prerequisites

- Git
- Python 3.11+
- Platform-specific tools:
  - **macOS:** Xcode Command Line Tools, Homebrew, Swift 5.9+
  - **Windows:** Visual Studio Build Tools 2022, WinGet, .NET 8 SDK
  - **Linux:** Python 3.11+, GTK4 dev headers, standard build utils

---

## Building SpeechPrint from Source

### macOS

```bash
git clone https://github.com/SpeechPrint/SpeechPrint.git
cd SpeechPrint

./macos/scripts/create_pkg.sh 0.3.0
# Output: build/macos/SpeechPrint-0.3.0.pkg
```

The `.pkg` installer uses a composite package design with three components:

1. **SpeechPrint-files** - Templates and CLI tool
2. **SpeechPrint-gui** - Universal SpeechPrint.app (arm64 + x86_64)
3. **SpeechPrint-launcher** - Postinstall coordinator

**macOS Architecture Notes:**

- Apple Silicon: macOS 14.0 minimum
- Intel: macOS 14.0 minimum
- SpeechPrint.app is a universal binary (both architectures in one executable)
- Built with Swift and SwiftUI frameworks

### Windows

```bash
git clone https://github.com/SpeechPrint/SpeechPrint.git
cd SpeechPrint

.\windows\scripts\create_installer.ps1 -Version 0.3.0
# Output: build\windows\SpeechPrint-0.3.0.exe
```

**Windows Architecture Notes:**

- Single self-contained executable (~25-30 MB)
- .NET 8 SDK required for building
- Built with C# and WinForms
- All templates and PowerShell scripts embedded as resources

### Linux

```bash
git clone https://github.com/SpeechPrint/SpeechPrint.git
cd SpeechPrint

./linux/scripts/build_distribution.sh
# Output: build/linux/SpeechPrint-X.X.X.tar.gz
```

**Linux Architecture Notes:**

- Built with Python 3.11+
- GTK4 GUI framework (via PyGObject)
- Tarball distribution for simplicity
- Automatic distribution detection (Arch/Fedora/Ubuntu)

---

## Project Structure

```
SpeechPrint/
├── macos/
│   ├── scripts/
│   │   └── build_speechprint_app.sh   # Builds universal SpeechPrint.app
│   ├── SpeechPrint.sh                  # CLI tool source
│   └── SpeechPrintGUI.swift            # The primary installer and corpus manager
│
├── windows/
│   ├── scripts/
│   │   ├── create_installer.ps1        # Main build script
│   │   ├── install_package.ps1         # Generic dependency installer
│   │   └── packages.psd1               # Dependency definitions
│   ├── SpeechPrint/                    # Main C# project (WinForms, .NET 8)
│   │   ├── Program.cs                  # Entry point (mode → release → languages → main window)
│   │   ├── ModeSelector.cs             # Install / Create Corpus dialog
│   │   ├── ReleaseTypeSelector.cs      # Stable / Dev radio dialog
│   │   ├── LanguageSelector.cs         # Language module checkboxes
│   │   ├── MainWindow.cs               # Installer log view + corpus creator
│   │   ├── Theme.cs                    # Shared dark theme
│   │   ├── app.manifest                # UAC elevation + DPI awareness
│   │   └── SpeechPrint.csproj
│   └── SpeechPrint.sln                 # Solution file
│
├── linux/
│   ├── lib/
│   │   ├── modes/                      # Installation and corpus modes
│   │   ├── ui/                         # GTK4 UI theme
│   │   ├── cli.py                      # CLI tool
│   │   ├── config.py                   # Configuration loader
│   │   └── main.py                     # GUI entry point
│   ├── scripts/
│   │   ├── build_distribution.sh       # Build script
│   │   ├── create_corpus.sh            # Corpus creation
│   │   └── install_deps.sh             # Dependency installation
│   ├── SpeechPrint                     # Launcher script
│   └── pyproject.toml                  # Python project config
│
├── templates/
│   ├── corpus.toml                     # Corpus template
│   ├── README.md
│   ├── data/.gitkeep
│   ├── out/.gitkeep
│   └── vscode/
│       ├── settings.json
│       ├── tasks.json
│       └── launch.json
│
├── .github/
│   ├── workflows/
│   │   └── build.yml                   # CI/CD pipeline
│   └── scripts/
│       ├── verify-macos-build.sh
│       ├── verify-windows-build.ps1
│       └── generate-release-body.sh
│
└── docs/
    ├── MACOS.md
    ├── WINDOWS.md
    ├── LINUX.md
    ├── PACKAGE.md
    └── DEVELOP.md (this file)
```

---

## Testing Installers

Always test on clean systems before release:

### macOS

```bash
# Test on Apple Silicon (arm64)
# Test on Intel (x86_64)
# Verify both architectures in universal binary:
lipo -info build/macos/SpeechPrintApp/SpeechPrint.app/Contents/MacOS/SpeechPrint
# Should show: Mach header integer 2-architecture universal binary with 2 architectures

# Test "unverified developer" warning
# Security & Privacy → "Open Anyway" workflow
```

### Windows

```bash
# Test on Windows 10 and Windows 11
# Verify UAC prompt appears
# Verify all embedded resources extracted correctly
# Test MFA model download flow on a slow network
```

### Linux

```bash
# Test on Arch (AUR installation)
# Test on Fedora 43+ (COPR installation)
# Test on Ubuntu 25+ (CI binary)
# Test on openSUSE Tumbleweed (CI binary)
```

---

## Code Style Guidelines

### Swift (macOS)

- Use SwiftUI for new UI components
- Follow Apple's Swift API guidelines
- 4 spaces for indentation
- Use meaningful variable names (avoid abbreviations)

### C# (Windows)

- .NET 8 and newer
- WinForms for UI
- Follow Microsoft C# coding conventions
- Use property-based initialization where possible
- Proper error handling and logging

### Python (Linux + pipeline)

- Python 3.11+
- Follow PEP 8 style guide
- Use type hints throughout `speechprint_pkg/`
- GTK4 for GUI

### Bash/Shell

- POSIX-compliant where possible
- Error handling with `set -euo pipefail`
- Clear variable naming
- Comment complex logic

---

## CI/CD Pipeline

GitHub Actions workflows automatically build and publish releases:

### macOS Workflow

```yaml
# Builds on macos-14 (Apple Silicon compatible)
# Outputs: SpeechPrint-X.X.X.pkg, SHA256 hash
```

**Steps:**

1. Verify source files
2. Build SpeechPrint.app as universal binary
3. Package .pkg installer
4. Verify binary architectures
5. Generate SHA256 hash
6. Upload artifacts

### Windows Workflow

```yaml
# Builds on windows-latest
# Outputs: SpeechPrint-X.X.X.exe, SHA256 hash
```

**Steps:**

1. Verify source files
2. Restore .NET dependencies
3. Build solution (Release mode)
4. Publish self-contained executable
5. Verify embedded resources
6. Generate SHA256 hash
7. Upload artifacts

### Linux Workflow

```yaml
# Builds on ubuntu-latest
# Outputs: SpeechPrint-X.X.X.tar.gz, SHA256 hash
```

**Steps:**

1. Verify source files
2. Make scripts executable
3. Build distribution package
4. Verify tarball contents
5. Generate SHA256 hash
6. Upload artifacts

---

## Release Process

### 1. Prepare Release

- Update version numbers in all files:
  - `pyproject.toml` (Linux)
  - `.csproj` files (Windows)
  - Script versions (macOS)
- Update documentation if needed
- Create release notes

### 2. Tag and Push

```bash
git tag v0.X.Y
git push origin v0.X.Y
```

This automatically triggers CI/CD workflows.

### 3. Generate Release Body

```bash
.github/scripts/generate-release-body.sh \
  --version 0.X.Y \
  --macos-sha256 <hash> \
  --windows-sha256 <hash> \
  --linux-sha256 <hash> \
  --output release-body.md
```

### 4. Create GitHub Release

- Use generated `release-body.md` as description
- Upload artifacts from CI/CD
- Mark as pre-release if applicable
- Publish

---

## Pull Request Guidelines

Before submitting:

1. **Test your changes:**
   - Build successfully on your platform
   - Test installer on a clean system
   - Test both GUI and CLI (where applicable)
   - Run `speechprint annotate` on a known WAV and diff outputs

2. **Documentation:**
   - Update relevant docs if behavior changes
   - Add comments for complex logic
   - Update README if user-facing changes

3. **Code quality:**
   - Follow style guidelines for your language
   - No hardcoded paths (use environment variables)
   - Proper error handling and user feedback

4. **Commit messages:**
   - Clear, concise descriptions
   - Reference issues when applicable
   - One logical change per commit

---
