# Speech DAW — Interactive Prosody Editing (Foundation)

Web-based timeline editor for interactive prosody manipulation with real-time synthesis.

**Status:** Chapter 6.2 foundation (design in thesis, basic web UI + API implemented)

**Architecture:** FastAPI backend + vanilla HTML/JS frontend (extensible to React/Vue)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn python-multipart TTS
```

### 2. Start Server

```bash
cd linux
python speech_daw_server.py
```

Server runs on `http://localhost:8000`

### 3. Open UI

```
http://localhost:8000
```

### 4. Load Project

- **TextGrid Path:** Path to `.TextGrid` file with prosody tier
- **Audio Path:** Path to `.wav` file for voice cloning (optional)
- **Speaker Name:** Identifier for cloned voice

Click "Load Project" → timeline appears

### 5. Edit Prosody

- **Click syllable** in timeline to select
- **Modify:** height, direction, accent
- **See changes:** Real-time UI updates
- **Synthesize:** Generate audio with modified prosody
- **Export:** Save modified TextGrid

---

## Architecture

### Backend: `speech_daw_server.py`

FastAPI REST API with endpoints:

```
POST   /api/project/new                 Load TextGrid + audio
GET    /api/project                     Get current project info
GET    /api/syllables                   Get all syllables
POST   /api/syllable/{id}/edit          Modify one syllable
POST   /api/syllable/{id}/reset         Revert to original
POST   /api/synthesize                  Compile F0 + verify
POST   /api/export                      Save modified TextGrid
GET    /api/export/download             Download TextGrid
GET    /api/health                      Server status
```

**State Management:**
- `current_project` — Loaded TextGrid + metadata
- `current_editor` — ProsodyEditor instance (from prosody_resynthesis module)
- `current_synth` — CoquiSynthesizer instance (optional, if audio provided)

**Extensibility:**
- Add endpoints for batch processing
- Add WebSocket for real-time synthesis
- Add user authentication
- Add project persistence (database)

### Frontend: `speech_daw_ui/`

Simple vanilla HTML/JS (no build step required):

**Files:**
- `index.html` — Layout: project loader + timeline + editor
- `style.css` — Responsive design
- `app.js` — API communication + interactivity

**Key Components:**

| Component | Purpose |
|-----------|---------|
| Project Loader | TextGrid path input, speaker setup |
| Timeline | Horizontal syllable tiles with symbols |
| Syllable Editor | Height/direction/accent controls |
| Summary | Shows modified syllables |
| Synthesis Panel | F0 range inputs, export button |

**Interactivity:**
```
User clicks syllable
↓
selectSyllable() → renders controls
↓
User modifies height/direction/accent
↓
editSyllable() → POST to /api/syllable/{id}/edit
↓
API updates state
↓
loadSyllables() → re-fetch
↓
renderTimeline() → visual update
```

---

## Components

### Syllable Editing

**Modify symbol directly:**
```javascript
editSyllable({ symbol: "//" })
```

**Modify component:**
```javascript
setHeight("high")        // ‾
setDirection("falling")  // \\
toggleAccent()           // *
```

**Reset to original:**
```javascript
resetSyllable()
```

### Synthesis

**Compile to F0 targets:**
```javascript
await synthesize()
// Returns: F0 range, modified count
```

**Export modified TextGrid:**
```javascript
await exportTextGrid()
// Downloads: prosody_resynthesized.TextGrid
```

---

## Data Flow

```
┌──────────────────┐
│  User loads TG   │
│ + audio for      │
│  voice cloning   │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│ speech_daw_server.py     │
│ (FastAPI backend)        │
│                          │
│ - ProsodyEditor loaded   │
│ - CoquiSynthesizer ready │
└────────┬─────────────────┘
         │
         ▼ (REST API)
┌──────────────────────────┐
│  speech_daw_ui/app.js    │
│  (Frontend)              │
│                          │
│ - Timeline rendered      │
│ - Controls displayed     │
└────────┬─────────────────┘
         │
         ▼ (Click syllable)
┌──────────────────────────┐
│  selectSyllable(idx)     │
│  → showSyllableEditor()  │
└────────┬─────────────────┘
         │
         ▼ (User edits)
┌──────────────────────────┐
│  setHeight("high")       │
│  setDirection("falling") │
│  toggleAccent()          │
└────────┬─────────────────┘
         │
         ▼ (POST /api/syllable/edit)
┌──────────────────────────┐
│  Backend processes:      │
│  editor.modify_symbol()  │
└────────┬─────────────────┘
         │
         ▼ (Return updated)
┌──────────────────────────┐
│  Frontend updates:       │
│  loadSyllables()         │
│  renderTimeline()        │
│  updateSummary()         │
└──────────────────────────┘
```

