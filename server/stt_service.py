"""STT service for the Windows GPU box (GPU 3).

Wraps faster-whisper behind the route contract from the Phase 1 spec:
POST /transcribe (wav in, JSON out). Qwen3-ASR becomes a second backend
behind the same route in Phase 4.

Run (PowerShell):
    $env:CUDA_VISIBLE_DEVICES = "2"   # GPU 3 in PROJECT.md numbering
    uv run uvicorn stt_service:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import io
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from faster_whisper import WhisperModel

MODEL_NAME = os.environ.get("STT_MODEL", "large-v3-turbo")
DEVICE = os.environ.get("STT_DEVICE", "cuda")
# beam_size 1 trades a sliver of accuracy for latency; bump for bake-offs.
BEAM_SIZE = int(os.environ.get("STT_BEAM_SIZE", "1"))

model: WhisperModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    t0 = time.perf_counter()
    model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type="float16")
    print(f"[stt] {MODEL_NAME} loaded on {DEVICE} in {time.perf_counter() - t0:.1f}s")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "device": DEVICE}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Form(None),  # None = autodetect (Hinglish reality)
):
    data = await audio.read()
    t0 = time.perf_counter()
    segments, info = model.transcribe(
        io.BytesIO(data),
        language=language,
        beam_size=BEAM_SIZE,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return {
        "text": text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "audio_seconds": round(info.duration, 2),
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "model": MODEL_NAME,
    }
