#!/usr/bin/env python3
r"""
prosody2tract.py: Convert ProsodyPrompt TextGrid to articulatory synthesis parameters

Converts prosody tier symbols (/, //, \, etc.) to F0 targets and articulatory
trajectories for synthesis.

Usage:
    python prosody2tract.py recording.TextGrid
    python prosody2tract.py recording.TextGrid --f0-floor 85 --f0-ceiling 300
    python prosody2tract.py --list-generators
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor, F0Compiler
from prosody_resynthesis.textgrid_io import TextGridReader


def list_generators():
    """List available movement generators."""
    generators = {
        'linear': 'Straight-line interpolation',
        'sigmoid': 'S-curve (slow at extremes, fast in middle)',
        'ease_in_out': 'Smoothstep cubic',
        'exponential': 'Exponential curve',
        'quadratic': 'Quadratic acceleration',
        'cubic': 'Cubic acceleration',
    }
    print("Available movement generators:")
    for name, desc in generators.items():
        print(f"  {name:15s} - {desc}")


def list_parameters():
    """List articulatory parameters."""
    params = {
        'f0': 'Fundamental frequency (Hz)',
        'pressure': 'Subglottal pressure',
        'TCX': 'Tongue body constriction (front-back)',
        'TCY': 'Tongue body constriction (height)',
        'TTX': 'Tongue tip position (front-back)',
        'TTY': 'Tongue tip height',
        'TBX': 'Tongue blade position',
        'TBY': 'Tongue blade height',
        'VO': 'Velum opening',
        'LPX': 'Lip position (front-back)',
        'LPY': 'Lip position (height)',
        'JAW': 'Jaw opening',
    }
    print("Articulatory parameters:")
    for param, desc in params.items():
        print(f"  {param:5s} - {desc}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert ProsodyPrompt prosody tier to articulatory parameters'
    )
    parser.add_argument('textgrid', nargs='?', help='Input TextGrid file')
    parser.add_argument('--f0-floor', type=float, default=75, help='Minimum F0 (Hz)')
    parser.add_argument('--f0-ceiling', type=float, default=300, help='Maximum F0 (Hz)')
    parser.add_argument('--generator', default='linear', help='Movement generator (linear, sigmoid, ease_in_out, etc.)')
    parser.add_argument('--list-generators', action='store_true', help='List available generators')
    parser.add_argument('--list-params', action='store_true', help='List articulatory parameters')
    parser.add_argument('--output', help='Output file (default: recording_tract.txt)')

    args = parser.parse_args()

    # Handle info requests
    if args.list_generators:
        list_generators()
        return 0

    if args.list_params:
        list_parameters()
        return 0

    # Require TextGrid for actual processing
    if not args.textgrid:
        parser.print_help()
        return 1

    try:
        # Load TextGrid
        tg_path = Path(args.textgrid)
        if not tg_path.exists():
            print(f"❌ TextGrid not found: {tg_path}")
            return 1

        print(f"Loading: {tg_path}")
        editor = ProsodyEditor(str(tg_path))
        print(f"✓ Loaded {len(editor.syllables)} syllables")

        # Compile F0 targets
        print(f"\nCompiling F0 targets (floor={args.f0_floor}, ceiling={args.f0_ceiling})...")
        targets = editor.compile_to_f0_targets(
            f0_floor=args.f0_floor,
            f0_ceiling=args.f0_ceiling
        )
        print(f"✓ Generated {len(targets)} F0 targets")

        # Map to articulatory parameters
        print(f"\nMapping to articulatory parameters...")
        tract_params = []

        for target in targets:
            # F0 → pitch parameter
            f0_param = target.f0

            # Prosody symbols → articulation
            # High prosody → higher tongue position
            # Rising → forward tongue movement
            # Accent → more lip rounding/jaw opening

            syl_idx = 0
            for syl in editor.syllables:
                if syl.onset <= target.time < syl.offset:
                    break

            components = editor.syllables[0].symbol_components if editor.syllables else {}

            # Generate tract parameters based on prosody
            tcp_y = 0.5  # Default tongue body height
            if components.get('height') == 'high':
                tcp_y = 0.7  # Raise tongue for high prosody
            elif components.get('height') == 'low':
                tcp_y = 0.3  # Lower tongue for low prosody

            ttx = 0.5  # Tongue tip front-back
            if components.get('direction') == 'rising' or 'rising' in str(components.get('direction', '')):
                ttx = 0.6  # Advance tongue for rising pitch

            jaw = 0.4  # Jaw opening
            if components.get('has_accent'):
                jaw = 0.5  # Open jaw more for accents

            tract_params.append({
                'time': target.time,
                'f0': f0_param,
                'TCY': tcp_y,
                'TTX': ttx,
                'JAW': jaw,
                'VO': 0.0,  # Velum closed
            })

        # Write output
        output_file = args.output or f"{tg_path.stem}_tract.txt"
        print(f"\nWriting tract parameters to: {output_file}")

        with open(output_file, 'w') as f:
            f.write("# Articulatory tract parameters\n")
            f.write("# time(s)\tf0(Hz)\tTCY\tTTX\tJAW\tVO\n")
            for params in tract_params:
                f.write(f"{params['time']:.3f}\t{params['f0']:.1f}\t{params['TCY']:.2f}\t{params['TTX']:.2f}\t{params['JAW']:.2f}\t{params['VO']:.2f}\n")

        print(f"✓ Written {len(tract_params)} parameters")
        print("\n✅ Conversion complete")
        print(f"   Output: {output_file}")
        print(f"   Generator: {args.generator}")
        print(f"   Parameters: f0, TCY (tongue body height), TTX (tongue tip front-back), JAW, VO (velum)")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
