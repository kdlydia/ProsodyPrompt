# 2026-06-05 — SpeechPrint Defense Prep
### Session findings + 10-day pre-checklist + today's key decisions

---

## What was built and decided today

### 1. DoReCo BEST (`DORECO_BEST/`)
- CREPE full model, 10 ms hop, batch_size=128 — confirmed no OOM
- All 5 algorithmic optimisations applied and validated with data:
  - Strong movements: 30.9% → 21.0% (MAD threshold)
  - Falls: 26.7% → 18.8% (declination removal)
  - Rises/falls ratio: 0.61 → 0.72
- 8-tier TextGrid: sentence · translation · words · gloss · syllables · phones · prosody_crepe + video

### 2. GToBI BEST (`GTOBI_BEST/`) — MFA abandoned
**Red flag discovered:** MFA produced wrong transcriptions for 3/5 sentences:
- "gelbe" → "gerbe" | "einige Melonen" → "einigen mal lohnt" | "er sang die Lieder" → "hesangli lieder"
- MFA timing off by 66–430 ms from human Wort tier in ALL 5 sentences
- Cannot mix human Wort + MFA tiers in same TextGrid

**Fix:** Hardcoded correct German IPA, distributed proportionally within human Wort boundaries.
Now 8 tiers matching DoReCo structure exactly:
`sentence · translation · words · gloss · syllables · phones · gtobi · prosody`

### 3. GToBI results comparison

| Pipeline | ✓ correct | ~ partial | ✗ wrong |
|----------|-----------|-----------|---------|
| pYIN (v3 baseline) | 3 | 1 | 1 |
| CREPE + corrected IPA | 1 | 4 | 0 |

CREPE: gets pitch *direction* right on all 5; pYIN wins the binary score. The 4 partials are all correct word + correct direction — missing only the `*` accent marker (threshold not calibrated for short utterances < 2s).

### 4. Thesis updated
- `methods/methods.tex`: CREPE described fully; 5 optimisations documented; DoReCo pipeline section added; `‾` overline replaces `-` throughout; "ProsodyPro" removed from all methodology descriptions
- `results/results.tex`: Two GToBI tables (pYIN + CREPE); MFA red flag documented; tracker recommendations split into two-pipeline approach

### 5. New slide images
- `11_DORECO_tracker_table_and_optimisations.png`
- `12_OPTIMISATIONS_table.png`
- `13_GTOBI_BEST_summary.png`
- Insert order in PPTX: after slide 17, after slide 21, after slide 21

### 6. Symbol change
`-` (high level) → `‾` (U+203E overline) everywhere. Overline and underscore are visual opposites — one stroke above baseline, one below.

---

## The one-paragraph thesis summary you should know by heart

> I built SpeechPrint — an end-to-end pipeline that takes any WAV file in any language and produces a prosodically annotated TextGrid in under two minutes, with no specialist knowledge required. The core contribution is a symbolic tier: rising, falling, high, low, accented — seven shapes that summarise the pitch contour of each syllable without requiring the reader to open Praat. I evaluated it against German GToBI expert annotations and against a 162-second recording of Daakie, an endangered language from Vanuatu. I found that the default Praat pitch tracker makes 238 octave errors in 30 seconds of English speech — which directly inverts prosody labels. Switching to CREPE, a neural pitch tracker from NYU, and applying five evidence-based algorithmic improvements brought the label distribution into the expected range. The system is publicly documented, reproducible, and designed for fieldwork contexts where no specialist software or ASR model exists for the target language.

---

## 10-Day Pre-Defense Checklist

> **You struggle with impromptu presentations. That means you need to practice speaking, not reading. Every item below is about talking, not studying.**

### How to use this checklist
Tick each item when done. If you don't tick it, do it the next day too. Nothing carries over silently.

---

