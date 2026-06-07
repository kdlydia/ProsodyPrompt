# Intuition Guide — SpeechPrint Defense
### Read this BEFORE drilling Anki cards. Understand first, memorise second.

---

## THE BIG STORY (say this to yourself every morning)

> Writing captures words. It doesn't capture how the words were said.
> SpeechPrint recovers that — automatically, in any language, in two minutes.

Every technical thing in this thesis is a detail inside that one sentence.

---

## CREPE — the neural pitch tracker

**The analogy that works:**

Praat is a ruler. It measures the distance between peaks in the sound wave and
says "this is the pitch." It works when the sound is clean and periodic.
But voices are not always clean. Creaky voice, breathy voice, a microphone in
the rain — the peaks get messy. The ruler gets confused and sometimes picks a
peak that is half the real one. That is the octave error.

CREPE is a trained ear. It listened to millions of recordings where the pitch
was already known, and it learned what pitch *sounds* like — not what it
*looks like mathematically*. So even when the waveform is messy, it recognises
the sound pattern. It does not need the peaks to be perfect.

**Why 10 ms hop?**  
CREPE moves through the audio in 10 ms steps. That is one frame every 10 ms.
For 162.7 seconds of audio: 162.7 / 0.01 = 16,270 frames. That is the number
you remember.

**Why 16 kHz?**  
That is the sample rate the model was trained on. Any audio gets resampled
to 16 kHz before CREPE sees it. Not our choice — that is baked into the model.

**The confidence score (0.5 threshold):**  
CREPE does not just return a Hz value. It returns a probability: "I'm 73%
confident this frame has pitch." Below 0.5, we say unvoiced. This replaces
pYIN's probabilistic voiced/unvoiced model with something equivalent.

---

## pYIN vs YIN — why YIN is disqualified

Think of YIN as someone who answers every question even when they don't know
the answer. Ask "what's the weather in Tokyo right now?" and they will say
"28 degrees." They might be right. They might be completely wrong. You cannot
trust them because they never say "I don't know."

pYIN says "I don't know" — and gives you the probability that it does know.
When pYIN returns a value, you can trust it. When it returns nothing, that is
also information: the frame was unvoiced.

YIN had 27,350 "voiced" frames out of ~28,000 total — 97.7%. It detected
pitch in nearly every frame of a recording that includes silence, consonants,
and pauses. That is not accuracy. That is recklessness.

---

## The five optimisations — one intuition each

**1. MAD instead of std (robust statistics)**

Imagine measuring the "typical" wealth of people in a room. If Jeff Bezos
walks in, the *mean* wealth skyrockets. The *median* barely moves. MAD is
based on the median — it is immune to Jeff Bezos.

In pitch data: a few very fast accent movements (our Jeff Bezos) inflated
the standard deviation. This made the "strong movement" threshold too low.
MAD ignores them. Result: 30.9% → 21.0% strong movements.

**2. Utterance boundary reset**

Imagine rating how tall someone is by comparing them to their neighbours.
If their left neighbour is a basketball player and their right neighbour is
a child, the same person can look either short or tall depending on which
neighbour you compare to. The algorithm was doing exactly this across
utterance boundaries.

End of utterance: voice drops (final lowering). Start of next utterance:
voice resets high. Treating those two as neighbours produced a false
"this one is low, that one is high" contrast. Fix: only compare within
the same utterance.

**3. Declination removal (detrending)**

Every utterance has a slow downward slope baked in — the voice physically
relaxes toward the end. It is like a river that flows gently downhill.
Without correction, the algorithm labelled the slope as "falling" movements.

Fix: fit a straight line through the F0 values within each utterance and
subtract the slope. You are removing the river's tilt, so what remains
are only the waves on top of the river.

Result: falls 26.7% → 18.8%. Rises/falls ratio 0.61 → 0.72.

**4. Nucleus edge trimming (15%)**

When you go from a consonant to a vowel, the voice does not switch on
instantly. There is a 10–20 ms transition zone where the pitch is unstable.
If you measure at the very edge of the vowel, you are measuring the
transition, not the vowel.

Fix: skip the outer 15% of the nucleus window. The slight increase in
unknowns (0.9% → 1.5%) is correct — very short vowels that were previously
forced to a value are now honestly flagged as uncertain.

**5. Octave recovery**

Xu(1999) flags any frame more than 12 semitones from the median as a spike.
But many of those frames are not random noise — they are octave errors.
The tracker found a frequency that is exactly twice or half the real pitch.

