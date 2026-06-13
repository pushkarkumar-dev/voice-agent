"""Unit tests for shared.text.sentencize — pure text, runs anywhere."""

from __future__ import annotations

import asyncio

from shared.text import sentencize


async def _from_chunks(chunks):
    for c in chunks:
        yield c


def _run(chunks, **kw):
    async def go():
        return [s async for s in sentencize(_from_chunks(chunks), **kw)]
    return asyncio.run(go())


def test_basic_sentences():
    # arrives split across deltas mid-word
    out = _run(["Hello the", "re. How are", " you?"], first_clause_min=99)
    assert out == ["Hello there.", "How are you?"]


def test_hindi_danda():
    out = _run(["नमस्ते।", " आप कैसे हैं?"], first_clause_min=99)
    assert out == ["नमस्ते।", "आप कैसे हैं?"]


def test_decimal_not_split():
    out = _run(["Pi is 3.14 ", "roughly."], first_clause_min=99)
    assert out == ["Pi is 3.14 roughly."]


def test_first_chunk_clause_flush():
    # long first sentence: clause break past the min offset flushes early so
    # audio can start; the comma arrives before the period in the stream
    out = _run(["To be completely honest with you, I think ", "it works."])
    assert out[0] == "To be completely honest with you,"
    assert out[1] == "I think it works."


def test_short_first_clause_not_flushed():
    # comma below the min offset stays attached; no tiny first chunk
    out = _run(["Well honestly, I think it works fine."])
    assert out == ["Well honestly, I think it works fine."]


def test_tail_flushed_without_terminator():
    out = _run(["no punctuation here"], first_clause_min=99)
    assert out == ["no punctuation here"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
