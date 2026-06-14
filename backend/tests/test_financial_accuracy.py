from decimal import Decimal

import pytest

from backend.app.facts import build_financial_answer, load_financial_facts_json, resolve_ebitda
from backend.app.facts.models import FinancialFact, MoneyAmount
from backend.app.facts.repository import FinancialFactsRepository
from scripts.extract_financials import csv_row_to_json_fact, load_csv, read_csv_records


def fact(metric, value, period_end="2025-02-28", reported_or_computed="reported", source_page=12, reviewed=True, used_in_answers=True):
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
        reviewed=reviewed,
        used_in_answers=used_in_answers,
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
    assert ebitda.reported_or_computed == "unavailable"
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


def test_required_financial_facts_json_loads_unknown_seed_facts():
    facts = load_financial_facts_json("backend/data/financial_facts.json")

    by_metric = {fact.metric: fact for fact in facts}
    assert {"revenue", "ebitda", "debt"}.issubset(by_metric)
    assert by_metric["revenue"].workspace_id == "gails-limited"
    assert by_metric["revenue"].reported_or_computed == "unavailable"
    assert by_metric["revenue"].value is None
    assert by_metric["ebitda"].reported_or_computed == "unavailable"
    assert {"turnover", "profit_before_tax", "cash", "borrowings", "depreciation", "amortisation"}.issubset(by_metric)
    assert not any(fact.reviewed or fact.used_in_answers for fact in facts)


def test_extract_financials_preserves_exact_decimal_values(tmp_path):
    csv_path = tmp_path / "facts.csv"
    csv_path.write_text(
        "periodEnd,metric,value,currency,unit,reportedOrComputed,sourceId,page,quote,extractionConfidence,reviewed,usedInAnswers\n"
        "2025-02-28,revenue,159432100.25,GBP,GBP,reported,ch-parent-accounts-2025,12,Revenue table,0.99,true,true\n",
        encoding="utf-8",
    )

    records = read_csv_records(csv_path)

    assert records[0]["value"] == "159432100.25"
    assert records[0]["reviewed"] is True
    assert records[0]["usedInAnswers"] is True

    database_path = tmp_path / "facts.sqlite"
    assert load_csv(csv_path, database_path) == 1
    stored = FinancialFactsRepository(database_path).get_fact("revenue", "2025-02-28")
    assert stored is not None
    assert stored.value is not None
    assert stored.value.minor_units == 15943210025
    assert stored.used_in_answers is True


def test_extract_financials_does_not_review_without_page_evidence():
    record = csv_row_to_json_fact(
        {
            "periodEnd": "2025-02-28",
            "metric": "borrowings",
            "value": "12345",
            "reportedOrComputed": "reported",
            "sourceId": "ch-parent-accounts-2025",
            "page": "",
            "quote": "Borrowings table",
            "reviewed": "true",
            "usedInAnswers": "true",
        }
    )

    assert record["reviewed"] is False
    assert record["usedInAnswers"] is False


def test_financial_answer_labels_ebitda_unknown_without_estimating():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("revenue", "159432100.00"))

    answer = build_financial_answer("What was revenue and EBITDA?", repository)

    assert answer["answer_type"] == "financial_metric"
    assert "£159,432,100.00" in answer["answer"]
    assert "EBITDA is unavailable" in answer["answer"]
    assert "EBITDA" in answer["missing_information"]
    assert all(item["metric"] != "ebitda" for item in answer["facts_used"])


def test_repository_can_store_unusable_fact_without_answering_from_it():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("revenue", "159432100.00", reviewed=False, used_in_answers=False))
    repository.add_fact(fact("debt", "9876543.21", reviewed=True, used_in_answers=False))

    assert repository.get_fact("revenue", "2025-02-28") is not None
    assert repository.get_fact("revenue", "2025-02-28", usable_only=True) is None
    assert repository.get_fact("debt", "2025-02-28", usable_only=True) is None

    answer = build_financial_answer("What was revenue and debt?", repository)

    assert answer["answer_type"] == "unknown"
    assert answer["facts_used"] == []
    assert "reviewed usable financial_facts" in answer["missing_information"]


def test_ebitda_does_not_compute_from_unreviewed_or_disabled_components():
    repository = FinancialFactsRepository()
    repository.add_fact(fact("operating_profit", "1000000", reviewed=True, used_in_answers=True))
    repository.add_fact(fact("depreciation", "200000", reviewed=False, used_in_answers=False))
    repository.add_fact(fact("amortisation", "50000", reviewed=True, used_in_answers=False))

    ebitda = resolve_ebitda(repository, "2025-02-28")

    assert ebitda.value is None
    assert ebitda.reported_or_computed == "unavailable"


def test_financial_facts_json_defaults_not_usable_for_answers():
    facts = load_financial_facts_json("backend/data/financial_facts.json")

    assert all(not fact.reviewed for fact in facts)
    assert all(not fact.used_in_answers for fact in facts)
    assert all(not fact.usable_in_answers for fact in facts)
