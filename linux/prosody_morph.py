#!/usr/bin/env python3
"""
prosody_morph.py: Morph prosody between two speakers

Combines the articulatory trajectory of one speaker with the prosody
(F0 contour) of another, creating a morphed version.

Usage:
  python prosody_morph.py \\
    --prima speaker_a.wav \\
    --secunda speaker_b.wav \\
    --blend 0.5
"""

import sys
import argparse
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor


class ProsodyMorpher:
    """Morph prosody between two speakers."""

    def __init__(self, prima_path, secunda_path):
        """Initialize with two audio/TextGrid pairs."""
        self.prima_path = Path(prima_path)
        self.secunda_path = Path(secunda_path)

        # Find TextGrids
        self.prima_tg = self._find_textgrid(self.prima_path)
        self.secunda_tg = self._find_textgrid(self.secunda_path)

        if not self.prima_tg or not self.secunda_tg:
            raise FileNotFoundError("Could not find TextGrids for both speakers")

        # Load editors
        self.prima_editor = ProsodyEditor(str(self.prima_tg))
        self.secunda_editor = ProsodyEditor(str(self.secunda_tg))

        # Extract parameters
        self.prima_targets = self.prima_editor.compile_to_f0_targets()
        self.secunda_targets = self.secunda_editor.compile_to_f0_targets()

        print(f"✓ Prima: {len(self.prima_targets)} targets from {self.prima_tg}")
        print(f"✓ Secunda: {len(self.secunda_targets)} targets from {self.secunda_tg}")

    def _find_textgrid(self, audio_path):
        """Find TextGrid for audio file."""
        audio_stem = audio_path.stem
        patterns = [
            audio_path.parent / f"{audio_stem}.TextGrid",
            audio_path.parent / f"{audio_stem}/input.TextGrid",
            Path('out/questionaire_2026-06-02/english') / f"{audio_stem}.TextGrid",
        ]
        for p in patterns:
            if p.exists():
                return p
        return None

    def morph(self, blend=0.5, generator='linear'):
        """Create morphed F0 contour.

        Args:
            blend: 0.0 = all prima, 1.0 = all secunda, 0.5 = 50/50
            generator: Movement generator (linear, sigmoid, ease_in_out)

        Returns:
            Morphed F0 array
        """
        # Blend F0 targets
        prima_f0 = [t.f0 for t in self.prima_targets]
        secunda_f0 = [t.f0 for t in self.secunda_targets]

        # Use prima's length as base
        num_frames = len(prima_f0)

        morphed_f0 = []
        for i in range(num_frames):
            # Map to secunda's frame index
            if len(secunda_f0) > 1:
                secunda_idx = int(i * (len(secunda_f0) - 1) / (num_frames - 1))
                secunda_idx = min(secunda_idx, len(secunda_f0) - 1)
            else:
                secunda_idx = 0

            # Blend at this frame
            prima_val = prima_f0[i]
            secunda_val = secunda_f0[secunda_idx]

            # Linear blend
            if generator == 'linear':
                blended = prima_val * (1 - blend) + secunda_val * blend

            # Sigmoid blend (emphasize transitions)
            elif generator == 'sigmoid':
                import math
                # Smooth transition using sigmoid
                sigmoid = 1 / (1 + math.exp(-(blend * 6 - 3)))
                blended = prima_val * (1 - sigmoid) + secunda_val * sigmoid

            else:
                blended = prima_val * (1 - blend) + secunda_val * blend

            morphed_f0.append(blended)

        return morphed_f0

    def synthesize(self, blend=0.5, output_path='output_morphed.wav'):
        """Synthesize morphed audio."""

        print(f"\nMorphing with blend={blend}...")

        # Get text from prima
        text = ''.join(syl.text for syl in self.prima_editor.syllables)

        # Step 1: Generate base audio
        print("\n[1/3] Generating base audio...")
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
            print("❌ espeak-ng not found")
            return None

        print(f"✓ Base audio: {base_wav}")

        # Step 2: Morph F0
        print("\n[2/3] Morphing F0 contour...")
        morphed_f0 = self.morph(blend)
        median_f0 = sorted(morphed_f0)[len(morphed_f0)//2]
        print(f"✓ Morphed F0: {min(morphed_f0):.0f}-{max(morphed_f0):.0f} Hz (median: {median_f0:.0f})")

        # Step 3: Apply pitch modification
        print(f"\n[3/3] Applying pitch shift...")
        try:
            subprocess.run([
                'sox',
                base_wav,
                output_path,
                'pitch', str(int(median_f0 - 110)),
                'rate', '16000',
            ], check=True, capture_output=True)
        except FileNotFoundError:
            print("❌ sox not found")
            return None

        print(f"✓ Morphed audio: {output_path}")

        # Cleanup
        Path(base_wav).unlink(missing_ok=True)

        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Morph prosody between two speakers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python prosody_morph.py --prima speaker_a.wav --secunda speaker_b.wav --blend 0.5
  python prosody_morph.py --prima speaker_a.wav --secunda speaker_b.wav --blend-curve sigmoid
        '''
    )

    parser.add_argument('--prima', required=True, help='First speaker audio')
    parser.add_argument('--secunda', required=True, help='Second speaker audio')
    parser.add_argument('--blend', type=float, default=0.5,
                       help='Blend ratio (0=all prima, 1=all secunda)')
    parser.add_argument('--blend-curve', default='linear',
                       choices=['linear', 'sigmoid', 'ease_in_out'],
                       help='Blending curve shape')
    parser.add_argument('--num-variations', type=int, default=1,
                       help='Number of blend variations (animate blend)')
    parser.add_argument('-o', '--output', help='Output audio file')

    args = parser.parse_args()

    try:
        print("=" * 70)
        print("Prosody Morpher: Blend two speakers")
        print("=" * 70)

        morpher = ProsodyMorpher(args.prima, args.secunda)

        if args.num_variations > 1:
            # Generate animation sequence
            print(f"\nGenerating {args.num_variations} blend variations...")
            for i in range(args.num_variations):
                blend = i / (args.num_variations - 1)
                output = args.output or f'morph_{i:02d}.wav'
                morpher.synthesize(blend=blend, output_path=output)
                print(f"  Variation {i+1}/{args.num_variations}: blend={blend:.2f}")
        else:
            # Single blend
            output = args.output or 'morphed.wav'
            result = morpher.synthesize(
                blend=args.blend,
                output_path=output
            )

            if result:
                size_mb = Path(result).stat().st_size / (1024 * 1024)
                print(f"\n{'=' * 70}")
                print(f"✅ Morphed audio: {result} ({size_mb:.1f} MB)")
                print(f"{'=' * 70}")
                print(f"\nPlay with: ffplay {result}")
                return 0

        return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
