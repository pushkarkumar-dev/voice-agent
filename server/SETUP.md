# Windows GPU Box — Service Setup

Living document: everything needed to bring the model servers up from scratch.
Phase 5 automates whatever this file describes.

## Box

- IP on home LAN: **192.168.0.158** (confirm it's static / DHCP-reserved —
  if it changes, update `shared/config.toml` or set `VOICEAGENT_HOST`)
- 3× RTX 5090 (32GB). Allocation: GPU 1 → LLM, GPU 2 → TTS, GPU 3 → STT.

## LLM — LM Studio (native Windows, GPU 1)  ✅ running

- OpenAI-compatible server on port **1234**, network serving enabled
  (verified reachable from the Mac on 2026-06-13).
- Default model for the agent: `huihui-qwen3-vl-8b-instruct-abliterated`
  (clean instruct — no reasoning tokens, ~650–800ms non-streaming round trip,
  handles Hindi, and doubles as the Phase 6 vision model). The bigger
  `qwen/qwen3.6-27b` and `google/gemma-4-31b` both force thinking mode and
  ignore `chat_template_kwargs`/`/no_think` over the API — unusable for voice
  until LM Studio exposes a reasoning toggle, revisit in Phase 4.
- TODO: pin LM Studio's GPU affinity to GPU 1 once STT/TTS occupy the others.

## STT service (GPU 3) — milestone 2, not yet built

- FastAPI wrapper around faster-whisper large-v3-turbo, port **8001**.
- TODO: Python env, CUDA deps, `CUDA_VISIBLE_DEVICES`, firewall rule for 8001.

## TTS service (GPU 2) — milestone 3, not yet built

- FastAPI wrapper around Higgs Audio v3 4B, port **8002**.
- TODO: env, model download, `CUDA_VISIBLE_DEVICES`, firewall rule for 8002.

## Windows firewall

Port 1234 is already reachable from the LAN. 8001/8002 will need inbound
rules when those services land.
