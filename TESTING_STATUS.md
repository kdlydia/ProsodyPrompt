# Testing Status & Production Readiness

**Last Updated:** 2026-06-10  
**Overall Status:** ⚠️ **Alpha** — Core logic works, integration untested

---

## What Actually Works ✅

### 1. F0 Compiler Module
```python
from prosody_resynthesis.f0_compiler import F0Compiler

compiler = F0Compiler()
targets = compiler.compile_syllable('//', 0.0, 0.5)
# Result: 4 F0Target objects with proper pitch computation
```
**Status:** ✅ **TESTED & WORKING**
- Symbol parsing: ✅
- F0 computation: ✅
- Trajectory generation: ✅
- Semitone-based transitions: ✅

---

### 2. TextGrid I/O Module
```python
from prosody_resynthesis.textgrid_io import TextGridReader

tg = TextGridReader.read('doreco_port1286_2017_06_30_Jaklin.TextGrid')
# Loads TextGrid with 10 tiers successfully
```
**Status:** ✅ **TESTED & WORKING**
- Read TextGrid format: ✅
- Parse tier structure: ✅
- Extract specific tiers: ✅
- Write TextGrid: ⚠️ (written, not tested)

---

### 3. Speech DAW Server
```bash
$ python linux/speech_daw_server.py
Starting Speech DAW Server on http://localhost:8000
API docs: http://localhost:8000/docs
```
**Status:** ⚠️ **STARTS BUT UNTESTED**
- Server starts: ✅
- Uvicorn import: ✅
- API endpoints defined: ✅
- Endpoints tested: ❌

---

## What Doesn't Work Yet ❌

### 1. Prosody Editor (ProsodyEditor class)
**Issue:** Requires TextGrid with prosody tier
```
⚠ No prosody tier found in doreco_port1286_2017_06_30_Jaklin.TextGrid
```
**Why:** Test data (DoReCo) doesn't have prosody annotations yet.  
**Fix:** Run `build_questionnaire_v3.py` first to generate prosody tiers.

### 2. Coqui TTS Integration
```python
from prosody_resynthesis.coqui_interface import CoquiSynthesizer
synth = CoquiSynthesizer()  # Will fail: TTS not installed
```
**Status:** ❌ **NOT INSTALLED**
```bash
pip install TTS  # Not in requirements yet
```
**Fix:** Add to requirements.txt and test

### 3. CLI Tool (resynthesis_cli.py)
**Status:** ❌ **NOT TESTED**
```bash
python linux/resynthesis_cli.py recording.TextGrid --audio recording.wav
# Untested: need TextGrid with prosody tier first
```

### 4. Speech DAW Web UI
**Status:** ❌ **NOT TESTED IN BROWSER**
- HTML/CSS/JS files created: ✅
- Endpoints exist: ✅
- Integration tested: ❌

---

## Test Results Summary

| Component | Imports | Runs | Logic | Integration |
|-----------|---------|------|-------|-------------|
| F0Compiler | ✅ | ✅ | ✅ | - |
| TextGridReader | ✅ | ✅ | ✅ | - |
| TextGridWriter | ✅ | ✅ | ⚠️ | - |
| ProsodyEditor | ✅ | ❌ | ? | ? |
| CoquiSynthesizer | ✅ | ❌ | ? | ? |
| speech_daw_server | ✅ | ✅ | ⚠️ | ❌ |
| resynthesis_cli | ✅ | ❌ | ? | ? |
| speech_daw_ui | ✅ | N/A | ⚠️ | ❌ |

---

## Production Readiness Checklist

### Critical Blockers 🔴

- [ ] **Generate test prosody tier**
  - Run `build_questionnaire_v3.py` to create test TextGrid with prosody
  - Once done: Can test ProsodyEditor, CLI, complete resynthesis

- [ ] **Install Coqui TTS**
  - `pip install TTS` (~2GB download)
  - Test voice cloning + synthesis
  - Verify audio quality

- [ ] **Test end-to-end resynthesis workflow**
  - Load TextGrid with prosody tier
  - Edit symbols
  - Compile F0 targets
  - Generate audio
  - Export TextGrid
  - Verify quality

- [ ] **Test Speech DAW API endpoints**
  - POST /api/project/new
  - GET /api/syllables
  - POST /api/syllable/{id}/edit
  - POST /api/synthesize
  - POST /api/export
  - Verify all return correct JSON

- [ ] **Test Speech DAW web UI in browser**
  - Load project
  - Click syllables
  - Edit height/direction/accent
  - See real-time updates
  - Export works

### Important Issues 🟡

