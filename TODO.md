# SpeechPrint / ProsodyPrompt — Research Directions & Todo

---

## Sound Communication class (1-week deadline)

### Core idea: generative speech instrument with traversable latent space

Instead of mapping one parameter (hand height → F0), navigate a multi-dimensional
articulatory manifold where position in space simultaneously controls pitch, vowel
quality, and spectral envelope. "Speech as vector graphics."

**References:**
- SampleBrain (corpus-based granular synthesis): https://thentrythis.org/projects/samplebrain/
- Neu-Grains Max patch + paper: https://neutone.ai/m4l/neu-grains
  (paper: https://arxiv.org/pdf/2507.19202)
- Latent Granular (HuggingFace space, try with speech sounds):
  https://huggingface.co/spaces/naotokui/latentgranular

### The "Vowel Print" workflow
1. Take a pretrained model (CREPE or HuBERT)
2. Run a dataset of vowels/phonemes through it → extract embeddings
3. Each embedding = a point in latent space = a "vowel print"
4. Train a classifier (or use Wekinator) to map Leap Motion XYZ → latent coordinates
5. Map latent coordinates back to Pink Trombone articulatory parameters

**CREPE embedding:** output of fifth max-pooling layer = pretrained pitch embedding.  
**HuBERT:** upper layers (9-12) encode prosodic/discourse-level structure.

### Implementation checklist (7 days)
- [ ] Run WhisperX on reference sentence → get word-level timestamps JSON
- [ ] Extract vowel embeddings via torchcrepe (fifth layer) from phoneme dataset
- [ ] Set up OSC bridge: Python ↔ Max/MSP
- [ ] Wekinator: map Leap Motion XYZ → 2D latent coordinates
- [ ] Max: map latent coordinates → Pink Trombone (tension, tongue index, diameter)
- [ ] Smoothing: median filter or Viterbi path in Max to avoid pitch jumps
- [ ] Caption layer: send F0 via OSC → font size / vertical position of word

### 5 core gestures (GToBI-inspired)
1. **Neutral fall** (H\* L-%): downward arc → statement
2. **Question rise** (L\* H-%): sharp upward flick at end → yes/no question
3. **Contrastive peak** (L+H\*): vertical spike → emphasis on one word
4. **Sustained level**: horizontal → list continuation / hesitation
5. **Creak / low tension**: low + shaky → drives shimmer/jitter in Pink Trombone

### With Leap Motion (satisfies class requirement)
- Hand height (Y) → F0 / vocal fold tension
- Hand horizontal (X) → tongue position / vowel quality
- Hand depth (Z) → blend between Vox Prima and Vox Secunda prosodic states
- Finger spread → lip opening / oral cavity width
- Pinch gesture → voicing on/off

### With AirPods (alternative to Leap Motion)
- Mic: pYIN extracts F0 from humming in real time → maps to Pink Trombone frequency
- IMU head nod: stamps `*` accent marker on current syllable
- Head tilt: blend ratio between two prosodic states

### Wekinator (optional, already available)
- Input: Leap Motion XYZ (3 dims)
- Output: 2D latent space coordinates
- Useful if the direct mapping feels too rigid; Wekinator learns a smooth manifold

---

## SpeechPrint pipeline — unfinished / future

### Not yet implemented (written but not built)
1. Prosody resynthesis: edit symbols → compile to F0 targets → Coqui TTS → audio
2. Speech DAW: click syllable tier, change symbol, hear resynthesis in real time
3. Automatic prosody classification (5 labels: declarative / interrogative / narrow focus / continuation / exclamation)
4. Vox Prima / Secunda morphing: `prosody_morph.py` stub exists, not running
5. Source-target pairs with movement generators for prosody (GENDY, Lorenz, sigmoid)
6. Phonologically similar language finder: hardcoded hints, no real PHOIBLE lookup
7. PESTO shape mismatch on Cabécar: documented as failure, not diagnosed
8. DrawSpeech as working pipeline: noted in Discussion, not connected to code
9. Noise-cleaned English recording v2
10. GToBI all-five-tracker comparison: only CREPE in GTOBI_BEST

### External projects to integrate
- **DrawSpeech** (Chen et al. 2025) — synthesis side of the loop.
  SpeechPrint prosody tier → DrawSpeech sketch → diffusion synthesis.
  https://happycolor.github.io/DrawSpeech
- **Lawrence McGuire's VIS** — GENDY articulatory trajectories, insitunit concept.
  https://github.com/hogobogobogo/VIS
- **Pink Trombone Timeline Editor** (zakaton) — working web TTS DAW.
  https://zakaton.github.io/pink-trombone-editor/
- **VocalTractLab 2.3** — articulatory synthesis. `prosody2tract.py` stub ready.
  https://vocaltractlab.de
- **TensorTract** — acoustic-to-articulatory inversion. Prerequisite for Vox Prima/Secunda.
  `pip install tensortract2`
- **FluCoMa** — novelty-slice segmentation. Used in Lawrence's segmentation patch.
  https://github.com/jamesb93/python-flucoma
- **Kakabe DoReCo** — third endangered language. Files already in project root.
  Process same as Daakie + Cabécar pipeline.

---

## Longer research directions (post-thesis / MIT)

### Prosodic vocality (Idea 1)
Voice as compositional material. Natural voice + synthetic voice juxtaposed.
Spectralist interpolation between two vocal identities (Vox Prima / Vox Secunda).
Requires: TensorTract (inversion) + VocalTractLab (synthesis) + morphing script.
Connection to Lawrence McGuire's NKOAPP and articulatory morphing work.

### Bias as generative material (Idea 2 — already in thesis Discussion §4)
Recursive cross-lingual ASR feedback: loop a voice through Whisper across languages.
Each iteration = phonological projection of the previous model onto unknown phonology.
The SpeechPrint Daakie/Italian finding is this, accidental. Make it intentional.
Reference: Lawrence's Phonesthemic Palimpsest — poop-sequences converging toward a language.

### Closed loop: SpeechPrint → edit → DrawSpeech
Analysis side: SpeechPrint extracts symbolic prosody tier.
Edit: user modifies symbols in Praat or a web editor.
Synthesis: DrawSpeech-style diffusion model conditioned on the edited sketch.
DrawSpeech (Chen et al. 2025) achieves MOS 4.49 — above ground truth 4.46.

---

## Tools to test / install
- `pip install tensortract2` — acoustic-to-articulatory inversion
- `pip install vocaltractlab-cython` — articulatory synthesis
- FluCoMa: https://github.com/jamesb93/python-flucoma
- SPICE (Self-Supervised Pitch Estimation, Google) — traversable pitch latent space
- Wekinator — machine learning for gestural mapping: http://wekinator.org

---

## Colab notebook
Open in Colab (pYIN + CREPE + EnCodec + HuBERT):
https://colab.research.google.com/github/kdlydia/SpeechPrint/blob/main/SpeechPrint.ipynb

---

## Questionnaire files for supervisor
Location: `FINAL_QUESTIONNAIRE_2026-06-07/`
```
daakie/       doreco_port1286_2017_06_30_Jaklin.wav + daakie.TextGrid
cabeca/       doreco_cabeca.wav + cabeca.TextGrid
german_gtobi/ eine_gelbe_banane, einige_melonen, er_sang_die_lieder,
              er_will_die_rosen_haben, ich_wohne_in_bern  (.wav + .TextGrid each)
english/      audio_original.wav + english.TextGrid
```
All TextGrids: 6 tiers — sentence | words | translation | syllables | phones | prosody
German GToBI: expert `gtobi` tier intentionally excluded to avoid priming.
