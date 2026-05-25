#!/usr/bin/env python3
"""Corpus creation mode - GTK4 compatible"""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio, GLib
import subprocess
import os
from pathlib import Path


class CorpusCreationMode(Gtk.ApplicationWindow):
    """Create new SpeechPrint corpus"""

    def __init__(self, app, cfg):
        super().__init__(application=app)
        self.cfg = cfg
        self.template_dir = cfg.templates_dir
        self.script_dir = cfg.scripts_dir
        # Callback invoked with the created project Path after a successful run.
        # Set by the launcher to open the project workspace automatically.
        self.on_finished = None
        self.created_path = None
        self.set_title("SpeechPrint - New Project / Corpus")
        self.set_default_size(600, 500)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Gtk.HeaderBar()
        main_box.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_top(20)
        content.set_margin_start(30)
        content.set_margin_end(30)
        content.set_margin_bottom(20)

        title = Gtk.Label()
        title.set_markup("<span size='18000' weight='bold'>New Project / Corpus</span>")
        title.set_halign(Gtk.Align.START)
        content.append(title)

        name_label = Gtk.Label(label="Project Name:")
        name_label.set_halign(Gtk.Align.START)
        content.append(name_label)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("MyCorpus")
        self.name_entry.set_text("MyCorpus")
        self.name_entry.connect("changed", self._update_preview)
        content.append(self.name_entry)

        loc_label = Gtk.Label(label="Location:")
        loc_label.set_halign(Gtk.Align.START)
        content.append(loc_label)

        loc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        loc_box.set_homogeneous(False)

        self.loc_entry = Gtk.Entry()
        self.loc_entry.set_text(str(Path.home() / "Corpora"))
        self.loc_entry.set_hexpand(True)
        self.loc_entry.connect("changed", self._update_preview)
        loc_box.append(self.loc_entry)

        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.set_size_request(100, -1)
        browse_btn.connect("clicked", self._on_browse)
        loc_box.append(browse_btn)

        content.append(loc_box)

        lang_label = Gtk.Label(label="Primary Language:")
        lang_label.set_halign(Gtk.Align.START)
        content.append(lang_label)

        self.lang_combo = Gtk.DropDown()
        codes = cfg.supported_languages
        names = cfg.language_names
        labels = [f"{names.get(c, c)} ({c})" for c in codes]
        model = Gtk.StringList.new(labels)
        self.lang_combo.set_model(model)
        # Set default
        try:
            default_idx = codes.index(cfg.default_language)
        except ValueError:
            default_idx = 0
        self.lang_combo.set_selected(default_idx)
        self._lang_codes = codes
        content.append(self.lang_combo)

        lang_hint = Gtk.Label()
        lang_hint.set_markup(
            "<span size='small'>This only sets the default language for new recordings. "
            "You can change language per file later.</span>"
        )
        lang_hint.set_halign(Gtk.Align.START)
        lang_hint.set_wrap(True)
        lang_hint.set_xalign(0.0)
        lang_hint.add_css_class("dim-label")
        content.append(lang_hint)

        self.ensemble_check = Gtk.CheckButton(
            label="Auto-ensemble (run aggregation after each annotate)"
        )
        content.append(self.ensemble_check)

        self.vscode_check = Gtk.CheckButton(label="Include VS Code configuration")
        self.vscode_check.set_active(True)
        content.append(self.vscode_check)

        preview_label = Gtk.Label(label="Project / corpus will be created at:")
        preview_label.set_halign(Gtk.Align.START)
        preview_label.add_css_class("dim-label")
        content.append(preview_label)

        self.preview = Gtk.Label()
        self.preview.set_markup(f"<tt>{Path.home()}/Corpora/MyCorpus</tt>")
        self.preview.set_halign(Gtk.Align.START)
        self.preview.set_selectable(True)
        content.append(self.preview)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        content.append(spacer)

        scroll.set_child(content)
        main_box.append(scroll)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_margin_top(10)
        btn_box.set_margin_bottom(10)
        btn_box.set_margin_start(30)
        btn_box.set_margin_end(30)
        btn_box.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.close())
        btn_box.append(cancel)

        self.create_btn = Gtk.Button(label="New Project / Corpus")
        self.create_btn.add_css_class("suggested-action")
        self.create_btn.connect("clicked", self._on_create)
        btn_box.append(self.create_btn)

        main_box.append(btn_box)
        self.set_child(main_box)

    def _on_browse(self, btn):
        """Open folder chooser dialog"""
        dialog = Gtk.FileChooserDialog(
            title="Select Corpus Location",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            transient_for=self,
        )

        dialog.add_buttons(
            "_Cancel",
            Gtk.ResponseType.CANCEL,
            "_Open",
            Gtk.ResponseType.OK,
        )

        current_path = self.loc_entry.get_text()
        if Path(current_path).is_dir():
            dialog.set_current_folder(Gio.File.new_for_path(current_path))

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                file = dialog.get_file()
                if file:
                    self.loc_entry.set_text(file.get_path())
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _update_preview(self, widget):
        """Update preview path as user types"""
        name = self.name_entry.get_text() or "MyCorpus"
        loc = self.loc_entry.get_text() or str(Path.home())

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

        preview_path = f"{loc}/{safe_name}"
        self.preview.set_markup(f"<tt>{preview_path}</tt>")

    def _selected_language(self):
        idx = self.lang_combo.get_selected()
        if 0 <= idx < len(self._lang_codes):
            return self._lang_codes[idx]
        return self.cfg.default_language

    def _on_create(self, btn):
        """Create the corpus"""
        name = self.name_entry.get_text().strip()
        loc = self.loc_entry.get_text().strip()

        if not name:
            self._show_error("Corpus name cannot be empty")
            return

        if not loc:
            self._show_error("Please select a location")
            return

        loc_path = Path(loc).expanduser()
        if not loc_path.is_dir():
            try:
                loc_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self._show_error(f"Cannot create location:\n{loc_path}\n\n{e}")
                return

        corpus_dir = loc_path / name
        if corpus_dir.exists():
            self._show_error(f"Corpus already exists:\n{corpus_dir}")
            return

        self.create_btn.set_sensitive(False)
        original_label = self.create_btn.get_label()
        self.create_btn.set_label("Creating...")

        name_captured = name
        loc_captured = str(loc_path)
        label_captured = original_label

        GLib.timeout_add(
            100,
            lambda n=name_captured, l=loc_captured, lbl=label_captured: self._create_corpus_async(
                n, l, lbl
            ),
        )

    def _create_corpus_async(self, name, loc, original_label):
        """New project / corpus asynchronously"""
        try:
            loc = str(Path(loc).expanduser().resolve())
            env = os.environ.copy()
            env["SPEECHPRINT_TEMPLATE_DIR"] = str(self.template_dir)
            script_path = self.script_dir / "create_corpus.sh"

            cmd = [
                str(script_path),
                "new",
                name,
                loc,
                "--language",
                self._selected_language(),
            ]
            if self.ensemble_check.get_active():
                cmd.append("--auto-ensemble")
            if not self.vscode_check.get_active():
                cmd.append("--no-vscode")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, env=env
            )

            if result.returncode == 0:
                corpus_path = Path(loc) / name
                self.created_path = corpus_path
                dialog = Gtk.AlertDialog(
                    message="Project Created",
                    detail=(
                        f"Location:\n{corpus_path}\n\n"
                        f"You can now import or record audio, run annotation, "
                        f"and open results in Praat — all from the workspace."
                    ),
                )
                dialog.set_buttons(["Open Project", "Close"])
                dialog.set_default_button(0)
                dialog.set_cancel_button(1)
                dialog.choose(self, None, self._on_creation_complete, corpus_path)
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self._show_error(f"Failed to create project:\n{error_msg}")
                self.create_btn.set_sensitive(True)
                self.create_btn.set_label(original_label)
        except subprocess.TimeoutExpired:
            self._show_error("Project creation timed out")
            self.create_btn.set_sensitive(True)
            self.create_btn.set_label(original_label)
        except Exception as e:
            self._show_error(f"Error:\n{str(e)}")
            self.create_btn.set_sensitive(True)
            self.create_btn.set_label(original_label)

    def _on_creation_complete(self, dialog, result, corpus_path):
        """Handle corpus creation completion."""
        try:
            choice = dialog.choose_finish(result)
        except Exception:
            choice = 1
        # choice == 0 → Open Project; 1 → Close
        if choice == 0 and corpus_path and self.on_finished:
            try:
                self.on_finished(corpus_path)
            except Exception as e:
                print(f"on_finished error: {e}")
        self.close()

    def _show_error(self, message):
        """Show error dialog"""
        dialog = Gtk.AlertDialog(message="Error", detail=message)
        dialog.choose(self, None, lambda d, r, u: d.choose_finish(r), None)


# Optional evaluation link
EVALUATION_FORM_URL = "https://google.com/forms/speechprint-evaluation"

