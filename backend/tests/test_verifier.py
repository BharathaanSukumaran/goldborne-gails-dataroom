from backend.app.qa.verifier import answer_unknown_policy, verify_answer


def test_verifier_rejects_unknown_source():
    result = verify_answer({"answer": "Known answer", "citations": [{"source_id": "missing"}], "facts_used": []}, manifest_sources=[])
    assert result.passed is False
    assert result.errors


def test_verifier_rejects_unsupported_money_claim():
    result = verify_answer({"answer": "Revenue was GBP 123,000.", "citations": [], "facts_used": [], "answer_type": "structured"})
    assert result.passed is False
    assert "unsupported numeric claims" in result.errors[0]


def test_verifier_allows_dates_and_charge_numbers_when_supported_by_charges():
    result = verify_answer(
        {"answer": "Charge 0605 5393 0006 was created on 2022-06-06.", "citations": [], "facts_used": [], "answer_type": "structured"},
        charges=[{"charge_id": "0605 5393 0006", "created_on": "2022-06-06"}],
    )
    assert result.passed is True
    assert result.errors == ()



def test_verifier_allows_supported_financial_numeric_claim_with_manifest_source():
    result = verify_answer(
        {
            "answer": "Revenue was GBP 214,000,000.",
            "citations": [{"source_id": "accounts-2024"}],
            "facts_used": [],
            "answer_type": "structured",
        },
        financial_facts=[{"metric": "revenue", "value": "214000000", "period_end": "2024-02-29"}],
        manifest_sources=[{"source_id": "accounts-2024"}],
    )
    assert result.passed is True
    assert result.errors == ()


def test_verifier_requires_ebitda_status_in_answer_text():
    result = verify_answer(
        {
            "answer": "EBITDA was GBP 35,000,000.",
            "citations": [{"source_id": "accounts-2024"}],
            "facts_used": [{"metric": "ebitda", "value": "35000000", "reported_or_computed": "computed"}],
            "answer_type": "structured",
        },
        financial_facts=[{"metric": "ebitda", "value": "35000000", "reported_or_computed": "computed"}],
        manifest_sources=[{"source_id": "accounts-2024"}],
    )
    assert result.passed is False
    assert "EBITDA answer must state reported, computed, or unknown" in result.errors


def test_unknown_policy_keeps_covenant_questions_unknown_without_structured_covenants():
    decision = answer_unknown_policy("What are the financial covenants and leverage ratio headroom?")
    assert decision.should_answer_unknown is True
    assert decision.missing_information == ("structured_covenant_terms",)


def test_unknown_policy_keeps_private_information_questions_unknown():
    decision = answer_unknown_policy("What is the director's home address and date of birth?")
    assert decision.should_answer_unknown is True
    assert decision.missing_information == ("private_information_not_in_dataroom",)
