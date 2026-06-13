# VoiceAgent — Local STT → LLM → TTS Voice Agent

A fully local, bilingual (English + Hindi) voice agent built from scratch as a
learning project, then hardened for deployment. No cloud APIs anywhere in the
audio or language path.

## Vision

Talk naturally to an agent running entirely on home hardware. The bar for
"feels alive" is **< 800ms voice-to-voice latency** (user stops speaking →
agent audio starts), with streaming at every stage and clean barge-in
(interrupting the agent mid-sentence works).

Goals, in order:
1. **Learning** — build the pipeline raw (Python, asyncio, websockets) so every
   moving part is visible. No voice-agent frameworks in this repo.
2. **Deployment** — by the end, a hardened service the whole house can talk to.
   (A framework-based rebuild — Pipecat/LiveKit — is a separate future project.)
3. **Web client with live sound-wave visualization** — a website that animates
   a waveform while the agent listens/speaks (Web Audio `AnalyserNode` +
   canvas). Lands in Phase 5.
4. **Vision** — a low-fps, low-res camera feed through Qwen3-VL so the agent
   can see as well as hear. Lands in Phase 6.

## Hardware & Topology

| Machine | Role |
|---|---|
| Windows box, 3× RTX 5090 (32GB each), home LAN | Model servers (STT, LLM, TTS) |
| Mac (this repo's dev machine) | Orchestrator + mic/speaker client |

GPU allocation: **#1 → LLM (LM Studio)**, **#2 → TTS (Higgs Audio v3)**,
**#3 → STT + VAD + experiments** (and Qwen3-VL from Phase 6 — STT at 1.7B
leaves ample room on 32GB). LAN hop adds ~1–5ms per leg — negligible.

## Model Choices (decided 2026-06-12)

| Stage | Primary | Alternates / bake-off | Why |
|---|---|---|---|
| STT | Qwen3-ASR 1.7B (Jan 2026) | Whisper large-v3-turbo (phase-1 baseline, frictionless via faster-whisper) | Open SOTA, 52 languages incl. Hindi, timestamps |
| LLM | LM Studio (OpenAI-compatible API), model TBD per session | Ollama, then vLLM (WSL2) for deployment phase | Already in use on the Windows box; API-compatible swap later |
| TTS | **Higgs Audio v3 4B** (chat-native, HF transformers pipeline; 24kHz wav out) | Kokoro (tiny/fast debug baseline) | Only top-tier open TTS with Hindi (85 production-quality of 100+ languages). Qwen3-TTS **rejected**: no Hindi (10 langs only) |
| VAD | Silero VAD | — | De-facto standard |

NVIDIA Parakeet rejected: English-only, and we need Hindi + Hinglish
code-switching.

## Decisions Log

- **2026-06-12** — Raw pipeline first; framework rebuild is a *separate future
  project*, not a phase here.
- **2026-06-12** — Languages: English + Hindi (incl. code-switched Hinglish).
- **2026-06-12** — LLM serving: LM Studio native Windows now; vLLM under WSL2
  later. All pipeline code talks only to an OpenAI-compatible `base_url` so the
  swap is config-only.
- **2026-06-12** — TTS: Higgs Audio v3 (Hindi support decided it).
- **2026-06-12** — Phase-1 client: terminal app on the Mac over LAN.
  Browser/WebRTC client deferred to Phase 5 (default assumption — revisit).
- **2026-06-13** — End goals expanded: web client must include live waveform
  visualization (Phase 5); vision via Qwen3-VL on a low-fps/low-res camera
  feed added as Phase 6.
- **2026-06-13** — Default LLM: `huihui-qwen3-vl-8b-instruct-abliterated`.
  The larger qwen3.6-27b / gemma-4-31b on the box are thinking models whose
  reasoning can't be disabled through LM Studio's API (tried
  `chat_template_kwargs` and `/no_think`) — reasoning tokens are unusable for
  voice latency. Revisit model choice in Phase 4.
