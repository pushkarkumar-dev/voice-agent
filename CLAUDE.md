# VoiceAgent — Session Context

Fully local English+Hindi voice agent (STT → LLM → TTS), built raw (no
voice-agent frameworks) for learning, then hardened for deployment.

**Read `PROJECT.md` first** — vision, hardware, model choices, decisions log,
phase roadmap. Then read the current phase spec in `specs/` and **`RUNBOOK.md`**
for exact current status (milestone checkboxes) and how to run everything.

## Quick facts

- Models run on a Windows box with 3× RTX 5090 on the home LAN; this Mac runs
  the orchestrator + mic/speaker client. Code never assumes localhost GPUs.
- LLM: LM Studio via OpenAI-compatible API — always go through a configurable
  `base_url`, never hardcode a backend (vLLM swap comes in Phase 5).
- STT: Qwen3-ASR (Whisper large-v3-turbo as baseline). TTS: Higgs Audio v3
  (Hindi support is why; Qwen3-TTS has no Hindi). VAD: Silero.
- Latency is the product: instrument every stage, target < 800ms
  voice-to-voice by Phase 3.
- End goals beyond voice: web client with live waveform visualization
  (Phase 5) and Qwen3-VL camera vision (Phase 6) — see PROJECT.md roadmap.

## Working conventions

- One spec per phase in `specs/`, written at phase start. Update
  PROJECT.md's Decisions Log (with date) whenever a real decision is made or
  reversed — that log is the source of truth across sessions.
- Each phase ends runnable; don't start the next phase's features early.
- User is experienced with open-source AI models — skip beginner explanations,
  discuss trade-offs directly.
