from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_sources_and_source_detail():
    response = client.get("/sources")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["company_number"] == "06055393"
    assert len(body["sources"]) >= 12

    detail = client.get("/sources/ch-parent-accounts-2025")
    assert detail.status_code == 200
    assert "2025" in detail.json()["title"]


def test_ask_financial_unknown_until_reviewed_source_pdf():
    response = client.post("/ask", json={"question": "What was revenue and EBITDA in the last reported year?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "unknown"
    assert "revenue" in body["missing_information"]
    assert "EBITDA" in body["missing_information"]
    assert "unknown" in body["answer"]


def test_ask_charges_uses_structured_facts_and_citations():
    response = client.post("/ask", json={"question": "What charges are registered against the company and who holds them?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "Glas Trust Corporation Limited" in body["answer"]
    assert "0605 5393 0006" in body["answer"]
    assert body["citations"]
    assert body["citations"][0]["source_id"].startswith("ch-charge")


def test_unknown_private_information_refuses():
    response = client.post("/ask", json={"question": "What are the private bank covenants?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "unknown"
    assert "cannot answer" in body["answer"]


def test_ask_structured_routes_win_over_credit_narrative_terms():
    response = client.post("/ask", json={"question": "For a credit memo, what lenders or charges are registered?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "Glas Trust Corporation Limited" in body["answer"]


def test_ask_off_route_question_is_unavailable_not_retrieved_narrative(monkeypatch):
    captured = []

    def fake_synthesis(question, evidence):
        captured.append(evidence)
        return "Should not be used."

    monkeypatch.setattr("backend.app.main.synthesize_with_openai", fake_synthesis)
    response = client.post("/ask", json={"question": "What colour are the bakery walls?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "unknown"
    assert "not available" in body["answer"].lower()
    assert captured == []


def test_evals_run():
    response = client.post("/evals/run")
    body = response.json()
    assert response.status_code == 200
    assert body["results"]
    assert body["passed"] is True


def test_ask_narrative_uses_only_retrieved_manifest_backed_snippets(monkeypatch):
    captured = []

    def fake_synthesis(question, evidence):
        captured.append(evidence)
        return None

    monkeypatch.setattr("backend.app.main.synthesize_with_openai", fake_synthesis)
    response = client.post("/ask", json={"question": "What are the key expansion risks?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "credit_summary"
    assert body["citations"]
    manifest_ids = {source["source_id"] for source in client.get("/sources").json()["sources"]}
    assert {citation["source_id"] for citation in body["citations"]}.issubset(manifest_ids)
    assert captured
    assert all("snippet" in item and "source_id" in item for item in captured[0])
    assert all(item["source_id"] in manifest_ids for item in captured[0])