- **2026-06-13** — Serving stacks constrained to what's familiar: LM Studio,
  Ollama, llama.cpp, vLLM, HF transformers. **No SGLang.**
- **2026-06-13** — **Higgs Audio v3 deferred as Phase-1 TTS.** Its only
  documented self-hosting path is SGLang-Omni; the model card's
  `pipeline("text-to-speech")` example crashes (custom multi-codebook arch,
  not a standard TTS pipeline). Walking-skeleton TTS is now **Meta MMS-TTS**
  (`facebook/mms-tts-eng` / `-hin`) via the transformers `VitsModel` —
  rock-solid, runs in plain torch+transformers, covers EN+HI. Modest quality,
  but Phase 1 is about plumbing. Revisit Higgs (and Qwen3-TTS quality) in the
  Phase 4 bake-off; if Higgs still needs SGLang then, weigh SGLang-via-WSL2 as
  a one-off exception vs. another high-quality multilingual TTS. The TTS route
  contract (`POST /synthesize`) is unchanged, so the swap is server-internal.
- **2026-06-13** — Open (decide at Phase 6 start): Qwen3-VL as the *brain*
  (replaces the text LLM, agent natively sees) vs *sidecar captioner* feeding
  frame descriptions into the text LLM's context. Sidecar is simpler; brain is
  cleaner and saves a hop.

## Latency Budget (target, hands-free steady state)

| Stage | Target |
|---|---|
| Endpointing (silence → "turn over" decision) | ~200ms |
| STT final transcript (streaming, mostly amortized) | ~100ms |
| LLM time-to-first-sentence | ~250ms |
| TTS time-to-first-audio | ~150ms |
| Network + playback buffer | ~100ms |
| **Total voice-to-voice** | **~800ms** |

Measure from Phase 1 onward; every phase has a latency exit criterion.

## Phase Roadmap

Each phase ends with something runnable. One spec per phase in `specs/`,
written at the start of that phase (multi-session friendly — any session can
pick up from PROJECT.md + the current phase spec).

- **Phase 1 — Walking skeleton** (`specs/phase-1-walking-skeleton.md`):
  push-to-talk, non-streaming. Mic → STT → LM Studio → TTS → speaker, over
  LAN. Latency instrumentation from day one. *Exit: full round trip works;
  every stage timed.*
- **Phase 2 — Streaming**: LLM token streaming, sentence-chunked TTS, audio
  plays while text still generating. *Exit: voice-to-voice < 1.5s
  push-to-talk.*
- **Phase 3 — Hands-free**: Silero VAD, endpointing, barge-in (interrupt →
  cancel LLM + flush TTS + stop playback cleanly). *Exit: natural
  conversation, no buttons, interruptions work.*
- **Phase 4 — Model bake-off**: Qwen3-ASR vs Whisper on English/Hindi/Hinglish;
  latency + WER harness; Hindi TTS quality eval. *Exit: data-backed final
  model picks.*
- **Phase 5 — Deployment hardening + web client**: vLLM (WSL2) for the LLM,
  optimized Higgs serving (vLLM if supported, else tuned transformers),
  service supervision/auto-start on the Windows box; browser client
  (WebSocket/WebRTC audio) with live sound-wave visualization (Web Audio
  `AnalyserNode` + canvas) for both listening and speaking states. *Exit:
  survives reboots, usable from any device at home, waveform animates with
  the conversation.*
- **Phase 6 — Vision**: camera capture at low fps/low res (~1 frame per 1–2s),
  Qwen3-VL on GPU 3; settle the brain-vs-sidecar-captioner decision; agent can
  answer "what do you see?" and weave ambient visual context into
  conversation. *Exit: voice agent responds to questions about the live
  scene without breaking the latency budget for pure-voice turns.*

## Repo Layout (grows over time)

```
PROJECT.md          ← this file: vision, decisions, roadmap
CLAUDE.md           ← session pickup context
specs/              ← one spec per phase
server/             ← code that runs on the Windows box (STT/TTS wrappers)
client/             ← Mac-side orchestrator + terminal client
shared/             ← protocol definitions, metrics
```
