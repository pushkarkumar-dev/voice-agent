"""TTS service for the Windows GPU box (GPU 2).

Route contract (Phase 1 spec): POST /synthesize {text, language?, voice?}
-> wav bytes. Pluggable backend via the TTS_BACKEND env var:

  mms   (default) — Meta MMS-TTS via transformers VitsModel. Per-language
                    models (eng/hin), tiny, rock-solid, runs in plain
                    torch+transformers. The Phase 1 walking-skeleton voice.
  higgs           — Higgs Audio v3. Kept for the Phase 4 bake-off; its
                    supported self-hosting path is SGLang-Omni, so the
                    transformers attempt here may not work. Not the default.

Run (PowerShell):
    $env:CUDA_VISIBLE_DEVICES = "1"   # GPU 2 in PROJECT.md numbering
    uv run uvicorn tts_service:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import io
import os
import time
import traceback
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

BACKEND = os.environ.get("TTS_BACKEND", "mms").lower()
DEVICE = os.environ.get("TTS_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")

# STT language code (ISO 639-1) -> MMS model suffix (ISO 639-3).
_MMS_LANG = {"en": "eng", "hi": "hin"}
_MMS_DEFAULT = "eng"


class MMSBackend:
    """Lazy-loaded VitsModel per language."""

    name = "mms"

    def __init__(self) -> None:
        self._cache: dict[str, tuple] = {}

    def _get(self, lang3: str):
        if lang3 not in self._cache:
            from transformers import AutoTokenizer, VitsModel

            repo = f"facebook/mms-tts-{lang3}"
            t0 = time.perf_counter()
            model = VitsModel.from_pretrained(repo).to(DEVICE)
            tok = AutoTokenizer.from_pretrained(repo)
            print(f"[tts] loaded {repo} on {DEVICE} in {time.perf_counter()-t0:.1f}s")
            self._cache[lang3] = (model, tok)
        return self._cache[lang3]

    def synthesize(self, text: str, language: str | None) -> tuple[np.ndarray, int]:
        lang3 = _MMS_LANG.get((language or "").lower(), _MMS_DEFAULT)
        model, tok = self._get(lang3)
        inputs = tok(text, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            wav = model(**inputs).waveform  # (1, samples) float32 in [-1, 1]
        audio = wav.squeeze().cpu().numpy()
        return audio, int(model.config.sampling_rate)

    def warmup(self) -> None:
        self._get(_MMS_DEFAULT)


class HiggsBackend:
    """Best-effort Higgs Audio v3 via the transformers TTS pipeline. The
    supported path is SGLang-Omni; this may fail until that's wired up."""

    name = "higgs"

    def __init__(self) -> None:
        from transformers import pipeline

        model = os.environ.get("TTS_MODEL", "bosonai/higgs-audio-v3-tts-4b")
        self._pipe = pipeline("text-to-speech", model=model, device_map="auto",
                              trust_remote_code=True)

    def synthesize(self, text: str, language: str | None) -> tuple[np.ndarray, int]:
        out = self._pipe(text)
        return np.asarray(out["audio"]).squeeze(), int(out["sampling_rate"])

    def warmup(self) -> None:
        pass


backend = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global backend
    backend = HiggsBackend() if BACKEND == "higgs" else MMSBackend()
    backend.warmup()
    print(f"[tts] backend={backend.name} device={DEVICE} ready")
    yield


app = FastAPI(lifespan=lifespan)


class SynthesizeRequest(BaseModel):
    text: str
    language: str | None = None  # STT-detected code, routes MMS voice
    voice: str | None = None     # reserved: cloning later


@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND, "device": DEVICE}


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    t0 = time.perf_counter()
    try:
        audio, rate = backend.synthesize(req.text, req.language)
    except Exception as exc:  # report instead of killing the worker
        traceback.print_exc()
        return JSONResponse(status_code=500,
                            content={"error": f"{type(exc).__name__}: {exc}"})

    buf = io.BytesIO()
    sf.write(buf, audio, rate, format="WAV", subtype="PCM_16")
    return Response(
        content=buf.getvalue(),
        media_type="audio/wav",
        headers={
            "X-Duration-Ms": str(round((time.perf_counter() - t0) * 1000, 1)),
            "X-Audio-Seconds": str(round(len(audio) / rate, 2)),
            "X-Model": backend.name,
        },
    )
