"""Prosody Editor: Interactive editing of prosody tiers

Foundation for CLI tool and web-based Speech DAW.
Handles: parsing, editing, validation, synthesis integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .f0_compiler import F0Compiler, F0Target
from .textgrid_io import Interval, IntervalTier, TextGridReader, TextGridWriter


@dataclass
class EditableProsodicSyllable:
    """A syllable with editable prosody symbol."""
    index: int
    onset: float
    offset: float
    text: str
    original_symbol: str
    current_symbol: str
    is_modified: bool = False

    def modify(self, new_symbol: str):
        """Change prosody symbol."""
        self.current_symbol = new_symbol
        self.is_modified = (new_symbol != self.original_symbol)

    def reset(self):
        """Reset to original symbol."""
        self.current_symbol = self.original_symbol
        self.is_modified = False

    @property
    def symbol_components(self) -> dict:
        """Parse current symbol into components."""
        return {
            'has_accent': '*' in self.current_symbol,
            'height': 'high' if '‾' in self.current_symbol else 'low' if '_' in self.current_symbol else 'mid',
            'direction': self._parse_direction(self.current_symbol),
            'voiced': '?' not in self.current_symbol,
        }

    @staticmethod
    def _parse_direction(symbol: str) -> str:
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


class ProsodyEditor:
    """
    Edit prosody symbols and synthesize results.

    Workflow:
    1. Load TextGrid with prosody tier
    2. Parse into editable syllables
    3. User modifies symbols
    4. Compile to F0 targets
    5. Synthesize with Coqui TTS
    6. Export modified TextGrid
    """

    def __init__(
        self,
        textgrid_path: str,
        reference_audio_path: Optional[str] = None,
        speaker_name: str = "default",
    ):
        """
        Initialize editor.

        Args:
            textgrid_path: Path to existing TextGrid with prosody tier
            reference_audio_path: Optional audio for voice cloning
            speaker_name: Name for cloned speaker
        """
        self.textgrid_path = textgrid_path
        self.reference_audio_path = reference_audio_path
        self.speaker_name = speaker_name

        # Load TextGrid
        self.tg = TextGridReader.read(textgrid_path)
        self.prosody_tier = TextGridReader.get_prosody_tier(textgrid_path)
        self.syllable_tier = TextGridReader.get_syllable_tier(textgrid_path)

        if not self.prosody_tier:
            raise ValueError(f"No prosody tier found in {textgrid_path}")
        if not self.syllable_tier:
            raise ValueError(f"No syllable tier found in {textgrid_path}")

        # Parse into editable syllables
        self.syllables: list[EditableProsodicSyllable] = []
        self._parse_syllables()

        # Callbacks for UI integration
        self.on_modify: Optional[Callable[[EditableProsodicSyllable], None]] = None
        self.on_synthesize: Optional[Callable[[str, bytes], None]] = None

    def _parse_syllables(self):
        """Parse syllables with their prosody symbols."""
        for i, syl_interval in enumerate(self.syllable_tier.intervals):
            # Find corresponding prosody symbol
            prosody_symbol = self._get_prosody_at_time(syl_interval.xmin)

            self.syllables.append(
                EditableProsodicSyllable(
                    index=i,
                    onset=syl_interval.xmin,
                    offset=syl_interval.xmax,
                    text=syl_interval.text,
                    original_symbol=prosody_symbol,
                    current_symbol=prosody_symbol,
                )
            )

    def _get_prosody_at_time(self, time: float) -> str:
        """Get prosody symbol at given time."""
        for interval in self.prosody_tier.intervals:
            if interval.xmin <= time < interval.xmax:
                return interval.text
        return '?'

    def modify_symbol(self, syllable_index: int, new_symbol: str):
        """
        Modify prosody symbol for a syllable.

        Args:
            syllable_index: Index in self.syllables
            new_symbol: New symbol (/, //, \\, etc.)
        """
        if syllable_index >= len(self.syllables):
            raise IndexError(f"Syllable index {syllable_index} out of range")

        syl = self.syllables[syllable_index]
        syl.modify(new_symbol)

        if self.on_modify:
            self.on_modify(syl)

    def modify_accent(self, syllable_index: int, add: bool = True):
        """Toggle accent marker."""
        syl = self.syllables[syllable_index]
        if add and '*' not in syl.current_symbol:
            syl.modify('*' + syl.current_symbol)
        elif not add:
            syl.modify(syl.current_symbol.replace('*', ''))

    def modify_height(self, syllable_index: int, height: str):
        """
        Change height: 'high' (‾), 'mid', or 'low' (_).
        """
        syl = self.syllables[syllable_index]
        symbol = syl.current_symbol

        # Remove existing height marker
        symbol = symbol.replace('‾', '').replace('_', '')

        # Add new height
        if height == 'high':
            symbol += '‾'
        elif height == 'low':
            symbol += '_'

        syl.modify(symbol)

    def modify_direction(self, syllable_index: int, direction: str):
        """
        Change direction: 'rising', 'falling', 'level'.
        """
        syl = self.syllables[syllable_index]
        symbol = syl.current_symbol

        # Remove existing direction markers
        symbol = symbol.replace('/', '').replace('\\', '')

        # Add new direction
        if direction == 'rising':
            symbol += '//'
        elif direction == 'falling':
            symbol += '\\\\'
        elif direction == 'level':
            pass

        syl.modify(symbol)

    def compile_to_f0_targets(
        self,
        f0_floor: Optional[float] = None,
        f0_ceiling: Optional[float] = None,
    ) -> list[F0Target]:
        """
        Compile edited symbols to F0 targets.

        Args:
            f0_floor: Min F0 for speaker (Hz)
            f0_ceiling: Max F0 for speaker (Hz)

        Returns:
            List of F0Target points
        """
        compiler = F0Compiler(
            f0_floor=f0_floor or 75.0,
            f0_ceiling=f0_ceiling or 300.0,
        )

        syllables_data = [
            {
                'symbol': syl.current_symbol,
                'onset': syl.onset,
                'offset': syl.offset,
            }
            for syl in self.syllables
        ]

        return compiler.compile_utterance(syllables_data)

    def get_modified_syllables(self) -> list[EditableProsodicSyllable]:
        """Get list of syllables that were modified."""
        return [syl for syl in self.syllables if syl.is_modified]

    def reset_all(self):
        """Reset all syllables to original symbols."""
        for syl in self.syllables:
            syl.reset()

    def export_to_textgrid(self, output_path: str) -> str:
        """
        Export edited prosody tier to new TextGrid.

        Args:
            output_path: Where to save modified TextGrid

        Returns:
            Path to output file
        """
        # Create modified prosody tier
        new_intervals = []
        for syl in self.syllables:
            new_intervals.append(
                Interval(syl.onset, syl.offset, syl.current_symbol)
            )

        prosody_tier = IntervalTier(
            self.prosody_tier.name,
            self.prosody_tier.xmin,
            self.prosody_tier.xmax,
            new_intervals,
        )

        # Add modified tier to TextGrid
        tiers = dict(self.tg['tiers'])
        tiers[self.prosody_tier.name] = prosody_tier

        # Write
        TextGridWriter.write(
            output_path,
            self.tg.get('xmin', 0),
            self.tg.get('xmax', 1),
            tiers,
        )

        return output_path

    def summary(self) -> str:
        """Get text summary of current state."""
        modified = self.get_modified_syllables()
        lines = [
            f"Prosody Editor: {len(self.syllables)} syllables",
            f"Modified: {len(modified)}",
            "",
            "Syllables:",
        ]

        for syl in self.syllables:
            marker = "✓" if syl.is_modified else " "
            lines.append(
                f"  [{marker}] {syl.index:2d}: {syl.text:10s} "
                f"{syl.original_symbol:10s} → {syl.current_symbol}"
            )

        return "\n".join(lines)
