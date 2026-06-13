# Phase 1 — Walking Skeleton

**Goal:** one full push-to-talk round trip — mic on the Mac → STT → LLM → TTS →
speaker — across the LAN, non-streaming, with every stage timed. Ugly latency
is fine; invisible latency is not.

**Exit criteria**
- [ ] Speak an English sentence, hear a spoken reply. Same for Hindi.
- [ ] Per-stage timings printed after every turn (record, STT, LLM, TTS,
      playback start) plus total.
- [ ] All model endpoints configurable via one config file (host/port per
      service) — no hardcoded addresses.
- [ ] A `metrics.jsonl` log accumulating one line per turn (timings, transcript,
      reply, models used) — this becomes the Phase 4 bake-off harness's input.

## Architecture (this phase only)

```
Mac (client/)                          Windows box (server/)
┌──────────────────────┐               ┌─────────────────────────────┐
│ terminal app          │   HTTP/LAN   │ STT service   (FastAPI)     │ GPU3
│  push-to-talk record  │ ───────────▶ │   faster-whisper large-v3-  │
│  orchestrator         │              │   turbo  (Qwen3-ASR later)  │
│  audio playback       │ ───────────▶ │ LM Studio     (built-in API)│ GPU1
│  timing + metrics     │ ───────────▶ │ TTS service   (FastAPI)     │ GPU2
└──────────────────────┘               │   Higgs Audio v3            │
                                       └─────────────────────────────┘
```

Plain HTTP request/response everywhere this phase. WebSockets/streaming arrive
in Phase 2 — don't build them yet, but keep the orchestrator's stage interfaces
(`transcribe()`, `complete()`, `synthesize()`) async so streaming slots in
without a rewrite.

## Components

### 1. STT service (Windows, GPU 3)
- FastAPI app: `POST /transcribe` — wav/pcm in → `{text, language, duration_ms}`.
- Start with **faster-whisper large-v3-turbo** (zero-friction, good
  Hindi/Hinglish). Qwen3-ASR is a Phase 4 contender; structure the service so a
  second model behind the same route is a config flag.
- Language hint optional; default autodetect (Hinglish reality).

### 2. LLM (Windows, GPU 1)
- LM Studio's built-in OpenAI-compatible server — no code on our side beyond a
  thin client wrapper around `base_url`.
- Pick any solid instruct model already in LM Studio that handles Hindi; model
  choice is logged in metrics but not a Phase 1 concern.
- System prompt: concise spoken-style replies (TTS reads them verbatim — no
  markdown, no lists).

### 3. TTS service (Windows, GPU 2)
- FastAPI app: `POST /synthesize` — `{text, voice}` → wav bytes.
- **Higgs Audio v3 4B** via the HF transformers TTS pipeline (optimized
  serving is a Phase 5 upgrade). One fixed English+Hindi-capable voice for now.
- If Higgs setup fights back, stub with Kokoro first so the skeleton walks,
  then swap — the route contract doesn't change.

### 4. Client/orchestrator (Mac)
- Terminal app: hold-key or enter-to-toggle recording (`sounddevice`, 16kHz
  mono), then run the three stages sequentially, play reply, print timing
  table, append to `metrics.jsonl`, loop.
- Conversation history kept client-side and sent with each LLM call.
- `shared/config.toml`: hosts/ports/model names. `shared/metrics.py`: timing
  helpers used by client and (later) servers.

## Windows box setup (one-time, documented as we go)

Write `server/SETUP.md` capturing: Python env(s), CUDA/driver state, how each
service starts, which GPU each binds to (`CUDA_VISIBLE_DEVICES`), LM Studio
server settings, Windows firewall openings for the three ports. This doc is a
deliverable — Phase 5 automates what it describes.

## Suggested session-sized milestones

1. Repo skeleton + config + LM Studio round trip from the Mac (text only, no
   audio) — proves LAN + API path.
2. STT service up on the Windows box; Mac records and gets transcripts back.
3. TTS service up (Higgs or Kokoro stub); Mac plays synthesized speech.
4. Full loop + timing table + metrics.jsonl; English and Hindi smoke tests.

## Non-goals (resist)

Streaming, VAD, barge-in, wake words, model bake-offs, web UI, vLLM,
Docker. All have a later phase.
