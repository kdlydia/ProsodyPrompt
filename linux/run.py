#!/usr/bin/env python3
"""ProsodyPrompt — interactive CLI launcher.

Run from the linux/ directory:

    python run.py

No GUI required. Works like pacman: asks questions, shows options,
lets you pick with numbers or y/n, then runs the pipeline.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ── Resolve root automatically ────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
os.environ.setdefault("SPEECHPRINT_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT))

# ── ANSI colours ──────────────────────────────────────────────────────────────
R  = "\033[0m"       # reset
B  = "\033[1m"       # bold
DIM= "\033[2m"       # dim
G  = "\033[1;32m"    # green bold
Y  = "\033[1;33m"    # yellow bold
C  = "\033[1;36m"    # cyan bold
E  = "\033[1;31m"    # red bold

def hline(char="─", width=56):
    print(DIM + char * width + R)

def header(text):
    print()
    hline("═")
    print(f"{C}{B}  {text}{R}")
    hline("═")

def section(text):
    print()
    print(f"{B}{text}{R}")
    hline()

def ok(text):   print(f"  {G}✓{R}  {text}")
def warn(text): print(f"  {Y}!{R}  {text}")
def err(text):  print(f"  {E}✗{R}  {text}")
def info(text): print(f"  {DIM}{text}{R}")

def ask(prompt, default="y"):
    marker = "[Y/n]" if default.lower() == "y" else "[y/N]"
    ans = input(f"\n  {B}{prompt}{R} {DIM}{marker}{R} ").strip().lower()
    if not ans:
        return default.lower() == "y"
    return ans in ("y", "yes")

def pick(prompt, options, default=1):
    """Show numbered options, return chosen index (0-based)."""
    print(f"\n  {B}{prompt}{R}")
    for i, (label, desc) in enumerate(options, 1):
        marker = f"{G}→{R}" if i == default else " "
        print(f"  {marker} {B}{i}{R}) {label}  {DIM}{desc}{R}")
    while True:
        ans = input(f"\n  Select [{DIM}1–{len(options)}{R}, default {default}]: ").strip()
        if not ans:
            return default - 1
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return int(ans) - 1
        warn("Please enter a number from the list.")

def multi_pick(prompt, options, defaults):
    """Toggle-style multi-select. Returns list of selected keys."""
    selected = set(k for k, *_ in options if k in defaults)
    print(f"\n  {B}{prompt}{R}")
    print(f"  {DIM}Enter numbers to toggle. Press Enter when done.{R}")
    while True:
        print()
        for i, (key, label, desc) in enumerate(options, 1):
            tick = f"{G}[✓]{R}" if key in selected else f"{DIM}[ ]{R}"
            print(f"  {tick}  {B}{i}{R}) {label}  {DIM}{desc}{R}")
        ans = input(f"\n  Toggle [{DIM}1–{len(options)}{R}] or Enter to confirm: ").strip()
        if not ans:
            break
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            key = options[int(ans) - 1][0]
            if key in selected:
                selected.discard(key)
            else:
                selected.add(key)
        else:
            warn("Enter a number or press Enter to confirm.")
    return [k for k, *_ in options if k in selected]


# ── Data ──────────────────────────────────────────────────────────────────────
COMMON_LANGUAGES = [
    ("en", "English",    "MFA phone-level alignment available"),
    ("de", "German",     "WhisperX word-level"),
    ("es", "Spanish",    "WhisperX word-level"),
    ("fr", "French",     "WhisperX word-level"),
    ("it", "Italian",    "WhisperX word-level"),
    ("pt", "Portuguese", "WhisperX word-level"),
    ("nl", "Dutch",      "WhisperX word-level"),
    ("ru", "Russian",    "WhisperX word-level"),
    ("zh", "Mandarin",   "WhisperX word-level"),
    ("ja", "Japanese",   "WhisperX word-level"),
    ("ar", "Arabic",     "WhisperX word-level"),
    ("hi", "Hindi",      "WhisperX word-level"),
]

PHON_SIMILAR = {
    "mtp": ("it", "Italian — closest vowel inventory for Oceanic/Vanuatu"),
    "cjp": ("es", "Spanish — closest inventory for Chibchan/Costa Rica"),
    "default": ("it", "Italian — broadest cross-lingual phoneme coverage"),
}

TRACKERS = [
    ("pyin",  "pYIN",       "Fast, reliable V/UV detection. Best for clean studio speech."),
    ("crepe", "CREPE",      "Neural network. Best for field/archival recordings."),
    ("pesto", "PESTO",      "Self-supervised. Different error profile — good for comparison."),
    ("praat", "Praat AC",   "Signal-processing reference. Known octave-error risk."),
    ("yin",   "YIN",        "No V/UV detector — not recommended for prosody labelling."),
]

DEPS = [
    ("librosa",      "librosa",           "pYIN pitch tracking"),
    ("torchcrepe",   "torchcrepe",        "CREPE pitch tracking"),
    ("pesto",        "pesto-pitch",       "PESTO pitch tracking"),
    ("parselmouth",  "parselmouth",       "Praat / intensity extraction"),
    ("whisper",      "openai-whisper",    "Whisper ASR fallback"),
]


# ── Dependency check ──────────────────────────────────────────────────────────
def check_deps():
    section("Dependency check")
    missing = []
    for module, package, purpose in DEPS:
        try:
            __import__(module)
            ok(f"{package}  ({purpose})")
        except ImportError:
            warn(f"{package} not found  ({purpose})")
            missing.append((module, package))

    # WhisperX
    try:
        import whisperx  # noqa
        ok("whisperx  (primary ASR)")
    except ImportError:
        warn("whisperx not found  (primary ASR)")
        missing.append(("whisperx", "whisperx"))

    # MFA
    mfa = shutil.which("mfa") or shutil.which(
        str(Path.home() / "miniforge3/envs/speechprint-mfa/bin/mfa"))
    if mfa:
        ok(f"mfa  ({mfa})")
    else:
        warn("mfa not found  (forced alignment for English)")
        missing.append(("mfa", "conda: mfa (see MFA docs)"))

    return missing


def install_missing(missing):
    if not missing:
        ok("All dependencies present.")
        return
    print()
    warn(f"{len(missing)} package(s) not installed:")
    for _, pkg in missing:
        print(f"    • {pkg}")

    if not ask("Install missing packages now?"):
        info("Skipping installation. Some features may not work.")
        return

    for module, package in missing:
        if package.startswith("conda:"):
            warn(f"Manual installation required: {package}")
            info("  See: https://montreal-forced-aligner.readthedocs.io/")
            continue
        print(f"\n  Installing {package}…")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", package],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok(f"{package} installed.")
        else:
            err(f"Failed to install {package}:")
            print(f"  {result.stderr[:200]}")


# ── Annotation wizard ─────────────────────────────────────────────────────────
def annotation_wizard():
    header("ProsodyPrompt — Annotation Wizard")

    # ── Step 1: annotation source ─────────────────────────────────────────────
    section("Step 1 of 3 — Annotation source")
    print(f"""
  {B}Do you have a human-annotated TextGrid?{R}

  {G}→{R} 1) Yes — I have a TextGrid (DoReCo, ELAN export, fieldwork)
         Words, phones, and timing come from your file.
         Only F0 extraction and prosody labelling run automatically.

    2) No  — Run the full automatic pipeline
         Whisper → forced alignment → phonemization → prosody labels