Instead of discarding the frame, try multiplying and dividing by 2.
If either result passes the threshold, keep the best one.
It is the difference between throwing away a misspelled word and correcting it.

---

## The symbol system — how to think about it

Draw this in your mind:

```
‾//   means: you started high, and your pitch shot upward
_\\   means: you started low, and your pitch dropped hard
*‾/   means: you were prominent, high, and gently rising
```

The height symbol (‾ or _) is WHERE you start relative to neighbours.
The direction symbol (/ // \ \\) is WHERE you go within the syllable.
The asterisk (*) is HOW MUCH you stand out (louder + higher or longer).

They can combine: the first character is always * if accented,
then height, then direction.

The old dash (-) was replaced by ‾ (overline). Reason: _ and ‾ are
visual opposites — one stroke below the baseline, one above it.

---

## GToBI results — the honest framing

3 out of 5 is not a failure. Frame it this way:

> "Three of five German sentences are correctly labelled. The two failures
> both share the L*+H pattern — a delayed-peak accent where the high
> arrives on the syllable *after* the starred one. This is a known
> challenge for any local F0 labeller, and it is addressable: adding
> a one-syllable look-ahead window would fix it. The pattern is understood;
> the fix is clear."

The examiner will appreciate that you know exactly why it fails and what
would fix it. That is stronger than claiming 5/5.

---

## The numbers you must know cold (drill these)

| What | Number |
|------|--------|
| Octave errors, English, 30 s | **238** |
| Octave errors, Daakie, 30 s | **40** |
| DoReCo recording length | **162.7 s** |
| DoReCo syllables | **453** |
| DoReCo utterances | **34** |
| CREPE voiced frames | **9,912** |
| Strong movements before → after | **30.9% → 21.0%** |
| Falls before → after | **26.7% → 18.8%** |
| Rises/falls ratio before → after | **0.61 → 0.72** |
| Pipeline stages | **9** |
| GToBI correct | **3/5** |
| MAD normalisation factor | **1.4826** |
| Xu(1999) spike threshold | **12 semitones** |
| Accent amplitude threshold | **1.5 dB** |
| Nucleus edge trim | **15%** |

---

## Mnemonics

**9 pipeline stages** — "Lucy Cleans And Eats Peaches Like Wild Elephants"
Load · Clean · Align · Extract · Phonemize · Label · Write · Export
(Stage 2 is Transcribe, but L=Load/Listen works as memory hook)

**4 trackers in order of reliability** (for the defense audience):
"Creative People Play Praat" → CREPE · pYIN · Praat+Xu · Praat raw

**5 optimisations** — "My Buddy Definitely Enjoys Oranges"
MAD · Boundary · Declination · Edge trim · Octave recovery

**238** — "Two hundred, like two centuries, then 38 — almost 40 (Daakie had 40)"

**The L*+H failure** — "The star is late to the party." The high peak arrives
after the starred syllable. SpeechPrint only looks at the person currently
at the party, not who comes next.

---

## Questions you will probably get — and what to say

**"Why not just use Praat?"**
> "Praat's autocorrelation method assumes the voice is harmonic. On clean
> German, it works fine — all trackers agree. But on English, it produced
> 238 octave errors in 30 seconds, which directly inverted prosody labels.
> Switching to pYIN or CREPE eliminates those errors."

**"Why CREPE for Daakie specifically?"**
> "For a language we know little about, we cannot assume the voice behaves
> like the European languages that signal-processing models were designed
> for. CREPE learned pitch from data — it makes no assumptions. That is
> exactly what you want for an endangered language."

**"Is 3/5 GToBI accuracy good enough?"**
> "It is a promising baseline for a system with no language-specific
> training. The two failures are not random — they share a specific
> structural pattern, L*+H, and the fix is known. A single look-ahead
> window would address both."

**"What is the contribution exactly?"**
> "An end-to-end pipeline that takes any WAV file, any language, and
> produces a prosodically annotated TextGrid in two minutes, with no
> specialist knowledge required. Plus: a comparative tracker evaluation
> that documents exactly where and why Praat fails, and five
> evidence-based algorithmic improvements that bring the label
> distribution into the expected range."

**"What is declination and did you expect to find it?"**
> "Declination is the natural downward drift of F0 over an utterance.
> I found it diagnostically — the falls outnumbered rises by a factor of
> 1.6, which is implausible. I fit a linear regression per utterance and
> subtracted the slope. That is standard in phonetics; I implemented it
> after seeing the data required it."
