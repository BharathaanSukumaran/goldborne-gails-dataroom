from backend.app.evals.checks import evaluate_case


MANIFEST_SOURCE_IDS = {"ch-charge-0005", "ch-charge-0006"}


def test_generic_charge_list_fails_specific_description_eval():
    case = {
        "expect": {
            "answer_type_any_of": ["charges_security"],
            "charge_field": {
                "field_intent": "charge_description",
                "resolved_charge_code": "060553930006",
                "expected_source_id": "ch-charge-0006",
                "requires_unavailable": True,
                "forbid_generic_charge_list": True,
            },
        }
    }
    response = {
        "answer": "There are two outstanding charges: 0605 5393 0005 and 0605 5393 0006.",
        "answer_type": "charges_security",
        "field_intent": "charge_description",
        "resolved_charge_code": "060553930006",
        "citations": [
            {"source_id": "ch-charge-0006", "title": "Charge 0006", "snippet": "Charge metadata."}
        ],
        "missing_information": [],
    }

    failures = evaluate_case(case, response, MANIFEST_SOURCE_IDS)

    assert any("generic charge list" in failure for failure in failures)
    assert any("unavailable" in failure for failure in failures)


def test_unsupported_secured_assets_wording_fails_eval():
    case = {
        "expect": {
            "answer_type_any_of": ["charges_security"],
            "must_not_contain": ["all assets", "fixed charge", "floating charge"],
            "charge_field": {
                "field_intent": "secured_assets",
                "resolved_charge_code": "060553930006",
                "requires_unavailable": True,
                "forbid_generic_charge_list": True,
            },
        }
    }
    response = {
        "answer": "Charge 0605 5393 0006 secures all assets by fixed charge and floating charge.",
        "answer_type": "charges_security",
        "field_intent": "secured_assets",
        "resolved_charge_code": "060553930006",
        "citations": [],
        "missing_information": [],
    }

    failures = evaluate_case(case, response, MANIFEST_SOURCE_IDS)

    assert any("forbidden text 'all assets'" in failure for failure in failures)
    assert any("unavailable" in failure for failure in failures)


def test_charge_holder_answer_with_holder_evidence_passes_eval():
    case = {
        "expect": {
            "answer_type_any_of": ["charges_security"],
            "requires_citations": True,
            "charge_field": {
                "field_intent": "charge_holder",
                "resolved_charge_code": "060553930006",
                "expected_source_id": "ch-charge-0006",
                "must_contain": ["Glas Trust Corporation Limited"],
                "forbid_generic_charge_list": True,
            },
        }
    }
    response = {
        "answer": "Charge 0605 5393 0006 is listed with Glas Trust Corporation Limited as the person entitled / charge holder.",
        "answer_type": "charges_security",
        "field_intent": "charge_holder",
        "resolved_charge_code": "060553930006",
        "citations": [
            {"source_id": "ch-charge-0006", "title": "Charge 0006", "snippet": "Person entitled: Glas Trust Corporation Limited."}
        ],
        "missing_information": [],
    }

    assert evaluate_case(case, response, MANIFEST_SOURCE_IDS) == []
