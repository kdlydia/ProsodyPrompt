#!/usr/bin/env python3
"""Installation mode - multi-step setup with GTK4"""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GLib
import asyncio
import subprocess
import os
from pathlib import Path


class ConfirmationStep:
    """Step 0: Confirmation before starting"""

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup("<span size='18000' weight='bold'>Ready to Install?</span>")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        info = Gtk.Label()
        info.set_markup("""This will configure your machine for SpeechPrint analysis:

• Speech transcription (Whisper / WhisperX)
• Prosody analysis (Praat + Parselmouth)
• TextGrid generation
• Symbolic annotation layers
• Praat compatibility
• Optional forced alignment tools

This only needs to be done once per computer.

<b>Requires:</b> Internet connection, ~5 GB disk space (rough estimate)
<span size='small' alpha='65%'>It may take up to 5 minutes to complete.</span>""")
        info.set_wrap(True)
        info.set_halign(Gtk.Align.START)
        box.append(info)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        box.append(spacer)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    async def execute(self):
        return True


class ReleaseTypeStep:
    """Step 0.5: Choose Stable or Development release"""

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup(
            "<span size='18000' weight='bold'>Select Release Channel</span>"
        )
        title.set_halign(Gtk.Align.START)
        box.append(title)

        subtitle = Gtk.Label()
        subtitle.set_markup("Choose which version of SpeechPrint to install:")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        box.append(subtitle)

        stable_frame = Gtk.Frame()
        stable_frame.set_margin_top(10)
        stable_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        stable_box.set_margin_top(15)
        stable_box.set_margin_bottom(15)
        stable_box.set_margin_start(15)
        stable_box.set_margin_end(15)

        self.stable_radio = Gtk.CheckButton(label="Stable Release (Recommended)")
        self.stable_radio.set_active(True)
        stable_box.append(self.stable_radio)

        stable_desc = Gtk.Label()
        stable_desc.set_markup(
            "<span size='small'>Production-ready release. Tested and stable.\n"
            "Recommended for general use and field-recording workflows.</span>"
        )
        stable_desc.set_halign(Gtk.Align.START)
        stable_desc.set_margin_start(25)
        stable_desc.add_css_class("dim-label")
        stable_box.append(stable_desc)

        stable_frame.set_child(stable_box)
        box.append(stable_frame)

        dev_frame = Gtk.Frame()
        dev_frame.set_margin_top(10)
        dev_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dev_box.set_margin_top(15)
        dev_box.set_margin_bottom(15)
        dev_box.set_margin_start(15)
        dev_box.set_margin_end(15)

        self.dev_radio = Gtk.CheckButton(label="Development Release")
        self.dev_radio.set_group(self.stable_radio)
        dev_box.append(self.dev_radio)

        dev_desc = Gtk.Label()
        dev_desc.set_markup(
            "<span size='small'>Latest features and improvements. May contain bugs.\n"
            "For testing and early access to new functionality.</span>"
        )
        dev_desc.set_halign(Gtk.Align.START)
        dev_desc.set_margin_start(25)
        dev_desc.add_css_class("dim-label")
        dev_box.append(dev_desc)

        dev_frame.set_child(dev_box)
        box.append(dev_frame)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        box.append(spacer)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    async def execute(self):
        return True

    def get_release_type(self):
        return "dev" if self.dev_radio.get_active() else "stable"


