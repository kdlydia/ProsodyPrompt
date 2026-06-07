#!/usr/bin/env python3
"""CLI: speechprint new <name> <location>, plus passthrough to speechprint_pkg"""

import sys
import subprocess
import argparse
from pathlib import Path
import os

_cli_dir = Path(__file__).parent
_lib_dir = _cli_dir.parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

try:
    from lib.config import get_config
except ImportError as e:
    print(
        "Error: Cannot import lib.config\n"
        f"sys.path: {sys.path}\n"
        f"Expected lib at: {_lib_dir}\n"
        f"Error: {e}",
        file=sys.stderr,
    )
    sys.exit(1)


def _passthrough_to_pipeline(args_list):
    """Forward annotate/linguist/ensemble/etc. to speechprint_pkg.cli."""
    try:
        cfg = get_config()
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.update(cfg.get_env_vars())

    try:
        result = subprocess.run(
            [sys.executable, "-m", "speechprint_pkg.cli"] + args_list, env=env
        )
        return result.returncode
    except FileNotFoundError:
        print(
            "Error: speechprint_pkg not found on PYTHONPATH.\n"
            "Run the installer first: ~/.local/SpeechPrint-X.X.X/SpeechPrint",
            file=sys.stderr,
        )
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog="speechprint",
        description="SpeechPrint corpus creator and annotator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  speechprint new MyCorpus ~/Corpora/
  speechprint new FieldRecordings . --language it
  speechprint annotate data/recording.wav --language de
  speechprint ensemble
  speechprint gui
        """,
    )

    subparsers = parser.add_subparsers(dest="cmd", help="Commands")

    new_parser = subparsers.add_parser("new", help="Create a new corpus")
    new_parser.add_argument("name", help="Corpus name")
    new_parser.add_argument(
        "location",
        nargs="?",
        default=".",
        help="Corpus location (default: current directory)",
    )
    new_parser.add_argument(
        "--language",
        default="en",
        help="Default corpus language (en, de, it, es, fr, cs)",
    )
    new_parser.add_argument(
        "--no-vscode", action="store_true", help="Skip VS Code configuration"
    )
    new_parser.add_argument(
        "--auto-ensemble",
        action="store_true",
        help="Run ensemble aggregation automatically after annotate",
    )

    gui_parser = subparsers.add_parser("gui", help="Launch graphical installer")

    # Annotation passthrough commands — defined for --help output only.
    # Real argument parsing happens in speechprint_pkg.cli.
    for name, desc in [
        ("annotate", "Annotate a WAV file (full pipeline, steps 1–10)"),
        ("linguist", "Interactive annotation — drop a WAV, pick language"),
        ("ensemble", "Aggregate verified per-recording outputs"),
        ("transcribe", "Run WhisperX transcription only"),
        ("align", "Run MFA forced alignment only"),
        ("prosody", "Extract prosody (F0, intensity, jitter, formants)"),
        ("export", "Export to TextGrid / EAF / CSV / JSON"),
        ("corpus", "Batch-annotate a directory of WAVs"),
    ]:
        subparsers.add_parser(name, help=desc, add_help=False)

    parser.add_argument("--version", action="version", version="%(prog)s 0.3.0")
    parser.add_argument(
        "--config",
        action="store_true",
        help="Show configuration and exit",
    )

    # Pre-scan argv: if cmd is a passthrough command, hand off without parsing the rest
    PASSTHROUGH = {
        "annotate", "linguist", "ensemble", "transcribe",
        "align", "prosody", "export", "export-zip", "corpus",
    }
    if len(sys.argv) >= 2 and sys.argv[1] in PASSTHROUGH:
        return _passthrough_to_pipeline(sys.argv[1:])

    args = parser.parse_args()

    if args.config:
        try:
            cfg = get_config()
            print(f"SpeechPrint Configuration")
            print(f"=========================")
            print(f"Root: {cfg.root}")
            print(f"Scripts: {cfg.scripts_dir}")
            print(f"Templates: {cfg.templates_dir}")
            print(f"Supported languages: {', '.join(cfg.supported_languages)}")
            print(f"Default language: {cfg.default_language}")
            print(f"\nEnvironment variables:")
            for key, value in cfg.get_env_vars().items():
                print(f"  {key}={value}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return 0

    if args.cmd == "new":
        try:
            cfg = get_config()
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            sys.exit(1)

        script = cfg.get_script("create_corpus_sh")

        if not script.exists():
            print(f"Error: create_corpus.sh not found at {script}", file=sys.stderr)
            sys.exit(1)

        script.chmod(0o755)

        cmd = [str(script), "new", args.name, args.location, "--language", args.language]
        if args.no_vscode:
            cmd.append("--no-vscode")
        if args.auto_ensemble:
            cmd.append("--auto-ensemble")

        try:
            env = os.environ.copy()
            env.update(cfg.get_env_vars())

            result = subprocess.run(cmd, env=env)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(
                f"Error: Corpus creation failed with exit code {e.returncode}",
                file=sys.stderr,
            )
            return e.returncode
        except FileNotFoundError:
            print(f"Error: Script not found: {script}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.cmd == "gui":
        try:
            from lib.main import SpeechPrintApp

            cfg = get_config()
            app = SpeechPrintApp()
            return app.run([])
        except ImportError:
            print("Error: GUI dependencies not installed", file=sys.stderr)
            print("Try: pip install PyGObject", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())


# Optional evaluation link
EVALUATION_FORM_URL = "https://google.com/forms/speechprint-evaluation"

