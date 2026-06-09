"""Speech DAW Server: Web backend for interactive prosody editing

REST API for timeline-based prosody editing with real-time synthesis.

Endpoints:
- GET /api/project - Load project
- POST /api/syllables - Get syllables from TextGrid
- POST /api/syllable/{id}/edit - Modify symbol
- POST /api/synthesize - Full synthesis
- POST /api/export - Save TextGrid

Frontend communicates via JSON. Synthesis runs async in background.
"""

from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, WebSocket
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, StreamingResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI required. Run: pip install fastapi uvicorn python-multipart"
    )

from prosody_resynthesis import ProsodyEditor, CoquiSynthesizer
from prosody_resynthesis.utils import detect_speaker_pitch_range


app = FastAPI(
    title="ProsodyPrompt Speech DAW",
    description="Interactive prosody editing with real-time synthesis",
)

# Global state
current_project: Optional[dict] = None
current_editor: Optional[ProsodyEditor] = None
current_synth: Optional[CoquiSynthesizer] = None
synthesis_thread: Optional[threading.Thread] = None


# ── API Models ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    textgrid_path: str
    audio_path: Optional[str] = None
    speaker_name: str = "speaker"


class SyllableEdit(BaseModel):
    index: int
    symbol: Optional[str] = None
    height: Optional[str] = None
    direction: Optional[str] = None
    add_accent: Optional[bool] = None


class SynthesisRequest(BaseModel):
    f0_floor: Optional[float] = None
    f0_ceiling: Optional[float] = None


# ── Project Management ────────────────────────────────────────────────────

@app.post("/api/project/new")
def create_project(req: ProjectCreate):
    """Load a new TextGrid project."""
    global current_project, current_editor, current_synth

    try:
        tg_path = Path(req.textgrid_path)
        if not tg_path.exists():
            raise FileNotFoundError(f"TextGrid not found: {tg_path}")

        # Initialize editor
        editor = ProsodyEditor(
            str(tg_path),
            req.audio_path,
            req.speaker_name,
        )

        # Initialize synthesizer if audio provided
        synth = None
        if req.audio_path:
            synth = CoquiSynthesizer()
            synth.clone_voice(req.audio_path, req.speaker_name)

        # Store state
        current_editor = editor
        current_synth = synth
        current_project = {
            "textgrid_path": str(tg_path),
            "audio_path": req.audio_path,
            "speaker_name": req.speaker_name,
            "duration": editor.prosody_tier.xmax - editor.prosody_tier.xmin,
        }

        return {
            "status": "ok",
            "project": current_project,
            "syllables_count": len(editor.syllables),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/project")
def get_project():
    """Get current project info."""
    if not current_project:
        raise HTTPException(status_code=404, detail="No project loaded")
    return current_project


# ── Syllable Editing ──────────────────────────────────────────────────────

@app.get("/api/syllables")
def get_syllables():
    """Get all syllables with current symbols."""
    if not current_editor:
        raise HTTPException(status_code=404, detail="No project loaded")

    return [
        {
            "index": syl.index,
            "text": syl.text,
            "onset": syl.onset,
            "offset": syl.offset,
            "original_symbol": syl.original_symbol,
            "current_symbol": syl.current_symbol,
            "is_modified": syl.is_modified,
            "components": syl.symbol_components,
        }
        for syl in current_editor.syllables
    ]


@app.post("/api/syllable/{index}/edit")
def edit_syllable(index: int, req: SyllableEdit):
    """Modify a single syllable."""
    if not current_editor:
        raise HTTPException(status_code=404, detail="No project loaded")

    try:
        if req.symbol is not None:
            current_editor.modify_symbol(index, req.symbol)

        if req.height is not None:
            current_editor.modify_height(index, req.height)

        if req.direction is not None:
            current_editor.modify_direction(index, req.direction)

        if req.add_accent is not None:
            current_editor.modify_accent(index, add=req.add_accent)

        syl = current_editor.syllables[index]
        return {
            "status": "ok",
            "syllable": {
                "index": syl.index,
                "text": syl.text,
                "current_symbol": syl.current_symbol,
                "is_modified": syl.is_modified,
                "components": syl.symbol_components,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/syllable/{index}/reset")
def reset_syllable(index: int):
    """Reset a syllable to original symbol."""
    if not current_editor:
        raise HTTPException(status_code=404, detail="No project loaded")

    try:
        syl = current_editor.syllables[index]
        syl.reset()
        return {
            "status": "ok",
            "syllable": {
                "index": syl.index,
                "current_symbol": syl.current_symbol,
                "is_modified": syl.is_modified,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Synthesis ─────────────────────────────────────────────────────────────

@app.post("/api/synthesize")
def synthesize(req: SynthesisRequest):
    """Synthesize with current edits."""
    if not current_editor:
        raise HTTPException(status_code=404, detail="No project loaded")
    if not current_synth:
        raise HTTPException(status_code=400, detail="No audio loaded for synthesis")

    try:
        # Compile F0 targets
        targets = current_editor.compile_to_f0_targets(
            f0_floor=req.f0_floor,
            f0_ceiling=req.f0_ceiling,
        )

        f0_vals = [t.f0 for t in targets]
        f0_times = [t.time for t in targets]

        # Get summary
        return {
            "status": "ok",
            "f0_targets_count": len(targets),
            "f0_range": {
                "floor": min(f0_vals),
                "ceiling": max(f0_vals),
            },
            "modified_count": len(current_editor.get_modified_syllables()),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Export ────────────────────────────────────────────────────────────────

@app.post("/api/export")
def export_textgrid(output_filename: str = "prosody_resynthesized.TextGrid"):
    """Export modified TextGrid."""
    if not current_editor:
        raise HTTPException(status_code=404, detail="No project loaded")

    try:
        output_path = Path("out") / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        current_editor.export_to_textgrid(str(output_path))

        return {
            "status": "ok",
            "output_path": str(output_path),
            "size_bytes": output_path.stat().st_size,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/export/download")
def download_export():
    """Download last exported TextGrid."""
    export_path = Path("out/prosody_resynthesized.TextGrid")
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="No export file found")

    return FileResponse(
        export_path,
        filename="prosody_resynthesized.TextGrid",
        media_type="text/plain",
    )


# ── Health & Status ───────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """Server health check."""
    return {
        "status": "ok",
        "project_loaded": current_project is not None,
        "synth_ready": current_synth is not None,
    }


# ── Static Files & UI ─────────────────────────────────────────────────────

ui_dir = Path(__file__).parent / "speech_daw_ui"
if ui_dir.exists():
    app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

    @app.get("/")
    def serve_ui():
        """Serve main UI page."""
        index_path = ui_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Speech DAW UI (index.html not found; use /api)"}
else:
    @app.get("/")
    def serve_ui():
        return {"message": "Speech DAW API (no UI loaded)"}


if __name__ == "__main__":
    import uvicorn

    print("Starting Speech DAW Server on http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    print("ReDoc: http://localhost:8000/redoc")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