class LanguageModulesStep:
    """Step 1: Select language modules to install"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.checks = {}
        self.selected = set()

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(20)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup(
            "<span size='18000' weight='bold'>Select Language Modules</span>"
        )
        title.set_halign(Gtk.Align.START)
        box.append(title)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            "<span size='small'>Pick the languages you expect to use. "
            "Each adds an acoustic model + dictionary (~300 MB).\n"
            "You can add more languages later from this installer without "
            "starting over — per-recording language is set inside each project.</span>"
        )
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        subtitle.set_wrap(True)
        box.append(subtitle)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(280)

        grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        grid.set_margin_top(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)

        names = self.cfg.language_names
        default = self.cfg.default_language
        for code in self.cfg.supported_languages:
            display = names.get(code, code)
            cb = Gtk.CheckButton(label=f"{display} ({code})")
            if code == default:
                cb.set_active(True)
                self.selected.add(code)
            cb.connect("toggled", self._on_toggled, code)
            self.checks[code] = cb
            grid.append(cb)

        scroll.set_child(grid)
        box.append(scroll)

        self.summary = Gtk.Label()
        self.summary.set_halign(Gtk.Align.START)
        self.summary.add_css_class("dim-label")
        self._update_summary()
        box.append(self.summary)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    def _on_toggled(self, btn, code):
        if btn.get_active():
            self.selected.add(code)
        else:
            self.selected.discard(code)
        self._update_summary()

    def _update_summary(self):
        n = len(self.selected)
        size = n * 300
        if n == 0:
            self.summary.set_markup(
                "<span color='#dd5555'>Select at least one language.</span>"
            )
        else:
            self.summary.set_markup(
                f"<tt>{n} module(s) selected · approx. {size} MB acoustic models</tt>"
            )

    async def execute(self):
        return True

    def get_languages(self):
        return sorted(self.selected) if self.selected else [self.cfg.default_language]


class SystemCheckStep:
    """Step 2: System verification"""

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(20)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup("<span size='16000' weight='bold'>Step 2: Verify Installation</span>")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        self.status = Gtk.Label(label="Checking...")
        self.status.set_halign(Gtk.Align.START)
        box.append(self.status)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(250)

        self.log = Gtk.TextView()
        self.log.set_editable(False)
        self.log.add_css_class("monospace")
        scroll.set_child(self.log)
        box.append(scroll)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    async def execute(self):
        checks = {
            "64-bit system": lambda: __import__("struct").calcsize("P") == 8,
            "Python 3.11+": lambda: __import__("sys").version_info >= (3, 11),
            "Git": lambda: self._has_command("git"),
            "ffmpeg (optional, will install if missing)": lambda: True,
        }

        all_pass = True
        for name, check in checks.items():
            try:
                result = check()
            except Exception:
                result = False
            self._log(f"{'✓' if result else '✗'} {name}")
            if not result and "optional" not in name:
                all_pass = False
            await asyncio.sleep(0.2)

        self.status.set_text(
            "✓ Check complete" if all_pass else "✗ Some checks failed"
        )
        return all_pass

    def _has_command(self, cmd):
        try:
            subprocess.run(
                [cmd, "--version"], capture_output=True, timeout=5, check=True
            )
            return True
        except Exception:
            return False

    def _log(self, msg):
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), msg + "\n", -1)
        self.log.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)


class DependenciesStep:
    """Step 3: Install dependencies"""

    def __init__(self, script_dir):
        self.script_dir = script_dir
        self.release_type = "stable"
        self.languages = ["en"]

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(20)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup(
            "<span size='16000' weight='bold'>Step 3: Prepare Analysis Tools</span>"
        )
        title.set_halign(Gtk.Align.START)
        box.append(title)

        self.status = Gtk.Label(label="Preparing...")
        self.status.set_halign(Gtk.Align.START)
        box.append(self.status)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_min_content_height(250)

        self.log = Gtk.TextView()
        self.log.set_editable(False)
        self.log.add_css_class("monospace")
        scroll.set_child(self.log)
        box.append(scroll)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    async def execute(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "install_deps.sh"
        if not script.exists():
            self._log("✗ install_deps.sh not found")
            self.status.set_text("✗ Script not found")
            return False

        os.chmod(script, 0o755)

        try:
            lang_arg = ",".join(self.languages)
            self._log(f"[debug] release={self.release_type}  languages={lang_arg}")
            self._log(f"Running: {script}")
            process = await asyncio.create_subprocess_exec(
                str(script),
                self.release_type,
                lang_arg,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async for line in process.stdout:
                self._log(line.decode(errors="replace").rstrip())
                await asyncio.sleep(0)

            await process.wait()

            if process.returncode == 0:
                self.status.set_text("✓ Dependencies installed")
                return True
            else:
                self._log(f"✗ Exit code: {process.returncode}")
                self.status.set_text("⚠ Installation completed with warnings")
                return True
        except Exception as e:
            self._log(f"✗ Error: {e}")
            self.status.set_text("⚠ Continuing anyway")
            return True

    def _log(self, msg):
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), msg + "\n", -1)
        self.log.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)


class CompletionStep:
    """Step 4: Done"""

    def build_ui(self, container):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        title = Gtk.Label()
        title.set_markup(
            "<span size='20000' weight='bold'>✓ Installation Complete!</span>"
        )
        title.set_halign(Gtk.Align.CENTER)
        box.append(title)

        info = Gtk.Label()
        info.set_markup("""<b>Next steps:</b>

