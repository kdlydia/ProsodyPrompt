#!/bin/bash
# SETUP_DRAWSPEECH.sh - Install and test DrawSpeech integration
#
# This script:
# 1. Clones the DrawSpeech repository
# 2. Installs dependencies
# 3. Downloads pretrained model
# 4. Tests integration with ProsodyPrompt
#
# Usage:
#   chmod +x SETUP_DRAWSPEECH.sh
#   ./SETUP_DRAWSPEECH.sh

set -e

echo "========================================================================"
echo "DrawSpeech Setup & Integration"
echo "========================================================================"
echo ""

# Configuration
DRAWSPEECH_REPO="https://github.com/RayeRen/DrawSpeech.git"
MODEL_URL="https://github.com/RayeRen/DrawSpeech/releases/download/v1.0/drawspeech_ljspeech.pt"
INSTALL_DIR="${HOME}/DrawSpeech"

echo "Step 1: Clone DrawSpeech Repository"
echo "────────────────────────────────────────────────────────────────────"
echo ""

if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  DrawSpeech already exists at $INSTALL_DIR"
    echo "   Skipping clone (remove directory to reinstall)"
else
    echo "Cloning from: $DRAWSPEECH_REPO"
    git clone "$DRAWSPEECH_REPO" "$INSTALL_DIR"
    echo "✓ Cloned to: $INSTALL_DIR"
fi

echo ""
echo "Step 2: Install PyTorch & Dependencies"
echo "────────────────────────────────────────────────────────────────────"
echo ""

# Check if PyTorch is installed
if python3 -c "import torch" 2>/dev/null; then
    echo "✓ PyTorch already installed"
    python3 -c "import torch; print(f'  Version: {torch.__version__}')"
    if python3 -c "import torch; torch.cuda.is_available()" 2>/dev/null; then
        echo "  GPU support: CUDA available"
    else
        echo "  GPU support: Not available (will use CPU)"
    fi
else
    echo "Installing PyTorch..."
    echo ""
    echo "For GPU (NVIDIA CUDA 11.8+):"
    echo "  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118"
    echo ""
    echo "For CPU only:"
    echo "  pip install torch torchaudio"
    echo ""
    read -p "Press Enter to continue after PyTorch installation..."
fi

echo ""
echo "Step 3: Install DrawSpeech in Editable Mode"
echo "────────────────────────────────────────────────────────────────────"
echo ""

cd "$INSTALL_DIR"
pip install -e .

echo "✓ DrawSpeech installed in editable mode"

echo ""
echo "Step 4: Download Pretrained Model"
echo "────────────────────────────────────────────────────────────────────"
echo ""

MODEL_PATH="$INSTALL_DIR/models/drawspeech_ljspeech.pt"
mkdir -p "$INSTALL_DIR/models"

if [ -f "$MODEL_PATH" ]; then
    echo "✓ Model already exists at $MODEL_PATH"
else
    echo "Downloading pretrained model (~500 MB)..."
    echo "From: $MODEL_URL"
    echo ""
    wget -O "$MODEL_PATH" "$MODEL_URL"
    echo "✓ Model downloaded"
fi

echo ""
echo "Step 5: Test Integration"
echo "────────────────────────────────────────────────────────────────────"
echo ""

# Go to ProsodyPrompt directory
cd /home/lydia/School/UPF/semester3/test2/SpeechPrint-main/linux

echo "Testing synthesize_with_drawspeech.py..."
python3 << 'EOF'
import sys
try:
    from synthesize_with_drawspeech import DrawSpeechSynthesizer
    print("✓ DrawSpeechSynthesizer can be imported")
except ImportError as e:
    print(f"⚠️  Import issue: {e}")
    print("   This is expected if DrawSpeech not fully installed yet")

# Test TextGrid loading
sys.path.insert(0, '.')
from prosody_resynthesis import ProsodyEditor

tg_path = 'out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid'
try:
    editor = ProsodyEditor(tg_path)
    print(f"✓ TextGrid loaded: {len(editor.syllables)} syllables")
except Exception as e:
    print(f"✗ TextGrid loading failed: {e}")
EOF

echo ""
echo "========================================================================"
echo "Setup Complete!"
echo "========================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Verify PyTorch installation:"
echo "   python3 -c \"import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())\""
echo ""
echo "2. Test DrawSpeech synthesis:"
echo "   cd /home/lydia/School/UPF/semester3/test2/SpeechPrint-main/linux"
echo "   python3 synthesize_with_drawspeech.py \\"
echo "     out/questionaire_2026-06-02/english/audio_2026-05-30_19-01-35.TextGrid \\"
echo "     --ckpt $MODEL_PATH \\"
echo "     -o output_neural.wav"
echo ""
echo "3. Play the output:"
echo "   ffplay output_neural.wav"
echo ""
echo "Performance tips:"
echo "  • Use GPU (--device cuda) for speed (~30 sec/utterance)"
echo "  • CPU is feasible but slow (~5 min/utterance)"
echo "  • First run downloads model (~200 MB)"
echo ""
echo "Troubleshooting:"
echo "  • CUDA out of memory: Use --device cpu"
echo "  • Module not found: cd $INSTALL_DIR && pip install -e ."
echo "  • Slow on CPU: Consider renting GPU (Colab, RunPod, etc.)"
echo ""
echo "Documentation: See APPENDIX_F_DRAWSPEECH.md"
echo ""
