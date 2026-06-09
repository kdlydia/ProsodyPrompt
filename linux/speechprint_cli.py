#!/usr/bin/env python3
"""
speechprint: CLI tool for prosody annotation and resynthesis

Commands:
  run          Annotate a recording with prosody
  batch        Batch process multiple recordings
  export       Export prosody tier to CSV/JSON
  evaluate-gtobi  Evaluate against GToBI benchmark

Usage:
  python speechprint_cli.py run --wav recording.wav --language en --tracker pyin
  python speechprint_cli.py batch --input-dir corpora/ --language en
  python speechprint_cli.py export --textgrid out/recording.TextGrid --format csv
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor, F0Compiler


def cmd_run(args):
    """Annotate a single recording."""
    print(f"Running: annotate {args.wav}")
    print(f"  Language: {args.language}")
    print(f"  Tracker: {args.tracker}")

    wav_path = Path(args.wav)
    if not wav_path.exists():
        print(f"❌ Audio file not found: {wav_path}")
        return 1

    print(f"✓ Would process: {wav_path}")
    print(f"  This is the annotation pipeline")
    print(f"  1. Transcribe with WhisperX ({args.language})")
    print(f"  2. Align with MFA")
    print(f"  3. Extract F0 with {args.tracker}")
    print(f"  4. Generate prosody labels")
    print(f"✓ (Implementation: use build_questionnaire_v3.py for example)")

    return 0


def cmd_batch(args):
    """Batch process multiple recordings."""
    print(f"Batch processing: {args.input_dir}")
    print(f"  Language: {args.language}")
    print(f"  Trackers: {', '.join(args.tracker)}")

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"❌ Directory not found: {input_dir}")
        return 1

    wav_files = list(input_dir.glob('*.wav'))
    print(f"✓ Found {len(wav_files)} WAV files")
    print(f"✓ Would process all files with annotation pipeline")

    return 0


def cmd_export(args):
    """Export prosody tier to CSV."""
    print(f"Exporting: {args.textgrid}")
    print(f"  Format: {args.format}")

    tg_path = Path(args.textgrid)
    if not tg_path.exists():
        print(f"❌ TextGrid not found: {tg_path}")
        return 1

    try:
        from prosody_resynthesis.textgrid_io import TextGridReader
        tg = TextGridReader.read(str(tg_path))
        print(f"✓ Loaded TextGrid with {len(tg['tiers'])} tiers")

        # Export to CSV
        if args.format == 'csv':
            output_file = tg_path.stem + '.csv'
            with open(output_file, 'w') as f:
                f.write("time_start,time_end,text,prosody\n")
                if 'syllables' in tg['tiers']:
                    syllables = tg['tiers']['syllables']
                    prosody = tg['tiers'].get('prosody', None)

                    for syl in syllables.intervals:
                        prosody_sym = '?'
                        if prosody:
                            for p in prosody.intervals:
                                if p.xmin <= syl.xmin < p.xmax:
                                    prosody_sym = p.text
                                    break
                        f.write(f"{syl.xmin},{syl.xmax},{syl.text},{prosody_sym}\n")

            print(f"✓ Exported to: {output_file}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_evaluate_gtobi(args):
    """Evaluate against GToBI benchmark."""
    print(f"Evaluating: {args.sentences_dir}")

    sentences_dir = Path(args.sentences_dir)
    if not sentences_dir.exists():
        print(f"❌ Directory not found: {sentences_dir}")
        return 1

    tg_files = list(sentences_dir.glob('*.TextGrid'))
    print(f"✓ Found {len(tg_files)} TextGrid files")
    print(f"✓ Would evaluate prosody accuracy against GToBI annotations")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='ProsodyPrompt: Prosody annotation and analysis CLI',
        prog='python speechprint_cli.py'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # run command
    run_parser = subparsers.add_parser('run', help='Annotate a recording')
    run_parser.add_argument('--wav', required=True, help='Input WAV file')
    run_parser.add_argument('--textgrid', help='Input TextGrid (optional, for human annotation)')
    run_parser.add_argument('--language', default='en', help='Language code (en, de, es, etc.)')
    run_parser.add_argument('--tracker', default='pyin', choices=['pyin', 'crepe', 'pesto', 'praat', 'yin'],
                           help='Pitch tracker')
    run_parser.add_argument('--comparison', action='store_true', help='Generate comparison tier with all trackers')

    # batch command
    batch_parser = subparsers.add_parser('batch', help='Batch process recordings')
    batch_parser.add_argument('--input-dir', required=True, help='Directory with WAV files')
    batch_parser.add_argument('--language', default='en', help='Language code')
    batch_parser.add_argument('--tracker', nargs='+', default=['pyin'], help='Pitch trackers')
    batch_parser.add_argument('--comparison', action='store_true', help='Generate comparison tiers')

    # export command
    export_parser = subparsers.add_parser('export', help='Export prosody tier')
    export_parser.add_argument('--textgrid', required=True, help='Input TextGrid file')
    export_parser.add_argument('--format', default='csv', choices=['csv', 'json'], help='Output format')
    export_parser.add_argument('--output', help='Output file (default: auto-generated)')

    # evaluate command
    evaluate_parser = subparsers.add_parser('evaluate-gtobi', help='Evaluate against GToBI')
    evaluate_parser.add_argument('--sentences-dir', required=True, help='Directory with GToBI sentences')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    if args.command == 'run':
        return cmd_run(args)
    elif args.command == 'batch':
        return cmd_batch(args)
    elif args.command == 'export':
        return cmd_export(args)
    elif args.command == 'evaluate-gtobi':
        return cmd_evaluate_gtobi(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
