from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT_DIR = PROJECT_ROOT / "backend"
DATAROOM_DIR = PROJECT_ROOT / "dataroom"
MANIFEST_PATH = DATAROOM_DIR / "manifest.json"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'backend' / 'dataroom.sqlite'}")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
USE_OPENAI_SYNTHESIS = os.getenv("USE_OPENAI_SYNTHESIS", "false").lower() in {"1", "true", "yes"}
