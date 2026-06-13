# Phase 3 — Hands-Free

**Goal:** drop the keyboard. The agent listens continuously, decides on its own
when you've finished a sentence (endpointing), and — optionally — lets you cut
it off mid-reply (barge-in). This is the phase where conversation starts to feel
natural, and where the coordination is genuinely hard.

VAD runs locally on the Mac (Silero, CPU — tiny). The model services on the
Windows box are unchanged.

**Exit criteria**
- [ ] No key presses: speak, pause, and the agent responds on its own.
- [ ] Endpointing feels right — it waits out natural pauses but doesn't hang
      for seconds after you stop. First word isn't clipped (pre-roll buffer).
- [ ] Barge-in mode: talking over the agent stops its speech promptly and your
      new utterance becomes the next turn.
- [ ] EN and HI both work.

## The echo problem (read this first)

If the agent's voice plays through **speakers**, the mic hears it and VAD
thinks *you're* talking — false barge-in, the agent cuts itself off. Real fix
is acoustic echo cancellation (out of scope here). So Phase 3 ships two modes:

- **half-duplex (default)** — the mic is ignored while the agent is speaking.
  Robust on speakers. No barge-in.
- **barge-in (opt-in, `--barge-in`)** — mic stays live during playback; best
  with **headphones**, otherwise echo causes self-interruption.

## Components

### `client/vad.py` — Silero wrapper
`SileroVAD.prob(frame_int16[512]) -> float` speech probability per 32ms window
(512 samples @ 16kHz). `reset()` clears model state between utterances.

### `client/endpointer.py` — turn-taking state machine (pure, unit-tested)
Consumes per-frame probabilities, emits `SPEECH_START` and `UTTERANCE_END`:
- `threshold` (~0.5) — speech vs. not.
- `min_speech_ms` (~200) — debounce; ignore blips so a cough isn't a turn.
- `silence_ms` (~700) — trailing silence that declares the turn over
  (the endpointing delay; the main feel knob).
No audio, no I/O — just float in, events out. Fully testable with synthetic
probability sequences.

### `client/listener.py` — continuous capture
Always-open `sounddevice` input stream, 512-sample blocks → `SileroVAD` →
`Endpointer`. Keeps a ~300ms **pre-roll** ring buffer so the first word isn't
clipped. Emits events to an async queue: `('start',)` and
`('utterance', wav_bytes)`. Bridges the audio callback thread to asyncio.

### `client/player.py` — interruptible playback
Wraps the audio output so it can be **stopped immediately** (`stop()`), and
exposes `is_playing`. Replaces Phase 2's blocking `play_wav` in the hands-free
loop so barge-in can cut playback off.

### `client/voice_hands_free.py` — the loop
One always-on capture task feeding events; a cancellable `respond()` task per
turn running the Phase 2 streaming pipeline (STT → stream LLM → sentence TTS →
player).
- **half-duplex:** stop feeding the endpointer while `player.is_playing`.
- **barge-in:** keep feeding; on `SPEECH_START` during a response, `stop()` the
  player and cancel the `respond()` task, then respond to the new utterance.

## Reuse

STT/LLM/TTS clients, `sentencize`, and the streaming pipeline shape come
straight from Phase 2. New code is VAD + endpointing + interruptible playback
+ the event-driven loop. `client/voice.py` (P1) and `client/voice_stream.py`
(P2) stay as-is for comparison.

## Non-goals (resist)

Wake word, acoustic echo cancellation, speaker diarization, multi-turn memory
beyond the running history, web UI, model bake-offs. Later or out of scope.
