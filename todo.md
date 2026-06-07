# todo

roughly urgent → less urgent. tick things off as you go.

---

## do this week (thesis + sound comm)

### thesis

- [ ] send questionnaire folder to dad — `FINAL_QUESTIONNAIRE_2026-06-07/`
      he picks the english pairs, lydia picks the language examples
- [ ] replace overleaf files: only `discussion.tex` and `abstract.tex` differ from github
      methods, results, appendix are already right in overleaf
- [ ] compile pdf and check: missing figures? page count under 100? no undefined cites?
- [ ] remove lydia2k and sainish from github contributors
      settings → collaborators → remove (can't do from terminal sorry)
- [ ] update github "about" description manually:
      `one-click installer and linguistic analysis toolkit for asr, forced alignment,
      prosody extraction, and corpus analysis.`

### sound communication class

the idea: leap motion navigates a latent articulatory space. hand position = prosodic state.
pink trombone speaks it. vowel print via CREPE embeddings.

- [ ] whisperx on reference sentence → word timestamps json
- [ ] extract CREPE embeddings (5th max-pooling layer) from vowel recordings
- [ ] osc bridge python ↔ max (`pip install python-osc`, udp port 8000)
- [ ] leap motion hand height → pink trombone frequency (minimum viable demo)
- [ ] show in presentation: "mary flew to milan" with gesture on each word

nice to have for the class:
- [ ] wekinator: map 5 hand positions to 5 prosodic states
- [ ] two-hand blend between question intonation and statement
- [ ] hum → pyin → pink trombone (airpods mic version)
- [ ] caption layer: word floats higher when f0 is high
- [ ] explore latentgranular with speech sounds: https://huggingface.co/spaces/naotokui/latentgranular
- [ ] try samplebrain with vowels: https://thentrythis.org/projects/samplebrain/
- [ ] neu-grains max patch: https://neutone.ai/m4l/neu-grains

signal flow for the writeup:
```
leap motion xyz → python (crepe embedding lookup) → osc
→ max/msp → pink trombone (frequency, tenseness, tongue) → audio
→ caption display (f0 → font size / vertical position)
```

---

## important but not this week

### prosodyprompt synthesis direction

- [ ] drawspeech as working pipeline
      prosodyprompt prosody tier → per-phoneme pitch sketch → drawspeech synthesis
      https://happycolor.github.io/DrawSpeech  (chen et al. 2025)
- [ ] prosody resynthesis via psola at syllable level (prosody_prompt.py transfer already works file-level)
- [ ] speech daw prototype — web page, editable prosody tier, hear resynthesis on symbol change
- [ ] GENDY articulatory trajectories for prosody curves
- [ ] automatic prosody classification (declarative / interrogative / narrow focus / continuation / exclamation)

### corpora + annotation

- [ ] english v2 noise cleaned — `noisereduce` on `audio_2026-05-30_19-01-35.wav`
- [ ] fix pesto shape mismatch on cabécar (pad audio to round frame count before `pesto.predict()`)
- [ ] gtobi all-five-tracker comparison textgrid (currently only crepe)

### infrastructure

- [ ] real phoible phonological similarity lookup (currently hardcoded hints)
      download phoible.csv, rank supported languages by consonant inventory overlap
- [ ] colab notebook: add questionnaire rating mode → save to google sheet
- [ ] add colab badge to readme (copy from todo references section)

---

## someday / when inspired

- [ ] vox prima / vox secunda morphing (tensortract inversion + vocaltractlab synthesis)
- [ ] bias feedback loop — loop a sentence through whisper across 4 languages recursively
      document each iteration as audio + transcript. phonological drift = composition.
- [ ] prosody-annotated video — overlay symbolic tier as animated captions on any interview clip
- [ ] insistunit for prosody — canonical base phrase + stochastic variations (like lawrence's vis)
- [ ] pink trombone web integration — bridge prosodyprompt textgrid → zakaton timeline editor
- [ ] spice (google) — traversable pitch latent space, different from crepe
- [ ] speech daw with live articulatory resynthesis (the full dream)
- [ ] prosody-sensitive subtitles for a movie clip

---

## references

```
drawspeech          https://happycolor.github.io/DrawSpeech
pink trombone DAW   https://zakaton.github.io/pink-trombone-editor/
samplebrain         https://thentrythis.org/projects/samplebrain/
neu-grains          https://neutone.ai/m4l/neu-grains
latent granular     https://huggingface.co/spaces/naotokui/latentgranular
vocaltractlab       https://vocaltractlab.de
wekinator           http://wekinator.org
phoible             https://phoible.org/data
colab notebook      https://colab.research.google.com/github/kdlydia/ProsodyPrompt/blob/main/SpeechPrint.ipynb
```
