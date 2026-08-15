"""talks to Groq's API. kept seperate from LangGraph entirely, this file
doesn't know graphs exists. It just does one thing: send a system + user
prompt, get text back."""

import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

_override = None    # set by tests only, via set_override() below, never touch in prod
_usage_log = []       # drained by operations.py after each graph run, via drain_usage_log()

def set_override(fn):
    """Test-only hook. Pass a function with the same signature as
    complete() below, or None to go back to the real Groq call."""
    global _override
    _override = fn


def drain_usage_log() -> list[dict]:
    """Returns everything logged since the last drain, and clears it.
    Called once per graph run by operations.py, right after the run
    finishes, to persist usage into cost_log."""
    global _usage_log
    log, _usage_log = _usage_log, []
    return log


async def complete(system: str, prompt: str, stage: str = "unknown") -> str:
    start = time.monotonic()

    if _override is not None:
        text = await _override(system, prompt)
        _usage_log.append({
            "stage": stage,
            "tokens_in": len(prompt.split()),    # crude estimate for fake calls, tests don't check cost accuracy
            "tokens_out": len(text.split()),
            "latency_ms": int((time.monotonic() - start) * 1000),
        })
        return text

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                # temperature=0 means "be as deterministic as possible" —
                # important for extraction/classification tasks where we
                # want consistent structured output, not creative variation.
            },
        )

        resp.raise_for_status()
        # raises an exception immediately if Groq returns an error status instead of silently continuing with a broken resp

        data = resp.json()
        usage = data.get("usage", {})  # Groq's OpenAI-compatible response includes real token counts
        _usage_log.append({
            "stage": stage,
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "latency_ms": int((time.monotonic() - start) * 1000),
        })

        return data["choices"][0]["message"]["content"]