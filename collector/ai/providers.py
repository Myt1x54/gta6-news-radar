"""Low-level AI provider calls. Each returns raw response text (expected JSON).

Imports of the provider SDKs are lazy so the rest of the collector and the unit
tests don't require them installed.
"""

from __future__ import annotations

from config import GEMINI_API_KEY, GROQ_API_KEY


def call_gemini(system: str, user: str, model: str, temperature: float = 0.7) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    return resp.text or ""


def call_groq(system: str, user: str, model: str, temperature: float = 0.7) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""
