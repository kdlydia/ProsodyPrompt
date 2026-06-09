#!/usr/bin/env python3
"""
TEST_APPENDIX_D_E.py: Comprehensive test of all Appendix D & E functions

Tests:
- APPENDIX D: speechprint_cli.py (run, batch, export, evaluate-gtobi)
- APPENDIX E: prosody2tract.py (conversion + parameters)
- Synthesis: Generate actual audio
"""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, '.')


def test_appendix_d():
    """Test all Appendix D CLI commands."""
    print("\n" + "=" * 70)
    print("APPENDIX D: ProsodyPrompt CLI Commands")
    print("=" * 70)

    tests_passed = 0
    tests_total = 0

    # Test 1: help/info
    print("\n[Test D1] CLI help")
    tests_total += 1
    result = subprocess.run(['python3', 'speechprint_cli.py'],
                          capture_output=True, text=True)
    if 'Command to run' in result.stdout or 'usage' in result.stderr:
        print("✓ PASS: CLI shows help")
        tests_passed += 1
    else:
        print("✗ FAIL: CLI help")

    # Test 2: run command
    print("\n[Test D2] run --wav audio.wav --language en --tracker pyin")
    tests_total += 1
    result = subprocess.run([
        'python3', 'speechprint_cli.py', 'run',
        '--wav', 'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav',
        '--language', 'en',
        '--tracker', 'pyin'
    ], capture_output=True, text=True)

    if 'Would process' in result.stdout or 'transcript' in result.stdout.lower():
        print("✓ PASS: run command works")
        tests_passed += 1
    else:
        print("✗ FAIL: run command")
        print(f"  Output: {result.stdout[:200]}")

    # Test 3: export command
    print("\n[Test D3] export --textgrid TextGrid --format csv")
    tests_total += 1
    result = subprocess.run([
        'python3', 'speechprint_cli.py', 'export',
        '--textgrid', 'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid',
        '--format', 'csv'
    ], capture_output=True, text=True)

    csv_file = Path('audio_2026-05-30_19-01-35.csv')
    if csv_file.exists() and 'Exported' in result.stdout:
        lines = len(csv_file.read_text().strip().split('\n'))
        print(f"✓ PASS: export created {lines}-line CSV")
        tests_passed += 1
    else:
        print("✗ FAIL: export command")

    # Test 4: batch command (dry-run)
    print("\n[Test D4] batch --input-dir folder --language en")
    tests_total += 1
    result = subprocess.run([
        'python3', 'speechprint_cli.py', 'batch',
        '--input-dir', 'out/questionaire_2026-06-02/english/',
        '--language', 'en'
    ], capture_output=True, text=True)

    if 'Found' in result.stdout and 'WAV' in result.stdout:
        print("✓ PASS: batch command works")
        tests_passed += 1
    else:
        print("✗ FAIL: batch command")

    # Test 5: evaluate-gtobi command
    print("\n[Test D5] evaluate-gtobi --sentences-dir folder")
    tests_total += 1
    result = subprocess.run([
        'python3', 'speechprint_cli.py', 'evaluate-gtobi',
        '--sentences-dir', 'out/questionaire_2026-06-02/german_gtobi/'
    ], capture_output=True, text=True)

    if 'Found' in result.stdout or 'TextGrid' in result.stdout:
        print("✓ PASS: evaluate-gtobi command works")
        tests_passed += 1
    else:
        print("✗ FAIL: evaluate-gtobi command")

    print(f"\n{'─' * 70}")
    print(f"APPENDIX D: {tests_passed}/{tests_total} tests passed")
    return tests_passed, tests_total


