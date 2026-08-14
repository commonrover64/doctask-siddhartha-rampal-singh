"""talks to Groq's API. kept seperate from LangGraph entirely, this file doesn't know graphs exists. It just does one 
thing: send a system + user prompt, get text back."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

_override = None    # set by tests only, via set_override() below, never touch in prod

def set_override(fn):
    """Test-only hook. Pass a function with the same signature as
    complete() below, or None to go back to the real Groq call."""
    global _override
    _override = fn

async def complete(system: str, prompt: str) -> str:

    if _override is not None:
        return await _override(system, prompt)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content":system},
                    {"role": "user", "content":prompt},
                ],
                "temperature": 0,
                # temperature=0 means "be as deterministic as possible" —
                # important for extraction/classification tasks where we
                # want consistent structured output, not creative variation.
            },
        )

        resp.raise_for_status()
        # raises an execption immediately if Groq returns an error status instead of silently continuing with a broken resp

        data = resp.json()

        return data["choices"][0]["message"]["content"]