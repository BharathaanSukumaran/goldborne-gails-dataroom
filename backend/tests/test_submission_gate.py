from pathlib import Path

from scripts.test_submission import scan_for_secrets


ROOT = Path(__file__).resolve().parents[2]


def test_secret_scan_passes_repository_without_live_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert scan_for_secrets() == []


def test_required_local_env_files_are_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in gitignore
    assert "frontend/.env.local" in gitignore