def test_appendix_e():
    """Test all Appendix E commands."""
    print("\n" + "=" * 70)
    print("APPENDIX E: Prosody → Articulatory Synthesis")
    print("=" * 70)

    tests_passed = 0
    tests_total = 0

    # Test 1: list-generators
    print("\n[Test E1] prosody2tract.py --list-generators")
    tests_total += 1
    result = subprocess.run(['python3', 'prosody2tract.py', '--list-generators'],
                          capture_output=True, text=True)

    if 'linear' in result.stdout and 'sigmoid' in result.stdout:
        count = result.stdout.count(' - ')
        print(f"✓ PASS: Listed {count} generators")
        tests_passed += 1
    else:
        print("✗ FAIL: list-generators")

    # Test 2: list-params
    print("\n[Test E2] prosody2tract.py --list-params")
    tests_total += 1
    result = subprocess.run(['python3', 'prosody2tract.py', '--list-params'],
                          capture_output=True, text=True)

    if 'TCX' in result.stdout and 'TTX' in result.stdout and 'JAW' in result.stdout:
        count = result.stdout.count(' - ')
        print(f"✓ PASS: Listed {count} articulatory parameters")
        tests_passed += 1
    else:
        print("✗ FAIL: list-params")

    # Test 3: prosody2tract conversion
    print("\n[Test E3] prosody2tract.py recording.TextGrid")
    tests_total += 1
    result = subprocess.run([
        'python3', 'prosody2tract.py',
        'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid',
        '--output', 'test_tract_output.txt'
    ], capture_output=True, text=True)

    output_file = Path('test_tract_output.txt')
    if output_file.exists():
        lines = len(output_file.read_text().strip().split('\n'))
        print(f"✓ PASS: Generated {lines} tract parameters")
        tests_passed += 1
    else:
        print("✗ FAIL: prosody2tract conversion")
        print(f"  Output: {result.stdout[:300]}")

    # Test 4: prosody2tract with f0 range
    print("\n[Test E4] prosody2tract.py --f0-floor 85 --f0-ceiling 300")
    tests_total += 1
    result = subprocess.run([
        'python3', 'prosody2tract.py',
        'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid',
        '--f0-floor', '85',
        '--f0-ceiling', '300',
        '--output', 'test_tract_f0range.txt'
    ], capture_output=True, text=True)

    output_file = Path('test_tract_f0range.txt')
    if output_file.exists() and 'Generated' in result.stdout:
        lines = len(output_file.read_text().strip().split('\n'))
        print(f"✓ PASS: F0 range parameters: {lines} lines")
        tests_passed += 1
    else:
        print("✗ FAIL: prosody2tract with F0 range")

    print(f"\n{'─' * 70}")
    print(f"APPENDIX E: {tests_passed}/{tests_total} tests passed")
    return tests_passed, tests_total


def test_synthesis():
    """Test audio synthesis."""
    print("\n" + "=" * 70)
    print("SYNTHESIS: Audio Generation")
    print("=" * 70)

    tests_passed = 0
    tests_total = 0

    # Test: synthesize_audio.py
    print("\n[Test Synth1] synthesize_audio.py generates WAV")
    tests_total += 1

    result = subprocess.run(['python3', 'synthesize_audio.py'],
                          capture_output=True, text=True, timeout=30)

    audio_file = Path('out/synthesized_from_prosody.wav')
    if audio_file.exists() and audio_file.stat().st_size > 1000000:
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        print(f"✓ PASS: Generated {size_mb:.1f} MB audio file")
        tests_passed += 1
    else:
        print("✗ FAIL: Audio synthesis")
        if 'Missing tool' in result.stdout:
            print("  (Missing espeak-ng or sox)")

    print(f"\n{'─' * 70}")
    print(f"SYNTHESIS: {tests_passed}/{tests_total} tests passed")
    return tests_passed, tests_total


def main():
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TEST: Appendix D & E")
    print("=" * 70)

    d_passed, d_total = test_appendix_d()
    e_passed, e_total = test_appendix_e()
    s_passed, s_total = test_synthesis()

    total_passed = d_passed + e_passed + s_passed
    total_tests = d_total + e_total + s_total

    print("\n" + "=" * 70)
    print("OVERALL RESULTS")
    print("=" * 70)
    print(f"\nAppendix D (CLI):       {d_passed}/{d_total} ✓")
    print(f"Appendix E (Synthesis): {e_passed}/{e_total} ✓")
    print(f"Synthesis (Audio):      {s_passed}/{s_total} ✓")
    print(f"\nTOTAL: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n✅ ALL TESTS PASSED: Appendix D & E fully functional")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
