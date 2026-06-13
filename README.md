# VoiceAgent

A fully **local, bilingual (English + Hindi) voice agent**: speak to it, and it
speaks back — STT → LLM → TTS, with no cloud APIs anywhere in the audio or
language path. Built from scratch (raw Python, no voice-agent frameworks) as a
learning project, then hardened toward deployment.

> **Status:** Phase 1 (walking skeleton) works end-to-end in English. See
> [`RUNBOOK.md`](RUNBOOK.md) for exact milestone status and how to run it.

## How it works

```
   Mac (client/)                         Windows box, 3× RTX 5090 (server/)
┌─────────────────────┐                ┌──────────────────────────────────┐
│ mic capture          │  record       │                                  │
│ orchestrator ────────┼──HTTP/LAN────▶ │ STT   faster-whisper   :8001 GPU3│
│ playback             │ ──────────────▶│ LLM   LM Studio        :1234 GPU1│
│ timing + metrics     │ ──────────────▶│ TTS   MMS-TTS          :8003 GPU2│
└─────────────────────┘                └──────────────────────────────────┘
```

The Mac runs the orchestrator and the mic/speaker client; all models run on a
Windows GPU box across the home LAN. The pipeline only ever talks to
configurable endpoints, so any service can move or be swapped without code
changes.

## Models

| Stage | Current | Notes |
|-------|---------|-------|
| **STT** | faster-whisper `large-v3-turbo` | Qwen3-ASR is a Phase 4 bake-off contender |
| **LLM** | LM Studio (OpenAI-compatible API) | `qwen3-vl-8b-instruct`; any OpenAI-compatible backend (Ollama, vLLM) drops in |
| **TTS** | Meta MMS-TTS (`mms-tts-eng`/`-hin`) | Walking-skeleton voice; Higgs Audio v3 / Qwen3-TTS evaluated in Phase 4 |
| **VAD** | Silero (Phase 3) | For hands-free turn detection |

## Quick start

Models run on the Windows box; the client runs on the Mac. Full setup,
including the Windows-side service commands and firewall rules, is in
[`server/SETUP.md`](server/SETUP.md) and [`RUNBOOK.md`](RUNBOOK.md).

```bash
# on the Mac, in the repo root:
uv sync

# text-only chat (verifies the LAN + LLM path):
uv run python -m client.chat

# record → transcribe (needs the STT service up):
uv run python -m client.transcribe_test

# full voice loop (needs STT + LLM + TTS up):
uv run python -m client.voice
```

Endpoints live in [`shared/config.toml`](shared/config.toml); override the GPU
box's address without editing the file via `VOICEAGENT_HOST=x.x.x.x`.

## Roadmap

Latency is the product — the target is **< 800ms voice-to-voice**. Each phase
ends with something runnable; specs live in [`specs/`](specs/).

1. **Walking skeleton** — push-to-talk, non-streaming, end-to-end. ✅ (EN)
2. **Streaming** — LLM token streaming + sentence-chunked TTS; audio plays
   while the reply is still generating.
3. **Hands-free** — Silero VAD, endpointing, barge-in (interrupt mid-reply).
4. **Model bake-off** — Qwen3-ASR vs Whisper; Higgs/Qwen3-TTS quality on
   EN/HI/Hinglish, scored with the latency + WER harness.
5. **Deployment + web client** — vLLM serving, auto-start on reboot, browser
   client with live sound-wave visualization.
6. **Vision** — low-fps camera through Qwen3-VL so the agent can see as well
   as hear.

## Repo layout

```
PROJECT.md     vision, hardware, model decisions (with dated log), roadmap
RUNBOOK.md     current status + step-by-step run/test instructions
CLAUDE.md      session pickup context
specs/         one spec per phase
server/        services for the Windows GPU box (STT, TTS) + SETUP.md
client/        Mac-side orchestrator, mic/speaker, per-stage clients
shared/        config + per-turn metrics
```

## Hardware

- **Windows box:** 3× RTX 5090 (32GB each) on the home LAN — runs all models.
- **Mac:** orchestrator + mic/speaker client.

All open-source, all local.