- [ ] **Fix uvicorn deployment**
  - speech_daw_server.py warns about reload without import string
  - Fix: Use proper uvicorn.run() call

- [ ] **Update requirements.txt**
  - Add TTS (Coqui)
  - Add fastapi, uvicorn (already there)
  - Verify all versions compatible

- [ ] **Create test data**
  - Add sample TextGrid with prosody tier to git
  - Or document how to generate it
  - Make quick-start work without manual setup

- [ ] **README commands verification**
  - RESYNTHESIS_README.md: test all commands
  - SPEECH_DAW_README.md: test all commands
  - Fix any broken instructions

- [ ] **Error handling**
  - What if TextGrid missing prosody tier?
  - What if audio file not found?
  - What if TTS not installed?
  - All should give clear error messages

### Nice-to-Have ✅

- [ ] Unit tests (test_resynthesis.py, test_daw_api.py)
- [ ] Integration tests (full workflow)
- [ ] Performance benchmarks
- [ ] Keyboard shortcuts in web UI
- [ ] Audio playback in Speech DAW
- [ ] Undo/redo functionality

---

## How to Complete Testing

### Phase 1: Core Logic (1-2 hours)
1. Run `build_questionnaire_v3.py` to generate prosody tier
2. Test ProsodyEditor with output
3. Test F0 compilation
4. Verify TextGrid write works

### Phase 2: TTS Integration (2-3 hours)
1. Install Coqui: `pip install TTS` (~2GB, ~10 min download)
2. Test CoquiSynthesizer voice cloning
3. Test synthesis with F0 targets
4. Verify audio output quality

### Phase 3: CLI Tool (1 hour)
1. Test resynthesis_cli.py load
2. Test interactive editing
3. Test synthesis
4. Test export
5. Verify output TextGrid is valid

### Phase 4: Web Integration (2 hours)
1. Start speech_daw_server.py
2. Open http://localhost:8000 in browser
3. Test each endpoint via UI
4. Test full workflow (load → edit → export)
5. Verify responsive design on mobile

### Phase 5: Documentation (1 hour)
1. Run all README commands
2. Fix any failures
3. Update with actual output
4. Add troubleshooting section

---

## Dependencies Status

```
✅ INSTALLED:
  - numpy, scipy, soundfile
  - librosa (for pYIN)
  - fastapi, pydantic
  - torch, torchaudio (for CREPE)

⚠️  NOT INSTALLED:
  - TTS (Coqui) - ~2GB, required for synthesis
  - uvicorn (probably in fastapi deps)

❌ NOT CHECKED:
  - parselmouth (Praat interface)
  - textgrid (TextGrid library - we wrote custom parser)
  - whisperx, MFA (for upstream pipeline)
```

---

## Issues Found & Fixes

### Issue 1: Docstring SyntaxWarning
**File:** `linux/prosody_resynthesis/__init__.py` and others
**Problem:** Backslashes in docstrings not escaped
**Fix:** Use raw strings (r"...") or double backslashes

### Issue 2: Uvicorn Warning
**File:** `linux/speech_daw_server.py`
**Problem:** "You must pass the application as an import string to enable 'reload'"
**Fix:** Change `uvicorn.run(app, ...)` to use proper application import string

### Issue 3: Missing Prosody Tier in Test Data
**File:** None (data issue)
**Problem:** Test TextGrids don't have prosody tier
**Fix:** Document requirement to run build_questionnaire_v3.py first

---

## Next Steps

1. **Immediate (Today):** Run tests from Phase 1 above
2. **This week:** Complete Phase 2 (install TTS, test synthesis)
3. **Next week:** Phase 3-5 (CLI, web, docs)

Once all phases complete: **Production Ready** ✅

---

## How to Verify Yourself

Run these commands to check current status:

```bash
# Test F0Compiler
python3 -c "
import sys
sys.path.insert(0, 'linux')
from prosody_resynthesis.f0_compiler import F0Compiler
c = F0Compiler()
targets = c.compile_syllable('//', 0.0, 0.5)
print(f'✅ F0Compiler: {len(targets)} targets generated')
"

# Test TextGrid reader
python3 -c "
import sys
sys.path.insert(0, 'linux')
from prosody_resynthesis.textgrid_io import TextGridReader
tg = TextGridReader.read('linux/doreco_port1286_2017_06_30_Jaklin.TextGrid')
print(f'✅ TextGrid: {len(tg[\"tiers\"])} tiers loaded')
"

# Start Speech DAW server (will warn but start)
python3 linux/speech_daw_server.py &
sleep 2
curl http://localhost:8000/api/health | python3 -m json.tool
kill %1
```

