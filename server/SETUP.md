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

## STT service (GPU 3) — milestone 2

FastAPI wrapper around faster-whisper large-v3-turbo (`server/stt_service.py`),
port **8001**. First run downloads the model (~1.6GB) to the HF cache.

One-time setup (PowerShell, in the repo's `server/` directory):

```powershell
# install uv if missing:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv sync
# allow the Mac to reach the service (run as Administrator):
netsh advfirewall firewall add rule name="VoiceAgent STT" dir=in action=allow protocol=TCP localport=8001
```

Start the service:

```powershell
$env:CUDA_VISIBLE_DEVICES = "2"   # GPU 3 in our numbering (CUDA is 0-based)
uv run uvicorn stt_service:app --host 0.0.0.0 --port 8001
```

Smoke test from the Mac: `curl http://192.168.0.158:8001/health`, then
`uv run python -m client.transcribe_test` (records mic, prints transcript).

Troubleshooting: if ctranslate2 complains about missing cuDNN/cuBLAS DLLs,
`uv add nvidia-cublas-cu12 nvidia-cudnn-cu12` in `server/` and add their
`bin` dirs to PATH; if the 5090 (Blackwell, sm_120) is rejected, update
ctranslate2 to the latest release. `STT_DEVICE=cpu` works as a slow fallback
to prove the plumbing.

## TTS service (GPU 2) — milestone 3, not yet built

- FastAPI wrapper around Higgs Audio v3 4B, port **8002**.
- TODO: env, model download, `CUDA_VISIBLE_DEVICES`, firewall rule for 8002.

## Windows firewall

Port 1234 is already reachable from the LAN. 8001/8002 will need inbound
rules when those services land.
