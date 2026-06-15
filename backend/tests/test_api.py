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


def test_company_number_bare_field_answer():
    response = client.post("/ask", json={"question": "Company number"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "source_lookup"
    assert body["field_intent"] == "company_number"
    assert "06055393" in body["answer"]
    assert body["citations"][0]["source_id"] == "ch-profile-06055393"


def test_latest_accounts_metadata_answer_without_inventing_financials():
    response = client.post("/ask", json={"question": "Latest accounts"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "source_lookup"
    assert body["field_intent"] == "latest_accounts"
    assert "28 February 2025" in body["answer"] or "2025-02-28" in body["answer"]
    assert "processing" in body["answer"].lower()
    assert body["missing_information"]
    assert body["citations"][0]["source_id"] == "ch-parent-accounts-2025"


def test_filing_history_field_answer():
    response = client.post("/ask", json={"question": "Filing history"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "source_lookup"
    assert body["field_intent"] == "filing_history"
    assert "parent consolidated accounts" in body["answer"].lower()
    assert body["citations"][0]["source_id"] == "ch-filing-history-06055393"


def test_document_processing_status_field_answer():
    response = client.post("/ask", json={"question": "Document status"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "source_lookup"
    assert body["field_intent"] == "document_status"
    assert "processed sources" in body["answer"]
    assert "sources needing processing" in body["answer"]


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




def test_ask_charges_resolves_charge_number_reference():
    response = client.post("/ask", json={"question": "Who holds charge 0005?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "0605 5393 0005" in body["answer"]
    assert "0605 5393 0006" not in body["answer"]
    assert body["citations"][0]["source_id"] == "ch-charge-0005"


def test_ask_charges_resolves_year_reference():
    response = client.post("/ask", json={"question": "What is the status of the 2022 security?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "0605 5393 0006" in body["answer"]
    assert "2022-06-06" in body["answer"]
    assert "0605 5393 0005" not in body["answer"]


def test_ask_charges_resolves_latest_outstanding_reference():
    response = client.post("/ask", json={"question": "Who holds the latest outstanding charge?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "0605 5393 0006" in body["answer"]
    assert "0605 5393 0005" not in body["answer"]


def test_ask_charges_detects_field_intent_with_reference():
    response = client.post("/ask", json={"question": "Who holds 0006?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert "Glas Trust Corporation Limited" in body["answer"]
    assert "0605 5393 0006" in body["answer"]
    assert "0605 5393 0005" not in body["answer"]



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


def test_charge_holder_0006_specific_field_answer():
    response = client.post("/ask", json={"question": "Who holds charge 0006?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert body["field_intent"] == "charge_holder"
    assert body["resolved_charge_code"] == "060553930006"
    assert "Glas Trust Corporation Limited" in body["answer"]
    assert "created on" not in body["answer"].lower()
    assert body["citations"]


def test_charge_created_date_0006_specific_field_answer():
    response = client.post("/ask", json={"question": "When was charge 0006 created?"})
    body = response.json()
    assert response.status_code == 200
    assert body["field_intent"] == "charge_created_date"
    assert body["resolved_charge_code"] == "060553930006"
    assert "2022-06-06" in body["answer"]
    assert body["citations"]


def test_charge_status_0005_specific_field_answer():
    response = client.post("/ask", json={"question": "What is the status of charge 0005?"})
    body = response.json()
    assert response.status_code == 200
    assert body["field_intent"] == "charge_status"
    assert body["resolved_charge_code"] == "060553930005"
    assert "outstanding" in body["answer"].lower()
    assert body["citations"]


def test_bare_brief_description_answers_registered_charge_descriptions():
    response = client.post("/ask", json={"question": "Brief description"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert body["field_intent"] == "charge_description"
    assert "No specific land, ship, aircraft or intellectual property" in body["answer"]
    assert "Charge 0605 5393 0006" in body["answer"]
    assert "Charge 0605 5393 0005" in body["answer"]
    assert body["missing_information"] == []


def test_charge_description_0006_answers_reviewed_brief_description():
    response = client.post("/ask", json={"question": "What is the description of charge 0006?"})
    body = response.json()
    assert response.status_code == 200
    assert body["field_intent"] == "charge_description"
    assert body["resolved_charge_code"] == "060553930006"
    assert "no specific land, ship, aircraft or intellectual property" in body["answer"].lower()
    assert "contains fixed charge" in body["answer"].lower()
    assert "floating charge covers all the property or undertaking" in body["answer"].lower()
    assert "charge 0605 5393 0005" not in body["answer"]
    assert body["missing_information"] == []


def test_charge_assets_0006_answers_reviewed_companies_house_summary():
    response = client.post("/ask", json={"question": "What assets are secured by charge 0006?"})
    body = response.json()
    assert response.status_code == 200
    assert body["field_intent"] == "secured_assets"
    assert body["resolved_charge_code"] == "060553930006"
    assert "no specific land, ship, aircraft or intellectual property" in body["answer"].lower()
    assert "floating charge covers all the property or undertaking" in body["answer"].lower()
    assert body["missing_information"] == []


def test_charge_description_resolves_2021_and_2022_charge_years():
    response_2021 = client.post("/ask", json={"question": "What is the description of the 2021 charge?"})
    response_2022 = client.post("/ask", json={"question": "What is the description of the 2022 charge?"})
    body_2021 = response_2021.json()
    body_2022 = response_2022.json()
    assert body_2021["resolved_charge_code"] == "060553930005"
    assert body_2022["resolved_charge_code"] == "060553930006"
    assert "no specific land, ship, aircraft or intellectual property" in body_2021["answer"].lower()
    assert "no specific land, ship, aircraft or intellectual property" in body_2022["answer"].lower()


def test_charge_instrument_all_assets_answers_reviewed_summary():
    response = client.post("/ask", json={"question": "What does the charge instrument say about all assets?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert body["field_intent"] in {"secured_assets", "charge_instrument_summary"}
    assert "floating charge covers all the property or undertaking" in body["answer"].lower()
    assert body["missing_information"] == []


def test_what_is_charge_0006_for_routes_to_security_summary():
    response = client.post("/ask", json={"question": "What is charge 0006 for?"})
    body = response.json()
    assert response.status_code == 200
    assert body["answer_type"] == "charges_security"
    assert body["field_intent"] == "charge_instrument_summary"
    assert body["resolved_charge_code"] == "060553930006"
    assert "floating charge covers all the property or undertaking" in body["answer"].lower()
    assert "Glas Trust Corporation Limited" not in body["answer"]
