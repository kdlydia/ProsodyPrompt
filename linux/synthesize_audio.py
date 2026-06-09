#!/usr/bin/env python3
"""
synthesize_audio.py: Generate audio from prosody parameters

Uses espeak-ng (text-to-speech) + sox (audio processing) to create
audio with prosodic modifications based on F0 targets.
"""

import sys
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor


def synthesize(textgrid_path, output_path='output.wav'):
    """Synthesize audio from TextGrid prosody."""

    print(f"Loading TextGrid: {textgrid_path}")
    editor = ProsodyEditor(textgrid_path)

    # Get text from syllables
    text = ''.join(syl.text for syl in editor.syllables)
    print(f"Text: {text[:100]}...")

    # Step 1: Generate base audio with espeak-ng
    print("\n[1/3] Generating base audio with espeak-ng...")
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        base_wav = tmp.name

    subprocess.run([
        'espeak-ng',
        '-w', base_wav,
        '-s', '150',  # Speed
        '-p', '50',   # Pitch
        text
    ], check=True, capture_output=True)

    print(f"✓ Generated base audio: {base_wav}")

    # Step 2: Get F0 targets for pitch modification
    print("\n[2/3] Extracting F0 targets...")
    targets = editor.compile_to_f0_targets()
    f0_vals = [t.f0 for t in targets]
    median_f0 = sorted(f0_vals)[len(f0_vals)//2]
    print(f"✓ F0 range: {min(f0_vals):.0f}-{max(f0_vals):.0f} Hz (median: {median_f0:.0f})")

    # Step 3: Apply pitch modification with sox
    print(f"\n[3/3] Applying pitch modifications with sox...")
    subprocess.run([
        'sox',
        base_wav,
        output_path,
        'pitch', str(int(median_f0 - 110)),  # Shift to match target range
        'rate', '16000',  # Normalize to 16kHz
    ], check=True, capture_output=True)

    print(f"✓ Synthesized audio saved: {output_path}")

    # Get file info
    result = subprocess.run(['sox', output_path, '-n', 'stat'],
                          capture_output=True, text=True)

    print(f"\nAudio info:")
    print(f"  File: {output_path}")
    print(f"  Size: {Path(output_path).stat().st_size / 1024:.1f} KB")

    # Clean up temp file
    Path(base_wav).unlink(missing_ok=True)

    return output_path


def main():
    # Use the generated TextGrid
    tg_path = 'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid'
    output_path = 'out/synthesized_prosody.wav'

    print("=" * 70)
    print("ProsodyPrompt Audio Synthesis")
    print("=" * 70)

    try:
        result = synthesize(tg_path, output_path)
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS: Audio synthesized")
        print("=" * 70)
        print(f"\nYou can now play: {output_path}")
        print("  Command: ffplay synthesized_prosody.wav")
        print("  or: sox synthesized_prosody.wav -d")

        return 0

    except FileNotFoundError as e:
        print(f"❌ Missing tool: {e}")
        print("\nInstall with:")
        print("  Arch: sudo pacman -S espeak-ng sox")
        print("  Ubuntu: sudo apt install espeak-ng sox")
        print("  Fedora: sudo dnf install espeak-ng sox")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