""")
    has_annotation = pick("", [
        ("Human TextGrid",   "DoReCo / fieldwork annotation"),
        ("Automatic (ASR)",  "full pipeline from audio only"),
    ], default=2)[0] == 0 if False else None

    while True:
        ans = input(f"  Select [1/2, default 2]: ").strip()
        if not ans or ans == "2":
            has_annotation = False; break
        if ans == "1":
            has_annotation = True; break
        warn("Enter 1 or 2.")

    textgrid_path = None
    tier_suffix = "@TA"

    if has_annotation:
        while True:
            p = input(f"\n  {B}Path to TextGrid file:{R} ").strip()
            if p and Path(p).exists():
                textgrid_path = Path(p)
                ok(f"TextGrid: {textgrid_path.name}")
                break
            warn("File not found. Enter the full path to a .TextGrid file.")

        suffixes = ["@TA", "@6", "custom"]
        idx = pick("Tier suffix", [
            ("@TA",    "DoReCo standard (Daakie, most corpora)"),
            ("@6",     "DoReCo v2 (Cabécar, newer datasets)"),
            ("custom", "enter manually"),
        ], default=1)
        tier_suffix = suffixes[idx]
        if tier_suffix == "custom":
            tier_suffix = input("  Custom suffix: ").strip() or "@TA"

    # ── Step 2: language ──────────────────────────────────────────────────────
    section("Step 2 of 3 — Language")

    print(f"\n  {B}Common languages (ASR + alignment available):{R}")
    for i, (code, name, note) in enumerate(COMMON_LANGUAGES, 1):
        print(f"    {B}{i:2d}{R}) {name} ({code})  {DIM}{note}{R}")
    print(f"\n    {B} e{R}) Endangered / under-resourced language")

    language = "en"
    is_endangered = False

    while True:
        ans = input(f"\n  Select [1–{len(COMMON_LANGUAGES)}/e, default 1]: ").strip().lower()
        if not ans or ans == "1":
            language = COMMON_LANGUAGES[0][0]; break
        if ans == "e":
            is_endangered = True; break
        if ans.isdigit() and 1 <= int(ans) <= len(COMMON_LANGUAGES):
            language = COMMON_LANGUAGES[int(ans) - 1][0]; break
        warn("Enter a number or 'e' for endangered.")

    if is_endangered:
        iso = input(f"\n  {B}ISO 639-3 code{R} {DIM}(or press Enter to skip){R}: ").strip().lower()

        if ask("Find phonologically similar supported language?"):
            hint = PHON_SIMILAR.get(iso, PHON_SIMILAR["default"])
            print(f"\n  {G}Suggested:{R} {hint[1]}")
            if ask(f"Use {hint[0]} as the ASR model language?"):
                language = hint[0]
            else:
                custom = input("  Enter language code manually: ").strip() or "it"
                language = custom
        else:
            language = iso or "it"

        warn("ASR output will be phonetically plausible but lexically incorrect.")
        info("Prosody labels remain acoustically valid regardless of transcription quality.")

    ok(f"Language: {language}")

    # ── Step 3: tracker ───────────────────────────────────────────────────────
    section("Step 3 of 3 — Pitch tracker")

    trackers = multi_pick(
        "Select pitch trackers (toggle with number, Enter to confirm):",
        TRACKERS,
        defaults={"pyin", "crepe"},
    )

    if not trackers:
        warn("No tracker selected — defaulting to pYIN.")
        trackers = ["pyin"]

    comparison = ask("Generate comparison TextGrid (one prosody tier per tracker)?", default="y")

    # ── Summary ───────────────────────────────────────────────────────────────
    section("Summary")
    info(f"Source   : {'human TextGrid' if has_annotation else 'automatic ASR'}")
    if textgrid_path:
        info(f"TextGrid : {textgrid_path}")
        info(f"Suffix   : {tier_suffix}")
    info(f"Language : {language}")
    info(f"Trackers : {', '.join(trackers)}")
    info(f"Comparison mode: {comparison}")

    if not ask("Run annotation with these settings?"):
        info("Cancelled.")
        return None

    return {
        "has_annotation": has_annotation,
        "textgrid_path":  textgrid_path,
        "tier_suffix":    tier_suffix,
        "language":       language,
        "is_endangered":  is_endangered,
        "trackers":       trackers,
        "comparison":     comparison,
    }


# ── Run pipeline ──────────────────────────────────────────────────────────────
def run_pipeline(wav: Path, config: dict):
    section(f"Running annotation: {wav.name}")

    # Build CLI args for speechprint_pkg
    trackers = config["trackers"]
    language = config["language"]

    cmd = [
        sys.executable, "-m", "speechprint_pkg.cli",
        "annotate", str(wav),
        "--language", language,
        "--output", str(ROOT / "out"),
        "--tracker", *trackers,
    ]

    if config.get("has_annotation") and config.get("textgrid_path"):
        cmd += ["--textgrid", str(config["textgrid_path"]),
                "--tier-suffix", config["tier_suffix"]]

    if config.get("comparison"):
        cmd.append("--comparison")

    info(f"Command: {' '.join(cmd)}")
    print()

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                env={**os.environ, "SPEECHPRINT_ROOT": str(ROOT)})
        for line in proc.stdout:
            line = line.rstrip()
            if line.startswith("[") and "/" in line[:10]:
                print(f"  {G}{line}{R}")
            elif line.startswith("✗") or "error" in line.lower():
                err(line)
            elif line.startswith("✓") or "written" in line.lower():
                ok(line)
            else:
                info(line)
        proc.wait()
        if proc.returncode == 0:
            print()
            ok("Annotation complete.")
            out = ROOT / "out" / wav.stem / f"{wav.stem}.TextGrid"
            if out.exists():
                ok(f"TextGrid: {out}")
                if shutil.which("praat"):
                    if ask("Open in Praat?"):
                        subprocess.Popen(["praat", "--open", str(wav), str(out)])
        else:
            err(f"Pipeline exited with code {proc.returncode}.")
    except FileNotFoundError as e:
        err(f"Could not start pipeline: {e}")
        warn("Run option 3 (Install dependencies) first.")


# ── Main menu ─────────────────────────────────────────────────────────────────
def main():
    header("ProsodyPrompt  v0.3")
    print(f"""
  {DIM}Linguistic prosody annotation environment{R}
  {DIM}For Linux machines only.{R}
  {DIM}https://github.com/speechprint/ProsodyPrompt{R}
