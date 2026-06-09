"""F0 Compiler: Map symbolic prosody to quantitative pitch targets

Converts SpeechPrint prosody symbols to F0 contours for synthesis.

Symbols:
- / : weakly rising (small positive change)
- // : strongly rising (large positive change)
- \ : weakly falling (small negative change)
- \\ : strongly falling (large negative change)
- ‾ : high level (above baseline)
- _ : low level (below baseline)
- * : accent marker (prominence)
- ? : unvoiced
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class F0Target:
    """A single F0 target in a contour."""
    time: float  # seconds
    f0: float    # Hz
    is_accent: bool = False
    confidence: float = 1.0


class F0Compiler:
    """Compile prosody symbols to F0 targets."""

    def __init__(
        self,
        f0_floor: float = 75.0,
        f0_ceiling: float = 300.0,
        reference_f0: Optional[float] = None,
    ):
        """
        Args:
            f0_floor: Minimum F0 for speaker (Hz)
            f0_ceiling: Maximum F0 for speaker (Hz)
            reference_f0: Baseline F0 for neutral prosody (auto-detect if None)
        """
        self.f0_floor = f0_floor
        self.f0_ceiling = f0_ceiling
        self.reference_f0 = reference_f0 or (f0_floor + f0_ceiling) / 2

    def compile_syllable(
        self,
        symbol: str,
        onset_time: float,
        offset_time: float,
        previous_f0: Optional[float] = None,
    ) -> list[F0Target]:
        """
        Compile a single syllable's prosody symbol to F0 targets.

        Args:
            symbol: Prosody symbol(s) like '*‾//', '_\\', '?', etc.
            onset_time: Syllable start time (s)
            offset_time: Syllable end time (s)
            previous_f0: F0 at end of previous syllable (for continuity)

        Returns:
            List of F0Target points spanning the syllable.
        """
        if not symbol or '?' in symbol:
            # Unvoiced or missing data
            return [F0Target(onset_time, self.reference_f0, confidence=0.0)]

        # Parse symbol components
        is_accent = '*' in symbol
        height = 'high' if '‾' in symbol else 'low' if '_' in symbol else 'mid'
        direction = self._parse_direction(symbol)

        # Compute onset and offset F0 values
        onset_f0 = self._compute_f0_for_height(height, is_accent)
        offset_f0 = self._compute_f0_for_direction(direction, is_accent)

        # Ensure continuity with previous syllable
        if previous_f0 is not None:
            onset_f0 = self._smooth_transition(previous_f0, onset_f0)

        # Generate trajectory through syllable
        targets = self._generate_trajectory(
            onset_time, offset_time,
            onset_f0, offset_f0,
            direction, is_accent
        )

        return targets

    def _parse_direction(self, symbol: str) -> str:
        """Extract pitch direction from symbol."""
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

    def _compute_f0_for_height(self, height: str, is_accent: bool) -> float:
        """Compute onset F0 based on height."""
        mid = self.reference_f0
        range_hz = (self.f0_ceiling - self.f0_floor) / 2

        if height == 'high':
            f0 = mid + range_hz * 0.5
        elif height == 'low':
            f0 = mid - range_hz * 0.5
        else:
            f0 = mid

        if is_accent:
            f0 += range_hz * 0.15  # Boost accent

        return max(self.f0_floor, min(self.f0_ceiling, f0))

    def _compute_f0_for_direction(
        self, direction: str, is_accent: bool
    ) -> float:
        """Compute offset F0 based on direction."""
        mid = self.reference_f0
        range_hz = (self.f0_ceiling - self.f0_floor) / 2

        change_semitones = {
            'strongly_rising': 5,      # ~19% increase
            'weakly_rising': 2,        # ~6% increase
            'level': 0,
            'weakly_falling': -2,      # ~6% decrease
            'strongly_falling': -5,    # ~19% decrease
        }

        semitones = change_semitones.get(direction, 0)
        f0 = mid * (2 ** (semitones / 12))

        # Clamp to speaker range
        return max(self.f0_floor, min(self.f0_ceiling, f0))

    def _smooth_transition(self, previous_f0: float, target_f0: float) -> float:
        """Smooth transition from previous syllable (avoid jumps)."""
        # Max jump: 3 semitones to avoid voice breaks
        max_jump_semitones = 3
        max_ratio = 2 ** (max_jump_semitones / 12)

        ratio = target_f0 / previous_f0
        ratio = max(1 / max_ratio, min(max_ratio, ratio))

        return previous_f0 * ratio

    def _generate_trajectory(
        self,
        onset_time: float,
        offset_time: float,
        onset_f0: float,
        offset_f0: float,
        direction: str,
        is_accent: bool,
        num_points: int = 3,
    ) -> list[F0Target]:
        """Generate smooth F0 trajectory through syllable."""
        targets = []
        duration = offset_time - onset_time

        if direction in ('strongly_rising', 'weakly_rising'):
            # Rising: slow start, fast end
            times = [
                onset_time,
                onset_time + duration * 0.33,
                onset_time + duration * 0.67,
                offset_time,
            ]
            f0s = [
                onset_f0,
                onset_f0 + (offset_f0 - onset_f0) * 0.25,
                onset_f0 + (offset_f0 - onset_f0) * 0.75,
                offset_f0,
            ]

        elif direction in ('strongly_falling', 'weakly_falling'):
            # Falling: fast start, slow end
            times = [
                onset_time,
                onset_time + duration * 0.33,
                onset_time + duration * 0.67,
                offset_time,
            ]
            f0s = [
                onset_f0,
                onset_f0 + (offset_f0 - onset_f0) * 0.75,
                onset_f0 + (offset_f0 - onset_f0) * 0.25,
                offset_f0,
            ]

        else:
            # Level: constant F0
            times = [onset_time, offset_time]
            f0s = [onset_f0, offset_f0]

        for t, f0 in zip(times, f0s):
            targets.append(F0Target(t, f0, is_accent=is_accent))

        return targets

    def compile_utterance(
        self,
        syllables: list[dict],
        speaker_f0_floor: Optional[float] = None,
        speaker_f0_ceiling: Optional[float] = None,
    ) -> list[F0Target]:
        """
        Compile an entire utterance.

        Args:
            syllables: List of dicts with keys:
                - 'symbol': prosody symbol string
                - 'onset': start time (s)
                - 'offset': end time (s)
            speaker_f0_floor: Override floor for this speaker
            speaker_f0_ceiling: Override ceiling for this speaker

        Returns:
            List of F0Target points for entire utterance.
        """
        if speaker_f0_floor is not None:
            self.f0_floor = speaker_f0_floor
        if speaker_f0_ceiling is not None:
            self.f0_ceiling = speaker_f0_ceiling

        all_targets = []
        previous_f0 = None

        for syl in syllables:
            targets = self.compile_syllable(
                syl['symbol'],
                syl['onset'],
                syl['offset'],
                previous_f0=previous_f0,
            )
            all_targets.extend(targets)
            if targets:
                previous_f0 = targets[-1].f0

        return all_targets

    def targets_to_f0_array(
        self,
        targets: list[F0Target],
        sample_rate: int = 50,
    ) -> tuple[list[float], list[float]]:
        """
        Convert F0Target list to sampled F0 array.

        Args:
            targets: List of F0Target points
            sample_rate: Samples per second (default 50 Hz for typical pitch shift)

        Returns:
            (times, f0_values) arrays
        """
        if not targets:
            return [], []

        times = []
        f0_values = []

        for i in range(len(targets) - 1):
            t0, t1 = targets[i].time, targets[i + 1].time
            f0_0, f0_1 = targets[i].f0, targets[i + 1].f0

            num_samples = max(1, int((t1 - t0) * sample_rate))

            for j in range(num_samples):
                alpha = j / num_samples
                t = t0 + (t1 - t0) * alpha
                f0 = f0_0 + (f0_1 - f0_0) * alpha

                times.append(t)
                f0_values.append(f0)

        # Add final point
        if targets:
            times.append(targets[-1].time)
            f0_values.append(targets[-1].f0)

        return times, f0_values
