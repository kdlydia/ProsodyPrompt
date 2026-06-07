#!/usr/bin/env python3
"""SpeechPrint - Toolchain installer and project workspace launcher for Linux"""

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

from gi.repository import Gtk, Adw, Gio
from enum import Enum

from lib.modes.installation import InstallationMode
from lib.modes.corpus import CorpusCreationMode
from lib.modes.project import ProjectWorkspace
from lib.ui.theme import setup_css


# ============================================================================
# LAUNCH SCREEN
# ============================================================================


class Mode(Enum):
    INSTALLATION = 1
    NEW_PROJECT = 2
    OPEN_PROJECT = 3


class LaunchScreen(Gtk.ApplicationWindow):
    """Initial launcher: choose Install / New Project / Open Project."""

    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.selected_mode = None
        self.selected_project_dir = None

        self.set_title("SpeechPrint")
        self.set_default_size(540, 460)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_top(30)
        outer.set_margin_bottom(30)
        outer.set_margin_start(40)
        outer.set_margin_end(40)
        outer.set_spacing(18)
        self.set_child(outer)

        # Header
        title = Gtk.Label()
        title.set_markup(
            "<span size='22000' weight='bold'>SpeechPrint</span>"
        )
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            "<span size='small'>Linguistic Annotation Toolchain</span>"
        )
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        outer.append(subtitle)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        outer.append(sep)

        # ---- Three big choices -------------------------------------------

        outer.append(self._option(
            label="Install SpeechPrint",
            subtitle="Set up dependencies on this machine. One-time, ~5 GB.",
            on_click=self._on_install,
            primary=True,
        ))

        outer.append(self._option(
            label="New Project / Corpus",
            subtitle="Create a new analysis workspace for recordings and annotations.",
            on_click=self._on_new_project,
        ))

        outer.append(self._option(
            label="Open Existing Project",
            subtitle="Open a SpeechPrint project folder and work with its recordings.",
            on_click=self._on_open_project,
        ))

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        outer.append(spacer)

        quit_btn = Gtk.Button(label="Quit")
        quit_btn.add_css_class("flat")
        quit_btn.set_halign(Gtk.Align.END)
        quit_btn.connect("clicked", lambda b: self.close())
        outer.append(quit_btn)

    def _option(self, label, subtitle, on_click, primary=False):
        btn = Gtk.Button()
        if primary:
            btn.add_css_class("suggested-action")
        btn.set_size_request(-1, 70)
        btn.connect("clicked", on_click)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)
        title_lbl = Gtk.Label(label=label)
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.add_css_class("title")
        sub_lbl = Gtk.Label(label=subtitle)
        sub_lbl.set_halign(Gtk.Align.START)
        sub_lbl.set_wrap(True)
        sub_lbl.set_xalign(0.0)
        if not primary:
            sub_lbl.add_css_class("dim-label")
        box.append(title_lbl)
        box.append(sub_lbl)
        btn.set_child(box)
        return btn

    # -- handlers ---------------------------------------------------------

    def _on_install(self, btn):
        self.selected_mode = Mode.INSTALLATION
        self.close()

    def _on_new_project(self, btn):
        self.selected_mode = Mode.NEW_PROJECT
        self.close()

    def _on_open_project(self, btn):
        dlg = Gtk.FileChooserDialog(
            title="Open SpeechPrint project",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            transient_for=self,
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                        "_Open", Gtk.ResponseType.OK)
        dlg.connect("response", self._on_open_project_response)
        dlg.present()

    def _on_open_project_response(self, dlg, response):
        if response == Gtk.ResponseType.OK:
            gfile = dlg.get_file()
            if gfile:
                self.selected_project_dir = Path(gfile.get_path())
                self.selected_mode = Mode.OPEN_PROJECT
                dlg.close()
                self.close()
                return
        dlg.close()


# ============================================================================
# APP
# ============================================================================


class SpeechPrintApp(Adw.Application):
    """Main application."""

    def __init__(self):
        super().__init__(application_id="org.speechprint.workspace")
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        setup_css(app)

        # If invoked with a directory argument, jump straight to the workspace
        args = sys.argv[1:]
        project_dir = None
        for a in args:
            p = Path(a)
            if p.is_dir() and (p / "corpus.toml").exists():
                project_dir = p.resolve()
                break

        if project_dir:
            window = ProjectWorkspace(self, cfg, project_dir)
            window.present()
            return

        launcher = LaunchScreen(self)
        launcher.present()
        launcher.connect("close-request", self._on_launcher_closed, launcher)

    def _on_launcher_closed(self, window, launcher):
        if launcher.selected_mode == Mode.INSTALLATION:
            InstallationMode(self, cfg).present()
        elif launcher.selected_mode == Mode.NEW_PROJECT:
            corpus_window = CorpusCreationMode(self, cfg)
            # After successful creation, the corpus window will set
            # `corpus_window.created_path` and close; we open the workspace.
            corpus_window.on_finished = self._open_workspace_from_path
            corpus_window.present()
        elif launcher.selected_mode == Mode.OPEN_PROJECT and launcher.selected_project_dir:
            self._open_workspace_from_path(launcher.selected_project_dir)
        else:
            self.quit()
        return False

    def _open_workspace_from_path(self, project_dir: Path):
        window = ProjectWorkspace(self, cfg, project_dir)
        window.present()


def main():
    app = SpeechPrintApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
