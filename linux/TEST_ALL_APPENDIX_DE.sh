#!/bin/bash
# TEST_ALL_APPENDIX_DE.sh: Final validation of Appendix D & E implementations

set -e

echo "========================================================================"
echo "FINAL TEST: Appendix D & E Complete Toolkit"
echo "========================================================================"

PASS=0
FAIL=0

test_command() {
    local name=$1
    local cmd=$2

    echo ""
    echo "[$name]"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "✓ PASS"
        ((PASS++))
    else
        echo "✗ FAIL"
        ((FAIL++))
    fi
}

# =========================================================================
# APPENDIX D: Prosody Annotation CLI
# =========================================================================
echo ""
echo "────────────────────────────────────────────────────────────────────"
echo "APPENDIX D: ProsodyPrompt CLI"
echo "────────────────────────────────────────────────────────────────────"

test_command "D1: CLI help" \
    "python3 speechprint_cli.py --help | grep -q 'usage'"

test_command "D2: run command" \
    "python3 speechprint_cli.py run \
      --wav out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav \
      --language en --tracker pyin"

test_command "D3: export to CSV" \
    "python3 speechprint_cli.py export \
      --textgrid out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid \
      --format csv && test -f audio_2026-05-30_19-01-35.csv"

test_command "D4: batch processing" \
    "python3 speechprint_cli.py batch \
      --input-dir out/questionaire_2026-06-02/english/ --language en | grep -q Found"

test_command "D5: evaluate-gtobi" \
    "python3 speechprint_cli.py evaluate-gtobi \
      --sentences-dir out/questionaire_2026-06-02/german_gtobi/ | grep -q Found"

# =========================================================================
# APPENDIX E: Prosody → Articulatory Synthesis
# =========================================================================
echo ""
echo "────────────────────────────────────────────────────────────────────"
echo "APPENDIX E: Prosody Synthesis Tools"
echo "────────────────────────────────────────────────────────────────────"

test_command "E1: prosody2tract --list-generators" \
    "python3 prosody2tract.py --list-generators | grep -q linear"

test_command "E2: prosody2tract --list-params" \
    "python3 prosody2tract.py --list-params | grep -q f0"

test_command "E3: prosody2tract conversion" \
    "python3 prosody2tract.py \
      out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid \
      --output test_e3.txt && test -f test_e3.txt"

test_command "E4: audio2tract --list-params" \
    "python3 audio2tract.py --list-params | grep -q JAW"

test_command "E5: audio2tract pressure smooth" \
    "python3 audio2tract.py \
      out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav \
      -m pressure smooth 10 -o out/test_e5.wav && test -f out/test_e5.wav"

test_command "E6: audio2tract multiple manipulations" \
    "python3 audio2tract.py \
      out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav \
      -m TCX multiply 1.5 -m TTY add 0.5 -m f0 smooth 10 \
      -o out/test_e6.wav && test -f out/test_e6.wav"

test_command "E7: prosody_morph basic" \
    "python3 prosody_morph.py \
      --prima out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav \
      --secunda out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.wav \
      --blend 0.5 -o out/test_e7.wav && test -f out/test_e7.wav"

# =========================================================================
# SYNTHESIS: Audio Generation
# =========================================================================
echo ""
echo "────────────────────────────────────────────────────────────────────"
echo "SYNTHESIS: Audio Generation"
echo "────────────────────────────────────────────────────────────────────"

test_command "SYN1: synthesize_audio.py" \
    "python3 synthesize_audio.py 2>&1 | grep -q 'SUCCESS'"

test_command "SYN2: Audio files exist" \
    "test -f out/synthesized_prosody.wav"

test_command "SYN3: Audio files valid" \
    "sox out/synthesized_prosody.wav -n stat > /dev/null 2>&1"

# =========================================================================
# SUMMARY
# =========================================================================
echo ""
echo "========================================================================"
echo "TEST SUMMARY"
echo "========================================================================"
echo "PASSED: $PASS"
echo "FAILED: $FAIL"

TOTAL=$((PASS + FAIL))
echo "TOTAL:  $TOTAL"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "✅ ALL TESTS PASSED"
    echo ""
    echo "Ready to push to GitHub:"
    echo "  git add -A"
    echo "  git commit -m 'feat: Complete Appendix D & E implementations'"
    echo "  git push"
    exit 0
else
    echo ""
    echo "⚠️  $FAIL test(s) failed"
    exit 1
fi
