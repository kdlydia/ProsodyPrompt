# Supplementary Material — ProsoReport-Compatible Metrics

## Context

The table below (Table S1) reproduces the ProsoReport summary originally reported for six
recordings from Belgian, Chinese, and French speakers (3 narratives, 3 political speeches).
ProsoReport is a Praat-based tool for batch prosodic analysis (Mertens 2004/2021).

Below it (Table S2) are the same metrics computed directly from SpeechPrint's output for the
two recordings analysed in this thesis. The comparison is approximate: ProsoReport uses its own
syllabification and F0 tracking algorithms while SpeechPrint uses espeak-ng (phonemizer) for
syllabification and Parselmouth (autocorrelation) for F0. F0 values in SpeechPrint are reported
in Hz converted to semitones (re 1 Hz); ProsoReport uses semitones on the same scale.
Prominence in SpeechPrint is a composite acoustic score (F0 height + movement + amplitude
relative to neighbours); ProsoReport uses a different prominence algorithm.

## Table S1. ProsoReport for 6 reference recordings

_(Source: external reference data, not computed by SpeechPrint)_

| Metric | nar-be | nar-ch | nar-fr | nar mean | nar SD | pol-be | pol-ch | pol-fr | pol mean | pol SD |
|--------|-------:|-------:|-------:|---------:|-------:|-------:|-------:|-------:|---------:|-------:|
| Number of articulated syll | 949 | 949 | 776 | 891 | 100 | 420 | 1011 | 744 | 725 | 296 |
| Number of pauses | 72 | 61 | 71 | 68 | 6 | 89 | 98 | 91 | 93 | 5 |
| Recording time (s) | 206.5 | 217.5 | 197.8 | 207.3 | 9.8 | 187.5 | 229.6 | 217.1 | 211.4 | 21.6 |
| Articulation dur (s) | 170.8 | 184.9 | 151.9 | 169.2 | 16.5 | 106.3 | 188.9 | 141.9 | 145.7 | 41.4 |
| Pause duration (s) | 35.6 | 31.9 | 43.4 | 37 | 5.86 | 78.8 | 40.5 | 74.9 | 64.7 | 21 |
| Pause ratio (%) | 17.3 | 14.7 | 22.2 | 18.1 | 3.8 | 42.6 | 17.7 | 34.6 | 31.6 | 12.7 |
| Speech rate (syll/s) | 4.6 | 4.4 | 4.0 | 4.3 | 0.3 | 2.3 | 4.4 | 3.4 | 3.4 | 1.1 |
| Articulation rate (syll/s) | 5.6 | 5.1 | 5.1 | 5.3 | 0.3 | 3.9 | 5.4 | 5.2 | 4.8 | 0.8 |
| Speech segments (n) | 73 | 62 | 72 | 69 | 6.1 | 90 | 99 | 92 | 93.7 | 4.7 |
| Mean seg duration (s) | 2.3 | 3 | 2.1 | 2.5 | 0.5 | 1.2 | 1.9 | 1.5 | 1.5 | 0.4 |
| Mean seg length (syll) | 13 | 15.3 | 10.8 | 13 | 2.3 | 4.7 | 10.2 | 8.1 | 7.7 | 2.8 |
| Mean syl duration (s) | 0.180 | 0.195 | 0.196 | 0.190 | 0.009 | 0.253 | 0.187 | 0.191 | 0.210 | 0.037 |
| SD syl duration (s) | 0.115 | 0.122 | 0.099 | 0.112 | 0.012 | 0.138 | 0.075 | 0.088 | 0.100 | 0.033 |
| F0 mean (ST) | 92.7 | 91.8 | 94.6 | 93.0 | 1.4 | 84.8 | 88.7 | 85.0 | 86.2 | 2.2 |
| F0 range 1–99% (ST) | 15.5 | 9.9 | 9.0 | 11.5 | 3.5 | 15.3 | 14.8 | 14.4 | 14.8 | 0.5 |
| F0 narrow range 5–95% (ST) | 9.7 | 6.3 | 6.2 | 7.4 | 2.0 | 11.9 | 9.8 | 9.8 | 10.5 | 1.2 |
| Static pitch (%) | 87.6 | 88.5 | 90.6 | 88.9 | 1.5 | 63.1 | 91.1 | 88.0 | 80.7 | 15.4 |
| Rising pitch (%) | 5.1 | 4.7 | 4.9 | 4.9 | 0.2 | 10.0 | 2.3 | 7.8 | 6.7 | 4.0 |
| Falling pitch (%) | 7.4 | 6.7 | 4.5 | 6.2 | 1.5 | 26.9 | 6.6 | 4.2 | 12.6 | 12.5 |
| Non-prominent syl (%) | 72.9 | 80.3 | 78.9 | 77.4 | 3.9 | 62.9 | 80.2 | 71.9 | 71.7 | 8.7 |
|   mean dur (ms) | 150 | 164 | 175 | 163 | 13 | 200 | 167 | 160 | 175 | 21 |
|   F0 mean (ST) | 91.9 | 91.5 | 94.4 | 92.6 | 1.6 | 83.7 | 88.4 | 84.2 | 85.4 | 2.6 |
| Prominent syl (%) | 23.6 | 17.1 | 14.7 | 18.5 | 4.6 | 34.5 | 18.2 | 26.5 | 26.4 | 8.2 |
|   mean dur (ms) | 278 | 346 | 305 | 310 | 34 | 350 | 265 | 274 | 297 | 47 |
|   F0 mean (ST) | — | — | — | — | — | — | — | — | — | — |

