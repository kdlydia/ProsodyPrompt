"""Utility functions for prosody resynthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


def semitones_to_ratio(semitones: float) -> float:
    """Convert semitone shift to frequency ratio."""
    return 2 ** (semitones / 12)


def ratio_to_semitones(ratio: float) -> float:
    """Convert frequency ratio to semitones."""
    return 12 * np.log2(ratio)


def hz_to_semitones(f0_hz: float, reference_hz: float = 440.0) -> float:
    """Convert Hz to semitones relative to A4 (440 Hz)."""
    return 12 * np.log2(f0_hz / reference_hz)


def semitones_to_hz(semitones: float, reference_hz: float = 440.0) -> float:
    """Convert semitones to Hz."""
    return reference_hz * 2 ** (semitones / 12)


def smooth_f0_array(
    f0: np.ndarray,
    window_size: int = 3,
    method: str = 'median',
) -> np.ndarray:
    """
    Smooth F0 array to remove glitches.

    Args:
        f0: F0 array (Hz)
        window_size: Smoothing window
        method: 'median' or 'mean'

    Returns:
        Smoothed F0 array
    """
    if method == 'median':
        from scipy.ndimage import median_filter
        return median_filter(f0, size=window_size)
    elif method == 'mean':
        from scipy.ndimage import uniform_filter
        return uniform_filter(f0, size=window_size)
    else:
        raise ValueError(f"Unknown smoothing method: {method}")


def detect_speaker_pitch_range(
    audio: np.ndarray,
    sr: int = 22050,
    method: str = 'pyin',
) -> tuple[float, float]:
    """
    Auto-detect speaker's pitch range from audio.

    Args:
        audio: Audio waveform
        sr: Sample rate
        method: 'pyin' or 'autocorrelation'

    Returns:
        (f0_floor, f0_ceiling) in Hz
    """
    try:
        import librosa
    except ImportError:
        raise ImportError("librosa required. Run: pip install librosa")

    if method == 'pyin':
        f0 = librosa.yin(audio, fmin=50, fmax=400, sr=sr)
    else:
        # Autocorrelation fallback
        f0 = librosa.autocorrelate(audio, max_size=sr // 50)

    # Get quartiles (exclude unvoiced frames marked as 0)
    voiced_f0 = f0[f0 > 0]

    if len(voiced_f0) < 10:
        # Not enough data; return conservative range
        return 75.0, 300.0

    q1 = np.percentile(voiced_f0, 25)
    q3 = np.percentile(voiced_f0, 75)

    # Add safety margin
    f0_floor = max(50.0, q1 * 0.9)
    f0_ceiling = min(500.0, q3 * 1.1)

    return f0_floor, f0_ceiling


def validate_prosody_symbol(symbol: str) -> bool:
    """Check if symbol is valid."""
    valid_chars = set('/*\\_‾_?')
    return all(c in valid_chars for c in symbol) and len(symbol) > 0


def parse_symbol(symbol: str) -> dict:
    """Parse prosody symbol into components."""
    return {
        'has_accent': '*' in symbol,
        'height': 'high' if '‾' in symbol else 'low' if '_' in symbol else 'mid',
        'direction': _parse_direction(symbol),
        'voiced': '?' not in symbol,
    }


def _parse_direction(symbol: str) -> str:
    """Extract direction from symbol."""
    if '//' in symbol:
        return 'strongly_rising'
    elif '/' in symbol:
        return 'weakly_rising'
    elif '\\\\' in symbol:
        return 'strongly_falling'
    elif '\\' in symbol:
        return 'weakly_falling'
    else:
        return 'level'


def load_or_extract_f0(
    audio_path: str | Path,
    sr: int = 22050,
    method: str = 'pyin',
) -> tuple[np.ndarray, np.ndarray]:
    """
    Load audio and extract F0.

    Args:
        audio_path: Path to WAV file
        sr: Target sample rate
        method: 'pyin', 'crepe', or 'autocorrelation'

    Returns:
        (f0_contour, times) both as numpy arrays
    """
    try:
        import librosa
        import soundfile as sf
    except ImportError:
        raise ImportError("librosa and soundfile required")

    # Load audio
    audio, sr_orig = sf.read(audio_path)
    if sr_orig != sr:
        audio = librosa.resample(audio, orig_sr=sr_orig, target_sr=sr)

    # Extract F0
    if method == 'pyin':
        f0 = librosa.yin(audio, fmin=50, fmax=400, sr=sr)
    elif method == 'autocorrelation':
        f0 = librosa.autocorrelate(audio, max_size=sr // 50)
    elif method == 'crepe':
        try:
            import torchcrepe
            f0, confidence = torchcrepe.predict(
                torch.from_numpy(audio).unsqueeze(0),
                sr=sr,
                hop_length=160,  # 10ms at 16kHz
            )
            f0 = f0.squeeze(0).numpy()
        except ImportError:
            raise ImportError("torchcrepe required for CREPE. Run: pip install torchcrepe")
    else:
        raise ValueError(f"Unknown F0 method: {method}")

    # Get times
    hop_length = sr // 100  # 10ms frames
    times = np.arange(len(f0)) * hop_length / sr

    return f0, times


def interpolate_f0(
    f0: np.ndarray,
    times: np.ndarray,
    target_times: np.ndarray,
    kind: str = 'linear',
) -> np.ndarray:
    """
    Interpolate F0 contour to new time points.

    Args:
        f0: F0 values
        times: Time points for F0
        target_times: New time points to interpolate to
        kind: 'linear', 'cubic', etc.

    Returns:
        Interpolated F0 values
    """
    from scipy.interpolate import interp1d

    # Filter out invalid F0 (0 or NaN)
    valid = (f0 > 0) & ~np.isnan(f0)
    valid_times = times[valid]
    valid_f0 = f0[valid]

    if len(valid_times) < 2:
        return np.full_like(target_times, 120.0)  # Fallback

    interp_fn = interp1d(
        valid_times, valid_f0,
        kind=kind, fill_value='extrapolate',
    )

    return interp_fn(target_times)
