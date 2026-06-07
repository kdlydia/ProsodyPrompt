# Appendix A — Phoneme Tier Comparison: Human vs. Automatic (DoReCo Endangered Language Recording)

## A.1 Recording and Annotation Details

| Property | Value |
|----------|-------|
| File | `doreco_port1286_2017_06_30_Jaklin.wav` |
| Duration | 162.7 s |
| Language | European Portuguese (DoReCo corpus) |
| ASR model applied | Italian (`it`) — WhisperX `small` + `wav2vec2_voxpopuli_base_10k_asr_it` |
| Phoneme source | espeak-ng Italian backend via `phonemizer` |

## A.2 Comparison Table

| Metric | Human `h_ph@TA` | Automatic `phonemes` |
|--------|----------------|----------------------|
| Total phoneme intervals | 1065 | 790 |
| Pause/silence intervals | 89 | implicit in word gaps |
| Recording coverage | 62% (101 s) | 41% (67 s) |
| Mean phone duration | 95 ms | 85 ms |
| Distinct IPA symbols | 33 | 36 |
| Symbols shared (after SAMPA→IPA remap) | 24 | 24 |
| Temporal overlap of phone spans | 55% of human duration | — |
| Boundary-matched pairs (±30 ms) | 168 / 1065 (16%) | — |
| Correct symbol at matched boundary | 13 / 168 (8%) | — |

## A.3 IPA Inventory Comparison

The human annotation uses a SAMPA-like extended IPA notation (capitals for vowels: `E`=ɛ, `O`=ɔ; `_w` suffix for labialized consonants).
After remapping to standard IPA, the inventories share 24 symbols.

**Symbols shared:** `a`, `aː`, `b`, `d`, `eː`, `i`, `iː`, `j`, `k`, `l`, `m`, `n`, `o`, `p`, `r`, `s`, `t`, `ts`, `u`, `v`, `ŋ`, `ɔ`, `ɛ`, `ɛː`

**Human-only symbols** (language-specific features absent from Italian espeak-ng):

| Symbol | IPA equiv. | Count | Linguistic feature |
|--------|-----------|-------|--------------------|
| `mʷ` | mʷ | 30 | mʷ |
| `h` | h | 25 | h — pharyngeal fricative |
| `pʷ` | pʷ | 11 | pʷ |
| `ɔː` | ɔː | 8 | ɔː |
| `g` | g | 6 | g — voiced velar stop |
| `ɸ` | ɸ | 6 | ɸ |
| `æ` | æ | 5 | æ |

**Automatic-only symbols** (Italian-model artefacts not in human annotation):

| Symbol | Count | Likely source |
|--------|-------|---------------|
| `e` | 84 | Italian /e/ — distinguished from open /ɛ/, merged in human annotation |
| `ɲ` | 18 | Italian palatal nasal — common in Italian, rare in this language |
| `z` | 11 | Italian /z/ — voiced sibilant |
| `ss` | 9 | Geminate /ss/ — Italian gemination, not present in target language |
| `tʃ` | 9 | Italian /tʃ/ affricate — common in Italian |
| `ʃ` | 7 | Italian voiceless palato-alveolar — Italian-specific |
| `ʎ` | 7 | Italian palatal lateral — Italian-specific |
| `ʊ` | 5 | Italian phoneme inventory artefact |

## A.4 Interpretation

The comparison reveals a three-layer mismatch between the human and automatic phoneme tiers:

**1. Coverage mismatch (62% vs 41%).** The human annotation covers the full recording including
inter-utterance pauses explicitly labelled as `<p:>`. The automatic tier spans only the 41% of
the recording where WhisperX detected speech activity. The 21-percentage-point gap reflects both
genuine silences (correctly excluded by the ASR voice-activity detector) and portions of speech
where the Italian ASR model failed to segment or assign tokens.

**2. Inventory mismatch (33 vs 36 symbols, 24 shared after remapping).** The human annotation
captures language-specific segments absent from the Italian model's output: labialized consonants
(`mʷ`, `pʷ`, `bʷ`) that are phonemic in the documented language, the voiceless bilabial fricative
`ɸ`, and pharyngeal `h`. Conversely, the Italian model introduces Italian-specific segments
(`ɲ`, `ʎ`, `ʃ`, geminates `ss`) that do not occur in the target language. The 16 symbols exclusive
to the Italian model are systematic artefacts of applying a mismatched phoneme inventory.

**3. Boundary mismatch (15.8% matched within ±30 ms).** Only 168 of the 1065 human phone boundaries
align within 30 ms with an automatic boundary, and of those only 7% carry the same IPA symbol.
This is a near-chance-level agreement, confirming that the automatic segmentation is not a usable
approximation of the human phoneme tier for this language. The 55% temporal overlap of phone spans
is higher because the automatic phones are longer on average (85 ms vs 95 ms human), creating
broad spans that happen to overlap human spans without sharing boundaries.

**Conclusion.** For an endangered language without a trained ASR model, the automatic phoneme tier
cannot substitute for hand annotation. It can still serve as a time-stamped scaffold — providing
approximate positions of syllable nuclei and enabling the prosody layer (F0, amplitude) which is
acoustic rather than linguistic. The phoneme labels themselves should be treated as Italian
interpretations of the speech signal and corrected manually.

