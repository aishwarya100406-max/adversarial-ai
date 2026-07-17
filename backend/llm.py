import json
import os
from openai import OpenAI

_client: OpenAI | None = None

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    return _client


def call_json(system: str, user: str, model: str = DEFAULT_MODEL, max_tokens: int = 2000) -> dict | list:
    """Call the model and parse a JSON object/array out of its response.

    Instructs the model to respond with ONLY JSON, then extracts the first
    top-level JSON value in the text as a fallback if it wraps it in prose.
    """
    resp = client().chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system + "\n\nRespond with ONLY valid JSON. No prose, no markdown fences."},
            {"role": "user", "content": user},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return _extract_json(text)


def _extract_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # fallback: find first balanced {...} or [...]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == open_ch:
                depth += 1
            elif text[i] == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"Could not parse JSON from model output: {text[:300]}")
