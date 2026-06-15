import json

import pytest

from scripts.extract_charges import extract_candidates, load_pages, merge_candidates
from scripts.process_documents import process_charge_instrument_sidecar
from scripts.review_charge_facts import apply_decisions, load_facts


def charge_source(local_path: str = "dataroom/raw/companies_house/ch-charge-0006.pdf"):
    return {
        "source_id": "ch-charge-0006",
        "title": "Registration of charge 060553930006 created 6 June 2022",
        "category": "charges",
        "issuer": "Companies House",
        "retrieved_at": "2026-06-15T08:51:42Z",
        "local_path": local_path,
    }


def charge_fact():
    return {
        "workspaceId": "gails-limited",
        "chargeCode": "060553930006",
        "displayChargeCode": "0605 5393 0006",
        "shortCode": "0006",
        "createdDate": "2022-06-06",
        "deliveredDate": None,
        "status": "outstanding",
        "satisfiedDate": None,
        "holder": "Glas Trust Corporation Limited",
        "description": None,
        "shortParticulars": None,
        "securedAssets": None,
        "securityType": None,
        "obligationsSecured": None,
        "instrumentSummary": None,
        "sourceId": "ch-charge-0006",
        "sourcePage": None,
        "sourceQuote": "Companies House charges metadata records this charge.",
        "reviewed": True,
        "fieldReview": {"holder": True, "createdDate": True, "status": True, "description": False, "securedAssets": False},
    }


def test_charge_instrument_processing_writes_explicit_error_when_raw_pdf_missing(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    result = process_charge_instrument_sidecar(charge_source(), tmp_path, processed_dir)

    assert result["status"] == "processing_failed"
    error_path = processed_dir / "ch-charge-0006.processing_error.json"
    error = json.loads(error_path.read_text(encoding="utf-8"))
    assert error["source_id"] == "ch-charge-0006"
    assert "Raw charge instrument is missing" in error["error"]


def test_extract_charges_writes_legal_candidates_unreviewed(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "ch-charge-0006.pages.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "source_id": "ch-charge-0006",
                        "page": 3,
                        "text": "Short particulars The debenture creates fixed charge and floating charge security over all assets and undertaking of the company. Obligations secured include all present and future liabilities.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    fact = charge_fact()

    candidates = extract_candidates(load_pages("ch-charge-0006", processed_dir))
    changed = merge_candidates(fact, candidates)

    assert changed > 0
    assert fact["securedAssets"] is not None
    assert fact["fieldReview"]["securedAssets"] is False
    assert fact["fieldReview"]["securityType"] is False
    assert fact["fieldEvidence"]["securedAssets"]["sourcePage"] == 3
    assert fact["fieldEvidence"]["securedAssets"]["reviewed"] is False


def test_review_charge_facts_approves_only_named_field(tmp_path):
    facts_path = tmp_path / "charge_facts.json"
    decisions_path = tmp_path / "decisions.json"
    fact = charge_fact()
    fact["description"] = "The debenture creates security over specified assets."
    fact["securedAssets"] = "All assets and undertaking."
    fact["fieldEvidence"] = {
        "description": {
            "sourceId": "ch-charge-0006",
            "sourcePage": 3,
            "sourceQuote": "The debenture creates security over specified assets.",
            "reviewed": False,
        },
        "securedAssets": {
            "sourceId": "ch-charge-0006",
            "sourcePage": 4,
            "sourceQuote": "All assets and undertaking.",
            "reviewed": False,
        },
    }
    facts_path.write_text(json.dumps({"facts": [fact]}), encoding="utf-8")
    decisions_path.write_text(
        json.dumps({"approved": [{"chargeCode": "060553930006", "field": "description", "sourceId": "ch-charge-0006", "sourcePage": 3}]}),
        encoding="utf-8",
    )

    facts = load_facts(facts_path)
    assert apply_decisions(facts, decisions_path) == 1

    reviewed = facts[0]
    assert reviewed["fieldReview"]["description"] is True
    assert reviewed["fieldReview"]["securedAssets"] is False
    assert reviewed["fieldEvidence"]["description"]["reviewed"] is True
    assert reviewed["sourcePage"] == 3


def test_review_charge_facts_rejects_approval_without_page_evidence(tmp_path):
    facts_path = tmp_path / "charge_facts.json"
    decisions_path = tmp_path / "decisions.json"
    fact = charge_fact()
    fact["description"] = "The debenture creates security over specified assets."
    facts_path.write_text(json.dumps({"facts": [fact]}), encoding="utf-8")
    decisions_path.write_text(
        json.dumps({"approved": [{"chargeCode": "0006", "field": "description", "sourceId": "ch-charge-0006"}]}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="without sourcePage and sourceQuote"):
        apply_decisions(load_facts(facts_path), decisions_path)
