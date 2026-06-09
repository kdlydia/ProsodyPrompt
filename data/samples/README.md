# Sample Audio Files

These samples are included for quick testing of ProsodyPrompt without needing to find your own audio.

## Files

**german_banana.wav** (~130 KB, 3.2s)
- Single German sentence: "eine gelbe Banane" (a yellow banana)
- Clean studio recording, moderate pitch range
- Good for testing pitch tracking and basic prosody labelling

**demo_clip_10s.wav** (~320 KB, 10s)
- English speech, read aloud
- Longer sample for testing alignment and multi-utterance processing

**demo_clip_20s.wav** (~640 KB, 20s)
- English speech, read aloud
- Good for testing full pipeline with multiple speakers and pauses

## Quick Start

```bash
cd ProsodyPrompt/linux
python run.py
# Choose: 1) Annotate a recording
# Language: en (English) or de (German)
# Point to: ../data/samples/german_banana.wav  (or any other sample)
# Tracker: pYIN (fast, CPU-only)
```

Expected output: `linux/out/german_banana/german_banana.TextGrid`

---

For larger datasets or your own recordings, place them in this directory or elsewhere and point `run.py` to them.
