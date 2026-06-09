#!/usr/bin/env python3
"""Interactive CLI for prosody resynthesis.

Workflow:
1. Load TextGrid with prosody tier
2. Edit symbols interactively
3. Synthesize with cloned voice
4. Export modified TextGrid
"""

import argparse
import sys
from pathlib import Path

from prosody_resynthesis import (
    CoquiSynthesizer,
    F0Compiler,
    ProsodyEditor,
    TextGridReader,
)
from prosody_resynthesis.utils import detect_speaker_pitch_range, load_or_extract_f0


def main():
    parser = argparse.ArgumentParser(
        description="Prosody Resynthesis: Edit prosody and re-synthesize speech",
    )
    parser.add_argument("textgrid", help="Path to TextGrid with prosody tier")
    parser.add_argument(
        "--audio",
        help="Original audio file (for voice cloning)",
        required=False,
    )
    parser.add_argument(
        "--speaker",
        default="speaker",
        help="Speaker name for voice cloning",
    )
    parser.add_argument(
        "--output",
        help="Output directory (default: out/)",
        default="out",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Device for synthesis",
    )
    parser.add_argument(
        "--mode",
        choices=["interactive", "batch"],
        default="interactive",
        help="Edit mode",
    )
    parser.add_argument(
        "--f0-floor",
        type=float,
        help="Minimum F0 for speaker (auto-detect if not specified)",
    )
    parser.add_argument(
        "--f0-ceiling",
        type=float,
        help="Maximum F0 for speaker (auto-detect if not specified)",
    )

    args = parser.parse_args()

    # Validate inputs
    textgrid_path = Path(args.textgrid)
    if not textgrid_path.exists():
        print(f"Error: TextGrid not found: {textgrid_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize editor
        print(f"Loading TextGrid: {textgrid_path}")
        editor = ProsodyEditor(str(textgrid_path), args.audio, args.speaker)
        print(f"Loaded: {len(editor.syllables)} syllables")
        print()

        # Auto-detect pitch range if audio provided
        f0_floor = args.f0_floor
        f0_ceiling = args.f0_ceiling

        if args.audio:
            print(f"Detecting pitch range from: {args.audio}")
            f0_array, times = load_or_extract_f0(args.audio)
            f0_floor, f0_ceiling = detect_speaker_pitch_range(f0_array)
            print(f"Pitch range: {f0_floor:.1f} – {f0_ceiling:.1f} Hz")
            print()

        # Interactive editing
        if args.mode == "interactive":
            _interactive_edit(editor, output_dir, f0_floor, f0_ceiling, args)
        else:
            _batch_process(editor, output_dir, f0_floor, f0_ceiling, args)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _interactive_edit(editor, output_dir, f0_floor, f0_ceiling, args):
    """Interactive editing session."""
    print("Interactive Prosody Editor")
    print("=" * 60)
    print("Commands:")
    print("  list              Show all syllables")
    print("  edit N SYMBOL     Change symbol for syllable N")
    print("  accent N          Toggle accent on syllable N")
    print("  height N high|mid|low  Change height")
    print("  direction N rising|falling|level  Change direction")
    print("  preview N         Synthesize one syllable")
    print("  synthesize        Full synthesis with all changes")
    print("  export FILE       Save modified TextGrid")
    print("  reset             Reset all changes")
    print("  quit              Exit")
    print()

    synth = None
    if args.audio:
        print("Initializing Coqui TTS...")
        synth = CoquiSynthesizer(device=args.device)
        synth.clone_voice(args.audio, args.speaker)
        print("Voice cloned successfully")
        print()

    while True:
        try:
            cmd = input("> ").strip().lower().split()

            if not cmd:
                continue

            if cmd[0] == "quit":
                break

            elif cmd[0] == "list":
                print(editor.summary())

            elif cmd[0] == "edit" and len(cmd) >= 3:
                idx = int(cmd[1])
                symbol = " ".join(cmd[2:])
                editor.modify_symbol(idx, symbol)
                print(f"Modified syllable {idx}: {symbol}")

            elif cmd[0] == "accent" and len(cmd) >= 2:
                idx = int(cmd[1])
                editor.modify_accent(idx, add=True)
                print(f"Added accent to syllable {idx}")

            elif cmd[0] == "height" and len(cmd) >= 3:
                idx = int(cmd[1])
                height = cmd[2]
                editor.modify_height(idx, height)
                print(f"Changed height of syllable {idx} to {height}")

            elif cmd[0] == "direction" and len(cmd) >= 3:
                idx = int(cmd[1])
                direction = cmd[2]
                editor.modify_direction(idx, direction)
                print(f"Changed direction of syllable {idx} to {direction}")

            elif cmd[0] == "synthesize":
                if not synth:
                    print("Error: No audio provided for voice cloning")
                    continue

                print("Synthesizing...")
                targets = editor.compile_to_f0_targets(f0_floor, f0_ceiling)
                print(f"Compiled {len(targets)} F0 targets")

                # TODO: Full synthesis with concatenation
                # For now, just show targets
                f0_vals = [t.f0 for t in targets]
                print(f"F0 range: {min(f0_vals):.1f} – {max(f0_vals):.1f} Hz")

            elif cmd[0] == "export" and len(cmd) >= 2:
                output_path = output_dir / cmd[1]
                editor.export_to_textgrid(str(output_path))
                print(f"Exported to: {output_path}")

            elif cmd[0] == "reset":
                editor.reset_all()
                print("Reset all changes")

            else:
                print("Unknown command")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def _batch_process(editor, output_dir, f0_floor, f0_ceiling, args):
    """Batch processing mode."""
    print("Batch Processing Mode")
    print("=" * 60)

    # Example: synthesize with all changes
    print("Compiling prosody symbols to F0 targets...")
    targets = editor.compile_to_f0_targets(f0_floor, f0_ceiling)
    print(f"Generated {len(targets)} F0 targets")

    # Export modified TextGrid
    output_tg = output_dir / "prosody_resynthesized.TextGrid"
    editor.export_to_textgrid(str(output_tg))
    print(f"Exported TextGrid: {output_tg}")

    # Show summary
    print()
    print(editor.summary())


if __name__ == "__main__":
    sys.exit(main())