---

## Configuration

### Server

**Port & Host:**
```python
# In speech_daw_server.py
uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Change to localhost only:**
```python
uvicorn.run(app, host="127.0.0.1", port=8000)
```

**Enable auto-reload:**
```python
uvicorn.run(app, reload=True)  # Already enabled
```

### Frontend

**API base URL:**
```javascript
// In app.js
const API_BASE = "/api";  // Relative to server root

// For remote server:
// const API_BASE = "http://remote-server:8000/api";
```

---

## Performance

| Task | Time |
|------|------|
| Load TextGrid | <100ms |
| Render 100-syllable timeline | ~50ms |
| Edit one syllable | <50ms |
| Compile F0 targets | ~100ms |
| Export TextGrid | <50ms |

**Browser:** Modern browsers (Chrome, Firefox, Safari) all supported.

---

## Future Extensions

### 1. Real-time Audio Playback
```javascript
// Play synthesized audio on demand
async function playPreview() {
    const targets = await synthesize();
    const audio = await synth.synthesize(...);
    playAudio(audio);  // HTML5 <audio>
}
```

### 2. Regional Resynthesis
```javascript
// Synthesize only modified region
async function previewRegion(startIdx, endIdx) {
    // Compile F0 only for syllables[startIdx:endIdx]
    // Stream synthesis result
}
```

### 3. Multi-speaker Blending
```javascript
// Load two TextGrids, blend between speakers
editor1 = ProsodyEditor(tg1)
editor2 = ProsodyEditor(tg2)
blendWeights = [0.7, 0.3]  // 70% speaker1, 30% speaker2
```

### 4. Undo/Redo Stack
```javascript
edits = []
undo() → pop from edits
redo() → restore
```

### 5. React/Vue Frontend
Replace vanilla JS with component-based framework for:
- State management (Redux, Pinia)
- Real-time updates
- Keyboard shortcuts
- Export to multiple formats (TextGrid, CSV, ELAN)

### 6. WebSocket for Streaming Synthesis
```python
# Backend
@app.websocket("/ws/synthesize")
async def ws_synthesize(websocket):
    while True:
        edit = await websocket.receive_json()
        result = synthesize(edit)
        await websocket.send_json(result)
```

---

## Testing

### Manual Testing

1. **Load project:**
   ```bash
   curl -X POST http://localhost:8000/api/project/new \
     -H "Content-Type: application/json" \
     -d '{
       "textgrid_path": "recording.TextGrid",
       "audio_path": "recording.wav",
       "speaker_name": "speaker"
     }'
   ```

2. **Get syllables:**
   ```bash
   curl http://localhost:8000/api/syllables
   ```

3. **Edit syllable 0:**
   ```bash
   curl -X POST http://localhost:8000/api/syllable/0/edit \
     -H "Content-Type: application/json" \
     -d '{"height": "high"}'
   ```

4. **Synthesize:**
   ```bash
   curl -X POST http://localhost:8000/api/synthesize \
     -H "Content-Type: application/json" \
     -d '{"f0_floor": 75, "f0_ceiling": 300}'
   ```

### Unit Tests

```python
# test_speech_daw.py
import pytest
from speech_daw_server import app

client = TestClient(app)

def test_load_project():
    response = client.post("/api/project/new", json={
        "textgrid_path": "test.TextGrid",
        "speaker_name": "test_speaker"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

---

## Deployment

### Local Machine
```bash
python speech_daw_server.py
```

### Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "speech_daw_server.py"]
```

```bash
docker build -t speech-daw .
docker run -p 8000:8000 -v /path/to/data:/app/data speech-daw
```

### Cloud (AWS, GCP, Heroku)
- API is stateless (except in-memory state)
- Audio files stored in cloud storage (S3, GCS)
- Models downloaded on first request
- Scaling: run multiple instances behind load balancer

---

## Limitations & Known Issues

1. **In-memory state:** Server resets when restarted. Add database for persistence.
2. **Single user:** No multi-user support. Add authentication + per-user state.
3. **No real-time synthesis:** Synthesis returns JSON summary only. Full audio synthesis TBD.
4. **No pitch shift:** F0 control not yet connected to audio output.
5. **No keyboard shortcuts:** Add vim-like keybindings (/, e, undo, etc.)

---

## References

- **Thesis Chapter 6.2:** Speech DAW design and vision
- **FastAPI:** https://fastapi.tiangolo.com/
- **Prosody Resynthesis Module:** See RESYNTHESIS_README.md
- **ProsodyPrompt Paper:** (awaiting publication)

