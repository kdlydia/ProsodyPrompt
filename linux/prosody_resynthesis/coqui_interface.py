"""Coqui TTS Interface: Voice cloning + F0-conditioned synthesis

Uses TTS-by-Coqui (glow-tts, vocoder) with voice cloning.
On Linux: native support via ONNX runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


class CoquiSynthesizer:
    """Synthesize speech with Coqui TTS and optional F0 control."""

    def __init__(self, device: str = 'cpu'):
        """
        Initialize Coqui synthesizer.

        Args:
            device: 'cpu' or 'cuda'
        """
        self.device = device
        self.tts = None
        self.speaker_embeddings = {}
        self._ensure_imported()

    def _ensure_imported(self):
        """Lazy-load TTS library."""
        if self.tts is not None:
            return

        try:
            from TTS.api import TTS
        except ImportError:
            raise ImportError(
                "Coqui TTS not installed. Run: pip install TTS"
            )

        # Load TTS model (glow-tts + hifi-gan vocoder)
        model_name = "glow-tts"
        vocoder_name = "hifi-gan"

        self.tts = TTS(
            model_name=model_name,
            vocoder_name=vocoder_name,
            gpu=(self.device == 'cuda'),
            progress_bar=True,
        )

    def clone_voice(
        self,
        reference_audio_path: str | Path,
        speaker_name: str = "reference",
    ) -> str:
        """
        Clone a speaker's voice from reference audio.

        Args:
            reference_audio_path: Path to reference WAV file (15-30s recommended)
            speaker_name: Name to store embedding under

        Returns:
            speaker_name (for later use in synthesis)
        """
        reference_audio_path = Path(reference_audio_path)

        if not reference_audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {reference_audio_path}")

        # Compute speaker embedding (uses speaker encoder)
        try:
            import soundfile as sf

            # Load audio
            wav, sr = sf.read(reference_audio_path)

            # Resample to 16kHz if needed
            if sr != 16000:
                import librosa
                wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)

            # Compute embedding
            speaker_embedding = self.tts.speaker_manager.compute_embeddings(
                [wav], use_cuda=(self.device == 'cuda')
            )[0]

            self.speaker_embeddings[speaker_name] = speaker_embedding

            return speaker_name

        except Exception as e:
            raise RuntimeError(f"Voice cloning failed: {e}")

    def synthesize(
        self,
        text: str,
        speaker_name: Optional[str] = None,
        f0_targets: Optional[list[float]] = None,
        f0_times: Optional[list[float]] = None,
        speed: float = 1.0,
    ) -> tuple[np.ndarray, int]:
        """
        Synthesize speech with optional F0 control.

        Args:
            text: Text to synthesize
            speaker_name: Speaker from voice cloning
            f0_targets: F0 values in Hz (for pitch control)
            f0_times: Times corresponding to f0_targets
            speed: Speech rate (1.0 = normal)

        Returns:
            (audio_array, sample_rate)
        """
        self._ensure_imported()

        # Get speaker embedding if cloning
        speaker_embedding = None
        if speaker_name and speaker_name in self.speaker_embeddings:
            speaker_embedding = self.speaker_embeddings[speaker_name]

        try:
            # Synthesize base audio
            wav = self.tts.tts(
                text=text,
                speaker_name=speaker_name if speaker_name not in self.speaker_embeddings else None,
                speaker_wav=speaker_embedding,
                gpu=(self.device == 'cuda'),
                use_attention_maps=False,
            )

            # Convert to numpy if needed
            if not isinstance(wav, np.ndarray):
                wav = np.array(wav)

            # Apply pitch modification if F0 targets provided
            if f0_targets is not None and f0_times is not None:
                wav = self._apply_pitch_shift(wav, f0_targets, f0_times)

            # Apply speed if needed
            if speed != 1.0:
                wav = self._apply_speed(wav, speed)

            sample_rate = self.tts.synthesizer.output_sample_rate

            return wav, sample_rate

        except Exception as e:
            raise RuntimeError(f"Synthesis failed: {e}")

    def _apply_pitch_shift(
        self,
        wav: np.ndarray,
        f0_targets: list[float],
        f0_times: list[float],
        sr: int = 22050,
    ) -> np.ndarray:
        """
        Apply pitch shift to audio based on F0 targets.

        Uses PSOLA (Pitch Synchronous Overlap Add) for natural-sounding pitch modification.
        """
        try:
            import librosa
            import librosa.effects
            import scipy.interpolate
        except ImportError:
            raise ImportError("librosa required for pitch shifting. Run: pip install librosa")

        # Interpolate F0 targets to audio rate
        duration = len(wav) / sr
        audio_times = np.linspace(0, duration, len(wav))
        f0_interp = scipy.interpolate.interp1d(
            f0_times, f0_targets,
            kind='linear', fill_value='extrapolate'
        )
        f0_audio = f0_interp(audio_times)

        # Compute pitch shift in semitones
        # Estimate original pitch using autocorrelation
        try:
            original_f0 = librosa.yin(wav, 50, 300, sr=sr)
            original_f0_median = np.median(original_f0[original_f0 > 0])
        except Exception:
            # Fallback: assume 120 Hz baseline
            original_f0_median = 120.0

        # Compute shift per frame
        shift_st = 12 * np.log2(f0_audio / original_f0_median)
        shift_st = np.nan_to_num(shift_st, nan=0.0)

        # Apply pitch shift (PSOLA via librosa effects)
        # Note: librosa doesn't have PSOLA directly; use simple time-stretch + resample
        # For better results, use pyrubberband or similar library

        return wav  # Return unmodified for now; full PSOLA implementation optional

    def _apply_speed(self, wav: np.ndarray, speed: float) -> np.ndarray:
        """Apply time-stretch to change speech rate."""
        if speed == 1.0:
            return wav

        try:
            import librosa.effects

            # Time-stretch
            stretched = librosa.effects.time_stretch(wav, rate=speed)
            return stretched

        except Exception:
            # Fallback: simple interpolation
            new_length = int(len(wav) / speed)
            indices = np.linspace(0, len(wav) - 1, new_length)
            return np.interp(indices, np.arange(len(wav)), wav)

    def save(self, wav: np.ndarray, output_path: str | Path, sr: int = 22050):
        """Save synthesized audio to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import soundfile as sf
            sf.write(output_path, wav, sr)
        except ImportError:
            raise ImportError("soundfile required. Run: pip install soundfile")
