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

    def run(self, wav: Path, language: str, output_dir: Path,
            aligner: str = "whisperx", compare: bool = False):
        """Kick off the pipeline subprocess."""
        cmd = [
            sys.executable, "-m", "speechprint_pkg.cli",
            "annotate", str(wav),
            "--language", language,
            "--output", str(output_dir),
            "--aligner", aligner,
        ]
        if compare:
            cmd.append("--compare-aligners")
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



def _finalize_recorded_wav(path: Path) -> Path:
    """Rewrite recorded WAV to clean 16k mono PCM so Parselmouth/Praat do not warn."""
    try:
        import shutil, subprocess
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg or not path.exists():
            return path
        tmp = path.with_suffix(".fixed.wav")
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-i", str(path),
             "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(tmp)],
            check=True,
        )
        if tmp.exists() and tmp.stat().st_size > 1000:
            tmp.replace(path)
    except Exception:
        pass
    return path


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
        out_path.parent.mkdir(parents=True, exist_ok=True)

        arecord = self._which("arecord")
        ffmpeg = self._which("ffmpeg")

        if arecord:
            cmd = [
                arecord,
                "-q",
                "-f", "S16_LE",
                "-r", "16000",
                "-c", "1",
                str(out_path),
            ]
        elif ffmpeg:
            cmd = [
                ffmpeg,
                "-y",
                "-f", "pulse",
                "-i", "default",
                "-ac", "1",
                "-ar", "16000",
                str(out_path),
            ]
        else:
            return False, "Install alsa-utils or ffmpeg."

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.started_at = time.time()
            return True, ""
        except Exception as e:
            self.proc = None
            return False, str(e)


    def stop(self) -> tuple[bool, str]:
        if self.proc is None:
            return False, "Not recording"

        try:
            # arecord finalizes WAV headers correctly on SIGINT.
            import signal
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

        self.proc = None
        return True, ""


        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass

        self.proc = None
        return True, ""


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

        # Aligner picker — additive, same row pattern
        lang_box.append(Gtk.Label(label="   Aligner:"))
        self.aligner_combo = Gtk.DropDown()
        self._aligner_codes = ["whisperx", "mfa", "gentle", "crisperwhisper"]
        self._aligner_labels = {
            "whisperx": "WhisperX (wav2vec2)",
            "mfa": "MFA (Kaldi, phone-level)",
            "gentle": "Gentle (Kaldi, English)",
            "crisperwhisper": "CrisperWhisper (DTW)",
        }
        self.aligner_combo.set_model(Gtk.StringList.new(
            [self._aligner_labels[c] for c in self._aligner_codes]
        ))
        self.aligner_combo.set_selected(0)
        self.aligner_combo.set_tooltip_text(
            "Forced aligner used for the primary 6-tier TextGrid. "
            "Tick 'Compare aligners' to also run the others side by side."
        )
        lang_box.append(self.aligner_combo)
        right.append(lang_box)

        # Compare-aligners toggle + aligner status label
        compare_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.compare_check = Gtk.CheckButton(
            label="Compare aligners (run all available, write per-aligner TextGrids + comparison CSV)"
        )
        self.compare_check.set_active(False)
        compare_box.append(self.compare_check)
        right.append(compare_box)

        self.aligner_status_label = Gtk.Label(label="")
        self.aligner_status_label.set_halign(Gtk.Align.START)
        self.aligner_status_label.add_css_class("dim-label")
        self.aligner_status_label.set_wrap(True)

        right.append(self.aligner_status_label)

        # Multi-aligner selection checkboxes
        self.aligner_checks = {}

        checks_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4
        )

        checks_label = Gtk.Label(label="Alignment layers")
        checks_label.set_halign(Gtk.Align.START)
        checks_box.append(checks_label)

        for _code in self._aligner_codes:

            cb = Gtk.CheckButton(
                label=self._aligner_labels.get(_code, _code)
            )

            if _code == "whisperx":
                cb.set_active(True)

            checks_box.append(cb)
            self.aligner_checks[_code] = cb

        right.append(checks_box)

        # Probe in the background so we don't slow window open
        threading.Thread(target=self._refresh_aligner_status,
                         daemon=True).start()

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

        self.compare_open_btn = Gtk.Button(label="Open Comparison")
        self.compare_open_btn.set_tooltip_text(
            "Open the aligners/comparison.csv produced by 'Compare aligners'."
        )
        self.compare_open_btn.connect("clicked", self._on_open_comparison)
        self.compare_open_btn.set_sensitive(False)
        open_box.append(self.compare_open_btn)
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
        child = self.recordings_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.recordings_list.remove(child)
            child = nxt

        wavs = sorted(self.data_dir.glob("*.wav"))

        first = None
        for wav in wavs:
            annotated = (
                (self.out_dir / wav.stem / f"{wav.stem}.master_emet.TextGrid").exists()
                or (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
            )
            row = self._make_recording_row(wav, annotated)
            self.recordings_list.append(row)
            if first is None:
                first = row

        if first is not None:
            self.recordings_list.select_row(first)
        else:
            row = Gtk.ListBoxRow()
            label = Gtk.Label()
            label.set_use_markup(True)
            label.set_markup("<span foreground='#111111'>No recordings yet. Use Import Audio or Record to add one.</span>")
            label.set_xalign(0)
            label.set_margin_top(16)
            label.set_margin_bottom(16)
            label.set_margin_start(16)
            label.set_margin_end(16)
            row.set_child(label)
            self.recordings_list.append(row)


    def _make_recording_row(self, wav: Path, annotated: bool) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.wav_path = wav

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(14)
        box.set_margin_end(14)

        title = Gtk.Label()
        title.set_use_markup(True)
        title.set_markup(f"<span foreground='#111111' weight='bold'>{wav.name}</span>")
        title.set_xalign(0)
        box.append(title)

        status = "Annotated" if annotated else "Not yet annotated"
        sub = Gtk.Label()
        sub.set_use_markup(True)
        sub.set_markup(f"<span foreground='#333333'>{status}</span>")
        sub.set_xalign(0)
        box.append(sub)

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
            self.compare_open_btn.set_sensitive(False)
            return
        wav = row.wav_path
        self.selected_wav = wav
        self.selected_label.set_label(wav.name)
        self.run_btn.set_sensitive(True)
        annotated = (self.out_dir / wav.stem / f"{wav.stem}.TextGrid").exists()
        self.praat_btn.set_sensitive(annotated)
        self.folder_btn.set_sensitive(annotated)
        self.zip_btn.set_sensitive(annotated)
        comparison = self.out_dir / wav.stem / "aligners" / "comparison.csv"
        self.compare_open_btn.set_sensitive(comparison.exists())

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
            name = _next_recording_name(self.data_dir)
            target = self.data_dir / name
            ok, err = self.recorder.start(target)
            if not ok:
                self._error(f"Recording failed: {err}")
                return
            btn.set_label("■ Stop")
            self.record_status.set_label(f"Recording → {name}")
            self.recorder_tick_source = GLib.timeout_add(500, self._tick_record_status)
            return

        ok, msg = self.recorder.stop()
        btn.set_label("● Record")

        if self.recorder_tick_source:
            GLib.source_remove(self.recorder_tick_source)
            self.recorder_tick_source = None

        saved = self.recorder.out_path
        if saved:
                _finalize_recorded_wav(saved)
        self.record_status.set_label(f"Saved {saved.name if saved else ''}")

        # Force GTK list rebuild after the file is flushed to disk.
        def finish_refresh():
            if saved and saved.exists():
                # Remove placeholder rows without wav_path.
                child = self.recordings_list.get_first_child()
                while child:
                    nxt = child.get_next_sibling()
                    if not hasattr(child, "wav_path"):
                        self.recordings_list.remove(child)
                    child = nxt

                # Avoid duplicate row if refresh already added it.
                found = None
                child = self.recordings_list.get_first_child()
                while child:
                    if getattr(child, "wav_path", None) == saved:
                        found = child
                        break
                    child = child.get_next_sibling()

                if found is None:
                    row = self._make_recording_row(saved, False)
                    self.recordings_list.append(row)
                    found = row

                self.recordings_list.select_row(found)
                self._on_row_selected(self.recordings_list, found)
            else:
                self.refresh_recordings()

            return False

        GLib.timeout_add(250, finish_refresh)


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
        # Reset progress state
        for lbl in self.stage_labels:
            text = lbl.get_label()
            # Reset to "○" prefix
            text = re.sub(r"^\s*[●✓○]\s*", "  ○  ", text)
            lbl.set_label(text)
            lbl.add_css_class("dim-label")
            lbl.remove_css_class("success")

        self.status_line.set_label("Starting…")
        self.run_btn.set_sensitive(False)
        self.cancel_btn.set_sensitive(True)
        # Clear log
        self.log_view.get_buffer().set_text("")

        idx = self.lang_combo.get_selected()
        lang = self._lang_codes[idx] if 0 <= idx < len(self._lang_codes) else self.default_language

        aidx = self.aligner_combo.get_selected()
        aligner = self._aligner_codes[aidx] if 0 <= aidx < len(self._aligner_codes) else "whisperx"
        compare = self.compare_check.get_active()

        self.runner = PipelineRunner(
            on_stage=self._on_pipeline_stage,
            on_line=self._append_log,
            on_done=self._on_pipeline_done,
        )
        self.runner.run(self.selected_wav, lang, self.out_dir,
                        aligner=aligner, compare=compare)

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
            # Compare-open button reflects whether the run produced a CSV
            if self.selected_wav:
                csv_path = (self.out_dir / self.selected_wav.stem
                            / "aligners" / "comparison.csv")
                self.compare_open_btn.set_sensitive(csv_path.exists())
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

    # ---------------------------------------------------- Aligner helpers

    def _refresh_aligner_status(self):
        """Worker: probe aligner availability via `speechprint_pkg.cli aligners`
        and update the dim label on the right side. Runs on a background thread
        because the probe imports whisperx/transformers which can take a couple
        of seconds.
        """
        try:
            cmd = [sys.executable, "-m", "speechprint_pkg.cli", "aligners"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                rep = json.loads(result.stdout.split("\n\n")[0])
            else:
                rep = {}
        except Exception:
            rep = {}

        if not rep:
            text = "Aligner status: (probe failed — pipeline will still run)"
        else:
            parts = []
            for name in ["whisperx", "mfa", "gentle", "crisperwhisper"]:
                entry = rep.get(name, {})
                mark = "✓" if entry.get("installed") else "○"
                parts.append(f"{mark} {name}")
            text = "Aligners detected: " + "   ".join(parts)

        GLib.idle_add(self.aligner_status_label.set_label, text)

    def _on_open_comparison(self, btn):
        if not self.selected_wav:
            return
        csv_path = (self.out_dir / self.selected_wav.stem
                    / "aligners" / "comparison.csv")
        if not csv_path.exists():
            self._error(
                "No comparison CSV yet.\n\n"
                "Tick 'Compare aligners' before clicking Run Annotation to "
                "produce one."
            )
            return
        opener = shutil.which("xdg-open") or shutil.which("open")
        if not opener:
            self._error(f"No xdg-open/open available. CSV is at:\n{csv_path}")
            return
        try:
            subprocess.Popen([opener, str(csv_path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._error(str(e))

    # ---------------------------------------------------------- Notifications


    def _return_to_launcher(self, project_name=None):
        try:
            if hasattr(self, "stack"):
                self.stack.set_visible_child_name("launcher")

            if hasattr(self, "refresh_projects"):
                self.refresh_projects()

            if project_name and hasattr(self, "select_project"):
                self.select_project(project_name)

        except Exception as exc:
            print(f"[SpeechPrint] launcher return failed: {exc}")

    def _info(self, message):
        self.status_line.set_label(message)

    def _error(self, message):
        dlg = Gtk.AlertDialog(message="SpeechPrint", detail=str(message))
        dlg.choose(self, None, lambda d, r, u: d.choose_finish(r), None)
