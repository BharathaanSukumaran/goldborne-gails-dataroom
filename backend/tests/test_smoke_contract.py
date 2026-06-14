from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_health_endpoint_smoke_contract():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_sources_endpoint_returns_indexed_sources():
    response = client.get("/sources")
    body = response.json()

    assert response.status_code == 200
    assert isinstance(body["sources"], list)
    assert len(body["sources"]) > 0


def test_ask_unknown_question_returns_unknown_or_not_available():
    response = client.post("/ask", json={"question": "What is the CFO's favourite lunch order?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "unknown"
    assert body["missing_information"]
    assert any(term in body["answer"].lower() for term in ["unknown", "not available", "cannot answer"])


def test_ask_financial_question_is_cited_or_structured_unknown():
    response = client.post("/ask", json={"question": "What was revenue and EBITDA in the latest reported year?"})
    body = response.json()

    assert response.status_code == 200
    if body["answer_type"] == "unknown":
        assert body["missing_information"]
        assert any("revenue" in item.lower() or "ebitda" in item.lower() for item in body["missing_information"])
        assert not body["citations"]
    else:
        assert body["citations"]
        assert body["facts_used"]


def test_ask_narrative_uses_backend_retrieval_path(monkeypatch):
    captured = []

    def fake_synthesis(question, evidence):
        captured.append({"question": question, "evidence": evidence})
        return "Backend synthesis used retrieved dataroom evidence."

    monkeypatch.setattr("backend.app.main.synthesize_with_openai", fake_synthesis)
    response = client.post("/ask", json={"question": "Summarise this company for a credit committee."})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == "Backend synthesis used retrieved dataroom evidence."
    assert body["answer_type"] == "credit_summary"
    assert body["citations"]
    assert captured
    assert captured[0]["evidence"]


def test_readme_documents_testing_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "run backend tests" in readme
    assert "pytest" in readme
    assert "run frontend checks" in readme
    assert "npm run lint" in readme
    assert "npm run build" in readme
    assert "run answer-quality evals" in readme
    assert "scripts/run_evals.py" in readme
