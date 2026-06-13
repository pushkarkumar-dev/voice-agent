"""TTS service for the Windows GPU box (GPU 2).

Higgs Audio v3 4B through the HF transformers text-to-speech pipeline,
behind the route contract from the Phase 1 spec: POST /synthesize
({text, voice}) -> wav bytes. 24kHz output. Voice cloning and streaming
come later (Phase 2 streams, Phase 5 optimizes serving).

Run (PowerShell):
    $env:CUDA_VISIBLE_DEVICES = "1"   # GPU 2 in PROJECT.md numbering
    uv run uvicorn tts_service:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import io
import os
import time
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

MODEL_NAME = os.environ.get("TTS_MODEL", "bosonai/higgs-audio-v3-tts-4b")

pipe = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
    from transformers import pipeline  # heavy import kept off module load

    t0 = time.perf_counter()
    pipe = pipeline("text-to-speech", model=MODEL_NAME, device_map="auto")
    print(f"[tts] {MODEL_NAME} loaded in {time.perf_counter() - t0:.1f}s")
    yield


app = FastAPI(lifespan=lifespan)


class SynthesizeRequest(BaseModel):
    text: str
    voice: str | None = None  # reserved: voice selection/cloning later


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    t0 = time.perf_counter()
    out = pipe(req.text)
    audio = np.asarray(out["audio"]).squeeze()
    rate = int(out["sampling_rate"])

    buf = io.BytesIO()
    sf.write(buf, audio, rate, format="WAV", subtype="PCM_16")
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    return Response(
        content=buf.getvalue(),
        media_type="audio/wav",
        headers={
            "X-Duration-Ms": str(elapsed_ms),
            "X-Audio-Seconds": str(round(len(audio) / rate, 2)),
            "X-Model": MODEL_NAME,
        },
    )
