"""Streaming sentence aggregation for the Phase 2 pipeline.

Turns a stream of LLM token deltas into sentence-sized chunks suitable for
per-sentence TTS. Pure text, no GPU — unit-test it directly.
"""

from __future__ import annotations

from typing import AsyncIterator

# Sentence enders: Hindi danda + Western terminals + newline.
_PRIMARY = set("।.!?\n")
# First-chunk-only early-flush points, to start audio sooner.
_CLAUSE = set(",;:—")


def _boundary(buf: str, clause_min: int | None) -> int | None:
    """Index just past the earliest acceptable break in buf, or None.

    clause_min: if set, the first chunk may also break on a clause mark at or
    after this character offset; if None, only sentence terminators count.
    """
    for i, ch in enumerate(buf):
        if ch in _PRIMARY:
            # don't split decimals like 3.14 (only when both neighbours exist)
            if (
                ch == "."
                and 0 < i < len(buf) - 1
                and buf[i - 1].isdigit()
                and buf[i + 1].isdigit()
            ):
                continue
            return i + 1
    if clause_min is not None:
        for i, ch in enumerate(buf):
            if ch in _CLAUSE and i + 1 >= clause_min:
                return i + 1
    return None


async def sentencize(
    deltas: AsyncIterator[str], first_clause_min: int = 20
) -> AsyncIterator[str]:
    """Yield sentence chunks from a stream of token deltas, in order."""
    buf = ""
    emitted = False
    async for delta in deltas:
        buf += delta
        while True:
            clause_min = None if emitted else first_clause_min
            idx = _boundary(buf, clause_min)
            if idx is None:
                break
            chunk = buf[:idx].strip()
            buf = buf[idx:].lstrip()
            if chunk:
                emitted = True
                yield chunk
    tail = buf.strip()
    if tail:
        yield tail
