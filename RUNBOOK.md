# Runbook — Where Things Stand & What To Do Next

Last updated: 2026-06-13 (after milestone 2 code, before its first real run)

## Status

- [x] **Milestone 1 — text round trip** Mac → LM Studio (`192.168.0.158:1234`),
      verified: EN 630ms, HI 796ms, model `huihui-qwen3-vl-8b-instruct-abliterated`.
- [ ] **Milestone 2 — STT**: code complete on both sides, **never run on the
      Windows box yet**. That's the next action (below).
- [~] **Milestone 3 — TTS** (port 8003): first attempt with Higgs crashed
      (needs SGLang). Re-pointed at **MMS-TTS** backend (EN+HI). Retest with
      step 4 below.
- [~] **Milestone 4 — full voice loop** (`client/voice.py`): STT+LLM verified
      working in the first run (transcribed + replied correctly); only the TTS
      stage failed. Should close once MMS TTS works. Retest with step 5.

## Step 1 — Get the repo onto the Windows box (once)

Pick one:

**A. Git over LAN (preferred — `git pull` keeps working later).**
On the Mac: System Settings → General → Sharing → enable *Remote Login*.
On Windows (PowerShell, in your projects folder):

```powershell
git clone ssh://pushkar@192.168.0.201/Users/pushkar/Desktop/workspace/GithubAssests/VoiceAgent
```

**B. Plain copy** (shared folder / USB) — fine for today; redo manually after
every change on the Mac.

## Step 2 — Start the STT service on Windows

PowerShell, inside the repo:

```powershell
cd VoiceAgent\server
# if uv is missing:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv sync
# once, as Administrator:
netsh advfirewall firewall add rule name="VoiceAgent STT" dir=in action=allow protocol=TCP localport=8001

$env:CUDA_VISIBLE_DEVICES = "2"     # GPU 3; CUDA numbering is 0-based
uv run uvicorn stt_service:app --host 0.0.0.0 --port 8001
```

First run downloads large-v3-turbo (~1.6GB). Wait for:
`[stt] large-v3-turbo loaded on cuda in X.Xs`.

Keep LM Studio running as usual (server on port 1234, network serving on).

## Step 3 — Test from the Mac

```bash
cd ~/Desktop/workspace/GithubAssests/VoiceAgent

# 1. service reachable?
curl http://192.168.0.158:8001/health

# 2. mic → transcript loop (Enter starts/stops a recording, Ctrl-C quits)
uv run python -m client.transcribe_test

# 3. (regression) text chat still works
uv run python -m client.chat --once "hello again"
```

macOS will ask for microphone permission for your terminal on first record —
allow it (System Settings → Privacy & Security → Microphone if you missed it).

**Test script:** one English sentence, one Hindi sentence, one Hinglish
sentence (e.g. "kal meeting hai, can you remind me at 9?"). Check the
transcript text, the detected language, and the timing table. Every run is
appended to `metrics.jsonl` automatically.

**Milestone 2 is done when:** all three transcribe correctly-ish and
server-side inference is well under ~1s for short clips (a 5090 should do a
5s clip in a few hundred ms).

## Step 4 — TTS service (after STT works)

New PowerShell window on the Windows box (same `server/` env):

```powershell
cd VoiceAgent\server
# once, as Administrator:
netsh advfirewall firewall add rule name="VoiceAgent TTS" dir=in action=allow protocol=TCP localport=8003

$env:CUDA_VISIBLE_DEVICES = "1"   # GPU 2
uv run uvicorn tts_service:app --host 0.0.0.0 --port 8003
```

Backend defaults to **MMS-TTS** (small per-language models, fast download).
Wait for `[tts] backend=mms device=cuda ready`, then from the Mac:

```bash
curl http://192.168.0.158:8003/health
# English:
curl -s -X POST http://192.168.0.158:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from the voice agent."}' -o /tmp/en.wav && afplay /tmp/en.wav
# Hindi:
curl -s -X POST http://192.168.0.158:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"नमस्ते, मैं आपका वॉइस एजेंट हूँ।","language":"hi"}' -o /tmp/hi.wav && afplay /tmp/hi.wav
```

(Higgs Audio v3 was deferred — needs SGLang, out of scope now. MMS is the
skeleton voice; see PROJECT.md decisions log. Quality is modest by design.)

## Step 5 — Full voice loop (closes Phase 1)

With all three services up (LM Studio, STT :8001, TTS :8003):

```bash
uv run python -m client.voice
```

Speak; you should hear a reply. The timing table prints a `voice-to-voice`
number (everything between end-of-recording and start-of-playback). Expect
seconds, not milliseconds — it's sequential and non-streaming on purpose;
Phase 2 fixes that. **Phase 1 exit:** EN and HI turns work end-to-end and
metrics.jsonl has the numbers.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `curl /health` hangs/refused | Firewall rule missing (step 2), or service not started, or box IP changed — check `ipconfig`, then `VOICEAGENT_HOST=<new-ip>` on the Mac and update `shared/config.toml` |
| ctranslate2: missing cuDNN/cuBLAS DLLs | In `server/`: `uv add nvidia-cublas-cu12 nvidia-cudnn-cu12`, add their `bin` dirs to PATH |
| ctranslate2 rejects the 5090 (sm_120) | Update: `uv lock --upgrade-package ctranslate2 && uv sync`; worst case `$env:STT_DEVICE="cpu"` to prove plumbing |
| Mac records 0s / silent wav | Mic permission denied, or wrong input device — check `sounddevice.query_devices()` (Yeti was default when built) |
| LM Studio 400 errors | Model not loaded in LM Studio, or thinking model selected — stick to the model in `shared/config.toml` |

## Continuing development (any Claude Code session)

Start the session in this repo and say where you are, e.g.:

> Read PROJECT.md, CLAUDE.md, specs/phase-1-walking-skeleton.md and RUNBOOK.md.
> Milestone 2 testing result: <what happened / paste errors>. Continue.

Then:
- **If milestones 2–4 passed** → update the checkboxes above, commit, and
  start **Phase 2 (streaming)**: write `specs/phase-2-streaming.md` first
  (LLM token streaming, sentence-chunked TTS, playback while generating),
  then implement.
- **If something failed** → paste the exact error into the session; the
  usual suspects are in the table above. The TTS pipeline call in
  `server/tts_service.py` is the least battle-tested code (transformers
  pipeline API for Higgs v3) — expect possible API mismatches there; the
  fix belongs in `synthesize()`, the route contract must not change.

House rules (also in CLAUDE.md): every endpoint via `shared/config.toml`,
every stage timed, every turn logged to `metrics.jsonl`, decisions recorded
in PROJECT.md's Decisions Log with a date.
