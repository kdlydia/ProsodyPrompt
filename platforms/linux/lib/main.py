#!/usr/bin/env python3
"""SpeechPrint - Toolchain installer and corpus creator for Linux"""

import os
import sys
from pathlib import Path

_main_dir = Path(__file__).parent
_lib_dir = _main_dir.parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

try:
    from lib.config import get_config

    cfg = get_config()

    for key, value in cfg.get_env_vars().items():
        os.environ.setdefault(key, value)

except Exception as e:
    print(f"Error loading SpeechPrint configuration: {e}", file=sys.stderr)
    sys.exit(1)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from enum import Enum

from lib.modes.installation import InstallationMode
from lib.modes.corpus import CorpusCreationMode
from lib.modes.project import ProjectWorkspace
from lib.ui.theme import setup_css


class Mode(Enum):
    INSTALLATION = 1
    CORPUS_CREATION = 2


class ModeSelector(Gtk.ApplicationWindow):
    """Modal to choose Install or New Project / Corpus"""

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("SpeechPrint - Select Mode")
        self.set_default_size(500, 300)
        self.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(30)
        box.set_margin_bottom(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup(
            "<span size='18000' weight='bold'>What would you like to do?</span>"
        )
        title.set_halign(Gtk.Align.START)
        box.append(title)

        install_btn = Gtk.Button(label="Install SpeechPrint")
        install_btn.set_size_request(-1, 80)
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self._on_install_clicked)
        box.append(install_btn)

        corpus_btn = Gtk.Button(label="New Project / Corpus")
        corpus_btn.set_size_request(-1, 80)
        corpus_btn.add_css_class("suggested-action")
        corpus_btn.connect("clicked", self._on_corpus_clicked)
        box.append(corpus_btn)

        self.set_child(box)
        self.selected_mode = None

    def _on_install_clicked(self, btn):
        self.selected_mode = Mode.INSTALLATION
        self.close()

    def _on_corpus_clicked(self, btn):
        self.selected_mode = Mode.CORPUS_CREATION
        self.close()


class SpeechPrintApp(Adw.Application):
    """Main application"""

    def __init__(self):
        super().__init__(application_id="org.speechprint.installer")
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        setup_css(app)

        # If invoked with a directory argument, jump straight to the workspace
        for a in sys.argv[1:]:
            p = Path(a)
            if p.is_dir() and (p / "corpus.toml").exists():
                ProjectWorkspace(self, cfg, p.resolve()).present()
                return

        icon_path = Path(__file__).parent.parent / "resources" / "speechprint.png"
        if icon_path.exists():
            pass

        selector = ModeSelector(self)
        selector.present()
        selector.connect("close-request", self._on_mode_selected, selector)

    def _on_mode_selected(self, window, selector):
        if selector.selected_mode == Mode.INSTALLATION:
            main_window = InstallationMode(self, cfg)
            main_window.present()
        elif selector.selected_mode == Mode.CORPUS_CREATION:
            main_window = CorpusCreationMode(self, cfg)
            # Wire the project workspace so "Open Project" in the success
            # dialog drops the user straight into Import/Record/Annotate.
            main_window.on_finished = self._open_workspace_from_path
            main_window.present()
        else:
            self.quit()
            return
        return False

    def _open_workspace_from_path(self, project_dir: Path):
        ProjectWorkspace(self, cfg, project_dir).present()


def main():
    app = SpeechPrintApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())


# Optional evaluation link
EVALUATION_FORM_URL = "https://google.com/forms/speechprint-evaluation"