""")

    while True:
        section("Main menu")
        print(f"""
  {B}1{R})  Annotate a recording
  {B}2{R})  Batch annotate a folder
  {B}3{R})  Check / install dependencies
  {B}4{R})  Open output folder in file manager
  {B}q{R})  Quit
""")
        ans = input("  > ").strip().lower()

        if ans == "1":
            wav_str = input(f"\n  {B}Path to WAV file:{R} ").strip()
            wav = Path(wav_str)
            if not wav.exists():
                err(f"File not found: {wav_str}")
                continue
            config = annotation_wizard()
            if config:
                run_pipeline(wav, config)

        elif ans == "2":
            folder_str = input(f"\n  {B}Path to folder:{R} ").strip()
            folder = Path(folder_str)
            if not folder.is_dir():
                err(f"Directory not found: {folder_str}")
                continue
            wavs = sorted(folder.glob("*.wav"))
            if not wavs:
                warn("No WAV files found in that folder.")
                continue
            print(f"\n  Found {len(wavs)} WAV file(s):")
            for w in wavs[:10]:
                info(f"  • {w.name}")
            if len(wavs) > 10:
                info(f"  … and {len(wavs)-10} more")
            config = annotation_wizard()
            if config:
                for wav in wavs:
                    run_pipeline(wav, config)

        elif ans == "3":
            missing = check_deps()
            install_missing(missing)

        elif ans == "4":
            out = ROOT / "out"
            out.mkdir(exist_ok=True)
            xdg = shutil.which("xdg-open") or shutil.which("nautilus")
            if xdg:
                subprocess.Popen([xdg, str(out)])
                ok(f"Opened: {out}")
            else:
                info(f"Output folder: {out}")

        elif ans in ("q", "quit", "exit"):
            print(f"\n  {DIM}Bye.{R}\n")
            break

        else:
            warn("Enter a number 1–4 or q to quit.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Interrupted.{R}\n")
