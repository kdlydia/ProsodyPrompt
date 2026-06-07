SpeechPrint — Questionnaire Demo Files
========================================
Open each WAV + TextGrid pair together in Praat:
  drag both files onto Praat → select both in Objects → "View & Edit"


FOLDERS
-------

german_gtobi/
  Five GToBI-annotated German sentences.
  Each sentence has THREE TextGrid versions (pick the best for your demo):

  _v_human.TextGrid  ★ RECOMMENDED for questionnaire
    Tiers: Wort | Ton | syllables | phonemes | f0_pitch | prosody
    Word timing comes from the hand-annotated Wort tier.
    Syllables, phonemes, and prosody are computed from those human boundaries.
    Shows the GToBI annotation (Ton) directly above the SpeechPrint prosody layer.
    Safe to use for ALL sentences.

  _v_full.TextGrid   (comparison view)
    Tiers: Wort | Ton | words_SP | syllables_SP | phonemes_SP | f0_pitch_SP | prosody_SP
    Shows the original GToBI tiers PLUS the full SpeechPrint WhisperX output.
    Good for demonstrating what WhisperX transcribes vs what humans annotated.

  _v_both.TextGrid   (best-of-both)
    Tiers: Wort | Ton | [words_SP] | syllables | phonemes | f0_pitch | prosody
    WhisperX words tier included only when it closely matches the human annotation.
    Prosody/syllables computed from human word boundaries.


  WHISPER vs HUMAN SIMILARITY PER SENTENCE:
  ┌──────────────────────────────┬──────────────────────────────────────────────────┐
  │ Sentence                     │ WhisperX transcription           │ Similarity    │
  ├──────────────────────────────┼──────────────────────────────────┼───────────────┤
  │ er_will_die_rosen_haben      │ "er will die rosen haben" ✓✓     │ 100% PERFECT  │
  │ ich_wohne_in_bern            │ "ich wohne in bern" ✓✓           │ 100% PERFECT  │
  │ eine_gelbe_banane            │ "eine gerbe banana" (≈close)     │ 67% fuzzy     │
  │ einige_melonen               │ "einigen mal lohnt" ✗            │ DIFFERENT     │
  │ er_sang_die_lieder           │ "hesangli lieder" ✗              │ DIFFERENT     │
  └──────────────────────────────┴──────────────────────────────────┴───────────────┘

  → For the two PERFECT matches (er_will/ich_wohne): use _v_both to show
    "whisper got it exactly right AND the prosody analysis matches GToBI"
  → For the DIFFERENT cases (einige_melonen, er_sang_die_lieder): use _v_human
    because whisper got the words wrong; human boundaries give accurate prosody
  → _v_human is always safe for all five sentences


  PROSODY SYMBOLS (in the prosody tier of all TextGrids):
    /    weakly rising pitch          (onset→offset > ~0.5–1 ST)
    //   strongly rising              (> 2.5× adaptive threshold)
    \    weakly falling
    \\   strongly falling
    --   level (no significant movement)
    *    most prominent syllable (stands out in F0 + amplitude)


  GToBI ANNOTATIONS (in the Ton tier):
    L+H*   rising nuclear accent (pitch rises to the accented syllable)
    H+L*   falling nuclear accent (high onset, low on the nucleus)
    H+!H*  downstepped high nuclear accent
    L*+H   low nuclear accent with trailing high tone
    L-%    low boundary tone (utterance ends low)


english/
  Your own voice, English prosody minimal-pair corpus.
  One WAV + one TextGrid (SpeechPrint WhisperX output, v2).
  6 tiers: words / syllables / phonemes / f0_pitch / prosody_labels / warnings_review
  No human annotation available — this IS the SpeechPrint output.


SUGGESTED QUESTIONNAIRE DEMO SEQUENCE
--------------------------------------
1. Open ich_wohne_in_bern_v_both.TextGrid + WAV
   → Show: whisper got all 4 words right, prosody shows L*+H rising correctly

2. Open er_will_die_rosen_haben_v_both.TextGrid + WAV
   → Show: 5/5 words correct, L*+H hat pattern visible (// then *\\)

3. Open eine_gelbe_banane_v_human.TextGrid + WAV
   → Show: L+H* rising captured (// on pre-nuclear, *\\ on peak)

4. Open er_sang_die_lieder_v_human.TextGrid + WAV
   → Show: H+!H* falling, successive \\ on Lieder syllables

5. Open audio_2026-05-30_19-01-35.TextGrid + WAV (English)
   → Show: statement vs question pair, focus movement, lexical stress shifts
