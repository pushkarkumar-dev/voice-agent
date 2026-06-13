"""Unit tests for the endpointer state machine. Pure logic, runs anywhere.

Frames are 32ms. min_speech_ms=200 -> ~7 frames; silence_ms=700 -> ~22 frames.
"""

from __future__ import annotations

from client.endpointer import Endpointer, Event


def _feed(ep, probs):
    return [ep.update(p) for p in probs]


def test_sustained_speech_then_silence_full_turn():
    ep = Endpointer(min_speech_ms=200, silence_ms=700)
    events = _feed(ep, [0.9] * 20 + [0.0] * 30)
    assert events.count(Event.SPEECH_START) == 1
    assert events.count(Event.UTTERANCE_END) == 1
    # 200ms/32ms = 6 frames of speech to start (fires on the 6th, index 5)
    assert events.index(Event.SPEECH_START) == 5


def test_brief_blip_is_not_a_turn():
    # 3 speech frames (~96ms) < 200ms debounce -> nothing
    ep = Endpointer(min_speech_ms=200, silence_ms=700)
    events = _feed(ep, [0.9] * 3 + [0.0] * 30)
    assert all(e is None for e in events)


def test_short_pause_does_not_end_turn():
    ep = Endpointer(min_speech_ms=200, silence_ms=700)
    # speak, pause ~320ms (10 frames < 22), speak again, then long silence
    seq = [0.9] * 10 + [0.0] * 10 + [0.9] * 10 + [0.0] * 30
    events = _feed(ep, seq)
    assert events.count(Event.SPEECH_START) == 1  # one turn, not two
    assert events.count(Event.UTTERANCE_END) == 1


def test_two_separate_turns():
    ep = Endpointer(min_speech_ms=200, silence_ms=700)
    seq = [0.9] * 10 + [0.0] * 30 + [0.9] * 10 + [0.0] * 30
    events = _feed(ep, seq)
    assert events.count(Event.SPEECH_START) == 2
    assert events.count(Event.UTTERANCE_END) == 2


def test_threshold_boundary():
    ep = Endpointer(threshold=0.5, min_speech_ms=200, silence_ms=700)
    # exactly at threshold counts as speech (>=)
    events = _feed(ep, [0.5] * 10 + [0.49] * 30)
    assert Event.SPEECH_START in events
    assert Event.UTTERANCE_END in events


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
