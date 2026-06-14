from __future__ import annotations

import json
import urllib.request

from .config import OPENAI_API_KEY, OPENAI_MODEL, USE_OPENAI_SYNTHESIS

SYSTEM_PROMPT = """You are a credit dataroom assistant. Use only supplied evidence. Do not invent financial figures, charges, ownership, lenders or dates. Keep answers concise and cite evidence."""

def synthesize_with_openai(question: str, evidence: list[dict]) -> str | None:
    if not USE_OPENAI_SYNTHESIS or not OPENAI_API_KEY:
        return None
    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}\nEvidence JSON: {json.dumps(evidence)[:12000]}"},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("output_text")