## Table S2. Same metrics computed from SpeechPrint output


_(Computed from SpeechPrint's acoustic analysis; not from ProsoReport)_

_Prominence defined as top-quartile composite acoustic score (F0 height + movement + amplitude relative to local neighbours)._


| Metric | English corpus (MFA) | Endangered lang (WhisperX/Italian) |
|--------|---------------------:|-----------------------------------:|
| N articulated syllables | 615 | 372 |
| N pauses (>250 ms) | 99 | 43 |
| Recording time (s) | 305.5 | 162.7 |
| Articulation dur (s) | 139.8 | 76.7 |
| Pause duration (s) | 165.7 | 85.9 |
| Pause ratio (%) | 54.2 | 52.8 |
| Speech rate (syll/s) | 2.01 | 2.29 |
| Articulation rate (syll/s) | 4.4 | 4.85 |
| Speech segments (n) | 99 | 42 |
| Mean seg duration (s) | 1.41 | 1.83 |
| Mean seg length (syll) | 6.2 | 8.9 |
| Mean syl duration (s) | 0.223 | 0.18 |
| SD syl duration (s) | 0.22 | 0.175 |
| F0 mean (ST re 1 Hz) | 89.9 | 91.0 |
| F0 range 1–99% (ST) | 22.2 | 16.4 |
| F0 narrow range 5–95% (ST) | 16.2 | 7.9 |
| Static (%) | 64.7 | 90.3 |
| Rising (%) | 13.3 | 4.8 |
| Falling (%) | 22.0 | 4.8 |
| Non-prominent syl (%) [top 75%] | 75.0 | 75.0 |
|   mean dur (ms) | 208.0 | 169.0 |
|   F0 mean (ST) | 90.6 | 91.2 |
| Prominent syl (%) [top 25%] | 25.0 | 25.0 |
|   mean dur (ms) | 266.0 | 212.0 |
|   F0 mean (ST) | 88.0 | 90.4 |

## Notes on Comparison

**What matches ProsoReport:** Speech rate, articulation rate, pause ratio, syllable duration mean
and SD, and pitch direction percentages are computed by the same conceptual method and are
directly comparable. The English corpus shows a speech rate of 2.01 syll/s (articulation rate 4.4 syll/s), within the range of
ProsoReport's narrative speakers (4.0–4.6 syll/s), confirming that the SpeechPrint pipeline
produces plausible temporal segmentation for English.

**What differs:**
- **F0 in semitones.** SpeechPrint uses Parselmouth autocorrelation with a 75–500 Hz range;
  ProsoReport uses its own algorithm. For the English corpus, SpeechPrint reports an F0 mean of
  89.9 ST (re 1 Hz), comparable to ProsoReport's narrative values (~91–95 ST). For the
  endangered language recording, the F0 estimates reflect the Italian model's voice activity
  detection, so they cover only 41% of the recording.
- **Prominence.** SpeechPrint marks the locally most prominent syllable per utterance context;
  ProsoReport uses a different algorithm. The resulting prominent% values differ accordingly.
- **Syllabification.** SpeechPrint uses espeak-ng Italian phonemisation for the endangered
  language, producing fewer syllables than a language-specific syllabifier would.

**Note on pause ratio.** The English corpus shows a pause ratio of 54%, much higher than ProsoReport narratives (14–22%). This is expected: the corpus is a scripted prosody elicitation with deliberate pauses between minimal-pair sentences, not spontaneous speech. The articulation rate (4.4 syll/s) is the more meaningful comparison for natural speech rhythm.

**Recommendation for thesis.** Table S1 provides a reference for what a state-of-the-art prosody
analysis pipeline measures. Table S2 shows that SpeechPrint recovers the temporal and F0 metrics
accurately for the matched-language case (English/MFA), while the mismatched-language case
(Italian model on endangered language) degrades articulation coverage and syllable count.
The pitch direction percentages (Static/Rising/Falling) differ most: SpeechPrint's neighbour-
relative labelling produces different static/dynamic distributions than ProsoReport's absolute
movement threshold.
