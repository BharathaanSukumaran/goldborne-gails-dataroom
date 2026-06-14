from backend.app.qa.verifier import answer_unknown_policy, verify_answer


def test_verifier_rejects_unknown_source():
    result = verify_answer({"answer": "Known answer", "citations": [{"source_id": "missing"}], "facts_used": []}, manifest_sources=[])
    assert result.passed is False
    assert result.errors


def test_verifier_rejects_unsupported_money_claim():
    result = verify_answer({"answer": "Revenue was GBP 123,000.", "citations": [], "facts_used": [], "answer_type": "structured"})
    assert result.passed is False
    assert any("unsupported numeric claims" in error or "not reviewed and approved" in error for error in result.errors)


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
        financial_facts=[{"metric": "revenue", "value": "214000000", "period_end": "2024-02-29", "reviewed": True, "used_in_answers": True}],
        manifest_sources=[{"source_id": "accounts-2024"}],
    )
    assert result.passed is True
    assert result.errors == ()


def test_verifier_requires_ebitda_status_in_answer_text():
    result = verify_answer(
        {
            "answer": "EBITDA was GBP 35,000,000.",
            "citations": [{"source_id": "accounts-2024"}],
            "facts_used": [{"metric": "ebitda", "value": "35000000", "reported_or_computed": "computed", "reviewed": True, "used_in_answers": True}],
            "answer_type": "structured",
        },
        financial_facts=[{"metric": "ebitda", "value": "35000000", "reported_or_computed": "computed", "reviewed": True, "used_in_answers": True}],
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


def test_verifier_allows_formatted_major_currency_from_trusted_minor_unit_fact():
    trusted_fact = {
        "metric": "revenue",
        "period_end": "2025-02-28",
        "value": 15943210000,
        "reported_or_computed": "reported",
        "source_document_id": "accounts-2025",
        "reviewed": True,
        "used_in_answers": True,
    }
    result = verify_answer(
        {
            "answer": "For the period ended 2025-02-28: revenue was £159,432,100.00 (reported).",
            "citations": [{"source_document_id": "accounts-2025"}],
            "facts_used": [trusted_fact],
            "answer_type": "financial_metric",
        },
        financial_facts=[trusted_fact],
        manifest_sources=[{"source_id": "accounts-2025"}],
    )

    assert result.passed is True


def test_verifier_blocks_model_invented_revenue_and_returns_safe_unknown():
    result = verify_answer(
        {
            "answer": "Revenue was £160,000,000 and EBITDA was £12,000,000 (reported).",
            "citations": [{"source_document_id": "accounts-2025"}],
            "facts_used": [
                {
                    "metric": "revenue",
                    "period_end": "2025-02-28",
                    "value": 15943210000,
                    "reported_or_computed": "reported",
                    "reviewed": True,
                    "used_in_answers": True,
                },
                {
                    "metric": "ebitda",
                    "period_end": "2025-02-28",
                    "value": None,
                    "reported_or_computed": "unknown",
                    "reviewed": False,
                    "used_in_answers": False,
                },
            ],
            "answer_type": "financial_metric",
        },
        manifest_sources=[{"source_id": "accounts-2025"}],
    )

    assert result.passed is False
    assert result.answer["answer"] == "I cannot answer this from the current dataroom."
    assert result.answer["answer_type"] == "unknown"
    assert any("unsupported numeric claims" in error for error in result.errors)


def test_verifier_ignores_unusable_supplied_financial_facts_but_blocks_facts_used():
    supplied_unusable = {
        "metric": "revenue",
        "value": "214000000",
        "period_end": "2024-02-29",
        "reviewed": False,
        "used_in_answers": True,
    }

    result = verify_answer(
        {
            "answer": "Revenue was GBP 214,000,000.",
            "citations": [{"source_id": "accounts-2024"}],
            "facts_used": [],
            "answer_type": "structured",
        },
        financial_facts=[supplied_unusable],
        manifest_sources=[{"source_id": "accounts-2024"}],
    )
    assert result.passed is False
    assert "unsupported numeric claims" in result.errors[0]

    result = verify_answer(
        {
            "answer": "Revenue was GBP 214,000,000.",
            "citations": [{"source_id": "accounts-2024"}],
            "facts_used": [supplied_unusable],
            "answer_type": "structured",
        },
        financial_facts=[],
        manifest_sources=[{"source_id": "accounts-2024"}],
    )
    assert result.passed is False
    assert any("not reviewed and approved" in error for error in result.errors)



def test_verifier_blocks_answer_payload_financial_fact_without_trusted_row():
    result = verify_answer(
        {
            "answer": "Revenue was £159,432,100.00 (reported).",
            "citations": [{"source_document_id": "accounts-2025"}],
            "facts_used": [
                {
                    "metric": "revenue",
                    "period_end": "2025-02-28",
                    "value": 15943210000,
                    "reported_or_computed": "reported",
                    "source_document_id": "accounts-2025",
                    "reviewed": True,
                    "used_in_answers": True,
                }
            ],
            "answer_type": "financial_metric",
        },
        financial_facts=[],
        manifest_sources=[{"source_id": "accounts-2025"}],
    )

    assert result.passed is False
    assert any("unsupported financial facts_used" in error for error in result.errors)


def test_verifier_blocks_unsupported_debt_and_ebitda_values():
    trusted_revenue = {
        "metric": "revenue",
        "period_end": "2025-02-28",
        "value": 15943210000,
        "reported_or_computed": "reported",
        "source_document_id": "accounts-2025",
        "reviewed": True,
    }
    result = verify_answer(
        {
            "answer": "Revenue was £159,432,100.00 (reported), EBITDA was £12,000,000 (computed), and debt was £9,000,000 (reported).",
            "citations": [{"source_document_id": "accounts-2025"}],
            "facts_used": [trusted_revenue],
            "answer_type": "financial_metric",
        },
        financial_facts=[trusted_revenue],
        manifest_sources=[{"source_id": "accounts-2025"}],
    )

    assert result.passed is False
    assert any("unsupported numeric claims" in error for error in result.errors)


def test_verifier_blocks_covenant_headroom_claims():
    result = verify_answer(
        {
            "answer": "The company has comfortable covenant headroom under its leverage ratio.",
            "citations": [{"source_id": "ch-charge-0006"}],
            "facts_used": [],
            "answer_type": "structured",
        },
        manifest_sources=[{"source_id": "ch-charge-0006"}],
    )

    assert result.passed is False
    assert "unsupported covenant/headroom claim" in result.errors


def test_verifier_blocks_unsupported_lender_names_but_allows_supported_holder():
    unsupported = verify_answer(
        {
            "answer": "The registered security lender is Barclays Bank PLC.",
            "citations": [{"source_id": "ch-charge-0006"}],
            "facts_used": [],
            "answer_type": "charges_security",
        },
        charges=[{"charge_id": "0605 5393 0006", "created_on": "2022-06-06", "holder": "Glas Trust Corporation Limited"}],
        manifest_sources=[{"source_id": "ch-charge-0006"}],
    )
    assert unsupported.passed is False
    assert any("unsupported lender claim" in error for error in unsupported.errors)

    supported = verify_answer(
        {
            "answer": "Charge 0605 5393 0006 was created on 2022-06-06; holder/person entitled: Glas Trust Corporation Limited.",
            "citations": [{"source_id": "ch-charge-0006"}],
            "facts_used": [],
            "answer_type": "charges_security",
        },
        charges=[{"charge_id": "0605 5393 0006", "created_on": "2022-06-06", "holder": "Glas Trust Corporation Limited"}],
        manifest_sources=[{"source_id": "ch-charge-0006"}],
    )
    assert supported.passed is True


def test_verifier_rejects_empty_citation_source_id():
    result = verify_answer(
        {"answer": "Known answer", "citations": [{"source_id": ""}], "facts_used": [], "answer_type": "structured"},
        manifest_sources=[{"source_id": "accounts-2025"}],
    )

    assert result.passed is False
    assert any("cited source_id is not in manifest" in error for error in result.errors)
