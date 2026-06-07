QUESTIONNAIRE OUTPUT — 2026-06-02
==================================================

This folder contains SpeechPrint v3 TextGrids for:

  english/
    audio_2026-05-30_19-01-35.TextGrid  — English minimal pairs recording
    audio_2026-05-30_19-01-35.wav

  german_gtobi/
    eine_gelbe_banane.TextGrid          — Tiers: Wort (human) + Ton (GToBI annotation)
    einige_melonen.TextGrid             —        + syllables (IPA) + phonemes (IPA)
    er_sang_die_lieder.TextGrid         —        + f0_vowel (onset|offset Hz  amp dB)
    er_will_die_rosen_haben.TextGrid    —        + prosody (/ \ * - _ symbols)
    ich_wohne_in_bern.TextGrid

  doreco/
    doreco_port1286_2017_06_30_Jaklin.TextGrid
    doreco_port1286_2017_06_30_Jaklin.wav

PITCH TRACKING (v3 improvements over v2):
  PRIMARY  : Librosa pYIN — probabilistic YIN, returns voiced/unvoiced confidence,
             more robust against octave errors than Praat SCC
  FALLBACK : Praat to_pitch_ac() with octave_jump_cost=0.5
  CORRECTION: Xu (1999) / ProsodyPro octave-spike removal:
             - median of voiced frames computed
             - frames >10 ST from median: try F0/2 and F0*2
             - keep whichever is closest to median
             - triangular smoothing (1:2:1) over 3 consecutive voiced frames
  RANGE    : speaker-adaptive floor/ceiling from 20-second scan (pYIN)

PROSODY SYMBOLS (v3):
  /    rising intra-syllable pitch (onset→offset > threshold)
  //   strongly rising (very large excursion)
  \   falling
  \\  strongly falling
  -    high level relative to neighbours
  _    low level relative to neighbours
  *    prominent accent (louder AND higher/longer)
  ?    unvoiced (no pitch data)
  Combinations: */ *\ *- *_ */ *// etc.

SYMBOLIC LAYER (v3 improvements):
  - Neighbour window: ±2 syllables (was ±1)
  - Recording-level median F0 as secondary height reference
  - Accent fires when louder AND (higher OR longer) — catches "flew"-type accents
  - Strong rise/fall: requires both large magnitude AND high velocity
  - All syllable labels are IPA (no orthographic fallback)
