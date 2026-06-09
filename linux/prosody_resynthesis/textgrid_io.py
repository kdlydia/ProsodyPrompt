"""TextGrid I/O: Read and write TextGrid files with prosody tier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Interval:
    """A TextGrid interval."""
    xmin: float
    xmax: float
    text: str

    @property
    def duration(self) -> float:
        return self.xmax - self.xmin


@dataclass
class IntervalTier:
    """A TextGrid interval tier."""
    name: str
    xmin: float
    xmax: float
    intervals: list[Interval]

    def get_at_time(self, time: float) -> Optional[Interval]:
        """Get interval containing time."""
        for interval in self.intervals:
            if interval.xmin <= time < interval.xmax:
                return interval
        return None


class TextGridReader:
    """Read TextGrid files."""

    @staticmethod
    def read(path: str | Path) -> dict:
        """
        Read TextGrid file.

        Returns:
            Dict with keys:
            - 'xmin', 'xmax': overall time bounds
            - 'tiers': dict mapping tier names to IntervalTier objects
        """
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {'tiers': {}}

        # Extract overall bounds
        xmin_match = re.search(r'xmin = ([\d.]+)', content)
        xmax_match = re.search(r'xmax = ([\d.]+)', content)

        if xmin_match:
            result['xmin'] = float(xmin_match.group(1))
        if xmax_match:
            result['xmax'] = float(xmax_match.group(1))

        # Extract tiers
        tier_pattern = r'name = "(.*?)"\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)'
        for match in re.finditer(tier_pattern, content):
            tier_name = match.group(1)
            xmin = float(match.group(2))
            xmax = float(match.group(3))

            # Find intervals for this tier
            intervals = TextGridReader._extract_intervals(content, tier_name)

            tier = IntervalTier(tier_name, xmin, xmax, intervals)
            result['tiers'][tier_name] = tier

        return result

    @staticmethod
    def _extract_intervals(content: str, tier_name: str) -> list[Interval]:
        """Extract all intervals for a specific tier."""
        intervals = []

        # Find the tier section
        tier_start = content.find(f'name = "{tier_name}"')
        if tier_start == -1:
            return intervals

        # Find next tier or end of file
        next_tier = content.find('name = "', tier_start + 1)
        tier_section = content[tier_start:next_tier] if next_tier != -1 else content[tier_start:]

        # Find intervals in this section
        interval_pattern = r'xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "(.*?)"'
        for match in re.finditer(interval_pattern, tier_section):
            xmin = float(match.group(1))
            xmax = float(match.group(2))
            text = match.group(3)

            # Unescape quotes in text
            text = text.replace('\\"', '"')

            intervals.append(Interval(xmin, xmax, text))

        return intervals

    @staticmethod
    def get_prosody_tier(textgrid_path: str | Path) -> Optional[IntervalTier]:
        """Get the prosody tier from a TextGrid."""
        tg = TextGridReader.read(textgrid_path)

        # Try common prosody tier names
        for name in ['prosody', 'prosody_pyin', 'prosody_crepe', 'tone']:
            if name in tg['tiers']:
                return tg['tiers'][name]

        # Fall back to any tier with 'prosody' in name
        for name, tier in tg['tiers'].items():
            if 'prosody' in name.lower():
                return tier

        return None

    @staticmethod
    def get_syllable_tier(textgrid_path: str | Path) -> Optional[IntervalTier]:
        """Get the syllable tier from a TextGrid."""
        tg = TextGridReader.read(textgrid_path)

        if 'syllables' in tg['tiers']:
            return tg['tiers']['syllables']

        for name in tg['tiers'].keys():
            if 'syll' in name.lower():
                return tg['tiers'][name]

        return None


class TextGridWriter:
    """Write TextGrid files."""

    @staticmethod
    def write(
        output_path: str | Path,
        xmin: float,
        xmax: float,
        tiers: dict[str, IntervalTier],
    ):
        """Write TextGrid file."""
        output_path = Path(output_path)

        lines = [
            'File type = "ooTextFile"',
            'Object class = "TextGrid"',
            '',
            f'xmin = {xmin}',
            f'xmax = {xmax}',
            'tiers? <exists>',
            f'size = {len(tiers)}',
            'item []:',
        ]

        for i, (tier_name, tier) in enumerate(tiers.items(), 1):
            lines.append(f'    item [{i}]:')
            lines.append(f'        class = "IntervalTier"')
            lines.append(f'        name = "{tier_name}"')
            lines.append(f'        xmin = {tier.xmin}')
            lines.append(f'        xmax = {tier.xmax}')
            lines.append(f'        intervals: size = {len(tier.intervals)}')

            for j, interval in enumerate(tier.intervals, 1):
                lines.append(f'        intervals [{j}]:')
                lines.append(f'            xmin = {interval.xmin}')
                lines.append(f'            xmax = {interval.xmax}')
                # Escape quotes in text
                text = interval.text.replace('"', '\\"')
                lines.append(f'            text = "{text}"')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    @staticmethod
    def add_prosody_tier(
        input_path: str | Path,
        output_path: str | Path,
        new_tier_name: str,
        new_tier_intervals: list[Interval],
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
    ):
        """Add a new prosody tier to an existing TextGrid."""
        input_path = Path(input_path)

        # Read existing TextGrid
        tg = TextGridReader.read(input_path)

        # Use bounds from input or provided values
        xmin = xmin or tg.get('xmin', 0)
        xmax = xmax or tg.get('xmax', 1)

        # Create new tier
        new_tier = IntervalTier(new_tier_name, xmin, xmax, new_tier_intervals)

        # Add to tiers
        tg['tiers'][new_tier_name] = new_tier

        # Write output
        TextGridWriter.write(output_path, xmin, xmax, tg['tiers'])
