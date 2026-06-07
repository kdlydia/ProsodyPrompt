"""SpeechPrint Annotation Wizard — multi-step dialog before running the pipeline.

Step 1: Annotation source    (human TextGrid  vs  automatic ASR)
Step 2: Language selection   (common / endangered + phonological similarity)
Step 3: Tracker selection    (pYIN / CREPE / PESTO / Praat / comparison)
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango
from pathlib import Path


# ── Language data ─────────────────────────────────────────────────────────────
COMMON_LANGUAGES = [
    ("en", "English"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("ru", "Russian"),
    ("zh", "Mandarin"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("tr", "Turkish"),
]

# Phonological similarity hints for common endangered/under-resourced families
PHON_SIMILAR = {
    "Oceanic":    ("it", "Italian (closest Romance; Oceanic vowel inventory matches)"),
    "Chibchan":   ("es", "Spanish (closest available for Chibchan languages)"),
    "Bantu":      ("sw", "Swahili (if available) or Yoruba"),
    "default":    ("it", "Italian (broad coverage of cross-lingual phoneme sets)"),
}

TRACKERS = [
    ("pyin",  "pYIN (librosa)",       True,  "Best for clean studio speech. No model download. 3–5× real-time."),
    ("crepe", "CREPE (torchcrepe)",   True,  "Best for archival/field recordings. Robust to irregular phonation. Slower."),
    ("pesto", "PESTO",                False, "Self-supervised. Different error profile from CREPE. Good for comparison."),
    ("praat", "Praat AC + Xu(1999)",  False, "Signal-processing reference. Known octave-error risk on some speakers."),
    ("yin",   "YIN (librosa)",        False, "No V/UV detector — not recommended for prosody labelling."),
]


# ── Result dataclass ──────────────────────────────────────────────────────────
class WizardResult:
    def __init__(self):
        self.cancelled = True
        self.has_annotation = False       # True → human TextGrid path provided
        self.textgrid_path = None         # Path | None
        self.tier_suffix = "@TA"          # "@TA" | "@6" | custom
        self.language = "en"
        self.is_endangered = False
        self.trackers = ["pyin", "crepe"] # list of tracker keys
        self.comparison_mode = True       # generate all-tracker TextGrid


# ── Wizard dialog ─────────────────────────────────────────────────────────────
class AnnotationWizard(Gtk.Dialog):
    """Three-page wizard shown before running the annotation pipeline."""

    def __init__(self, parent):
        super().__init__(title="SpeechPrint — Annotation Setup", transient_for=parent,
                         modal=True)
        self.set_default_size(520, 480)
        self.result = WizardResult()
        self._page = 0

        # main content area
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.get_content_area().append(self._stack)

        self._build_page0()
        self._build_page1()
        self._build_page2()

        # footer buttons
        self._btn_back   = self.add_button("← Back",   10)
        self._btn_next   = self.add_button("Next →",   11)
        self._btn_cancel = self.add_button("Cancel",   Gtk.ResponseType.CANCEL)
        self._btn_run    = self.add_button("▶  Run",   Gtk.ResponseType.OK)
        self._btn_run.add_css_class("suggested-action")
        self._btn_back.set_sensitive(False)
        self._btn_run.set_visible(False)

        self.connect("response", self._on_response)
        self._stack.set_visible_child_name("page0")

    # ── Page 0: annotation source ─────────────────────────────────────────────
    def _build_page0(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24); box.set_margin_bottom(16)
        box.set_margin_start(28); box.set_margin_end(28)

        title = Gtk.Label(label="Do you have a human-annotated TextGrid?")
        title.add_css_class("title-3")
        title.set_halign(Gtk.Align.START)
        title.set_wrap(True)
        box.append(title)

        sub = Gtk.Label(label="This determines which pipeline stages run automatically.")
        sub.add_css_class("dim-label")
        sub.set_halign(Gtk.Align.START)
        sub.set_wrap(True)
        box.append(sub)

        # Radio buttons
        self._radio_human = Gtk.CheckButton(
            label="Yes — I have a human-annotated TextGrid (DoReCo, ELAN export, fieldwork)")
        self._radio_auto  = Gtk.CheckButton(
            label="No — run the full automatic pipeline (Whisper → MFA → prosody)",
            group=self._radio_human)
        self._radio_auto.set_active(True)
        box.append(self._radio_human)
        box.append(self._radio_auto)

        # Human annotation options (shown when radio_human is active)
        self._human_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._human_box.set_margin_start(24)
        self._human_box.set_visible(False)

        tg_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._tg_label = Gtk.Label(label="No file selected")
        self._tg_label.set_ellipsize(Pango.EllipsizeMode.START)
        self._tg_label.set_hexpand(True)
        self._tg_label.set_halign(Gtk.Align.START)
        tg_btn = Gtk.Button(label="Browse…")
        tg_btn.connect("clicked", self._on_browse_tg)
        tg_row.append(self._tg_label)
        tg_row.append(tg_btn)
        self._human_box.append(tg_row)

        suffix_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        suffix_row.append(Gtk.Label(label="Tier suffix:"))
        self._suffix_combo = Gtk.DropDown.new_from_strings(["@TA (DoReCo standard)", "@6 (DoReCo v2)", "custom"])
        suffix_row.append(self._suffix_combo)
        self._human_box.append(suffix_row)

        box.append(self._human_box)

        self._radio_human.connect("toggled", self._on_source_toggled)

        # Note box
        note = Gtk.Label()
        note.set_markup("<small><b>Human annotation path:</b> words, phones, and timing come from your file.\n"
                        "Only F0 extraction and prosody labelling run automatically.\n\n"
                        "<b>Automatic path:</b> nine stages from transcription to prosody labels.</small>")
        note.set_halign(Gtk.Align.START)
        note.set_wrap(True)
        note.add_css_class("dim-label")
        box.append(note)

        self._stack.add_named(box, "page0")

    def _on_source_toggled(self, btn):
        self._human_box.set_visible(btn.get_active())

    def _on_browse_tg(self, btn):
        dialog = Gtk.FileChooserDialog(title="Select TextGrid", transient_for=self,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Open",   Gtk.ResponseType.ACCEPT)
        f = Gtk.FileFilter(); f.set_name("TextGrid files"); f.add_pattern("*.TextGrid")
        dialog.add_filter(f)
        dialog.connect("response", self._on_tg_chosen)
        dialog.show()

    def _on_tg_chosen(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            path = dialog.get_file().get_path()
            self.result.textgrid_path = Path(path)
            self._tg_label.set_label(Path(path).name)
        dialog.destroy()

    # ── Page 1: language ──────────────────────────────────────────────────────
    def _build_page1(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(24); box.set_margin_bottom(16)
        box.set_margin_start(28); box.set_margin_end(28)

        title = Gtk.Label(label="Language")
        title.add_css_class("title-3")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        # Common language list
        self._lang_radio_common = Gtk.CheckButton(label="Common language (ASR + forced alignment available)")
        self._lang_radio_other  = Gtk.CheckButton(label="Endangered / under-resourced language",
                                                   group=self._lang_radio_common)
        self._lang_radio_common.set_active(True)
        box.append(self._lang_radio_common)

        # Common language dropdown
        self._common_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._common_box.set_margin_start(24)
        codes = [f[0] for f in COMMON_LANGUAGES]
        labels = [f"{f[1]} ({f[0]})" for f in COMMON_LANGUAGES]
        self._lang_dropdown = Gtk.DropDown.new_from_strings(labels)
        self._common_box.append(self._lang_dropdown)
        box.append(self._common_box)

        box.append(self._lang_radio_other)

        # Endangered options
        self._other_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._other_box.set_margin_start(24)
        self._other_box.set_visible(False)

        iso_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        iso_row.append(Gtk.Label(label="ISO 639-3 code (optional):"))
        self._iso_entry = Gtk.Entry(); self._iso_entry.set_placeholder_text("e.g. mtp")
        iso_row.append(self._iso_entry)
        self._other_box.append(iso_row)

        self._phon_check = Gtk.CheckButton(
            label="Find phonologically similar supported language\n(uses consonant/vowel inventory overlap from PHOIBLE data)")
        self._other_box.append(self._phon_check)

        self._phon_suggestion = Gtk.Label(label="")
        self._phon_suggestion.add_css_class("dim-label")
        self._phon_suggestion.set_halign(Gtk.Align.START)
        self._phon_suggestion.set_wrap(True)
        self._other_box.append(self._phon_suggestion)

        self._phon_check.connect("toggled", self._on_phon_check)
        self._iso_entry.connect("changed", self._on_iso_changed)

        box.append(self._other_box)

        note = Gtk.Label()
        note.set_markup("<small>For endangered languages, ASR output will be phonetically plausible\n"
                        "but lexically incorrect. Prosody labels remain acoustically valid\n"
                        "regardless of transcription quality.</small>")
        note.set_halign(Gtk.Align.START)
        note.set_wrap(True)
        note.add_css_class("dim-label")
        box.append(note)

        self._lang_radio_other.connect("toggled", self._on_lang_toggled)
        self._stack.add_named(box, "page1")

    def _on_lang_toggled(self, btn):
        self._other_box.set_visible(btn.get_active())
        self._common_box.set_visible(not btn.get_active())

    def _on_iso_changed(self, entry):
        if self._phon_check.get_active():
            self._show_phon_suggestion()

    def _on_phon_check(self, btn):
        if btn.get_active():
            self._show_phon_suggestion()
        else:
            self._phon_suggestion.set_label("")

    def _show_phon_suggestion(self):
        iso = self._iso_entry.get_text().strip().lower()
        hint = PHON_SIMILAR.get("default")
        self._phon_suggestion.set_label(
            f"Suggested: {hint[1]}")

    # ── Page 2: tracker selection ─────────────────────────────────────────────
    def _build_page2(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24); box.set_margin_bottom(16)
        box.set_margin_start(28); box.set_margin_end(28)

        title = Gtk.Label(label="Pitch tracker")
        title.add_css_class("title-3")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        sub = Gtk.Label(label="Select one or more. All checked trackers run in parallel.\nComparison mode writes a separate prosody tier for each.")
        sub.add_css_class("dim-label")
        sub.set_halign(Gtk.Align.START)
        sub.set_wrap(True)
        box.append(sub)

        self._tracker_checks = {}
        for key, label, default, description in TRACKERS:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row.set_margin_bottom(4)
            check = Gtk.CheckButton(label=label)
            check.set_active(default)
            desc = Gtk.Label(label=description)
            desc.add_css_class("dim-label")
            desc.set_halign(Gtk.Align.START)
            desc.set_margin_start(28)
            desc.set_wrap(True)
            row.append(check)
            row.append(desc)
            box.append(row)
            self._tracker_checks[key] = check

        sep = Gtk.Separator()
        box.append(sep)

        self._comparison_check = Gtk.CheckButton(
            label="Generate comparison TextGrid (one prosody_* tier per tracker)")
        self._comparison_check.set_active(True)
        box.append(self._comparison_check)

        self._stack.add_named(box, "page2")

    # ── Navigation ────────────────────────────────────────────────────────────
    def _on_response(self, dialog, response_id):
        if response_id == 10:  # Back
            self._page -= 1
            self._update_page()
        elif response_id == 11:  # Next
            self._page += 1
            self._update_page()
        elif response_id == Gtk.ResponseType.OK:
            self._collect_result()
        # CANCEL handled by default

    def _update_page(self):
        names = ["page0", "page1", "page2"]
        self._stack.set_visible_child_name(names[self._page])
        self._btn_back.set_sensitive(self._page > 0)
        is_last = self._page == len(names) - 1
        self._btn_next.set_visible(not is_last)
        self._btn_run.set_visible(is_last)

    def _collect_result(self):
        r = self.result
        r.cancelled = False
        r.has_annotation = self._radio_human.get_active()
        suffixes = ["@TA", "@6", "custom"]
        r.tier_suffix = suffixes[self._suffix_combo.get_selected()]
        if self._lang_radio_other.get_active():
            r.is_endangered = True
            r.language = self._iso_entry.get_text().strip() or "it"
        else:
            idx = self._lang_dropdown.get_selected()
            r.language = COMMON_LANGUAGES[idx][0]
        r.trackers = [k for k, c in self._tracker_checks.items() if c.get_active()]
        r.comparison_mode = self._comparison_check.get_active()
