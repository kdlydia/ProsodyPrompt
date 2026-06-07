"""Project workspace - the main GUI for working with a SpeechPrint corpus.

This is what the user sees AFTER creating a project. It exposes:
    - Import Audio (file chooser, copies into data/)
    - Record Audio (uses parec/arecord, saves as data/recording_NN.wav)
    - Run Annotation (runs the full pipeline on a selected file)
    - Open in Praat (launches Praat with the file and TextGrid loaded)
    - Open Folder (opens out/<name>/ in the file manager)
    - Export ZIP (zips an annotation output for sharing)
    - Open Feedback Form
"""

import gi
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GLib, Gio, Pango
from lib.ui.annotation_wizard import AnnotationWizard

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


# ============================================================================
# UTILITIES
# ============================================================================


def _safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9_\-\.]", "_", name)
    return name or "recording"


def _next_recording_name(data_dir: Path, prefix: str = "recording") -> str:
    """Find the next free recording_NN.wav name."""
    n = 1
    while (data_dir / f"{prefix}_{n:02d}.wav").exists():
        n += 1
    return f"{prefix}_{n:02d}.wav"


# ============================================================================
# RUN PIPELINE IN BACKGROUND
# ============================================================================


class PipelineRunner:
    """Runs `python -m speechprint_pkg.cli annotate` in a subprocess and streams
    the staged-progress output back to a GTK callback.
    """

    def __init__(self, on_stage, on_line, on_done):
        """on_stage(num:int, total:int, name:str)   - called for each [N/T] stage line
        on_line(text:str)                           - called for every other log line
        on_done(rc:int, out_dir:Path|None)          - called when subprocess exits
        """
        self.on_stage = on_stage
        self.on_line = on_line
        self.on_done = on_done
        self._proc = None
        self._thread = None
        self._cancelled = False

    def run(self, wav: Path, language: str, output_dir: Path):
        """Kick off the pipeline subprocess."""
        cmd = [
            sys.executable, "-m", "speechprint_pkg.cli",
            "annotate", str(wav),
            "--language", language,
            "--output", str(output_dir),
        ]
        self._thread = threading.Thread(
            target=self._run_worker,
            args=(cmd, output_dir / wav.stem),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _run_worker(self, cmd, expected_out_dir):
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            GLib.idle_add(self.on_line, f"✗ Failed to start pipeline: {e}")
            GLib.idle_add(self.on_done, 1, None)
            return

        stage_re = re.compile(r"^\[(\d+)/(\d+)\]\s+(.+)$")

        for raw in self._proc.stdout:
            if self._cancelled:
                break
            line = raw.rstrip("\n")
            m = stage_re.match(line.strip())
            if m:
                num = int(m.group(1))
                total = int(m.group(2))
                rest = m.group(3)
                # Drop trailing " — context" if present, keep just the stage name
                name = rest.split(" — ", 1)[0]
                GLib.idle_add(self.on_stage, num, total, name)
                GLib.idle_add(self.on_line, line)
            else:
                GLib.idle_add(self.on_line, line)

        rc = self._proc.wait()
        out_dir = expected_out_dir if expected_out_dir.exists() else None
        GLib.idle_add(self.on_done, rc, out_dir)


# ============================================================================
# RECORD AUDIO  (Linux: arecord / parec / ffmpeg)
# ============================================================================


class AudioRecorder:
    """Record from default mic to a 16 kHz mono WAV using whichever tool is around."""

    def __init__(self):
        self.proc = None
        self.out_path: Path | None = None
        self.started_at: float | None = None

    @staticmethod
    def _which(*names):
        for n in names:
            p = shutil.which(n)
            if p:
                return p
        return None

    def start(self, out_path: Path) -> tuple[bool, str]:
        self.out_path = out_path
        # ffmpeg is the most portable option here
        ffmpeg = self._which("ffmpeg")
        arecord = self._which("arecord")
        parec = self._which("parec")
        if ffmpeg:
            # Try pulseaudio first (works on most modern desktops), fall back to ALSA default
            cmd = [
                ffmpeg, "-y",
                "-f", "pulse", "-i", "default",
                "-ac", "1", "-ar", "16000",
                str(out_path),
            ]
        elif arecord:
            cmd = [arecord, "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", str(out_path)]
        elif parec:
            # parec → wav via sox-less pipe is awkward; require ffmpeg/arecord
            return False, "Found parec but no ffmpeg/arecord to write WAV directly. Install ffmpeg."
        else:
            return False, "No audio capture tool found. Install ffmpeg or alsa-utils."

        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
            self.started_at = time.time()
            return True, ""
        except Exception as e:
            return False, str(e)

    def stop(self) -> tuple[bool, str]:
        if not self.proc:
            return False, "Not recording"
        try:
            # ffmpeg responds to 'q' on stdin or SIGINT; SIGTERM is safer here
            self.proc.terminate()
            self.proc.wait(timeout=5)
            return True, ""
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            return True, "Recorder force-killed"
        except Exception as e:
            return False, str(e)
        finally:
            self.proc = None

    def elapsed(self) -> float:
        return (time.time() - self.started_at) if self.started_at else 0.0


# ============================================================================
# OPEN-EXTERNAL HELPERS
# ============================================================================


def open_in_praat(wav: Path, textgrid: Path | None = None):
    """Open a WAV (+ TextGrid) in Praat using its command-line invocation."""
    praat = shutil.which("praat")
    if not praat:
        return False, "Praat not found in PATH"

    # Praat's "--open" works for both Sound and TextGrid; opening both at once
    # gives the user the editor view with the TextGrid aligned to the sound.
    args = [praat, "--open", str(wav)]
    if textgrid and textgrid.exists():
        args.append(str(textgrid))
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as e:
        return False, str(e)


def open_folder(path: Path):
    """Open a folder in the system file manager."""
    if not path.exists():
        return False, f"Folder not found: {path}"
    opener = shutil.which("xdg-open") or shutil.which("open")
    if not opener:
        return False, "No xdg-open / open found"
    try:
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as e:
        return False, str(e)


def open_url(url: str):
    """Open URL in default browser."""
    opener = shutil.which("xdg-open") or shutil.which("open")
    if not opener:
        return False, "No xdg-open / open found"
    try:
        subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as e:
        return False, str(e)


# ============================================================================
# WORKSPACE WINDOW
# ============================================================================


# Pipeline stage names — must match speechprint_pkg/cli.py STAGES
PIPELINE_STAGES = [
    "Loading audio",
    "Transcribing speech with Whisper",
    "Preparing transcript for alignment",
    "Running forced alignment",
    "Extracting pitch, intensity, and formants",
    "Creating IPA / phone layer",
    "Creating symbolic prosody layer",
    "Writing Praat TextGrid",
    "Exporting CSV / ZIP",
]


FEEDBACK_FORM_URL = "https://forms.gle/speechprint-evaluation"


class ProjectWorkspace(Gtk.ApplicationWindow):
    """The main project window. Lists recordings in data/, shows status of
    each (annotated or not), exposes the action buttons.
    """

    def __init__(self, app, cfg, project_dir: Path):
        super().__init__(application=app)
        self.cfg = cfg
        self.project_dir = Path(project_dir).resolve()
        self.data_dir = self.project_dir / "data"
        self.out_dir = self.project_dir / "out"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Read corpus.toml for the default language (without needing tomllib)
        self.default_language = self._read_default_language()

        self.recorder = AudioRecorder()
        self.recorder_tick_source = None
        self.runner: PipelineRunner | None = None
        self.selected_wav: Path | None = None

        self.set_title(f"SpeechPrint — {self.project_dir.name}")
        self.set_default_size(900, 640)

        self._build_ui()
        self.refresh_recordings()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)

        header = Gtk.HeaderBar()
        outer.append(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=self.project_dir.name)
        title.add_css_class("title")
        subtitle = Gtk.Label(label=str(self.project_dir))
        subtitle.add_css_class("dim-label")
        subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        title_box.append(title)
        title_box.append(subtitle)
        header.set_title_widget(title_box)

        # Main horizontal split: list on the left, detail+log on the right
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(330)
        paned.set_vexpand(True)
        outer.append(paned)

        # ---- LEFT: recordings list + import/record buttons ----
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_margin_top(12)
        left.set_margin_bottom(12)
        left.set_margin_start(12)
        left.set_margin_end(6)

        left.append(self._section_label("Recordings"))

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        self.recordings_list = Gtk.ListBox()
        self.recordings_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.recordings_list.connect("row-selected", self._on_row_selected)
        scroller.set_child(self.recordings_list)
        left.append(scroller)

        # Import + Record buttons
        action_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_grid.set_homogeneous(True)

        import_btn = Gtk.Button(label="Import Audio")
        import_btn.connect("clicked", self._on_import)
        action_grid.append(import_btn)

        self.record_btn = Gtk.Button(label="● Record")
        self.record_btn.add_css_class("destructive-action")
        self.record_btn.connect("clicked", self._on_record_toggle)
        action_grid.append(self.record_btn)
        left.append(action_grid)

        self.record_status = Gtk.Label(label="")
        self.record_status.add_css_class("dim-label")
        self.record_status.set_halign(Gtk.Align.START)
        left.append(self.record_status)

        paned.set_start_child(left)

        # ---- RIGHT: actions + progress + log ----
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_margin_top(12)
        right.set_margin_bottom(12)
        right.set_margin_start(6)
        right.set_margin_end(12)

        # Selected file info
        self.selected_label = Gtk.Label(label="No recording selected")
        self.selected_label.set_halign(Gtk.Align.START)
        self.selected_label.add_css_class("heading")
        right.append(self.selected_label)

        # Language picker
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_box.append(Gtk.Label(label="Language for this recording:"))
        self.lang_combo = Gtk.DropDown()
        self._lang_codes = self.cfg.supported_languages
        labels = [
            f"{self.cfg.language_names.get(c, c)} ({c})"
            for c in self._lang_codes
        ]
        self.lang_combo.set_model(Gtk.StringList.new(labels))
        try:
            self.lang_combo.set_selected(self._lang_codes.index(self.default_language))
        except ValueError:
            self.lang_combo.set_selected(0)
        lang_box.append(self.lang_combo)
        right.append(lang_box)

        # Action buttons row 1: Run pipelines
        run_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        run_box.set_homogeneous(True)
        self.run_btn = Gtk.Button(label="Run Annotation")
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.connect("clicked", self._on_run_annotation)
        self.run_btn.set_sensitive(False)
        run_box.append(self.run_btn)

        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.connect("clicked", self._on_cancel_pipeline)
        self.cancel_btn.set_sensitive(False)
        run_box.append(self.cancel_btn)
        right.append(run_box)

        # Action buttons row 2: open + export
        open_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        open_box.set_homogeneous(True)
        self.praat_btn = Gtk.Button(label="Open in Praat")
        self.praat_btn.connect("clicked", self._on_open_in_praat)
        self.praat_btn.set_sensitive(False)
        open_box.append(self.praat_btn)

        self.folder_btn = Gtk.Button(label="Open Folder")
        self.folder_btn.connect("clicked", self._on_open_folder)
        self.folder_btn.set_sensitive(False)
        open_box.append(self.folder_btn)

        self.zip_btn = Gtk.Button(label="Export ZIP")
        self.zip_btn.connect("clicked", self._on_export_zip)
        self.zip_btn.set_sensitive(False)
        open_box.append(self.zip_btn)
        right.append(open_box)

        # Progress display ----------------------------------------------------
        right.append(self._section_label("Annotation progress"))

        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.progress_box.set_margin_start(8)
        self.stage_labels: list[Gtk.Label] = []
        for i, name in enumerate(PIPELINE_STAGES, 1):
            lbl = Gtk.Label(label=f"  ○  {i}. {name}")
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("dim-label")
            self.stage_labels.append(lbl)
            self.progress_box.append(lbl)
        right.append(self.progress_box)

        # Status line
        self.status_line = Gtk.Label(label="")
        self.status_line.set_halign(Gtk.Align.START)
        right.append(self.status_line)

        # Collapsible technical log -----------------------------------------
        log_expander = Gtk.Expander(label="Show technical log")
        log_expander.set_vexpand(True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(120)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_scroll.set_child(self.log_view)
        log_expander.set_child(log_scroll)
        right.append(log_expander)

        # Footer: feedback link
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_halign(Gtk.Align.END)
        feedback_btn = Gtk.Button(label="Feedback Form")
        feedback_btn.add_css_class("flat")
        feedback_btn.connect("clicked", lambda b: open_url(FEEDBACK_FORM_URL))
        footer.append(feedback_btn)
        right.append(footer)

        paned.set_end_child(right)

    @staticmethod
    def _section_label(text):
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        lbl.add_css_class("heading")
        return lbl

    # ----------------------------------------------------------- Data list

    def _read_default_language(self) -> str:
        toml = self.project_dir / "corpus.toml"
        if not toml.exists():
            return self.cfg.default_language
        try:
            for line in toml.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*language\s*=\s*[\"']([^\"']+)[\"']", line)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return self.cfg.default_language

    def refresh_recordings(self):
        # Clear current
        child = self.recordings_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.recordings_list.remove(child)
            child = nxt

        wavs = sorted(
            p for p in self.data_dir.glob("*.wav")
            if p.is_file() and not p.name.startswith(".")
        )
        for wav in wavs:
            annotated = (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
            row = self._make_recording_row(wav, annotated)
            self.recordings_list.append(row)

        if not wavs:
            placeholder = Gtk.Label(label="\nNo recordings yet.\n\nUse Import Audio or ● Record to add one.\n")
            placeholder.add_css_class("dim-label")
            placeholder.set_wrap(True)
            row = Gtk.ListBoxRow()
            row.set_child(placeholder)
            row.set_selectable(False)
            self.recordings_list.append(row)

    def _make_recording_row(self, wav: Path, annotated: bool) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.wav_path = wav  # attach path to row for selection callback
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        status_icon = "✓" if annotated else "○"
        icon_lbl = Gtk.Label(label=status_icon)
        icon_lbl.add_css_class("success" if annotated else "dim-label")
        box.append(icon_lbl)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_lbl = Gtk.Label(label=wav.name)
        name_lbl.set_halign(Gtk.Align.START)
        info_box.append(name_lbl)
        status_lbl = Gtk.Label(label="Annotated" if annotated else "Not yet annotated")
        status_lbl.set_halign(Gtk.Align.START)
        status_lbl.add_css_class("dim-label")
        info_box.append(status_lbl)
        box.append(info_box)
        row.set_child(box)
        return row

    def _on_row_selected(self, listbox, row):
        if row is None or not hasattr(row, "wav_path"):
            self.selected_wav = None
            self.selected_label.set_label("No recording selected")
            self.run_btn.set_sensitive(False)
            self.praat_btn.set_sensitive(False)
            self.folder_btn.set_sensitive(False)
            self.zip_btn.set_sensitive(False)
            return
        wav = row.wav_path
        self.selected_wav = wav
        self.selected_label.set_label(wav.name)
        self.run_btn.set_sensitive(True)
        annotated = (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
        self.praat_btn.set_sensitive(annotated)
        self.folder_btn.set_sensitive(annotated)
        self.zip_btn.set_sensitive(annotated)

    # ---------------------------------------------------------- Import audio

    def _on_import(self, btn):
        dlg = Gtk.FileChooserDialog(
            title="Import audio file",
            action=Gtk.FileChooserAction.OPEN,
            transient_for=self,
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                        "_Import", Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Audio files")
        for ext in ("wav", "mp3", "flac", "ogg", "m4a", "aac", "opus"):
            f.add_pattern(f"*.{ext}")
            f.add_pattern(f"*.{ext.upper()}")
        dlg.add_filter(f)
        dlg.connect("response", self._on_import_response)
        dlg.present()

    def _on_import_response(self, dlg, response):
        if response == Gtk.ResponseType.OK:
            gfile = dlg.get_file()
            if gfile:
                src = Path(gfile.get_path())
                self._import_audio_file(src)
        dlg.close()

    def _import_audio_file(self, src: Path):
        """Copy or convert the imported file into data/ as 16 kHz mono WAV."""
        if not src.exists():
            self._error("Source file not found")
            return

        target_name = _safe_filename(src.stem) + ".wav"
        target = self.data_dir / target_name
        if target.exists():
            target = self.data_dir / f"{src.stem}_{_next_recording_name(self.data_dir).split('_')[-1]}"

        if src.suffix.lower() == ".wav":
            try:
                shutil.copy2(src, target)
                self._info(f"Imported {target.name}")
                self.refresh_recordings()
                return
            except Exception as e:
                self._error(f"Import failed: {e}")
                return

        # Non-wav → use ffmpeg to convert
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._error("Imported file is not WAV and ffmpeg isn't available to convert.")
            return

        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(target)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._info(f"Imported and converted {target.name}")
            self.refresh_recordings()
        except subprocess.CalledProcessError as e:
            self._error(f"ffmpeg conversion failed:\n{e.stderr.decode()[:400]}")

    # --------------------------------------------------------- Record audio

    def _on_record_toggle(self, btn):
        if self.recorder.proc is None:
            # Start
            name = _next_recording_name(self.data_dir)
            target = self.data_dir / name
            ok, err = self.recorder.start(target)
            if not ok:
                self._error(f"Recording failed: {err}")
                return
            btn.set_label("■ Stop")
            self.record_status.set_label(f"Recording → {name}")
            self.recorder_tick_source = GLib.timeout_add(500, self._tick_record_status)
        else:
            # Stop
            ok, msg = self.recorder.stop()
            btn.set_label("● Record")
            if self.recorder_tick_source:
                GLib.source_remove(self.recorder_tick_source)
                self.recorder_tick_source = None
            self.record_status.set_label(f"Saved {self.recorder.out_path.name if self.recorder.out_path else ''}")
            self.refresh_recordings()

    def _tick_record_status(self):
        if self.recorder.proc is None:
            return False
        sec = int(self.recorder.elapsed())
        self.record_status.set_label(
            f"Recording → {self.recorder.out_path.name if self.recorder.out_path else ''}  ({sec}s)"
        )
        return True

    # ------------------------------------------------------- Run pipeline

    def _on_run_annotation(self, btn):
        if not self.selected_wav:
            return

        # Show annotation wizard — let user configure source, language, trackers
        wizard = AnnotationWizard(self.get_root())
        wizard.connect("response", self._on_wizard_response)
        wizard.show()

    def _on_wizard_response(self, wizard, response_id):
        from gi.repository import Gtk as _Gtk
        if response_id != _Gtk.ResponseType.OK:
            wizard.destroy()
            return

        result = wizard.result
        wizard.destroy()

        if result.cancelled:
            return

        # Reset progress state
        for lbl in self.stage_labels:
            text = lbl.get_label()
            text = re.sub(r"^\s*[●✓○]\s*", "  ○  ", text)
            lbl.set_label(text)
            lbl.add_css_class("dim-label")
            lbl.remove_css_class("success")

        self.status_line.set_label("Starting…")
        self.run_btn.set_sensitive(False)
        self.cancel_btn.set_sensitive(True)
        self.log_view.get_buffer().set_text("")

        lang = result.language
        trackers = result.trackers or ["pyin"]

        self._append_log(f"Pipeline configuration:")
        self._append_log(f"  Source: {'human annotation' if result.has_annotation else 'automatic ASR'}")
        if result.has_annotation and result.textgrid_path:
            self._append_log(f"  TextGrid: {result.textgrid_path.name}  (suffix: {result.tier_suffix})")
        self._append_log(f"  Language: {lang}")
        self._append_log(f"  Trackers: {', '.join(trackers)}")
        self._append_log(f"  Comparison mode: {result.comparison_mode}")
        self._append_log("")

        self.runner = PipelineRunner(
            on_stage=self._on_pipeline_stage,
            on_line=self._append_log,
            on_done=self._on_pipeline_done,
        )
        self.runner.run(self.selected_wav, lang, self.out_dir)

    def _on_cancel_pipeline(self, btn):
        if self.runner:
            self.runner.cancel()
            self.status_line.set_label("Cancelling…")

    def _on_pipeline_stage(self, num, total, name):
        # Mark current stage as running, previous as done
        for i, lbl in enumerate(self.stage_labels, 1):
            text = lbl.get_label()
            # Strip the leading marker
            stripped = re.sub(r"^\s*[●✓○]\s*\d+\.\s*", "", text)
            stage_name = stripped
            if i < num:
                marker = "✓"
                lbl.add_css_class("success")
                lbl.remove_css_class("dim-label")
            elif i == num:
                marker = "●"
                lbl.remove_css_class("dim-label")
                lbl.remove_css_class("success")
            else:
                marker = "○"
            lbl.set_label(f"  {marker}  {i}. {stage_name}")
        self.status_line.set_label(f"Step {num} of {total}: {name}")

    def _append_log(self, text):
        buf = self.log_view.get_buffer()
        buf.insert(buf.get_end_iter(), text + "\n")
        # Auto-scroll
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0.0, False, 0.0, 0.0)

    def _on_pipeline_done(self, rc, out_dir):
        self.run_btn.set_sensitive(True)
        self.cancel_btn.set_sensitive(False)
        if rc == 0 and out_dir:
            # Mark all stages done
            for i, lbl in enumerate(self.stage_labels, 1):
                text = lbl.get_label()
                stripped = re.sub(r"^\s*[●✓○]\s*\d+\.\s*", "", text)
                lbl.set_label(f"  ✓  {i}. {stripped}")
                lbl.add_css_class("success")
                lbl.remove_css_class("dim-label")
            self.status_line.set_label("✓ Annotation complete")
            self._success_dialog(out_dir)
            self.refresh_recordings()
            # Reselect the current row to refresh action buttons
            self._reselect_current()
        else:
            self.status_line.set_label(f"✗ Pipeline exited with code {rc}")

    def _reselect_current(self):
        if not self.selected_wav:
            return
        idx = 0
        child = self.recordings_list.get_first_child()
        while child:
            if getattr(child, "wav_path", None) == self.selected_wav:
                self.recordings_list.select_row(child)
                return
            child = child.get_next_sibling()
            idx += 1

    def _success_dialog(self, out_dir: Path):
        dlg = Gtk.AlertDialog(
            message="Annotation complete",
            detail=(
                f"Created in {out_dir.name}/:\n"
                f"  ✓ Praat TextGrid (6 tiers)\n"
                f"  ✓ Words, syllables, phonemes\n"
                f"  ✓ Prosody summary\n"
                f"  ✓ CSV exports\n"
            ),
        )
        dlg.set_buttons(["Open in Praat", "Open Folder", "Export ZIP", "Close"])
        dlg.set_default_button(0)
        dlg.set_cancel_button(3)
        dlg.choose(self, None, self._on_success_choice, out_dir)

    def _on_success_choice(self, dialog, result, out_dir):
        try:
            choice = dialog.choose_finish(result)
        except Exception:
            return
        wav = out_dir / f"{out_dir.name}.wav"
        if not wav.exists():
            wav = self.selected_wav
        textgrid = out_dir / f"{out_dir.name}.TextGrid"
        if choice == 0:
            ok, err = open_in_praat(wav, textgrid)
            if not ok:
                self._error(err)
        elif choice == 1:
            ok, err = open_folder(out_dir)
            if not ok:
                self._error(err)
        elif choice == 2:
            self._export_zip(out_dir)

    # ------------------------------------------------------- Open / Export

    def _on_open_in_praat(self, btn):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        textgrid = out_dir / f"{self.selected_wav.stem}.TextGrid"
        wav_for_praat = out_dir / f"{self.selected_wav.stem}.wav"
        if not wav_for_praat.exists():
            wav_for_praat = self.selected_wav
        ok, err = open_in_praat(wav_for_praat, textgrid)
        if not ok:
            self._error(err)

    def _on_open_folder(self, btn):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        if not out_dir.exists():
            out_dir = self.project_dir
        ok, err = open_folder(out_dir)
        if not ok:
            self._error(err)

    def _on_export_zip(self, btn):
        if not self.selected_wav:
            return
        out_dir = self.out_dir / self.selected_wav.stem
        if not out_dir.exists():
            self._error("Run annotation first to create an output folder to zip.")
            return
        self._export_zip(out_dir)

    def _export_zip(self, out_dir: Path):
        try:
            cmd = [sys.executable, "-m", "speechprint_pkg.cli", "export-zip", str(out_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                zip_path = out_dir.parent / f"{out_dir.name}.zip"
                self._info(f"Exported {zip_path.name}")
                open_folder(zip_path.parent)
            else:
                self._error(f"Export failed:\n{result.stderr or result.stdout}")
        except Exception as e:
            self._error(f"Export error: {e}")

    # ---------------------------------------------------------- Notifications

    def _info(self, message):
        self.status_line.set_label(message)

    def _error(self, message):
        dlg = Gtk.AlertDialog(message="SpeechPrint", detail=str(message))
        dlg.choose(self, None, lambda d, r, u: d.choose_finish(r), None)
