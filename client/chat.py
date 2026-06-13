"""Milestone 1: text-only chat REPL against LM Studio on the Windows box.

Proves the LAN + OpenAI-compatible API path and exercises the config and
metrics plumbing that the full voice loop will reuse.

  uv run python -m client.chat              # interactive REPL
  uv run python -m client.chat --once "hi"  # single turn, for smoke tests
"""

from __future__ import annotations

import asyncio
import sys

from client.llm import LLMClient
from shared.config import load_config
from shared.metrics import TurnTimer, log_turn

SYSTEM_PROMPT = (
    "You are a friendly voice assistant. Your replies are read aloud by a "
    "text-to-speech engine, so answer in short, natural spoken sentences — "
    "no markdown, no bullet points, no emoji. Reply in the language the user "
    "used: English for English, Hindi for Hindi, and match mixed "
    "Hindi-English (Hinglish) naturally."
)


async def run_turn(llm: LLMClient, history: list[dict], user_text: str) -> str:
    history.append({"role": "user", "content": user_text})
    timer = TurnTimer()

    with timer.stage("llm"):
        completion = await llm.complete(history)

    history.append({"role": "assistant", "content": completion.text})

    print(f"\nagent> {completion.text}\n")
    print(timer.table())
    log_turn(
        {
            "phase": "1-milestone-1",
            "user_text": user_text,
            "reply_text": completion.text,
            "llm_model": completion.model,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "stages_ms": timer.stages,
            "total_ms": timer.total_ms,
        }
    )
    return completion.text


async def main() -> None:
    cfg = load_config()
    llm = LLMClient(cfg.llm)
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"LLM: {cfg.llm.model} @ {cfg.llm.base_url}")

    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--once":
            await run_turn(llm, history, sys.argv[2])
            return

        print("Type a message (Ctrl-D to exit).\n")
        while True:
            try:
                user_text = input("you> ").strip()
            except EOFError:
                break
            if not user_text:
                continue
            await run_turn(llm, history, user_text)
    finally:
        await llm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
