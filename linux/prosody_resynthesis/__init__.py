"""ProsodyPrompt Resynthesis Module

Closes the loop: TextGrid (edited prosody) → F0 targets → Coqui TTS → Resynthesized audio

Architecture:
- f0_compiler: Maps symbolic prosody (/, //, \, etc.) → quantitative F0 targets
- coqui_interface: Voice cloning + F0-conditioned synthesis
- textgrid_io: Read/write TextGrid with prosody tier
- prosody_editor: Foundation for interactive editing (CLI + web UI later)
"""

from .f0_compiler import F0Compiler
from .coqui_interface import CoquiSynthesizer
from .textgrid_io import TextGridReader, TextGridWriter
from .prosody_editor import ProsodyEditor

__all__ = [
    "F0Compiler",
    "CoquiSynthesizer",
    "TextGridReader",
    "TextGridWriter",
    "ProsodyEditor",
]

__version__ = "0.1.0"
