from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import PROJECT_ROOT


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    model: str
    enabled: bool
    openai_api_key_present: bool
    gemini_api_key_present: bool
    ollama_base_url: str


def llm_settings() -> LlmSettings:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "deterministic").strip().lower()
    enabled = os.getenv("ASSISTANT_USE_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}
    model = os.getenv("MODEL_NAME", "").strip()
    if provider == "ollama" and not model:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    elif provider == "gemini" and not model:
        model = "gemini-2.0-flash"
    elif provider == "openai" and not model:
        model = "gpt-4.1-mini"
    return LlmSettings(
        provider=provider,
        model=model or "deterministic",
        enabled=enabled,
        openai_api_key_present=bool(os.getenv("OPENAI_API_KEY")),
        gemini_api_key_present=bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