### Day 1 (Jun 5 — today) · Orientation only
- [ ] Read the one-paragraph summary above 3 times, then close this file and say it out loud.
- [ ] Read `anki/intuition_guide.md` top to bottom. Slowly. Say each concept back to yourself.
- [ ] Do NOT open the PPTX today. Do NOT look at speaker notes.
- [ ] Before sleep: say the Big Story out loud in the dark.
  > *"Writing captures words. Speech has prosody — pitch, stress, rhythm. SpeechPrint recovers that. Automatically. Any language. Two minutes."*

---

### Day 2 (Jun 6) · Numbers only
- [ ] Import `anki/speechprint_anki_10days.txt` into Anki. Filter tag `day2`. Study until 90% correct.
- [ ] Say out loud, from memory, without looking: 238 · 40 · 162.7s · 453 · 9912 · 30.9%→21.0% · 26.7%→18.8% · 1 correct / 4 partial
- [ ] Set a 2-minute timer. Explain the octave error out loud to no one, using the "ΔF₀ = 12·log₂" formula. Stop at 2 minutes whether or not you're done.

---

### Day 3 (Jun 7) · Technical concepts
- [ ] Anki: filter tag `day3`. Study CREPE, pYIN, MAD, declination cards.
- [ ] Explain CREPE to an imaginary person who is a musician but not a scientist. Use the "trained ear vs ruler" analogy. Time it: under 90 seconds.
- [ ] Explain declination to the same person. Use the "river tilt" analogy. Under 60 seconds.
- [ ] Explain why YIN's zero unknowns is a red flag. Under 45 seconds. No notes.

---

### Day 4 (Jun 8) · The 5 optimisations by heart
- [ ] Anki: filter tag `day4`. Study all optimisation cards.
- [ ] Memorise the mnemonic: **M**y **B**uddy **D**efinitely **E**njoys **O**ranges → MAD · Boundary · Declination · Edge trim · Octave recovery
- [ ] Set a 5-minute timer. Walk around the room. Say all 5 optimisations out loud — for each one: what was wrong, what you did, what changed. No notes.
- [ ] Say the GToBI MFA red flag story out loud: what you found, why it mattered, what you did. Under 2 minutes.

---

### Day 5 (Jun 9) · Results and GToBI
- [ ] Anki: filter tag `day5`. Study GToBI and results cards.
- [ ] Say the two-pipeline conclusion out loud: when pYIN, when CREPE, and why.
- [ ] Say the GToBI result honestly: pYIN 3/5, CREPE 1/5 but all 5 directions correct. Practice this — you will be asked. Frame it as: "pYIN wins the binary score; CREPE wins the interpretability score."
- [ ] Say the L*+H explanation. What it is. Why it's hard. What would fix it. Under 90 seconds.

---

### Day 6 (Jun 10) · First full run-through
- [ ] Sit down with your laptop, slides open, nobody watching.
- [ ] Do the full 25-slide presentation out loud. Talk to an imaginary committee of 4 people.
- [ ] **Do not stop when you stumble.** Keep going. Say "what this means in practice is..." and continue.
- [ ] Time it. Write down the time and the 3 worst moments.
- [ ] After: fix ONE thing. Only one.

---

### Day 7 (Jun 11) · Hard questions day
- [ ] Anki: filter tag `day7`. Study the examiner scenario cards.
- [ ] Have someone ask you these 5 questions one by one. If nobody is available, record yourself asking and then answering.
  1. "Why not just use Praat?"
  2. "Is 1 out of 5 GToBI correct good enough?"
  3. "What was the MFA error and why did you miss it initially?"
  4. "What is the actual contribution of this thesis?"
  5. "If you had 6 more months, what would you do?"
- [ ] For each answer: aim for 60–90 seconds. Stop there even if you have more to say.
- [ ] Practice the recovery phrase: *"Let me make sure I understand the question — are you asking about X or Y?"* This buys you 5 seconds and sounds intentional.

---

