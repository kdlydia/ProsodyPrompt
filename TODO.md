# SpeechPrint / ProsodyPrompt — Master Todo

Organised by the urgent/important matrix.
Do Quadrant 1 first. Schedule Quadrant 2. Quadrant 3 when inspired.

---

## Quadrant 1: Urgent + Important (thesis deadline + class deadline)

### Thesis — submit by end of June / defense July 2026

- [ ] **Send questionnaire to linguists.**
  Files are in `FINAL_QUESTIONNAIRE_2026-06-07/`. Send your father the folder path
  so he can select which English pairs and language examples to include.
  Collect responses before the defense.

- [ ] **Replace Overleaf files with updated local versions.**
  Only two files differ from what is on GitHub:
  `discussion/discussion.tex` and `abstract/abstract.tex`.
  methods, results, appendix are already correct in Overleaf.

- [ ] **Abstract: paste hybrid version.**
  The final version is written and ready (from earlier session).
  Copy it into Overleaf `abstract/abstract.tex`, replacing the old second abstract.

- [ ] **Compile and check PDF.**
  Run full LaTeX build. Verify: no undefined citations, no missing figures,
  page count under 100. The Figures/ directory needs the pitch comparison PNG files
  referenced in results.tex — confirm they are present.

- [ ] **Fix PESTO shape mismatch on Cabécar.**
  PESTO failed with `operands could not be broadcast together with shapes (8182,384) (8182,)`.
  Likely a context-window edge case. Pad the audio to a round number of frames before
  calling `pesto.predict()` and retry.

- [ ] **Remove GitHub contributors lydia2k and sainish.**
  Settings → Collaborators → Remove. Cannot be done from terminal.

---

### Sound Communication class — 1 week deadline

**Core idea:** generative speech instrument. Leap Motion navigates a latent articulatory
space. Hand position = prosodic state. Pink Trombone speaks it.

Not training from scratch. Feature-mapping task using pretrained embeddings.

#### Necessary (the project cannot exist without these)

- [ ] **Python: WhisperX word timestamps.**
  Run `whisperx your_sentence.wav --language en` on a short reference sentence.
  Output: JSON with start/end time for every word.
  This creates the scaffold — you need to know *when* each word happens
  so gestures hit the right moment.
  ```bash
  python -c "
  import whisperx, json
  model = whisperx.load_model('large-v3', device='cpu')
  audio = whisperx.load_audio('sentence.wav')
  result = model.transcribe(audio, language='en')
  print(json.dumps(result['segments'], indent=2))
  "
  ```

- [ ] **Python: CREPE vowel embeddings (the "vowel print").**
  Load a small set of vowel recordings (a, e, i, o, u + a few diphthongs).
  Pass each through torchcrepe. Extract the activation of the fifth max-pooling layer
  (before the final linear layer). This 256-dim vector = the vowel's signature in
  pitch-embedding space. Reduce to 2D with PCA or UMAP for visualisation.
  The resulting 2D map is your latent vowel space.
  ```python
  import torchcrepe, torch, librosa
  # torchcrepe internal layers: use torchcrepe.load.model() and hook on layer 4
  ```

- [ ] **Max/MSP: OSC bridge from Python.**
  Install `python-osc` (`pip install python-osc`).
  Python sends: `/f0 [float]`, `/tongue_x [float]`, `/tongue_y [float]` via UDP.
  Max receives with `udpreceive 8000` → `route /f0 /tongue_x /tongue_y`.
  Test with a fixed pitch value before connecting Leap Motion.

- [ ] **Leap Motion: hand height → Pink Trombone frequency.**
  This is the minimum viable demo. Hand Y coordinate (0–300 mm) maps linearly
  to frequency in semitones (e.g., 60 ST to 90 ST = 261 Hz to 1047 Hz).
  Use logarithmic mapping so small hand movements at the bottom feel natural.
  The Leap Motion SDK provides `hand.palm.position.y` in mm.
  Python script → OSC → Max → Pink Trombone `frequency` inlet.
  If this works and sounds good, the class project is defensible.

- [ ] **Max: connect OSC F0 to Pink Trombone vocal fold tension.**
  Pink Trombone's main pitch control is `tenseness` (0–1) and `frequency` (Hz).
  In the zakaton web version, these are exposed as message inputs.
  In a Max port, they map to the glottis parameters.
  Start with frequency only. Add tenseness only after frequency works.

