# Phase 2 — Streaming

**Goal:** stop waiting for whole stages. Stream LLM tokens, cut them into
sentences as they arrive, synthesize each sentence as it's ready, and play
audio while the rest of the reply is still being generated. The metric that
matters becomes **time-to-first-audio (TTFA)** — end of recording to the first
sound out of the speaker.

Still push-to-talk (VAD/barge-in is Phase 3). Phase 1's `client/voice.py` stays
as the non-streaming baseline for comparison.

**Exit criteria**
- [ ] LLM responses stream (token-by-token) instead of arriving whole.
- [ ] First audio plays before the LLM has finished generating, on
      multi-sentence replies.
- [ ] TTFA logged per turn to `metrics.jsonl`; measurably lower than Phase 1's
      voice-to-voice on the same prompt (once TTS is on the GPU).
- [ ] Sentences play in order, no dropped/duplicated text.
- [ ] EN and HI both work.

## Pipeline

```
record ─▶ STT ─┬─▶ LLM stream ─▶ sentencize ─▶ [sentence queue]
   (PTT)        │                                     │
               t0 = end of record               TTS worker (1, ordered)
                                                       │
                                                 [audio queue]
                                                       │
                                                 play worker ─▶ speaker
```

Three coroutines connected by `asyncio.Queue`s, each closed by a sentinel:
1. **LLM producer** — `llm.stream_complete()` yields text deltas; `sentencize()`
   aggregates them into sentence chunks; each chunk is put on the sentence
   queue. Records first-token and first-sentence timestamps.
2. **TTS worker** — one worker (keeps output ordered), pulls a sentence,
   `tts.synthesize(sentence, language=...)`, puts wav on the audio queue.
3. **Play worker** — pulls wav, plays it (blocking playback in a thread
   executor so the event loop keeps moving). Records first-audio timestamp.

Single TTS worker on purpose: parallel synthesis would reorder sentences.
Parallel-with-reorder-buffer is a later optimization.

## Sentence chunking (`shared/text.py`)

Pure-text, unit-testable, no GPU. `sentencize(deltas)` consumes an async
iterator of token deltas and yields sentence strings:
- Primary boundaries: `। . ! ? \n` (Hindi danda included).
- `.` between two digits is not a boundary (don't split `3.14`).
- **First-chunk latency trick:** only the first chunk may also break on a
  clause boundary (`, ; : —`) once it's ~20+ chars, so audio starts sooner;
  later chunks use full-sentence boundaries only.
- Flush any remainder when the stream ends.

## LLM streaming (`client/llm.py`)

Add `stream_complete(messages) -> AsyncIterator[str]`: same endpoint with
`"stream": true`, parse SSE `data:` lines, yield `choices[0].delta.content`,
stop on `[DONE]`. Keep non-streaming `complete()` (used by `client/chat.py`).

## New metrics (per turn, `phase: "2-streaming"`)

- `ttft_ms` — STT end → first LLM token
- `tt_first_sentence_ms` — STT end → first sentence emitted
- `ttfa_ms` — **end of recording → first audio plays** (the headline number)
- `total_ms` — end of recording → playback finished

## Non-goals (resist)

VAD, barge-in, gapless continuous-stream playback, parallel TTS, wake words,
sub-sentence audio streaming (needs a streaming TTS model — Phase 4+),
web UI. Later phases.

## Prerequisite

Real TTFA gains need TTS on the GPU (Phase 1 left MMS on CPU at ~22s/clip).
The streaming code is correct regardless, but verify the win after the
torch-cu128 fix from RUNBOOK.
