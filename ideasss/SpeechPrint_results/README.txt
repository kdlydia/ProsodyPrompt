SpeechPrint Results — for Praat
================================
Open each .wav + .TextGrid pair together in Praat (drag both files onto Praat,
select both in the Objects window, then click "View & Edit").

Prosody symbols used in all TextGrids:
  /    weakly rising pitch
  //   strongly rising pitch
  \    weakly falling pitch
  \\   strongly falling pitch
  --   level (no significant movement)
  *    prominent syllable (stands out from neighbours in F0 + amplitude)

Symbols are relative to immediate neighbours (adaptive thresholds, floor 0.5 ST).


FOLDERS
-------

english/
  One WAV + one TextGrid. Your own voice, English prosody minimal-pair corpus
  (82 sentences, 21 categories: contrastive stress, focus, statement vs. question,
  lexical stress, etc.). Alignment: WhisperX English. 6 tiers:
    words / syllables / phonemes / f0_pitch / prosody_labels / warnings_review

german_gtobi/
  Five GToBI-annotated German training sentences. Each has:
    <name>.wav              — the original recording
    <name>_MERGED.TextGrid  — 7 tiers:
      Wort         : original hand-annotated word boundaries (GToBI corpus)
      Ton          : original GToBI nuclear tone + boundary tone annotations
                     (e.g. L+H* L-%, H+L* L-%, L*+H)
      sp_words     : SpeechPrint WhisperX transcription + word timing
      sp_syllables : SpeechPrint syllable segmentation (IPA-derived)
      sp_phonemes  : SpeechPrint IPA phones
      sp_f0_pitch  : mean F0 per syllable in Hz
      sp_prosody   : prosody symbols (/ // \ \\ -- *)

  Sentences and their GToBI annotations:
    eine_gelbe_banane       L+H*  L-%   (rising nuclear accent)
    einige_melonen          H+L*  L-%   (falling nuclear accent)
    er_sang_die_lieder      H+!H* L-%   (downstepped high, falling)
    er_will_die_rosen_haben L*+H        (low nuclear, rising)
    ich_wohne_in_bern       L*+H  L-%   (low nuclear, rising, with boundary)

endangered_daakie/
  The Daakie (Vanuatu / DoReCo corpus) recording. One WAV, two TextGrids:
    *_ITALIAN.TextGrid  — analysed with the Italian language model (--language it)
    *_SPANISH.TextGrid  — analysed with the Spanish language model (--language es)

  Both TextGrids have the same 6 tiers (words / syllables / phonemes /
  f0_pitch / prosody_labels / warnings_review). The prosody layer is
  acoustically valid for both; the phoneme/word tiers reflect Italian or
  Spanish phonology respectively (no Daakie ASR model exists).

  Key difference: Spanish detects more speech (918 syllables vs 572 for Italian)
  but also more false-positive word boundaries. Italian produces a cleaner,
  less fragmented transcription for this recording.
