"""Multi-backend word-level forced alignment for SpeechPrint.

Each backend is a function that takes (wav_path, transcript_text, language)
and returns an `AlignmentResult` dict with the same shape regardless of
backend, so the rest of the pipeline doesn't have to care which one ran:

    {
        "aligner": "whisperx" | "mfa" | "gentle" | "crisperwhisper",
        "available": bool,            # did the backend actually run?
        "words":   [ {start, end, word, confidence?}, ... ],
        "phones":  [ {start, end, phone}, ... ] | None,   # MFA-only at the moment
        "warnings": [str, ...],
        "duration_s": float,          # of the recording, for sanity checks
        "elapsed_s": float,           # how long the aligner took
    }

If a backend isn't installed / set up, the function returns
`available=False` with a warning explaining what's missing. It does NOT
raise — the pipeline keeps going and just reports that backend as
unavailable.

`run_all()` runs every available backend and returns a list of results
plus a comparison table (per-word start/end from each backend, plus the
mean absolute deviation across backends in seconds).

This module is deliberately import-light at the top level — heavy
imports (torch, transformers, whisperx) happen INSIDE the per-backend
functions so an unavailable backend doesn't break the import of this
module.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def _clean_word(w: str) -> str:
    w = w.strip().lower()
    w = re.sub(r"[^a-zà-ÿ0-9']+", "", w)
    return w


def _norm_transcript(t: str) -> str:
    t = re.sub(r"[^A-Za-zÀ-ÿ0-9' -]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _result_template(aligner: str, duration: float) -> dict:
    return {
        "aligner": aligner,
        "available": False,
        "words": [],
        "phones": None,
        "warnings": [],
        "duration_s": duration,
        "elapsed_s": 0.0,
    }


# ---------------------------------------------------------------------------
# 1. WhisperX
# ---------------------------------------------------------------------------


def align_whisperx(wav: Path, transcript_text: str, language: str = "en",
                   whisper_segments: Optional[list] = None) -> dict:
    """WhisperX align() over Whisper segments. wav2vec2 based.

    If `whisper_segments` is None we'll run a fresh Whisper transcription
    inside WhisperX first. Passing it in saves the transcription step.
    """
    duration = _wav_duration(wav)
    result = _result_template("whisperx", duration)
    t0 = time.time()

    try:
        import whisperx  # type: ignore
    except Exception as e:
        result["warnings"].append(f"whisperx not installed: {e}")
        return result

    try:
        if whisper_segments is None:
            # Use a small Whisper model just to get segment timestamps for align()
            model = whisperx.load_model("tiny", device="cpu", compute_type="int8")
            tr = model.transcribe(str(wav), language=language)
            whisper_segments = tr.get("segments", []) or []

        if not whisper_segments:
            result["warnings"].append("No Whisper segments to align")
            result["elapsed_s"] = time.time() - t0
            return result

        align_model, metadata = whisperx.load_align_model(
            language_code=language, device="cpu",
        )
        aligned = whisperx.align(
            whisper_segments, align_model, metadata, str(wav),
            device="cpu", return_char_alignments=False,
        )
        words = []
        for seg in aligned.get("segments", []) or []:
            for w in seg.get("words", []) or []:
                s = w.get("start")
                e = w.get("end")
                tok = _clean_word(w.get("word") or "")
                if s is None or e is None or not tok or e <= s:
                    continue
                words.append({
                    "start": float(s), "end": float(e),
                    "word": tok, "confidence": float(w.get("score") or 0.0),
                })
        result["available"] = True
        result["words"] = words
        if not words:
            result["warnings"].append("WhisperX align returned no words")
    except Exception as e:
        result["warnings"].append(f"WhisperX align failed: {e}")

    result["elapsed_s"] = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# 2. MFA  (Montreal Forced Aligner)
# ---------------------------------------------------------------------------


# Look in the standard mamba/conda envs people use for MFA, plus a plain
# system install. Order matters — first hit wins.
_MFA_CANDIDATES = [
    "{home}/miniforge3/envs/speechprint-mfa/bin/mfa",
    "{home}/.local/share/mamba/envs/speechprint-mfa/bin/mfa",
    "{home}/mambaforge/envs/speechprint-mfa/bin/mfa",
    "{home}/.local/bin/mfa",
]

_MFA_LANG_MODEL = {
    "en": "english_mfa", "de": "german_mfa", "fr": "french_mfa",
    "es": "spanish_mfa", "it": "italian_mfa", "cs": "czech_mfa",
    "nl": "dutch_mfa", "pt": "portuguese_mfa", "pl": "polish_mfa",
}


def _find_mfa_binary() -> Optional[str]:
    home = os.path.expanduser("~")

    for tpl in _MFA_CANDIDATES:
        path = tpl.format(home=home)

        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    mfa = shutil.which("mfa")

    if mfa:
        return mfa

    fallback = (
        Path.home()
        / "miniforge3"
        / "envs"
        / "speechprint-mfa"
        / "bin"
        / "mfa"
    )

    if fallback.exists():
        return str(fallback)

    return None



def align_mfa(wav: Path, transcript_text: str, language: str = "en") -> dict:
    """Run MFA `align` on a single-file corpus and parse the TextGrid.

    Returns phone intervals too (MFA's main reason for existing).
    """
    duration = _wav_duration(wav)
    result = _result_template("mfa", duration)
    t0 = time.time()

    mfa_bin = _find_mfa_binary()
    if not mfa_bin:
        result["warnings"].append(
            "MFA not found. Run setup_mfa_mamba.sh or install montreal-forced-aligner."
        )
        return result

    if language not in _MFA_LANG_MODEL:
        result["warnings"].append(f"MFA: no preset model for language '{language}'")
        return result

    model = _MFA_LANG_MODEL[language]

    # Build a temp corpus dir
    import tempfile
    workdir = Path(tempfile.mkdtemp(prefix="speechprint_mfa_"))
    corpus = workdir / "corpus"
    out_dir = workdir / "aligned"
    corpus.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    stem = wav.stem
    shutil.copy2(wav, corpus / f"{stem}.wav")
    (corpus / f"{stem}.lab").write_text(_norm_transcript(transcript_text) + "\n",
                                        encoding="utf-8")

    env = os.environ.copy()
    env.setdefault("MFA_ROOT_DIR", os.path.expanduser("~/.local/share/mfa"))
    os.makedirs(env["MFA_ROOT_DIR"], exist_ok=True)

    cmd = [
        mfa_bin, "align",
        str(corpus), model, model, str(out_dir),
        "--clean", "--overwrite", "--single_speaker",
    ]
    try:
        mfa_bin_dir = str(Path(mfa_bin).parent)
        mfa_prefix = str(Path(mfa_bin).parent.parent)

        env["PATH"] = mfa_bin_dir + ":" + env.get("PATH", "")
        env["CONDA_PREFIX"] = mfa_prefix
        env["LD_LIBRARY_PATH"] = str(Path(mfa_prefix) / "lib") + ":" + env.get("LD_LIBRARY_PATH", "")

        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            result["warnings"].append(
                f"MFA align failed (rc={proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-400:]}"
            )
            shutil.rmtree(workdir, ignore_errors=True)
            result["elapsed_s"] = time.time() - t0
            return result
    except subprocess.TimeoutExpired:
        result["warnings"].append("MFA align timed out after 10 minutes")
        shutil.rmtree(workdir, ignore_errors=True)
        result["elapsed_s"] = time.time() - t0
        return result
    except Exception as e:
        result["warnings"].append(f"MFA align error: {e}")
        shutil.rmtree(workdir, ignore_errors=True)
        result["elapsed_s"] = time.time() - t0
        return result

    # Parse the produced TextGrid
    tg_path = next(out_dir.rglob(f"{stem}.TextGrid"), None)
    if not tg_path:
        result["warnings"].append("MFA produced no TextGrid")
        shutil.rmtree(workdir, ignore_errors=True)
        result["elapsed_s"] = time.time() - t0
        return result

    try:
        tiers = _parse_textgrid(tg_path)
        words = []
        for iv in tiers.get("words", tiers.get("word", [])):
            tok = _clean_word(iv["text"])
            if not tok or iv["end"] <= iv["start"]:
                continue
            words.append({"start": iv["start"], "end": iv["end"], "word": tok})
        phones = []
        for iv in tiers.get("phones", tiers.get("phone", [])):
            txt = iv["text"].strip()
            if not txt or txt in {"sp", "sil", "spn", "<eps>"}:
                continue
            if iv["end"] <= iv["start"]:
                continue
            phones.append({"start": iv["start"], "end": iv["end"], "phone": txt})
        result["available"] = True
        result["words"] = words
        result["phones"] = phones
        if not words:
            result["warnings"].append("MFA TextGrid parsed but had no word intervals")
    except Exception as e:
        result["warnings"].append(f"MFA TextGrid parse failed: {e}")

    shutil.rmtree(workdir, ignore_errors=True)
    result["elapsed_s"] = time.time() - t0
    return result


def _parse_textgrid(path: Path) -> dict:
    """Minimal TextGrid parser. Returns {tier_name: [{start, end, text}, ...]}."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    tiers: dict = {}
    blocks = re.split(r"\n\s*item \[\d+\]:", txt)
    for block in blocks:
        nm = re.search(r'name = "([^"]+)"', block)
        if not nm:
            continue
        rows = []
        for m in re.finditer(
            r"intervals \[\d+\]:\s*xmin = ([0-9.eE+-]+)\s*xmax = ([0-9.eE+-]+)\s*text = \"([^\"]*)\"",
            block, flags=re.S,
        ):
            rows.append({
                "start": float(m.group(1)),
                "end": float(m.group(2)),
                "text": m.group(3),
            })
        tiers[nm.group(1)] = rows
    return tiers


# ---------------------------------------------------------------------------
# 3. Gentle  (Kaldi-based, HTTP API)
# ---------------------------------------------------------------------------


_GENTLE_URL = os.environ.get("GENTLE_URL", "http://localhost:8765")


def _gentle_reachable() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(_GENTLE_URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False



def _ensure_gentle_server(timeout: float = 15.0) -> bool:
    if _gentle_reachable():
        return True

    script = Path(__file__).resolve().parent.parent / "lib" / "scripts" / "serve_gentle.sh"

    if not script.exists():
        return False

    try:
        subprocess.Popen(
            ["bash", str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False

    start = time.time()

    while time.time() - start < timeout:
        if _gentle_reachable():
            return True
        time.sleep(0.5)

    return False


def align_gentle(wav: Path, transcript_text: str, language: str = "en") -> dict:
    """Send WAV + transcript to a running Gentle server and parse JSON.

    Gentle's REST API returns a JSON document with a `words` array.
    Each entry has `case` ("success" | "not-found-in-audio" |
    "not-found-in-transcript"), `start`, `end`, `alignedWord`, `word`.
    We only emit successfully-aligned words.
    """
    duration = _wav_duration(wav)
    result = _result_template("gentle", duration)
    t0 = time.time()

    if language != "en":
        result["warnings"].append("Gentle is English-only; skipping")
        return result

    if not _ensure_gentle_server():
        result["warnings"].append(
            f"Gentle server not reachable at {_GENTLE_URL}, and automatic startup failed."
        )
        return result

    try:
        import urllib.request
        # Build multipart/form-data manually so we don't add a 'requests' dep
        boundary = "----SpeechPrintBoundary" + str(int(time.time() * 1000))
        body_parts = []

        def add_field(name: str, value: bytes, filename: Optional[str] = None,
                      content_type: str = "application/octet-stream"):
            disp = f'form-data; name="{name}"'
            if filename:
                disp += f'; filename="{filename}"'
            head = (
                f"--{boundary}\r\n"
                f"Content-Disposition: {disp}\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            body_parts.append(head)
            body_parts.append(value)
            body_parts.append(b"\r\n")

        add_field("audio", wav.read_bytes(), filename=wav.name,
                  content_type="audio/wav")
        add_field("transcript", _norm_transcript(transcript_text).encode("utf-8"),
                  filename="transcript.txt", content_type="text/plain")
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(body_parts)

        req = urllib.request.Request(
            f"{_GENTLE_URL}/transcriptions?async=false",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            payload = json.loads(r.read().decode("utf-8"))

        words = []
        for w in payload.get("words", []):
            case = w.get("case")
            s = w.get("start")
            e = w.get("end")
            tok = _clean_word(w.get("alignedWord") or w.get("word") or "")
            if case != "success" or s is None or e is None or not tok:
                continue
            if e <= s:
                continue
            words.append({"start": float(s), "end": float(e), "word": tok})
        result["available"] = True
        result["words"] = words
        if not words:
            result["warnings"].append("Gentle returned no successful word alignments")
    except Exception as e:
        result["warnings"].append(f"Gentle align failed: {e}")

    result["elapsed_s"] = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# 4. CrisperWhisper
# ---------------------------------------------------------------------------


def align_crisperwhisper(wav: Path, transcript_text: str,
                         language: str = "en") -> dict:
    """Whisper.Crisper / CrisperWhisper backend.

    Preferred path: HuggingFace ASR pipeline with word timestamps.
    Fallback path: plain transcription + approximate word timing so the
    backend remains useful instead of failing the whole comparison.
    """
    duration = _wav_duration(wav)
    result = _result_template("crisperwhisper", duration)
    t0 = time.time()

    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
    except Exception as e:
        result["warnings"].append(f"transformers/torch not installed: {e}")
        return result

    model_id = os.environ.get("CRISPERWHISPER_MODEL_ID", "nyrahealth/CrisperWhisper")

    device = 0 if torch.cuda.is_available() else -1
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    def parse_chunks(chunks):
        words = []
        for c in chunks or []:
            tok_raw = c.get("text") or c.get("word") or ""
            ts = c.get("timestamp") or c.get("timestamps") or (None, None)
            if isinstance(ts, dict):
                s, e = ts.get("start"), ts.get("end")
            else:
                s, e = ts[0], ts[1]
            tok = _clean_word(tok_raw)
            if s is None or e is None or not tok or float(e) <= float(s):
                continue
            words.append({"start": float(s), "end": float(e), "word": tok})
        return words

    try:
        pipe = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            device=device,
            torch_dtype=torch_dtype,
            model_kwargs={"attn_implementation": "eager"},
        )

        try:
            out = pipe(
                str(wav),
                return_timestamps="word",
                generate_kwargs={"language": language, "task": "transcribe"},
            )
            chunks = out.get("chunks") if isinstance(out, dict) else []
            chunks = _crisper_redistribute_pauses(chunks, split_threshold=0.12)
            words = parse_chunks(chunks)

            if words:
                # Post-process real Crisper timestamps:
                # 1. clamp impossible end times to audio duration
                # 2. if Crisper verbatim transcript includes extra words, keep
                #    only the shared transcript token sequence for comparison.
                for w in words:
                    w["start"] = max(0.0, min(float(w["start"]), duration))
                    w["end"] = max(w["start"] + 0.001, min(float(w["end"]), duration))

                target = [_clean_word(x) for x in transcript_text.split()]
                target = [x for x in target if x]
                if target:
                    filtered = []
                    j = 0
                    for w in words:
                        if j < len(target) and w.get("word") == target[j]:
                            filtered.append(w)
                            j += 1
                    if len(filtered) >= max(1, int(0.7 * len(target))):
                        words = filtered

                result["available"] = True
                result["words"] = words
                result["elapsed_s"] = time.time() - t0
                return result

            result["warnings"].append("Whisper.Crisper word timestamp path returned no chunks")

        except Exception as e:
            result["warnings"].append(f"Whisper.Crisper word timestamp path failed: {e}")

        # Fallback: use the shared input transcript tokens, not Crisper's
        # own generated text, so comparison rows stay aligned.
        toks = [_clean_word(x) for x in transcript_text.split()]
        toks = [x for x in toks if x]
        result["warnings"].append(
            "Whisper.Crisper fallback used shared transcript tokens"
        )

        if toks and duration > 0:
            speech_start, speech_end = _speech_span_from_wav(wav)
            usable = max(0.05, speech_end - speech_start)
            weights = [max(1.0, float(len(t))) for t in toks]
            total_w = sum(weights)
            words = []
            cursor = speech_start
            for tok, weight in zip(toks, weights):
                dur = usable * (weight / total_w)
                words.append({
                    "start": float(cursor),
                    "end": float(min(speech_end, cursor + dur)),
                    "word": tok,
                    "confidence": 0.0,
                    "approximate": True,
                })
                cursor += dur
            result["aligner"] = "crisperwhisper_approx"
            result["available"] = True
            result["words"] = words
            result["warnings"].append(
                "Whisper.Crisper used approximate timings because word timestamps failed"
            )
        else:
            result["warnings"].append("Whisper.Crisper fallback produced no words")

    except Exception as e:
        result["warnings"].append(f"Whisper.Crisper failed: {e}")

    result["elapsed_s"] = time.time() - t0
    return result




def _speech_span_from_wav(path: Path, frame_s: float = 0.02) -> tuple[float, float]:
    """Cheap energy VAD: return first/last likely speech time in seconds."""
    try:
        import numpy as np
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            n = w.getnframes()
            raw = w.readframes(n)
            if w.getsampwidth() != 2:
                return 0.0, _wav_duration(path)
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            if w.getnchannels() > 1:
                x = x.reshape(-1, w.getnchannels()).mean(axis=1)
            if len(x) == 0:
                return 0.0, _wav_duration(path)

            frame = max(1, int(sr * frame_s))
            rms = []
            for i in range(0, len(x), frame):
                chunk = x[i:i + frame]
                if len(chunk):
                    rms.append(float(np.sqrt(np.mean(chunk * chunk))))
            if not rms:
                return 0.0, _wav_duration(path)

            rms = np.array(rms)
            peak = float(rms.max())
            if peak <= 0:
                return 0.0, _wav_duration(path)

            thresh = max(peak * 0.08, float(np.percentile(rms, 65)) * 1.5)
            active = np.where(rms >= thresh)[0]
            if len(active) == 0:
                return 0.0, _wav_duration(path)

            start = max(0.0, active[0] * frame_s - 0.08)
            end = min(_wav_duration(path), (active[-1] + 1) * frame_s + 0.08)
            if end <= start:
                return 0.0, _wav_duration(path)
            return start, end
    except Exception:
        return 0.0, _wav_duration(path)


def _crisper_redistribute_pauses(chunks: list, split_threshold: float = 0.12) -> list:
    """Direct port of the helper in CrisperWhisper's README: when two adjacent
    word chunks are separated by a pause, push half the pause onto each side
    (capped at split_threshold) so we don't get hard snap-to-onset artifacts.
    """
    if not chunks:
        return chunks
    adjusted = [dict(c) for c in chunks]
    for i in range(len(adjusted) - 1):
        cur_ts = adjusted[i].get("timestamp") or (None, None)
        nxt_ts = adjusted[i + 1].get("timestamp") or (None, None)
        cs, ce = cur_ts
        ns, ne = nxt_ts
        if None in (cs, ce, ns, ne):
            continue
        pause = ns - ce
        if pause <= 0:
            continue
        give = min(pause / 2.0, split_threshold / 2.0)
        adjusted[i]["timestamp"] = (cs, ce + give)
        adjusted[i + 1]["timestamp"] = (ns - give, ne)
    return adjusted


# ---------------------------------------------------------------------------
# Compare / run-all
# ---------------------------------------------------------------------------


ALIGNER_FNS = {
    "whisperx": align_whisperx,
    "mfa": align_mfa,
    "gentle": align_gentle,
    "crisperwhisper": align_crisperwhisper,
}


def _run_crisper_isolated(wav: Path, transcript_text: str, language: str = "en") -> dict:
    """Run CrisperWhisper in a child process so it cannot freeze the full pipeline."""
    import sys
    import tempfile
    import signal

    duration = _wav_duration(wav)
    fallback = _result_template("crisperwhisper", duration)

    timeout_s = int(os.environ.get("SPEECHPRINT_CRISPER_TIMEOUT", "45"))

    with tempfile.TemporaryDirectory(prefix="speechprint_crisper_") as td:
        td = Path(td)
        transcript_file = td / "transcript.txt"
        json_file = td / "crisper.json"
        transcript_file.write_text(transcript_text, encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "speechprint_pkg.aligners",
            str(wav),
            "--transcript",
            "@" + str(transcript_file),
            "--aligner",
            "crisperwhisper",
            "--language",
            language,
            "--out",
            str(json_file),
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                fallback["warnings"].append(
                    f"CrisperWhisper timed out after {timeout_s}s; skipped"
                )
                return fallback

        except Exception as exc:
            fallback["warnings"].append(f"CrisperWhisper worker failed to start: {exc}")
            return fallback

        if proc.returncode != 0:
            detail = (stderr or stdout or "").strip()
            fallback["warnings"].append(
                f"CrisperWhisper worker failed rc={proc.returncode}: {detail[-500:]}"
            )
            return fallback

        if not json_file.exists():
            detail = (stderr or stdout or "").strip()
            fallback["warnings"].append(
                f"CrisperWhisper worker produced no JSON: {detail[-500:]}"
            )
            return fallback

        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(payload, list) and payload:
                return payload[0]
            fallback["warnings"].append("CrisperWhisper JSON was empty")
            return fallback
        except Exception as exc:
            fallback["warnings"].append(f"Could not parse CrisperWhisper JSON: {exc}")
            return fallback


def run_all(wav: Path, transcript_text: str, language: str = "en",
            include: Optional[list] = None,
            whisper_segments: Optional[list] = None) -> list:
    """Run every requested aligner and return a list of result dicts.

    `include` selects a subset by name; default is all four.
    Whisper.Crisper is isolated because it can be memory-heavy.
    """
    names = include or list(ALIGNER_FNS.keys())
    results = []

    for name in names:
        if name in {"whisper_crisper", "whisper.crisper"}:
            name = "crisperwhisper"

        fn = ALIGNER_FNS.get(name)
        if not fn:
            continue

        if name == "crisperwhisper":
            res = _run_crisper_isolated(wav, transcript_text, language)
        elif name == "whisperx":
            res = fn(wav, transcript_text, language,
                     whisper_segments=whisper_segments)
        else:
            res = fn(wav, transcript_text, language)

        results.append(res)

    return results


def _match_words_by_token(results_by_aligner: dict) -> list:
    """Walk word lists from each aligner in parallel, matching by token order
    where possible. Where the token at position i differs across aligners we
    still align by index (the rows align column-wise, not by content) — the
    user can see the disagreement that way.

    Returns a list of rows, each:
       { "index": i, "tokens": {aligner: token},
         "starts": {aligner: s}, "ends": {aligner: e},
         "mad_start_s": float, "mad_end_s": float }
    """
    n = max((len(r["words"]) for r in results_by_aligner.values()), default=0)
    rows = []
    for i in range(n):
        tokens = {}
        starts = {}
        ends = {}
        for name, res in results_by_aligner.items():
            if i < len(res["words"]):
                w = res["words"][i]
                tokens[name] = w["word"]
                starts[name] = w["start"]
                ends[name] = w["end"]
        s_vals = list(starts.values())
        e_vals = list(ends.values())
        mad_s = _mad(s_vals)
        mad_e = _mad(e_vals)
        rows.append({
            "index": i + 1,
            "tokens": tokens, "starts": starts, "ends": ends,
            "mad_start_s": mad_s, "mad_end_s": mad_e,
        })
    return rows


def _mad(xs: list) -> float:
    """Mean absolute deviation from the mean."""
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    mu = sum(xs) / len(xs)
    return sum(abs(x - mu) for x in xs) / len(xs)


def write_comparison_csv(results: list, out_path: Path) -> int:
    """Write a comparison CSV: one row per word-position, columns for each
    aligner's token/start/end, plus the across-aligner MAD on each boundary.
    Returns row count.
    """
    by_name = {r["aligner"]: r for r in results if r["available"]}
    if not by_name:
        return 0
    rows = _match_words_by_token(by_name)
    aligner_names = list(by_name.keys())
    headers = ["index"]
    for n in aligner_names:
        headers += [f"token_{n}", f"start_{n}", f"end_{n}"]
    headers += ["mad_start_s", "mad_end_s"]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(headers)
        for r in rows:
            row = [r["index"]]
            for n in aligner_names:
                row.append(r["tokens"].get(n, ""))
                row.append(f"{r['starts'].get(n, ''):.4f}" if r["starts"].get(n) is not None else "")
                row.append(f"{r['ends'].get(n, ''):.4f}" if r["ends"].get(n) is not None else "")
            row.append(f"{r['mad_start_s']:.4f}")
            row.append(f"{r['mad_end_s']:.4f}")
            wr.writerow(row)
    return len(rows)


def write_simple_textgrid(words: list, duration: float, out_path: Path,
                          aligner_name: str) -> None:
    """Write a minimal 1-tier TextGrid (`words`) for a single aligner. This
    lets the user open each backend's output independently in Praat for
    comparison.
    """
    # Fill gaps with empty intervals so Praat is happy
    filled = []
    cursor = 0.0
    for w in sorted(words, key=lambda x: x["start"]):
        s, e = float(w["start"]), float(w["end"])
        if s < cursor:
            s = cursor
        if e <= s:
            continue
        if s > cursor:
            filled.append({"start": cursor, "end": s, "text": ""})
        filled.append({"start": s, "end": e, "text": w["word"]})
        cursor = e
    if cursor < duration:
        filled.append({"start": cursor, "end": duration, "text": ""})
    if not filled:
        filled = [{"start": 0.0, "end": max(duration, 0.001), "text": ""}]

    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {duration}",
        "tiers? <exists>",
        "size = 1",
        "item []:",
        "    item [1]:",
        '        class = "IntervalTier"',
        f'        name = "words_{aligner_name}"',
        "        xmin = 0",
        f"        xmax = {duration}",
        f"        intervals: size = {len(filled)}",
    ]
    for i, iv in enumerate(filled, 1):
        txt = iv["text"].replace('"', "'")
        lines += [
            f"        intervals [{i}]:",
            f"            xmin = {iv['start']}",
            f"            xmax = {iv['end']}",
            f'            text = "{txt}"',
        ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def availability_report() -> dict:
    """Quick probe of which backends are installed RIGHT NOW. The GUI uses
    this to tell the user which aligners are usable before they hit Run.
    Each entry is a dict { "installed": bool, "detail": str }.
    """
    report = {}

    # whisperx
    try:
        import whisperx  # noqa: F401
        report["whisperx"] = {"installed": True, "detail": "Python module available"}
    except Exception as e:
        report["whisperx"] = {"installed": False, "detail": f"not importable: {e}"}

    # mfa
    mfa_bin = _find_mfa_binary()
    if mfa_bin:
        report["mfa"] = {"installed": True, "detail": mfa_bin}
    else:
        report["mfa"] = {
            "installed": False,
            "detail": "mfa binary not found (run setup_mfa_mamba.sh)",
        }

    # gentle
    if _gentle_reachable():
        report["gentle"] = {"installed": True, "detail": f"server up at {_GENTLE_URL}"}
    else:
        report["gentle"] = {
            "installed": False,
            "detail": f"server not reachable at {_GENTLE_URL} "
                      "(run setup_gentle.sh and serve_gentle.sh)",
        }

    # crisperwhisper
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        report["crisperwhisper"] = {
            "installed": True,
            "detail": "transformers/torch available "
                      "(model downloads on first use)",
        }
    except Exception as e:
        report["crisperwhisper"] = {
            "installed": False,
            "detail": f"transformers/torch missing: {e}",
        }

    return report


# ---------------------------------------------------------------------------
# CLI entry — useful for ad-hoc tests
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Run a single aligner on one wav and dump JSON.",
    )
    ap.add_argument("wav")
    ap.add_argument("--transcript", required=True,
                    help="Transcript text (or @file.txt to read from file)")
    ap.add_argument("--aligner", choices=list(ALIGNER_FNS.keys()) + ["all", "available"],
                    default="all")
    ap.add_argument("--language", default="en")
    ap.add_argument("--out", default=None,
                    help="Write JSON results to this path instead of stdout")
    args = ap.parse_args()

    if args.aligner == "available":
        print(json.dumps(availability_report(), indent=2))
        raise SystemExit(0)

    transcript = args.transcript
    if transcript.startswith("@"):
        transcript = Path(transcript[1:]).read_text(encoding="utf-8")

    wav = Path(args.wav).resolve()
    if args.aligner == "all":
        out = run_all(wav, transcript, args.language)
    else:
        out = [ALIGNER_FNS[args.aligner](wav, transcript, args.language)]

    blob = json.dumps(out, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(blob, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(blob)


def write_combined_textgrid(results, out_path, duration=None):
    from pathlib import Path
    out_path = Path(out_path)

    usable = []
    max_t = float(duration or 0.0)

    for r in results:
        if not r.get("available"):
            continue

        name = r.get("aligner", "unknown")
        intervals = []

        for w in r.get("words") or []:
            start = float(w.get("start", 0) or 0)
            end = float(w.get("end", 0) or 0)
            text = str(w.get("word", w.get("text", ""))).replace("\"", "'")

            if end > start and text.strip():
                intervals.append((start, end, text))
                max_t = max(max_t, end)

        if intervals:
            usable.append((f"words_{name}", intervals))

    lines = [
        "File type = \"ooTextFile\"",
        "Object class = \"TextGrid\"",
        "",
        "xmin = 0",
        f"xmax = {max_t:.6f}",
        "tiers? <exists>",
        f"size = {len(usable)}",
        "item []:",
    ]

    for i, (tier_name, intervals) in enumerate(usable, 1):
        lines += [
            f"    item [{i}]:",
            "        class = \"IntervalTier\"",
            f"        name = \"{tier_name}\"",
            "        xmin = 0",
            f"        xmax = {max_t:.6f}",
            f"        intervals: size = {len(intervals)}",
        ]

        for j, (start, end, text) in enumerate(intervals, 1):
            lines += [
                f"        intervals [{j}]:",
                f"            xmin = {start:.6f}",
                f"            xmax = {end:.6f}",
                f"            text = \"{text}\"",
            ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
