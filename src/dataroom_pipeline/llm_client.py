from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict

from .settings import llm_settings


def provider_status() -> dict[str, object]:
    settings = llm_settings()
    ready = False
    reason = "LLM synthesis disabled; deterministic assistant is active."
    if settings.enabled:
        if settings.provider == "ollama":
            ready = True
            reason = "Local Ollama provider selected. No API key or card required."
        elif settings.provider == "openai" and settings.openai_api_key_present:
            ready = True
            reason = "OpenAI provider selected with API key present."
        elif settings.provider == "gemini" and settings.gemini_api_key_present:
            ready = True
            reason = "Gemini provider selected with API key present."
        else:
            reason = f"Provider {settings.provider!r} is selected but required configuration is missing."
    return {**asdict(settings), "ready": ready, "reason": reason}


def synthesize(system_prompt: str, user_prompt: str) -> str | None:
    settings = llm_settings()
    if not settings.enabled:
        return None
    try:
        if settings.provider == "ollama":
            return _ollama(settings.model, system_prompt, user_prompt, settings.ollama_base_url)
        if settings.provider == "openai" and settings.openai_api_key_present:
            return _openai(settings.model, system_prompt, user_prompt)
        if settings.provider == "gemini" and settings.gemini_api_key_present:
            return _gemini(settings.model, system_prompt, user_prompt)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None
    return None


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _ollama(model: str, system_prompt: str, user_prompt: str, base_url: str) -> str | None:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = _post_json(f"{base_url.rstrip('/')}/api/chat", payload)
    return response.get("message", {}).get("content")


def _openai(model: str, system_prompt: str, user_prompt: str) -> str | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    response = _post_json(
        "https://api.openai.com/v1/chat/completions",
        payload,
        {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
    )
    return response["choices"][0]["message"]["content"]


def _gemini(model: str, system_prompt: str, user_prompt: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    response = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        payload,
    )
    return response["candidates"][0]["content"]["parts"][0]["text"]
