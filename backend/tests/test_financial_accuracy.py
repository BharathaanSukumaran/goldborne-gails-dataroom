from decimal import Decimal

import pytest

from backend.app.facts import build_financial_answer, resolve_ebitda
from backend.app.facts.models import FinancialFact, MoneyAmount
from backend.app.facts.repository import FinancialFactsRepository


def fact(metric, value, period_end="2025-02-28", reported_or_computed="reported", source_page=12):
    return FinancialFact(
        period_end=period_end,
        metric=metric,
        value=MoneyAmount.from_major_units(value),
        unit="minor_units",
        reported_or_computed=reported_or_computed,
        formula=None,
        source_document_id=f"accounts-{period_end}",
        source_page=source_page,
        source_quote=f"{metric} {value}",
        extraction_confidence=Decimal("0.99"),
        reviewed=True,
    )


def test_money_values_are_stored_as_integer_minor_units():
    amount = MoneyAmount.from_major_units(Decimal("123456789.01"))

    assert amount.minor_units == 12345678901
    assert amount.format() == "£123,456,789.01"


def test_money_values_reject_float_input():
    with pytest.raises(TypeError):
        MoneyAmount.from_major_units(12.34)


def test_repository_round_trips_exact_financial_fact():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("revenue", "159000000.25"))

    stored = repository.get_fact("revenue", "2025-02-28")

    assert stored is not None
    assert stored.value is not None
    assert stored.value.minor_units == 15900000025
    assert stored.source_document_id == "accounts-2025-02-28"
    assert stored.source_quote == "revenue 159000000.25"


def test_ebitda_uses_reported_value_before_computed_components():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("ebitda", "7500000"))
    repository.add_fact(fact("operating_profit", "1000000"))
    repository.add_fact(fact("depreciation", "2000000"))
    repository.add_fact(fact("amortisation", "3000000"))

    ebitda = resolve_ebitda(repository, "2025-02-28")

    assert ebitda.value is not None
    assert ebitda.value.minor_units == 750000000
    assert ebitda.reported_or_computed == "reported"
    assert ebitda.formula is None


def test_ebitda_computes_only_when_all_components_present():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("operating_profit", "1000000"))
    repository.add_fact(fact("depreciation", "200000"))
    repository.add_fact(fact("amortisation", "50000"))

    ebitda = resolve_ebitda(repository, "2025-02-28")

    assert ebitda.value is not None
    assert ebitda.value.minor_units == 125000000
    assert ebitda.reported_or_computed == "computed"
    assert ebitda.formula == "operating_profit + depreciation + amortisation"


def test_ebitda_unknown_when_report_and_components_are_missing():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("operating_profit", "1000000"))

    ebitda = resolve_ebitda(repository, "2025-02-28")

    assert ebitda.value is None
    assert ebitda.reported_or_computed == "unknown"
    assert "not reported" in ebitda.source_quote


def test_financial_answer_uses_database_values_not_approximated_model_output():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("revenue", "159432100.00"))
    repository.add_fact(fact("debt", "9876543.21"))
    repository.add_fact(fact("operating_profit", "12000000.00"))
    repository.add_fact(fact("depreciation", "345678.90"))
    repository.add_fact(fact("amortisation", "1000.10"))

    answer = build_financial_answer(
        "What was revenue, EBITDA and debt in the last reported year?",
        repository,
        model_draft="Revenue was about £160m, EBITDA around £12m, and debt roughly £10m.",
    )

    assert "£159,432,100.00" in answer["answer"]
    assert "£12,346,679.00" in answer["answer"]
    assert "£9,876,543.21" in answer["answer"]
    assert "£160m" not in answer["answer"]
    assert "around" not in answer["answer"]
    assert answer["facts_used"][0]["value"] == 15943210000
    assert {citation["source_document_id"] for citation in answer["citations"]} == {"accounts-2025-02-28"}