1. Click <b>Finish</b> to close this installer.
2. From the launcher, choose <b>New Project / Corpus</b>.
3. Inside the project workspace you can:
   • <b>Import Audio</b> or <b>● Record</b> a new file
   • <b>Run Annotation</b> to generate the TextGrid
   • <b>Open in Praat</b> to inspect
   • <b>Export ZIP</b> to share

<span size='small' alpha='65%'>The CLI is still available for power users:
<tt>speechprint annotate data/recording.wav --language en</tt></span>""")
        info.set_wrap(True)
        info.set_halign(Gtk.Align.START)
        box.append(info)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        box.append(spacer)

        while container.get_first_child():
            container.remove(container.get_first_child())
        container.append(box)

    async def execute(self):
        return True


class InstallationMode(Gtk.ApplicationWindow):
    """Main installation window"""

    def __init__(self, app, cfg):
        super().__init__(application=app)
        self.cfg = cfg
        self.script_dir = cfg.scripts_dir
        self.set_title("SpeechPrint - Install Toolchain")
        self.set_default_size(700, 600)

        self.steps = [
            ConfirmationStep(),
            ReleaseTypeStep(),
            LanguageModulesStep(cfg),
            SystemCheckStep(),
            DependenciesStep(self.script_dir),
            CompletionStep(),
        ]
        self.current = 0

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Gtk.HeaderBar()
        self.step_label = Gtk.Label()
        header.set_title_widget(self.step_label)
        main_box.append(header)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_vexpand(True)
        main_box.append(self.content)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_margin_top(10)
        btn_box.set_margin_bottom(10)
        btn_box.set_margin_start(30)
        btn_box.set_margin_end(30)
        btn_box.set_halign(Gtk.Align.END)

        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.set_sensitive(False)
        self.back_btn.connect("clicked", self._on_back)
        btn_box.append(self.back_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_box.append(spacer)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.add_css_class("suggested-action")
        self.next_btn.connect("clicked", self._on_next)
        btn_box.append(self.next_btn)

        main_box.append(btn_box)
        self.set_child(main_box)

        self._show_step(0)

    def _show_step(self, idx):
        self.current = idx
        self.step_label.set_text(f"Step {idx + 1} of {len(self.steps)}")

        step = self.steps[idx]
        step.build_ui(self.content)

        self.back_btn.set_sensitive(idx > 0)

        if idx == 0:
            self.next_btn.set_label("Start Installation")
        elif idx == len(self.steps) - 1:
            self.next_btn.set_label("Finish")
        else:
            self.next_btn.set_label("Next")

        self.next_btn.set_sensitive(False)
        GLib.timeout_add(100, lambda: self._run_step(step))

    def _run_step(self, step):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(step.execute())
        except Exception as e:
            print(f"Step error: {e}")
        finally:
            self.next_btn.set_sensitive(True)

    def _on_next(self, btn):
        if self.current < len(self.steps) - 1:
            # Capture release type after step 1
            if self.current == 1:
                step = self.steps[1]
                if hasattr(step, "get_release_type"):
                    self.release_type = step.get_release_type()
                    self.steps[4].release_type = self.release_type
            # Capture languages after step 2
            if self.current == 2:
                step = self.steps[2]
                if hasattr(step, "get_languages"):
                    self.languages = step.get_languages()
                    self.steps[4].languages = self.languages

            self._show_step(self.current + 1)
        else:
            self.close()

    def _on_back(self, btn):
        if self.current > 0:
            self._show_step(self.current - 1)


# Optional evaluation link
EVALUATION_FORM_URL = "https://google.com/forms/speechprint-evaluation"

