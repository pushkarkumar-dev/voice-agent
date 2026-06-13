"""Per-turn timing instrumentation. Latency is the product: every stage of
every turn gets timed, and every turn appends one line to metrics.jsonl —
that file later feeds the Phase 4 model bake-off."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

METRICS_PATH = Path(__file__).parent.parent / "metrics.jsonl"


class TurnTimer:
    """Collects named stage durations for one conversation turn."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._turn_start = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = round((time.perf_counter() - start) * 1000, 1)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._turn_start) * 1000, 1)

    def table(self) -> str:
        lines = [f"  {name:<12} {ms:>8.1f} ms" for name, ms in self.stages.items()]
        lines.append(f"  {'total':<12} {self.total_ms:>8.1f} ms")
        return "\n".join(lines)


def log_turn(record: dict, path: Path = METRICS_PATH) -> None:
    record["ts"] = datetime.now(timezone.utc).isoformat()
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