- [ ] **Demo sentence for presentation.**
  Pick one sentence that shows the difference clearly.
  "Mary flew to Milan" is ideal: hand gesture on MARY raises pitch sharply,
  on MILAN it rises again, on YESTERDAY the sentence falls.
  Rehearse this gesture sequence so it looks intentional.

#### Nice to have (adds depth, not required for pass)

- [ ] **Wekinator: train 5 gestures to 5 prosodic states.**
  Wekinator receives Leap Motion XYZ → outputs 2D latent coordinate.
  The 5 states (from GToBI):
  neutral fall / question rise / contrastive peak / sustained level / creaky low.
  Train by holding each gesture position for 5 seconds and pressing record.
  Output drives Pink Trombone via OSC.

- [ ] **Two-hand prosody morphing.**
  Left hand = Vox Prima state (e.g., English question intonation).
  Right hand = Vox Secunda state (e.g., Mandarin level-tone intonation).
  Horizontal distance between hands = blend ratio.
  Python interpolates between the two embedding vectors, sends blended
  articulatory parameters to Pink Trombone.
  This is the Spectralist interpolation idea made physical.

- [ ] **Hum to control (AirPods alternative to Leap Motion).**
  AirPods mic → pYIN real-time F0 extraction → Pink Trombone frequency.
  You hum a melody, the synthesiser speaks it.
  Very small to implement: `sounddevice` stream → librosa pYIN frame-by-frame.
  ```python
  import sounddevice as sd, librosa, numpy as np
  # stream callback: extract single-frame pYIN estimate, send via OSC
  ```

- [ ] **Prosodic typography caption layer.**
  Display the WhisperX words on a web canvas or Max `lcd` object.
  Font size or vertical position of each word scales with current F0.
  High pitch = word floats higher / gets larger.
  One `route` in Max + a `mathdiv` to normalise the Hz range.
  Direct visual demonstration of "prosody as typography" without any extra hardware.

- [ ] **SampleBrain / Neu-Grains exploration.**
  SampleBrain (corpus-based granular): load a set of vowel recordings as corpus.
  Hand position navigates between them using nearest-neighbour search.
  https://thentrythis.org/projects/samplebrain/
  Neu-Grains Max patch: https://neutone.ai/m4l/neu-grains
  Paper: https://arxiv.org/pdf/2507.19202
  Test on English vowel recordings from the minimal pairs corpus.

- [ ] **Latent Granular with speech sounds.**
  https://huggingface.co/spaces/naotokui/latentgranular
  Upload vowel/consonant WAV files. Explore the latent space in the browser.
  Screenshot / record the traversal as documentation for the class writeup.