### Day 8 (Jun 12) · Symbols and relative measurement
- [ ] Anki: filter tag `day8`. Review symbol and relative measurement cards.
- [ ] Write the full symbol table from memory on paper. No looking. ‾ _ / // \ \\ * ?
- [ ] Explain the overline vs dash change. Why it matters visually. Under 30 seconds.
- [ ] Explain relative vs absolute measurement with the English recording example (Mary 4.2 ST, flew 2.1 ST). Under 60 seconds.
- [ ] Second full run-through. Aim for under 32 minutes. Record yourself on your phone.

---

### Day 9 (Jun 13) · Recording + weak spots
- [ ] Watch yesterday's recording. Note the top 3 things that looked or sounded wrong.
- [ ] Fix exactly those 3 things. Practise just those slides 3 times each.
- [ ] Run through slides 9, 10, 18, 18b, 21, 21b, 21c only — the technically dense ones.
- [ ] Anki: any cards marked difficult from the past week. 20 minutes max.
- [ ] Practice: committee asks "what is your contribution?" Answer under 90 seconds. Do this 3 times until it sounds natural.

---

### Day 10 (Jun 14 — day before) · Very light
- [ ] Say the Big Story sentence out loud when you wake up.
- [ ] Say the mnemonic (MBDEO) out loud once.
- [ ] Read the "questions you will probably get" section in `intuition_guide.md` once, slowly.
- [ ] Do NOT do a full run-through. Do NOT open Anki for more than 15 minutes.
- [ ] Prepare what you are wearing. Eat properly. Sleep 8+ hours.
- [ ] Before sleep: say the one-paragraph summary from memory. Go to sleep.

---

### Defense day
**Before you walk in:**
- Say: *"Writing captures words. Speech has prosody. SpeechPrint recovers that."*
- Say: My Buddy Definitely Enjoys Oranges.
- Take 3 slow breaths.

**During:**
- If you lose your place → look at the slide. One image = one idea. The slide is your anchor.
- If you go blank → pause, look at the slide, say *"what this means in practice is..."*
- If you can't answer → *"Let me make sure I understand the question..."* + think for 3 seconds.
- If you're asked something you truly don't know → *"That's outside what I measured, but my intuition is..."*

**The secret:** They are not testing whether you can recite. They are testing whether you understand. You built this. Nobody in the room knows it better than you.

---

## Key facts to drill this week

| Fact | Value |
|------|-------|
| English octave errors (30s) | 238 |
| Daakie octave errors (30s) | 40 |
| DoReCo recording duration | 162.7 s |
| DoReCo syllables | 453 |
| DoReCo utterances | 34 |
| CREPE voiced frames (DoReCo) | 9,912 (60.9%) |
| Strong movements before → after | 30.9% → 21.0% |
| Falls before → after | 26.7% → 18.8% |
| Rises/falls ratio before → after | 0.61 → 0.72 |
| pYIN GToBI score | 3 correct / 1 partial / 1 wrong |
| CREPE GToBI score | 1 correct / 4 partial / 0 wrong |
| Pipeline stages | 9 |
| CREPE hop length | 10 ms |
| Nucleus edge trim | 15% each side |
| MAD normalisation factor | 1.4826 |
| Xu(1999) spike threshold | 12 semitones |
| Accent amplitude threshold | 1.5 dB |
| MFA errors found | 3/5 sentences wrong; timing off 66–430 ms |
| GToBI sentences | 5 (1.0–1.5s each) |
| New slides added | 3 (18b, 21b, 21c) |

---

## Recoveries — memorise these phrases

| Situation | Say this |
|-----------|----------|
| Go blank mid-sentence | *"What this means in practice is..."* |
| Don't understand the question | *"Let me make sure I understand — are you asking about X or Y?"* |
| Don't know the answer | *"That's outside what I measured, but my intuition based on the data is..."* |
| Made a mistake they noticed | *"You're right — let me correct that. What the data actually shows is..."* |
| Running long | *"I'll pause here — happy to go deeper on that in questions."* |
| Nervous and freezing | Look at the slide. Pick any word in the slide. Say something about that word. |
