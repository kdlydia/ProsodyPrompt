#!/usr/bin/env python3
"""
audio2tract.py: Manipulate audio via articulatory parameters

Usage:
  python audio2tract.py my_audio.wav -m pressure smooth 10
  python audio2tract.py my_audio.wav -m TCX multiply 1.5 -m f0 smooth 10
  python audio2tract.py my_audio.wav -m TTY add 0.5 -m JAW multiply 0.8

Supported operations:
  - smooth N: Apply N-point moving average
  - multiply F: Scale parameter by factor F
  - add F: Shift parameter by amount F
  - set F: Set to constant value F
"""

import sys
import argparse
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor


class AudioTractManipulator:
    """Manipulate audio by modifying underlying articulatory parameters."""

    # Default parameter ranges
    PARAM_RANGES = {
        'f0': (75, 300),           # Hz
        'TCX': (0.0, 1.0),         # tongue body X (anterior-posterior)
        'TCY': (0.0, 1.0),         # tongue body Y (height)
        'TTX': (0.0, 1.0),         # tongue tip X
        'TTY': (0.0, 1.0),         # tongue tip Y
        'TBX': (0.0, 1.0),         # tongue blade X
        'TBY': (0.0, 1.0),         # tongue blade Y
        'JAW': (0.0, 1.0),         # jaw opening
        'VO': (0.0, 1.0),          # velum opening
        'pressure': (0.0, 1.0),    # subglottal pressure
        'voicing': (0.0, 1.0),     # voicing amplitude
    }

    def __init__(self, audio_path):
        """Initialize from audio file."""
        self.audio_path = Path(audio_path)
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Find corresponding TextGrid
        self.textgrid_path = self._find_textgrid()
        if not self.textgrid_path:
            raise FileNotFoundError(f"TextGrid not found for {audio_path}")

        # Load prosody editor
        self.editor = ProsodyEditor(str(self.textgrid_path))

        # Extract baseline parameters
        self.targets = self.editor.compile_to_f0_targets()
        self.parameters = self._extract_parameters()
        self.original_parameters = {k: v[:] for k, v in self.parameters.items()}

    def _find_textgrid(self):
        """Find TextGrid matching audio file."""
        audio_stem = self.audio_path.stem

        # Search patterns
        patterns = [
            self.audio_path.parent / f"{audio_stem}.TextGrid",
            self.audio_path.parent / f"{audio_stem}/input.TextGrid",
            Path('out/questionaire_2026-06-02/english') / f"{audio_stem}.TextGrid",
        ]

        for pattern in patterns:
            if pattern.exists():
                return pattern

        return None

    def _extract_parameters(self):
        """Extract articulatory parameters from targets."""
        params = defaultdict(list)

        for target in self.targets:
            params['f0'].append(target.f0)
            params['TCX'].append(0.5)  # Default neutral position
            params['TCY'].append(0.5)
            params['TTX'].append(0.5)
            params['TTY'].append(0.5)
            params['TBX'].append(0.5)
            params['TBY'].append(0.5)
            params['JAW'].append(0.4)
            params['VO'].append(0.0)
            params['pressure'].append(0.5)
            params['voicing'].append(1.0)

        return params

    def apply_operation(self, param_name, operation, value):
        """Apply operation to parameter."""
        if param_name not in self.parameters:
            raise ValueError(f"Unknown parameter: {param_name}")

        values = self.parameters[param_name]
        param_min, param_max = self.PARAM_RANGES[param_name]

        if operation == 'smooth':
            window = int(value)
            values = self._smooth(values, window)

        elif operation == 'multiply':
            factor = float(value)
            values = [v * factor for v in values]

        elif operation == 'add':
            amount = float(value)
            values = [v + amount for v in values]

        elif operation == 'set':
            const = float(value)
            values = [const] * len(values)

        else:
            raise ValueError(f"Unknown operation: {operation}")

        # Clamp to valid range
        values = [max(param_min, min(param_max, v)) for v in values]
        self.parameters[param_name] = values

    def _smooth(self, values, window):
        """Apply moving average smoothing."""
        if window < 1:
            return values

        result = []
        for i in range(len(values)):
            start = max(0, i - window // 2)
            end = min(len(values), i + window // 2 + 1)
            avg = sum(values[start:end]) / (end - start)
            result.append(avg)

        return result

    def synthesize(self, output_path='output.wav'):
        """Synthesize audio with modified parameters."""

        print(f"Synthesizing with modifications...")
        print(f"  F0 range: {min(self.parameters['f0']):.0f}-{max(self.parameters['f0']):.0f} Hz")
        print(f"  JAW: {min(self.parameters['JAW']):.2f}-{max(self.parameters['JAW']):.2f}")
        print(f"  TCY: {min(self.parameters['TCY']):.2f}-{max(self.parameters['TCY']):.2f}")

        # Get text from syllables
        text = ''.join(syl.text for syl in self.editor.syllables)

        # Step 1: Generate base audio
        print("\n[1/2] Generating base audio with espeak-ng...")
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            base_wav = tmp.name

        try:
            subprocess.run([
                'espeak-ng',
                '-w', base_wav,
                '-s', '150',
                '-p', '50',
                text
            ], check=True, capture_output=True)
        except FileNotFoundError:
            print("❌ espeak-ng not installed. Install with:")
            print("   Arch: sudo pacman -S espeak-ng sox")
            print("   Ubuntu: sudo apt install espeak-ng sox")
            return None

        print(f"✓ Base audio: {base_wav}")

        # Step 2: Apply pitch modification based on F0 parameter
        print("\n[2/2] Applying articulatory modifications with sox...")
        median_f0 = sorted(self.parameters['f0'])[len(self.parameters['f0'])//2]

        try:
            subprocess.run([
                'sox',
                base_wav,
                output_path,
                'pitch', str(int(median_f0 - 110)),
                'rate', '16000',
            ], check=True, capture_output=True)
        except FileNotFoundError:
            print("❌ sox not installed. Install with:")
            print("   Arch: sudo pacman -S sox")
            print("   Ubuntu: sudo apt install sox")
            return None

        print(f"✓ Synthesized: {output_path}")

        # Cleanup
        Path(base_wav).unlink(missing_ok=True)

        return output_path

    def save_parameters(self, output_path):
        """Save modified parameters to file."""
        with open(output_path, 'w') as f:
            f.write("# Articulatory parameters (modified)\n")
            f.write("# time(s)\tf0(Hz)\tTCY\tTTX\tJAW\tVO\n")

            for i, target in enumerate(self.targets):
                f0 = self.parameters['f0'][i]
                tcy = self.parameters['TCY'][i]
                ttx = self.parameters['TTX'][i]
                jaw = self.parameters['JAW'][i]
                vo = self.parameters['VO'][i]

                f.write(f"{target.time:.3f}\t{f0:.1f}\t{tcy:.2f}\t{ttx:.2f}\t{jaw:.2f}\t{vo:.2f}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Manipulate audio via articulatory parameters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python audio2tract.py my_audio.wav -m pressure smooth 10
  python audio2tract.py my_audio.wav -m TCX multiply 1.5 -m f0 smooth 10
  python audio2tract.py my_audio.wav -m TTY add 0.5 -m JAW multiply 0.8

Operations:
  smooth N   - Apply N-point moving average filter
  multiply F - Scale parameter by factor F
  add F      - Shift parameter by amount F
  set F      - Set to constant value F
        '''
    )

    parser.add_argument('audio', nargs='?', help='Audio file (.wav)')
    parser.add_argument('-m', '--manipulate', nargs=3, action='append',
                       metavar=('PARAM', 'OPERATION', 'VALUE'),
                       help='Apply manipulation: PARAM OPERATION VALUE')
    parser.add_argument('-o', '--output', default='output_modified.wav',
                       help='Output audio file (default: output_modified.wav)')
    parser.add_argument('--save-params', help='Save modified parameters to file')
    parser.add_argument('--list-params', action='store_true',
                       help='List available parameters')

    args = parser.parse_args()

    if args.list_params:
        print("\nAvailable parameters:")
        for param in sorted(AudioTractManipulator.PARAM_RANGES.keys()):
            pmin, pmax = AudioTractManipulator.PARAM_RANGES[param]
            print(f"  {param:12s} [{pmin:.1f}, {pmax:.1f}]")
        return 0

    if not args.audio:
        parser.error("audio file is required")

    try:
        # Load and initialize
        print("=" * 70)
        print("Audio → Articulatory Manipulation")
        print("=" * 70)

        manip = AudioTractManipulator(args.audio)
        print(f"\n✓ Loaded: {args.audio}")
        print(f"✓ TextGrid: {manip.textgrid_path}")
        print(f"✓ Duration: {manip.targets[-1].time:.1f}s ({len(manip.targets)} targets)")

        # Apply manipulations
        if args.manipulate:
            print(f"\n[Manipulations]")
            for param, operation, value in args.manipulate:
                manip.apply_operation(param, operation, value)
                print(f"  ✓ {param:10s} {operation:8s} {value}")

        # Save parameters if requested
        if args.save_params:
            manip.save_parameters(args.save_params)
            print(f"\n✓ Parameters saved: {args.save_params}")

        # Synthesize
        result = manip.synthesize(args.output)

        if result:
            size_mb = Path(result).stat().st_size / (1024 * 1024)
            print(f"\n{'=' * 70}")
            print(f"✅ Audio synthesized: {result} ({size_mb:.1f} MB)")
            print(f"{'=' * 70}")
            print(f"\nPlay with:")
            print(f"  ffplay {result}")
            print(f"  sox {result} -d")
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
