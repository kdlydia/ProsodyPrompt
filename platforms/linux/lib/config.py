#!/usr/bin/env python3
"""
Unified configuration loader for SpeechPrint.

All components (Python, Bash, CI scripts) should use this to discover paths.
This is the single source of truth for where things are located.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional


class SpeechPrintConfig:
    """Single source of truth for SpeechPrint configuration."""

    def __init__(self):
        self._config: Dict = {}
        self._root: Optional[Path] = None
        self._load()

    def _load(self):
        """Load configuration from speechprint-config.json."""
        self._root = self._find_speechprint_root()

        if not self._root:
            raise RuntimeError(
                "Cannot find SpeechPrint installation. "
                "Set SPEECHPRINT_ROOT environment variable or ensure "
                "speechprint-config.json exists."
            )

        config_path = self._root / "speechprint-config.json"

        if not config_path.exists():
            raise RuntimeError(
                f"Configuration file not found: {config_path}\n"
                f"SpeechPrint root detected at: {self._root}"
            )

        with open(config_path) as f:
            self._config = json.load(f)

        # Resolve all ${SPEECHPRINT_ROOT} and ${...} references
        self._resolve_paths()

    def _find_speechprint_root(self) -> Optional[Path]:
        """Find SpeechPrint root directory in order of priority."""

        # 1. Explicit environment variable
        if sp_root := os.environ.get("SPEECHPRINT_ROOT"):
            path = Path(sp_root).expanduser().resolve()
            if (path / "speechprint-config.json").exists():
                return path

        # 2. Relative to this Python module (bundled distribution)
        module_path = Path(__file__).parent.parent.parent  # lib/config.py -> SpeechPrint/
        if (module_path / "speechprint-config.json").exists():
            return module_path

        # 3. Relative to launcher script (if SPEECHPRINT_LAUNCHER_DIR is set)
        if launcher_dir := os.environ.get("SPEECHPRINT_LAUNCHER_DIR"):
            path = Path(launcher_dir).expanduser().resolve()
            if (path / "speechprint-config.json").exists():
                return path

        # 4. Standard system locations
        standard_locations = [
            Path.home() / ".local/speechprint",
            Path.home() / "SpeechPrint",
            Path("/opt/speechprint"),
            Path("/usr/local/speechprint"),
        ]

        for location in standard_locations:
            if (location / "speechprint-config.json").exists():
                return location

        return None

    def _resolve_paths(self):
        """Resolve ${SPEECHPRINT_ROOT} and other variable references."""
        root_str = str(self._root)

        def resolve_value(value):
            if isinstance(value, str):
                return value.replace("${SPEECHPRINT_ROOT}", root_str)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            return value

        self._config = resolve_value(self._config)

    def get(self, key: str, default=None):
        """Get configuration value by dot-notation key."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    @property
    def root(self) -> Path:
        """Get SpeechPrint root directory."""
        return self._root

    @property
    def scripts_dir(self) -> Path:
        """Get scripts directory."""
        return Path(self.get("paths.scripts"))

    @property
    def templates_dir(self) -> Path:
        """Get templates directory."""
        return Path(self.get("paths.templates"))

    @property
    def lib_dir(self) -> Path:
        """Get lib directory."""
        return Path(self.get("paths.lib"))

    @property
    def python_path(self) -> str:
        """Get PYTHONPATH value."""
        return self.get("paths.python_path")

    @property
    def supported_languages(self) -> list:
        """Get list of supported language codes."""
        return self.get("languages.supported", ["en"])

    @property
    def default_language(self) -> str:
        """Get default language code."""
        return self.get("languages.default", "en")

    @property
    def language_names(self) -> Dict[str, str]:
        """Get language code to display-name map."""
        return self.get("languages.names", {})

    def get_script(self, name: str) -> Path:
        """Get path to a bundled script."""
        script_path = self.get(f"executables.{name}")
        if not script_path:
            raise KeyError(f"Script not found in config: {name}")
        return Path(script_path)

    def get_env_vars(self) -> Dict[str, str]:
        """Get all environment variables that should be set."""
        env_vars = self.get("environment_variables", {})
        resolved = {}

        for key, value in env_vars.items():
            if isinstance(value, str):
                resolved[key] = value.replace("${SPEECHPRINT_ROOT}", str(self._root))
                # Preserve existing env vars in paths
                if "${PYTHONPATH}" in resolved[key]:
                    existing = os.environ.get("PYTHONPATH", "")
                    resolved[key] = resolved[key].replace("${PYTHONPATH}", existing)
            else:
                resolved[key] = value

        return resolved

    def to_bash_export(self) -> str:
        """Generate bash export statements for sourcing."""
        exports = []
        for key, value in self.get_env_vars().items():
            # Escape for bash
            escaped = value.replace('"', '\\"')
            exports.append(f'export {key}="{escaped}"')
        return "\n".join(exports)

    def to_json(self) -> str:
        """Serialize configuration to JSON."""
        return json.dumps(self._config, indent=2)


# Singleton instance
_config_instance: Optional[SpeechPrintConfig] = None


def get_config() -> SpeechPrintConfig:
    """Get or create the configuration singleton."""
    global _config_instance
    if _config_instance is None:
        _config_instance = SpeechPrintConfig()
    return _config_instance


if __name__ == "__main__":
    # Debug: print configuration
    try:
        cfg = get_config()
        print(f"SpeechPrint root: {cfg.root}")
        print(f"Scripts dir: {cfg.scripts_dir}")
        print(f"Templates dir: {cfg.templates_dir}")
        print(f"Supported languages: {cfg.supported_languages}")
        print("\nEnvironment variables:")
        for key, value in cfg.get_env_vars().items():
            print(f"  {key}={value}")
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)


# Optional evaluation link
EVALUATION_FORM_URL = "https://google.com/forms/speechprint-evaluation"

