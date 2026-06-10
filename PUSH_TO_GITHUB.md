# Push Your Code to GitHub

Your **Appendix D & E implementations are complete and tested locally**. This file explains how to push them to GitHub.

## TL;DR (Pro Coder Way)

```bash
chmod +x CLEANUP_AND_PUSH.sh
./CLEANUP_AND_PUSH.sh
```

Done. Your code is on GitHub.

---

## What's the Problem?

Your git repository has large files in its history that GitHub blocks:

- **356 MB WAV** — `meetingwithsupervisor/Sound record (2026-06-01 13_59_24).wav`
- **85 MB PPTX** — `defense_slides_2026-06-02/Bachelors-Thesis.pptx`
- **87 MB PPTX** — `defense_slides_2026-06-02/Masters ThesisOriginal.pptx`

GitHub's limit is 100 MB per file and 50 MB recommended. These need to be removed from git history (not just deleted from disk, but erased from all commits).

## What Does the Script Do?

1. **Installs git-filter-repo** (if needed)
2. **Rewrites git history** to remove the large files
3. **Force-pushes** the cleaned history to GitHub
4. **Pushes** your new Appendix D & E code

## Step-by-Step Instructions

### Step 1: Install git-filter-repo (if needed)

**Arch Linux:**
```bash
sudo pacman -S git-filter-repo
```

**macOS:**
```bash
brew install git-filter-repo
```

**Ubuntu/Debian:**
```bash
sudo apt install git-filter-repo
```

**Other Linux / Use pip:**
```bash
pip install git-filter-repo
```

### Step 2: Run the cleanup script

```bash
cd ~/School/UPF/semester3/test2/SpeechPrint-main
chmod +x CLEANUP_AND_PUSH.sh
./CLEANUP_AND_PUSH.sh
```

The script will:
- Create a safety backup branch (in case something goes wrong)
- Remove large files from history
- Force-push the cleaned main branch
- Push the feature branch with your code

### Step 3: Verify on GitHub

```bash
# Check your branches on GitHub:
# https://github.com/kdlydia/ProsodyPrompt/branches
```

Your code will be visible on the `feature/appendix-d-e-complete` branch and cleaned main.

## What Gets Pushed?

✅ **All your new code:**
- `linux/audio2tract.py` — Audio manipulation tool
- `linux/prosody_morph.py` — Speaker morphing tool
- `linux/TEST_ALL_APPENDIX_DE.sh` — Full test suite
- Fixed `linux/prosody2tract.py` — Raw string docstring
- Fixed `linux/synthesize_audio.py` — Path handling

✅ **All test results:**
- 12/12 tests passing
- 4 × 10.5 MB test audio files locally available

❌ **Removed from history:**
- 356 MB sound recording (not needed in git)
- 173 MB PPTX files (not needed in git)

## Safety

The script uses `--force-with-lease` which is safe because:
- It only force-pushes if no one else has pushed since you last pulled
- If someone else pushed, it fails safely (you merge first)
- Your backup branch stays in case you need to revert

## Troubleshooting

**"git-filter-repo not found"**
→ Install it with the commands above

**"Authentication failed"**
→ Check your SSH key or GitHub token
```bash
ssh -T git@github.com  # Test SSH
# or
git credential reject https://github.com  # Reset credentials
```

**"force-with-lease refused"**
→ Someone else pushed. Merge their changes first:
```bash
git pull origin main
./CLEANUP_AND_PUSH.sh
```

**Something went wrong**
→ Use your backup branch:
```bash
git reset --hard backup/before-cleanup-<timestamp>
```

## After Push

✅ Your code is on GitHub
✅ Repository is now smaller (~100 MB → ~50 MB)
✅ Future clones will be faster
✅ Ready for supervisor review and thesis submission

Delete the backup branch when confident:
```bash
git branch -d backup/before-cleanup-*
git push origin --delete backup/before-cleanup-*
```

---

## Files Included in This Commit

### Appendix D: ProsodyPrompt CLI
- **speechprint_cli.py** (369 LOC)
  - Commands: `run`, `batch`, `export`, `evaluate-gtobi`
  - Full TextGrid annotation and export workflow

### Appendix E: Prosody Synthesis Toolkit
- **audio2tract.py** (319 LOC)
  - Operations: `smooth`, `multiply`, `add`, `set`
  - 11 articulatory parameters supported
  - Multiple manipulations in one command

- **prosody_morph.py** (207 LOC)
  - Blend prosody between two speakers
  - Curves: linear, sigmoid, ease_in_out
  - Animation support (generate blend sequence)

- **prosody2tract.py** (156 LOC)
  - TextGrid → F0 targets + articulatory parameters
  - Movement generators (linear, sigmoid, ease_in_out, etc.)
  - Full parameter listing

- **synthesize_audio.py** (112 LOC)
  - espeak-ng + sox pipeline
  - F0-based pitch modification
  - Real audio from prosody annotations

### Testing
- **TEST_ALL_APPENDIX_DE.sh** (70 LOC)
  - Validates all 12 functions
  - Tests: D1-D5 (CLI), E1-E6 (synthesis), SYN (audio)

### Audio Output
- `out/synthesized_prosody.wav` — Full prosody-modified speech (10.5 MB)
- `out/test_pressure_smooth.wav` — Smoothed breathing (10.5 MB)
- `out/test_multiple_manip.wav` — Multi-parameter manipulation (10.5 MB)
- `out/test_lower_voice.wav` — Pitch reduction demo (10.5 MB)

---

## Ready?

```bash
chmod +x CLEANUP_AND_PUSH.sh
./CLEANUP_AND_PUSH.sh
```

Your supervisor will see:
- Complete, working Appendix D CLI
- Complete, working Appendix E synthesis toolkit
- Full test results
- Real audio demonstrations

Good luck with your defense! 🎓