- [ ] **Signal flow diagram (like Lawrence's Figure 3.1).**
  Hand-drawn or simple TikZ/LaTeX:
  `Leap Motion XYZ → Python (CREPE embedding lookup) → OSC → Max
  → Pink Trombone (frequency, tenseness, tongue) → Audio out → Caption display`
  Include this in the class writeup / thesis appendix.

---

## Quadrant 2: Important, not urgent (post-defense / MIT)

### SpeechPrint synthesis direction

- [ ] **DrawSpeech as working pipeline.**
  SpeechPrint prosody tier (symbolic symbols per syllable) → convert to
  per-phoneme pitch sketch (smooth curve, one value per phoneme) →
  feed to DrawSpeech as control condition → synthesised audio output.
  This closes the full loop: record → annotate → edit symbols → synthesise.
  Reference: Chen et al. 2025, arXiv 2501.04256.
  Requires: DrawSpeech weights from https://happycolor.github.io/DrawSpeech

- [ ] **Prosody resynthesis via PSOLA (already partially working).**
  `prosody_prompt.py transfer` does this for whole-recording F0 transfer.
  Next step: apply transfer at syllable level, matching specific `*` marked syllables.
  Then: synthesise using Coqui XTTS with the modified F0 as a guide.

- [ ] **Speech DAW prototype.**
  Web page showing the TextGrid prosody tier as an editable timeline.
  Click a cell → dropdown of symbols (/ \\ ‾ _ *).
  On change: call prosody_prompt.py with the modified tier → play resulting WAV.
  Tech: React + Flask + prosody_prompt.py as subprocess.
  Start with just the prosody tier for one short sentence.

- [ ] **Automatic prosody classification (5 labels).**
  Input: SpeechPrint symbolic tier sequence for one utterance.
  Output: declarative / interrogative / narrow focus / continuation / exclamation.
  Simple rule-based version first: if last syllable is `//` → interrogative, etc.
  Then train a small sequence classifier on GToBI-labelled data.

### ProsodyPrompt synthesis pipeline

- [ ] **Vox Prima / Vox Secunda morphing (working version).**
  1. `audio2tract.py`: invert two WAV files to articulatory trajectories (TensorTract).
  2. Interpolate trajectories frame by frame at a given blend ratio.
  3. Synthesise with VocalTractLab.
  4. Result: a recording whose phonemes come from speaker A
     but whose prosody/timbre blend toward speaker B.
  Prerequisite: install TensorTract (`pip install tensortract2`) and VTL 2.3 on Windows.

- [ ] **GENDY movement generators for prosody curves.**
  Replace the fixed linear interpolation between syllable F0 targets with
  GENDY-style stochastic breakpoint trajectories.
  Each prosody symbol maps to a generator type:
  `//` → elastic (overshoot-and-settle), `\\` → sigmoid, `*` → gendy (Cauchy).
  Produces more expressive, less mechanical-sounding synthesis.

- [ ] **Source-target pair representation of prosody.**
  Represent a sentence's prosody as N (source, target, duration, generator) tuples,
  one per syllable. The canonical base phrase = *prosodic insistunit* (after Lawrence).
  Variations = same tuples with stochastic perturbation applied.
  Connects directly to Lawrence's VIS insistunit concept.

### Corpora and annotation

- [ ] **Kakabe DoReCo as third endangered language.**
  Files already in project root: `doreco_kaka1265_kke-c_2013-12-27_AK-narr-1.wav/.TextGrid`.
  Run same pipeline as Daakie/Cabécar. Tier suffix needs identifying from TextGrid.

- [ ] **English v2 noise-cleaned recording.**
  Apply `noisereduce` to `audio_2026-05-30_19-01-35.wav` → save as `_v2.wav`.
  Run same SpeechPrint pipeline on both and compare prosody tier stability.
  Useful for questionnaire: cleaner audio = clearer perception test.

- [ ] **GToBI all five trackers comparison TextGrid.**
  Currently GTOBI_BEST uses CREPE only. The questionnaire version uses pYIN only.
  Build a version with all five in parallel for the thesis tracker comparison section.
  Already have the infrastructure in `build_doreco_speechprint.py` — just point at
  the GToBI WAVs.

- [ ] **Fix PESTO on Cabécar.**
  Pad audio to nearest power of 2 in frames before calling `pesto.predict()`.
  Or test with step_size=20.0 to see if shorter context avoids the shape mismatch.

### Infrastructure

- [ ] **Phonologically similar language finder (real PHOIBLE lookup).**
  Replace hardcoded hints in `run.py` with actual PHOIBLE data.
  Download PHOIBLE CSV → compute consonant inventory overlap + vowel system distance
  → rank supported ASR languages by proximity to ISO code input.
  ```python
  # PHOIBLE: https://phoible.org/data (phoible.csv download)
  # For each ISO code, compare phoneme inventory intersection / union ratio
  ```

- [ ] **ProsodyPrompt rename.**
  Rename GitHub repo from SpeechPrint to ProsodyPrompt.
  Settings → Rename. Then: `git remote set-url origin https://github.com/kdlydia/ProsodyPrompt.git`

- [ ] **Colab notebook: add interactive questionnaire mode.**
  Add a cell where participants upload their own audio, run analysis, and
  fill in a rating form (1-5 scale: does the prosody tier match what you hear?).
  Results saved to a shared Google Sheet via the Sheets API.

---

## Quadrant 3: Nice to have, do when inspired

### Creative / artistic extensions

- [ ] **Bias feedback loop (Idea 2 formalised).**
  Loop a 10-second speech recording through Whisper sequentially:
  English → Italian → Japanese → Swahili → back to English.
  Record each iteration as audio + text transcript.
  Document the phonological drift: timbre shifts, intelligibility degrades,
  new sounds appear. Each iteration = one compositional layer.
  Direct realisation of the cross-lingual projection phenomenon in the thesis.

- [ ] **Prosody-annotated video.**
  Take any interview clip. Run SpeechPrint. Overlay the symbolic tier as animated
  captions: `*` marked words pulse briefly, `‾` words sit higher in frame,
  `_` words drop. A visual argument for what transcription discards.
  Tech: MoviePy + SpeechPrint output → render frame by frame.

- [ ] **Hand-drawn trajectory figure (like Lawrence's Figure 2.10).**
  Sketch the Vox Prima / Vox Secunda concept as a hand-drawn diagram.
  Show: two articulatory trajectories in a 2D vocal space, with a curved
  path between them. Add prosody symbols along the path.
  Include in thesis Discussion appendix or Sound Communication writeup.

- [ ] **Lawrence McGuire's insistunit applied to prosody.**
  Take one short sentence. Define its prosodic trajectory as a base phrase (insistunit).
  Generate 10 variations using stochastic perturbation (additive noise, time warp).
  Synthesise each with PSOLA. Result: a "prosodic insistunit series" —
  the same sentence repeated with accumulating presence-by-differential.
  Record and document for the creative component of the thesis.

- [ ] **Pink Trombone web integration with SpeechPrint.**
  Write a small web server that reads a TextGrid prosody tier and
  sends the symbols as a phoneme+prosody sequence to the zakaton
  Pink Trombone Timeline Editor via the existing JavaScript API.
  https://zakaton.github.io/pink-trombone-editor/
  Demonstrates the full analysis → synthesis loop in a browser.

### Tools to explore when time allows

- [ ] **SampleBrain** — corpus-based granular with vowel recordings.
  https://thentrythis.org/projects/samplebrain/

- [ ] **Latent Granular** — explore latent space traversal in browser.
  https://huggingface.co/spaces/naotokui/latentgranular
  Upload the DoReCo Daakie vowel recordings. Compare the latent topology
  with the PHOIBLE vowel space.

- [ ] **SPICE** (Self-Supervised Pitch Estimation, Google) — traversable pitch latent space.
  Different from CREPE: uses a Siamese network, relative pitch differences,
  continuous latent space. Could replace CREPE embeddings in the vowel print workflow.

- [ ] **Wekinator integration with Leap Motion for thesis demo.**
  http://wekinator.org
  Train five gesture-to-prosody mappings, record a live performance
  of "I didn't say you stole the money" with different gestures for each emphasis.
  Document as a video for the thesis questionnaire supplementary material.

---

## GitHub repo hygiene

- [ ] **Remove contributors lydia2k and sainish.**
  Settings → Collaborators → Remove (each one). Cannot be done from terminal.

- [ ] **Rename repo to ProsodyPrompt** (when ready).
  Settings → General → Repository name → ProsodyPrompt.
  Then locally: `git remote set-url origin https://github.com/kdlydia/ProsodyPrompt.git`

- [ ] **Add Colab badge to README.**
  Add this line near the Quick start section:
  ```
  [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kdlydia/SpeechPrint/blob/main/SpeechPrint.ipynb)
  ```

---

## References for everything above

- SampleBrain: https://thentrythis.org/projects/samplebrain/
- Neu-Grains (M4L): https://neutone.ai/m4l/neu-grains
  Paper: https://arxiv.org/pdf/2507.19202
- Latent Granular: https://huggingface.co/spaces/naotokui/latentgranular
- DrawSpeech: https://happycolor.github.io/DrawSpeech
  Chen et al. 2025, arXiv 2501.04256
- Pink Trombone Timeline Editor: https://zakaton.github.io/pink-trombone-editor/
- VocalTractLab: https://vocaltractlab.de
- Lawrence McGuire VIS: https://github.com/hogobogobogo/VIS
  "Poetics of the Lacking Voice," Institute of Sonology, The Hague, 2026
- Lawrence McGuire bandcamp (audio excerpts): https://hogobogobogoo.bandcamp.com/album/vox-sound-excerpts-ii
- Birkholz 2013: https://doi.org/10.1371/journal.pone.0060603
- Krug et al. 2023: https://doi.org/10.21437/Interspeech.2023-2173
- Krug et al. 2025: https://doi.org/10.1109/ICASSP49660.2025.10890772
- PHOIBLE data: https://phoible.org/data
- Wekinator: http://wekinator.org
